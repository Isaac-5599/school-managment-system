"""All HTTP API handlers, with role-based access enforced per route and per record."""

import re
from datetime import date

from . import auth, reports
from .http_util import ApiError, csv_response

DEFAULT_STUDENT_PASSWORD = "Student@123"
SORT_WHITELIST = {
    "students": {"admission_no": "s.admission_no", "name": "s.last_name", "class": "c.name"},
    "teachers": {"staff_no": "t.staff_no", "name": "t.last_name"},
}
TERMS = ("First Term", "Second Term", "Third Term")
TODAY = date.today().isoformat()


# --------------------------------------------------------------------------
# field validation helpers
# --------------------------------------------------------------------------

def _str(data, key, maxlen=200, required=True, default=None):
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError(400, f"Field '{key}' is required")
        return default
    return str(value).strip()[:maxlen]


def _choice(data, key, allowed, required=True, default=None):
    value = _str(data, key, required=required, default=default)
    if value is None:
        return None
    if value not in allowed:
        raise ApiError(400, f"Field '{key}' must be one of: {', '.join(allowed)}")
    return value


def _num(data, key, required=True, minimum=None, maximum=None, default=None):
    value = data.get(key)
    if value is None or value == "":
        if required:
            raise ApiError(400, f"Field '{key}' is required")
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ApiError(400, f"Field '{key}' must be a number")
    if minimum is not None and number < minimum:
        raise ApiError(400, f"Field '{key}' must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ApiError(400, f"Field '{key}' cannot be more than {maximum}")
    return number


def _date(data, key, required=True, default=None):
    value = _str(data, key, maxlen=10, required=required, default=default)
    if value is None:
        return None
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        raise ApiError(400, f"Field '{key}' must be a date in YYYY-MM-DD format")
    return value


def _email(data, key, required=False, default=None):
    value = _str(data, key, maxlen=200, required=required, default=default)
    if value and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        raise ApiError(400, f"Field '{key}' must be a valid email address")
    return value


# --------------------------------------------------------------------------
# context helpers
# --------------------------------------------------------------------------

def teacher_row(ctx):
    return ctx.db.execute("SELECT * FROM teachers WHERE user_id = ?", (ctx.user["user_id"],)).fetchone()


def student_row(ctx):
    return ctx.db.execute("SELECT * FROM students WHERE user_id = ?", (ctx.user["user_id"],)).fetchone()


def is_admin(ctx):
    return ctx.user and ctx.user["role"] == "admin"


def require(ctx, minimum):
    if not auth.has_role(ctx.user["role"], minimum):
        raise ApiError(403, "Your role does not have permission to perform this action")


def get_or_404(db, sql, params, label):
    row = db.execute(sql, params).fetchone()
    if not row:
        raise ApiError(404, f"{label} not found")
    return row


def term_params(ctx):
    term = ctx.get("term", TERMS[0])
    if term not in TERMS:
        raise ApiError(400, "Invalid term")
    year = ctx.get("academic_year", "2025/2026")
    return term, year


def class_id_param(ctx, required=True):
    raw = ctx.get("class_id")
    if raw in (None, "", "0"):
        if required:
            raise ApiError(400, "Field 'class_id' is required")
        return None
    try:
        return int(raw)
    except ValueError:
        raise ApiError(400, "Field 'class_id' must be an integer")


def date_param(ctx, name):
    raw = ctx.get(name)
    if not raw:
        return None
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        raise ApiError(400, f"Query parameter '{name}' must be a date in YYYY-MM-DD format")
    return raw


def can_teach(ctx, class_id, subject_id):
    if is_admin(ctx):
        return True
    teacher = teacher_row(ctx)
    if not teacher:
        return False
    return ctx.db.execute(
        "SELECT 1 FROM teacher_assignments WHERE teacher_id = ? AND class_id = ? AND subject_id = ?",
        (teacher["id"], class_id, subject_id),
    ).fetchone() is not None


def unique_or_409(db, sql, params, label):
    if db.execute(sql, params).fetchone():
        raise ApiError(409, f"That {label} already exists")


# --------------------------------------------------------------------------
# auth
# --------------------------------------------------------------------------

def login(ctx):
    username = _str(ctx.data, "username", maxlen=60)
    password = _str(ctx.data, "password", maxlen=200)
    result = auth.login(ctx.db, username, password)
    if not result:
        raise ApiError(401, "Invalid username or password")
    ctx.set_cookie = result.pop("token")
    auth.audit(ctx.db, result["user_id"], "login", f"role={result['role']}")
    return {
        **result,
        "links": _role_links(result["role"]),
    }


def logout(ctx):
    if ctx.token:
        auth.destroy_session(ctx.token)
    ctx.clear_cookie = True
    return {"ok": True}


def me(ctx):
    row = ctx.db.execute(
        "SELECT id, full_name, username, email, role FROM users WHERE id = ?", (ctx.user["user_id"],)
    ).fetchone()
    payload = dict(row)
    payload["links"] = _role_links(row["role"])
    if row["role"] == "student":
        student = student_row(ctx)
        payload["record_id"] = student["id"] if student else None
    elif row["role"] == "teacher":
        teacher = teacher_row(ctx)
        payload["record_id"] = teacher["id"] if teacher else None
    return payload


def _role_links(role):
    if role == "student":
        return ["dashboard", "my-results", "my-attendance", "my-fees"]
    if role == "teacher":
        return ["dashboard", "students", "teachers", "classes", "subjects", "exams", "attendance", "reports"]
    return [
        "dashboard", "students", "teachers", "classes", "subjects", "exams",
        "attendance", "fees", "reports", "users",
    ]


def change_own_password(ctx):
    current = _str(ctx.data, "current_password", maxlen=200)
    new = _str(ctx.data, "new_password", maxlen=200)
    if len(new) < 8:
        raise ApiError(400, "New password must be at least 8 characters")
    row = ctx.db.execute("SELECT password_hash, password_salt FROM users WHERE id = ?", (ctx.user["user_id"],)).fetchone()
    if not auth.verify_password(current, row["password_hash"], row["password_salt"]):
        raise ApiError(401, "Current password is incorrect")
    digest, salt = auth.hash_password(new)
    ctx.db.execute("UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?", (digest, salt, ctx.user["user_id"]))
    auth.audit(ctx.db, ctx.user["user_id"], "password_changed")
    return {"ok": True}


# --------------------------------------------------------------------------
# dashboard
# --------------------------------------------------------------------------

def dashboard(ctx):
    db = ctx.db
    term, year = term_params(ctx)
    counts = {
        "students": db.execute("SELECT COUNT(*) n FROM students WHERE status = 'active'").fetchone()["n"],
        "teachers": db.execute("SELECT COUNT(*) n FROM teachers WHERE status = 'active'").fetchone()["n"],
        "classes": db.execute("SELECT COUNT(*) n FROM classes").fetchone()["n"],
        "subjects": db.execute("SELECT COUNT(*) n FROM subjects").fetchone()["n"],
    }

    if ctx.user["role"] == "student":
        student = student_row(ctx)
        if not student:
            raise ApiError(403, "No student record is linked to your account")
        report = reports.student_report(db, student, term, year)
        return {
            "role": "student",
            "term": term,
            "academic_year": year,
            "profile": dict(student),
            "average": report["overall_average"],
            "grade": report["overall_grade"],
            "position": report["position"],
            "class_size": report["class_size"],
            "attendance": report["attendance"],
            "fees": report["fees"],
            "subjects": report["subjects"],
        }

    fees = db.execute(
        "SELECT COALESCE(SUM(amount_due),0) due, COALESCE(SUM(amount_paid),0) paid, "
        "COALESCE(SUM(balance),0) outstanding FROM v_fee_balances WHERE term = ? AND academic_year = ?",
        (term, year),
    ).fetchone()
    attendance = db.execute(
        "SELECT COALESCE(ROUND(AVG(rate),1),0) rate FROM v_attendance_summary"
    ).fetchone()
    class_performance = db.execute(
        "SELECT c.name, ROUND(AVG(v.average),2) average, COUNT(*) counted FROM ("
        "  SELECT m.student_id, ROUND(100.0*SUM(m.score)/SUM(e.max_marks),2) average "
        "  FROM marks m JOIN exam_sessions e ON e.id = m.exam_id "
        "  WHERE e.term = ? AND e.academic_year = ? GROUP BY m.student_id"
        ") v JOIN students s ON s.id = v.student_id JOIN classes c ON c.id = s.class_id GROUP BY c.id",
        (term, year),
    ).fetchall()
    recent = db.execute(
        "SELECT u.full_name AS actor, a.action, a.detail, a.at FROM audit_log a "
        "LEFT JOIN users u ON u.id = a.user_id ORDER BY a.id DESC LIMIT 8"
    ).fetchall()

    payload = {
        "role": ctx.user["role"],
        "term": term,
        "academic_year": year,
        "counts": counts,
        "fees": dict(fees),
        "attendance_rate": attendance["rate"],
        "class_performance": [dict(r) for r in class_performance],
        "recent_activity": [dict(r) for r in recent],
    }
    if ctx.user["role"] == "teacher":
        teacher = teacher_row(ctx)
        payload["my_classes"] = (
            [dict(r) for r in db.execute(
                "SELECT c.name, COUNT(s.id) students FROM teacher_assignments ta "
                "JOIN classes c ON c.id = ta.class_id "
                "LEFT JOIN students s ON s.class_id = c.id AND s.status = 'active' "
                "WHERE ta.teacher_id = ? GROUP BY c.id ORDER BY c.name", (teacher["id"],)
            ).fetchall()]
            if teacher else []
        )
    return payload


# --------------------------------------------------------------------------
# students
# --------------------------------------------------------------------------

STUDENT_SELECT = (
    "SELECT s.*, c.name AS class_name FROM students s "
    "LEFT JOIN classes c ON c.id = s.class_id"
)


def list_students(ctx):
    require(ctx, "teacher")
    where, params = ["1=1"], []
    if ctx.get("class_id"):
        where.append("s.class_id = ?")
        params.append(int(ctx.get("class_id")))
    if ctx.get("status"):
        where.append("s.status = ?")
        params.append(ctx.get("status"))
    search = ctx.get("q")
    if search:
        where.append("(s.first_name LIKE ? OR s.last_name LIKE ? OR s.admission_no LIKE ?)")
        params += [f"%{search}%"] * 3
    column = SORT_WHITELIST["students"].get(ctx.get("sort", "admission_no"), "s.admission_no")
    return _paged(ctx, STUDENT_SELECT + " WHERE " + " AND ".join(where) + f" ORDER BY {column}, s.id", params)


def _paged(ctx, sql, params):
    total = ctx.db.execute("SELECT COUNT(*) n FROM (%s)" % sql, params).fetchone()["n"]
    try:
        page = max(1, int(ctx.get("page", 1)))
        size = min(200, max(1, int(ctx.get("page_size", 50))))
    except ValueError:
        raise ApiError(400, "page and page_size must be integers")
    rows = ctx.db.execute(sql + " LIMIT ? OFFSET ?", params + [size, (page - 1) * size]).fetchall()
    return {"total": total, "page": page, "page_size": size, "rows": [dict(r) for r in rows]}


def get_student(ctx):
    sid = int(ctx.params["sid"])
    student = get_or_404(ctx.db, STUDENT_SELECT + " WHERE s.id = ?", (sid,), "Student")
    if ctx.user["role"] == "student":
        mine = student_row(ctx)
        if not mine or mine["id"] != sid:
            raise ApiError(403, "Students may only view their own record")
    term, year = term_params(ctx)
    return {
        "student": dict(student),
        "report": reports.student_report(ctx.db, student, term, year),
    }


def create_student(ctx):
    require(ctx, "admin")
    db = ctx.db
    first = _str(ctx.data, "first_name", maxlen=60)
    last = _str(ctx.data, "last_name", maxlen=60)
    gender = _choice(ctx.data, "gender", ("Male", "Female"))
    class_id = int(_num(ctx.data, "class_id"))
    get_or_404(db, "SELECT 1 id FROM classes WHERE id = ?", (class_id,), "Class")

    admission = _str(ctx.data, "admission_no", maxlen=40, required=False)
    if not admission:
        next_no = db.execute("SELECT COUNT(*) n FROM students").fetchone()["n"] + 1
        year = db.execute("SELECT academic_year FROM classes WHERE id = ?", (class_id,)).fetchone()["academic_year"]
        admission = f"SMS/{year[:4]}/{next_no:03d}"
        while db.execute("SELECT 1 FROM students WHERE admission_no = ?", (admission,)).fetchone():
            next_no += 1
            admission = f"SMS/{year[:4]}/{next_no:03d}"

    unique_or_409(db, "SELECT 1 FROM students WHERE admission_no = ?", (admission,), "admission number")

    cur = db.execute(
        "INSERT INTO students (admission_no, class_id, first_name, last_name, gender, date_of_birth, "
        "guardian_name, guardian_phone, guardian_email, enrollment_date, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            admission, class_id, first, last, gender,
            _date(ctx.data, "date_of_birth", required=False),
            _str(ctx.data, "guardian_name", required=False),
            _str(ctx.data, "guardian_phone", required=False),
            _email(ctx.data, "guardian_email"),
            _date(ctx.data, "enrollment_date", required=False, default=None) or TODAY,
            _choice(ctx.data, "status", ("active", "graduated", "withdrawn"), required=False, default="active"),
        ),
    )
    student_id = cur.lastrowid

    create_login = ctx.data.get("create_login", True)
    credentials = None
    if create_login:
        username = "std-" + re.sub(r"[^A-Za-z0-9]+", "-", admission).strip("-").lower()
        if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            username = f"{username}-{student_id}"
        digest, salt = auth.hash_password(DEFAULT_STUDENT_PASSWORD)
        uid = db.execute(
            "INSERT INTO users (full_name, username, email, password_hash, password_salt, role) "
            "VALUES (?,?,?,?,?,?)",
            (f"{first} {last}", username, _email(ctx.data, "email"), digest, salt, "student"),
        ).lastrowid
        db.execute("UPDATE students SET user_id = ? WHERE id = ?", (uid, student_id))
        credentials = {"username": username, "password": DEFAULT_STUDENT_PASSWORD}

    auth.audit(db, ctx.user["user_id"], "student_created", admission)
    return {"id": student_id, "admission_no": admission, "credentials": credentials}


