"""Private CV upload, version history and authorised file delivery."""

from io import BytesIO
from pathlib import Path
import zipfile
import uuid

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from db import get_db
from security import role_required
from utils import utc_now

bp = Blueprint("cv_management", __name__)
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
ALLOWED_MIME_TYPES = {
    "pdf": {"application/pdf", "application/octet-stream"},
    "doc": {"application/msword", "application/octet-stream"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
}


def _validate_document(filename, content, browser_mime):
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        return None, "Only PDF, DOC and DOCX files are accepted."
    if not content:
        return None, "Choose a non-empty CV file."
    if browser_mime and browser_mime.lower() not in ALLOWED_MIME_TYPES[extension]:
        return None, "The file type does not match the selected document extension."

    if extension == "pdf":
        valid_signature = content.startswith(b"%PDF-")
    elif extension == "doc":
        valid_signature = content.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
    else:
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
                valid_signature = "[Content_Types].xml" in names and "word/document.xml" in names
        except (zipfile.BadZipFile, OSError):
            valid_signature = False
    if not valid_signature:
        return None, "The uploaded file content could not be validated as the selected document type."
    return extension, None


@bp.route("/cv", methods=["GET", "POST"])
@role_required("jobseeker")
def manage():
    db = get_db()
    user_id = session["user_id"]
    if request.method == "POST":
        uploaded = request.files.get("cv_file")
        if not uploaded or not uploaded.filename:
            flash("Choose a CV file to upload.", "error")
            return redirect(url_for("cv_management.manage"))
        content = uploaded.read(current_app.config["MAX_CONTENT_LENGTH"] + 1)
        if len(content) > current_app.config["MAX_CONTENT_LENGTH"]:
            flash("The CV exceeds the 5 MB upload limit.", "error")
            return redirect(url_for("cv_management.manage"))
        extension, error = _validate_document(uploaded.filename, content, uploaded.mimetype)
        if error:
            flash(error, "error")
            return redirect(url_for("cv_management.manage"))

        safe_original = secure_filename(uploaded.filename)[:180] or f"CV.{extension}"
        stored_filename = f"{uuid.uuid4().hex}.{extension}"
        upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = upload_dir / stored_filename
        try:
            destination.write_bytes(content)
            now = utc_now()
            db.execute("UPDATE cv_versions SET is_current = 0 WHERE jobseeker_id = ? AND is_current = 1", (user_id,))
            db.execute(
                """INSERT INTO cv_versions
                   (jobseeker_id, stored_filename, original_filename, uploaded_at, approval_status, is_current)
                   VALUES (?, ?, ?, ?, 'pending', 1)""",
                (user_id, stored_filename, safe_original, now),
            )
            db.commit()
        except Exception:
            db.rollback()
            destination.unlink(missing_ok=True)
            current_app.logger.exception("CV upload could not be stored")
            flash("The CV could not be saved. Please try again.", "error")
            return redirect(url_for("cv_management.manage"))
        flash("Your new CV has been uploaded and is awaiting adviser review.", "success")
        return redirect(url_for("cv_management.manage"))

    versions = db.execute(
        """SELECT cv.*, u.full_name AS reviewer_name
           FROM cv_versions cv LEFT JOIN users u ON u.id = cv.reviewed_by
           WHERE cv.jobseeker_id = ? ORDER BY cv.uploaded_at DESC""",
        (user_id,),
    ).fetchall()
    reviews = db.execute(
        """SELECT r.*, u.full_name AS adviser_name, cv.original_filename
           FROM cv_reviews r
           JOIN cv_versions cv ON cv.id = r.cv_version_id
           JOIN users u ON u.id = r.adviser_id
           WHERE cv.jobseeker_id = ? ORDER BY r.reviewed_at DESC""",
        (user_id,),
    ).fetchall()
    return render_template("cv.html", versions=versions, reviews=reviews)


@bp.get("/cv/<int:cv_id>/download")
def download(cv_id):
    if not session.get("user_id"):
        abort(401)
    db = get_db()
    viewer_id = session["user_id"]
    viewer_role = session.get("role")
    if viewer_role == "jobseeker":
        row = db.execute(
            "SELECT cv.* FROM cv_versions cv WHERE cv.id = ? AND cv.jobseeker_id = ?",
            (cv_id, viewer_id),
        ).fetchone()
    elif viewer_role == "career_adviser":
        row = db.execute(
            """SELECT cv.* FROM cv_versions cv
               JOIN users j ON j.id = cv.jobseeker_id
               WHERE cv.id = ? AND j.role = 'jobseeker' AND j.assigned_adviser_id = ?""",
            (cv_id, viewer_id),
        ).fetchone()
    else:
        row = None
    if not row:
        abort(404)

    path = Path(current_app.config["UPLOAD_FOLDER"]) / row["stored_filename"]
    if not path.is_file():
        abort(404)
    return send_file(
        path,
        as_attachment=True,
        download_name=row["original_filename"],
        mimetype="application/octet-stream",
        max_age=0,
    )
