"""Command-line entry point for the weekly digest and due reminder worker.

Default OS schedule: every Monday at 09:00 server-local time.
Test manually with: python run_automations.py
"""

import secrets

from app import create_app
from automation_tasks import process_due_reminders, run_weekly_digest
from db import get_db


def main():
    # This script serves no web pages and never signs a cookie, so it does not need the
    # real FLASK_SECRET_KEY. A random throwaway key lets it run from cron without it.
    app = create_app({"SECRET_KEY": secrets.token_hex(32)})
    with app.app_context():
        db = get_db()
        digest = run_weekly_digest(db)
        reminders = process_due_reminders(db)
        print(f"Weekly digest: {digest}")
        print(f"Follow-up reminders: {reminders}")


if __name__ == "__main__":
    main()
