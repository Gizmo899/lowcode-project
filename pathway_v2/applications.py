"""Jobseeker-owned job application routes."""

import sqlite3
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

import events
from db import (
    count_job_applications_by_status,
    create_job_application,
    delete_job_application,
    friendly_error_message,
    get_connection,
    get_job_application,
    list_job_applications,
    update_job_application,
)
from security import role_required
from utils import APPLICATION_STATUSES, irish_today, valid_http_url

bp = Blueprint("applications", __name__, url_prefix="/applications")


def _form_values():
    return {
        "company_name": request.form.get("company_name", "").strip(),
        "job_title": request.form.get("job_title", "").strip(),
        "date_applied": request.form.get("date_applied", "").strip(),
        "advert_url": request.form.get("advert_url", "").strip(),
        "notes": request.form.get("notes", "").strip(),
        "status": request.form.get("status", "applied").strip(),
    }


def _validate(values, old_status=None):
    """Checks the database cannot make: today's date and the stage rules (docs/data-model.md)."""
    errors = []
    if not values["company_name"] or len(values["company_name"]) > 160:
        errors.append("Enter a company name (up to 160 characters).")
    if not values["job_title"] or len(values["job_title"]) > 160:
        errors.append("Enter a job title (up to 160 characters).")
    try:
        applied = date.fromisoformat(values["date_applied"])
    except ValueError:
        errors.append("Enter a valid date applied.")
    else:
        if applied > irish_today():
            errors.append("The date applied cannot be in the future.")
    if values["advert_url"] and (not valid_http_url(values["advert_url"]) or len(values["advert_url"]) > 2048):
        errors.append("The job advert link must be a web address starting with http:// or https://.")
    if len(values["notes"]) > 4000:
        errors.append("Notes can be up to 4,000 characters.")
    if old_status is not None:
        if values["status"] not in APPLICATION_STATUSES:
            errors.append("Choose one of the permitted application stages.")
        elif values["status"] == "applied" and old_status != "applied":
            errors.append("An application cannot move back to applied.")
    return errors


def _statuses_for(old_status):
    """The stages offered on the edit form: never 'applied' once an application has left it."""
    if old_status == "applied":
        return APPLICATION_STATUSES
    return tuple(status for status in APPLICATION_STATUSES if status != "applied")


@bp.get("")
@role_required("jobseeker")
def listing():
    conn = get_connection()
    counts = count_job_applications_by_status(conn, session["user_id"])
    return render_template(
        "applications.html",
        applications=list_job_applications(conn, session["user_id"]),
        counts=counts,
        total=sum(counts.values()),
        statuses=APPLICATION_STATUSES,
    )


@bp.route("/new", methods=["GET", "POST"])
@role_required("jobseeker")
def create():
    values = {"company_name": "", "job_title": "", "date_applied": irish_today().isoformat(),
              "advert_url": "", "notes": "", "status": "applied"}
    if request.method == "POST":
        values = _form_values()
        errors = _validate(values)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            conn = get_connection()
            today = irish_today().isoformat()
            try:
                application_id = create_job_application(
                    conn, session["user_id"], values["company_name"], values["job_title"],
                    values["date_applied"], values["advert_url"] or None, values["notes"] or None,
                )
                events.application_saved(conn, application_id, values["date_applied"], today)
                conn.commit()
            except sqlite3.IntegrityError as error:
                conn.rollback()
                flash(friendly_error_message(error), "error")
            else:
                flash("Your job application has been saved.", "success")
                return redirect(url_for("applications.listing"))
    return render_template("application_form.html", values=values, statuses=(), heading="Add an application",
                           is_new=True, today=irish_today().isoformat())


@bp.route("/<int:application_id>/edit", methods=["GET", "POST"])
@role_required("jobseeker")
def edit(application_id):
    conn = get_connection()
    application = get_job_application(conn, application_id, session["user_id"])
    if not application:
        abort(404)
    old_status = application["status"]
    values = {key: ("" if application[key] is None else application[key])
              for key in ("company_name", "job_title", "date_applied", "advert_url", "notes", "status")}
    if request.method == "POST":
        values = _form_values()
        errors = _validate(values, old_status)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            today = irish_today().isoformat()
            try:
                update_job_application(
                    conn, application_id, session["user_id"], values["company_name"], values["job_title"],
                    values["date_applied"], values["status"], values["advert_url"] or None, values["notes"] or None,
                )
                events.application_stage_changed(conn, application_id, old_status, values["status"], today)
                conn.commit()
            except sqlite3.IntegrityError as error:
                conn.rollback()
                flash(friendly_error_message(error), "error")
            else:
                flash("Your application has been updated.", "success")
                return redirect(url_for("applications.listing"))
    return render_template("application_form.html", values=values, statuses=_statuses_for(old_status),
                           heading="Edit application", is_new=False, today=irish_today().isoformat())


@bp.post("/<int:application_id>/delete")
@role_required("jobseeker")
def delete(application_id):
    conn = get_connection()
    removed = delete_job_application(conn, application_id, session["user_id"])
    conn.commit()
    if removed == 0:
        abort(404)
    flash("The application has been deleted.", "success")
    return redirect(url_for("applications.listing"))
