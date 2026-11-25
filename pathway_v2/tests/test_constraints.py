"""Constraint tests: each test tries to put BAD data into a fresh database and checks it is REJECTED.

Every test builds its own temporary database by running the files in schema/ in number order.
The real app.db is never touched: every connection below is opened with an explicit temporary path.

Run from the top folder of the project (the one that contains AGENTS.md):

    Windows:  python -m unittest tests.test_constraints -v
    Mac:      python3 -m unittest tests.test_constraints -v

They also run under pytest:  python -m pytest tests/test_constraints.py -v
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # so "import db" works however the tests are started
    sys.path.insert(0, str(ROOT))

import db  # noqa: E402
from db import get_connection  # noqa: E402

SCHEMA_DIR = ROOT / "schema"
PDF = b"%PDF-1.4\nsynthetic test document"

INSERT_USER = "INSERT INTO user (full_name, email, password_hash, phone, role, assigned_adviser_id) VALUES (?, ?, ?, ?, ?, ?)"
INSERT_CV = "INSERT INTO cv (jobseeker_id, title, file_name, file_type, file_data) VALUES (?, ?, ?, ?, ?)"
INSERT_APPLICATION = "INSERT INTO job_application (jobseeker_id, company_name, job_title, date_applied) VALUES (?, ?, ?, ?)"
INSERT_REMINDER = "INSERT INTO follow_up_reminder (application_id, due_on) VALUES (?, ?)"
INSERT_NOTIFICATION = "INSERT INTO notification (user_id, kind, message, created_at, is_read) VALUES (?, ?, ?, ?, ?)"

COUNT = {  # fixed queries, so no SQL is ever built from strings
    "user": "SELECT COUNT(*) FROM user",
    "cv": "SELECT COUNT(*) FROM cv",
    "job_application": "SELECT COUNT(*) FROM job_application",
    "follow_up_reminder": "SELECT COUNT(*) FROM follow_up_reminder",
    "notification": "SELECT COUNT(*) FROM notification",
}


def build_database(path):
    """Run every file in schema/ in number order (001, 002, ...) against a new database file."""
    files = sorted(SCHEMA_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise AssertionError("No numbered .sql files found in schema/")
    conn = get_connection(path)
    try:
        for sql_file in files:
            conn.executescript(sql_file.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


class ConstraintTestCase(unittest.TestCase):
    """A fresh temporary database for every single test."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db_path = str(Path(temp.name) / "test_constraints.db")
        self.assertNotEqual(Path(self.db_path).resolve(), (ROOT / "app.db").resolve())  # never the real database
        build_database(self.db_path)
        self.conn = get_connection(self.db_path)  # foreign keys are switched on here, as in the app
        self.addCleanup(self.conn.close)

    # ----- helpers that put GOOD data in
    def make_user(self, role, email, name="Test Person", phone=None, adviser_id=None):
        cursor = self.conn.execute(INSERT_USER, (name, email, "not-a-real-hash", phone, role, adviser_id))
        self.conn.commit()
        return cursor.lastrowid

    def make_cv(self, jobseeker_id, title="My CV"):
        cursor = self.conn.execute(INSERT_CV, (jobseeker_id, title, "cv.pdf", "pdf", PDF))
        self.conn.commit()
        return cursor.lastrowid

    def make_application(self, jobseeker_id, company="Acme Ltd"):
        cursor = self.conn.execute(INSERT_APPLICATION, (jobseeker_id, company, "Analyst", "2026-11-15"))
        self.conn.commit()
        return cursor.lastrowid

    def count(self, table):
        return self.conn.execute(COUNT[table]).fetchone()[0]

    # ----- the check every bad-data test uses
    def assert_rejected(self, expected_text, sql, params=()):
        """The database must refuse this with an IntegrityError that names the rule that was broken."""
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            self.conn.execute(sql, params)
        self.conn.rollback()
        self.assertIn(expected_text, str(caught.exception))