def update_student(ctx):
    require(ctx, "admin")
    sid = int(ctx.params["sid"])
    student = get_or_404(ctx.db, "SELECT * FROM students WHERE id = ?", (sid,), "Student")
    db = ctx.db

    fields = {
        "first_name": _str(ctx.data, "first_name", maxlen=60),
        "last_name": _str(ctx.data, "last_name", maxlen=60),
        "gender": _choice(ctx.data, "gender", ("Male", "Female")),
        "class_id": int(_num(ctx.data, "class_id")),
        "date_of_birth": _date(ctx.data, "date_of_birth", required=False),
        "guardian_name": _str(ctx.data, "guardian_name", required=False),
        "guardian_phone": _str(ctx.data, "guardian_phone", required=False),
        "guardian_email": _email(ctx.data, "guardian_email"),
        "status": _choice(ctx.data, "status", ("active", "graduated", "withdrawn"), required=False,
                          default=student["status"]),
    }
    get_or_404(db, "SELECT 1 id FROM classes WHERE id = ?", (fields["class_id"],), "Class")
    db.execute(
        "UPDATE students SET first_name=:first_name, last_name=:last_name, gender=:gender, "
        "class_id=:class_id, date_of_birth=:date_of_birth, guardian_name=:guardian_name, "
        "guardian_phone=:guardian_phone, guardian_email=:guardian_email, status=:status WHERE id=:sid",
        {**fields, "sid": sid},
    )
    if db.execute("SELECT 1 FROM users WHERE id = ?", (student["user_id"],)).fetchone() and fields["class_id"] != student["class_id"]:
        db.execute(
            "DELETE FROM marks WHERE student_id = ? AND exam_id NOT IN "
            "(SELECT id FROM exam_sessions WHERE class_id = ?)", (sid, fields["class_id"])
        )
    auth.audit(db, ctx.user["user_id"], "student_updated", student["admission_no"])
    return {"ok": True}


