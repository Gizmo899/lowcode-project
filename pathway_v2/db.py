"""All database access for the Job Application Tracker.

Rules (see AGENTS.md):
- Every part of the app opens the database through get_connection(), so every connection
  runs PRAGMA foreign_keys = ON.
- Every value goes into SQL through a ? placeholder. SQL is never built from strings.
- A function that looks something up returns None when nothing is found. The route turns
  that into a 404 page.
- The tables are created by tools/migrate.py from the files in schema/. Nothing here
  creates or changes a table.
"""

import os
import sqlite3
from pathlib import Path

from flask import current_app, g, has_app_context

from utils import APPLICATION_STATUSES

DEFAULT_DATABASE = str(Path(__file__).resolve().parent / "app.db")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _open(path):
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row            # rows can be read by column name
    connection.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys without this
    connection.execute("PRAGMA busy_timeout = 5000")  # wait up to 5 s if the script and the app collide
    return connection


def get_connection(path=None):
    """Return a database connection with foreign keys switched on.

    - With a path: a new connection to that file. The caller closes it.
    - Inside a web request or app context: one connection per request, closed automatically.
    - Otherwise: a new connection to DATABASE_PATH (default app.db). The caller closes it.
    """
    if path is not None:
        return _open(path)
    if has_app_context():
        if "db" not in g:
            g.db = _open(current_app.config["DATABASE"])
        return g.db
    return _open(os.environ.get("DATABASE_PATH", DEFAULT_DATABASE))


