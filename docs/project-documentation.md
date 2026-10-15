# Design and Implementation of a School Management System

**Student Name:** ______________________________
**Registration Number:** ______________________________
**Programme:** Bachelor of Computer Science
**University:** Starford International University
**Supervisor:** ______________________________
**Date:** ______________________________

---

## Abstract

School records in many secondary schools are still kept in paper ledgers and disconnected
spreadsheets. The result is duplicated data, slow and error-prone result compilation, poor
attendance visibility, weak fee control and no reliable audit trail. This project designs,
implements and tests a **School Management System (SMS)** — a role-controlled web
application that consolidates student, staff, class, subject, attendance, examination and
fee records into one relational database and produces automated reports from them.

The system was developed iteratively using the **Agile** methodology and implements all
eight objectives set out in the project proposal: student, teacher, class, subject,
attendance, examination, fee and report management, with a secure login and role-based
access control for administrators, teachers and students. The delivered prototype consists
of **14 relational tables and 3 reporting views**, **50 HTTP JSON endpoints**, a
zero-dependency browser client, and **35 automated end-to-end tests** that all pass. It
demonstrates that a small institution can be served by a lightweight, secure, low-cost
system rather than by expensive commercial suites, in support of **Sustainable Development
Goal 4 (Quality Education)**.

---

# Chapter One: Introduction

## 1.1 Background of the Study

A secondary school is, in information terms, a data-processing organisation. Every term it
captures admissions and personal details for hundreds of learners, roster teaching staff
against classes and subjects, records attendance daily, examines learners in each subject,
converts raw scores into graded results and positions, and bills and receipts school fees.
Where these activities are performed on paper or in unrelated spreadsheets, the school
pays for the same information several times over — in clerical effort, in transcription
errors, and in decisions taken on stale data.

Web-based information systems offer a standard remedy: a single shared database, a
browser front end that needs no client installation, and access controlled by the role of
the person signing in. This project builds such a system for the school context described
in the proposal, and treats the record-keeping workflow end to end — from admission to
report card, and from fee invoice to payment receipt.

## 1.2 Statement of the Problem

The manual and semi-computerised process used in the case-study environment exhibits the
following defects, each of which the system is designed to remove:

1. **Data duplication and inconsistency.** A learner's details are re-entered on the
   admission book, the class register, the examination card and the fees ledger. Any change
   (a correction of a name, a change of guardian phone number) must be repeated in every
   book, and in practice is not.
2. **Slow, error-prone result compilation.** Computing subject totals, term averages,
   percentages, grades and class positions by hand at the end of a term takes days and
   produces arithmetic errors that surface as complaints from parents.
3. **Weak attendance visibility.** Daily registers capture presence but rarely aggregate
   it, so a learner with a chronic absence pattern is often identified only at the end of
   the term.
4. **Poor fee control.** Without a running balance per invoice, part-payments are
   difficult to reconcile, overpayment and double-billing go undetected, and the school
   cannot state its outstanding receivables at a glance.
5. **No access control or audit trail.** Paper files and shared spreadsheet files cannot
   restrict a viewer to their own records, and they cannot record who changed what.
6. **No reporting.** Requests from the principal, parents or the education authority for
   summaries are answered by manual compilation.

## 1.3 Aim and Objectives

The aim is to design and implement a web-based School Management System that automates the
management of school records and produces accurate reports on demand.

The specific objectives are:

1. To design and implement a **student management module** for admission, update, search,
   class assignment and status of learners.
2. To implement a **teacher management module** for staff records, qualifications and
   subject/class assignments.
3. To implement a **class management module** for classes, academic years and class
   composition.
4. To implement a **subject management module** for the subject catalogue and the
   class–subject curriculum.
5. To implement an **attendance management module** that captures daily attendance and
   summarises it per learner and per class.
6. To implement an **examination management module** that creates exam sessions, captures
   scores, computes grades and ranks class positions.
7. To implement a **fee management module** that bills learners, records part- and
   full-payments, and reports outstanding balances.
8. To implement a **report management module** together with secure login and **role-based
   access control** for administrator, teacher and student.

## 1.4 Scope and Limitations

**In scope.** Single-school deployment; three roles; the eight functional objectives above;
a printable academic report sheet; CSV export of tabular reports; a seeded demonstration
dataset.

**Out of scope** (as stated in the proposal, and respected by the implementation): online
learning and course content delivery, video conferencing, biometric attendance capture,
and complex financial accounting (general ledger, payroll, tax and final accounts).
Attendance is captured by roll-call, not by biometric device. Fees are tracked as invoices,
payments and balances — not as a double-entry accounting system.

**Limitations of the study.** The system was validated against a synthetic but realistic
dataset of 18 learners, 6 staff, 3 classes and 8 subjects because access to a live school's
personal data required approvals outside the project period. The prototype is a single-node
deployment; multi-campus and multi-tenancy designs were not investigated.

## 1.5 Significance of the Study

The work is significant to four constituencies. **School administrators** obtain a single
source of truth and instant answers to "how many", "who owes what" and "who is at risk".
**Teachers** spend their preparation time on teaching rather than on transcription, and see
a class's performance and attendance in one view. **Learners and parents** gain timely,
accurate access to results, attendance and fee status, which is a precondition for
educational accountability. **The academic community** gains a documented, tested,
fully-readable implementation of the classic information-systems case study, including its
security design and its automated test suite.

## 1.6 Alignment with Sustainable Development Goal 4

