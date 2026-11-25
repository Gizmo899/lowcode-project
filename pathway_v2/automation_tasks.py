"""The scheduled automations, run every hour by tools/run_automations.py.

Every step is safe to repeat: a reminder that is already sent or skipped is never processed
again, only one reminder can be waiting per application, and the digest checks that it has not
already been created today.
"""

import sqlite3

from db import (
    create_follow_up_reminder,
    create_notification,
    delete_finished_reminders_before,
    delete_read_notifications_before,
    list_due_reminders,
    list_jobseeker_ids_with_applications,
    mark_reminder_processed,
    notification_exists,
)
from utils import REMINDER_DAYS, add_days

DIGEST_WEEKDAY = 0   # Monday
DIGEST_HOUR = 8      # 8:00 Irish time
RETENTION_DAYS = 90  # read notifications and finished reminders are removed after this long


def process_due_reminders(conn, today):
    """Send the nudges that are due. `today` is YYYY-MM-DD in Irish time."""
    sent = skipped = failed = 0
    for reminder in list_due_reminders(conn, today):
        try:
            if reminder["application_status"] == "applied":
                if mark_reminder_processed(conn, reminder["reminder_id"], "sent", today):
                    create_notification(
                        conn,
                        reminder["jobseeker_id"],
                        "nudge",
                        f"No reply yet from {reminder['company_name']} ({reminder['job_title']}). "
                        "Time to follow up?",
                        today,
                    )
                    # The nudge repeats every 7 days until the stage changes.
                    create_follow_up_reminder(
                        conn, reminder["application_id"], add_days(today, REMINDER_DAYS), today
                    )
                    sent += 1
            elif mark_reminder_processed(conn, reminder["reminder_id"], "skipped", today):
                skipped += 1
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            failed += 1
    return {"due": sent + skipped + failed, "sent": sent, "skipped": skipped, "failed": failed}


def run_weekly_digest(conn, now):
    """On Mondays from 8:00 Irish time, tell each jobseeker with applications their digest is ready.

    `now` must be a date and time in Irish time. The figures are not stored: the digest page
    works them out when the jobseeker opens it.
    """
    if now.weekday() != DIGEST_WEEKDAY or now.hour < DIGEST_HOUR:
        return {"digest_time": False, "created": 0}
    today = now.date().isoformat()
    created = 0
    for jobseeker_id in list_jobseeker_ids_with_applications(conn):
        if notification_exists(conn, jobseeker_id, "digest", today):
            continue
        create_notification(
            conn, jobseeker_id, "digest",
            "Your weekly digest is ready. Open it to see where your applications stand.", today,
        )
        created += 1
    conn.commit()
    return {"digest_time": True, "created": created}


def run_tidy_up(conn, today):
    """Remove old read notifications and finished reminders (see docs/data-protection.md)."""
    cutoff = add_days(today, -RETENTION_DAYS)
    notifications = delete_read_notifications_before(conn, cutoff)
    reminders = delete_finished_reminders_before(conn, cutoff)
    conn.commit()
    return {"notifications_removed": notifications, "reminders_removed": reminders}


def run_all(conn, now):
    """Everything the hourly script does. Returns counts only, never personal data."""
    today = now.date().isoformat()
    return {
        "reminders": process_due_reminders(conn, today),
        "digest": run_weekly_digest(conn, now),
        "tidy_up": run_tidy_up(conn, today),
    }
