"""Shared test helpers. Every test builds its own temporary database with tools/migrate.py."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from db import create_user, get_connection
from tools.migrate import apply_migrations

PASSWORD = "Long-test-password1!"
PDF = b"%PDF-1.4\nsynthetic test document"


class DatabaseTestCase(unittest.TestCase):
    """A temporary, freshly migrated database. Never touches the real app.db."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db_path = str(Path(temp.name) / "test.db")
        apply_migrations(self.db_path)
        self.conn = get_connection(self.db_path)  # foreign keys ON, like every other connection
        # Resolve self.conn when cleanup runs, not when setUp registers the callback.
        # Tests may close and replace the connection (for example, persistence tests).
        self.addCleanup(self._close_database_connection)

    def _close_database_connection(self):
        connection = getattr(self, "conn", None)
        if connection is not None:
            connection.close()

    # ----- tiny helpers for direct database checks
    def rows(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def add_user(self, role, email, name="Test Person", phone=None, adviser_id=None):
        user_id = create_user(self.conn, name, email, generate_password_hash(PASSWORD), phone, role, adviser_id)
        self.conn.commit()
        return user_id

    def add_application(self, jobseeker_id, company="Acme", title="Analyst", date="2026-11-15", **extra):
        columns = {"jobseeker_id": jobseeker_id, "company_name": company, "job_title": title, "date_applied": date}
        columns.update(extra)
        cursor = self.conn.execute(
            "INSERT INTO job_application (jobseeker_id, company_name, job_title, date_applied, status, advert_url, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (jobseeker_id, company, title, date, "applied", columns.get("advert_url"), columns.get("notes")),
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_cv(self, jobseeker_id, title="My CV", data=PDF):
        cursor = self.conn.execute(
            "INSERT INTO cv (jobseeker_id, title, file_name, file_type, file_data) VALUES (?, ?, 'cv.pdf', 'pdf', ?)",
            (jobseeker_id, title, data),
        )
        self.conn.commit()
        return cursor.lastrowid

    def assertRejected(self, sql, params=()):
        """The database must refuse this and nothing must be saved."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(sql, params)
        self.conn.rollback()


class AppTestCase(DatabaseTestCase):
    """The same, plus a Flask app and test browsers."""

    def setUp(self):
        super().setUp()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-not-for-deployment",
                "DATABASE": self.db_path,
                "SESSION_COOKIE_SECURE": False,
            }
        )

    def csrf(self, client):
        client.get("/login")
        with client.session_transaction() as session:
            return session["csrf_token"]

    def login(self, client, email, password=PASSWORD):
        return client.post("/login", data={"csrf_token": self.csrf(client), "email": email, "password": password})

    def client_for(self, email):
        client = self.app.test_client()
        response = self.login(client, email)
        self.assertEqual(response.status_code, 302, "test setup: sign-in should work")
        return client

    def post(self, client, url, data=None, **kwargs):
        payload = {"csrf_token": self.csrf(client)}
        payload.update(data or {})
        return client.post(url, data=payload, **kwargs)

    def text(self, response):
        return response.get_data(as_text=True)
