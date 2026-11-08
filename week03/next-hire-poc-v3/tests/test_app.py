import io
import tempfile
import unittest
from datetime import date, datetime, timedelta, time, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from app import create_app
from app.extensions import db
from app.models import Application, Digest, Notification, User
from app.automations import generate_weekly_digests, process_due_nudges, start_scheduler
from app.seed import seed_demo
from app.timeutils import local_midnight_to_utc, local_today


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


    # ---- timezone consistency -------------------------------------------------------
    # 23:30 UTC on Sunday 8 Nov 2026 is already 12:30 on Monday 9 Nov in Auckland (NZDT, UTC+13),
    # so UTC/server-local "today" and APP_TIMEZONE "today" disagree. That is exactly where the
    # old date.today() / naive-midnight code went wrong.
    SUNDAY_NIGHT_UTC = datetime(2026, 11, 8, 23, 30, tzinfo=timezone.utc)

    def clock(self, moment=None):
        return mock.patch("app.timeutils._now_utc", return_value=moment or self.SUNDAY_NIGHT_UTC)

    def test_local_today_follows_app_timezone(self):
        with self.clock():
            self.app.config["APP_TIMEZONE"] = "UTC"
            self.assertEqual(local_today(), date(2026, 11, 8))
            self.app.config["APP_TIMEZONE"] = "Pacific/Auckland"
            self.assertEqual(local_today(), date(2026, 11, 9))
        with self.clock(datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)):
            self.app.config["APP_TIMEZONE"] = "America/Los_Angeles"  # 19:00 on the 8th (PST)
            self.assertEqual(local_today(), date(2026, 11, 8))

    def test_local_midnight_to_utc_handles_offsets_and_dst(self):
        self.app.config["APP_TIMEZONE"] = "UTC"
        self.assertEqual(local_midnight_to_utc(date(2026, 11, 16)), datetime(2026, 11, 16, 0, 0))
        self.app.config["APP_TIMEZONE"] = "Pacific/Auckland"
        self.assertEqual(local_midnight_to_utc(date(2026, 11, 16)), datetime(2026, 11, 15, 11, 0))
        self.app.config["APP_TIMEZONE"] = "Europe/Dublin"
        self.assertEqual(local_midnight_to_utc(date(2026, 7, 1)), datetime(2026, 6, 30, 23, 0))   # IST, UTC+1
        self.assertEqual(local_midnight_to_utc(date(2026, 12, 1)), datetime(2026, 12, 1, 0, 0))   # GMT

    def test_new_applied_application_uses_local_date_and_local_midnight_nudge(self):
        self.app.config["APP_TIMEZONE"] = "Pacific/Auckland"
        self.login("jobseeker2@example.com", "jobseeker123")
        with self.clock():
            response = self.client.post("/applications/new", data={
                "company": "Tz Test Co", "job_title": "Analyst", "stage": "applied"})
        self.assertEqual(response.status_code, 302)
        item = Application.query.filter_by(company="Tz Test Co").one()
        # Defaulted from Auckland's calendar (Mon 9 Nov), not UTC's (Sun 8 Nov).
        self.assertEqual(item.date_applied, date(2026, 11, 9))
        # Due at the START of 16 Nov in Auckland = 11:00 UTC on 15 Nov, stored as UTC.
        self.assertEqual(item.nudge_due_at, datetime(2026, 11, 15, 11, 0))

    def test_nudge_fires_at_local_midnight_not_utc_midnight(self):
        self.app.config["APP_TIMEZONE"] = "Pacific/Auckland"
        self.login("jobseeker2@example.com", "jobseeker123")
        with self.clock():
            self.client.post("/applications/new", data={
                "company": "Tz Test Co", "job_title": "Analyst", "stage": "applied"})
        application_id = Application.query.filter_by(company="Tz Test Co").one().id

        def nudges():
            return Notification.query.filter_by(application_id=application_id, type="follow_up_nudge").count()

        process_due_nudges(self.app, now=datetime(2026, 11, 15, 10, 59))   # 23:59 on the 15th in Auckland
        self.assertEqual(nudges(), 0)
        process_due_nudges(self.app, now=datetime(2026, 11, 15, 11, 0))    # 00:00 on the 16th in Auckland
        self.assertEqual(nudges(), 1)

    def test_dashboard_deadlines_use_local_today(self):
        self.app.config["APP_TIMEZONE"] = "Pacific/Auckland"
        owner = User.query.filter_by(email="jobseeker2@example.com").one()
        db.session.add_all([
            Application(jobseeker_id=owner.id, company="Yesterday Ltd", job_title="X", stage="saved", deadline=date(2026, 11, 8)),
            Application(jobseeker_id=owner.id, company="Today Ltd", job_title="X", stage="saved", deadline=date(2026, 11, 9)),
        ])
        db.session.commit()
        self.login("jobseeker2@example.com", "jobseeker123")
        with self.clock():
            body = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("Today Ltd", body)          # 9 Nov is today in Auckland
        self.assertNotIn("Yesterday Ltd", body)   # 8 Nov has already passed there

    def test_weekly_digest_week_follows_app_timezone(self):
        self.app.config["APP_TIMEZONE"] = "Pacific/Auckland"
        with self.clock():
            generate_weekly_digests(self.app)
        # Monday 9 Nov in Auckland starts the week; UTC would still be in the week of 2 Nov.
        self.assertEqual(Digest.query.filter_by(week_start=date(2026, 11, 9)).count(), 2)

    def test_seeded_nudges_are_due_at_local_midnight(self):
        db.drop_all()
        db.create_all()
        self.app.config["APP_TIMEZONE"] = "Pacific/Auckland"
        seed_demo(self.app)
        row = Application.query.filter_by(company="Brightside Studio").one()
        naive_midnight = datetime.combine(row.date_applied + timedelta(days=7), time.min)
        expected = (naive_midnight.replace(tzinfo=ZoneInfo("Pacific/Auckland"))
                    .astimezone(timezone.utc).replace(tzinfo=None))
        self.assertEqual(row.nudge_due_at, expected)
        self.assertNotEqual(row.nudge_due_at, naive_midnight)

    def test_invalid_app_timezone_fails_at_startup_with_a_clear_message(self):
        for bad in ("Mars/Olympus", ""):
            with self.subTest(timezone=bad):
                with self.assertRaisesRegex(RuntimeError, "APP_TIMEZONE"):
                    create_app({
                        "TESTING": True, "WTF_CSRF_ENABLED": False,
                        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "UPLOAD_DIR": self.upload_dir,
                        "AUTO_INIT_DB": False, "START_SCHEDULER": False,
                        "SECRET_KEY": "test-secret", "APP_TIMEZONE": bad,
                    })


if __name__ == "__main__":
    unittest.main()
