"""Tests for how the app treats its session secret (FLASK_SECRET_KEY)."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flask import Flask

from tools.migrate import apply_migrations
from flask.sessions import SecureCookieSessionInterface

import app as app_module
from app import ConfigError, create_app

GOOD_KEY = "0123456789abcdef" * 4  # 64 characters
OTHER_GOOD_KEY = "fedcba9876543210" * 4
OLD_HARD_CODED_DEFAULT = "dev-only-change-this-secret-before-deployment"
OLD_DOCS_PLACEHOLDER = "replace-with-a-long-random-secret"


class SecretKeyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.env_file = root / ".env"  # only exists if a test writes it
        self.config = {"DATABASE": str(root / "t.sqlite")}
        apply_migrations(self.config["DATABASE"])  # the control check opens the adviser page, which reads the database

        # Every test starts with no secret in the environment, and the real environment is
        # put back afterwards (python-dotenv writes into os.environ).
        env_patch = mock.patch.dict(os.environ, {}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        os.environ.pop("FLASK_SECRET_KEY", None)
        # Never read a real .env from the project folder while testing.
        file_patch = mock.patch.object(app_module, "ENV_FILE", self.env_file)
        file_patch.start()
        self.addCleanup(file_patch.stop)

    def test_refuses_to_start_without_a_key(self):
        with self.assertRaises(ConfigError) as caught:
            create_app(self.config)
        self.assertIn("FLASK_SECRET_KEY is not set", str(caught.exception))

    def test_blank_key_is_treated_as_missing(self):
        os.environ["FLASK_SECRET_KEY"] = "   "
        with self.assertRaises(ConfigError):
            create_app(self.config)

    def test_refuses_the_old_hard_coded_default(self):
        os.environ["FLASK_SECRET_KEY"] = OLD_HARD_CODED_DEFAULT
        with self.assertRaises(ConfigError):
            create_app(self.config)

    def test_refuses_the_placeholder_from_the_old_docs(self):
        os.environ["FLASK_SECRET_KEY"] = OLD_DOCS_PLACEHOLDER
        with self.assertRaises(ConfigError):
            create_app(self.config)

    def test_refuses_a_short_key_and_accepts_the_minimum_length(self):
        os.environ["FLASK_SECRET_KEY"] = "a" * 31
        with self.assertRaises(ConfigError):
            create_app(self.config)
        os.environ["FLASK_SECRET_KEY"] = "a" * 32
        self.assertEqual(create_app(self.config).config["SECRET_KEY"], "a" * 32)

    def test_uses_the_key_from_the_environment(self):
        os.environ["FLASK_SECRET_KEY"] = GOOD_KEY
        self.assertEqual(create_app(self.config).config["SECRET_KEY"], GOOD_KEY)

    def test_reads_the_key_from_a_dotenv_file(self):
        self.env_file.write_text(f"FLASK_SECRET_KEY={GOOD_KEY}\n", encoding="utf-8")
        self.assertEqual(create_app(self.config).config["SECRET_KEY"], GOOD_KEY)

    def test_environment_variable_wins_over_the_dotenv_file(self):
        self.env_file.write_text(f"FLASK_SECRET_KEY={GOOD_KEY}\n", encoding="utf-8")
        os.environ["FLASK_SECRET_KEY"] = OTHER_GOOD_KEY
        self.assertEqual(create_app(self.config).config["SECRET_KEY"], OTHER_GOOD_KEY)

    def test_the_example_env_file_does_not_start_the_app_unedited(self):
        example = Path(app_module.__file__).with_name(".env.example").read_text(encoding="utf-8")
        self.env_file.write_text(example, encoding="utf-8")
        with self.assertRaises(ConfigError):
            create_app(self.config)

    def test_cookie_forged_with_the_old_public_key_is_rejected(self):
        forger = Flask("forger")
        forger.secret_key = OLD_HARD_CODED_DEFAULT
        serializer = SecureCookieSessionInterface().get_signing_serializer(forger)
        forged = serializer.dumps({"user_id": 1, "role": "adviser", "full_name": "x"})

        # Control: an app that really does use the old key accepts the forgery, so this
        # test would notice if the forging technique stopped working.
        weak = create_app({**self.config, "SECRET_KEY": OLD_HARD_CODED_DEFAULT})
        weak_client = weak.test_client()
        weak_client.set_cookie("session", forged)
        self.assertEqual(weak_client.get("/adviser/dashboard").status_code, 200)

        os.environ["FLASK_SECRET_KEY"] = GOOD_KEY
        client = create_app(self.config).test_client()
        client.set_cookie("session", forged)
        response = client.get("/adviser/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_importing_app_does_not_build_an_app(self):
        self.assertFalse(hasattr(app_module, "app"))

    def test_automation_script_runs_without_the_web_secret(self):
        from tools import run_automations
        from tools.migrate import apply_migrations

        apply_migrations(self.config["DATABASE"])
        os.environ["DATABASE_PATH"] = self.config["DATABASE"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = run_automations.main(["run_automations.py"])
        self.assertEqual(exit_code, 0)
        for part in ("reminders", "digest", "tidy_up"):
            self.assertIn(part, output.getvalue())


if __name__ == "__main__":
    unittest.main()
