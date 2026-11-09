import io
import mimetypes
import os
import uuid
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from ..extensions import db
from ..models import Application, Contact, CV, Digest, Notification, User
from ..security import jobseeker_required
from ..timeutils import local_midnight_to_utc, local_today

bp = Blueprint("jobseeker", __name__)
STAGES = ["saved", "applied", "interview", "offer"]
OUTCOMES = ["accepted", "rejected", "withdrawn", "no_reply"]
WORK_MODES = ["remote", "hybrid", "on_site"]


def _owned_application(application_id):
    item = Application.query.filter_by(id=application_id, jobseeker_id=current_user.id).first()
    if not item:
        abort(404)
    return item


def _owned_contact(contact_id):
    item = Contact.query.filter_by(id=contact_id, jobseeker_id=current_user.id).first()
    if not item:
        abort(404)
    return item


def _owned_cv(cv_id):
    item = CV.query.filter_by(id=cv_id, jobseeker_id=current_user.id).first()
    if not item:
        abort(404)
    return item


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid date.")


def _application_values(form, existing=None):
    errors = []
    company = form.get("company", "").strip()
    job_title = form.get("job_title", "").strip()
    stage = form.get("stage", "saved")
    outcome = form.get("outcome", "").strip() or None
    work_mode = form.get("work_mode", "").strip() or None
    job_url = form.get("job_url", "").strip() or None
    if job_url:
        parsed_url = urlparse(job_url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            errors.append("Job URL must start with http:// or https://.")
    if not company:
        errors.append("Company is required.")
    if not job_title:
        errors.append("Job title is required.")
    if stage not in STAGES:
        errors.append("Choose a valid pipeline stage.")
    if outcome and outcome not in OUTCOMES:
        errors.append("Choose a valid outcome.")
    if work_mode and work_mode not in WORK_MODES:
        errors.append("Choose a valid work mode.")
    if outcome == "accepted" and stage != "offer":
        errors.append("An application can only be marked Accepted at the Offer stage.")
    try:
        date_applied = _parse_date(form.get("date_applied", ""))
        deadline = _parse_date(form.get("deadline", ""))
    except ValueError as exc:
        errors.append(str(exc))
        date_applied = deadline = None
    if stage == "applied" and not date_applied:
        date_applied = local_today()
    cv = None
    cv_id = form.get("cv_id", "").strip()
    if cv_id:
        try:
            cv = CV.query.filter_by(id=int(cv_id), jobseeker_id=current_user.id).first()
        except ValueError:
            cv = None
        if not cv:
            errors.append("Select one of your own CV versions.")

    values = {
        "company": company,
        "job_title": job_title,
        "job_url": job_url,
        "location": form.get("location", "").strip() or None,
        "work_mode": work_mode,
        "salary_range": form.get("salary_range", "").strip() or None,
        "date_applied": date_applied,
        "deadline": deadline,
        "notes": form.get("notes", "").strip() or None,
        "stage": stage,
        "outcome": outcome,
        "cv": cv,
        "cover_letter_ref": form.get("cover_letter_ref", "").strip() or None,
    }
    return values, errors


def _apply_values(item, values):
    previous_stage = item.stage
    previous_date = item.date_applied
    item.company = values["company"]
    item.job_title = values["job_title"]
    item.job_url = values["job_url"]
    item.location = values["location"]
    item.work_mode = values["work_mode"]
    item.salary_range = values["salary_range"]
    item.date_applied = values["date_applied"]
    item.deadline = values["deadline"]
    item.notes = values["notes"]
    item.stage = values["stage"]
    item.outcome = values["outcome"]
    item.cv = values["cv"]
    item.cover_letter_ref = values["cover_letter_ref"]
    if item.stage == "applied" and item.outcome is None:
        if not item.date_applied:
            item.date_applied = local_today()
        if not item.nudge_sent_at:
            if previous_stage != "applied" or previous_date != item.date_applied or not item.nudge_due_at:
                # Due at the start of that day in APP_TIMEZONE, stored as UTC so it is
                # comparable with utcnow() in the nudge job.
                item.nudge_due_at = local_midnight_to_utc(
                    item.date_applied + timedelta(days=current_app.config["NUDGE_DELAY_DAYS"])
                )
    else:
        item.nudge_due_at = None


@bp.get("/dashboard")
@jobseeker_required
def dashboard():
    today = local_today()
    deadlines = Application.query.filter(
        Application.jobseeker_id == current_user.id,
        Application.outcome.is_(None),
        Application.deadline.isnot(None),
        Application.deadline >= today,
    ).order_by(Application.deadline.asc()).limit(10).all()
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()
    latest_digest = Digest.query.filter_by(jobseeker_id=current_user.id).order_by(Digest.week_start.desc()).first()
    open_count = Application.query.filter_by(jobseeker_id=current_user.id, outcome=None).count()
    return render_template("jobseeker/dashboard.html", deadlines=deadlines, notifications=notifications,
                           latest_digest=latest_digest, open_count=open_count)


@bp.get("/applications")
@jobseeker_required
def applications():
    sort = request.args.get("sort", "updated")
    query = Application.query.filter_by(jobseeker_id=current_user.id)
    if sort == "deadline":
        query = query.order_by(Application.deadline.is_(None), Application.deadline.asc())
    elif sort == "date_applied":
        query = query.order_by(Application.date_applied.is_(None), Application.date_applied.desc())
    else:
        query = query.order_by(Application.updated_at.desc())
    return render_template("jobseeker/applications.html", applications=query.all(), sort=sort)


@bp.route("/applications/new", methods=["GET", "POST"])
@jobseeker_required
def application_new():
    if request.method == "POST":
        values, errors = _application_values(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            item = Application(jobseeker_id=current_user.id)
            _apply_values(item, values)
            db.session.add(item)
            db.session.commit()
            flash("Application added to your pipeline.", "success")
            return redirect(url_for("jobseeker.application_detail", application_id=item.id))
    return render_template("jobseeker/application_form.html", item=None, cvs=CV.query.filter_by(jobseeker_id=current_user.id).order_by(CV.uploaded_at.desc()).all(), stages=STAGES, outcomes=OUTCOMES, work_modes=WORK_MODES)


@bp.get("/applications/<int:application_id>")
@jobseeker_required
def application_detail(application_id):
    item = _owned_application(application_id)
    linked_ids = {contact.id for contact in item.contacts}
    return render_template("jobseeker/application_detail.html", item=item,
                           contacts=Contact.query.filter_by(jobseeker_id=current_user.id).order_by(Contact.name.asc()).all(),
                           available_contacts=[contact for contact in Contact.query.filter_by(jobseeker_id=current_user.id).order_by(Contact.name.asc()).all() if contact.id not in linked_ids],
                           linked_ids=linked_ids)


@bp.route("/applications/<int:application_id>/edit", methods=["GET", "POST"])
@jobseeker_required
def application_edit(application_id):
    item = _owned_application(application_id)
    if request.method == "POST":
        values, errors = _application_values(request.form, item)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            _apply_values(item, values)
            db.session.commit()
            flash("Application updated.", "success")
            return redirect(url_for("jobseeker.application_detail", application_id=item.id))
    return render_template("jobseeker/application_form.html", item=item, cvs=CV.query.filter_by(jobseeker_id=current_user.id).order_by(CV.uploaded_at.desc()).all(), stages=STAGES, outcomes=OUTCOMES, work_modes=WORK_MODES)


@bp.post("/applications/<int:application_id>/delete")
@jobseeker_required
def application_delete(application_id):
    item = _owned_application(application_id)
    db.session.delete(item)
    db.session.commit()
    flash("Application deleted.", "success")
    return redirect(url_for("jobseeker.applications"))


@bp.post("/applications/<int:application_id>/contacts")
@jobseeker_required
def application_contacts_update(application_id):
    item = _owned_application(application_id)
    contact_id = request.form.get("contact_id", type=int)
    action = request.form.get("action")
    contact = Contact.query.filter_by(id=contact_id, jobseeker_id=current_user.id).first() if contact_id else None
    if not contact:
        abort(404)
    if action == "link" and contact not in item.contacts:
        item.contacts.append(contact)
        flash("Contact linked to application.", "success")
    elif action == "unlink" and contact in item.contacts:
        item.contacts.remove(contact)
        flash("Contact unlinked from application.", "success")
    db.session.commit()
    return redirect(url_for("jobseeker.application_detail", application_id=item.id))


def _validate_cv_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None, "Choose a PDF or DOCX file."
    filename = secure_filename(file_storage.filename)
    extension = Path(filename).suffix.lower()
    if extension not in (".pdf", ".docx"):
        return None, "Only PDF and DOCX files are accepted."
    data = file_storage.read()
    file_storage.stream.seek(0)
    if len(data) > current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024:
        return None, f"File exceeds the {current_app.config['MAX_UPLOAD_MB']} MB limit."
    mime = file_storage.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if extension == ".pdf":
        valid_mime = mime == "application/pdf"
        valid_content = data.startswith(b"%PDF-")
        expected_mime = "application/pdf"
    else:
        valid_mime = mime in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/x-zip-compressed",
        )
        valid_content = data.startswith(b"PK")
        expected_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if valid_content:
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    valid_content = "word/document.xml" in archive.namelist()
            except zipfile.BadZipFile:
                valid_content = False
    if not valid_mime or not valid_content:
        return None, "The file content or MIME type does not match a valid PDF/DOCX document."
    return (filename, data, expected_mime), None


@bp.route("/cvs", methods=["GET", "POST"])
@jobseeker_required
def cvs():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        version_label = request.form.get("version_label", "").strip()
        file_storage = request.files.get("file")
        if not title or not version_label:
            flash("CV title and version label are required.", "error")
        else:
            validated, error = _validate_cv_upload(file_storage)
            if error:
                flash(error, "error")
            else:
                original_filename, data, mime = validated
                suffix = Path(original_filename).suffix.lower()
                stored_filename = f"{uuid.uuid4().hex}{suffix}"
                target = Path(current_app.config["UPLOAD_DIR"]) / stored_filename
                target.write_bytes(data)
                cv = CV(jobseeker_id=current_user.id, title=title, version_label=version_label,
                        original_filename=original_filename, stored_filename=stored_filename,
                        mime_type=mime, status="submitted")
                db.session.add(cv)
                db.session.commit()
                flash("CV uploaded. A new version has been added with status Submitted.", "success")
                return redirect(url_for("jobseeker.cvs"))
    records = CV.query.filter_by(jobseeker_id=current_user.id).order_by(CV.uploaded_at.desc()).all()
    return render_template("jobseeker/cvs.html", cvs=records)


@bp.get("/cvs/<int:cv_id>/download")
@login_required
def cv_download_owner(cv_id):
    cv = CV.query.get_or_404(cv_id)
    is_owner = current_user.role == "jobseeker" and current_user.status == "active" and cv.jobseeker_id == current_user.id
    is_adviser = current_user.role == "adviser" and current_user.status == "active"
    if not (is_owner or is_adviser):
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_DIR"], cv.stored_filename,
                               as_attachment=True, download_name=cv.original_filename)