SDG 4 aims to "ensure inclusive and equitable quality education and promote lifelong
learning opportunities for all". Target 4.c and the SDG 4 indicator framework depend on
reliable education data: without accurate enrolment, attendance and achievement records, a
school cannot identify learners who are falling behind, and an education authority cannot
measure progress. This system contributes at the institutional layer — it makes the
attendance, achievement and fee data that quality-education monitoring depends on
complete, current and queryable, and it removes the financial opacity that most often
keeps learners out of school.

## 1.7 Organisation of the Report

Chapter Two reviews the concepts, existing practice and technology literature. Chapter
Three analyses the problem domain and states the requirements, feasibility and method.
Chapter Four presents the design: architecture, data model, process model, behavioural
model, access-control and security design. Chapter Five reports the implementation and the
testing carried out, with results. Chapter Six summarises the work, states the conclusion
and offers recommendations for further work.

---

# Chapter Two: Literature Review

## 2.1 Conceptual Review: the School Management System

A School Management System is a class of **Management Information System (MIS)** specialised
to the education domain. Following Davis's classical definition of an MIS as an organised
collection of people, data and procedures that supports daily operations and
decision-making, the school variant is normally decomposed into modules for admissions and
records, timetabling, attendance, examinations and grading, fees and bursary, staff
records, and reporting. The modules are not independent: attendance, marks and fees all
reference the learner record, and the learner record references the class, which
references the academic year. This interdependence is precisely why a single relational
database is preferred over per-module spreadsheets, and it is the reason the relational
model (Codd, 1970) remains the correct storage design for this problem.

## 2.2 Review of Existing Systems and Current Practice

Three current practices dominate in the case-study environment:

* **Pure paper ledgers.** The admission book, class register, examination card and cashbook
  are separate physical artefacts. Integrity is enforced only by periodic manual
  reconciliation, which is expensive and usually skipped.
* **Spreadsheets per function.** A workbook per class or per term removes arithmetic burden
  but multiplies copies of the same entity, has no access control, no concurrency control,
  and no audit trail. Fee balances in particular become unreliable once part-payments are
  recorded across sheets.
* **Commercial school suites.** These are feature-rich but expensive, often hosted abroad,
  and typically bundle modules (e-learning, transport, biometrics) that the school neither
  needs nor can maintain, which raises both cost and complexity.

## 2.3 Technology Review

The proposal specified a LAMP-class stack: HTML, CSS/Bootstrap, JavaScript on the client;
PHP on the server; MySQL on the database; XAMPP/WAMP as the local environment; Visual
Studio Code as the editor. That is an appropriate and widely taught architecture, and the
design produced in this project is deliberately **faithful to it**: the database is written
in MySQL-compatible DDL (see `schema/mysql_schema.sql`), the server exposes an HTTP JSON
API, and the client is ordinary HTML/CSS/JavaScript.

Two facts constrained the implementation actually delivered. First, the target development
machine had no PHP runtime, no MySQL server and no package manager available, so a
PHP/MySQL build could not be compiled, run or tested on it. Second, the project's testing
objective required that the system be executed and verified, not merely written. The
implementation therefore uses the **Python 3 standard library** for the server tier and
**SQLite** for storage, both of which are present by default, while keeping the SQL design
MySQL-shaped (views, `CHECK` constraints, `FOREIGN KEY` constraints, `UNIQUE` constraints
and upsert semantics). The trade-off is analysed in section 3.8; the consequence is that
the schema, the endpoints and the client can be ported to PHP/MySQL without redesign.

On the client, the review of frameworks (React, Vue, Angular) favoured none of them for
this problem: the interface is a set of tabular forms and reports, and a hand-written
vanilla-JavaScript single-page application keeps the deliverable readable, dependency-free
and auditable — an important consideration for an academic project that must be defended
line by line.

## 2.4 Gap Identified

The literature and the field practice reviewed above leave a clear gap: an **open,
readable, secure, low-cost** system that covers the eight record-keeping functions of a
small secondary school *without* the unneeded modules of commercial suites, that runs on
commodity hardware, and whose security and correctness are demonstrated by automated
tests rather than asserted. That gap is what this project addresses.

---

# Chapter Three: System Analysis and Requirements

## 3.1 Analysis of the Existing System

The existing workflow was modelled as: admission → paper file → manual class register →
manual examination card → hand-computed result sheet → manual cashbook entry. Each arrow
is a re-keying step. Data about one learner exists in four places with no enforced
identity, so the "current" value of a guardian phone number is undefined. There is no
concept of a permission: anyone with physical access to the office can read or alter any
record, and no evidence of the alteration survives.

## 3.2 Analysis of the Proposed System

The proposed system replaces the chain with one shared store. Each record is entered once
and referenced by identifier elsewhere. Validation and referential integrity are enforced
at the database boundary; business rules (a score may not exceed the exam's maximum, a
payment may not exceed the outstanding balance) are enforced in the service layer; every
read is filtered by the signed-in user's role. Reports are computed from the stored data
rather than transcribed alongside it, so they cannot disagree with it.

## 3.3 Functional Requirements

