"""End-to-end tests for the School Management System API.

Run with:  python3 -m unittest discover -s tests -v
Uses a throwaway database on a temporary port; never touches data/school.db.
"""

import http.client
import json
import os
import shutil
import subprocess
import sqlite3
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="sms-test-")
DB_PATH = os.path.join(TMP, "test.db")
PORT = 8731
BASE = "127.0.0.1"


def request(method, path, body=None, token=None, raw=False):
    headers = {}
    if token:
        headers["Cookie"] = f"sms_session={token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    conn = http.client.HTTPConnection(BASE, PORT, timeout=10)
    conn.request(method, path, body=data, headers=headers)
    response = conn.getresponse()
    payload = response.read()
    cookie = response.getheader("Set-Cookie")
    status = response.status
    conn.close()

    new_token = token
    if cookie and cookie.startswith("sms_session="):
        value = cookie.split(";")[0].split("=", 1)[1]
        new_token = value or None
    if raw:
        return status, payload.decode("utf-8", "replace"), response.getheaders(), new_token
    try:
        return status, json.loads(payload or b"null"), new_token
    except ValueError:
        return status, {"error": payload.decode("utf-8", "replace")}, new_token


class APITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sms import db as db_module

        db_module.DB_PATH = DB_PATH
        connection = db_module.get_conn()
        db_module.init_schema(connection)
        if db_module.is_empty(connection):
            db_module.seed(connection)
        connection.close()

        env = dict(os.environ, SMS_DB=DB_PATH, PYTHONPATH=ROOT)
        cls._log = open(os.path.join(TMP, "server.log"), "w")
        cls._proc = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "run.py"), "--port", str(PORT)],
            cwd=ROOT, env=env, stdout=cls._log, stderr=cls._log,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            probe = http.client.HTTPConnection(BASE, PORT, timeout=2)
            try:
                probe.request("GET", "/api/auth/me")
                if probe.getresponse().status != 503:
                    break
            except OSError:
                pass
            finally:
                probe.close()
            time.sleep(0.2)
        else:
            raise RuntimeError("test server did not start; see " + os.path.join(TMP, "server.log"))

        cls.admin = cls.login("admin", "Admin@123")
        cls.teacher1 = cls.login("teacher1", "Teach@123")
        cls.teacher2 = cls.login("teacher2", "Teach@123")
        cls.student1 = cls.login("student1", "Student@123")

    @classmethod
    def tearDownClass(cls):
        proc = getattr(cls, "_proc", None)
        if proc:
            proc.terminate()
            proc.wait(timeout=10)
        log = getattr(cls, "_log", None)
        if log:
            log.close()
        shutil.rmtree(TMP, ignore_errors=True)

    @staticmethod
    def login(username, password):
        status, body, token = request("POST", "/api/auth/login", {"username": username, "password": password})
        assert status == 200, f"login failed for {username}: {status} {body}"
        return token

    def get(self, path, token=None, **kw):
        return request("GET", path, token=token or self.admin, **kw)

    # ------------------------------------------------------------------ auth
    def test_01_login_rejects_bad_password(self):
        status, body, token = request("POST", "/api/auth/login", {"username": "admin", "password": "nope"})
        self.assertEqual(status, 401)
        self.assertIsNone(token)

    def test_02_protected_route_requires_auth(self):
        status, body, _ = request("GET", "/api/dashboard")
        self.assertEqual(status, 401)

    def test_03_login_is_not_vulnerable_to_sql_injection(self):
        status, _, token = request(
            "POST", "/api/auth/login", {"username": "admin' OR '1'='1' --", "password": "x"}
        )
        self.assertEqual(status, 401)
        self.assertIsNone(token)

    def test_04_logout_invalidates_session(self):
        token = self.login("admin", "Admin@123")
        status, _, _ = request("GET", "/api/dashboard", token=token)
        self.assertEqual(status, 200)
        request("POST", "/api/auth/logout", {}, token=token)
        status, _, _ = request("GET", "/api/dashboard", token=token)
        self.assertEqual(status, 401)

    def test_05_role_scopes_are_distinct(self):
        status, student_view, _ = request("GET", "/api/auth/me", token=self.student1)
        self.assertEqual(status, 200)
        self.assertEqual(student_view["role"], "student")
        self.assertIn("my-results", student_view["links"])
        self.assertNotIn("users", student_view["links"])

    # ------------------------------------------------------------------ rbac
    def test_10_student_cannot_list_all_students(self):
        status, _, _ = request("GET", "/api/students", token=self.student1)
        self.assertEqual(status, 403)

    def test_11_student_cannot_create_students(self):
        status, _, _ = request("POST", "/api/students", {"first_name": "X", "last_name": "Y"}, token=self.student1)
        self.assertEqual(status, 403)

    def test_12_teacher_cannot_delete_a_student(self):
        status, _, _ = request("DELETE", "/api/students/1", token=self.teacher1)
        self.assertEqual(status, 403)

    def test_13_teacher_sees_only_assigned_exams(self):
        _, assignments, _ = request("GET", "/api/assignments", token=self.teacher2)
        own_keys = {(a["class_id"], a["subject_name"]) for a in assignments["rows"]}
        self.assertTrue(own_keys, "teacher2 should have at least one assignment")
        status, body, _ = request("GET", "/api/exams", token=self.teacher2)
        self.assertEqual(status, 200)
        for exam in body["rows"]:
            self.assertIn((exam["class_id"], exam["subject_name"]), own_keys)

    def test_14_student_cannot_read_another_students_record(self):
        own = request("GET", "/api/auth/me", token=self.student1)[1]["record_id"]
        status, _, _ = request("GET", f"/api/students/{own}", token=self.student1)
        self.assertEqual(status, 200)
        status, _, _ = request("GET", f"/api/students/{own + 1}", token=self.student1)
        self.assertEqual(status, 403)

    # -------------------------------------------------------------- students
    def test_20_create_student_generates_login(self):
        status, body, _ = request(
            "POST", "/api/students",
            {"first_name": "Test", "last_name": "Candidate", "gender": "Male", "class_id": 1},
            token=self.admin,
        )
        self.assertEqual(status, 200, body)
        self.assertTrue(body["credentials"]["username"])
        new_token = self.login(body["credentials"]["username"], body["credentials"]["password"])
        me = request("GET", "/api/auth/me", token=new_token)[1]
        self.assertEqual(me["role"], "student")

    def test_21_student_validation_rejects_bad_input(self):
        status, body, _ = request(
            "POST", "/api/students",
            {"first_name": "NoGender", "last_name": "Surname", "class_id": 1}, token=self.admin,
        )
        self.assertEqual(status, 400)
        self.assertIn("gender", body["error"])

        status, body, _ = request(
            "POST", "/api/students",
            {"first_name": "A", "last_name": "B", "gender": "Other", "class_id": 1}, token=self.admin,
        )
        self.assertEqual(status, 400)
        self.assertIn("gender", body["error"])

        status, body, _ = request(
            "POST", "/api/students",
            {"first_name": "A", "last_name": "B", "gender": "Male", "class_id": 9999}, token=self.admin,
        )
        self.assertEqual(status, 404)

    def test_22_duplicate_admission_number_rejected(self):
        status, _, _ = request(
            "POST", "/api/students",
            {"first_name": "Dup", "last_name": "Licate", "gender": "Male", "class_id": 1,
             "admission_no": "SMS/2025/001"}, token=self.admin,
        )
        self.assertEqual(status, 409)

    def test_23_search_and_pagination(self):
        status, body, _ = request("GET", "/api/students?page=1&page_size=5", token=self.admin)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["rows"]), 5)
        self.assertGreaterEqual(body["total"], 18)
        status, body, _ = request("GET", "/api/students?q=Bello", token=self.admin)
        self.assertTrue(all("Bello" in (r["first_name"] + " " + r["last_name"] + r["admission_no"]) for r in body["rows"]))

    # ------------------------------------------------------------------ marks
    def test_30_teacher_saves_and_reads_marks(self):
        status, exams, _ = request("GET", "/api/exams", token=self.teacher1)
        self.assertEqual(status, 200)
        exam = exams["rows"][0]
        status, sheet, _ = request("GET", f"/api/exams/{exam['id']}/marks", token=self.teacher1)
        self.assertEqual(status, 200)
        student_id = sheet["rows"][0]["student_id"]
        scores = {str(student_id): exam["max_marks"] * 0.5}
        status, body, _ = request("PUT", f"/api/exams/{exam['id']}/marks", {"scores": scores}, token=self.teacher1)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["saved"], 1)
        _, sheet2, _ = request("GET", f"/api/exams/{exam['id']}/marks", token=self.teacher1)
        saved = [r for r in sheet2["rows"] if r["student_id"] == student_id][0]
        self.assertAlmostEqual(saved["score"], exam["max_marks"] * 0.5, places=2)

    def test_31_marks_above_max_are_rejected_not_stored(self):
        _, exams, _ = request("GET", "/api/exams", token=self.teacher1)
        exam = exams["rows"][0]
        _, sheet, _ = request("GET", f"/api/exams/{exam['id']}/marks", token=self.teacher1)
        sid = sheet["rows"][0]["student_id"]
        _, body, _ = request("PUT", f"/api/exams/{exam['id']}/marks",
                             {"scores": {str(sid): exam["max_marks"] + 500}}, token=self.teacher1)
        self.assertEqual(body["saved"], 0)
        self.assertEqual(len(body["skipped"]), 1)
        self.assertIn("must be between", body["skipped"][0]["reason"])

    def test_32_teacher_cannot_mark_unassigned_subject(self):
        _, exams, _ = request("GET", "/api/exams", token=self.admin)
        _, mine, _ = request("GET", "/api/exams", token=self.teacher2)
        owned = {e["id"] for e in mine["rows"]}
        target = next(e for e in exams["rows"] if e["id"] not in owned)
        status, _, _ = request("GET", f"/api/exams/{target['id']}/marks", token=self.teacher2)
        self.assertEqual(status, 403)
        status, _, _ = request("PUT", f"/api/exams/{target['id']}/marks", {"scores": {"1": 5}}, token=self.teacher2)
        self.assertEqual(status, 403)

    def test_33_marks_reject_students_outside_the_class(self):
        _, exams, _ = request("GET", "/api/exams", token=self.teacher1)
        exam = exams["rows"][0]
        _, roster, _ = request("GET", f"/api/exams/{exam['id']}/marks", token=self.teacher1)
        inside = {r["student_id"] for r in roster["rows"]}
        _, all_students, _ = request("GET", "/api/students?page_size=200", token=self.admin)
        outsider = next(s["id"] for s in all_students["rows"] if s["id"] not in inside)
        _, body, _ = request("PUT", f"/api/exams/{exam['id']}/marks",
                             {"scores": {str(outsider): 10}}, token=self.teacher1)
        self.assertEqual(body["saved"], 0)
        self.assertEqual(body["skipped"][0]["reason"], "not in this class")

    # --------------------------------------------------------------- grading
    def test_40_report_card_has_grades_and_position(self):
        _, students, _ = request("GET", "/api/students?class_id=3&page_size=50", token=self.admin)
        sid = students["rows"][0]["id"]
        status, report, _ = request("GET", f"/api/reports/students/{sid}", token=self.admin)
        self.assertEqual(status, 200)
        self.assertTrue(report["subjects"], "report card should list assessed subjects")
        for subject in report["subjects"]:
            self.assertIn(subject["grade"], list("ABCDEF"))
            self.assertGreaterEqual(subject["average"], 0)
            self.assertLessEqual(subject["average"], 100)
        self.assertIsNotNone(report["overall_average"])
        self.assertGreaterEqual(report["position"], 1)
        self.assertLessEqual(report["position"], report["class_size"])

    def test_41_class_positions_are_unique_and_complete(self):
        _, body, _ = request("GET", "/api/reports/results?class_id=3", token=self.admin)
        positions = sorted(r["position"] for r in body["results"] if r["position"])
        self.assertEqual(positions[0], 1)
        averages = [r["average"] for r in body["results"] if r["average"] is not None]
        self.assertEqual(averages, sorted(averages, reverse=True), "results must be ordered by average")

    # ------------------------------------------------------------ attendance
    def test_50_attendance_save_and_rate(self):
        _, students, _ = request("GET", "/api/students?class_id=1&page_size=50", token=self.admin)
        records = [{"student_id": s["id"], "status": "present"} for s in students["rows"]]
        records[0]["status"] = "absent"
        status, body, _ = request(
            "POST", "/api/attendance",
            {"class_id": 1, "date": "2025-12-01", "period": "Daily", "records": records}, token=self.admin,
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(body["saved"], len(records))

        # re-posting the same day must update, not duplicate
        status, body, _ = request(
            "POST", "/api/attendance",
            {"class_id": 1, "date": "2025-12-01", "period": "Daily", "records": records}, token=self.admin,
        )
        self.assertEqual(body["saved"], len(records))
        _, day, _ = request("GET", "/api/attendance?class_id=1&date=2025-12-01", token=self.admin)
        self.assertEqual(len(day["rows"]), len(records))

    def test_51_attendance_rejects_foreign_student(self):
        _, all_students, _ = request("GET", "/api/students?class_id=3", token=self.admin)
        status, body, _ = request(
            "POST", "/api/attendance",
            {"class_id": 1, "date": "2025-12-02", "records": [
                {"student_id": all_students["rows"][0]["id"], "status": "present"}]}, token=self.admin,
        )
        self.assertEqual(body["saved"], 0)
        self.assertEqual(body["rejected"][0]["reason"], "not an active student in this class")

    def test_52_attendance_rejects_bad_date(self):
        status, body, _ = request(
            "POST", "/api/attendance",
            {"class_id": 1, "date": "01/12/2025", "records": [{"student_id": 1, "status": "present"}]},
            token=self.admin)
        self.assertEqual(status, 400)

    # ------------------------------------------------------------------ fees
    def test_60_overpayment_is_refused(self):
        _, rows, _ = request("GET", "/api/fees/invoices?term=First%20Term&unpaid_only=1", token=self.admin)
        invoice = next(r for r in rows["rows"] if r["balance"] > 0)
        status, body, _ = request(
            "POST", "/api/fees/payments",
            {"invoice_id": invoice["invoice_id"], "amount": invoice["balance"] + 10000, "method": "cash"},
            token=self.admin)
        self.assertEqual(status, 400)
        self.assertIn("balance", body["error"])

    def test_61_payment_reduces_balance_exactly(self):
        _, rows, _ = request("GET", "/api/fees/invoices?unpaid_only=1", token=self.admin)
        invoice = next(r for r in rows["rows"] if r["balance"] > 5000)
        before = invoice["balance"]
        status, _, _ = request("POST", "/api/fees/payments",
                               {"invoice_id": invoice["invoice_id"], "amount": 5000, "method": "cash"},
                               token=self.admin)
        self.assertEqual(status, 200)
        _, after, _ = request("GET", "/api/fees/invoices?student_id=%d" % invoice["student_id"], token=self.admin)
        total = sum(r["balance"] for r in after["rows"] if r["student_id"] == invoice["student_id"])
        self.assertAlmostEqual(total, before - 5000, places=2)

    def test_62_student_sees_only_own_fees(self):
        _, mine, _ = request("GET", "/api/fees/invoices", token=self.student1)
        sid = request("GET", "/api/auth/me", token=self.student1)[1]["record_id"]
        self.assertTrue(mine["rows"])
        self.assertTrue(all(r["student_id"] == sid for r in mine["rows"]))

    def test_63_no_negative_balances_in_view(self):
        _, rows, _ = request("GET", "/api/fees/invoices", token=self.admin)
        for row in rows["rows"]:
            self.assertGreaterEqual(row["balance"], -0.001, f"negative balance for student {row['student_id']}")

    # --------------------------------------------------------------- reports
    def test_70_csv_export(self):
        status, text, headers, _ = request("GET", "/api/reports/export/fees", token=self.admin, raw=True)
        self.assertEqual(status, 200)
        self.assertEqual(dict(headers).get("Content-Type"), "text/csv; charset=utf-8")
        self.assertIn("amount_due", text.splitlines()[0])

    def test_71_dashboard_summary(self):
        _, body, _ = request("GET", "/api/dashboard", token=self.admin)
        self.assertEqual(body["counts"]["students"], 18 + 1)  # 18 seeded + 1 created in test_20
        self.assertGreater(body["fees"]["due"], 0)
        self.assertAlmostEqual(
            body["fees"]["due"] - body["fees"]["paid"], body["fees"]["outstanding"], places=1)

    def test_72_student_dashboard_is_personal(self):
        _, body, _ = request("GET", "/api/dashboard", token=self.student1)
        self.assertEqual(body["role"], "student")
        self.assertIn("average", body)
        self.assertNotIn("recent_activity", body, "students must not see the audit trail")

    def test_73_unknown_route_is_404_and_bad_method_is_405(self):
        self.assertEqual(request("GET", "/api/does-not-exist", token=self.admin)[0], 404)
        self.assertEqual(request("PATCH", "/api/students", token=self.admin)[0], 405)

    def test_74_malformed_json_body(self):
        conn = http.client.HTTPConnection(BASE, PORT, timeout=10)
        conn.request("POST", "/api/students", body=b"{not json",
                     headers={"Content-Type": "application/json",
                              "Cookie": f"sms_session={self.admin}"})
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()

    def test_75_deactivating_account_kills_its_sessions(self):
        _, created, _ = request("POST", "/api/users",
                                {"full_name": "Temp Admin", "username": "tempadmin",
                                 "password": "Temp@12345", "role": "admin"}, token=self.admin)
        token = self.login("tempadmin", "Temp@12345")
        self.assertEqual(request("GET", "/api/dashboard", token=token)[0], 200)
        request("PUT", f"/api/users/{created['id']}/active", {"is_active": False}, token=self.admin)
        self.assertEqual(request("GET", "/api/dashboard", token=token)[0], 401)

    def test_76_admin_cannot_lock_out_own_account(self):
        me = request("GET", "/api/auth/me", token=self.admin)[1]["id"]
        status, body, _ = request("PUT", f"/api/users/{me}/active", {"is_active": False}, token=self.admin)
        self.assertEqual(status, 400)

    def test_77_change_own_password_flow(self):
        token = self.login("admin", "Admin@123")
        status, _, _ = request("POST", "/api/auth/change-password",
                               {"current_password": "wrong", "new_password": "Brand@New1"}, token=token)
        self.assertEqual(status, 401)
        status, _, _ = request("POST", "/api/auth/change-password",
                               {"current_password": "Admin@123", "new_password": "short"}, token=token)
        self.assertEqual(status, 400)
        status, _, _ = request("POST", "/api/auth/change-password",
                               {"current_password": "Admin@123", "new_password": "Brand@New1"}, token=token)
        self.assertEqual(status, 200)
        self.assertEqual(request("POST", "/api/auth/login",
                                 {"username": "admin", "password": "Brand@New1"})[0], 200)
        request("POST", "/api/auth/change-password",
                {"current_password": "Brand@New1", "new_password": "Admin@123"}, token=token)


if __name__ == "__main__":
    unittest.main(verbosity=2)
