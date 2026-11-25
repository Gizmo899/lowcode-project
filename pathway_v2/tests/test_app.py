"""Integration tests for the web app, using a temporary database."""

from io import BytesIO

from db import friendly_error_message
from tests.helpers import PASSWORD, PDF, AppTestCase


class AppBase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.adviser = self.add_user("adviser", "adviser@example.test", "Avery Adviser")
        self.other_adviser = self.add_user("adviser", "taylor@example.test", "Taylor Adviser")
        self.seeker = self.add_user("jobseeker", "seeker@example.test", "Jamie Jobseeker", "07123456789", self.adviser)
        self.other_seeker = self.add_user("jobseeker", "second@example.test", "Second Jobseeker", "07000000000", self.other_adviser)
        self.seeker_client = self.client_for("seeker@example.test")
        self.adviser_client = self.client_for("adviser@example.test")
        self.other_adviser_client = self.client_for("taylor@example.test")
        self.other_seeker_client = self.client_for("second@example.test")

    def application_form(self, **overrides):
        data = {"company_name": "Northstar Studio", "job_title": "Junior Designer", "date_applied": "2026-11-20",
                "advert_url": "https://example.test/jobs/123", "notes": "Phone screen booked"}
        data.update(overrides)
        return data

    def upload(self, client, name="sample.pdf", content=PDF, title="Marketing CV", mime="application/pdf"):
        client.get("/cv")
        return client.post("/cv", data={"csrf_token": self.csrf(client), "title": title,
                                         "cv_file": (BytesIO(content), name, mime)},
                           content_type="multipart/form-data")


class RegistrationAndSignInTests(AppBase):
    def register(self, **fields):
        client = self.app.test_client()
        data = {"role": "jobseeker", "full_name": "New Person", "email": "new@example.test",
                "password": PASSWORD, "assigned_adviser_id": str(self.adviser)}
        data.update(fields)
        return client, self.post(client, "/register", data)

    def test_a_valid_jobseeker_registers_with_a_hashed_password_and_chosen_adviser(self):
        _, response = self.register()
        self.assertEqual(response.status_code, 302)
        row = self.one("SELECT * FROM user WHERE email = 'new@example.test'")
        self.assertNotEqual(row["password_hash"], PASSWORD)
        self.assertEqual((row["role"], row["assigned_adviser_id"], row["phone"]), ("jobseeker", self.adviser, None))

    def test_password_rules_are_enforced_by_the_app(self):
        for bad in ("Short1!", "alllowercase1!", "NoSpecialChar1", "Has space1!A", "Éclair-pass"):
            with self.subTest(password=bad):
                _, response = self.register(password=bad)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(self.one("SELECT id FROM user WHERE email = 'new@example.test'"))

    def test_a_jobseeker_must_choose_an_adviser_when_advisers_exist(self):
        _, response = self.register(assigned_adviser_id="")
        self.assertIn("Select a career adviser", self.text(response))

    def test_a_jobseeker_cannot_pick_a_jobseeker_as_adviser(self):
        _, response = self.register(assigned_adviser_id=str(self.seeker))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.one("SELECT id FROM user WHERE email = 'new@example.test'"))

    def test_an_adviser_registers_without_a_phone_or_adviser(self):
        _, response = self.register(role="adviser", phone="0851234567", assigned_adviser_id="")
        self.assertEqual(response.status_code, 302)
        row = self.one("SELECT phone, assigned_adviser_id FROM user WHERE email = 'new@example.test'")
        self.assertEqual((row["phone"], row["assigned_adviser_id"]), (None, None))

    def test_the_old_role_name_is_refused(self):
        _, response = self.register(role="career_adviser")
        self.assertEqual(response.status_code, 200)

    def test_duplicate_email_and_phone_get_a_friendly_message_not_a_crash(self):
        _, response = self.register(email="SEEKER@example.test")
        self.assertIn("already in use", self.text(response))
        self.assertEqual(response.status_code, 200)
        _, response = self.register(phone="07123456789")
        self.assertIn("phone number is already in use", self.text(response))

    def test_sign_in_failure_is_generic_and_capitals_in_the_email_do_not_matter(self):
        client = self.app.test_client()
        bad = self.login(client, "seeker@example.test", "Wrong-password1!")
        self.assertEqual(bad.status_code, 401)
        good = self.login(self.app.test_client(), "SEEKER@Example.test")
        self.assertEqual(good.status_code, 302)

    def test_csrf_token_is_required_for_state_changes(self):
        self.assertEqual(self.app.test_client().post("/login", data={"email": "x@y.test", "password": "bad"}).status_code, 400)

    def test_jobseekers_and_advisers_cannot_open_each_others_pages(self):
        self.assertEqual(self.seeker_client.get("/adviser/dashboard").status_code, 403)
        self.assertEqual(self.adviser_client.get("/dashboard").status_code, 403)
        self.assertEqual(self.adviser_client.get("/applications").status_code, 403)
        self.assertEqual(self.adviser_client.get("/cv").status_code, 403)
        self.assertEqual(self.adviser_client.get("/notifications").status_code, 403)