def delete_student(ctx):
    require(ctx, "admin")
    sid = int(ctx.params["sid"])
    student = get_or_404(ctx.db, "SELECT * FROM students WHERE id = ?", (sid,), "Student")
    db = ctx.db
    user_id = student["user_id"]
    db.execute("DELETE FROM students WHERE id = ?", (sid,))
    if user_id:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    auth.audit(db, ctx.user["user_id"], "student_deleted", student["admission_no"])
    return {"ok": True}


# --------------------------------------------------------------------------
# teachers
# --------------------------------------------------------------------------

TEACHER_SELECT = (
    "SELECT t.*, u.username, (SELECT COUNT(*) FROM teacher_assignments ta WHERE ta.teacher_id = t.id) "
    "AS assignment_count FROM teachers t LEFT JOIN users u ON u.id = t.user_id"
)


def list_teachers(ctx):
    require(ctx, "teacher")
    where, params = ["1=1"], []
    search = ctx.get("q")
    if search:
        where.append("(t.first_name LIKE ? OR t.last_name LIKE ? OR t.staff_no LIKE ?)")
        params += [f"%{search}%"] * 3
    column = SORT_WHITELIST["teachers"].get(ctx.get("sort", "staff_no"), "t.staff_no")
    return _paged(ctx, TEACHER_SELECT + " WHERE " + " AND ".join(where) + f" ORDER BY {column}, t.id", params)


def get_teacher(ctx):
    tid = int(ctx.params["tid"])
    teacher = get_or_404(ctx.db, TEACHER_SELECT + " WHERE t.id = ?", (tid,), "Teacher")
    assignments = ctx.db.execute(
        "SELECT ta.id, c.name AS class_name, sub.name AS subject_name, sub.id AS subject_id, c.id AS class_id "
        "FROM teacher_assignments ta JOIN classes c ON c.id = ta.class_id JOIN subjects sub ON sub.id = ta.subject_id "
        "WHERE ta.teacher_id = ? ORDER BY c.name, sub.name", (tid,),
    ).fetchall()
    return {"teacher": dict(teacher), "assignments": [dict(a) for a in assignments]}


def create_teacher(ctx):
    require(ctx, "admin")
    db = ctx.db
    first = _str(ctx.data, "first_name", maxlen=60)
    last = _str(ctx.data, "last_name", maxlen=60)
    staff_no = _str(ctx.data, "staff_no", maxlen=40, required=False)
    if not staff_no:
        count = db.execute("SELECT COUNT(*) n FROM teachers").fetchone()["n"] + 1
        staff_no = f"STF/{count:03d}"
    unique_or_409(db, "SELECT 1 FROM teachers WHERE staff_no = ?", (staff_no,), "staff number")

    email = _email(ctx.data, "email")
    username = None
    user_id = None
    if ctx.data.get("create_login", True):
        base = f"{first[0]}{last}".lower()
        username = re.sub(r"[^a-z0-9]", "", base) or "teacher"
        candidate = username
        suffix = 1
        while db.execute("SELECT 1 FROM users WHERE username = ?", (candidate,)).fetchone():
            suffix += 1
            candidate = f"{username}{suffix}"
        digest, salt = auth.hash_password("Teach@123")
        user_id = db.execute(
            "INSERT INTO users (full_name, username, email, password_hash, password_salt, role) VALUES (?,?,?,?,?,?)",
            (f"{first} {last}", candidate, email, digest, salt, "teacher"),
        ).lastrowid

    cur = db.execute(
        "INSERT INTO teachers (staff_no, user_id, first_name, last_name, email, phone, qualification, "
        "specialization, hire_date, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            staff_no, user_id, first, last, email,
            _str(ctx.data, "phone", maxlen=40, required=False),
            _str(ctx.data, "qualification", maxlen=100, required=False),
            _str(ctx.data, "specialization", maxlen=100, required=False),
            _date(ctx.data, "hire_date", required=False),
            _choice(ctx.data, "status", ("active", "on leave", "retired"), required=False, default="active"),
        ),
    )
    auth.audit(db, ctx.user["user_id"], "teacher_created", staff_no)
    credentials = {"username": username, "password": "Teach@123"} if username else None
    return {"id": cur.lastrowid, "staff_no": staff_no, "credentials": credentials}


