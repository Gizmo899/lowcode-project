"""Prove-it tests: the database must REJECT bad data, and keep good data.

Run from the example folder (the one containing db.py):
    Mac:      python3 -m unittest -v
    Windows:  python -m unittest -v
(pytest works too, if you have it: python3 -m pytest -v)

Each test builds a brand-new database in a temporary folder from the files
in schema/, so the tests never touch your real app.db.
"""
import glob
import os
import re
import sqlite3
import tempfile
import unittest

import db

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(HERE, "..", "schema")


def schema_files(up_to=None):
    files = sorted(glob.glob(os.path.join(SCHEMA_DIR, "*.sql")),
                   key=lambda p: int(re.match(r"(\d+)", os.path.basename(p)).group(1)))
    if up_to is not None:
        files = [f for f in files if int(re.match(r"(\d+)", os.path.basename(f)).group(1)) <= up_to]
    return files


def apply_schema(db_path, files):
    conn = sqlite3.connect(db_path)
    for path in files:
        with open(path, encoding="utf-8") as handle:
            conn.executescript(handle.read())
    conn.close()


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test.db")
        apply_schema(self.db_path, schema_files())
        self.member = db.add_member("Aoife Byrne", "aoife@example.com", db_path=self.db_path)
        self.tent = db.add_equipment("TENT-01", "4-person tent", db_path=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()


class TestConstraintsRejectBadData(DatabaseTestCase):
    def test_unique_rejects_duplicate_tag(self):
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            db.add_equipment("TENT-01", "Another tent", db_path=self.db_path)
        self.assertIn("UNIQUE", str(caught.exception))

    def test_unique_rejects_duplicate_email(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.add_member("Someone Else", "aoife@example.com", db_path=self.db_path)

    def test_check_rejects_unknown_condition(self):
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            db.add_equipment("KAYAK-01", "Kayak", condition="lost", db_path=self.db_path)
        self.assertIn("CHECK", str(caught.exception))

    def test_check_rejects_return_before_borrow(self):
        loan = db.create_loan(self.member, self.tent, borrowed_on="2026-11-11", db_path=self.db_path)
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            db.return_loan(loan, returned_on="2026-11-01", db_path=self.db_path)
        self.assertIn("CHECK", str(caught.exception))

    def test_not_null_rejects_missing_name(self):
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            db.add_member(None, "noname@example.com", db_path=self.db_path)
        self.assertIn("NOT NULL", str(caught.exception))

    def test_foreign_key_rejects_orphan_loan(self):
        # Member 999 does not exist. db.get_connection() switches foreign keys on.
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            db.create_loan(999, self.tent, db_path=self.db_path)
        self.assertIn("FOREIGN KEY", str(caught.exception))

    def test_same_item_cannot_be_out_twice(self):
        db.create_loan(self.member, self.tent, db_path=self.db_path)
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_loan(self.member, self.tent, db_path=self.db_path)


class TestTheTrap(DatabaseTestCase):
    def test_orphan_gets_in_when_pragma_is_missing(self):
        """Documents the trap: a plain connection does NOT enforce foreign keys."""
        conn = sqlite3.connect(self.db_path)  # no PRAGMA foreign_keys = ON
        conn.execute("INSERT INTO loan (member_id, equipment_id, borrowed_on) VALUES (999, ?, '2026-11-11')",
                     (self.tent,))
        conn.commit()
        orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()
        self.assertEqual(len(orphans), 1, "the orphan row got in, exactly as SQLite does by default")


class TestDeleteRule(DatabaseTestCase):
    def test_restrict_blocks_deleting_member_with_loans(self):
        db.create_loan(self.member, self.tent, db_path=self.db_path)
        with self.assertRaises(db.InUseError):
            db.delete_member(self.member, db_path=self.db_path)
        self.assertIsNotNone(db.get_member(self.member, db_path=self.db_path), "member must still exist")
        self.assertEqual(len(db.list_loans(db_path=self.db_path)), 1, "their loan history must still exist")

    def test_member_without_loans_can_be_deleted(self):
        other = db.add_member("Ciarán Ó Súilleabháin", "ciaran@example.com", db_path=self.db_path)
        self.assertTrue(db.delete_member(other, db_path=self.db_path))


class TestNotFound(DatabaseTestCase):
    def test_missing_loan_returns_none(self):
        self.assertIsNone(db.get_loan(12345, db_path=self.db_path))

    def test_returning_missing_loan_reports_false(self):
        self.assertFalse(db.return_loan(12345, db_path=self.db_path))


class TestPersistence(DatabaseTestCase):
    def test_data_survives_reopening_the_file(self):
        loan = db.create_loan(self.member, self.tent, borrowed_on="2026-11-11", db_path=self.db_path)
        # Every db function opens and closes its own connection, so this read
        # comes from the file on disk, exactly like after an app restart.
        fresh = sqlite3.connect(self.db_path)
        row = fresh.execute("SELECT member_id, borrowed_on FROM loan WHERE id = ?", (loan,)).fetchone()
        fresh.close()
        self.assertEqual(row, (self.member, "2026-11-11"))


class TestMigration002(unittest.TestCase):
    def test_due_date_added_to_database_that_already_has_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.db")
            apply_schema(path, schema_files(up_to=1))
            conn = sqlite3.connect(path)
            conn.execute("INSERT INTO member (full_name, email) VALUES ('Old Member', 'old@example.com')")
            conn.execute("INSERT INTO equipment (tag, name) VALUES ('STOVE-01', 'Camping stove')")
            conn.execute("INSERT INTO loan (member_id, equipment_id, borrowed_on) VALUES (1, 1, '2026-10-01')")
            conn.commit()
            conn.close()
            apply_schema(path, [f for f in schema_files() if f not in schema_files(up_to=1)])
            conn = sqlite3.connect(path)
            rows = conn.execute("SELECT borrowed_on, due_on FROM loan").fetchall()
            conn.close()
        self.assertEqual(rows, [("2026-10-01", "2026-10-15")], "old row kept and given a due date")


try:
    import flask  # noqa: F401
    HAVE_FLASK = True
except ImportError:
    HAVE_FLASK = False


@unittest.skipUnless(HAVE_FLASK, "Flask is not installed, so the web tests are skipped")
class TestWebApp(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.old_path = db.DB_PATH
        db.DB_PATH = self.db_path
        import app as web
        self.client = web.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_path
        super().tearDown()

    def test_missing_loan_is_404_not_500(self):
        self.assertEqual(self.client.get("/loans/12345").status_code, 404)

    def test_create_loan_through_the_web_form(self):
        response = self.client.post("/loans", data={"member_id": self.member, "equipment_id": self.tent})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(db.list_loans()), 1)


if __name__ == "__main__":
    unittest.main()
