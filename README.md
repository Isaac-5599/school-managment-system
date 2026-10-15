# School Management System

A working implementation of *Design and Implementation of a School Management System*
(Bachelor of Computer Science, Starford International University) — a role-controlled web
application for student, teacher, class, subject, attendance, examination, fee and report
management.

Zero dependencies: Python 3 standard library on the server, SQLite for storage,
vanilla HTML/CSS/JavaScript in the browser. No installation, no CDN, works offline.

## Deploying to Render (free tier)

Render needs the code in a git repository it can read. The app is ready as-is: it honours
the `PORT` environment variable, binds `0.0.0.0` when told to, and opens its socket before
seeding the demonstration database so the health check passes.

1. Push this directory to a repository — GitHub, or Render's own Git repository
   (dashboard → **Create → Git Repository**, which avoids a third-party account).
2. In Render, choose **New → Blueprint** and pick the repository. `render.yaml` pre-fills
   everything: Python environment, free plan, start command `python3 run.py --host 0.0.0.0`,
   health check on `/`.
3. Click **Deploy**. The first build takes a couple of minutes; the service then reseeds
   its own demo database on every boot.

If you prefer the manual route, use **New → Web Service** with *Runtime* Python and the
same start command.

### What to expect on the free plan

* The URL is `https://<service-name>.onrender.com`. It is reachable from anywhere, so the
  demonstration logins below are live on the public internet. Treat them as throwaway, or
  change them from **Users** immediately after deploying.
* Idle instances sleep after ~15 minutes; the next request takes 30–60 seconds to wake.
* The filesystem is **ephemeral**. Records entered during a session survive normal use but
  are wiped on redeploy or restart, and the demo data is regenerated. For permanent school
  records you need a persistent disk (paid plan) or the MySQL backend.
* Sessions are held in memory, so a restart signs everyone out. That is deliberate for a
  single-instance academic prototype.

### Before using it with real records

* Serve it only over Render's HTTPS (already the case) and change every seeded password.
* Replace the demonstration accounts: **Users → Add user** for staff, and issue each learner
  a login from their student record.
* Consider a persistent disk, or port the service layer to PHP/MySQL using
  [`schema/mysql_schema.sql`](schema/mysql_schema.sql).

## Run it locally

```bash
python3 run.py                 # then open http://127.0.0.1:8000
python3 run.py --port 8123     # if 8000 is busy
python3 run.py --reset         # rebuild and reseed the demonstration database
```

The database is created and seeded on first run at `data/school.db`.

## Demonstration logins

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `Admin@123` |
| Teacher | `teacher1` … `teacher6` | `Teach@123` |
| Student | `student1` … `student18` | `Student@123` |

These are seeded demo accounts for an academic demonstration. Change them before using real
records, and put the service behind a TLS-terminating reverse proxy before exposing it to
any network you do not control.

## What is implemented

| Module | Capability |
| --- | --- |
| User & access control | PBKDF2-SHA256 password hashing, 8-hour `HttpOnly`/`SameSite=Strict` sessions, three-role access control with per-record data scoping, audit trail |
| Student | Admission records, search, pagination, class assignment, status, optional auto-created login, per-student drawer with results, attendance and fees |
| Teacher | Staff records, qualifications, class–subject assignments (which also define the teacher's data scope) |
| Class | Classes per academic year, homeroom teacher, enrolment counts, curriculum per class |
| Subject | Subject catalogue, core/elective, class–subject offering |
| Attendance | Daily roll-call per class (present / absent / late / excused), idempotent re-submission, per-learner and per-class summaries |
| Examination | Exam sessions per class/subject/term, marks grid with per-exam maximum enforcement, automatic percentages, grades, remarks and competition-ranked class positions |
| Fee | Invoices per learner/term/item, part- and full-payments, overpayment refusal, billed/collected/outstanding/collection rate |
| Report | Learner report card (printable), class results, attendance and fee reports, CSV export |

50 JSON endpoints · 14 tables + 3 reporting views · 35 automated end-to-end tests.

## Tests

```bash
python3 -W ignore -m unittest tests.test_api
```

The suite starts the server as a subprocess against a temporary database and covers
authentication, session revocation, an SQL-injection login attempt, role and data-scope
enforcement for every module, validation and integrity errors, grading and class positions,
attendance idempotency, fee balance reconciliation, CSV export and dashboard totals.

## Layout

```
run.py            entry point
sms/              server: routing, API, auth, schema, reports, demo data
web/              browser client: index.html, app.js, styles.css
tests/test_api.py end-to-end test suite
schema/           MySQL port of the same design (XAMPP / phpMyAdmin import)
docs/             project documentation, report figures and their generator
```

## Documentation

* [`docs/project-documentation.md`](docs/project-documentation.md) — the full report draft:
  introduction, literature review, requirements and feasibility, design (data model, DFDs,
  use cases, access control, security), implementation, testing and results, conclusion.
* `docs/diagrams/` — ERD, context diagram, DFD level 1 and use-case diagram as printable
  SVG figures. Regenerate with `python3 docs/make_diagrams.py`.
* [`schema/mysql_schema.sql`](schema/mysql_schema.sql) — the same relational design in
  MySQL 8 DDL, for a PHP/MySQL deployment as originally proposed.

## Notes on the stack

The proposal specified PHP + MySQL on XAMPP. This machine has neither a PHP runtime nor a
MySQL server, and no package manager to add them, so the server tier is Python and the
storage is SQLite. Everything else is as proposed: the same relational design (the MySQL
script is provided), the same HTTP JSON API boundary, and the same HTML/CSS/JavaScript
client. Porting the service layer to PHP is a rewrite of one tier, not a redesign.