def update_teacher(ctx):
    require(ctx, "admin")
    tid = int(ctx.params["tid"])
    get_or_404(ctx.db, "SELECT id FROM teachers WHERE id = ?", (tid,), "Teacher")
    ctx.db.execute(
        "UPDATE teachers SET first_name=?, last_name=?, email=?, phone=?, qualification=?, "
        "specialization=?, hire_date=?, status=? WHERE id=?",
        (
            _str(ctx.data, "first_name", maxlen=60), _str(ctx.data, "last_name", maxlen=60),
            _email(ctx.data, "email"), _str(ctx.data, "phone", maxlen=40, required=False),
            _str(ctx.data, "qualification", maxlen=100, required=False),
            _str(ctx.data, "specialization", maxlen=100, required=False),
            _date(ctx.data, "hire_date", required=False),
            _choice(ctx.data, "status", ("active", "on leave", "retired")),
            tid,
        ),
    )
    auth.audit(ctx.db, ctx.user["user_id"], "teacher_updated", str(tid))
    return {"ok": True}


def delete_teacher(ctx):
    require(ctx, "admin")
    tid = int(ctx.params["tid"])
    teacher = get_or_404(ctx.db, "SELECT * FROM teachers WHERE id = ?", (tid,), "Teacher")
    if teacher["user_id"]:
        ctx.db.execute("DELETE FROM users WHERE id = ?", (teacher["user_id"],))
    ctx.db.execute("DELETE FROM teachers WHERE id = ?", (tid,))
    auth.audit(ctx.db, ctx.user["user_id"], "teacher_deleted", teacher["staff_no"])
    return {"ok": True}


# --------------------------------------------------------------------------
# classes and subjects
# --------------------------------------------------------------------------

def list_classes(ctx):
    rows = ctx.db.execute(
        "SELECT c.*, t.first_name || ' ' || t.last_name AS homeroom_name, "
        "(SELECT COUNT(*) FROM students s WHERE s.class_id = c.id AND s.status = 'active') AS student_count "
        "FROM classes c LEFT JOIN teachers t ON t.id = c.homeroom_teacher_id ORDER BY c.name"
    ).fetchall()
    return {"rows": [dict(r) for r in rows]}


def create_class(ctx):
    require(ctx, "admin")
    name = _str(ctx.data, "name", maxlen=40)
    unique_or_409(ctx.db, "SELECT 1 FROM classes WHERE name = ?", (name,), "class name")
    cid = ctx.db.execute(
        "INSERT INTO classes (name, level, academic_year, homeroom_teacher_id) VALUES (?,?,?,?)",
        (
            name, _str(ctx.data, "level", maxlen=20),
            _str(ctx.data, "academic_year", maxlen=20, default=None) or "2025/2026",
            int(ctx.data["homeroom_teacher_id"]) if ctx.data.get("homeroom_teacher_id") else None,
        ),
    ).lastrowid
    auth.audit(ctx.db, ctx.user["user_id"], "class_created", name)
    return {"id": cid}


def update_class(ctx):
    require(ctx, "admin")
    cid = int(ctx.params["cid"])
    get_or_404(ctx.db, "SELECT id FROM classes WHERE id = ?", (cid,), "Class")
    ctx.db.execute(
        "UPDATE classes SET name=?, level=?, academic_year=?, homeroom_teacher_id=? WHERE id=?",
        (
            _str(ctx.data, "name", maxlen=40), _str(ctx.data, "level", maxlen=20),
            _str(ctx.data, "academic_year", maxlen=20),
            int(ctx.data["homeroom_teacher_id"]) if ctx.data.get("homeroom_teacher_id") else None,
            cid,
        ),
    )
    auth.audit(ctx.db, ctx.user["user_id"], "class_updated", str(cid))
    return {"ok": True}


def delete_class(ctx):
    require(ctx, "admin")
    cid = int(ctx.params["cid"])
    if ctx.db.execute("SELECT 1 FROM students WHERE class_id = ?", (cid,)).fetchone():
        raise ApiError(409, "This class still has students enrolled. Move them first.")
    ctx.db.execute("DELETE FROM classes WHERE id = ?", (cid,))
    auth.audit(ctx.db, ctx.user["user_id"], "class_deleted", str(cid))
    return {"ok": True}


def class_subjects(ctx):
    cid = int(ctx.params["cid"])
    rows = ctx.db.execute(
        "SELECT cs.subject_id, s.name, s.code, s.category, t.first_name || ' ' || t.last_name AS teacher "
        "FROM class_subjects cs JOIN subjects s ON s.id = cs.subject_id "
        "LEFT JOIN teacher_assignments ta ON ta.class_id = cs.class_id AND ta.subject_id = cs.subject_id "
        "LEFT JOIN teachers t ON t.id = ta.teacher_id WHERE cs.class_id = ? ORDER BY s.name", (cid,),
    ).fetchall()
    return {"rows": [dict(r) for r in rows]}


def assign_class_subject(ctx):
    require(ctx, "admin")
    cid = int(ctx.params["cid"])
    subject_id = int(_num(ctx.data, "subject_id"))
    get_or_404(ctx.db, "SELECT 1 id FROM classes WHERE id = ?", (cid,), "Class")
    get_or_404(ctx.db, "SELECT 1 id FROM subjects WHERE id = ?", (subject_id,), "Subject")
    try:
        ctx.db.execute("INSERT INTO class_subjects (class_id, subject_id) VALUES (?,?)", (cid, subject_id))
    except Exception:
        raise ApiError(409, "That subject is already assigned to this class")
    return {"ok": True}


def unassign_class_subject(ctx):
    require(ctx, "admin")
    ctx.db.execute("DELETE FROM class_subjects WHERE class_id = ? AND subject_id = ?",
                   (int(ctx.params["cid"]), int(ctx.params["subject_id"])))
    return {"ok": True}


def list_subjects(ctx):
    rows = ctx.db.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    return {"rows": [dict(r) for r in rows]}


