"""Integration tests for the Pathway PoC using temporary SQLite files."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from app import create_app
from automation_tasks import process_due_reminders, run_weekly_digest
from db import get_db


class PathwayTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.database_path = root / "test.sqlite"
        self.upload_dir = root / "private" / "cv"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-not-for-deployment",
                "DATABASE": str(self.database_path),
                "UPLOAD_FOLDER": str(self.upload_dir),
                "MAX_CONTENT_LENGTH": 5 * 1024 * 1024,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.client = self.app.test_client()
        self.adviser_id = None
        self.jobseeker_id = None
        self.register_adviser("adviser@example.test", "Avery Adviser")
        self.adviser_id = self.user_id("adviser@example.test")
        self.register_jobseeker("jobseeker@example.test", "Jamie Jobseeker", "07123456789", self.adviser_id)
        self.jobseeker_id = self.user_id("jobseeker@example.test")

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf(self, client=None):
        client = client or self.client
        with client.session_transaction() as session:
            token = session.get("csrf_token")
        if not token:
            client.get("/register")
            with client.session_transaction() as session:
                token = session.get("csrf_token")
        return token

    def register_adviser(self, email, name):
        self.client.get("/register")
        response = self.client.post(
            "/register",
            data={
                "csrf_token": self.csrf(),
                "role": "career_adviser",
                "full_name": name,
                "email": email,
                "password": "a-long-test-password",
            },
        )
        self.assertEqual(response.status_code, 302)

    def register_jobseeker(self, email, name, phone, adviser_id):
        self.client.get("/register")
        response = self.client.post(
            "/register",
            data={
                "csrf_token": self.csrf(),
                "role": "jobseeker",
                "full_name": name,
                "email": email,
                "phone": phone,
                "assigned_adviser_id": str(adviser_id),
                "password": "a-long-test-password",
            },
        )
        self.assertEqual(response.status_code, 302)

    def user_id(self, email):
        with self.app.app_context():
            return get_db().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]

    def login(self, client, email):
        client.get("/login")
        return client.post(
            "/login",
            data={"csrf_token": self.csrf(client), "email": email, "password": "a-long-test-password"},
        )

    def db_rows(self, query, params=()):
        with self.app.app_context():
            return get_db().execute(query, params).fetchall()

    def test_passwords_are_hashed_and_adviser_is_assigned(self):
        rows = self.db_rows("SELECT email, password_hash, role, assigned_adviser_id, account_status FROM users")
        seeker = next(row for row in rows if row["email"] == "jobseeker@example.test")
        self.assertNotEqual(seeker["password_hash"], "a-long-test-password")
        self.assertTrue(seeker["password_hash"].startswith("scrypt:") or seeker["password_hash"].startswith("pbkdf2:"))
        self.assertEqual(seeker["role"], "jobseeker")
        self.assertEqual(seeker["assigned_adviser_id"], self.adviser_id)
        self.assertEqual(seeker["account_status"], "active")

    def test_csrf_is_required_for_state_changes(self):
        response = self.client.post("/login", data={"email": "nobody@example.test", "password": "bad"})
        self.assertEqual(response.status_code, 400)

    def test_application_creation_creates_seven_day_reminder_and_nudge_is_idempotent(self):
        self.login(self.client, "jobseeker@example.test")
        self.client.get("/applications/new")
        response = self.client.post(
            "/applications/new",
            data={
                "csrf_token": self.csrf(),
                "employer_name": "Northstar Studio",
                "job_title": "Junior Designer",
                "date_applied": "2026-11-20",
                "job_url": "https://example.test/jobs/123",
                "status": "Applied",
            },
        )
        self.assertEqual(response.status_code, 302)
        reminder = self.db_rows("SELECT * FROM follow_up_reminders")[0]
        due = datetime.fromisoformat(reminder["due_at"].replace("Z", "+00:00"))
        created = datetime.fromisoformat(reminder["created_at"].replace("Z", "+00:00"))
        self.assertEqual(due - created, timedelta(days=7))

        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE follow_up_reminders SET due_at = ? WHERE id = ?", ("2000-01-01T00:00:00Z", reminder["id"]))
            db.commit()
            first = process_due_reminders(db, datetime.now(timezone.utc))
            second = process_due_reminders(db, datetime.now(timezone.utc))
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(self.db_rows("SELECT status FROM follow_up_reminders")[0]["status"], "sent")
        self.assertEqual(len(self.db_rows("SELECT id FROM notifications WHERE notification_type = 'follow_up'")), 1)

    def test_weekly_digest_is_unique_per_jobseeker_and_iso_week(self):
        with self.app.app_context():
            db = get_db()
            fixed_now = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)
            first = run_weekly_digest(db, fixed_now)
            second = run_weekly_digest(db, fixed_now)
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(len(self.db_rows("SELECT id FROM notifications WHERE notification_type = 'weekly_digest'")), 1)

    def test_adviser_only_sees_assigned_jobseekers_and_jobseeker_cannot_edit_another_application(self):
        second_adviser_client = self.app.test_client()
        second_adviser_client.get("/register")
        second_adviser_client.post(
            "/register",
            data={
                "csrf_token": self.csrf(second_adviser_client),
                "role": "career_adviser",
                "full_name": "Taylor Adviser",
                "email": "taylor@example.test",
                "password": "a-long-test-password",
            },
        )
        second_adviser_client.get("/login")
        second_adviser_client.post(
            "/login",
            data={"csrf_token": self.csrf(second_adviser_client), "email": "taylor@example.test", "password": "a-long-test-password"},
        )
        hidden = second_adviser_client.get(f"/adviser/jobseekers/{self.jobseeker_id}")
        self.assertEqual(hidden.status_code, 404)

        self.login(self.client, "jobseeker@example.test")
        self.client.get("/applications/new")
        self.client.post(
            "/applications/new",
            data={
                "csrf_token": self.csrf(),
                "employer_name": "Example Ltd",
                "job_title": "Analyst",
                "date_applied": "2026-11-20",
                "job_url": "https://example.test/role",
                "status": "Applied",
            },
        )
        application_id = self.db_rows("SELECT id FROM job_applications")[0]["id"]
        other_client = self.app.test_client()
        other_client.get("/register")
        with self.app.app_context():
            other_adviser = get_db().execute("SELECT id FROM users WHERE email = 'adviser@example.test'").fetchone()[0]
        self.register_jobseeker("second@example.test", "Second Jobseeker", "07000000000", other_adviser)
        self.login(other_client, "second@example.test")
        denied = other_client.get(f"/applications/{application_id}/edit")
        self.assertEqual(denied.status_code, 404)

    def test_cv_is_private_and_adviser_review_notifies_owner(self):
        self.login(self.client, "jobseeker@example.test")
        self.client.get("/cv")
        response = self.client.post(
            "/cv",
            data={"csrf_token": self.csrf(), "cv_file": (BytesIO(b"%PDF-1.4\nsynthetic test document"), "sample.pdf", "application/pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        cv = self.db_rows("SELECT * FROM cv_versions")[0]
        self.assertEqual(cv["approval_status"], "pending")
        self.assertTrue((self.upload_dir / cv["stored_filename"]).is_file())
        self.assertNotIn("static", str(self.upload_dir))

        adviser_client = self.app.test_client()
        self.login(adviser_client, "adviser@example.test")
        downloaded = adviser_client.get(f"/cv/{cv['id']}/download")
        self.assertEqual(downloaded.status_code, 200)
        adviser_client.get(f"/adviser/jobseekers/{self.jobseeker_id}")
        reviewed = adviser_client.post(
            f"/adviser/cv/{cv['id']}/review",
            data={"csrf_token": self.csrf(adviser_client), "decision": "approved", "comments": "Clear layout and relevant experience."},
        )
        self.assertEqual(reviewed.status_code, 302)
        updated = self.db_rows("SELECT approval_status, reviewed_by, reviewed_at FROM cv_versions WHERE id = ?", (cv["id"],))[0]
        self.assertEqual(updated["approval_status"], "approved")
        self.assertEqual(updated["reviewed_by"], self.adviser_id)
        self.assertTrue(updated["reviewed_at"])
        self.assertEqual(len(self.db_rows("SELECT id FROM cv_reviews WHERE cv_version_id = ?", (cv["id"],))), 1)
        self.assertEqual(len(self.db_rows("SELECT id FROM notifications WHERE user_id = ? AND notification_type = 'cv_review'", (self.jobseeker_id,))), 1)

    def test_role_and_assignment_are_database_immutable(self):
        with self.app.app_context():
            db = get_db()
            with self.assertRaises(Exception):
                db.execute("UPDATE users SET role = 'career_adviser' WHERE id = ?", (self.jobseeker_id,))
            with self.assertRaises(Exception):
                db.execute("UPDATE users SET assigned_adviser_id = NULL WHERE id = ?", (self.jobseeker_id,))
            db.rollback()


if __name__ == "__main__":
    unittest.main()