class ApplicationTests(AppBase):
    def test_saving_an_application_plans_a_reminder_seven_days_after_the_date_applied(self):
        response = self.post(self.seeker_client, "/applications/new", self.application_form())
        self.assertEqual(response.status_code, 302)
        application = self.one("SELECT * FROM job_application")
        self.assertEqual((application["status"], application["notes"]), ("applied", "Phone screen booked"))
        reminder = self.one("SELECT * FROM follow_up_reminder")
        self.assertEqual((reminder["application_id"], reminder["due_on"], reminder["status"]),
                         (application["id"], "2026-11-27", "pending"))

    def test_link_and_notes_are_optional(self):
        self.post(self.seeker_client, "/applications/new", self.application_form(advert_url="", notes=""))
        row = self.one("SELECT advert_url, notes FROM job_application")
        self.assertEqual((row["advert_url"], row["notes"]), (None, None))

    def test_bad_values_are_refused_and_nothing_is_saved(self):
        for label, overrides in (
            ("future date", {"date_applied": "2999-01-01"}),
            ("not a date", {"date_applied": "soon"}),
            ("bad link", {"advert_url": "ftp://x.y"}),
            ("link with space", {"advert_url": "https://x.y/a b"}),
            ("no company", {"company_name": ""}),
        ):
            with self.subTest(label):
                response = self.post(self.seeker_client, "/applications/new", self.application_form(**overrides))
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.one("SELECT COUNT(*) FROM job_application")[0], 0)

    def test_a_new_application_always_starts_as_applied_even_if_the_form_says_otherwise(self):
        self.post(self.seeker_client, "/applications/new", self.application_form(status="interview"))
        self.assertEqual(self.one("SELECT status FROM job_application")["status"], "applied")

    def test_leaving_applied_cancels_the_reminder_and_it_can_never_go_back(self):
        self.post(self.seeker_client, "/applications/new", self.application_form())
        application_id = self.one("SELECT id FROM job_application")["id"]
        url = f"/applications/{application_id}/edit"
        response = self.post(self.seeker_client, url, self.application_form(status="interview"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.one("SELECT status FROM follow_up_reminder")["status"], "skipped")
        back = self.post(self.seeker_client, url, self.application_form(status="applied"))
        self.assertEqual(back.status_code, 200)
        self.assertIn("cannot move back to applied", self.text(back))
        self.assertEqual(self.one("SELECT status FROM job_application")["status"], "interview")
        self.assertNotIn('value="applied"', self.text(self.seeker_client.get(url)))
        self.post(self.seeker_client, url, self.application_form(status="rejected"))   # other moves are allowed
        self.assertEqual(self.one("SELECT status FROM job_application")["status"], "rejected")

    def test_missing_and_other_peoples_applications_give_404(self):
        application_id = self.add_application(self.seeker)
        for client in (self.other_seeker_client, self.seeker_client):
            target = 99999 if client is self.seeker_client else application_id
            self.assertEqual(client.get(f"/applications/{target}/edit").status_code, 404)
            self.assertEqual(self.post(client, f"/applications/{target}/delete").status_code, 404)
        self.assertEqual(self.one("SELECT COUNT(*) FROM job_application")[0], 1)

    def test_deleting_an_application_removes_its_reminders(self):
        self.post(self.seeker_client, "/applications/new", self.application_form())
        application_id = self.one("SELECT id FROM job_application")["id"]
        self.post(self.seeker_client, f"/applications/{application_id}/delete")
        self.assertEqual(self.one("SELECT COUNT(*) FROM follow_up_reminder")[0], 0)

    def test_a_database_rejection_shows_a_friendly_message_and_keeps_the_form(self):
        # the app's own check passes, but the database refuses (the phone is already used)
        response = self.post(self.seeker_client, "/profile",
                             {"full_name": "Jamie", "email": "seeker@example.test", "phone": "07000000000"})
        self.assertEqual(response.status_code, 200)
        page = self.text(response)
        self.assertIn("phone number is already in use", page)
        self.assertNotIn("constraint", page.lower())
        self.assertNotIn("Traceback", page)

    def test_friendly_messages_never_leak_database_text(self):
        message = friendly_error_message(Exception("CHECK constraint failed: length(trim(title)) > 0 -- secret"))
        self.assertNotIn("CHECK", message)
        self.assertNotIn("secret", message)


class AdviserAccessTests(AppBase):
    def test_an_adviser_sees_only_their_own_jobseekers(self):
        page = self.text(self.adviser_client.get("/adviser/dashboard"))
        self.assertIn("Jamie Jobseeker", page)
        self.assertNotIn("Second Jobseeker", page)
        self.assertEqual(self.adviser_client.get(f"/adviser/jobseekers/{self.seeker}").status_code, 200)
        self.assertEqual(self.adviser_client.get(f"/adviser/jobseekers/{self.other_seeker}").status_code, 404)
        self.assertEqual(self.other_adviser_client.get(f"/adviser/jobseekers/{self.seeker}").status_code, 404)
        self.assertEqual(self.adviser_client.get("/adviser/jobseekers/99999").status_code, 404)

    def test_an_adviser_sees_application_notes_but_never_the_phone_number(self):
        self.add_application(self.seeker, notes="Private thoughts about the interview")
        for url in ("/adviser/dashboard", f"/adviser/jobseekers/{self.seeker}"):
            page = self.text(self.adviser_client.get(url))
            self.assertNotIn("07123456789", page)
        self.assertIn("Private thoughts about the interview", self.text(self.adviser_client.get(f"/adviser/jobseekers/{self.seeker}")))

    def test_an_adviser_cannot_change_applications(self):
        application_id = self.add_application(self.seeker)
        self.assertEqual(self.adviser_client.get(f"/applications/{application_id}/edit").status_code, 403)
        self.assertEqual(self.post(self.adviser_client, f"/applications/{application_id}/delete").status_code, 403)
        self.assertEqual(self.post(self.adviser_client, "/applications/new", self.application_form()).status_code, 403)


class CvTests(AppBase):
    def test_a_valid_upload_is_stored_inside_the_database_and_waits_for_review(self):
        self.assertEqual(self.upload(self.seeker_client).status_code, 302)
        cv = self.one("SELECT * FROM cv")
        self.assertEqual((cv["title"], cv["status"], cv["file_type"], bytes(cv["file_data"])), ("Marketing CV", "waiting_for_review", "pdf", PDF))

    def test_bad_files_are_refused(self):
        self.upload(self.seeker_client, name="notes.txt", content=b"hello", mime="text/plain")
        self.upload(self.seeker_client, name="fake.pdf", content=b"this is not a pdf")
        self.upload(self.seeker_client, name="empty.pdf", content=b"")
        self.upload(self.seeker_client, title="   ")
        self.assertEqual(self.one("SELECT COUNT(*) FROM cv")[0], 0)

    def test_the_size_limit_is_exactly_one_megabyte(self):
        exactly = b"%PDF-" + b"a" * (1_048_576 - 5)
        self.assertEqual(len(exactly), 1_048_576)
        self.upload(self.seeker_client, name="exact.pdf", content=exactly)
        self.assertEqual(self.one("SELECT COUNT(*) FROM cv")[0], 1)
        response = self.upload(self.seeker_client, name="big.pdf", content=exactly + b"a")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.one("SELECT COUNT(*) FROM cv")[0], 1)
        self.assertIn("1 MB", self.text(self.seeker_client.get("/cv")))

    def test_only_the_owner_and_the_linked_adviser_can_download(self):
        cv_id = self.add_cv(self.seeker)
        url = f"/cv/{cv_id}/download"
        self.assertEqual(self.seeker_client.get(url).data, PDF)
        self.assertEqual(self.adviser_client.get(url).data, PDF)
        self.assertEqual(self.other_seeker_client.get(url).status_code, 404)
        self.assertEqual(self.other_adviser_client.get(url).status_code, 404)
        self.assertEqual(self.app.test_client().get(url).status_code, 401)
        self.assertEqual(self.seeker_client.get("/cv/99999/download").status_code, 404)

    def test_approving_notifies_the_jobseeker_and_records_who_and_when(self):
        cv_id = self.add_cv(self.seeker, "Marketing CV")
        response = self.post(self.adviser_client, f"/adviser/cv/{cv_id}/review", {"decision": "approved"})
        self.assertEqual(response.status_code, 302)
        cv = self.one("SELECT status, decided_by, decided_at, comment FROM cv WHERE id = ?", (cv_id,))
        self.assertEqual((cv["status"], cv["decided_by"], cv["comment"]), ("approved", self.adviser, None))
        self.assertTrue(cv["decided_at"])
        note = self.one("SELECT * FROM notification WHERE user_id = ?", (self.seeker,))
        self.assertEqual(note["kind"], "cv_decision")
        self.assertIn("approved", note["message"])

    def test_a_rejection_comment_stays_on_the_cv_and_is_not_copied_into_the_notification(self):
        cv_id = self.add_cv(self.seeker)
        self.post(self.adviser_client, f"/adviser/cv/{cv_id}/review", {"decision": "rejected", "comment": "Add your last job"})
        self.assertEqual(self.one("SELECT comment FROM cv WHERE id = ?", (cv_id,))["comment"], "Add your last job")
        self.assertNotIn("Add your last job", self.one("SELECT message FROM notification")["message"])
        self.assertIn("Add your last job", self.text(self.seeker_client.get("/cv")))

    def test_a_comment_on_an_approval_is_refused(self):
        cv_id = self.add_cv(self.seeker)
        self.post(self.adviser_client, f"/adviser/cv/{cv_id}/review", {"decision": "approved", "comment": "nice"})
        self.assertEqual(self.one("SELECT status FROM cv WHERE id = ?", (cv_id,))["status"], "waiting_for_review")

    def test_an_adviser_who_is_not_linked_cannot_decide_and_a_decided_cv_cannot_be_decided_again(self):
        cv_id = self.add_cv(self.seeker)
        self.assertEqual(self.post(self.other_adviser_client, f"/adviser/cv/{cv_id}/review", {"decision": "approved"}).status_code, 404)
        self.assertEqual(self.post(self.seeker_client, f"/adviser/cv/{cv_id}/review", {"decision": "approved"}).status_code, 403)
        self.post(self.adviser_client, f"/adviser/cv/{cv_id}/review", {"decision": "approved"})
        self.post(self.adviser_client, f"/adviser/cv/{cv_id}/review", {"decision": "rejected"})
        self.assertEqual(self.one("SELECT status FROM cv WHERE id = ?", (cv_id,))["status"], "approved")
        self.assertEqual(self.one("SELECT COUNT(*) FROM notification")[0], 1)

    def test_replacing_the_file_resets_the_approval_and_renaming_does_not(self):
        cv_id = self.add_cv(self.seeker)
        self.post(self.adviser_client, f"/adviser/cv/{cv_id}/review", {"decision": "rejected", "comment": "Too short"})
        self.post(self.seeker_client, f"/cv/{cv_id}/title", {"title": "Renamed"})
        self.assertEqual(tuple(self.one("SELECT title, status, comment FROM cv WHERE id = ?", (cv_id,))), ("Renamed", "rejected", "Too short"))
        new_pdf = b"%PDF-1.7\nsecond version"
        self.seeker_client.get("/cv")
        self.seeker_client.post(f"/cv/{cv_id}/replace", data={"csrf_token": self.csrf(self.seeker_client),
                                "cv_file": (BytesIO(new_pdf), "v2.pdf", "application/pdf")}, content_type="multipart/form-data")
        cv = self.one("SELECT status, decided_by, decided_at, comment, file_name, file_data FROM cv WHERE id = ?", (cv_id,))
        self.assertEqual((cv["status"], cv["decided_by"], cv["decided_at"], cv["comment"], cv["file_name"], bytes(cv["file_data"])),
                         ("waiting_for_review", None, None, None, "v2.pdf", new_pdf))

    def test_deleting_a_cv_and_other_peoples_cvs(self):
        cv_id = self.add_cv(self.seeker)
        self.assertEqual(self.post(self.other_seeker_client, f"/cv/{cv_id}/delete").status_code, 404)
        self.assertEqual(self.post(self.other_seeker_client, f"/cv/{cv_id}/title", {"title": "Hijack"}).status_code, 404)
        self.assertEqual(self.post(self.seeker_client, f"/cv/{cv_id}/delete").status_code, 302)
        self.assertEqual(self.one("SELECT COUNT(*) FROM cv")[0], 0)


