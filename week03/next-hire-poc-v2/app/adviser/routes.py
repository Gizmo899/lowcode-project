from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from ..extensions import db
from ..models import Application, CV, User
from ..security import adviser_required

bp = Blueprint("adviser", __name__, url_prefix="/adviser")


@bp.get("/reviews")
@adviser_required
def reviews():
    queue = CV.query.filter_by(status="submitted").order_by(CV.uploaded_at.asc()).all()
    return render_template("adviser/reviews.html", cvs=queue)


@bp.route("/cvs/<int:cv_id>", methods=["GET", "POST"])
@adviser_required
def review_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if request.method == "POST":
        if cv.status != "submitted":
            abort(409)
        action = request.form.get("action")
        comment = request.form.get("comment", "").strip() or None
        if action == "request_changes":
            if not comment:
                flash("A comment is required when requesting changes.", "error")
                return render_template("adviser/review_cv.html", cv=cv)
            cv.status = "changes_requested"
        elif action == "approve":
            cv.status = "approved"
        else:
            abort(400)
        cv.review_comment = comment
        from flask_login import current_user
        cv.reviewer_id = current_user.id
        from ..models import utcnow
        cv.reviewed_at = utcnow()
        db.session.commit()
        flash(f"CV marked as {cv.status.replace('_', ' ')}.", "success")
        return redirect(url_for("adviser.reviews"))
    return render_template("adviser/review_cv.html", cv=cv)


@bp.get("/jobseekers")
@adviser_required
def jobseekers():
    records = User.query.filter_by(role="jobseeker", status="active").order_by(User.full_name.asc()).all()
    return render_template("adviser/jobseekers.html", jobseekers=records)


@bp.get("/jobseekers/<int:jobseeker_id>")
@adviser_required
def jobseeker_detail(jobseeker_id):
    user = User.query.filter_by(id=jobseeker_id, role="jobseeker", status="active").first_or_404()
    applications = Application.query.filter_by(jobseeker_id=user.id).order_by(Application.updated_at.desc()).all()
    cvs = CV.query.filter_by(jobseeker_id=user.id).order_by(CV.uploaded_at.desc()).all()
    return render_template("adviser/jobseeker_detail.html", jobseeker=user, applications=applications, cvs=cvs)


@bp.get("/applications/<int:application_id>")
@adviser_required
def application_detail(application_id):
    item = Application.query.get_or_404(application_id)
    return render_template("adviser/application_detail.html", item=item)
