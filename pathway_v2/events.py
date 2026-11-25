"""Events: things that happen in one place and must cause something somewhere else.

These are the event-triggered automations from docs/data-model.md. Each one runs in the same
database transaction as the change that caused it, so both happen or neither does. The caller
commits. They only use the simple functions in db.py.
"""

from db import create_follow_up_reminder, create_notification, skip_pending_reminders
from utils import REMINDER_DAYS, add_days


def application_saved(conn, application_id, date_applied, today):
    """Event: an application is saved. A follow-up reminder is planned 7 days after it was sent."""
    create_follow_up_reminder(conn, application_id, add_days(date_applied, REMINDER_DAYS), today)


def application_stage_changed(conn, application_id, old_status, new_status, today):
    """Event: an application leaves 'applied'. Its waiting reminder is cancelled for good.

    An application can never move back to 'applied', so no new reminder is needed.
    """
    if old_status == "applied" and new_status != "applied":
        skip_pending_reminders(conn, application_id, today)


def cv_decided(conn, jobseeker_id, cv_title, outcome, has_comment, today):
    """Event: an adviser approves or rejects a CV. The jobseeker gets a notification.

    The message names the CV and the outcome. It never copies the adviser's comment: the
    comment stays on the CV only (docs/data-protection.md).
    """
    message = f"Your CV \u201c{cv_title}\u201d was {outcome}."
    if outcome == "rejected" and has_comment:
        message += " Open My CV to read your adviser's comment."
    create_notification(conn, jobseeker_id, "cv_decision", message, today)
