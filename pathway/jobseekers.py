"""Jobseeker dashboard, profile, adviser onboarding and account closure."""

from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from db import get_db
from security import role_required
from utils import utc_now

bp = Blueprint("jobseekers", __name__)


@bp.get("/dashboard")
@role_required("jobseeker")
def dashboard():
    db = get_db()
    user_id = session["user_id"]
    user = db.execute(
        """SELECT u.*, a.full_name AS adviser_name
           FROM users u LEFT JOIN users a ON a.id = u.assigned_adviser_id
           WHERE u.id = ? AND u.role = 'jobseeker'""",
        (user_id,),
    ).fetchone()
    if not user:
        abort(404)

    counts = {status: 0 for status in ("Applied", "Successful", "Unsuccessful", "Withdrawn")}
    rows = db.execute(
        "SELECT status, COUNT(*) AS total FROM job_applications WHERE jobseeker_id = ? GROUP BY status",
        (user_id,),
    ).fetchall()
    for row in rows:
        counts[row["status"]] = row["total"]

    current_cv = db.execute(
        "SELECT * FROM cv_versions WHERE jobseeker_id = ? AND is_current = 1",
        (user_id,),
    ).fetchone()
    recent_applications = db.execute(
        "SELECT * FROM job_applications WHERE jobseeker_id = ? ORDER BY date_applied DESC, id DESC LIMIT 5",
        (user_id,),
    ).fetchall()
    unread_count = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
        (user_id,),
    ).fetchone()[0]
    return render_template(
        "jobseeker_dashboard.html",
        user=user,
        counts=counts,
        total=sum(counts.values()),
        current_cv=current_cv,
        recent_applications=recent_applications,
        unread_count=unread_count,
    )


@bp.route("/profile", methods=["GET", "POST"])
@role_required("jobseeker")
def profile():
    db = get_db()
    user_id = session["user_id"]
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().casefold()
        phone = request.form.get("phone", "").strip()
        if not full_name or len(full_name) > 120 or not email or len(email) > 254 or "@" not in email or not phone or len(phone) > 40:
            flash("Enter a valid name, email address and phone number.", "error")
        else:
            try:
                db.execute(
                    "UPDATE users SET full_name = ?, email = ?, phone = ? WHERE id = ? AND role = 'jobseeker'",
                    (full_name, email, phone, user_id),
                )
                db.commit()
                session["full_name"] = full_name
                flash("Your profile has been updated.", "success")
                return redirect(url_for("jobseekers.profile"))
            except Exception as exc:
                db.rollback()
                if "UNIQUE constraint failed: users.email" in str(exc):
                    flash("We could not save those details. Check the email address and try again.", "error")
                else:
                    flash("We could not update your profile. Please try again.", "error")

    user = db.execute("SELECT * FROM users WHERE id = ? AND role = 'jobseeker'", (user_id,)).fetchone()
    advisers = db.execute(
        "SELECT id, full_name FROM users WHERE role = 'career_adviser' AND account_status = 'active' ORDER BY full_name COLLATE NOCASE"
    ).fetchall()
    assigned_adviser = None
    if user["assigned_adviser_id"]:
        assigned_adviser = db.execute(
            "SELECT full_name FROM users WHERE id = ? AND role = 'career_adviser'",
            (user["assigned_adviser_id"],),
        ).fetchone()
    return render_template("profile.html", user=user, advisers=advisers, assigned_adviser=assigned_adviser)


@bp.post("/jobseeker/assign-adviser")
@role_required("jobseeker")
def assign_adviser():
    db = get_db()
    user_id = session["user_id"]
    user = db.execute(
        "SELECT assigned_adviser_id, account_status FROM users WHERE id = ? AND role = 'jobseeker'",
        (user_id,),
    ).fetchone()
    if not user or user["assigned_adviser_id"] is not None:
        abort(403)
    try:
        adviser_id = int(request.form.get("assigned_adviser_id", ""))
    except (TypeError, ValueError):
        flash("Choose a valid career adviser.", "error")
        return redirect(url_for("jobseekers.profile"))
    adviser = db.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'career_adviser' AND account_status = 'active'",
        (adviser_id,),
    ).fetchone()
    if not adviser:
        flash("The selected adviser is not available. Please choose another adviser.", "error")
        return redirect(url_for("jobseekers.profile"))
    db.execute(
        "UPDATE users SET assigned_adviser_id = ?, account_status = 'active' WHERE id = ? AND role = 'jobseeker' AND assigned_adviser_id IS NULL",
        (adviser_id, user_id),
    )
    db.commit()
    flash("Your adviser has been selected. Your support is now active.", "success")
    return redirect(url_for("jobseekers.dashboard"))


@bp.post("/account/close")
@role_required("jobseeker")
def close_account():
    db = get_db()
    user_id = session["user_id"]
    password = request.form.get("password", "")
    user = db.execute("SELECT password_hash FROM users WHERE id = ? AND role = 'jobseeker'", (user_id,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Account closure could not be verified. Check your password and try again.", "error")
        return redirect(url_for("jobseekers.profile"))

    files = db.execute("SELECT stored_filename FROM cv_versions WHERE jobseeker_id = ?", (user_id,)).fetchall()
    db.execute("DELETE FROM users WHERE id = ? AND role = 'jobseeker'", (user_id,))
    db.commit()

    upload_dir = Path(current_app_upload_directory())
    for row in files:
        try:
            (upload_dir / row["stored_filename"]).unlink(missing_ok=True)
        except OSError:
            # Database deletion has succeeded; file cleanup is safely retriable by an operator.
            pass
    session.clear()
    flash("Your account and active application data have been deleted.", "success")
    return redirect(url_for("auth.login"))


def current_app_upload_directory():
    from flask import current_app
    return current_app.config["UPLOAD_FOLDER"]
