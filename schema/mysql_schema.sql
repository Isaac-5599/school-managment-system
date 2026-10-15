-- =====================================================================
--  School Management System — MySQL 8 schema (XAMPP / phpMyAdmin import)
--  Design and Implementation of a School Management System
--  Bachelor of Computer Science, Starford International University
--
--  This is the relational design used by the delivered prototype, written
--  in MySQL dialect so the same database can back a PHP/MySQL build.
--  Import with:  mysql -u root < schema/mysql_schema.sql
--           or: phpMyAdmin > Import > this file
-- =====================================================================

CREATE DATABASE IF NOT EXISTS school_mgmt
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE school_mgmt;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS audit_log, fee_payments, fee_invoices, attendance_records,
    marks, exam_sessions, teacher_assignments, class_subjects, grade_scales,
    students, subjects, classes, teachers, users;

-- ---------------------------------------------------------------------
-- 1. User management (authentication + role-based access control)
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    full_name     VARCHAR(150) NOT NULL,
    username      VARCHAR(60)  NOT NULL,
    email         VARCHAR(150),
    password_hash VARCHAR(255) NOT NULL,
    password_salt VARCHAR(255) NOT NULL,
    role          ENUM('admin','teacher','student') NOT NULL,
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. Teacher management
-- ---------------------------------------------------------------------
CREATE TABLE teachers (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    staff_no       VARCHAR(30)  NOT NULL,
    user_id        INT,
    first_name     VARCHAR(60)  NOT NULL,
    last_name      VARCHAR(60)  NOT NULL,
    email          VARCHAR(150),
    phone          VARCHAR(30),
    qualification  VARCHAR(100),
    specialization VARCHAR(100),
    hire_date      DATE,
    status         ENUM('active','on leave','retired') NOT NULL DEFAULT 'active',
    UNIQUE KEY uq_teachers_staff_no (staff_no),
    UNIQUE KEY uq_teachers_user (user_id),
    CONSTRAINT fk_teachers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. Class management
-- ---------------------------------------------------------------------
CREATE TABLE classes (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(50)  NOT NULL,
    level               VARCHAR(50)  NOT NULL,
    academic_year       VARCHAR(20)  NOT NULL,
    homeroom_teacher_id INT,
    UNIQUE KEY uq_classes_name (name),
    CONSTRAINT fk_classes_homeroom FOREIGN KEY (homeroom_teacher_id)
        REFERENCES teachers(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. Student management
-- ---------------------------------------------------------------------
CREATE TABLE students (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    admission_no   VARCHAR(30)  NOT NULL,
    user_id        INT,
    class_id       INT,
    first_name     VARCHAR(60)  NOT NULL,
    last_name      VARCHAR(60)  NOT NULL,
    gender         ENUM('Male','Female') NOT NULL,
    date_of_birth  DATE,
    guardian_name  VARCHAR(150),
    guardian_phone VARCHAR(30),
    guardian_email VARCHAR(150),
    enrollment_date DATE,
    status         ENUM('active','graduated','withdrawn') NOT NULL DEFAULT 'active',
    UNIQUE KEY uq_students_admission (admission_no),
    UNIQUE KEY uq_students_user (user_id),
    KEY idx_students_class (class_id),
    CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_students_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. Subject management
-- ---------------------------------------------------------------------
CREATE TABLE subjects (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    name     VARCHAR(100) NOT NULL,
    code     VARCHAR(20)  NOT NULL,
    category ENUM('core','elective') NOT NULL DEFAULT 'core',
    UNIQUE KEY uq_subjects_code (code)
) ENGINE=InnoDB;

-- 5a. Which subjects are offered in which class (many-to-many)
CREATE TABLE class_subjects (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    class_id   INT NOT NULL,
    subject_id INT NOT NULL,
    UNIQUE KEY uq_class_subject (class_id, subject_id),
    CONSTRAINT fk_cs_class   FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE,
    CONSTRAINT fk_cs_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5b. Which teacher teaches which subject to which class — the source of
--     the teacher's data-scoped permissions.
CREATE TABLE teacher_assignments (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    teacher_id INT NOT NULL,
    class_id   INT NOT NULL,
    subject_id INT NOT NULL,
    UNIQUE KEY uq_teacher_assignment (teacher_id, class_id, subject_id),
    CONSTRAINT fk_ta_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    CONSTRAINT fk_ta_class   FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE,
    CONSTRAINT fk_ta_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. Examination management
-- ---------------------------------------------------------------------
CREATE TABLE exam_sessions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    title         VARCHAR(100) NOT NULL,
    term          ENUM('First Term','Second Term','Third Term') NOT NULL,
    academic_year VARCHAR(20)  NOT NULL,
    class_id      INT NOT NULL,
    subject_id    INT NOT NULL,
    exam_date     DATE,
    max_marks     DECIMAL(6,2) NOT NULL DEFAULT 100.00,
    created_by    INT,
    UNIQUE KEY uq_exam (class_id, subject_id, title, term, academic_year),
    CONSTRAINT fk_exam_class   FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE,
    CONSTRAINT fk_exam_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_exam_creator FOREIGN KEY (created_by) REFERENCES users(id)    ON DELETE SET NULL,
    CONSTRAINT ck_exam_max CHECK (max_marks > 0)
) ENGINE=InnoDB;

CREATE TABLE marks (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    exam_id    INT NOT NULL,
    student_id INT NOT NULL,
    score      DECIMAL(6,2) NOT NULL,
    entered_by INT,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_mark (exam_id, student_id),
    KEY idx_marks_student (student_id),
    CONSTRAINT fk_marks_exam    FOREIGN KEY (exam_id)    REFERENCES exam_sessions(id) ON DELETE CASCADE,
    CONSTRAINT fk_marks_student FOREIGN KEY (student_id) REFERENCES students(id)      ON DELETE CASCADE,
    CONSTRAINT fk_marks_enterer FOREIGN KEY (entered_by) REFERENCES users(id)         ON DELETE SET NULL,
    CONSTRAINT ck_marks_score CHECK (score >= 0)
) ENGINE=InnoDB;

-- The score column stores the raw score; the ceiling is the parent exam's
-- max_marks, so the range check is enforced in the application layer
-- (score <= max_marks) rather than as a static table constraint.

-- ---------------------------------------------------------------------
-- 7. Attendance management
-- ---------------------------------------------------------------------
CREATE TABLE attendance_records (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    class_id    INT NOT NULL,
    student_id  INT NOT NULL,
    date        DATE NOT NULL,
    period      VARCHAR(30) NOT NULL DEFAULT 'Daily',
    status      ENUM('present','absent','late','excused') NOT NULL,
    note        VARCHAR(255),
    recorded_by INT,
    UNIQUE KEY uq_attendance (student_id, date, period),
    KEY idx_attendance_student (student_id, date),
    CONSTRAINT fk_att_class   FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE,
    CONSTRAINT fk_att_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_att_recorder FOREIGN KEY (recorded_by) REFERENCES users(id)  ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 8. Fee management
-- ---------------------------------------------------------------------
CREATE TABLE fee_invoices (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    student_id    INT NOT NULL,
    term          ENUM('First Term','Second Term','Third Term') NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    description   VARCHAR(150) NOT NULL,
    amount_due    DECIMAL(12,2) NOT NULL,
    issued_on     DATE NOT NULL DEFAULT (CURRENT_DATE),
    UNIQUE KEY uq_invoice (student_id, term, academic_year, description),
    KEY idx_invoice_student (student_id),
    CONSTRAINT fk_invoice_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT ck_invoice_due CHECK (amount_due >= 0)
) ENGINE=InnoDB;

CREATE TABLE fee_payments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    invoice_id  INT NOT NULL,
    amount      DECIMAL(12,2) NOT NULL,
    method      ENUM('cash','bank transfer','mobile money','cheque') NOT NULL,
    reference   VARCHAR(100),
    paid_on     DATE NOT NULL DEFAULT (CURRENT_DATE),
    received_by INT,
    KEY idx_payment_invoice (invoice_id),
    CONSTRAINT fk_payment_invoice FOREIGN KEY (invoice_id) REFERENCES fee_invoices(id) ON DELETE CASCADE,
    CONSTRAINT fk_payment_receiver FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT ck_payment_amount CHECK (amount > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 9. Grading scale (lookup table, keeps grade boundaries data not code)
-- ---------------------------------------------------------------------
CREATE TABLE grade_scales (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    min_pct DECIMAL(5,2) NOT NULL,
    max_pct DECIMAL(5,2) NOT NULL,
    grade   CHAR(1) NOT NULL,
    remark  VARCHAR(30) NOT NULL
) ENGINE=InnoDB;

INSERT INTO grade_scales (min_pct, max_pct, grade, remark) VALUES
    (75.00, 100.00, 'A', 'Excellent'),
    (65.00,  74.99, 'B', 'Very Good'),
    (55.00,  64.99, 'C', 'Good'),
    (45.00,  54.99, 'D', 'Fair'),
    (40.00,  44.99, 'E', 'Pass'),
    ( 0.00,  39.99, 'F', 'Fail');

-- ---------------------------------------------------------------------
-- 10. Audit trail
-- ---------------------------------------------------------------------
CREATE TABLE audit_log (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action  VARCHAR(60) NOT NULL,
    detail  VARCHAR(255),
    at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 11. Reporting views (objective 8: automated reports)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_student_results AS
SELECT m.student_id,
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

CREATE OR REPLACE VIEW v_fee_balances AS
SELECT i.id            AS invoice_id,
       i.student_id,
       i.term,
       i.academic_year,
       i.description,
       i.amount_due,
       COALESCE(SUM(p.amount), 0) AS amount_paid,
       i.amount_due - COALESCE(SUM(p.amount), 0) AS balance
FROM fee_invoices i
LEFT JOIN fee_payments p ON p.invoice_id = i.id
GROUP BY i.id, i.student_id, i.term, i.academic_year, i.description, i.amount_due;

CREATE OR REPLACE VIEW v_attendance_summary AS
SELECT a.student_id,
       COUNT(*) AS total_sessions,
       SUM(CASE WHEN a.status IN ('present','late') THEN 1 ELSE 0 END) AS attended,
       SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent,
       ROUND(100.0 * SUM(CASE WHEN a.status IN ('present','late') THEN 1 ELSE 0 END) / COUNT(*), 1) AS rate
FROM attendance_records a
GROUP BY a.student_id;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 12. Demo login
--     The prototype hashes passwords with PBKDF2-HMAC-SHA256, 200 000
--     rounds, stored as hex:  hash = PBKDF2(password, salt, 200000).
--     The row below is the seeded administrator (username "admin",
--     password "Admin@123"). A PHP build should re-hash it with
--     password_hash('Admin@123', PASSWORD_DEFAULT) and verify with
--     password_verify(); the salt column is then unused.
-- ---------------------------------------------------------------------
INSERT INTO users (full_name, username, email, password_hash, password_salt, role, is_active) VALUES
    ('System Administrator', 'admin', 'admin@school.edu.ng',
     '36270fc9edfb2ef4cb24a0168e71ee2b88a590c0ecab26e3caeb3a4b7f9481f0',
     '6e262085daa92c8e8daed7d9f3c7c7f1', 'admin', 1);