@bp.get("/contacts")
@jobseeker_required
def contacts():
    records = Contact.query.filter_by(jobseeker_id=current_user.id).order_by(Contact.name.asc()).all()
    return render_template("jobseeker/contacts.html", contacts=records)


@bp.route("/contacts/new", methods=["GET", "POST"])
@jobseeker_required
def contact_new():
    return _contact_form(None)


@bp.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
@jobseeker_required
def contact_edit(contact_id):
    return _contact_form(_owned_contact(contact_id))


def _contact_form(item):
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        linkedin_url = request.form.get("linkedin_url", "").strip()
        if not name:
            flash("Contact name is required.", "error")
        elif linkedin_url and (urlparse(linkedin_url).scheme not in ("http", "https") or not urlparse(linkedin_url).netloc):
            flash("LinkedIn URL must start with http:// or https://.", "error")
        else:
            if item is None:
                item = Contact(jobseeker_id=current_user.id)
                db.session.add(item)
            for field in ("name", "company", "email", "phone", "job_title", "linkedin_url", "notes"):
                setattr(item, field, request.form.get(field, "").strip() or (None if field != "name" else ""))
            db.session.commit()
            flash("Contact saved.", "success")
            return redirect(url_for("jobseeker.contact_detail", contact_id=item.id))
    return render_template("jobseeker/contact_form.html", item=item)