class BadDataIsRejectedTests(ConstraintTestCase):
    def test_a_duplicate_in_a_unique_field_is_rejected(self):
        self.make_user("jobseeker", "anna@example.test", phone="0851111111")
        bad_rows = {
            "the same email again": (INSERT_USER, ("Copy", "anna@example.test", "h", None, "jobseeker", None), "UNIQUE constraint failed: user.email"),
            "the same email with different capitals": (INSERT_USER, ("Copy", "ANNA@Example.TEST", "h", None, "jobseeker", None), "UNIQUE constraint failed: user.email"),
            "the same phone number": (INSERT_USER, ("Copy", "other@example.test", "h", "0851111111", "adviser", None), "UNIQUE constraint failed: user.phone"),
        }
        for label, (sql, params, expected) in bad_rows.items():
            with self.subTest(label):
                self.assert_rejected(expected, sql, params)
        self.assertEqual(self.count("user"), 1)  # none of the bad rows was saved

    def test_a_value_that_breaks_a_check_rule_is_rejected(self):
        seeker = self.make_user("jobseeker", "seeker@example.test")
        application = self.make_application(seeker)
        bad_rows = {
            "a role that does not exist": (INSERT_USER, ("X", "x@example.test", "h", None, "admin", None)),
            "a CV file type that is not allowed": (INSERT_CV, (seeker, "T", "notes.txt", "txt", PDF)),
            "a CV file over 1 MB": (INSERT_CV, (seeker, "T", "big.pdf", "pdf", b"a" * 1_048_577)),
            "an impossible application date": (INSERT_APPLICATION, (seeker, "Acme", "Dev", "2026-02-30")),
            "a notification read flag of 2": (INSERT_NOTIFICATION, (seeker, "nudge", "hello", "2026-11-22", 2)),
            "a reminder with an impossible due date": (INSERT_REMINDER, (application, "2026-13-45")),
        }
        for label, (sql, params) in bad_rows.items():
            with self.subTest(label):
                self.assert_rejected("CHECK constraint failed", sql, params)
        self.assertEqual(
            (self.count("user"), self.count("cv"), self.count("job_application"), self.count("follow_up_reminder"), self.count("notification")),
            (1, 0, 1, 0, 0),
        )

    def test_a_missing_value_in_a_required_field_is_rejected(self):
        seeker = self.make_user("jobseeker", "seeker@example.test")
        bad_rows = {
            "a user with no name": (INSERT_USER, (None, "x@example.test", "h", None, "jobseeker", None), "NOT NULL constraint failed: user.full_name"),
            "a user with no email": (INSERT_USER, ("X", None, "h", None, "jobseeker", None), "NOT NULL constraint failed: user.email"),
            "a user with no password hash": (INSERT_USER, ("X", "x@example.test", None, None, "jobseeker", None), "NOT NULL constraint failed: user.password_hash"),
            "a user with no role": (INSERT_USER, ("X", "x@example.test", "h", None, None, None), "NOT NULL constraint failed: user.role"),
            "a CV with no title": (INSERT_CV, (seeker, None, "a.pdf", "pdf", PDF), "NOT NULL constraint failed: cv.title"),
            "a CV with no file": (INSERT_CV, (seeker, "T", "a.pdf", "pdf", None), "NOT NULL constraint failed: cv.file_data"),
            "an application with no company": (INSERT_APPLICATION, (seeker, None, "Dev", "2026-11-15"), "NOT NULL constraint failed: job_application.company_name"),
            "an application with no date": (INSERT_APPLICATION, (seeker, "Acme", "Dev", None), "NOT NULL constraint failed: job_application.date_applied"),
        }
        for label, (sql, params, expected) in bad_rows.items():
            with self.subTest(label):
                self.assert_rejected(expected, sql, params)
        self.assertEqual((self.count("user"), self.count("cv"), self.count("job_application")), (1, 0, 0))

    def test_a_row_pointing_at_a_parent_that_does_not_exist_is_rejected(self):
        # get_connection() must have switched foreign keys on, otherwise SQLite would accept this row.
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        # A reminder points at a job application. No application with this id exists.
        self.assert_rejected("FOREIGN KEY constraint failed", INSERT_REMINDER, (999999, "2026-11-22"))
        self.assertEqual(self.count("follow_up_reminder"), 0)

    def test_without_the_foreign_key_pragma_the_same_bad_row_would_get_in(self):
        """Shows why every connection must come from get_connection(): a plain connection lets the orphan in."""
        plain = sqlite3.connect(self.db_path)  # deliberately NOT get_connection(), only to prove the point
        try:
            plain.execute(INSERT_REMINDER, (999999, "2026-11-22"))  # accepted: nobody is checking
            self.assertEqual(plain.execute(COUNT["follow_up_reminder"]).fetchone()[0], 1)
            plain.rollback()  # leave nothing behind
        finally:
            plain.close()