def close_connection(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_app(app):
    app.teardown_appcontext(close_connection)


# ---------------------------------------------------------------------------
# Friendly messages for rejected data
# ---------------------------------------------------------------------------

DEFAULT_REJECTION = "Some of those details are not allowed. Please check the form and try again."

# (text to look for in the database error, message to show the person)
_FRIENDLY_MESSAGES = (
    ("user.email", "That email address is already in use."),
    ("user.phone", "That phone number is already in use."),
    ("A role can never be changed", "An account's role can never be changed."),
    ("assigned adviser must be a user with the role adviser", "Choose one of the listed career advisers."),
    ("adviser choice cannot be switched", "Your adviser has already been chosen and cannot be switched."),
    ("A CV must belong to a jobseeker", "Only jobseekers can have CVs."),
    ("A new CV must start as waiting_for_review", "A new CV always starts as waiting for review."),
    ("Only the adviser assigned to the CV owner", "Only the jobseeker's own adviser can decide this CV."),
    ("A decision must be recorded by the adviser", "Only the jobseeker's own adviser can decide this CV."),
    ("A job application must belong to a jobseeker", "Only jobseekers can have job applications."),
    ("A new job application must start as applied", "A new application always starts as applied."),
    ("A notification must belong to a jobseeker", "Only jobseekers can have notifications."),
    ("follow_up_reminder.application_id", "That application already has a reminder waiting."),
)


def friendly_error_message(error):
    """Turn a database rejection (sqlite3.IntegrityError) into a short message for the form.

    The raw error text is never shown to people: it can contain internal rule text.
    """
    text = str(error)
    for fragment, message in _FRIENDLY_MESSAGES:
        if fragment in text:
            return message
    return DEFAULT_REJECTION


# ---------------------------------------------------------------------------
# user
# ---------------------------------------------------------------------------

def create_user(conn, full_name, email, password_hash, phone, role, assigned_adviser_id=None):
    cursor = conn.execute(
        "INSERT INTO user (full_name, email, password_hash, phone, role, assigned_adviser_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (full_name, email, password_hash, phone, role, assigned_adviser_id),
    )
    return cursor.lastrowid


def get_user(conn, user_id):
    return conn.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()


def get_user_by_email(conn, email):
    return conn.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()


def list_users(conn, role=None):
    if role is None:
        return conn.execute("SELECT * FROM user ORDER BY id").fetchall()
    return conn.execute("SELECT * FROM user WHERE role = ? ORDER BY id", (role,)).fetchall()


def list_advisers(conn):
    """Names only: what a jobseeker needs to choose an adviser."""
    return conn.execute(
        "SELECT id, full_name FROM user WHERE role = 'adviser' ORDER BY full_name COLLATE NOCASE"
    ).fetchall()


def get_jobseeker_with_adviser(conn, jobseeker_id):
    return conn.execute(
        "SELECT u.*, a.full_name AS adviser_name "
        "FROM user u LEFT JOIN user a ON a.id = u.assigned_adviser_id "
        "WHERE u.id = ? AND u.role = 'jobseeker'",
        (jobseeker_id,),
    ).fetchone()


def list_jobseekers_of_adviser(conn, adviser_id):
    """The adviser's own jobseekers. No phone number: advisers never see it."""
    return conn.execute(
        "SELECT u.id, u.full_name, u.email, "
        "  (SELECT COUNT(*) FROM job_application a WHERE a.jobseeker_id = u.id) AS application_count, "
        "  (SELECT COUNT(*) FROM cv WHERE cv.jobseeker_id = u.id) AS cv_count, "
        "  (SELECT COUNT(*) FROM cv WHERE cv.jobseeker_id = u.id AND cv.status = 'waiting_for_review') AS waiting_count "
        "FROM user u WHERE u.role = 'jobseeker' AND u.assigned_adviser_id = ? "
        "ORDER BY u.full_name COLLATE NOCASE",
        (adviser_id,),
    ).fetchall()


def get_jobseeker_of_adviser(conn, jobseeker_id, adviser_id):
    """One jobseeker, but only if they are linked to this adviser. No phone number."""
    return conn.execute(
        "SELECT id, full_name, email FROM user "
        "WHERE id = ? AND role = 'jobseeker' AND assigned_adviser_id = ?",
        (jobseeker_id, adviser_id),
    ).fetchone()


def list_jobseeker_ids_with_applications(conn):
    rows = conn.execute(
        "SELECT u.id FROM user u WHERE u.role = 'jobseeker' "
        "AND EXISTS (SELECT 1 FROM job_application a WHERE a.jobseeker_id = u.id) ORDER BY u.id"
    ).fetchall()
    return [row["id"] for row in rows]


def update_user_profile(conn, user_id, full_name, email, phone):
    cursor = conn.execute(
        "UPDATE user SET full_name = ?, email = ?, phone = ? WHERE id = ?",
        (full_name, email, phone, user_id),
    )
    return cursor.rowcount


def set_assigned_adviser(conn, jobseeker_id, adviser_id):
    """A jobseeker chooses an adviser. Only works while they have none."""
    cursor = conn.execute(
        "UPDATE user SET assigned_adviser_id = ? "
        "WHERE id = ? AND role = 'jobseeker' AND assigned_adviser_id IS NULL",
        (adviser_id, jobseeker_id),
    )
    return cursor.rowcount


def delete_user(conn, user_id):
    cursor = conn.execute("DELETE FROM user WHERE id = ?", (user_id,))
    return cursor.rowcount


# ---------------------------------------------------------------------------
# cv  (the file lives inside the database)
# ---------------------------------------------------------------------------

def create_cv(conn, jobseeker_id, title, file_name, file_type, file_data, uploaded_at):
    cursor = conn.execute(
        "INSERT INTO cv (jobseeker_id, title, file_name, file_type, file_data, uploaded_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (jobseeker_id, title, file_name, file_type, file_data, uploaded_at),
    )
    return cursor.lastrowid


def get_cv_for_jobseeker(conn, cv_id, jobseeker_id, with_file=False):
    """One of this jobseeker's own CVs, or None."""
    if with_file:
        return conn.execute(
            "SELECT * FROM cv WHERE id = ? AND jobseeker_id = ?", (cv_id, jobseeker_id)
        ).fetchone()
    return conn.execute(
        "SELECT id, jobseeker_id, title, file_name, file_type, length(file_data) AS size_bytes, "
        "uploaded_at, status, decided_by, decided_at, comment "
        "FROM cv WHERE id = ? AND jobseeker_id = ?",
        (cv_id, jobseeker_id),
    ).fetchone()


def get_cv_for_adviser(conn, cv_id, adviser_id, with_file=False):
    """A CV, but only if its owner is linked to this adviser."""
    if with_file:
        return conn.execute(
            "SELECT cv.* FROM cv JOIN user j ON j.id = cv.jobseeker_id "
            "WHERE cv.id = ? AND j.role = 'jobseeker' AND j.assigned_adviser_id = ?",
            (cv_id, adviser_id),
        ).fetchone()
    return conn.execute(
        "SELECT cv.id, cv.jobseeker_id, cv.title, cv.file_name, cv.file_type, "
        "length(cv.file_data) AS size_bytes, cv.uploaded_at, cv.status, cv.decided_by, "
        "cv.decided_at, cv.comment "
        "FROM cv JOIN user j ON j.id = cv.jobseeker_id "
        "WHERE cv.id = ? AND j.role = 'jobseeker' AND j.assigned_adviser_id = ?",
        (cv_id, adviser_id),
    ).fetchone()


def list_cvs_for_jobseeker(conn, jobseeker_id):
    """CV details without the file itself (files are large)."""
    return conn.execute(
        "SELECT cv.id, cv.jobseeker_id, cv.title, cv.file_name, cv.file_type, "
        "length(cv.file_data) AS size_bytes, cv.uploaded_at, cv.status, cv.decided_by, "
        "cv.decided_at, cv.comment, d.full_name AS decided_by_name "
        "FROM cv LEFT JOIN user d ON d.id = cv.decided_by "
        "WHERE cv.jobseeker_id = ? ORDER BY cv.uploaded_at DESC, cv.id DESC",
        (jobseeker_id,),
    ).fetchall()


def update_cv_title(conn, cv_id, jobseeker_id, title):
    cursor = conn.execute(
        "UPDATE cv SET title = ? WHERE id = ? AND jobseeker_id = ?", (title, cv_id, jobseeker_id)
    )
    return cursor.rowcount


def replace_cv_file(conn, cv_id, jobseeker_id, file_name, file_type, file_data, uploaded_at):
    """A new file means a new review: the decision, the adviser and the comment are emptied."""
    cursor = conn.execute(
        "UPDATE cv SET file_name = ?, file_type = ?, file_data = ?, uploaded_at = ?, "
        "status = 'waiting_for_review', decided_by = NULL, decided_at = NULL, comment = NULL "
        "WHERE id = ? AND jobseeker_id = ?",
        (file_name, file_type, file_data, uploaded_at, cv_id, jobseeker_id),
    )
    return cursor.rowcount


def decide_cv(conn, cv_id, status, adviser_id, decided_at, comment):
    """Record an approval or rejection. Only works on a CV that is still waiting."""
    cursor = conn.execute(
        "UPDATE cv SET status = ?, decided_by = ?, decided_at = ?, comment = ? "
        "WHERE id = ? AND status = 'waiting_for_review'",
        (status, adviser_id, decided_at, comment, cv_id),
    )
    return cursor.rowcount


def delete_cv(conn, cv_id, jobseeker_id):
    cursor = conn.execute("DELETE FROM cv WHERE id = ? AND jobseeker_id = ?", (cv_id, jobseeker_id))
    return cursor.rowcount


# ---------------------------------------------------------------------------
# job_application
# ---------------------------------------------------------------------------

def create_job_application(conn, jobseeker_id, company_name, job_title, date_applied, advert_url, notes):
    cursor = conn.execute(
        "INSERT INTO job_application (jobseeker_id, company_name, job_title, date_applied, advert_url, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (jobseeker_id, company_name, job_title, date_applied, advert_url, notes),
    )
    return cursor.lastrowid


def get_job_application(conn, application_id, jobseeker_id):
    """One of this jobseeker's own applications, or None."""
    return conn.execute(
        "SELECT * FROM job_application WHERE id = ? AND jobseeker_id = ?",
        (application_id, jobseeker_id),
    ).fetchone()


def list_job_applications(conn, jobseeker_id):
    return conn.execute(
        "SELECT * FROM job_application WHERE jobseeker_id = ? ORDER BY date_applied DESC, id DESC",
        (jobseeker_id,),
    ).fetchall()


def count_job_applications_by_status(conn, jobseeker_id):
    counts = {status: 0 for status in APPLICATION_STATUSES}
    rows = conn.execute(
        "SELECT status, COUNT(*) AS total FROM job_application WHERE jobseeker_id = ? GROUP BY status",
        (jobseeker_id,),
    ).fetchall()
    for row in rows:
        counts[row["status"]] = row["total"]
    return counts


def update_job_application(conn, application_id, jobseeker_id, company_name, job_title,
                           date_applied, status, advert_url, notes):
    cursor = conn.execute(
        "UPDATE job_application SET company_name = ?, job_title = ?, date_applied = ?, "
        "status = ?, advert_url = ?, notes = ? WHERE id = ? AND jobseeker_id = ?",
        (company_name, job_title, date_applied, status, advert_url, notes, application_id, jobseeker_id),
    )
    return cursor.rowcount


def delete_job_application(conn, application_id, jobseeker_id):
    cursor = conn.execute(
        "DELETE FROM job_application WHERE id = ? AND jobseeker_id = ?", (application_id, jobseeker_id)
    )
    return cursor.rowcount


# ---------------------------------------------------------------------------
# follow_up_reminder
# ---------------------------------------------------------------------------

def create_follow_up_reminder(conn, application_id, due_on, created_on):
    cursor = conn.execute(
        "INSERT INTO follow_up_reminder (application_id, due_on, created_on) VALUES (?, ?, ?)",
        (application_id, due_on, created_on),
    )
    return cursor.lastrowid


def get_follow_up_reminder(conn, reminder_id):
    return conn.execute("SELECT * FROM follow_up_reminder WHERE id = ?", (reminder_id,)).fetchone()


def list_follow_up_reminders(conn, application_id):
    return conn.execute(
        "SELECT * FROM follow_up_reminder WHERE application_id = ? ORDER BY id", (application_id,)
    ).fetchall()


def list_due_reminders(conn, today):
    """Waiting reminders whose due date has come, with what the nudge message needs."""
    return conn.execute(
        "SELECT r.id AS reminder_id, r.application_id, a.jobseeker_id, a.company_name, "
        "a.job_title, a.status AS application_status "
        "FROM follow_up_reminder r JOIN job_application a ON a.id = r.application_id "
        "WHERE r.status = 'pending' AND r.due_on <= ? ORDER BY r.due_on, r.id",
        (today,),
    ).fetchall()


def mark_reminder_processed(conn, reminder_id, status, processed_on):
    """Mark a waiting reminder as sent or skipped. A finished reminder is never changed again."""
    cursor = conn.execute(
        "UPDATE follow_up_reminder SET status = ?, processed_on = ? WHERE id = ? AND status = 'pending'",
        (status, processed_on, reminder_id),
    )
    return cursor.rowcount


def skip_pending_reminders(conn, application_id, processed_on):
    cursor = conn.execute(
        "UPDATE follow_up_reminder SET status = 'skipped', processed_on = ? "
        "WHERE application_id = ? AND status = 'pending'",
        (processed_on, application_id),
    )
    return cursor.rowcount


def delete_follow_up_reminder(conn, reminder_id):
    cursor = conn.execute("DELETE FROM follow_up_reminder WHERE id = ?", (reminder_id,))
    return cursor.rowcount


def delete_finished_reminders_before(conn, cutoff_date):
    cursor = conn.execute(
        "DELETE FROM follow_up_reminder WHERE status IN ('sent', 'skipped') AND processed_on < ?",
        (cutoff_date,),
    )
    return cursor.rowcount


# ---------------------------------------------------------------------------
# notification
# ---------------------------------------------------------------------------

def create_notification(conn, user_id, kind, message, created_at):
    cursor = conn.execute(
        "INSERT INTO notification (user_id, kind, message, created_at) VALUES (?, ?, ?, ?)",
        (user_id, kind, message, created_at),
    )
    return cursor.lastrowid


def get_notification(conn, notification_id, user_id):
    return conn.execute(
        "SELECT * FROM notification WHERE id = ? AND user_id = ?", (notification_id, user_id)
    ).fetchone()


def list_notifications(conn, user_id):
    return conn.execute(
        "SELECT * FROM notification WHERE user_id = ? ORDER BY created_at DESC, id DESC", (user_id,)
    ).fetchall()


def count_unread_notifications(conn, user_id):
    return conn.execute(
        "SELECT COUNT(*) FROM notification WHERE user_id = ? AND is_read = 0", (user_id,)
    ).fetchone()[0]


def mark_notification_read(conn, notification_id, user_id):
    cursor = conn.execute(
        "UPDATE notification SET is_read = 1 WHERE id = ? AND user_id = ?", (notification_id, user_id)
    )
    return cursor.rowcount


def notification_exists(conn, user_id, kind, created_at):
    row = conn.execute(
        "SELECT 1 FROM notification WHERE user_id = ? AND kind = ? AND created_at = ?",
        (user_id, kind, created_at),
    ).fetchone()
    return row is not None


def delete_notification(conn, notification_id, user_id):
    cursor = conn.execute(
        "DELETE FROM notification WHERE id = ? AND user_id = ?", (notification_id, user_id)
    )
    return cursor.rowcount


def delete_read_notifications_before(conn, cutoff_date):
    cursor = conn.execute(
        "DELETE FROM notification WHERE is_read = 1 AND created_at < ?", (cutoff_date,)
    )
    return cursor.rowcount
