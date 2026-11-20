"""Flask application factory for the Job Application Tracker PoC."""

import os
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, session, url_for

from db import init_app
from security import csrf_token, validate_csrf


def create_app(test_config=None):
    project_dir = Path(__file__).resolve().parent
    instance_dir = project_dir / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, instance_path=str(instance_dir), instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev-only-change-this-secret-before-deployment"),
        DATABASE=os.environ.get("DATABASE_PATH", str(instance_dir / "job_tracker.sqlite")),
        UPLOAD_FOLDER=os.environ.get("CV_UPLOAD_FOLDER", str(instance_dir / "private_uploads" / "cv")),
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_BYTES", 5 * 1024 * 1024)),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0").lower() in {"1", "true", "yes"},
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        TRUSTED_HOSTS=None,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    init_app(app)

    from auth import bp as auth_bp
    from jobseekers import bp as jobseekers_bp
    from advisers import bp as advisers_bp
    from applications import bp as applications_bp
    from cv_management import bp as cv_management_bp
    from notifications import bp as notifications_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(jobseekers_bp)
    app.register_blueprint(advisers_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(cv_management_bp)
    app.register_blueprint(notifications_bp)

    @app.before_request
    def protect_state_changes():
        validate_csrf()

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'",
        )
        return response

    @app.context_processor
    def inject_template_values():
        return {"csrf_token": csrf_token, "now_year": datetime.now().year}

    @app.get("/")
    def index():
        if not session.get("user_id"):
            return render_template("home.html")
        if session.get("role") == "career_adviser":
            return redirect(url_for("advisers.dashboard"))
        return redirect(url_for("jobseekers.dashboard"))

    @app.get("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", code=400, message=getattr(error, "description", "The request could not be processed.")), 400

    @app.errorhandler(401)
    def unauthorised(_error):
        return render_template("error.html", code=401, message="Please sign in to access this page."), 401

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="You do not have permission to access this information."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="The page or record could not be found."), 404

    @app.errorhandler(413)
    def too_large(_error):
        flash("The upload exceeds the configured 5 MB limit.", "error")
        return redirect(url_for("cv_management.manage")), 303

    @app.cli.command("init-db")
    def init_db_command():
        from db import init_db
        init_db()
        print("Initialised the Job Application Tracker database.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
