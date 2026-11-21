"""Registration, sign-in and sign-out routes."""

import hashlib
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from security import login_required
from utils import utc_now, valid_email

bp = Blueprint("auth", __name__)


def _login_identity(email):
    remote = request.remote_addr or "unknown"
    return hashlib.sha256(f"{email.casefold()}|{remote}".encode("utf-8")).hexdigest()


def _rate_limited(db, identity_hash):
    row = db.execute(
        "SELECT failed_count, window_started_at FROM login_attempts WHERE identity_hash = ?",
        (identity_hash,),
    ).fetchone()
    if not row:
        return False
    started = datetime.fromisoformat(row["window_started_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) - started > timedelta(minutes=15):
        db.execute("DELETE FROM login_attempts WHERE identity_hash = ?", (identity_hash,))
        db.commit()
        return False
    return row["failed_count"] >= 5


def _record_failure(db, identity_hash):
    now = utc_now()
    row = db.execute(
        "SELECT failed_count, window_started_at FROM login_attempts WHERE identity_hash = ?",
        (identity_hash,),
    ).fetchone()
    if row:
        started = datetime.fromisoformat(row["window_started_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - started > timedelta(minutes=15):
            db.execute(
                "UPDATE login_attempts SET failed_count = 1, window_started_at = ?, last_attempt_at = ? WHERE identity_hash = ?",
                (now, now, identity_hash),
            )
        else:
            db.execute(
                "UPDATE login_attempts SET failed_count = failed_count + 1, last_attempt_at = ? WHERE identity_hash = ?",
                (now, identity_hash),
            )
    else:
        db.execute(
            "INSERT INTO login_attempts (identity_hash, failed_count, window_started_at, last_attempt_at) VALUES (?, 1, ?, ?)",
            (identity_hash, now, now),
        )
    db.commit()


@bp.route("/register", methods=["GET", "POST"])
def register():
    db = get_db()
    advisers = db.execute(
        "SELECT id, full_name FROM users WHERE role = 'career_adviser' AND account_status = 'active' ORDER BY full_name COLLATE NOCASE"
    ).fetchall()

    if request.method == "POST":
        role = request.form.get("role", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        adviser_value = request.form.get("assigned_adviser_id", "").strip()
        errors = []

        if role not in {"jobseeker", "career_adviser"}:
            errors.append("Choose a valid account type.")
        if not full_name or len(full_name) > 120:
            errors.append("Enter your full name (up to 120 characters).")
        if not valid_email(email):
            errors.append("Enter a valid email address.")
        if len(password) < 10:
            errors.append("Use a password with at least 10 characters.")
        if role == "jobseeker" and (not phone or len(phone) > 40):
            errors.append("Enter a phone number (up to 40 characters).")

        adviser_id = None
        account_status = "active"
        if role == "jobseeker" and advisers:
            try:
                adviser_id = int(adviser_value)
            except (TypeError, ValueError):
                errors.append("Select a career adviser to activate your support.")
            else:
                adviser = db.execute(
                    "SELECT id FROM users WHERE id = ? AND role = 'career_adviser' AND account_status = 'active'",
                    (adviser_id,),
                ).fetchone()
                if not adviser:
                    errors.append("The selected adviser is not available. Please choose another adviser.")
        elif role == "jobseeker":
            account_status = "awaiting_adviser"
        elif role == "career_adviser":
            phone = None

        if not errors:
            try:
                db.execute(
                    """INSERT INTO users
                       (email, password_hash, role, full_name, phone, assigned_adviser_id, created_at, account_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        email,
                        generate_password_hash(password),
                        role,
                        full_name,
                        phone or None,
                        adviser_id,
                        utc_now(),
                        account_status,
                    ),
                )
                db.commit()
                flash("Your account has been created. Please sign in.", "success")
                return redirect(url_for("auth.login"))
            except Exception as exc:
                db.rollback()
                # A generic message avoids exposing account-existence details.
                if "UNIQUE constraint failed: users.email" in str(exc):
                    flash("We could not create this account with those details. Check the information and try again.", "error")
                else:
                    current_app.logger.exception("Registration failed")
                    flash("We could not create your account. Please try again.", "error")
        else:
            for error in errors:
                flash(error, "error")

    return render_template("register.html", advisers=advisers)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        db = get_db()
        identity_hash = _login_identity(email)

        if _rate_limited(db, identity_hash):
            flash("Sign-in failed. Check your details or try again later.", "error")
            return render_template("login.html"), 429

        user = db.execute(
            "SELECT id, email, password_hash, role, full_name, account_status FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            _record_failure(db, identity_hash)
            flash("Sign-in failed. Check your details and try again.", "error")
            return render_template("login.html"), 401

        db.execute("DELETE FROM login_attempts WHERE identity_hash = ?", (identity_hash,))
        db.commit()
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]
        session["csrf_token"] = __import__("secrets").token_urlsafe(32)
        return redirect(url_for("index"))

    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
