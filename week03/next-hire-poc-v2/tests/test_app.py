import io
import tempfile
import unittest
from datetime import date, datetime, timedelta, time
from pathlib import Path
from unittest import mock

from app import create_app
from app.extensions import db
from app.models import Application, Digest, Notification, User
from app.automations import generate_weekly_digests, process_due_nudges, start_scheduler
from app.seed import seed_demo


class JobTrackerSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.upload_dir = str(Path(self.tmp.name) / "uploads")
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_DIR": self.upload_dir,
            "AUTO_INIT_DB": False,
            "START_SCHEDULER": False,
            "SECRET_KEY": "test-secret",
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        seed_demo(self.app)
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.tmp.cleanup()

    def login(self, email, password):
        return self.client.post("/login", data={"email": email, "password": password}, follow_redirects=True)

    def test_jobseeker_can_see_dashboard_and_applications(self):
        response = self.login("jobseeker1@example.com", "jobseeker123")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Upcoming deadlines", response.data)
        apps = self.client.get("/applications")
        self.assertEqual(apps.status_code, 200)
        self.assertIn(b"Northstar Analytics", apps.data)

    def test_pending_adviser_login_is_blocked_and_admin_can_approve(self):
        response = self.login("adviser2@example.com", "adviser123")
        self.assertIn(b"awaiting admin approval", response.data)
        self.login("admin@example.com", "admin123")
        admin_response = self.client.post("/admin/advisers/3/approve", follow_redirects=True)
        self.assertEqual(admin_response.status_code, 200)
        self.client.post("/logout")
        response = self.login("adviser2@example.com", "adviser123")
        self.assertIn(b"Review queue", response.data)

    def test_jobseeker_cannot_access_another_users_application(self):
        other = User.query.filter_by(email="jobseeker2@example.com").first()
        foreign_app = Application.query.filter_by(jobseeker_id=other.id).first()
        self.login("jobseeker1@example.com", "jobseeker123")
        response = self.client.get(f"/applications/{foreign_app.id}")
        self.assertEqual(response.status_code, 404)

    def test_seeded_nudge_is_created_once(self):
        old_count = Notification.query.count()
        created = process_due_nudges(self.app)
        self.assertEqual(created, 1)
        self.assertEqual(Notification.query.count(), old_count + 1)
        self.assertEqual(process_due_nudges(self.app), 0)

    def test_nudge_is_not_duplicated_when_a_second_worker_saw_it_as_due(self):
        # Two scheduler instances both listed the application as due (stale candidate
        # list). Only the first atomic claim may create a notification.
        brightside = Application.query.filter_by(company="Brightside Studio").one()
        application_id = brightside.id
        old_count = Notification.query.count()
        with mock.patch("app.automations._due_application_ids", return_value=[application_id]):
            first_worker = process_due_nudges(self.app)
            second_worker = process_due_nudges(self.app)
        self.assertEqual((first_worker, second_worker), (1, 0))
        self.assertEqual(Notification.query.count(), old_count + 1)
        self.assertEqual(Notification.query.filter_by(application_id=application_id, type="follow_up_nudge").count(), 1)

    def test_nudge_is_skipped_if_application_stopped_qualifying_after_listing(self):
        # The jobseeker closed the application between the candidate query and the claim.
        brightside = Application.query.filter_by(company="Brightside Studio").one()
        application_id = brightside.id
        brightside.outcome = "rejected"
        db.session.commit()
        with mock.patch("app.automations._due_application_ids", return_value=[application_id]):
            self.assertEqual(process_due_nudges(self.app), 0)
        self.assertEqual(Notification.query.filter_by(application_id=application_id).count(), 0)
        db.session.refresh(brightside)
        self.assertIsNone(brightside.nudge_sent_at)

    def test_create_app_does_not_start_the_scheduler(self):
        app = create_app({
            "TESTING": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_DIR": self.upload_dir,
            "AUTO_INIT_DB": False,
            "START_SCHEDULER": True,
            "SECRET_KEY": "test-secret",
        })
        self.assertTrue(app.config["START_SCHEDULER"])
        self.assertNotIn("job_tracker_scheduler", app.extensions)

    def test_start_scheduler_registers_both_jobs_once(self):
        scheduler = start_scheduler(self.app)
        try:
            self.assertTrue(scheduler.running)
            self.assertEqual({job.id for job in scheduler.get_jobs()},
                             {"weekly_pipeline_digest", "hourly_follow_up_nudges"})
            self.assertIs(start_scheduler(self.app), scheduler)
        finally:
            scheduler.shutdown(wait=False)

    def test_digest_generation_is_idempotent(self):
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        first = generate_weekly_digests(self.app, week_start=monday)
        second = generate_weekly_digests(self.app, week_start=monday)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(Digest.query.filter_by(week_start=monday).count(), 2)

    def test_adviser_can_review_submitted_cv(self):
        self.login("adviser1@example.com", "adviser123")
        from app.models import CV
        cv = CV.query.filter_by(status="submitted").first()
        response = self.client.post(f"/adviser/cvs/{cv.id}", data={"action": "request_changes", "comment": "Please add measurable results."}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        db.session.refresh(cv)
        self.assertEqual(cv.status, "changes_requested")
        self.assertTrue(cv.reviewed_at)

    def test_pdf_upload_adds_submitted_version(self):
        self.login("jobseeker2@example.com", "jobseeker123")
        pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
        response = self.client.post("/cvs", data={
            "title": "Test CV", "version_label": "v1",
            "file": (io.BytesIO(pdf), "test-cv.pdf", "application/pdf"),
        }, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        from app.models import CV
        self.assertTrue(CV.query.filter_by(title="Test CV", status="submitted").first())


if __name__ == "__main__":
    unittest.main()
