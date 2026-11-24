"""Jobseeker dashboard, weekly digest, profile, adviser choice and account closure."""

import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from db import (
    count_job_applications_by_status,
    count_unread_notifications,
    delete_user,
    friendly_error_message,
    get_connection,
    get_jobseeker_with_adviser,
    get_user,
    list_advisers,
    list_cvs_for_jobseeker,
    list_job_applications,
    set_assigned_adviser,
    update_user_profile,
)
from security import role_required
from utils import valid_email

bp = Blueprint("jobseekers", __name__)


@bp.get("/dashboard")
@role_required("jobseeker")
def dashboard():
    conn = get_connection()
    user_id = session["user_id"]
    user = get_jobseeker_with_adviser(conn, user_id)
    if not user:
        abort(404)
    counts = count_job_applications_by_status(conn, user_id)
    cvs = list_cvs_for_jobseeker(conn, user_id)
    return render_template(
        "jobseeker_dashboard.html",
        user=user,
        counts=counts,
        total=sum(counts.values()),
        cvs=cvs,
        waiting_cvs=sum(1 for cv in cvs if cv["status"] == "waiting_for_review"),
        recent_applications=list_job_applications(conn, user_id)[:5],
        unread_count=count_unread_notifications(conn, user_id),
    )


@bp.get("/digest")
@role_required("jobseeker")
def digest():
    """The weekly digest. The figures are worked out now, from the stored applications."""
    conn = get_connection()
    counts = count_job_applications_by_status(conn, session["user_id"])
    waiting = [a for a in list_job_applications(conn, session["user_id"]) if a["status"] == "applied"]
    return render_template("digest.html", counts=counts, total=sum(counts.values()), waiting=waiting)


@bp.route("/profile", methods=["GET", "POST"])
@role_required("jobseeker")
def profile():
    conn = get_connection()
    user_id = session["user_id"]
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().casefold()
        phone = request.form.get("phone", "").strip()
        current = get_user(conn, user_id)
        if not current or current["role"] != "jobseeker":
            abort(404)
        # Saving the address you already have never needs a password. Changing it needs a valid
        # new address and the current password (the email is the sign-in name for the account).
        email_changed = email != current["email"].casefold()
        if not full_name or len(full_name) > 120 or len(phone) > 40 or (email_changed and not valid_email(email)):
            flash("Enter a valid name and email address. A phone number is optional (up to 40 characters).", "error")
        elif email_changed and not check_password_hash(current["password_hash"], request.form.get("current_password", "")):
            flash("Your current password is needed to change your email address. Check it and try again.", "error")
        else:
            try:
                update_user_profile(conn, user_id, full_name, email, phone or None)
                conn.commit()
            except sqlite3.IntegrityError as error:
                conn.rollback()
                flash(friendly_error_message(error), "error")
            else:
                session["full_name"] = full_name
                flash("Your profile has been updated.", "success")
                return redirect(url_for("jobseekers.profile"))

    user = get_jobseeker_with_adviser(conn, user_id)
    if not user:
        abort(404)
    return render_template("profile.html", user=user, advisers=list_advisers(conn))


@bp.post("/jobseeker/assign-adviser")
@role_required("jobseeker")
def assign_adviser():
    conn = get_connection()
    user = get_user(conn, session["user_id"])
    if not user or user["role"] != "jobseeker":
        abort(404)
    if user["assigned_adviser_id"] is not None:
        abort(403)  # the choice is made once
    try:
        adviser_id = int(request.form.get("assigned_adviser_id", ""))
    except (TypeError, ValueError):
        flash("Choose a valid career adviser.", "error")
        return redirect(url_for("jobseekers.profile"))
    adviser = get_user(conn, adviser_id)
    if not adviser or adviser["role"] != "adviser":
        flash("The selected adviser is not available. Please choose another adviser.", "error")
        return redirect(url_for("jobseekers.profile"))
    try:
        set_assigned_adviser(conn, user["id"], adviser_id)
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        flash(friendly_error_message(error), "error")
        return redirect(url_for("jobseekers.profile"))
    flash("Your adviser has been chosen. Your support is now active.", "success")
    return redirect(url_for("jobseekers.dashboard"))


@bp.post("/account/close")
@role_required("jobseeker")
def close_account():
    conn = get_connection()
    user = get_user(conn, session["user_id"])
    if not user or user["role"] != "jobseeker" or not check_password_hash(
        user["password_hash"], request.form.get("password", "")
    ):
        flash("Account closure could not be verified. Check your password and try again.", "error")
        return redirect(url_for("jobseekers.profile"))
    delete_user(conn, user["id"])  # CVs, applications, reminders and notifications go with it
    conn.commit()
    session.clear()
    flash("Your account and all of your data have been deleted.", "success")
    return redirect(url_for("auth.login"))