class DeleteRuleTests(ConstraintTestCase):
    def family(self):
        """An adviser, their jobseeker, and rows that belong to the jobseeker."""
        adviser = self.make_user("adviser", "adviser@example.test", "Avery Adviser")
        seeker = self.make_user("jobseeker", "seeker@example.test", "Jamie Jobseeker", adviser_id=adviser)
        cv = self.make_cv(seeker, "Marketing CV")
        application = self.make_application(seeker)
        self.conn.execute(INSERT_REMINDER, (application, "2026-11-22"))
        self.conn.execute(INSERT_NOTIFICATION, (seeker, "digest", "Your weekly digest is ready.", "2026-11-23", 0))
        self.conn.commit()
        return adviser, seeker, cv

    def test_delete_rule_1_cascade_deleting_a_jobseeker_deletes_their_cvs_applications_reminders_and_notifications(self):
        _, seeker, _ = self.family()
        bystander = self.make_user("jobseeker", "bystander@example.test", "Someone Else")
        self.make_cv(bystander)  # a control: this CV must NOT be deleted
        self.conn.execute("DELETE FROM user WHERE id = ?", (seeker,))
        self.conn.commit()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM cv WHERE jobseeker_id = ?", (seeker,)).fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM job_application WHERE jobseeker_id = ?", (seeker,)).fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notification WHERE user_id = ?", (seeker,)).fetchone()[0], 0)
        self.assertEqual(self.count("follow_up_reminder"), 0)  # reminders go with their application
        self.assertEqual(self.count("cv"), 1)                  # the bystander's CV is still there

    def test_delete_rule_2_set_null_deleting_an_adviser_keeps_their_jobseekers_and_empties_the_link(self):
        adviser, seeker, _ = self.family()
        self.conn.execute("DELETE FROM user WHERE id = ?", (adviser,))
        self.conn.commit()
        row = self.conn.execute("SELECT full_name, assigned_adviser_id FROM user WHERE id = ?", (seeker,)).fetchone()
        self.assertIsNotNone(row, "the jobseeker must still exist")
        self.assertIsNone(row["assigned_adviser_id"], "the link to the adviser must be emptied")
        self.assertEqual((self.count("cv"), self.count("job_application"), self.count("notification")), (1, 1, 1))

    def test_delete_rule_3_set_null_deleting_an_adviser_keeps_the_cvs_they_decided(self):
        adviser, seeker, cv = self.family()
        self.conn.execute(
            "UPDATE cv SET status = 'rejected', decided_by = ?, decided_at = '2026-11-23', comment = 'Add your last job' WHERE id = ?",
            (adviser, cv),
        )
        self.conn.commit()
        self.conn.execute("DELETE FROM user WHERE id = ?", (adviser,))
        self.conn.commit()
        row = self.conn.execute("SELECT status, decided_by, decided_at, comment FROM cv WHERE id = ?", (cv,)).fetchone()
        self.assertIsNotNone(row, "the CV must still exist")
        self.assertEqual(tuple(row), ("rejected", None, "2026-11-23", "Add your last job"))


class SavingAndFindingTests(ConstraintTestCase):
    def test_a_saved_record_is_still_there_after_closing_and_reopening_the_database_file(self):
        seeker = self.make_user("jobseeker", "keeper@example.test", "Kept Person")
        self.make_application(seeker, company="Kept Ltd")
        self.conn.close()  # close the connection completely

        reopened = get_connection(self.db_path)  # open the same file again
        try:
            user = reopened.execute("SELECT full_name FROM user WHERE email = ?", ("keeper@example.test",)).fetchone()
            application = reopened.execute("SELECT company_name FROM job_application WHERE jobseeker_id = ?", (seeker,)).fetchone()
        finally:
            reopened.close()
        self.assertEqual(user["full_name"], "Kept Person")
        self.assertEqual(application["company_name"], "Kept Ltd")

    def test_asking_for_an_id_that_does_not_exist_returns_none_and_not_an_error(self):
        missing = 999999
        lookups = {
            "get_user": lambda: db.get_user(self.conn, missing),
            "get_user_by_email": lambda: db.get_user_by_email(self.conn, "nobody@example.test"),
            "get_jobseeker_with_adviser": lambda: db.get_jobseeker_with_adviser(self.conn, missing),
            "get_jobseeker_of_adviser": lambda: db.get_jobseeker_of_adviser(self.conn, missing, 1),
            "get_job_application": lambda: db.get_job_application(self.conn, missing, 1),
            "get_cv_for_jobseeker": lambda: db.get_cv_for_jobseeker(self.conn, missing, 1),
            "get_cv_for_adviser": lambda: db.get_cv_for_adviser(self.conn, missing, 1),
            "get_follow_up_reminder": lambda: db.get_follow_up_reminder(self.conn, missing),
            "get_notification": lambda: db.get_notification(self.conn, missing, 1),
        }
        for name, lookup in lookups.items():
            with self.subTest(name):
                self.assertIsNone(lookup())


if __name__ == "__main__":
    unittest.main()