def create_subject(ctx):
    require(ctx, "admin")
    name = _str(ctx.data, "name", maxlen=60)
    code = _str(ctx.data, "code", maxlen=12).upper()
    unique_or_409(ctx.db, "SELECT 1 FROM subjects WHERE code = ?", (code,), "subject code")
    sid = ctx.db.execute(
        "INSERT INTO subjects (name, code, category) VALUES (?,?,?)",
        (name, code, _choice(ctx.data, "category", ("core", "elective"), required=False, default="core")),
    ).lastrowid
    auth.audit(ctx.db, ctx.user["user_id"], "subject_created", code)
    return {"id": sid}


def delete_subject(ctx):
    require(ctx, "admin")
    sid = int(ctx.params["sid"])
    if ctx.db.execute("SELECT 1 FROM class_subjects WHERE subject_id = ?", (sid,)).fetchone():
        raise ApiError(409, "This subject is assigned to one or more classes.")
    ctx.db.execute("DELETE FROM subjects WHERE id = ?", (sid,))
    return {"ok": True}


def list_assignments(ctx):
    sql = (
        "SELECT ta.id, ta.teacher_id, ta.class_id, ta.subject_id, t.staff_no, "
        "t.first_name || ' ' || t.last_name AS teacher, c.name AS class_name, s.name AS subject_name "
        "FROM teacher_assignments ta JOIN teachers t ON t.id = ta.teacher_id "
        "JOIN classes c ON c.id = ta.class_id JOIN subjects s ON s.id = ta.subject_id"
    )
    params = []
    if ctx.user["role"] == "teacher":
        teacher = teacher_row(ctx)
        sql += " WHERE ta.teacher_id = ?"
        params.append(teacher["id"] if teacher else 0)
    else:
        if ctx.get("teacher_id"):
            sql += " WHERE ta.teacher_id = ?"
            params.append(int(ctx.get("teacher_id")))
    sql += " ORDER BY c.name, s.name"
    return {"rows": [dict(r) for r in ctx.db.execute(sql, params).fetchall()]}


def create_assignment(ctx):
    require(ctx, "admin")
    try:
        aid = ctx.db.execute(
            "INSERT INTO teacher_assignments (teacher_id, class_id, subject_id) VALUES (?,?,?)",
            (int(_num(ctx.data, "teacher_id")), int(_num(ctx.data, "class_id")), int(_num(ctx.data, "subject_id"))),
        ).lastrowid
    except Exception:
        raise ApiError(409, "That teacher already handles this subject for the class")
    return {"id": aid}


def delete_assignment(ctx):
    require(ctx, "admin")
    ctx.db.execute("DELETE FROM teacher_assignments WHERE id = ?", (int(ctx.params["aid"]),))
    return {"ok": True}


# --------------------------------------------------------------------------
# exams and marks
# --------------------------------------------------------------------------

EXAM_SELECT = (
    "SELECT e.*, c.name AS class_name, s.name AS subject_name, s.id AS subject_id, c.id AS class_id, "
    "(SELECT COUNT(*) FROM marks m WHERE m.exam_id = e.id) AS entries "
    "FROM exam_sessions e JOIN classes c ON c.id = e.class_id JOIN subjects s ON s.id = e.subject_id"
)


def list_exams(ctx):
    sql, params = EXAM_SELECT + " WHERE 1=1", []
    if ctx.get("class_id"):
        sql += " AND e.class_id = ?"
        params.append(int(ctx.get("class_id")))
    if ctx.get("term"):
        sql += " AND e.term = ?"
        params.append(ctx.get("term"))
    if ctx.user["role"] == "teacher":
        teacher = teacher_row(ctx)
        sql += (" AND EXISTS (SELECT 1 FROM teacher_assignments ta WHERE ta.teacher_id = ? "
                "AND ta.class_id = e.class_id AND ta.subject_id = e.subject_id)")
        params.append(teacher["id"] if teacher else 0)
    sql += " ORDER BY e.exam_date DESC, e.id DESC"
    return {"rows": [dict(r) for r in ctx.db.execute(sql, params).fetchall()]}


def create_exam(ctx):
    require(ctx, "teacher")
    if not can_teach(ctx, int(_num(ctx.data, "class_id")), int(_num(ctx.data, "subject_id"))):
        raise ApiError(403, "You can only create exams for subjects you teach")
    try:
        eid = ctx.db.execute(
            "INSERT INTO exam_sessions (title, term, academic_year, class_id, subject_id, exam_date, max_marks, created_by) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                _str(ctx.data, "title", maxlen=80), _choice(ctx.data, "term", TERMS),
                _str(ctx.data, "academic_year", maxlen=20, required=False, default="2025/2026"),
                int(_num(ctx.data, "class_id")), int(_num(ctx.data, "subject_id")),
                _date(ctx.data, "exam_date", required=False),
                _num(ctx.data, "max_marks", required=False, default=100, minimum=1, maximum=1000),
                ctx.user["user_id"],
            ),
        ).lastrowid
    except Exception:
        raise ApiError(409, "An exam with that title already exists for this class and subject")
    auth.audit(ctx.db, ctx.user["user_id"], "exam_created", str(eid))
    return {"id": eid}


def delete_exam(ctx):
    require(ctx, "admin")
    eid = int(ctx.params["eid"])
    ctx.db.execute("DELETE FROM exam_sessions WHERE id = ?", (eid,))
    auth.audit(ctx.db, ctx.user["user_id"], "exam_deleted", str(eid))
    return {"ok": True}


def get_marks(ctx):
    eid = int(ctx.params["eid"])
    exam = get_or_404(ctx.db, EXAM_SELECT + " WHERE e.id = ?", (eid,), "Exam")
    if not can_teach(ctx, exam["class_id"], exam["subject_id"]):
        raise ApiError(403, "You can only view marks for subjects you teach")
    rows = ctx.db.execute(
        "SELECT s.id AS student_id, s.admission_no, s.first_name, s.last_name, m.score "
        "FROM students s LEFT JOIN marks m ON m.student_id = s.id AND m.exam_id = ? "
        "WHERE s.class_id = ? AND s.status = 'active' ORDER BY s.admission_no", (eid, exam["class_id"]),
    ).fetchall()
    return {"exam": dict(exam), "rows": [dict(r) for r in rows]}


