"""Grade computation and academic/administrative report generation."""

_cache = {}


def grade_scales(conn):
    if "scales" not in _cache:
        _cache["scales"] = [
            (r["min_pct"], r["max_pct"], r["grade"], r["remark"])
            for r in conn.execute("SELECT min_pct, max_pct, grade, remark FROM grade_scales ORDER BY min_pct DESC")
        ]
    return _cache["scales"]


def invalidate_caches():
    _cache.clear()


def grade_for(conn, percentage):
    if percentage is None:
        return "", ""
    for low, high, grade, remark in grade_scales(conn):
        if percentage >= low:
            return grade, remark
    return "", ""


def student_subject_breakdown(conn, student_id, term, academic_year):
    rows = conn.execute(
        "SELECT sub.id AS subject_id, sub.name, sub.code, e.title, e.max_marks, m.score, "
        "       ROUND(100.0 * m.score / e.max_marks, 2) AS percentage "
        "FROM marks m "
        "JOIN exam_sessions e ON e.id = m.exam_id "
        "JOIN subjects sub ON sub.id = e.subject_id "
        "WHERE m.student_id = ? AND e.term = ? AND e.academic_year = ? "
        "ORDER BY sub.name, e.title",
        (student_id, term, academic_year),
    ).fetchall()

    per_subject = {}
    for r in rows:
        entry = per_subject.setdefault(
            r["subject_id"], {"subject": r["name"], "code": r["code"], "assessments": [], "pcts": []}
        )
        entry["assessments"].append(
            {"title": r["title"], "score": r["score"], "max_marks": r["max_marks"], "percentage": r["percentage"]}
        )
        entry["pcts"].append(r["percentage"])

    breakdown = []
    for entry in per_subject.values():
        avg = round(sum(entry["pcts"]) / len(entry["pcts"]), 2)
        grade, remark = grade_for(conn, avg)
        breakdown.append(
            {
                "subject": entry["subject"],
                "code": entry["code"],
                "average": avg,
                "grade": grade,
                "remark": remark,
                "assessments": entry["assessments"],
            }
        )
    return breakdown


def class_positions(conn, class_id, term, academic_year):
    """Rank students in a class by overall weighted percentage for the term."""
    rows = conn.execute(
        "SELECT m.student_id, SUM(m.score) AS total_score, SUM(e.max_marks) AS total_max, "
        "       ROUND(100.0 * SUM(m.score) / SUM(e.max_marks), 2) AS average "
        "FROM marks m JOIN exam_sessions e ON e.id = m.exam_id "
        "WHERE e.class_id = ? AND e.term = ? AND e.academic_year = ? "
        "GROUP BY m.student_id ORDER BY average DESC",
        (class_id, term, academic_year),
    ).fetchall()

    positions = {}
    rank = 0
    previous = None
    for index, row in enumerate(rows, start=1):
        if row["average"] != previous:
            rank = index
            previous = row["average"]
        positions[row["student_id"]] = {"position": rank, "average": row["average"], "graded": len(rows)}
    return positions


def student_report(conn, student, term, academic_year):
    student_id = student["id"]
    breakdown = student_subject_breakdown(conn, student_id, term, academic_year)
    positions = (
        class_positions(conn, student["class_id"], term, academic_year) if student["class_id"] else {}
    )
    standing = positions.get(student_id, {})
    overall = standing.get("average")
    grade, remark = grade_for(conn, overall)

    attendance = conn.execute(
        "SELECT total_sessions, attended, absent, rate FROM v_attendance_summary WHERE student_id = ?",
        (student_id,),
    ).fetchone()
    fees = conn.execute(
        "SELECT COALESCE(SUM(amount_due),0) due, COALESCE(SUM(amount_paid),0) paid, "
        "       COALESCE(SUM(balance),0) balance FROM v_fee_balances "
        "WHERE student_id = ? AND term = ? AND academic_year = ?",
        (student_id, term, academic_year),
    ).fetchone()

    return {
        "student": dict(student),
        "term": term,
        "academic_year": academic_year,
        "subjects": breakdown,
        "overall_average": overall,
        "overall_grade": grade,
        "overall_remark": remark,
        "position": standing.get("position"),
        "class_size": standing.get("graded"),
        "attendance": dict(attendance) if attendance else None,
        "fees": dict(fees) if fees else None,
    }


def class_results(conn, class_id, term, academic_year):
    positions = class_positions(conn, class_id, term, academic_year)
    students = conn.execute(
        "SELECT id, admission_no, first_name, last_name FROM students WHERE class_id = ? ORDER BY admission_no",
        (class_id,),
    ).fetchall()
    subject_rows = conn.execute(
        "SELECT m.student_id, sub.name, ROUND(100.0 * m.score / e.max_marks, 2) AS percentage "
        "FROM marks m JOIN exam_sessions e ON e.id = m.exam_id JOIN subjects sub ON sub.id = e.subject_id "
        "WHERE e.class_id = ? AND e.term = ? AND e.academic_year = ?",
        (class_id, term, academic_year),
    ).fetchall()

    by_student = {}
    for r in subject_rows:
        by_student.setdefault(r["student_id"], []).append(r["percentage"])

    results = []
    for s in students:
        scores = by_student.get(s["id"], [])
        standing = positions.get(s["id"], {})
        results.append(
            {
                "student_id": s["id"],
                "admission_no": s["admission_no"],
                "name": f"{s['first_name']} {s['last_name']}",
                "subjects_assessed": len(scores),
                "average": standing.get("average"),
                "grade": grade_for(conn, standing.get("average"))[0],
                "position": standing.get("position"),
            }
        )
    results.sort(key=lambda x: (x["position"] is None, x["position"] or 999))
    return results


def attendance_report(conn, class_id=None, term_start=None, term_end=None):
    sql = (
        "SELECT s.id AS student_id, s.admission_no, s.first_name, s.last_name, c.name AS class_name, "
        "       v.total_sessions, v.attended, v.absent, v.rate "
        "FROM v_attendance_summary v JOIN students s ON s.id = v.student_id "
        "LEFT JOIN classes c ON c.id = s.class_id "
        "WHERE 1=1"
    )
    params = []
    if class_id:
        sql += " AND s.class_id = ?"
        params.append(class_id)
    if term_start and term_end:
        sql += " AND EXISTS (SELECT 1 FROM attendance_records a WHERE a.student_id = s.id AND a.date BETWEEN ? AND ?)"
        params += [term_start, term_end]
    sql += " ORDER BY v.rate DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def fee_report(conn, class_id=None, term=None, academic_year=None):
    sql = (
        "SELECT s.id AS student_id, s.admission_no, s.first_name, s.last_name, c.name AS class_name, "
        "       SUM(v.amount_due) AS amount_due, SUM(v.amount_paid) AS amount_paid, SUM(v.balance) AS balance "
        "FROM v_fee_balances v JOIN students s ON s.id = v.student_id "
        "LEFT JOIN classes c ON c.id = s.class_id WHERE 1=1"
    )
    params = []
    if class_id:
        sql += " AND s.class_id = ?"
        params.append(class_id)
    if term:
        sql += " AND v.term = ?"
        params.append(term)
    if academic_year:
        sql += " AND v.academic_year = ?"
        params.append(academic_year)
    sql += " GROUP BY s.id ORDER BY balance DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def to_csv(rows):
    if not rows:
        return ""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        cells = []
        for h in headers:
            value = row.get(h)
            text = "" if value is None else str(value)
            if "," in text or '"' in text:
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        lines.append(",".join(cells))
    return "\r\n".join(lines) + "\r\n"