class AccountTests(AppBase):
    def test_closing_a_jobseeker_account_deletes_all_of_their_data(self):
        self.add_cv(self.seeker)
        self.add_application(self.seeker)
        self.conn.execute("INSERT INTO notification (user_id, kind, message, created_at) VALUES (?, 'digest', 'x', '2026-11-23')", (self.seeker,))
        self.conn.commit()
        bad = self.post(self.seeker_client, "/account/close", {"password": "wrong"})
        self.assertEqual(self.one("SELECT COUNT(*) FROM user WHERE id = ?", (self.seeker,))[0], 1)
        self.post(self.seeker_client, "/account/close", {"password": PASSWORD})
        self.assertEqual(self.one("SELECT COUNT(*) FROM user WHERE id = ?", (self.seeker,))[0], 0)
        for sql in ("SELECT COUNT(*) FROM cv", "SELECT COUNT(*) FROM job_application", "SELECT COUNT(*) FROM notification"):
            self.assertEqual(self.one(sql)[0], 0)
        self.assertEqual(bad.status_code, 302)

    def test_closing_an_adviser_account_keeps_the_jobseekers_and_decided_cvs(self):
        cv_id = self.add_cv(self.seeker)
        self.post(self.adviser_client, f"/adviser/cv/{cv_id}/review", {"decision": "rejected", "comment": "Add your last job"})
        self.post(self.adviser_client, "/adviser/account/close", {"password": PASSWORD})
        self.assertIsNone(self.one("SELECT id FROM user WHERE id = ?", (self.adviser,)))
        self.assertIsNone(self.one("SELECT assigned_adviser_id FROM user WHERE id = ?", (self.seeker,))[0])
        cv = self.one("SELECT status, decided_by, comment FROM cv WHERE id = ?", (cv_id,))
        self.assertEqual((cv["status"], cv["decided_by"], cv["comment"]), ("rejected", None, "Add your last job"))

    def test_a_jobseeker_whose_adviser_left_can_choose_again_once(self):
        self.post(self.adviser_client, "/adviser/account/close", {"password": PASSWORD})
        self.assertIn("Choose an adviser", self.text(self.seeker_client.get("/dashboard")))
        self.post(self.seeker_client, "/jobseeker/assign-adviser", {"assigned_adviser_id": str(self.other_adviser)})
        self.assertEqual(self.one("SELECT assigned_adviser_id FROM user WHERE id = ?", (self.seeker,))[0], self.other_adviser)
        again = self.post(self.seeker_client, "/jobseeker/assign-adviser", {"assigned_adviser_id": str(self.adviser)})
        self.assertEqual(again.status_code, 403)
        self.assertEqual(self.one("SELECT assigned_adviser_id FROM user WHERE id = ?", (self.seeker,))[0], self.other_adviser)

    def test_a_non_adviser_cannot_be_chosen_as_adviser(self):
        self.post(self.adviser_client, "/adviser/account/close", {"password": PASSWORD})
        self.post(self.seeker_client, "/jobseeker/assign-adviser", {"assigned_adviser_id": str(self.other_seeker)})
        self.assertIsNone(self.one("SELECT assigned_adviser_id FROM user WHERE id = ?", (self.seeker,))[0])