| ID | Requirement | Module |
| --- | --- | --- |
| FR-01 | The system shall create, update, search, paginate, assign to class, and retire student records. | Student |
| FR-02 | The system shall maintain teacher records including qualification and specialisation. | Teacher |
| FR-03 | The system shall assign a teacher to a class–subject pair and list a teacher's load. | Teacher |
| FR-04 | The system shall maintain classes with level and academic year, and a homeroom teacher. | Class |
| FR-05 | The system shall maintain a subject catalogue and the set of subjects offered per class. | Subject |
| FR-06 | The system shall record daily attendance per class as present, absent, late or excused. | Attendance |
| FR-07 | The system shall summarise attendance rate per learner and per class for a term. | Attendance |
| FR-08 | The system shall create examination sessions per class, subject, term and academic year. | Examination |
| FR-09 | The system shall capture and update scores for a class cohort, rejecting out-of-range values. | Examination |
| FR-10 | The system shall compute percentage, grade, remark and class position automatically. | Examination |
| FR-11 | The system shall raise fee invoices per learner, term and item. | Fee |
| FR-12 | The system shall record cash, transfer, mobile-money and cheque payments, including part-payments. | Fee |
| FR-13 | The system shall report billed, collected, outstanding and collection rate, and refuse overpayment. | Fee |
| FR-14 | The system shall generate a printable report card, class results, attendance and fee reports. | Report |
| FR-15 | The system shall export tabular reports as CSV. | Report |
| FR-16 | The system shall authenticate users, end sessions on logout, and enforce role-based access. | User |
| FR-17 | The system shall let an administrator create, deactivate and delete accounts. | User |
| FR-18 | The system shall record security-relevant events in an audit trail visible to the administrator. | User |

## 3.4 Non-Functional Requirements

| ID | Characteristic | Requirement as implemented |
| --- | --- | --- |
| NFR-01 | Security | Passwords stored only as PBKDF2-HMAC-SHA256 digests (200,000 rounds, per-user salt). Session cookie is `HttpOnly`, `SameSite=Strict`, 8-hour expiry. |
| NFR-02 | Input validation | Every field type-checked, length-checked and range-checked server-side; enumerated values validated against whitelists. |
| NFR-03 | Injection resistance | All SQL is parameterised; sort columns and export kinds are whitelisted identifiers, never interpolated strings. |
| NFR-04 | Cross-site scripting resistance | The client builds DOM nodes with `createElement`/`textContent`; no user data is ever assigned to `innerHTML`. A Content Security Policy header restricts script and style sources to the origin. |
| NFR-05 | Privacy by scope | A student's role can read only their own records; a teacher only for class–subject pairs assigned to them. |
| NFR-06 | Integrity | Foreign keys enforced; unique business keys on admission number, staff number, username, invoice identity and mark identity. |
| NFR-07 | Performance | Sub-second response on the seeded dataset; indexed lookups on class, exam, student and date. |
| NFR-08 | Usability | Single navigation model, responsive down to mobile width, printable report sheet. |
| NFR-09 | Portability | Runs from a source directory with no installation step; standard library only. |
| NFR-10 | Testability | 35 automated end-to-end tests over the HTTP API, plus manual browser verification per role. |
| NFR-11 | Maintainability | Layered separation of routing, service, domain/reporting and persistence; 4,700 lines total. |

## 3.5 Users and Access Levels

| Role | Level | Principal responsibilities |
| --- | --- | --- |
| Administrator | 3 | Full create/read/update/delete over all modules; user accounts; audit trail; fee receipts; all reports. |
| Teacher | 2 | Read school structure; take attendance and enter scores **only** for assigned class–subjects; read results of their classes; view reports. |
| Student | 1 | Read **only their own** results, attendance summary, fee position and report card; change their own password. |

Level semantics: a request is served only if `level(role) >= level(required)` **and** the
record-level scope check for that role passes. Both conditions are required; satisfying the
role level alone never widens data scope.

## 3.6 Feasibility Study

**Technical.** The architecture uses only components available on the target machine
(Python 3.9 standard library, SQLite 3.43, any modern browser). No custom native code, no
network service dependencies. Demonstrated feasible by the working prototype.

**Economic.** The proposal budgeted USD 400 for a PHP/MySQL/XAMPP build. The delivered
implementation uses no licensed software and no hosting: development and deployment cost is
effectively limited to hardware already owned, so the project finishes within budget.

**Operational.** Staff already work with tables of learners and terms; the interface mirrors
the class register and the fee ledger. Training reduces to a login and a menu. A seeded
demonstration dataset allows the school to trial the system before entering live records.

**Schedule.** Delivered within the project period using six iterations (section 3.7).

## 3.7 Development Methodology

**Agile** iteration was used, as proposed. Work was organised into short increments, each
of which was demonstrated and tested before the next began, so that defects in the data
model were found while they were still cheap to correct.

| Iteration | Deliverable | Exit test |
| --- | --- | --- |
| 1 | Requirements, schema, seed data | Schema creates; demo data loads deterministically |
| 2 | Authentication, sessions, RBAC | Login/logout/401 and role tests pass |
| 3 | Student, teacher, class, subject modules | CRUD and validation tests pass |
| 4 | Examination, grading, positions | Marks save, grade and position tests pass |
| 5 | Attendance and fee modules | Attendance idempotency and overpayment tests pass |
| 6 | Reports, CSV export, web UI, hardening | Full suite passes; UI verified in browser for all three roles |

## 3.8 Tools and Technologies

| Layer | Proposed in the project proposal | Used in the delivered prototype | Rationale |
| --- | --- | --- | --- |
| Markup | HTML5 | HTML5 | Unchanged |
| Presentation | CSS / Bootstrap | Hand-written CSS (355 lines) | No CDN dependency; works offline; no unused framework weight |
| Client logic | JavaScript | Vanilla JavaScript SPA (1,561 lines) | Unchanged; hash routing, DOM built with `textContent` |
| Server logic | PHP | Python 3 standard library `http.server` | PHP runtime not installable on the target machine; keeps the prototype runnable anywhere |
| Database | MySQL | SQLite 3 (SQL written in MySQL-compatible form) | No MySQL server available; `schema/mysql_schema.sql` is provided for the MySQL deployment |
| Local environment | XAMPP / WAMP | `python3 run.py` | Equivalent role: provides the HTTP server and the database |
| Editor | Visual Studio Code | Visual Studio Code | Unchanged |
| Testing | Manual | `unittest` end-to-end suite (35 tests) + manual browser verification | Objective 8 requires demonstrable correctness |

