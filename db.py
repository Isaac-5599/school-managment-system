"""Database connection, schema definition and seeding for the School Management System."""

import os
import sqlite3

DB_PATH = os.environ.get(
    "SMS_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "school.db")
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT    NOT NULL,
    username      TEXT    NOT NULL UNIQUE,
    email         TEXT    UNIQUE,
    password_hash TEXT    NOT NULL,
    password_salt TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS teachers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_no       TEXT    NOT NULL UNIQUE,
    user_id        INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    first_name     TEXT    NOT NULL,
    last_name      TEXT    NOT NULL,
    email          TEXT,
    phone          TEXT,
    qualification  TEXT,
    specialization TEXT,
    hire_date      TEXT,
    status         TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'on leave', 'retired'))
);

CREATE TABLE IF NOT EXISTS classes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT    NOT NULL UNIQUE,
    level              TEXT    NOT NULL,
    academic_year      TEXT    NOT NULL,
    homeroom_teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS students (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    admission_no   TEXT    NOT NULL UNIQUE,
    user_id        INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    class_id       INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    first_name     TEXT    NOT NULL,
    last_name      TEXT    NOT NULL,
    gender         TEXT    NOT NULL CHECK (gender IN ('Male', 'Female')),
    date_of_birth  TEXT,
    guardian_name  TEXT,
    guardian_phone TEXT,
    guardian_email TEXT,
    enrollment_date TEXT,
    status         TEXT    NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'graduated', 'withdrawn'))
);

CREATE TABLE IF NOT EXISTS subjects (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL,
    code     TEXT    NOT NULL UNIQUE,
    category TEXT    NOT NULL DEFAULT 'core' CHECK (category IN ('core', 'elective'))
);

CREATE TABLE IF NOT EXISTS class_subjects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id   INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE (class_id, subject_id)
);

CREATE TABLE IF NOT EXISTS teacher_assignments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    class_id   INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE (teacher_id, class_id, subject_id)
);

CREATE TABLE IF NOT EXISTS exam_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    term          TEXT    NOT NULL CHECK (term IN ('First Term', 'Second Term', 'Third Term')),
    academic_year TEXT    NOT NULL,
    class_id      INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    subject_id    INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    exam_date     TEXT,
    max_marks     REAL    NOT NULL DEFAULT 100 CHECK (max_marks > 0),
    created_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (class_id, subject_id, title, term, academic_year)
);

CREATE TABLE IF NOT EXISTS marks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id    INTEGER NOT NULL REFERENCES exam_sessions(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    score      REAL    NOT NULL CHECK (score >= 0),
    entered_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (exam_id, student_id)
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id    INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date        TEXT    NOT NULL,
    period      TEXT    NOT NULL DEFAULT 'Daily',
    status      TEXT    NOT NULL CHECK (status IN ('present', 'absent', 'late', 'excused')),
    note        TEXT,
    recorded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (student_id, date, period)
);

CREATE TABLE IF NOT EXISTS fee_invoices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    term          TEXT    NOT NULL CHECK (term IN ('First Term', 'Second Term', 'Third Term')),
    academic_year TEXT    NOT NULL,
    description   TEXT    NOT NULL,
    amount_due    REAL    NOT NULL CHECK (amount_due >= 0),
    issued_on     TEXT    NOT NULL DEFAULT (date('now')),
    UNIQUE (student_id, term, academic_year, description)
);

CREATE TABLE IF NOT EXISTS fee_payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES fee_invoices(id) ON DELETE CASCADE,
    amount      REAL    NOT NULL CHECK (amount > 0),
    method      TEXT    NOT NULL CHECK (method IN ('cash', 'bank transfer', 'mobile money', 'cheque')),
    reference   TEXT,
    paid_on     TEXT    NOT NULL DEFAULT (date('now')),
    received_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS grade_scales (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    min_pct  REAL    NOT NULL,
    max_pct  REAL    NOT NULL,
    grade    TEXT    NOT NULL,
    remark   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action  TEXT    NOT NULL,
    detail  TEXT,
    at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id);
CREATE INDEX IF NOT EXISTS idx_marks_exam ON marks(exam_id);
CREATE INDEX IF NOT EXISTS idx_marks_student ON marks(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_records(student_id, date);
CREATE INDEX IF NOT EXISTS idx_invoice_student ON fee_invoices(student_id);

CREATE VIEW IF NOT EXISTS v_student_results AS
SELECT
    m.student_id,
    e.class_id,
    e.subject_id,
    e.term,
    e.academic_year,
    e.title,
    m.score,
    e.max_marks,
    ROUND(m.score * 100.0 / e.max_marks, 2) AS percentage
FROM marks m
JOIN exam_sessions e ON e.id = m.exam_id;

CREATE VIEW IF NOT EXISTS v_fee_balances AS
SELECT
    i.id            AS invoice_id,
    i.student_id,
    i.term,
    i.academic_year,
    i.description,
    i.amount_due,
    COALESCE(SUM(p.amount), 0) AS amount_paid,
    i.amount_due - COALESCE(SUM(p.amount), 0) AS balance
FROM fee_invoices i
LEFT JOIN fee_payments p ON p.invoice_id = i.id
GROUP BY i.id;

CREATE VIEW IF NOT EXISTS v_attendance_summary AS
SELECT
    a.student_id,
    COUNT(*) AS total_sessions,
    SUM(CASE WHEN a.status IN ('present', 'late') THEN 1 ELSE 0 END) AS attended,
    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent,
    ROUND(
        100.0 * SUM(CASE WHEN a.status IN ('present', 'late') THEN 1 ELSE 0 END) / COUNT(*), 1
    ) AS rate
FROM attendance_records a
GROUP BY a.student_id;
"""

GRADE_SCALE = [
    (75.0, 100.0, "A", "Excellent"),
    (65.0, 74.99, "B", "Very Good"),
    (55.0, 64.99, "C", "Good"),
    (45.0, 54.99, "D", "Fair"),
    (40.0, 44.99, "E", "Pass"),
    (0.0, 39.99, "F", "Fail"),
]


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) c FROM grade_scales").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO grade_scales (min_pct, max_pct, grade, remark) VALUES (?,?,?,?)", GRADE_SCALE
        )
    conn.commit()


def is_empty(conn):
    return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0


def seed(conn):
    """Load demo records so reports and dashboards have realistic data."""
    from . import auth, demo

    demo.load(conn, auth.hash_password)
    conn.commit()


def bootstrap():
    conn = get_conn()
    init_schema(conn)
    if is_empty(conn):
        seed(conn)
    return conn
