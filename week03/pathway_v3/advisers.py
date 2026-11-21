"""Career adviser workspace and human CV review workflow."""

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from db import get_db
from security import role_required
from utils import CV_DECISIONS, utc_now, valid_email

bp = Blueprint("advisers", __name__, url_prefix="/adviser")


@bp.get("/dashboard")
@role_required("career_adviser")
def dashboard():
    db = get_db()
    adviser_id = session["user_id"]
    jobseekers = db.execute(
        """SELECT u.id, u.full_name, u.email, u.phone, u.created_at,
                  (SELECT COUNT(*) FROM job_applications ja WHERE ja.jobseeker_id = u.id) AS application_count,
                  (SELECT approval_status FROM cv_versions cv WHERE cv.jobseeker_id = u.id AND cv.is_current = 1) AS cv_status
           FROM users u
           WHERE u.role = 'jobseeker' AND u.assigned_adviser_id = ?
           ORDER BY u.full_name COLLATE NOCASE""",
        (adviser_id,),
    ).fetchall()
    return render_template("adviser_dashboard.html", jobseekers=jobseekers)


@bp.get("/jobseekers/<int:jobseeker_id>")
@role_required("career_adviser")
def jobseeker_detail(jobseeker_id):
    db = get_db()
    jobseeker = db.execute(
        """SELECT id, full_name, email, phone, created_at
           FROM users
           WHERE id = ? AND role = 'jobseeker' AND assigned_adviser_id = ?""",
        (jobseeker_id, session["user_id"]),
    ).fetchone()
    if not jobseeker:
        abort(404)
    cvs = db.execute(
        """SELECT cv.*, (SELECT COUNT(*) FROM cv_reviews r WHERE r.cv_version_id = cv.id) AS review_count
           FROM cv_versions cv WHERE cv.jobseeker_id = ?
           ORDER BY cv.uploaded_at DESC""",
        (jobseeker_id,),
    ).fetchall()
    reviews = db.execute(
        """SELECT r.*, cv.original_filename, u.full_name AS adviser_name
           FROM cv_reviews r
           JOIN cv_versions cv ON cv.id = r.cv_version_id
           JOIN users u ON u.id = r.adviser_id
           WHERE cv.jobseeker_id = ?
           ORDER BY r.reviewed_at DESC""",
        (jobseeker_id,),
    ).fetchall()
    applications = db.execute(
        "SELECT * FROM job_applications WHERE jobseeker_id = ? ORDER BY date_applied DESC, id DESC",
        (jobseeker_id,),
    ).fetchall()
    return render_template(
        "adviser_jobseeker.html",
        jobseeker=jobseeker,
        cvs=cvs,
        reviews=reviews,
        applications=applications,
    )


@bp.route("/profile", methods=["GET", "POST"])
@role_required("career_adviser")
def profile():
    db = get_db()
    adviser_id = session["user_id"]
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().casefold()
        current = db.execute(
            "SELECT email, password_hash FROM users WHERE id = ? AND role = 'career_adviser'",
            (adviser_id,),
        ).fetchone()
        if not current:
            abort(404)
        # Saving the address you already have never needs a password. Changing it needs a valid
        # new address and the current password (the email is the sign-in name for the account).
        email_changed = email != current["email"].casefold()
        if not full_name or len(full_name) > 120 or (email_changed and not valid_email(email)):
            flash("Enter a valid name and email address.", "error")
        elif email_changed and not check_password_hash(current["password_hash"], request.form.get("current_password", "")):
            flash("Your current password is needed to change your email address. Check it and try again.", "error")
        else:
            try:
                db.execute(
                    "UPDATE users SET full_name = ?, email = ? WHERE id = ? AND role = 'career_adviser'",
                    (full_name, email, adviser_id),
                )
                db.commit()
                session["full_name"] = full_name
                flash("Your profile has been updated.", "success")
                return redirect(url_for("advisers.profile"))
            except Exception as exc:
                db.rollback()
                if "UNIQUE constraint failed: users.email" in str(exc):
                    flash("We could not save those details. Check the email address and try again.", "error")
                else:
                    flash("We could not update your profile. Please try again.", "error")
    user = db.execute(
        "SELECT id, full_name, email FROM users WHERE id = ? AND role = 'career_adviser'",
        (adviser_id,),
    ).fetchone()
    return render_template("adviser_profile.html", user=user)


@bp.post("/account/close")
@role_required("career_adviser")
def close_account():
    db = get_db()
    adviser_id = session["user_id"]
    password = request.form.get("password", "")
    user = db.execute(
        "SELECT password_hash FROM users WHERE id = ? AND role = 'career_adviser'",
        (adviser_id,),
    ).fetchone()
    assigned_count = db.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'jobseeker' AND assigned_adviser_id = ?",
        (adviser_id,),
    ).fetchone()[0]
    if assigned_count:
        flash("This adviser account cannot be closed while jobseekers are assigned to it. The organisation must resolve those assignments first.", "error")
        return redirect(url_for("advisers.profile"))
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Account closure could not be verified. Check your password and try again.", "error")
        return redirect(url_for("advisers.profile"))
    db.execute("DELETE FROM users WHERE id = ? AND role = 'career_adviser'", (adviser_id,))
    db.commit()
    session.clear()
    flash("Your adviser account has been closed.", "success")
    return redirect(url_for("auth.login"))


@bp.post("/cv/<int:cv_id>/review")
@role_required("career_adviser")
def review_cv(cv_id):
    db = get_db()
    cv = db.execute(
        """SELECT cv.id, cv.jobseeker_id
           FROM cv_versions cv
           JOIN users u ON u.id = cv.jobseeker_id
           WHERE cv.id = ? AND cv.is_current = 1
             AND u.role = 'jobseeker' AND u.assigned_adviser_id = ?""",
        (cv_id, session["user_id"]),
    ).fetchone()
    if not cv:
        abort(404)
    decision = request.form.get("decision", "").strip().lower()
    comments = request.form.get("comments", "").strip()
    if decision not in CV_DECISIONS or not comments or len(comments) > 4000:
        flash("Choose an approval decision and provide comments (up to 4,000 characters).", "error")
        return redirect(url_for("advisers.jobseeker_detail", jobseeker_id=cv["jobseeker_id"]))

    reviewed_at = utc_now()
    try:
        db.execute(
            "UPDATE cv_versions SET approval_status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ? AND is_current = 1",
            (decision, session["user_id"], reviewed_at, cv_id),
        )
        db.execute(
            "INSERT INTO cv_reviews (cv_version_id, adviser_id, decision, comments, reviewed_at) VALUES (?, ?, ?, ?, ?)",
            (cv_id, session["user_id"], decision, comments, reviewed_at),
        )
        label = "approved" if decision == "approved" else "rejected"
        db.execute(
            """INSERT INTO notifications
               (user_id, notification_type, title, message, related_cv_version_id, created_at, deduplication_key)
               VALUES (?, 'cv_review', ?, ?, ?, ?, NULL)""",
            (
                cv["jobseeker_id"],
                f"Your CV was {label}",
                f"Your adviser {label} your current CV. Comments: {comments}",
                cv_id,
                reviewed_at,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        flash("The CV review could not be saved. Please try again.", "error")
        return redirect(url_for("advisers.jobseeker_detail", jobseeker_id=cv["jobseeker_id"]))

    flash("The CV decision and comments have been saved.", "success")
    return redirect(url_for("advisers.jobseeker_detail", jobseeker_id=cv["jobseeker_id"]))