The substitution is confined to the execution tier. The relational design, the request/response
contract and the browser client are unchanged in character, which is why the MySQL
script in `schema/` is a port rather than a rewrite.

## 3.9 Hardware and Software Requirements

**Server.** Any machine with Python ≥ 3.7 and ≥ 512 MB free RAM; 100 MB disk for the
database at the scale of a small school. **Client.** Any evergreen browser (Chrome, Edge,
Firefox, Safari) from roughly 2018 onward; 1,024 px or wider recommended, with a mobile
layout provided. **Development.** macOS/Linux/Windows with Python 3 and Visual Studio Code.

---

# Chapter Four: System Design

## 4.1 Architectural Overview

The system is a three-tier web application:

```
Browser (HTML + CSS + vanilla-JS SPA, hash routing)
        |  HTTP/JSON, session cookie
Application server (ThreadingHTTPServer -> router -> handler -> service)
        |  parameterised SQL
Relational store (SQLite; MySQL-compatible schema supplied)
```

Request handling is: parse and authenticate → resolve route → enforce role and scope →
validate input → execute parameterised SQL → commit (or roll back on error) → serialise
JSON. One database connection is opened per request and closed in a `finally` block, so no
connection can leak under concurrent load.

## 4.2 Data Model

**Figure 1 — Entity Relationship Diagram:** `diagrams/figure-erd.svg`

Fourteen entities were identified. They fall into four groups:

* **Identity and control:** `users` (one row per login, with role), `audit_log`.
* **People:** `teachers`, `students`, each optionally linked to a `users` row so that a
  person record can exist before an account is issued.
* **Structure:** `classes`, `subjects`, and the two associative entities `class_subjects`
  (a class offers a subject) and `teacher_assignments` (a teacher teaches a subject to a
  class). Both resolve many-to-many relationships, and `teacher_assignments` doubles as the
  authority for teacher data scope.
* **Transactions:** `exam_sessions` → `marks`, `attendance_records`,
  `fee_invoices` → `fee_payments`, plus the `grade_scales` lookup.

Cardinality highlights: one class has many students (0..1 login per student); one
`exam_session` has at most one mark per student, enforced by `UNIQUE(exam_id, student_id)`;
one invoice has many payments, and its balance is derived, never stored.

## 4.3 Normalisation

The schema is in third normal form. Every non-key attribute depends on the whole key
(`attendance_records` carries `date` and `period` because a learner may be marked once per
period), on the key and on nothing else. Derived values are excluded from base tables:
`amount_paid` and `balance` are computed from `fee_payments`, and `percentage` from
`score` and `max_marks`. Denormalisation was applied in exactly one place —
`attendance_records.class_id` — to make class-scoped queries and class-scoped permission
checks single-table operations; the redundancy is reconciled at write time by validating
that the learner belongs to that class.

## 4.4 Physical Schema

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `users` | Login identity and role | UNIQUE(username), UNIQUE(email), CHECK role ∈ {admin, teacher, student} |
| `teachers` | Staff records | UNIQUE(staff_no), FK user_id → users |
| `classes` | Class per academic year | UNIQUE(name), FK homeroom_teacher_id → teachers |
| `students` | Learner records | UNIQUE(admission_no), FK user_id, FK class_id, CHECK gender, CHECK status |
| `subjects` | Subject catalogue | UNIQUE(code), CHECK category |
| `class_subjects` | Curriculum per class | UNIQUE(class_id, subject_id), FKs ON DELETE CASCADE |
| `teacher_assignments` | Teaching load and permission scope | UNIQUE(teacher_id, class_id, subject_id) |
| `exam_sessions` | An assessment instrument | UNIQUE(class, subject, title, term, year), CHECK max_marks > 0 |
| `marks` | Score per learner per exam | UNIQUE(exam_id, student_id), CHECK score ≥ 0 |
| `attendance_records` | Roll-call entry | UNIQUE(student_id, date, period), CHECK status |
| `fee_invoices` | Bill line | UNIQUE(student, term, year, description), CHECK amount_due ≥ 0 |
| `fee_payments` | Receipt against an invoice | CHECK amount > 0, FK invoice CASCADE |
| `grade_scales` | Grade boundaries as data | min_pct / max_pct / grade / remark |
| `audit_log` | Security-relevant events | FK user_id |

Three views implement the reporting layer: `v_student_results` (score normalised to
percentage), `v_fee_balances` (invoice with paid and balance) and `v_attendance_summary`
(sessions, attended, absent, rate).

## 4.5 Process Model

**Figure 2 — Context diagram (DFD level 0):** `diagrams/figure-dfd-0.svg`
**Figure 3 — DFD level 1:** `diagrams/figure-dfd-1.svg`

Level 0 shows the system as one process exchanging data with four external entities: the
Administrator, the Teacher, the Student and the Project Supervisor. Level 1 decomposes it
into nine processes, P1 authentication through P9 reporting, each shown against the data
stores it maintains. P1 is deliberately the only entry point for credentials: no other
process accepts a password, which mirrors the running system where every handler sits
behind one session check.

## 4.6 Behavioural Model

**Figure 4 — Use case diagram:** `diagrams/figure-use-case.svg`

Twenty-two use cases are grouped by primary actor. `Authenticate user` is included by every
other use case (`«include»`), and `Export report as CSV` extends `Generate class results`
(`«extend»`), matching the optional export control in the reports view.

**Use-case specification — UC-09 Enter examination scores**