class NotificationAndDigestTests(AppBase):
    def test_notifications_are_private_and_can_be_marked_read(self):
        self.conn.execute("INSERT INTO notification (user_id, kind, message, created_at) VALUES (?, 'nudge', 'Follow up with Acme', '2026-11-23')", (self.seeker,))
        self.conn.commit()
        note_id = self.one("SELECT id FROM notification")["id"]
        self.assertIn("Follow up with Acme", self.text(self.seeker_client.get("/notifications")))
        self.assertNotIn("Follow up with Acme", self.text(self.other_seeker_client.get("/notifications")))
        self.assertEqual(self.post(self.other_seeker_client, f"/notifications/{note_id}/read").status_code, 404)
        self.post(self.seeker_client, f"/notifications/{note_id}/read")
        self.assertEqual(self.one("SELECT is_read FROM notification")["is_read"], 1)

    def test_the_digest_page_works_out_the_figures_live(self):
        self.add_application(self.seeker, company="Waiting Ltd")
        page = self.text(self.seeker_client.get("/digest"))
        self.assertIn("Waiting Ltd", page)
        self.assertEqual(self.one("SELECT COUNT(*) FROM notification")[0], 0)   # nothing is stored for it

    def test_every_page_renders_for_each_role(self):
        for url in ("/", "/dashboard", "/profile", "/applications", "/applications/new", "/cv", "/notifications", "/digest", "/privacy"):
            self.assertIn(self.seeker_client.get(url, follow_redirects=True).status_code, (200,), url)
        for url in ("/", "/adviser/dashboard", "/adviser/profile", f"/adviser/jobseekers/{self.seeker}"):
            self.assertEqual(self.adviser_client.get(url, follow_redirects=True).status_code, 200, url)
        self.assertEqual(self.app.test_client().get("/nope").status_code, 404)


if __name__ == "__main__":
    import unittest
    unittest.main()