def save_marks(ctx):
    eid = int(ctx.params["eid"])
    exam = get_or_404(ctx.db, EXAM_SELECT + " WHERE e.id = ?", (eid,), "Exam")
    if not can_teach(ctx, exam["class_id"], exam["subject_id"]):
        raise ApiError(403, "You can only enter marks for subjects you teach")

    scores = ctx.data.get("scores")
    if not isinstance(scores, dict) or not scores:
        raise ApiError(400, "Provide a 'scores' object mapping student_id to score")

    roster = {
        r["id"]: r
        for r in ctx.db.execute(
            "SELECT id FROM students WHERE class_id = ? AND status = 'active'", (exam["class_id"],)
        ).fetchall()
    }

    saved, skipped = 0, []
    for raw_id, raw_score in scores.items():
        try:
            sid = int(raw_id)
        except (TypeError, ValueError):
            skipped.append({"student_id": raw_id, "reason": "unknown student"})
            continue
        if sid not in roster:
            skipped.append({"student_id": raw_id, "reason": "not in this class"})
            continue
        if raw_score is None or raw_score == "":
            ctx.db.execute("DELETE FROM marks WHERE exam_id = ? AND student_id = ?", (eid, sid))
            continue
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            skipped.append({"student_id": raw_id, "reason": "not a number"})
            continue
        if score < 0 or score > exam["max_marks"]:
            skipped.append({"student_id": raw_id, "reason": f"must be between 0 and {exam['max_marks']}"})
            continue
        ctx.db.execute(
            "INSERT INTO marks (exam_id, student_id, score, entered_by) VALUES (?,?,?,?) "
            "ON CONFLICT(exam_id, student_id) DO UPDATE SET score = excluded.score, "
            "entered_by = excluded.entered_by, updated_at = datetime('now')",
            (eid, sid, score, ctx.user["user_id"]),
        )
        saved += 1

    reports.invalidate_caches()
    auth.audit(ctx.db, ctx.user["user_id"], "marks_saved", f"exam={eid} saved={saved}")
    return {"saved": saved, "skipped": skipped}


# --------------------------------------------------------------------------
# attendance
# --------------------------------------------------------------------------

def list_attendance(ctx):
    if ctx.user["role"] == "student":
        mine = student_row(ctx)
        if not mine:
            raise ApiError(403, "No student record linked to your account")
        rows = ctx.db.execute(
            "SELECT date, period, status, note FROM attendance_records WHERE student_id = ? "
            "AND date >= ? ORDER BY date DESC",
            (mine["id"], ctx.get("from", "2000-01-01")),
        ).fetchall()
        summary = ctx.db.execute(
            "SELECT total_sessions, attended, absent, rate FROM v_attendance_summary WHERE student_id = ?",
            (mine["id"],),
        ).fetchone()
        return {"rows": [dict(r) for r in rows], "summary": dict(summary) if summary else None}

    sql, params = (
        "SELECT a.*, s.admission_no, s.first_name, s.last_name, c.name AS class_name "
        "FROM attendance_records a JOIN students s ON s.id = a.student_id "
        "LEFT JOIN classes c ON c.id = a.class_id WHERE 1=1"
    ), []
    if ctx.get("class_id"):
        sql += " AND a.class_id = ?"
        params.append(int(ctx.get("class_id")))
    if ctx.get("date"):
        sql += " AND a.date = ?"
        params.append(date_param(ctx, "date"))
    if ctx.get("student_id"):
        sql += " AND a.student_id = ?"
        params.append(int(ctx.get("student_id")))
    if ctx.user["role"] == "teacher":
        teacher = teacher_row(ctx)
        if teacher:
            sql += " AND EXISTS (SELECT 1 FROM teacher_assignments ta WHERE ta.teacher_id = ? AND ta.class_id = a.class_id)"
            params.append(teacher["id"])
    sql += " ORDER BY a.date DESC, s.admission_no LIMIT 500"
    return {"rows": [dict(r) for r in ctx.db.execute(sql, params).fetchall()]}


def save_attendance(ctx):
    require(ctx, "teacher")
    class_id = int(_num(ctx.data, "class_id"))
    day = _date(ctx.data, "date")
    period = _str(ctx.data, "period", maxlen=20, required=False, default="Daily")
    records = ctx.data.get("records")
    if not isinstance(records, list) or not records:
        raise ApiError(400, "Provide a 'records' list of {student_id, status}")

    cls = get_or_404(ctx.db, "SELECT * FROM classes WHERE id = ?", (class_id,), "Class")
    if not is_admin(ctx):
        teacher = teacher_row(ctx)
        if not teacher or not ctx.db.execute(
            "SELECT 1 FROM teacher_assignments WHERE teacher_id = ? AND class_id = ?",
            (teacher["id"], class_id),
        ).fetchone():
            raise ApiError(403, "You are not assigned to this class")

    valid = {
        r["id"] for r in ctx.db.execute(
            "SELECT id FROM students WHERE class_id = ? AND status = 'active'", (class_id,)
        ).fetchall()
    }
    saved = 0
    rejected = []
    for item in records:
        try:
            sid = int(item.get("student_id"))
        except (TypeError, ValueError):
            rejected.append({"reason": "invalid student_id"})
            continue
        if sid not in valid:
            rejected.append({"student_id": sid, "reason": "not an active student in this class"})
            continue
        status = item.get("status")
        if status not in ("present", "absent", "late", "excused"):
            rejected.append({"student_id": sid, "reason": "invalid status"})
            continue
        ctx.db.execute(
            "INSERT INTO attendance_records (class_id, student_id, date, period, status, note, recorded_by) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(student_id, date, period) DO UPDATE SET "
            "status = excluded.status, note = excluded.note, recorded_by = excluded.recorded_by, class_id = excluded.class_id",
            (class_id, sid, day, period, status, str(item.get("note", ""))[:200] or None, ctx.user["user_id"]),
        )
        saved += 1

    auth.audit(ctx.db, ctx.user["user_id"], "attendance_saved", f"class={cls['name']} date={day} rows={saved}")
    return {"saved": saved, "rejected": rejected}


# --------------------------------------------------------------------------
# fees
# --------------------------------------------------------------------------

def list_invoices(ctx):
    sql, params = (
        "SELECT v.*, s.admission_no, s.first_name, s.last_name, c.name AS class_name "
        "FROM v_fee_balances v JOIN students s ON s.id = v.student_id "
        "LEFT JOIN classes c ON c.id = s.class_id WHERE 1=1"
    ), []
    if ctx.user["role"] == "student":
        mine = student_row(ctx)
        if not mine:
            raise ApiError(403, "No student record linked to your account")
        sql += " AND s.id = ?"
        params.append(mine["id"])
    else:
        if ctx.get("class_id"):
            sql += " AND s.class_id = ?"
            params.append(int(ctx.get("class_id")))
        if ctx.get("student_id"):
            sql += " AND s.id = ?"
            params.append(int(ctx.get("student_id")))
    if ctx.get("term"):
        sql += " AND v.term = ?"
        params.append(ctx.get("term"))
    if ctx.get("academic_year"):
        sql += " AND v.academic_year = ?"
        params.append(ctx.get("academic_year"))
    if ctx.get("unpaid_only") == "1":
        sql += " AND v.balance > 0"
    sql += " ORDER BY v.balance DESC, s.admission_no LIMIT 1000"
    return {"rows": [dict(r) for r in ctx.db.execute(sql, params).fetchall()]}