| Field | Description |
| --- | --- |
| Actor | Teacher (secondary: Administrator) |
| Precondition | Teacher is authenticated and is assigned to the class–subject of the exam session |
| Main flow | Teacher selects class, subject and session; the system lists the class cohort; teacher enters scores; teacher submits |
| System behaviour | Each score is validated against the session's maximum; valid rows are upserted on `(exam_id, student_id)`; out-of-range rows are reported as skipped, not stored |
| Postcondition | `marks` reflects the submitted scores; `audit_log` records the entry |
| Exceptions | Not assigned → 403; learner not in the exam's class → rejected; malformed payload → 400 |

**Use-case specification — UC-14 Record fee payment**

| Field | Description |
| --- | --- |
| Actor | Administrator |
| Precondition | Invoice exists and has a positive balance |
| Main flow | Administrator selects invoice, enters amount, method and date |
| System behaviour | Amount is checked against the outstanding balance; on success the payment is inserted and the derived balance reduced |
| Postcondition | `v_fee_balances.balance` = amount_due − Σ payments, and never negative |
| Exceptions | Overpayment → 400 with the permitted maximum reported |

## 4.7 Access Control Design

Two independent checks are applied to every request.

**Vertical check (role level).** `has_role(user.role, required)` compares against the
lattice student 1 < teacher 2 < admin 3.

**Horizontal check (data scope).**

| Operation | Scope rule enforced |
| --- | --- |
| Read a student record | Student may read only their own id |
| Read results / attendance / fees | Student sees only rows where `student_id` = their own |
| Read exams, save marks, save attendance | Teacher restricted to `teacher_assignments` rows naming them |
| Create exam, delete records, manage users | Administrator only |
| Dashboard | Aggregates computed inside the caller's scope; the audit trail is omitted for non-administrators |

The scope rules are implemented in the service layer, not in the browser, so a hand-crafted
HTTP request cannot bypass them. This was verified by tests that call the API directly with
a student's session cookie.

## 4.8 Security Design

| Threat | Control |
| --- | --- |
| Credential disclosure | PBKDF2-HMAC-SHA256, 200,000 rounds, 16-byte random per-user salt; comparison with `hmac.compare_digest` to avoid timing leaks |
| Session hijacking | 256-bit random token, `HttpOnly`, `SameSite=Strict`, `Path=/`, 8-hour expiry, revoked server-side on logout, deactivation and password change |
| SQL injection | Every statement parameterised; ORDER BY columns and export kinds resolved from fixed whitelists |
| Cross-site scripting | DOM built with `createElement`/`textContent`; no `innerHTML` on user data; CSP `script-src 'self'`, `style-src 'self'`, `default-src 'self'` |
| Cross-site request forgery | `SameSite=Strict` cookie plus JSON request bodies; no state change on GET |
| Path traversal on static files | Requested path resolved and required to stay inside the web root |
| Privilege escalation | Role level *and* record scope checked server-side; an administrator cannot deactivate their own account |
| Insider tampering | `audit_log` of logins, account changes, deletions, mark and attendance submissions |
| Information leakage on failure | Unhandled exceptions return a generic 500; tracebacks go to the server log only |

## 4.9 Interface Design

Navigation is generated from the signed-in user's role, so a student never sees an
administrative control. The screen inventory is:

| View | Roles | Content |
| --- | --- | --- |
| Login | all | Username and password; demo credential hints |
| Dashboard | all | Role-appropriate statistics, recent activity, quick links |
| Students | admin, teacher | Searchable, paginated table; add/edit; per-student drawer with results, attendance and fees |
| Teachers | admin, teacher | Staff table; add/edit; teaching-load assignment |
| Classes | admin, teacher | Classes with enrolment counts; curriculum assignment |
| Subjects | admin, teacher | Subject catalogue; core/elective |
| Examinations | admin, teacher | Sessions; marks grid with per-row validation and save summary |
| Attendance | admin, teacher | Class + date picker with present/absent/late/excused toggles |
| Fees | admin | Invoices, payments, billed/collected/outstanding/collection-rate |
| Reports | admin, teacher | Results, attendance and fee reports with CSV export |
| Users | admin | Accounts, roles, activation, password reset |
| My results / My attendance / My fees | student | Personal report sheet, attendance summary, fee position |

The layout is a sidebar-plus-content shell that collapses to a single column below 940 px,
and a dedicated print stylesheet renders the report sheet without navigation.

## 4.10 Report Generation Design

Grading is data-driven: percentage = score × 100 / max_marks, and the grade and remark are
looked up from `grade_scales` (A 75–100 Excellent … F 0–40 Fail). A learner's term
performance per subject combines every session for that subject, weighting each session by
its maximum, so a 20-mark quiz contributes proportionally less than a 100-mark exam. Class
position is computed with **competition ranking** — learners with identical averages share
a rank and the next rank is skipped — which is the convention the school's result sheets
already use. Report cards, class results, attendance summaries and fee statements are all
produced from the same views that the dashboards use, so a report can never disagree with
the screen it was drawn from.

---

# Chapter Five: Implementation and Testing

## 5.1 Implementation

| Component | File | Lines | Implements |
| --- | --- | --- | --- |
| Persistence and schema | `sms/db.py` | 249 | Objective 1–7 data model, views, seeding |
| Authentication and RBAC | `sms/auth.py` | 81 | Objective 8 (secure login, access control) |
| Routing | `sms/router.py` | 53 | URL pattern compilation and method dispatch |
| Service layer | `sms/api.py` | 1,234 | Objectives 1–8, 50 endpoints, validation, scope rules |
| Reporting engine | `sms/reports.py` | 215 | Objective 8: grading, positions, class/attendance/fee reports, CSV |
| HTTP server | `sms/server.py` | 231 | Request lifecycle, sessions, static files, CSP |
| Demonstration data | `sms/demo.py` | 219 | Realistic seed dataset |
| Browser client | `web/app.js`, `web/styles.css`, `web/index.html` | 1,932 | All views, forms, tables, print sheet |
| Test suite | `tests/test_api.py` | 430 | 35 end-to-end tests |

