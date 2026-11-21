"""Tests for email validation, the password rule for changing email, and safe mailto: links."""

import tempfile
import unittest
from pathlib import Path

from app import create_app
from db import get_db
from utils import mailto_link, valid_email

PASSWORD = "a-long-test-password"
ATTACK = "a@b.com?bcc=x@y.test"  # the address from the review finding


class ValidEmailTests(unittest.TestCase):
    def test_accepts_the_addresses_people_really_use(self):
        for address in (
            "a@b.com",
            "jamie.jobseeker@example.test",
            "first.last+jobs@sub.example.co.uk",
            "o'brien@example.ie",
            "USER@EXAMPLE.COM",
            "a_b-c@x-y.io",
            "x" * 64 + "@example.com",
        ):
            with self.subTest(address=address):
                self.assertTrue(valid_email(address))

    def test_rejects_the_attack_and_the_bare_at_sign_from_the_review(self):
        self.assertFalse(valid_email(ATTACK))
        self.assertFalse(valid_email("@"))

    def test_rejects_characters_that_change_what_a_mailto_link_does(self):
        for address in (
            "a?bcc=x@y.test",
            "a&cc=x@y.test",
            "a@b.com#frag",
            "a@b.com/path",
            "a%40b@c.com",
            "a@b.com,c@d.com",
            "a@b.com;c@d.com",
            "<a@b.com>",
            '"a b"@c.com',
            "a b@c.com",
            " a@b.com",
            "a@b.com\n",
            "a@b.com\r\nBcc: x@y.test",
        ):
            with self.subTest(address=address):
                self.assertFalse(valid_email(address))

    def test_rejects_malformed_addresses(self):
        for address in (
            "",
            "a@",
            "@b.com",
            "a@b",
            "a@b.",
            "a@.com",
            "a@b..com",
            "a@b.c",
            "a@@b.com",
            "a@b@c.com",
            ".a@b.com",
            "a.@b.com",
            "a..b@c.com",
            "a@-b.com",
            "a@b-.com",
            "a@[1.2.3.4]",
            "a@localhost",
            "é@b.com",
            "a@bücher.com",
            "x" * 65 + "@example.com",
            "a@" + "x" * 64 + ".com",
        ):
            with self.subTest(address=address):
                self.assertFalse(valid_email(address))

    def test_rejects_things_that_are_not_text(self):
        for value in (None, 123, ["a@b.com"]):
            with self.subTest(value=value):
                self.assertFalse(valid_email(value))

    def test_mailto_link_is_only_built_for_a_valid_address(self):
        self.assertEqual(mailto_link("jamie@example.test"), "mailto:jamie@example.test")
        self.assertEqual(mailto_link("o'brien+jobs@example.ie"), "mailto:o'brien+jobs@example.ie")
        for value in (ATTACK, "@", "", None):
            with self.subTest(value=value):
                self.assertIsNone(mailto_link(value))


class EmailFlowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-not-for-deployment",
                "DATABASE": str(root / "test.sqlite"),
                "UPLOAD_FOLDER": str(root / "private" / "cv"),
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.adviser = self.app.test_client()
        self.seeker = self.app.test_client()
        self.register(self.adviser, role="career_adviser", full_name="Avery Adviser", email="adviser@example.test")
        self.adviser_id = self.user_id("adviser@example.test")
        self.register(
            self.seeker,
            role="jobseeker",
            full_name="Jamie Jobseeker",
            email="jobseeker@example.test",
            phone="07123456789",
            assigned_adviser_id=str(self.adviser_id),
        )
        self.seeker_id = self.user_id("jobseeker@example.test")
        self.login(self.adviser, "adviser@example.test")
        self.login(self.seeker, "jobseeker@example.test")

    # ----- helpers
    def csrf(self, client):
        client.get("/register")
        with client.session_transaction() as session:
            return session["csrf_token"]

    def register(self, client, **fields):
        data = {"csrf_token": self.csrf(client), "password": PASSWORD}
        data.update(fields)
        return client.post("/register", data=data)

    def login(self, client, email, password=PASSWORD):
        client.get("/login")
        return client.post("/login", data={"csrf_token": self.csrf(client), "email": email, "password": password})

    def rows(self, query, params=()):
        with self.app.app_context():
            return get_db().execute(query, params).fetchall()

    def user_id(self, email):
        return self.rows("SELECT id FROM users WHERE email = ?", (email,))[0][0]

    def email_of(self, user_id):
        return self.rows("SELECT email FROM users WHERE id = ?", (user_id,))[0][0]

    def set_email_directly(self, user_id, email):
        """Write an address straight into the database, the way an older version of the app could."""
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
            db.commit()

    def seeker_profile(self, **overrides):
        data = {"full_name": "Jamie Jobseeker", "email": "jobseeker@example.test", "phone": "07123456789"}
        data.update(overrides)
        data["csrf_token"] = self.csrf(self.seeker)
        return self.seeker.post("/profile", data=data)

    def adviser_profile(self, **overrides):
        data = {"full_name": "Avery Adviser", "email": "adviser@example.test"}
        data.update(overrides)
        data["csrf_token"] = self.csrf(self.adviser)
        return self.adviser.post("/adviser/profile", data=data)

    # ----- registration
    def test_registration_refuses_bad_addresses_and_creates_no_account(self):
        for address in ("@", ATTACK, "a@b", "a b@example.test", "a@b.com\r\nBcc: x@y.test"):
            with self.subTest(address=address):
                client = self.app.test_client()
                response = self.register(
                    client, role="career_adviser", full_name="Mallory", email=address
                )
                self.assertEqual(response.status_code, 200)  # form shown again, not redirected
                self.assertIn("Enter a valid email address.", response.get_data(as_text=True))
                self.assertEqual(self.rows("SELECT COUNT(*) FROM users WHERE full_name = 'Mallory'")[0][0], 0)

    def test_registration_still_accepts_a_normal_address(self):
        response = self.register(
            self.app.test_client(), role="career_adviser", full_name="Casey Careers", email="Casey.Careers@Example.test"
        )
        self.assertEqual(response.status_code, 302)
        self.assertGreater(self.user_id("casey.careers@example.test"), 0)

    # ----- changing email needs the current password (jobseeker)
    def test_jobseeker_cannot_change_email_without_the_password(self):
        response = self.seeker_profile(email="new@example.test")
        self.assertEqual(response.status_code, 200)
        self.assertIn("current password is needed", response.get_data(as_text=True))
        self.assertEqual(self.email_of(self.seeker_id), "jobseeker@example.test")

    def test_jobseeker_cannot_change_email_with_the_wrong_password(self):
        response = self.seeker_profile(email="new@example.test", current_password="not-the-password")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.email_of(self.seeker_id), "jobseeker@example.test")

    def test_jobseeker_can_change_email_with_the_right_password_and_sign_in_with_it(self):
        response = self.seeker_profile(email="New.Address@example.test", current_password=PASSWORD)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.email_of(self.seeker_id), "new.address@example.test")
        fresh = self.app.test_client()
        self.assertEqual(self.login(fresh, "new.address@example.test").status_code, 302)

    def test_jobseeker_cannot_save_a_bad_address_even_with_the_right_password(self):
        for address in ("@", ATTACK):
            with self.subTest(address=address):
                response = self.seeker_profile(email=address, current_password=PASSWORD)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.email_of(self.seeker_id), "jobseeker@example.test")

    def test_jobseeker_can_edit_name_and_phone_without_a_password_when_email_is_untouched(self):
        response = self.seeker_profile(full_name="Jamie J. Seeker", phone="07000000000")
        self.assertEqual(response.status_code, 302)
        row = self.rows("SELECT full_name, phone, email FROM users WHERE id = ?", (self.seeker_id,))[0]
        self.assertEqual(tuple(row), ("Jamie J. Seeker", "07000000000", "jobseeker@example.test"))

    def test_resending_the_same_address_in_capitals_needs_no_password(self):
        response = self.seeker_profile(email="JobSeeker@Example.Test")
        self.assertEqual(response.status_code, 302)

    def test_an_older_stored_address_that_fails_the_new_rule_does_not_lock_the_profile(self):
        self.set_email_directly(self.seeker_id, "legacy@invalid")
        response = self.seeker_profile(email="legacy@invalid", full_name="Jamie Renamed")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.rows("SELECT full_name FROM users WHERE id = ?", (self.seeker_id,))[0][0], "Jamie Renamed")
        # ...but moving to a different bad address is still refused.
        self.assertEqual(self.seeker_profile(email="other@invalid", current_password=PASSWORD).status_code, 200)

    def test_profile_of_a_deleted_account_is_not_found_rather_than_a_crash(self):
        with self.app.app_context():
            db = get_db()
            db.execute("DELETE FROM users WHERE id = ?", (self.seeker_id,))
            db.commit()
        self.assertEqual(self.seeker_profile().status_code, 404)

    # ----- changing email needs the current password (adviser)
    def test_adviser_cannot_change_email_without_or_with_the_wrong_password(self):
        for extra in ({}, {"current_password": "not-the-password"}):
            with self.subTest(extra=extra):
                response = self.adviser_profile(email="new-adviser@example.test", **extra)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.email_of(self.adviser_id), "adviser@example.test")

    def test_adviser_can_change_email_with_the_right_password(self):
        response = self.adviser_profile(email="new-adviser@example.test", current_password=PASSWORD)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.email_of(self.adviser_id), "new-adviser@example.test")

    def test_adviser_cannot_save_a_bad_address_even_with_the_right_password(self):
        for address in ("@", ATTACK):
            with self.subTest(address=address):
                response = self.adviser_profile(email=address, current_password=PASSWORD)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.email_of(self.adviser_id), "adviser@example.test")

    def test_adviser_can_edit_name_without_a_password_when_email_is_untouched(self):
        self.assertEqual(self.adviser_profile(full_name="Avery A. Adviser").status_code, 302)

    def test_both_profile_forms_show_the_password_box(self):
        self.assertIn('name="current_password"', self.seeker.get("/profile").get_data(as_text=True))
        self.assertIn('name="current_password"', self.adviser.get("/adviser/profile").get_data(as_text=True))

    # ----- the links an adviser clicks
    def test_adviser_sees_a_mailto_link_for_a_valid_address(self):
        for path in ("/adviser/dashboard", f"/adviser/jobseekers/{self.seeker_id}"):
            with self.subTest(path=path):
                html = self.adviser.get(path).get_data(as_text=True)
                self.assertIn('href="mailto:jobseeker@example.test"', html)

    def test_an_older_bad_address_is_shown_as_plain_text_and_never_becomes_a_link(self):
        self.set_email_directly(self.seeker_id, ATTACK)
        for path in ("/adviser/dashboard", f"/adviser/jobseekers/{self.seeker_id}"):
            with self.subTest(path=path):
                response = self.adviser.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertNotIn("mailto:", html)
                self.assertIn("a@b.com?bcc=x@y.test", html)  # still visible, just not clickable


if __name__ == "__main__":
    unittest.main()