def create_invoice(ctx):
    require(ctx, "admin")
    sid = int(_num(ctx.data, "student_id"))
    get_or_404(ctx.db, "SELECT 1 id FROM students WHERE id = ?", (sid,), "Student")
    try:
        iid = ctx.db.execute(
            "INSERT INTO fee_invoices (student_id, term, academic_year, description, amount_due, issued_on) "
            "VALUES (?,?,?,?,?,?)",
            (
                sid, _choice(ctx.data, "term", TERMS),
                _str(ctx.data, "academic_year", maxlen=20, required=False, default="2025/2026"),
                _str(ctx.data, "description", maxlen=80),
                _num(ctx.data, "amount_due", minimum=0),
                _date(ctx.data, "issued_on", required=False, default=None) or TODAY,
            ),
        ).lastrowid
    except Exception:
        raise ApiError(409, "An invoice for that item, term and year already exists for this student")
    auth.audit(ctx.db, ctx.user["user_id"], "invoice_created", str(iid))
    return {"id": iid}


def record_payment(ctx):
    require(ctx, "admin")
    invoice_id = int(_num(ctx.data, "invoice_id"))
    amount = _num(ctx.data, "amount", minimum=0.01)
    invoice = get_or_404(
        ctx.db, "SELECT i.*, (i.amount_due - COALESCE((SELECT SUM(amount) FROM fee_payments WHERE invoice_id = i.id),0)) "
                "AS balance FROM fee_invoices i WHERE i.id = ?", (invoice_id,), "Invoice")
    if amount > invoice["balance"] + 0.001:
        raise ApiError(400, f"Payment exceeds the outstanding balance of {invoice['balance']:.2f}")
    pid = ctx.db.execute(
        "INSERT INTO fee_payments (invoice_id, amount, method, reference, paid_on, received_by) VALUES (?,?,?,?,?,?)",
        (
            invoice_id, amount, _choice(ctx.data, "method", ("cash", "bank transfer", "mobile money", "cheque")),
            _str(ctx.data, "reference", maxlen=60, required=False),
            _date(ctx.data, "paid_on", required=False, default=None) or TODAY,
            ctx.user["user_id"],
        ),
    ).lastrowid
    auth.audit(ctx.db, ctx.user["user_id"], "payment_recorded", f"invoice={invoice_id} amount={amount}")
    return {"id": pid}


def delete_invoice(ctx):
    require(ctx, "admin")
    iid = int(ctx.params["iid"])
    if ctx.db.execute("SELECT 1 FROM fee_payments WHERE invoice_id = ?", (iid,)).fetchone():
        raise ApiError(409, "This invoice has payments recorded against it and cannot be deleted")
    ctx.db.execute("DELETE FROM fee_invoices WHERE id = ?", (iid,))
    return {"ok": True}


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def report_results(ctx):
    require(ctx, "teacher")
    class_id = class_id_param(ctx)
    if ctx.user["role"] == "teacher" and not ctx.db.execute(
        "SELECT 1 FROM teacher_assignments ta JOIN teachers t ON t.id = ta.teacher_id "
        "WHERE t.user_id = ? AND ta.class_id = ?", (ctx.user["user_id"], class_id)
    ).fetchone():
        raise ApiError(403, "You are not assigned to this class")
    term, year = term_params(ctx)
    cls = get_or_404(ctx.db, "SELECT * FROM classes WHERE id = ?", (class_id,), "Class")
    return {"class": dict(cls), "term": term, "academic_year": year, "results": reports.class_results(ctx.db, class_id, term, year)}


def report_attendance(ctx):
    require(ctx, "teacher")
    return {
        "rows": reports.attendance_report(
            ctx.db,
            class_id_param(ctx, required=False),
            date_param(ctx, "from"), date_param(ctx, "to"),
        )
    }


def report_fees(ctx):
    require(ctx, "teacher")
    term = ctx.get("term") or TERMS[0]
    rows = reports.fee_report(ctx.db, class_id_param(ctx, required=False), term,
                              ctx.get("academic_year", "2025/2026"))
    totals = {
        "due": round(sum(r["amount_due"] for r in rows), 2),
        "paid": round(sum(r["amount_paid"] for r in rows), 2),
        "balance": round(sum(r["balance"] for r in rows), 2),
    }
    return {"rows": rows, "totals": totals, "term": term}


def report_student(ctx):
    sid = int(ctx.params["sid"])
    student = get_or_404(ctx.db, STUDENT_SELECT + " WHERE s.id = ?", (sid,), "Student")
    if ctx.user["role"] == "student":
        mine = student_row(ctx)
        if not mine or mine["id"] != sid:
            raise ApiError(403, "Students may only view their own report")
    else:
        require(ctx, "teacher")
    term, year = term_params(ctx)
    return reports.student_report(ctx.db, student, term, year)


def export_csv(ctx):
    require(ctx, "teacher")
    kind = ctx.params["kind"]
    term, year = term_params(ctx)
    class_id = class_id_param(ctx, required=False)
    if kind == "results":
        if not class_id:
            raise ApiError(400, "class_id is required for the results export")
        rows = reports.class_results(ctx.db, class_id, term, year)
        name = f"results-class-{class_id}-{term.replace(' ', '-').lower()}.csv"
    elif kind == "attendance":
        rows = reports.attendance_report(ctx.db, class_id, date_param(ctx, "from"), date_param(ctx, "to"))
        name = "attendance-report.csv"
    elif kind == "fees":
        rows = reports.fee_report(ctx.db, class_id, term, year)
        name = "fee-report.csv"
    else:
        raise ApiError(404, "Unknown report type")
    return csv_response(reports.to_csv(rows), name)


# --------------------------------------------------------------------------
# user administration
# --------------------------------------------------------------------------

def list_users(ctx):
    require(ctx, "admin")
    rows = ctx.db.execute(
        "SELECT id, full_name, username, email, role, is_active, created_at FROM users ORDER BY role, username"
    ).fetchall()
    return {"rows": [dict(r) for r in rows]}