Notable implementation decisions:

* **Idempotent writes.** Attendance submission uses an upsert on
  `(student_id, date, period)`, so a teacher who submits the same register twice does not
  create duplicate rows.
* **Partial acceptance of marks.** A marks submission containing an out-of-range score
  stores the valid rows and returns the rejected ones as `skipped`, rather than failing the
  whole sheet — a teacher correcting one cell should not lose the other thirty.
* **Derived balances.** No `balance` column exists. It is computed in `v_fee_balances`, so
  it cannot drift from the payments that produced it.
* **Deterministic seeding.** The demonstration dataset is generated from a fixed random
  seed, so every reviewer sees identical numbers and the figures in this report are
  reproducible.

## 5.2 Demonstration Dataset

18 learners across 3 classes (JSS 1A, JSS 2A, SSS 1A), 6 teaching staff, 8 subjects, 32
examination sessions (100-mark examinations and 20-mark continuous assessment), 192 marks,
20 school days of attendance (360 records), 36 fee invoices and 26 payments. Every learner
and staff member has a working login.

## 5.3 Testing Strategy

Four levels were applied: **schema/seed validation** (constraints reject bad rows; the seed
loads and reconciles), **service-level testing** through the real HTTP interface with an
isolated temporary database, **manual functional testing** of every view in a browser for
each of the three roles, and **security testing** by issuing API calls directly with
low-privilege session cookies and with crafted input.

## 5.4 Test Cases and Results

| # | Test | Type | Expected | Result |
| --- | --- | --- | --- | --- |
| 1 | Login with wrong password | Functional/security | 401, no session | Pass |
| 2 | Access API without session | Security | 401 on every protected route | Pass |
| 3 | SQL-injection login attempt (`' OR '1'='1`) | Security | Rejected, no bypass | Pass |
| 4 | Logout revokes session | Security | Subsequent request 401 | Pass |
| 5 | Student lists students | Security | 403 | Pass |
| 6 | Student creates student | Security | 403 | Pass |
| 7 | Teacher deletes student | Security | 403 | Pass |
| 8 | Teacher lists exams | Scope | Only assigned class–subjects | Pass |
| 9 | Student reads another learner | Privacy | 403/404 | Pass |
| 10 | Self-service registration issues login | Functional | Session created | Pass |
| 11 | Invalid payload | Validation | 400 with field message | Pass |
| 12 | Missing record | Validation | 404 | Pass |
| 13 | Duplicate business key | Integrity | 409 | Pass |
| 14 | Pagination and search | Functional | Correct page and count | Pass |
| 15 | Save marks then read back | Functional | Values persisted | Pass |
| 16 | Score above exam maximum | Validation | Rejected/skipped | Pass |
| 17 | Marks for unassigned subject (teacher) | Security | 403 | Pass |
| 18 | Mark for learner outside exam class | Validation | Rejected | Pass |
| 19 | Report card grades and positions | Functional | Matches grading scale | Pass |
| 20 | Position ordering by average | Functional | Competition ranking | Pass |
| 21 | Attendance save then re-post | Integrity | Idempotent, no duplicates | Pass |
| 22 | Attendance for learner in another class | Security | Rejected | Pass |
| 23 | Malformed date | Validation | 400 | Pass |
| 24 | Overpayment | Business rule | 400 | Pass |
| 25 | Payment reduces balance exactly | Functional | balance = due − paid | Pass |
| 26 | Student sees only own fees | Privacy | No foreign rows | Pass |
| 27 | No negative balances anywhere | Integrity | min(balance) ≥ 0 | Pass |
| 28 | CSV export | Functional | `text/csv`, correct header | Pass |
| 29 | Dashboard totals reconcile | Functional | Sum of parts equals total | Pass |
| 30 | Student dashboard hides audit trail | Privacy | Not present | Pass |
| 31 | Unknown route / wrong method | Robustness | 404 / 405 | Pass |
| 32 | Malformed JSON body | Robustness | 400, not 500 | Pass |
| 33 | Deactivation kills live sessions | Security | 401 afterwards | Pass |
| 34 | Administrator cannot disable own account | Safety | Rejected | Pass |
| 35 | Change password flow | Security | Old session revoked, new login works | Pass |

**Result: 35 of 35 tests pass** (`python3 -W ignore -m unittest tests.test_api`, 18.9 s).

## 5.5 Defects Found and Corrected During Development

Recording these is part of the Agile evidence trail; each was found by testing and fixed
before delivery.

1. **Mis-targeted fee payment in the seed.** A cursor variable was reused, so an
   examination payment was booked against the tuition invoice, producing a negative
   balance. Found by the balance-reconciliation test; fixed by capturing the correct insert
   key. A `min(balance) ≥ 0` assertion was added to the suite.
2. **Malformed JSON returned HTTP 500.** The body parser raised its error outside the
   handler that converted it to a response. Fixed by restructuring the request lifecycle so
   all expected errors are converted in one place.
3. **Keep-alive desynchronisation.** Early 401/404/405 responses returned without draining
   the request body, corrupting the next response on the same connection. Fixed by reading
   the body before any routing decision.
4. **`PATCH` unsupported (501).** Account-activation calls failed. Fixed by adding the
   method to the handler.
