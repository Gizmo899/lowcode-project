"""Career adviser workspace and the human CV approval step."""

import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

import events
from db import (
    decide_cv,
    delete_user,
    friendly_error_message,
    get_connection,
    get_cv_for_adviser,
    get_jobseeker_of_adviser,
    get_user,
    list_cvs_for_jobseeker,
    list_job_applications,
    list_jobseekers_of_adviser,
    update_user_profile,
)
from security import role_required
from utils import CV_DECISIONS, irish_today, valid_email

bp = Blueprint("advisers", __name__, url_prefix="/adviser")


@bp.get("/dashboard")
@role_required("adviser")
def dashboard():
    jobseekers = list_jobseekers_of_adviser(get_connection(), session["user_id"])
    return render_template("adviser_dashboard.html", jobseekers=jobseekers)


@bp.get("/jobseekers/<int:jobseeker_id>")
@role_required("adviser")
def jobseeker_detail(jobseeker_id):
    conn = get_connection()
    jobseeker = get_jobseeker_of_adviser(conn, jobseeker_id, session["user_id"])
    if not jobseeker:
        abort(404)  # not found, or not one of this adviser's jobseekers
    return render_template(
        "adviser_jobseeker.html",
        jobseeker=jobseeker,
        cvs=list_cvs_for_jobseeker(conn, jobseeker_id),
        applications=list_job_applications(conn, jobseeker_id),
    )


@bp.route("/profile", methods=["GET", "POST"])
@role_required("adviser")
def profile():
    conn = get_connection()
    adviser_id = session["user_id"]
    current = get_user(conn, adviser_id)
    if not current or current["role"] != "adviser":
        abort(404)
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().casefold()
        # Saving the address you already have never needs a password. Changing it needs a valid
        # new address and the current password (the email is the sign-in name for the account).
        email_changed = email != current["email"].casefold()
        if not full_name or len(full_name) > 120 or (email_changed and not valid_email(email)):
            flash("Enter a valid name and email address.", "error")
        elif email_changed and not check_password_hash(current["password_hash"], request.form.get("current_password", "")):
            flash("Your current password is needed to change your email address. Check it and try again.", "error")
        else:
            try:
                update_user_profile(conn, adviser_id, full_name, email, current["phone"])
                conn.commit()
            except sqlite3.IntegrityError as error:
                conn.rollback()
                flash(friendly_error_message(error), "error")
            else:
                session["full_name"] = full_name
                flash("Your profile has been updated.", "success")
                return redirect(url_for("advisers.profile"))
        current = get_user(conn, adviser_id)
    return render_template("adviser_profile.html", user=current)


@bp.post("/account/close")
@role_required("adviser")
def close_account():
    conn = get_connection()
    user = get_user(conn, session["user_id"])
    if not user or user["role"] != "adviser" or not check_password_hash(
        user["password_hash"], request.form.get("password", "")
    ):
        flash("Account closure could not be verified. Check your password and try again.", "error")
        return redirect(url_for("advisers.profile"))
    # Delete rules 2 and 3: linked jobseekers stay and become "awaiting adviser", and the CVs
    # this adviser decided keep their outcome, date and comment with "decided by" emptied.
    delete_user(conn, user["id"])
    conn.commit()
    session.clear()
    flash("Your adviser account has been closed. Your jobseekers and their data are unchanged.", "success")
    return redirect(url_for("auth.login"))


@bp.post("/cv/<int:cv_id>/review")
@role_required("adviser")
def review_cv(cv_id):
    conn = get_connection()
    cv = get_cv_for_adviser(conn, cv_id, session["user_id"])
    if not cv:
        abort(404)  # not found, or not the CV of one of this adviser's jobseekers
    back = redirect(url_for("advisers.jobseeker_detail", jobseeker_id=cv["jobseeker_id"]))
    decision = request.form.get("decision", "").strip().lower()
    comment = request.form.get("comment", "").strip()
    if decision not in CV_DECISIONS:
        flash("Choose approved or rejected.", "error")
        return back
    if len(comment) > 4000:
        flash("A comment can be up to 4,000 characters.", "error")
        return back
    if comment and decision != "rejected":
        flash("A comment can only be added when a CV is rejected.", "error")
        return back

    today = irish_today().isoformat()
    try:
        if not decide_cv(conn, cv_id, decision, session["user_id"], today, comment or None):
            conn.rollback()
            flash("This CV has already been decided.", "error")
            return back
        events.cv_decided(conn, cv["jobseeker_id"], cv["title"], decision, bool(comment), today)
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        flash(friendly_error_message(error), "error")
        return back
    flash("The CV decision has been saved.", "success")
    return back
