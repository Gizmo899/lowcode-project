"""Registration, sign-in and sign-out routes."""

import secrets
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import create_user, friendly_error_message, get_connection, get_user_by_email, list_advisers
from security import login_required
from utils import password_problems, valid_email

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    conn = get_connection()
    advisers = list_advisers(conn)

    if request.method == "POST":
        role = request.form.get("role", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        adviser_value = request.form.get("assigned_adviser_id", "").strip()
        errors = []

        if role not in {"jobseeker", "adviser"}:
            errors.append("Choose a valid account type.")
        if not full_name or len(full_name) > 120:
            errors.append("Enter your full name (up to 120 characters).")
        if not valid_email(email):
            errors.append("Enter a valid email address.")
        errors.extend(password_problems(password))
        if len(phone) > 40:
            errors.append("A phone number can be up to 40 characters.")

        adviser_id = None
        if role == "jobseeker" and advisers:
            try:
                adviser_id = int(adviser_value)
            except (TypeError, ValueError):
                errors.append("Select a career adviser.")
            else:
                if adviser_id not in {adviser["id"] for adviser in advisers}:
                    errors.append("The selected adviser is not available. Please choose another adviser.")
        if role == "adviser":
            phone = ""  # advisers do not give a phone number

        if errors:
            for error in errors:
                flash(error, "error")
        else:
            try:
                create_user(conn, full_name, email, generate_password_hash(password), phone or None, role, adviser_id)
                conn.commit()
            except sqlite3.IntegrityError as error:
                conn.rollback()
                flash(friendly_error_message(error), "error")
            else:
                flash("Your account has been created. Please sign in.", "success")
                return redirect(url_for("auth.login"))

    return render_template("register.html", advisers=advisers)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        user = get_user_by_email(get_connection(), email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Sign-in failed. Check your details and try again.", "error")
            return render_template("login.html"), 401

        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("index"))

    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
