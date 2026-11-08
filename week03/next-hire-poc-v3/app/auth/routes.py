from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(_home_for(current_user))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "jobseeker")
        errors = []
        if len(full_name) < 2:
            errors.append("Enter your full name.")
        if not email or "@" not in email or len(email) > 255:
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if role not in ("jobseeker", "adviser"):
            errors.append("Choose Jobseeker or Career adviser.")
        if email and User.query.filter(db.func.lower(User.email) == email).first():
            errors.append("An account with that email already exists.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("auth/register.html")
        user = User(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            status="pending" if role == "adviser" else "active",
        )
        db.session.add(user)
        db.session.commit()
        if role == "adviser":
            flash("Your adviser account is awaiting admin approval. You can sign in once it is approved.", "info")
            return redirect(url_for("auth.login"))
        login_user(user)
        flash("Welcome! Your jobseeker account is ready.", "success")
        return redirect(url_for("jobseeker.dashboard"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_home_for(current_user))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Email or password is incorrect.", "error")
        elif user.role == "adviser" and user.status == "pending":
            flash("Your adviser account is awaiting admin approval.", "info")
        elif user.role == "adviser" and user.status == "rejected":
            flash("Your adviser account application was rejected. Please contact the administrator.", "error")
        elif user.status != "active":
            flash("This account is not active.", "error")
        else:
            login_user(user)
            flash(f"Welcome back, {user.full_name.split()[0]}.", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(_home_for(user))
    return render_template("auth/login.html")


@bp.post("/logout")
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))


def _home_for(user):
    return {
        "jobseeker": url_for("jobseeker.dashboard"),
        "adviser": url_for("adviser.reviews"),
        "admin": url_for("admin.advisers"),
    }.get(user.role, url_for("auth.login"))
