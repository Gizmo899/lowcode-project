"""Jobseeker-owned job application CRUD routes."""

from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from db import get_db
from security import role_required
from utils import APPLICATION_STATUSES, valid_http_url, utc_now

bp = Blueprint("applications", __name__, url_prefix="/applications")


def _form_values():
    return {
        "employer_name": request.form.get("employer_name", "").strip(),
        "job_title": request.form.get("job_title", "").strip(),
        "date_applied": request.form.get("date_applied", "").strip(),
        "job_url": request.form.get("job_url", "").strip(),
        "status": request.form.get("status", "Applied").strip(),
    }


def _validate(values):
    errors = []
    if not values["employer_name"] or len(values["employer_name"]) > 160:
        errors.append("Enter an employer name (up to 160 characters).")
    if not values["job_title"] or len(values["job_title"]) > 160:
        errors.append("Enter a job title (up to 160 characters).")
    try:
        date.fromisoformat(values["date_applied"])
    except ValueError:
        errors.append("Enter a valid date applied.")
    if not valid_http_url(values["job_url"]) or len(values["job_url"]) > 2048:
        errors.append("Enter a valid HTTP or HTTPS job advert URL.")
    if values["status"] not in APPLICATION_STATUSES:
        errors.append("Choose one of the permitted application statuses.")
    return errors


def _create_reminder(db, application_id):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    created_at = now.isoformat().replace("+00:00", "Z")
    due_at = (now + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    db.execute(
        "INSERT INTO follow_up_reminders (application_id, due_at, status, created_at) VALUES (?, ?, 'pending', ?)",
        (application_id, due_at, created_at),
    )


@bp.get("")
@role_required("jobseeker")
def listing():
    db = get_db()
    applications = db.execute(
        "SELECT * FROM job_applications WHERE jobseeker_id = ? ORDER BY date_applied DESC, id DESC",
        (session["user_id"],),
    ).fetchall()
    counts = {status: 0 for status in APPLICATION_STATUSES}
    for row in db.execute(
        "SELECT status, COUNT(*) AS total FROM job_applications WHERE jobseeker_id = ? GROUP BY status",
        (session["user_id"],),
    ).fetchall():
        counts[row["status"]] = row["total"]
    return render_template("applications.html", applications=applications, counts=counts, total=sum(counts.values()))


@bp.route("/new", methods=["GET", "POST"])
@role_required("jobseeker")
def create():
    values = {"employer_name": "", "job_title": "", "date_applied": date.today().isoformat(), "job_url": "", "status": "Applied"}
    if request.method == "POST":
        values = _form_values()
        errors = _validate(values)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            now = utc_now()
            db = get_db()
            cursor = db.execute(
                """INSERT INTO job_applications
                   (jobseeker_id, employer_name, job_title, date_applied, job_url, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session["user_id"], values["employer_name"], values["job_title"], values["date_applied"], values["job_url"], values["status"], now, now),
            )
            application_id = cursor.lastrowid
            if values["status"] == "Applied":
                _create_reminder(db, application_id)
            db.commit()
            flash("Your job application has been saved.", "success")
            return redirect(url_for("applications.listing"))
    return render_template("application_form.html", values=values, statuses=APPLICATION_STATUSES, heading="Add an application")


@bp.route("/<int:application_id>/edit", methods=["GET", "POST"])
@role_required("jobseeker")
def edit(application_id):
    db = get_db()
    application = db.execute(
        "SELECT * FROM job_applications WHERE id = ? AND jobseeker_id = ?",
        (application_id, session["user_id"]),
    ).fetchone()
    if not application:
        abort(404)
    values = dict(application)
    if request.method == "POST":
        values = _form_values()
        errors = _validate(values)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            now = utc_now()
            old_status = application["status"]
            db.execute(
                """UPDATE job_applications
                   SET employer_name = ?, job_title = ?, date_applied = ?, job_url = ?, status = ?, updated_at = ?
                   WHERE id = ? AND jobseeker_id = ?""",
                (values["employer_name"], values["job_title"], values["date_applied"], values["job_url"], values["status"], now, application_id, session["user_id"]),
            )
            if old_status != values["status"]:
                # A status transition invalidates outstanding reminders. Returning to Applied starts a fresh 7-day period.
                db.execute(
                    "UPDATE follow_up_reminders SET status = 'skipped', processed_at = ? WHERE application_id = ? AND status = 'pending'",
                    (now, application_id),
                )
                if values["status"] == "Applied":
                    _create_reminder(db, application_id)
            db.commit()
            flash("Your application has been updated.", "success")
            return redirect(url_for("applications.listing"))
    return render_template("application_form.html", values=values, statuses=APPLICATION_STATUSES, heading="Edit application")


@bp.post("/<int:application_id>/delete")
@role_required("jobseeker")
def delete(application_id):
    db = get_db()
    cursor = db.execute(
        "DELETE FROM job_applications WHERE id = ? AND jobseeker_id = ?",
        (application_id, session["user_id"]),
    )
    db.commit()
    if cursor.rowcount == 0:
        abort(404)
    flash("The application has been deleted.", "success")
    return redirect(url_for("applications.listing"))
