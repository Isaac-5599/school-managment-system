"""Demo data so the system has realistic records to report on immediately."""

import random
from datetime import date, timedelta

ACADEMIC_YEAR = "2025/2026"
TERM = "First Term"

DEMOS_PASSWORDS = {
    "admin": "Admin@123",
    "teacher": "Teach@123",
    "student": "Student@123",
}

SUBJECTS = [
    ("Mathematics", "MTH", "core"),
    ("English Language", "ENG", "core"),
    ("Biology", "BIO", "core"),
    ("Chemistry", "CHM", "core"),
    ("Physics", "PHY", "core"),
    ("Economics", "ECO", "elective"),
    ("Government", "GOV", "elective"),
    ("Computer Studies", "CST", "core"),
]

TEACHERS = [
    ("Adewale", "Ogunleye", "M.Sc. Mathematics", "Mathematics", "OGN"),
    ("Chinelo", "Obi", "B.Ed. English", "English", "OBC"),
    ("Musa", "Danjuma", "M.Sc. Physics", "Physics", "MDA"),
    ("Grace", "Okonkwo", "M.Sc. Chemistry", "Chemistry", "OKG"),
    ("Emeka", "Nwosu", "B.Sc. Computer Science", "Computer Studies", "NWE"),
    ("Fatima", "Bello", "M.Ed. Biology", "Biology", "BLF"),
]

CLASSES = [
    ("JSS 1A", "JSS"),
    ("JSS 2A", "JSS"),
    ("SSS 1A", "SSS"),
]

STUDENTS = [
    ("Aisha", "Bello", "Female"), ("Tunde", "Adeyemi", "Male"), ("Chidera", "Eze", "Female"),
    ("Ibrahim", "Sani", "Male"), ("Kemi", "Oyelaran", "Female"), ("David", "Mensah", "Male"),
    ("Ngozi", "Ikpeba", "Female"), ("Suleiman", "Yakubu", "Male"), ("Blessing", "Ada", "Female"),
    ("Femi", "Olowu", "Male"), ("Zainab", "Umar", "Female"), ("Daniel", "Sarpong", "Male"),
    ("Amara", "Chukwu", "Female"), ("Yusuf", "Garba", "Male"), ("Titilayo", "Soyinka", "Female"),
    ("Kwame", "Asante", "Male"), ("Halima", "Lawan", "Female"), ("Obinna", "Nkechi", "Male"),
]

CLASS_SUBJECTS = {
    "JSS 1A": ["MTH", "ENG", "BIO", "CST"],
    "JSS 2A": ["MTH", "ENG", "PHY", "CST"],
    "SSS 1A": ["MTH", "ENG", "BIO", "CHM", "PHY", "ECO", "GOV", "CST"],
}

TEACHING = {
    "MTH": 1, "ENG": 2, "PHY": 3, "CHM": 4, "CST": 5, "BIO": 6, "ECO": 5, "GOV": 2,
}

TUITION = {"JSS 1A": 45000, "JSS 2A": 48000, "SSS 1A": 65000}


