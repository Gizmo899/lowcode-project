"""Tests for the database rules in schema/001_initial.sql: bad data must be rejected."""

import sqlite3

from db import get_connection
from tests.helpers import PDF, DatabaseTestCase

U = "INSERT INTO user (full_name, email, password_hash, phone, role, assigned_adviser_id) VALUES (?, ?, ?, ?, ?, ?)"
CV = "INSERT INTO cv (jobseeker_id, title, file_name, file_type, file_data) VALUES (?, ?, ?, ?, ?)"
APP = ("INSERT INTO job_application (jobseeker_id, company_name, job_title, date_applied, status, advert_url) "
       "VALUES (?, ?, ?, ?, ?, ?)")
DECIDE = "UPDATE cv SET status = ?, decided_by = ?, decided_at = '2026-11-23' WHERE id = ?"


class SchemaBase(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.adviser = self.add_user("adviser", "a@x.test", "Adviser A", "111")
        self.adviser_b = self.add_user("adviser", "b@x.test", "Adviser B")
        self.seeker = self.add_user("jobseeker", "j@x.test", "Jobseeker", "222", self.adviser)
        self.loner = self.add_user("jobseeker", "l@x.test", "No Adviser")


class UserRuleTests(SchemaBase):
    def test_duplicate_email_is_rejected_even_with_different_capitals(self):
        self.assertRejected(U, ("X", "J@X.TEST", "h", None, "jobseeker", None))

    def test_duplicate_phone_is_rejected_across_roles(self):
        self.assertRejected(U, ("X", "n@x.test", "h", "111", "jobseeker", None))

    def test_blank_phone_must_be_null_and_many_nulls_are_fine(self):
        self.assertRejected(U, ("X", "n1@x.test", "h", "", "jobseeker", None))
        self.assertRejected(U, ("X", "n2@x.test", "h", "   ", "jobseeker", None))
        self.conn.execute(U, ("Y", "n3@x.test", "h", None, "jobseeker", None))

    def test_missing_or_blank_required_fields_are_rejected(self):
        self.assertRejected(U, (None, "n@x.test", "h", None, "jobseeker", None))
        self.assertRejected(U, ("   ", "n@x.test", "h", None, "jobseeker", None))
        self.assertRejected(U, ("X", None, "h", None, "jobseeker", None))
        self.assertRejected(U, ("X", "n@x.test", None, None, "jobseeker", None))
        self.assertRejected(U, ("X", "n@x.test", "h", None, None, None))

    def test_role_must_be_jobseeker_or_adviser(self):
        self.assertRejected(U, ("X", "n@x.test", "h", None, "admin", None))

    def test_an_adviser_cannot_have_an_adviser(self):
        self.assertRejected(U, ("X", "n@x.test", "h", None, "adviser", self.adviser))

    def test_the_linked_person_must_be_an_adviser(self):
        self.assertRejected(U, ("X", "n@x.test", "h", None, "jobseeker", self.seeker))
        self.assertRejected(U, ("X", "n@x.test", "h", None, "jobseeker", 9999))
        self.assertRejected("UPDATE user SET assigned_adviser_id = ? WHERE id = ?", (self.seeker, self.loner))

    def test_a_role_can_never_change(self):
        self.assertRejected("UPDATE user SET role = 'adviser', assigned_adviser_id = NULL WHERE id = ?", (self.seeker,))

    def test_the_adviser_choice_cannot_be_switched_but_can_be_made_from_empty(self):
        self.assertRejected("UPDATE user SET assigned_adviser_id = ? WHERE id = ?", (self.adviser_b, self.seeker))
        self.conn.execute("UPDATE user SET assigned_adviser_id = ? WHERE id = ?", (self.adviser, self.loner))


class CvRuleTests(SchemaBase):
    def test_a_cv_must_belong_to_a_real_jobseeker(self):
        self.assertRejected(CV, (self.adviser, "T", "a.pdf", "pdf", PDF))
        self.assertRejected(CV, (9999, "T", "a.pdf", "pdf", PDF))

    def test_required_fields_and_allowed_values(self):
        self.assertRejected(CV, (self.seeker, "  ", "a.pdf", "pdf", PDF))
        self.assertRejected(CV, (self.seeker, "T", None, "pdf", PDF))
        self.assertRejected(CV, (self.seeker, "T", "a.txt", "txt", PDF))
        self.assertRejected(CV, (self.seeker, "T", "a.pdf", "pdf", None))

    def test_file_size_limit_is_one_megabyte_exactly(self):
        self.assertRejected(CV, (self.seeker, "T", "a.pdf", "pdf", b""))
        self.assertRejected(CV, (self.seeker, "T", "a.pdf", "pdf", b"a" * 1_048_577))
        self.conn.execute(CV, (self.seeker, "Big", "a.pdf", "pdf", b"a" * 1_048_576))

    def test_the_file_must_be_bytes_not_text(self):
        self.assertRejected(CV, (self.seeker, "T", "a.pdf", "pdf", "just text"))

    def test_a_new_cv_cannot_start_already_decided(self):
        self.assertRejected(
            "INSERT INTO cv (jobseeker_id, title, file_name, file_type, file_data, status, decided_by, decided_at) "
            "VALUES (?, 'T', 'a.pdf', 'pdf', ?, 'approved', ?, '2026-11-23')",
            (self.seeker, PDF, self.adviser),
        )

    def test_status_and_decision_fields_must_agree(self):
        cv = self.add_cv(self.seeker)
        self.assertRejected("UPDATE cv SET comment = 'hi' WHERE id = ?", (cv,))                 # comment on a waiting CV
        self.assertRejected("UPDATE cv SET decided_at = '2026-11-23' WHERE id = ?", (cv,))     # date on a waiting CV
        self.assertRejected(DECIDE.replace("'2026-11-23'", "'2026-02-30'"), ("approved", self.adviser, cv))
        self.assertRejected(
            "UPDATE cv SET status = 'approved', decided_by = ?, decided_at = '2026-11-23', comment = 'x' WHERE id = ?",
            (self.adviser, cv),
        )                                                                                         # comment on an approval
        self.assertRejected(
            "UPDATE cv SET status = 'rejected', decided_by = ?, decided_at = '2026-11-23', comment = '  ' WHERE id = ?",
            (self.adviser, cv),
        )                                                                                         # blank comment

    def test_only_the_owners_adviser_can_decide(self):
        cv = self.add_cv(self.seeker)
        self.assertRejected(DECIDE, ("approved", self.adviser_b, cv))      # an adviser who is not linked
        self.assertRejected("UPDATE cv SET status = 'approved', decided_at = '2026-11-23' WHERE id = ?", (cv,))  # nobody named
        loner_cv = self.add_cv(self.loner)
        self.assertRejected(DECIDE, ("approved", self.adviser, loner_cv))  # owner has no adviser
        self.conn.execute(DECIDE, ("approved", self.adviser, cv))          # the right adviser works
        self.assertEqual(self.one("SELECT status FROM cv WHERE id = ?", (cv,))["status"], "approved")


class ApplicationRuleTests(SchemaBase):
    def test_required_fields_and_dates(self):
        ok = (self.seeker, "Acme", "Dev", "2026-11-15", "applied", None)
        self.conn.execute(APP, ok)
        self.assertRejected(APP, (self.seeker, None, "Dev", "2026-11-15", "applied", None))
        self.assertRejected(APP, (self.seeker, " ", "Dev", "2026-11-15", "applied", None))
        self.assertRejected(APP, (self.seeker, "A", None, "2026-11-15", "applied", None))
        self.assertRejected(APP, (self.seeker, "A", "Dev", None, "applied", None))
        self.assertRejected(APP, (self.seeker, "A", "Dev", "2026-02-30", "applied", None))
        self.assertRejected(APP, (self.seeker, "A", "Dev", "15/11/2026", "applied", None))

    def test_stage_values_and_new_applications_start_as_applied(self):
        self.assertRejected(APP, (self.seeker, "A", "Dev", "2026-11-15", "offer", None))
        self.assertRejected(APP, (self.seeker, "A", "Dev", "2026-11-15", "interview", None))

    def test_the_owner_must_be_a_jobseeker(self):
        self.assertRejected(APP, (self.adviser, "A", "Dev", "2026-11-15", "applied", None))

    def test_advert_link_form(self):
        for bad in ("ftp://x.y", "example.com", "https://x.y/a b"):
            with self.subTest(link=bad):
                self.assertRejected(APP, (self.seeker, "A", "Dev", "2026-11-15", "applied", bad))
        self.conn.execute(APP, (self.seeker, "A", "Dev", "2026-11-15", "applied", "https://x.y/z"))


class ReminderAndNotificationRuleTests(SchemaBase):
    def setUp(self):
        super().setUp()
        self.application = self.add_application(self.seeker)

    R = "INSERT INTO follow_up_reminder (application_id, due_on, status, processed_on) VALUES (?, ?, ?, ?)"
    N = "INSERT INTO notification (user_id, kind, message, created_at, is_read) VALUES (?, ?, ?, ?, ?)"

    def test_only_one_waiting_reminder_per_application(self):
        self.conn.execute(self.R, (self.application, "2026-11-22", "pending", None))
        self.assertRejected(self.R, (self.application, "2026-11-29", "pending", None))

    def test_state_and_processed_date_must_agree(self):
        self.assertRejected(self.R, (self.application, "2026-11-22", "pending", "2026-11-22"))
        self.assertRejected(self.R, (self.application, "2026-11-22", "sent", None))
        self.assertRejected(self.R, (self.application, "2026-11-22", "late", None))
        self.assertRejected(self.R, (self.application, "2026-02-30", "pending", None))
        self.assertRejected(self.R, (9999, "2026-11-22", "pending", None))

    def test_notification_rules(self):
        self.conn.execute(self.N, (self.seeker, "nudge", "hello", "2026-11-22", 0))
        self.assertRejected(self.N, (self.seeker, "email", "x", "2026-11-22", 0))
        self.assertRejected(self.N, (self.seeker, "nudge", "  ", "2026-11-22", 0))
        self.assertRejected(self.N, (self.seeker, "nudge", "x", "22-11-2026", 0))
        self.assertRejected(self.N, (self.seeker, "nudge", "x", "2026-11-22", 2))
        self.assertRejected(self.N, (self.adviser, "nudge", "x", "2026-11-22", 0))  # advisers get none


class DeleteRuleTests(SchemaBase):
    def test_rule_1_deleting_a_jobseeker_deletes_everything_they_own(self):
        application = self.add_application(self.seeker)
        self.conn.execute("INSERT INTO follow_up_reminder (application_id, due_on) VALUES (?, '2026-11-22')", (application,))
        self.conn.execute("INSERT INTO notification (user_id, kind, message, created_at) VALUES (?, 'digest', 'x', '2026-11-23')", (self.seeker,))
        self.add_cv(self.seeker)
        self.conn.execute("DELETE FROM user WHERE id = ?", (self.seeker,))
        self.assertEqual(self.one("SELECT COUNT(*) FROM cv WHERE jobseeker_id = ?", (self.seeker,))[0], 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM job_application WHERE jobseeker_id = ?", (self.seeker,))[0], 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM notification WHERE user_id = ?", (self.seeker,))[0], 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM follow_up_reminder")[0], 0)

    def test_rules_2_and_3_deleting_an_adviser_unlinks_jobseekers_and_keeps_decided_cvs(self):
        approved, rejected = self.add_cv(self.seeker, "One"), self.add_cv(self.seeker, "Two")
        self.conn.execute(DECIDE, ("approved", self.adviser, approved))
        self.conn.execute(
            "UPDATE cv SET status = 'rejected', decided_by = ?, decided_at = '2026-11-23', comment = 'Add last job' WHERE id = ?",
            (self.adviser, rejected),
        )
        self.conn.execute("DELETE FROM user WHERE id = ?", (self.adviser,))
        self.assertIsNone(self.one("SELECT assigned_adviser_id FROM user WHERE id = ?", (self.seeker,))[0])
        self.assertEqual(tuple(self.one("SELECT status, decided_by, decided_at, comment FROM cv WHERE id = ?", (approved,))),
                         ("approved", None, "2026-11-23", None))
        self.assertEqual(tuple(self.one("SELECT status, decided_by, decided_at, comment FROM cv WHERE id = ?", (rejected,))),
                         ("rejected", None, "2026-11-23", "Add last job"))
        # the unlinked jobseeker can choose a new adviser once, and then not switch
        self.conn.execute("UPDATE user SET assigned_adviser_id = ? WHERE id = ?", (self.adviser_b, self.seeker))
        self.assertRejected("UPDATE user SET assigned_adviser_id = NULL, role = 'adviser' WHERE id = ?", (self.seeker,))

    def test_foreign_keys_are_really_on(self):
        self.assertEqual(self.one("PRAGMA foreign_keys")[0], 1)


class PersistenceTests(DatabaseTestCase):
    def test_data_survives_closing_and_reopening_the_database_file(self):
        seeker = self.add_user("jobseeker", "p@x.test", "Persistent")
        self.add_application(seeker, company="Kept Ltd")
        self.add_cv(seeker, title="Kept CV")
        self.conn.close()
        reopened = get_connection(self.db_path)
        try:
            self.assertEqual(reopened.execute("SELECT company_name FROM job_application").fetchone()[0], "Kept Ltd")
            self.assertEqual(reopened.execute("SELECT title FROM cv").fetchone()[0], "Kept CV")
            self.assertEqual(reopened.execute("SELECT email FROM user").fetchone()[0], "p@x.test")
        finally:
            reopened.close()
        self.conn = get_connection(self.db_path)  # so tearDown cleanup has something to close

    def test_migrations_apply_once_and_only_once(self):
        from tools.migrate import apply_migrations
        self.assertEqual(apply_migrations(self.db_path), [])  # already applied in setUp


if __name__ == "__main__":
    import unittest
    unittest.main()
