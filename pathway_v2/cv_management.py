"""Private CV upload, edit, delete and authorised download. CV files live inside the database."""

import sqlite3
import zipfile
from io import BytesIO
from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from db import (
    create_cv,
    delete_cv,
    friendly_error_message,
    get_connection,
    get_cv_for_adviser,
    get_cv_for_jobseeker,
    list_cvs_for_jobseeker,
    replace_cv_file,
    update_cv_title,
)
from security import role_required
from utils import MAX_CV_BYTES, irish_today

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
    """Checks the database cannot make: that the file really is a Word or PDF file."""
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        return None, "Only PDF, DOC and DOCX files are accepted."
    if not content:
        return None, "Choose a non-empty CV file."
    if len(content) > MAX_CV_BYTES:
        return None, "That CV is over the 1 MB limit. Please upload a smaller file."
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


def _read_upload(field_name):
    """Return (file_name, file_type, content) for a valid upload, or flash a message and return None."""
    uploaded = request.files.get(field_name)
    if not uploaded or not uploaded.filename:
        flash("Choose a CV file to upload.", "error")
        return None
    content = uploaded.read(MAX_CV_BYTES + 1)
    extension, error = _validate_document(uploaded.filename, content, uploaded.mimetype)
    if error:
        flash(error, "error")
        return None
    file_name = secure_filename(uploaded.filename)[:180] or f"CV.{extension}"
    return file_name, extension, content


def _title_from_form():
    title = request.form.get("title", "").strip()
    if not title or len(title) > 120:
        flash("Enter a CV title (up to 120 characters).", "error")
        return None
    return title


@bp.route("/cv", methods=["GET", "POST"])
@role_required("jobseeker")
def manage():
    conn = get_connection()
    user_id = session["user_id"]
    if request.method == "POST":
        title = _title_from_form()
        upload = _read_upload("cv_file") if title else None
        if title and upload:
            file_name, file_type, content = upload
            try:
                create_cv(conn, user_id, title, file_name, file_type, content, irish_today().isoformat())
                conn.commit()
            except sqlite3.IntegrityError as error:
                conn.rollback()
                flash(friendly_error_message(error), "error")
            else:
                flash("Your CV has been uploaded and is waiting for review.", "success")
        return redirect(url_for("cv_management.manage"))
    return render_template("cv.html", cvs=list_cvs_for_jobseeker(conn, user_id))


@bp.post("/cv/<int:cv_id>/title")
@role_required("jobseeker")
def rename(cv_id):
    conn = get_connection()
    if get_cv_for_jobseeker(conn, cv_id, session["user_id"]) is None:
        abort(404)
    title = _title_from_form()
    if title:
        try:
            update_cv_title(conn, cv_id, session["user_id"], title)
            conn.commit()
        except sqlite3.IntegrityError as error:
            conn.rollback()
            flash(friendly_error_message(error), "error")
        else:
            flash("The CV title has been updated.", "success")
    return redirect(url_for("cv_management.manage"))


@bp.post("/cv/<int:cv_id>/replace")
@role_required("jobseeker")
def replace(cv_id):
    conn = get_connection()
    if get_cv_for_jobseeker(conn, cv_id, session["user_id"]) is None:
        abort(404)
    upload = _read_upload("cv_file")
    if upload:
        file_name, file_type, content = upload
        try:
            replace_cv_file(conn, cv_id, session["user_id"], file_name, file_type, content,
                            irish_today().isoformat())
            conn.commit()
        except sqlite3.IntegrityError as error:
            conn.rollback()
            flash(friendly_error_message(error), "error")
        else:
            flash("Your CV has been replaced and is waiting for review again.", "success")
    return redirect(url_for("cv_management.manage"))


@bp.post("/cv/<int:cv_id>/delete")
@role_required("jobseeker")
def delete(cv_id):
    conn = get_connection()
    removed = delete_cv(conn, cv_id, session["user_id"])
    conn.commit()
    if removed == 0:
        abort(404)
    flash("The CV has been deleted.", "success")
    return redirect(url_for("cv_management.manage"))


@bp.get("/cv/<int:cv_id>/download")
def download(cv_id):
    if not session.get("user_id"):
        abort(401)
    conn = get_connection()
    if session.get("role") == "jobseeker":
        row = get_cv_for_jobseeker(conn, cv_id, session["user_id"], with_file=True)
    elif session.get("role") == "adviser":
        row = get_cv_for_adviser(conn, cv_id, session["user_id"], with_file=True)
    else:
        row = None
    if not row:
        abort(404)
    return send_file(
        BytesIO(row["file_data"]),
        as_attachment=True,
        download_name=row["file_name"],
        mimetype="application/octet-stream",
        max_age=0,
    )
