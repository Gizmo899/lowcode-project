"""Tests for the hourly automations: nudges (events plus processing), the Monday digest and the tidy-up."""

from datetime import datetime

from automation_tasks import process_due_reminders, run_all, run_tidy_up, run_weekly_digest
from events import application_saved, application_stage_changed
from tests.helpers import DatabaseTestCase
from utils import IRISH_TIME


class AutomationBase(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.adviser = self.add_user("adviser", "a@x.test")
        self.seeker = self.add_user("jobseeker", "j@x.test", "Jamie", None, self.adviser)

    def new_application(self, date_applied="2026-11-10", **extra):
        application_id = self.add_application(self.seeker, date=date_applied, **extra)
        application_saved(self.conn, application_id, date_applied, "2026-11-10")
        self.conn.commit()
        return application_id

    def notifications(self, kind=None):
        if kind:
            return self.rows("SELECT * FROM notification WHERE kind = ?", (kind,))
        return self.rows("SELECT * FROM notification")


class NudgeTests(AutomationBase):
    def test_saving_an_application_plans_exactly_one_reminder_seven_days_later(self):
        application_id = self.new_application("2026-11-10")
        reminders = self.rows("SELECT due_on, status FROM follow_up_reminder WHERE application_id = ?", (application_id,))
        self.assertEqual([tuple(r) for r in reminders], [("2026-11-17", "pending")])

    def test_nothing_happens_before_the_due_date(self):
        self.new_application("2026-11-10")
        self.assertEqual(process_due_reminders(self.conn, "2026-11-16")["sent"], 0)
        self.assertEqual(len(self.notifications()), 0)

    def test_a_due_reminder_sends_one_nudge_and_running_twice_is_harmless(self):
        self.new_application("2026-11-10", )
        first = process_due_reminders(self.conn, "2026-11-17")
        second = process_due_reminders(self.conn, "2026-11-17")
        self.assertEqual((first["sent"], second["sent"]), (1, 0))
        self.assertEqual(len(self.notifications("nudge")), 1)
        self.assertIn("No reply yet from Acme (Analyst)", self.notifications("nudge")[0]["message"])

    def test_the_nudge_repeats_every_seven_days_until_the_stage_changes(self):
        application_id = self.new_application("2026-11-10")
        process_due_reminders(self.conn, "2026-11-17")
        statuses = [tuple(r) for r in self.rows("SELECT status, due_on FROM follow_up_reminder ORDER BY id")]
        self.assertEqual(statuses, [("sent", "2026-11-17"), ("pending", "2026-11-24")])
        process_due_reminders(self.conn, "2026-11-24")
        self.assertEqual(len(self.notifications("nudge")), 2)
        # the stage changes: the waiting reminder is cancelled and nothing more is sent
        self.conn.execute("UPDATE job_application SET status = 'interview' WHERE id = ?", (application_id,))
        application_stage_changed(self.conn, application_id, "applied", "interview", "2026-11-25")
        self.conn.commit()
        process_due_reminders(self.conn, "2026-12-30")
        self.assertEqual(len(self.notifications("nudge")), 2)
        self.assertEqual(self.one("SELECT COUNT(*) FROM follow_up_reminder WHERE status = 'pending'")[0], 0)

    def test_a_missed_run_catches_up_without_piling_up(self):
        self.new_application("2026-11-10")
        result = process_due_reminders(self.conn, "2026-12-20")   # the computer was off for weeks
        self.assertEqual(result["sent"], 1)
        self.assertEqual(self.one("SELECT due_on FROM follow_up_reminder WHERE status = 'pending'")["due_on"], "2026-12-27")

    def test_a_due_reminder_for_an_application_that_moved_on_is_skipped_not_sent(self):
        application_id = self.new_application("2026-11-10")
        self.conn.execute("UPDATE job_application SET status = 'withdrawn' WHERE id = ?", (application_id,))
        self.conn.commit()   # the event did not run (for example an edit made directly in the database)
        result = process_due_reminders(self.conn, "2026-11-17")
        self.assertEqual((result["sent"], result["skipped"]), (0, 1))
        self.assertEqual(len(self.notifications()), 0)


class DigestTests(AutomationBase):
    MONDAY_8AM = datetime(2026, 11, 23, 8, 0, tzinfo=IRISH_TIME)

    def test_the_digest_is_only_made_on_mondays_from_eight_irish_time(self):
        self.new_application()
        for label, when in (("Monday 7:59", datetime(2026, 11, 23, 7, 59, tzinfo=IRISH_TIME)),
                            ("Tuesday 9:00", datetime(2026, 11, 24, 9, 0, tzinfo=IRISH_TIME)),
                            ("Sunday 8:00", datetime(2026, 11, 22, 8, 0, tzinfo=IRISH_TIME))):
            with self.subTest(label):
                self.assertEqual(run_weekly_digest(self.conn, when)["created"], 0)
        self.assertEqual(len(self.notifications("digest")), 0)
        self.assertEqual(run_weekly_digest(self.conn, self.MONDAY_8AM)["created"], 1)

    def test_running_the_digest_twice_on_the_same_monday_creates_it_once(self):
        self.new_application()
        run_weekly_digest(self.conn, self.MONDAY_8AM)
        run_weekly_digest(self.conn, datetime(2026, 11, 23, 15, 0, tzinfo=IRISH_TIME))
        self.assertEqual(len(self.notifications("digest")), 1)
        run_weekly_digest(self.conn, datetime(2026, 11, 30, 8, 0, tzinfo=IRISH_TIME))   # the next Monday
        self.assertEqual(len(self.notifications("digest")), 2)

    def test_a_jobseeker_with_no_applications_gets_no_digest_and_advisers_never_do(self):
        result = run_weekly_digest(self.conn, self.MONDAY_8AM)
        self.assertEqual(result["created"], 0)
        self.assertEqual(len(self.notifications()), 0)

    def test_the_digest_reads_applications_but_changes_nothing_else(self):
        self.new_application()
        before = [tuple(r) for r in self.rows("SELECT * FROM job_application")] + [tuple(r) for r in self.rows("SELECT id, status FROM follow_up_reminder")]
        run_weekly_digest(self.conn, self.MONDAY_8AM)
        after = [tuple(r) for r in self.rows("SELECT * FROM job_application")] + [tuple(r) for r in self.rows("SELECT id, status FROM follow_up_reminder")]
        self.assertEqual(before, after)


class TidyUpAndRunAllTests(AutomationBase):
    def test_old_read_notifications_and_finished_reminders_are_removed_but_unread_ones_stay(self):
        application_id = self.new_application("2026-01-01")
        self.conn.execute("UPDATE follow_up_reminder SET status = 'sent', processed_on = '2026-01-08' WHERE application_id = ?", (application_id,))
        for message, created, read in (("old read", "2026-01-01", 1), ("old unread", "2026-01-01", 0), ("recent read", "2026-11-20", 1)):
            self.conn.execute("INSERT INTO notification (user_id, kind, message, created_at, is_read) VALUES (?, 'nudge', ?, ?, ?)",
                              (self.seeker, message, created, read))
        self.conn.commit()
        result = run_tidy_up(self.conn, "2026-11-24")
        self.assertEqual(result, {"notifications_removed": 1, "reminders_removed": 1})
        self.assertEqual(sorted(r["message"] for r in self.notifications()), ["old unread", "recent read"])

    def test_run_all_returns_counts_only(self):
        self.new_application("2026-11-10")
        result = run_all(self.conn, datetime(2026, 11, 23, 8, 0, tzinfo=IRISH_TIME))
        self.assertEqual(result["reminders"]["sent"], 1)
        self.assertEqual(result["digest"]["created"], 1)
        self.assertEqual(set(result), {"reminders", "digest", "tidy_up"})


if __name__ == "__main__":
    import unittest
    unittest.main()