5. **Teachers could not reach Reports.** The role's navigation list named a view key that
   had no menu group. Fixed in the role-link table and re-verified in the browser.
6. **Content Security Policy injected as malformed markup.** An unescaped quote truncated
   the `<head>`, breaking the page entirely. Fixed by sending CSP as an HTTP header rather
   than as generated markup — caught only by reading the browser console, which is why
   browser verification is retained as a test level.
7. **Mobile top bar ordering.** A CSS `order` rule applied to a shared class reordered
   unrelated buttons. Fixed with explicit per-element order values.

## 5.6 Verification in the Browser

The delivered interface was exercised end to end for all three roles: administrator
dashboards and CRUD on each module, teacher marks grid and attendance register, student
personal report sheet. Console output is clean apart from the expected pre-login 401. The
student report sheet renders the school header, term, subject rows with assessment and
examination scores, summary tiles (term average, grade, position, attendance rate, fees
owing) and the grading-scale footnote.

---

# Chapter Six: Summary, Conclusion and Recommendations

## 6.1 Summary

The project set out to replace duplicated, uncontrolled paper and spreadsheet record-keeping
in a secondary school with a single, secure, web-based system. It analysed the existing
workflow, elicited 18 functional and 11 non-functional requirements, designed a normalised
14-table relational model with three reporting views, implemented 50 endpoints and a
browser client, and verified the result with 35 automated tests and manual browser
verification across three roles.

| Objective | Delivered as | Evidence |
| --- | --- | --- |
| 1 Student management | `students` table + CRUD/search/pagination | FR-01; tests 5, 6, 7, 9, 14 |
| 2 Teacher management | `teachers`, `teacher_assignments` | FR-02, FR-03; tests 8, 17 |
| 3 Class management | `classes`, enrolment and homeroom | FR-04; dashboard reconciliation test 29 |
| 4 Subject management | `subjects`, `class_subjects` | FR-05; schema constraints |
| 5 Attendance management | `attendance_records`, `v_attendance_summary` | FR-06, FR-07; tests 21, 22, 23 |
| 6 Examination management | `exam_sessions`, `marks`, grading, positions | FR-08–FR-10; tests 15–20 |
| 7 Fee management | `fee_invoices`, `fee_payments`, `v_fee_balances` | FR-11–FR-13; tests 24–27 |
| 8 Reports, secure login, RBAC | `reports.py`, `auth.py`, report views, CSV | FR-14–FR-18; tests 1–4, 10, 28, 30–35 |

## 6.2 Conclusion

All eight objectives in the proposal were met and demonstrated in a running system. The
work makes the point that the essential value of a school management system is not feature
count but **data integrity under controlled access**: once each fact is stored once,
correctly typed, related by enforced keys and readable only by those entitled to it, the
reports the school needs become arithmetic rather than clerical work. The graded result
sheet, the class position and the outstanding fee balance in this prototype are all derived
from the same records, which is why they cannot contradict one another — the failure mode
that makes manual ledgers unreliable.

The technology substitution in section 3.8 does not weaken the design. The relational
schema is delivered in MySQL form alongside the SQLite implementation, the server boundary
is an ordinary HTTP JSON API, and the client is standard HTML/CSS/JavaScript; a PHP/MySQL
deployment is therefore a port of the same design rather than a new project.

## 6.3 Recommendations and Future Work

1. **Port to the originally proposed stack.** Move the schema to MySQL and reimplement the
   service layer in PHP if the school's hosting environment requires it; `schema/mysql_schema.sql`
   is written for that purpose.
2. **Timetable generation.** A constraint-satisfaction module for lessons, rooms and
   teacher availability is the natural next module and the one most requested by schools.
3. **Authentication hardening.** Add rate limiting and lockout on failed logins, and
   optional time-based one-time passwords; move sessions from memory to a persistent store
   so that restarts do not sign everyone out.
4. **Transport and messaging.** SMS/email notification of results and fee reminders to
   guardians, within the school's data-protection obligations.
5. **Role granularity.** Separate "bursar" and "exams officer" roles from the general
   administrator so that least privilege is finer-grained.
6. **Multi-session attendance.** Period-level registers per subject rather than one daily
   roll-call, if the school adopts subject-based teaching.
7. **Biometrics and e-learning remain out of scope** by design and should be evaluated
   separately, as they carry cost and data-protection implications disproportionate to
   their benefit at this school size.

---

## References

1. Beck, K. *et al.* (2001) *Manifesto for Agile Software Development*. agilealliance.org.
2. Codd, E. F. (1970) 'A relational model of data for large shared data banks',
   *Communications of the ACM*, 13(6), pp. 377–387.
3. Davis, G. B. (1974) *Management Information Systems: Conceptual Foundations, Structure
   and Development*. New York: McGraw-Hill.
4. High Level Owasp (2021) *OWASP Top 10 — A01 Broken Access Control through A10 Server
   Side Request Forgery*. owasp.org.
5. International Organization for Standardization (2015) *ISO/IEC 25010:2011 Systems and
   software quality requirements and evaluation (SQuaRE)*. Geneva: ISO.
6. Pressman, R. S. and Maxim, B. R. (2015) *Software Engineering: A Practitioner's
   Approach*. 8th edn. New York: McGraw-Hill.
7. Sommerville, I. (2016) *Software Engineering*. 10th edn. Harlow: Pearson.
8. United Nations (2015) *Transforming our world: the 2030 Agenda for Sustainable
   Development*, Resolution A/RES/70/1. New York: UN General Assembly.
9. Elmasri, R. and Navathe, S. (2016) *Fundamentals of Database Systems*. 7th edn.
   Pearson.