@bp.get("/contacts/<int:contact_id>")
@jobseeker_required
def contact_detail(contact_id):
    item = _owned_contact(contact_id)
    linked_applications = Application.query.join(Application.contacts).filter(
        Application.jobseeker_id == current_user.id, Contact.id == item.id
    ).order_by(Application.updated_at.desc()).all()
    return render_template("jobseeker/contact_detail.html", item=item, applications=linked_applications)


@bp.post("/contacts/<int:contact_id>/delete")
@jobseeker_required
def contact_delete(contact_id):
    item = _owned_contact(contact_id)
    item.applications.clear()
    db.session.delete(item)
    db.session.commit()
    flash("Contact deleted.", "success")
    return redirect(url_for("jobseeker.contacts"))


@bp.get("/notifications")
@jobseeker_required
def notifications():
    records = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template("jobseeker/notifications.html", notifications=records)


@bp.post("/notifications/<int:notification_id>/read")
@jobseeker_required
def notification_read(notification_id):
    item = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    item.is_read = True
    db.session.commit()
    return redirect(url_for("jobseeker.notifications"))


@bp.get("/digests")
@jobseeker_required
def digests():
    records = Digest.query.filter_by(jobseeker_id=current_user.id).order_by(Digest.week_start.desc()).all()
    return render_template("jobseeker/digests.html", digests=records)


@bp.get("/digests/<int:digest_id>")
@jobseeker_required
def digest_detail(digest_id):
    item = Digest.query.filter_by(id=digest_id, jobseeker_id=current_user.id).first_or_404()
    return render_template("jobseeker/digest_detail.html", digest=item)