def load(conn, hash_password):
    rng = random.Random(20260101)

    def add_user(full_name, username, email, role):
        pw_hash, salt = hash_password(DEMOS_PASSWORDS[role])
        cur = conn.execute(
            "INSERT INTO users (full_name, username, email, password_hash, password_salt, role) "
            "VALUES (?,?,?,?,?,?)",
            (full_name, username, email, pw_hash, salt, role),
        )
        return cur.lastrowid

    admin_id = add_user("System Administrator", "admin", "admin@school.edu.ng", "admin")

    teacher_ids = []
    for i, (first, last, qual, spec, staff_root) in enumerate(TEACHERS, start=1):
        uid = add_user(f"{first} {last}", f"teacher{i}", f"{staff_root.lower()}@school.edu.ng", "teacher")
        cur = conn.execute(
            "INSERT INTO teachers (staff_no, user_id, first_name, last_name, email, phone, qualification, "
            "specialization, hire_date) VALUES (?,?,?,?,?,?,?,?,?)",
            (f"STF/{staff_root}", uid, first, last, f"{staff_root.lower()}@school.edu.ng",
             f"+234 80{rng.randint(1000000, 9999999)}", qual, spec,
             date(2018 + (i % 5), 9, 1).isoformat()),
        )
        teacher_ids.append(cur.lastrowid)

    class_ids = {}
    for idx, (name, level) in enumerate(CLASSES):
        cur = conn.execute(
            "INSERT INTO classes (name, level, academic_year, homeroom_teacher_id) VALUES (?,?,?,?)",
            (name, level, ACADEMIC_YEAR, teacher_ids[idx % len(teacher_ids)]),
        )
        class_ids[name] = cur.lastrowid

    subject_ids = {}
    for name, code, category in SUBJECTS:
        cur = conn.execute(
            "INSERT INTO subjects (name, code, category) VALUES (?,?,?)", (name, code, category)
        )
        subject_ids[code] = cur.lastrowid

    student_ids_by_class = {}
    per_class = [6, 6, 6]
    cursor_name = 0
    seq = 0
    for class_name, count in zip([c[0] for c in CLASSES], per_class):
        ids = []
        for _ in range(count):
            first, last, gender = STUDENTS[cursor_name % len(STUDENTS)]
            cursor_name += 1
            seq += 1
            admission = f"SMS/{ACADEMIC_YEAR[:4]}/{seq:03d}"
            uid = add_user(f"{first} {last}", f"student{seq}", f"{first.lower()}.{last.lower()}{seq}@student.school.edu.ng", "student")
            birth_year = 2013 if class_name.startswith("JSS 1") else 2012 if class_name.startswith("JSS 2") else 2009
            cur = conn.execute(
                "INSERT INTO students (admission_no, user_id, class_id, first_name, last_name, gender, "
                "date_of_birth, guardian_name, guardian_phone, guardian_email, enrollment_date) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (admission, uid, class_ids[class_name], first, last, gender,
                 date(birth_year, rng.randint(1, 12), rng.randint(1, 28)).isoformat(),
                 f"{rng.choice(['Mr', 'Mrs', 'Dr'])} {last}",
                 f"+234 80{rng.randint(1000000, 9999999)}",
                 f"guardian.{last.lower()}{seq}@mail.com", "2025-09-15"),
            )
            ids.append(cur.lastrowid)
        student_ids_by_class[class_name] = ids

    for class_name, codes in CLASS_SUBJECTS.items():
        for code in codes:
            conn.execute(
                "INSERT INTO class_subjects (class_id, subject_id) VALUES (?,?)",
                (class_ids[class_name], subject_ids[code]),
            )
            teacher_idx = TEACHING[code] - 1
            conn.execute(
                "INSERT OR IGNORE INTO teacher_assignments (teacher_id, class_id, subject_id) VALUES (?,?,?)",
                (teacher_ids[teacher_idx], class_ids[class_name], subject_ids[code]),
            )

    exam_ids = []
    for class_name, codes in CLASS_SUBJECTS.items():
        for code in codes:
            for title, max_marks in (("First Term Exam", 100.0), ("First Term Quiz", 20.0)):
                cur = conn.execute(
                    "INSERT INTO exam_sessions (title, term, academic_year, class_id, subject_id, exam_date, "
                    "max_marks, created_by) VALUES (?,?,?,?,?,?,?,?)",
                    (title, TERM, ACADEMIC_YEAR, class_ids[class_name], subject_ids[code],
                     date(2025, 11, 10).isoformat() if max_marks == 100 else date(2025, 10, 20).isoformat(),
                     max_marks, admin_id),
                )
                exam_ids.append((cur.lastrowid, max_marks, student_ids_by_class[class_name]))

    for exam_id, max_marks, ids in exam_ids:
        for sid in ids:
            ability = rng.gauss(0.68, 0.15)
            ability = max(0.15, min(0.98, ability))
            score = round(max_marks * ability, 1)
            conn.execute(
                "INSERT INTO marks (exam_id, student_id, score, entered_by) VALUES (?,?,?,?)",
                (exam_id, sid, score, admin_id),
            )

    school_days = []
    d = date(2025, 10, 6)
    while len(school_days) < 20:
        if d.weekday() < 5:
            school_days.append(d)
        d += timedelta(days=1)

    for class_name, ids in student_ids_by_class.items():
        for day in school_days:
            for sid in ids:
                roll = rng.random()
                status = "present" if roll < 0.84 else "late" if roll < 0.91 else "absent" if roll < 0.97 else "excused"
                conn.execute(
                    "INSERT INTO attendance_records (class_id, student_id, date, period, status, recorded_by) "
                    "VALUES (?,?,?,?,?,?)",
                    (class_ids[class_name], sid, day.isoformat(), "Daily", status, admin_id),
                )

    for class_name, ids in student_ids_by_class.items():
        tuition = TUITION[class_name]
        for sid in ids:
            cur = conn.execute(
                "INSERT INTO fee_invoices (student_id, term, academic_year, description, amount_due, issued_on) "
                "VALUES (?,?,?,?,?,?)",
                (sid, TERM, ACADEMIC_YEAR, "Tuition fee", float(tuition), "2025-09-05"),
            )
            invoice_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO fee_invoices (student_id, term, academic_year, description, amount_due, issued_on) "
                "VALUES (?,?,?,?,?,?)",
                (sid, TERM, ACADEMIC_YEAR, "Examination and ID card", 8000.0, "2025-09-05"),
            )
            exam_invoice = cur.lastrowid

            roll = rng.random()
            if roll < 0.45:
                paid = float(tuition)
            elif roll < 0.8:
                paid = round(tuition * rng.uniform(0.3, 0.8), 2)
            else:
                paid = 0.0
            if paid > 0:
                conn.execute(
                    "INSERT INTO fee_payments (invoice_id, amount, method, reference, paid_on, received_by) "
                    "VALUES (?,?,?,?,?,?)",
                    (invoice_id, paid, rng.choice(["cash", "bank transfer", "mobile money"]),
                     f"RCP{rng.randint(10000, 99999)}", "2025-09-20", admin_id),
                )
            if rng.random() < 0.7:
                conn.execute(
                    "INSERT INTO fee_payments (invoice_id, amount, method, reference, paid_on, received_by) "
                    "VALUES (?,?,?,?,?,?)",
                    (exam_invoice, 8000.0, "bank transfer", f"RCP{rng.randint(10000, 99999)}",
                     "2025-09-22", admin_id),
                )