> **Note for the candidate.** References 1–9 are the general methodological and technical
> sources for this work. Your institution will normally expect several *empirical* studies
> of school information systems in the local context; add those from your own reading list
> and replace the generic wording in Chapter Two where a specific study is cited.

---

## Appendix A — Installation and User Manual

### A.1 Running the prototype

```bash
cd /Users/sukesukari/Downloads/rita
python3 run.py                 # http://127.0.0.1:8000
python3 run.py --port 8123     # alternate port
python3 run.py --reset         # rebuild and reseed the demonstration database
```

No installation, no dependencies, no internet access required. The database is created and
seeded automatically on first run at `data/school.db`.

### A.2 Demonstration logins

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `Admin@123` |
| Teacher | `teacher1` … `teacher6` | `Teach@123` |
| Student | `student1` … `student18` | `Student@123` |

These credentials exist only in the seeded demonstration database. Change them before any
use with real records, and never expose the service to an untrusted network without a
TLS-terminating reverse proxy.

### A.3 Typical workflows

**Admit a learner.** Students → Add student → complete admission number, names, gender,
date of birth, class and guardian details. Tick *create login* to issue an account.

**Assign teaching.** Teachers → select staff member → assign class and subject. This
assignment is what grants the teacher access to that class's attendance and marks.

**Run an examination.** Examinations → New session (class, subject, term, title, maximum
marks) → open the marks grid → enter scores → Save. Out-of-range entries are reported and
skipped; valid ones persist.

**Take the register.** Attendance → choose class and date → mark each learner → Save.
Re-saving the same date updates rather than duplicates.

**Bill and receipt fees.** Fees → New invoice → record payment with amount, method and
date. The system refuses any payment greater than the outstanding balance.

**Produce reports.** Reports → Results / Attendance / Fees; choose term and class; use
Export CSV for spreadsheet analysis, or print the learner's report sheet from the student
drawer.

## Appendix B — API Reference

All endpoints are JSON over HTTP and require a session cookie except `POST /api/auth/login`.
Errors are `{"error": "message"}` with the matching status code.

**Authentication** `POST /api/auth/login` · `POST /api/auth/logout` ·
`GET /api/auth/me` · `POST /api/auth/change-password`

**Reference and dashboard** `GET /api/reference` · `GET /api/dashboard`

**Students** `GET/POST /api/students` · `GET/PUT/DELETE /api/students/{id}`

**Teachers** `GET/POST /api/teachers` · `GET/PUT/DELETE /api/teachers/{id}`

**Classes** `GET/POST /api/classes` · `PUT/DELETE /api/classes/{id}` ·
`GET/POST /api/classes/{id}/subjects` · `DELETE /api/classes/{id}/subjects/{subjectId}`

**Subjects** `GET/POST /api/subjects` · `DELETE /api/subjects/{id}`

**Assignments** `GET/POST /api/assignments` · `DELETE /api/assignments/{id}`

**Examinations** `GET/POST /api/exams` · `DELETE /api/exams/{id}` ·
`GET/PUT /api/exams/{id}/marks`

**Attendance** `GET/POST /api/attendance`

**Fees** `GET/POST /api/fees/invoices` · `DELETE /api/fees/invoices/{id}` ·
`POST /api/fees/payments`

**Reports** `GET /api/reports/results` · `/api/reports/attendance` · `/api/reports/fees` ·
`/api/reports/students/{id}` · `/api/reports/export/{kind}`

**Users** `GET/POST /api/users` · `PUT /api/users/{id}/active` ·
`PUT /api/users/{id}/password` · `DELETE /api/users/{id}`

## Appendix C — Project Structure

```
rita/
├── run.py                    entry point (--host, --port, --reset)
├── sms/                      application server
│   ├── server.py             HTTP lifecycle, static files, CSP
│   ├── router.py             URL pattern matching
│   ├── api.py                50 endpoints: validation, RBAC, scope
│   ├── auth.py               password hashing, sessions, role lattice
│   ├── db.py                 schema, views, connection, bootstrap
│   ├── reports.py            grading, positions, report and CSV builders
│   ├── demo.py               seeded demonstration data
│   └── http_util.py          response and error types
├── web/                      browser client
│   ├── index.html            application shell
│   ├── app.js                SPA: views, forms, tables, print sheet
│   └── styles.css            layout, components, responsive and print rules
├── tests/test_api.py         35 end-to-end tests
├── schema/mysql_schema.sql   MySQL/XAMPP port of the same design
└── docs/                     this documentation and the report figures
    ├── project-documentation.md
    ├── make_diagrams.py      regenerates the figures
    └── diagrams/             figure-erd, figure-dfd-0, figure-dfd-1, figure-use-case
```

## Appendix D — Figures

| Figure | File | Insert at |
| --- | --- | --- |
| 1 Entity Relationship Diagram | `docs/diagrams/figure-erd.svg` | Section 4.2 |
| 2 Context diagram (DFD level 0) | `docs/diagrams/figure-dfd-0.svg` | Section 4.5 |
| 3 Data Flow Diagram level 1 | `docs/diagrams/figure-dfd-1.svg` | Section 4.5 |
| 4 Use Case Diagram | `docs/diagrams/figure-use-case.svg` | Section 4.6 |
| 5+ System screenshots | capture from the running prototype | Section 4.9 / Chapter Five |

The SVG figures are self-contained vector images: open them in a browser, or insert them
directly into the report document. To change a figure, edit the coordinate tables in
`docs/make_diagrams.py` and re-run `python3 docs/make_diagrams.py`.

For the screenshots, run `python3 run.py`, sign in as each role in turn and capture the
dashboard, the students table, the marks grid, the attendance register, the fees view, the
reports view and the printed student report sheet.
