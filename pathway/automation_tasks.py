"""Idempotent scheduled digest and seven-day follow-up automation tasks."""

from datetime import datetime, timedelta, timezone
import json

from utils import normalise_timestamp, utc_now


def run_weekly_digest(db, now=None):
    """Create one current-pipeline digest per active jobseeker and ISO week."""
    now = now or datetime.now().astimezone()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local_date = now.date()
    week_start = local_date - timedelta(days=local_date.weekday())
    iso_year, iso_week, _ = local_date.isocalendar()
    run_key = f"weekly_digest:{iso_year}-W{iso_week:02d}"
    started_at = utc_now()
    db.execute(
        "INSERT OR IGNORE INTO automation_runs (run_key, task_name, started_at) VALUES (?, 'weekly_digest', ?)",
        (run_key, started_at),
    )
    created = 0
    jobseekers = db.execute(
        "SELECT id FROM users WHERE role = 'jobseeker' AND account_status = 'active' ORDER BY id"
    ).fetchall()
    report_label = f"Week commencing {week_start.isoformat()}"
    for user in jobseekers:
        counts = {"Applied": 0, "Successful": 0, "Unsuccessful": 0, "Withdrawn": 0}
        rows = db.execute(
            "SELECT status, COUNT(*) AS total FROM job_applications WHERE jobseeker_id = ? GROUP BY status",
            (user["id"],),
        ).fetchall()
        for row in rows:
            counts[row["status"]] = row["total"]
        total = sum(counts.values())
        message = (
            f"{report_label} — your current pipeline snapshot: {total} total applications. "
            f"Applied: {counts['Applied']}; Successful: {counts['Successful']}; "
            f"Unsuccessful: {counts['Unsuccessful']}; Withdrawn: {counts['Withdrawn']}."
        )
        dedupe = f"weekly_digest:{user['id']}:{iso_year}-W{iso_week:02d}"
        cursor = db.execute(
            """INSERT OR IGNORE INTO notifications
               (user_id, notification_type, title, message, created_at, deduplication_key)
               VALUES (?, 'weekly_digest', ?, ?, ?, ?)""",
            (user["id"], f"Weekly job pipeline — {report_label}", message, started_at, dedupe),
        )
        created += cursor.rowcount
    finished_at = utc_now()
    summary = json.dumps({"recipients": len(jobseekers), "notifications_created": created, "reporting_week": report_label})
    db.execute(
        "UPDATE automation_runs SET finished_at = ?, result_summary = ? WHERE run_key = ?",
        (finished_at, summary, run_key),
    )
    db.commit()
    return {"recipients": len(jobseekers), "created": created, "reporting_week": report_label, "run_key": run_key}


def process_due_reminders(db, now=None):
    """Send due nudges for still-Applied applications; skip changed outcomes."""
    now = now or datetime.now(timezone.utc)
    now_utc = normalise_timestamp(now)
    due = db.execute(
        """SELECT r.id AS reminder_id, r.application_id, a.jobseeker_id, a.employer_name,
                  a.job_title, a.status
           FROM follow_up_reminders r
           JOIN job_applications a ON a.id = r.application_id
           WHERE r.status = 'pending' AND r.due_at <= ?
           ORDER BY r.due_at, r.id""",
        (now_utc,),
    ).fetchall()
    sent = 0
    skipped = 0
    for reminder in due:
        if reminder["status"] == "Applied":
            dedupe = f"follow_up:{reminder['reminder_id']}"
            cursor = db.execute(
                """INSERT OR IGNORE INTO notifications
                   (user_id, notification_type, title, message, related_application_id, created_at, deduplication_key)
                   VALUES (?, 'follow_up', ?, ?, ?, ?, ?)""",
                (
                    reminder["jobseeker_id"],
                    "Time to follow up on an application",
                    f"Your application to {reminder['employer_name']} for {reminder['job_title']} is still marked Applied. Consider following up with the employer.",
                    reminder["application_id"],
                    now_utc,
                    dedupe,
                ),
            )
            db.execute(
                "UPDATE follow_up_reminders SET status = 'sent', processed_at = ? WHERE id = ? AND status = 'pending'",
                (now_utc, reminder["reminder_id"]),
            )
            sent += cursor.rowcount
        else:
            db.execute(
                "UPDATE follow_up_reminders SET status = 'skipped', processed_at = ? WHERE id = ? AND status = 'pending'",
                (now_utc, reminder["reminder_id"]),
            )
            skipped += 1
    run_key = f"follow_up:{now_utc}"
    db.execute(
        "INSERT OR IGNORE INTO automation_runs (run_key, task_name, started_at, finished_at, result_summary) VALUES (?, 'follow_up_reminders', ?, ?, ?)",
        (run_key, now_utc, now_utc, json.dumps({"due": len(due), "sent": sent, "skipped": skipped})),
    )
    db.commit()
    return {"due": len(due), "sent": sent, "skipped": skipped}