def create_user(ctx):
    require(ctx, "admin")
    role = _choice(ctx.data, "role", ("admin", "teacher", "student"))
    username = _str(ctx.data, "username", maxlen=60).lower()
    if not re.match(r"^[a-z0-9._-]{3,60}$", username):
        raise ApiError(400, "Username may only contain letters, numbers, dots, dashes and underscores")
    unique_or_409(ctx.db, "SELECT 1 FROM users WHERE username = ?", (username,), "username")
    password = _str(ctx.data, "password", maxlen=200, required=False, default=None) or "ChangeMe@123"
    if len(password) < 8:
        raise ApiError(400, "Password must be at least 8 characters")
    digest, salt = auth.hash_password(password)
    uid = ctx.db.execute(
        "INSERT INTO users (full_name, username, email, password_hash, password_salt, role) VALUES (?,?,?,?,?,?)",
        (_str(ctx.data, "full_name", maxlen=120), username, _email(ctx.data, "email"), digest, salt, role),
    ).lastrowid
    auth.audit(ctx.db, ctx.user["user_id"], "user_created", username)
    return {"id": uid}


def set_user_active(ctx):
    require(ctx, "admin")
    uid = int(ctx.params["uid"])
    if uid == ctx.user["user_id"]:
        raise ApiError(400, "You cannot deactivate your own account")
    active = 1 if ctx.data.get("is_active") else 0
    ctx.db.execute("UPDATE users SET is_active = ? WHERE id = ?", (active, uid))
    if not active:
        for token, session in list(auth._sessions.items()):
            if session["user_id"] == uid:
                auth.destroy_session(token)
    auth.audit(ctx.db, ctx.user["user_id"], "user_active_changed", f"id={uid} active={active}")
    return {"ok": True}


def reset_password(ctx):
    require(ctx, "admin")
    uid = int(ctx.params["uid"])
    password = _str(ctx.data, "password", maxlen=200)
    if len(password) < 8:
        raise ApiError(400, "Password must be at least 8 characters")
    get_or_404(ctx.db, "SELECT 1 id FROM users WHERE id = ?", (uid,), "User")
    digest, salt = auth.hash_password(password)
    ctx.db.execute("UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?", (digest, salt, uid))
    auth.audit(ctx.db, ctx.user["user_id"], "password_reset", f"user_id={uid}")
    return {"ok": True}


def delete_user(ctx):
    require(ctx, "admin")
    uid = int(ctx.params["uid"])
    if uid == ctx.user["user_id"]:
        raise ApiError(400, "You cannot delete your own account")
    linked = ctx.db.execute("SELECT 1 FROM students WHERE user_id = ? UNION SELECT 1 FROM teachers WHERE user_id = ?",
                            (uid, uid)).fetchone()
    if linked:
        raise ApiError(409, "This account is linked to a student or staff record. Delete that record instead.")
    ctx.db.execute("DELETE FROM users WHERE id = ?", (uid,))
    return {"ok": True}


def list_reference(ctx):
    db = ctx.db
    return {
        "classes": [dict(r) for r in db.execute("SELECT id, name, level, academic_year FROM classes ORDER BY name")],
        "subjects": [dict(r) for r in db.execute("SELECT id, name, code, category FROM subjects ORDER BY name")],
        "teachers": [dict(r) for r in db.execute(
            "SELECT id, staff_no, first_name || ' ' || last_name AS name FROM teachers WHERE status='active' ORDER BY name")],
        "terms": list(TERMS),
        "years": [dict(r)["academic_year"] for r in db.execute("SELECT DISTINCT academic_year FROM classes")],
        "grade_scales": [dict(r) for r in db.execute("SELECT * FROM grade_scales ORDER BY min_pct DESC")],
    }


HANDLERS = [
    ("POST", "/api/auth/login", login, True),
    ("POST", "/api/auth/logout", logout, True),
    ("GET", "/api/auth/me", me, False),
    ("POST", "/api/auth/change-password", change_own_password, False),
    ("GET", "/api/reference", list_reference, False),
    ("GET", "/api/dashboard", dashboard, False),

    ("GET", "/api/students", list_students, False),
    ("POST", "/api/students", create_student, False),
    ("GET", "/api/students/<int:sid>", get_student, False),
    ("PUT", "/api/students/<int:sid>", update_student, False),
    ("DELETE", "/api/students/<int:sid>", delete_student, False),

    ("GET", "/api/teachers", list_teachers, False),
    ("POST", "/api/teachers", create_teacher, False),
    ("GET", "/api/teachers/<int:tid>", get_teacher, False),
    ("PUT", "/api/teachers/<int:tid>", update_teacher, False),
    ("DELETE", "/api/teachers/<int:tid>", delete_teacher, False),

    ("GET", "/api/classes", list_classes, False),
    ("POST", "/api/classes", create_class, False),
    ("PUT", "/api/classes/<int:cid>", update_class, False),
    ("DELETE", "/api/classes/<int:cid>", delete_class, False),
    ("GET", "/api/classes/<int:cid>/subjects", class_subjects, False),
    ("POST", "/api/classes/<int:cid>/subjects", assign_class_subject, False),
    ("DELETE", "/api/classes/<int:cid>/subjects/<int:subject_id>", unassign_class_subject, False),

    ("GET", "/api/subjects", list_subjects, False),
    ("POST", "/api/subjects", create_subject, False),
    ("DELETE", "/api/subjects/<int:sid>", delete_subject, False),

    ("GET", "/api/assignments", list_assignments, False),
    ("POST", "/api/assignments", create_assignment, False),
    ("DELETE", "/api/assignments/<int:aid>", delete_assignment, False),

    ("GET", "/api/exams", list_exams, False),
    ("POST", "/api/exams", create_exam, False),
    ("DELETE", "/api/exams/<int:eid>", delete_exam, False),
    ("GET", "/api/exams/<int:eid>/marks", get_marks, False),
    ("PUT", "/api/exams/<int:eid>/marks", save_marks, False),

    ("GET", "/api/attendance", list_attendance, False),
    ("POST", "/api/attendance", save_attendance, False),

    ("GET", "/api/fees/invoices", list_invoices, False),
    ("POST", "/api/fees/invoices", create_invoice, False),
    ("DELETE", "/api/fees/invoices/<int:iid>", delete_invoice, False),
    ("POST", "/api/fees/payments", record_payment, False),

    ("GET", "/api/reports/results", report_results, False),
    ("GET", "/api/reports/attendance", report_attendance, False),
    ("GET", "/api/reports/fees", report_fees, False),
    ("GET", "/api/reports/students/<int:sid>", report_student, False),
    ("GET", "/api/reports/export/<kind>", export_csv, False),

    ("GET", "/api/users", list_users, False),
    ("POST", "/api/users", create_user, False),
    ("PUT", "/api/users/<int:uid>/active", set_user_active, False),
    ("PUT", "/api/users/<int:uid>/password", reset_password, False),
    ("DELETE", "/api/users/<int:uid>", delete_user, False),
]


def register(router):
    for method, pattern, handler, public in HANDLERS:
        router.add(method, pattern, handler, public=public)
