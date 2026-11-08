import os
from pathlib import Path
from datetime import date as calendar_date
from zoneinfo import ZoneInfo
from flask import Flask, abort, redirect, url_for
from flask_login import current_user
from .extensions import db, login_manager, csrf


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    upload_dir = os.getenv("UPLOAD_DIR", "instance/uploads")
    if not os.path.isabs(upload_dir):
        upload_dir = str(Path(app.root_path).parent / upload_dir)
    Path(upload_dir).mkdir(parents=True, exist_ok=True)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = f"sqlite:///{Path(app.instance_path) / 'app.db'}"
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me-before-deployment"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        UPLOAD_DIR=upload_dir,
        MAX_UPLOAD_MB=int(os.getenv("MAX_UPLOAD_MB", "5")),
        MAX_CONTENT_LENGTH=(int(os.getenv("MAX_UPLOAD_MB", "5")) * 1024 * 1024) + 512 * 1024,
        APP_TIMEZONE=os.getenv("APP_TIMEZONE", "UTC"),
        NUDGE_DELAY_DAYS=int(os.getenv("NUDGE_DELAY_DAYS", "7")),
        AUTO_INIT_DB=os.getenv("AUTO_INIT_DB", "true").lower() == "true",
        START_SCHEDULER=os.getenv("START_SCHEDULER", "true").lower() == "true",
    )
    if test_config:
        app.config.update(test_config)
        Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "info"
    csrf.init_app(app)

    from .auth.routes import bp as auth_bp
    from .jobseeker.routes import bp as jobseeker_bp
    from .adviser.routes import bp as adviser_bp
    from .admin.routes import bp as admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(jobseeker_bp)
    app.register_blueprint(adviser_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    def index():
        if current_user.is_authenticated:
            if current_user.role == "jobseeker":
                return redirect(url_for("jobseeker.dashboard"))
            if current_user.role == "adviser":
                return redirect(url_for("adviser.reviews"))
            if current_user.role == "admin":
                return redirect(url_for("admin.advisers"))
        return redirect(url_for("auth.login"))

    @app.template_filter("datefmt")
    def datefmt(value):
        return value.strftime("%d %b %Y") if value else "—"

    @app.template_filter("datetimefmt")
    def datetimefmt(value):
        return value.strftime("%d %b %Y, %H:%M UTC") if value else "—"

    @app.template_filter("isodatefmt")
    def isodatefmt(value):
        if not value:
            return "—"
        try:
            return calendar_date.fromisoformat(value).strftime("%d %b %Y")
        except (TypeError, ValueError):
            return value

    @app.context_processor
    def inject_navigation_data():
        unread = 0
        if current_user.is_authenticated and current_user.role == "jobseeker":
            from .models import Notification
            unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return {"nav_unread_count": unread}

    @app.errorhandler(413)
    def too_large(_error):
        from flask import flash
        flash(f"The upload is too large. Maximum file size is {app.config['MAX_UPLOAD_MB']} MB.", "error")
        return redirect(request_referrer_or("jobseeker.cvs"))

    from flask import request
    def request_referrer_or(endpoint):
        return request.referrer or url_for(endpoint)

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables and insert demo records if the database is empty."""
        from .seed import seed_demo
        db.create_all()
        seed_demo(app)
        print("Database initialised and demo data ensured.")

    @app.cli.command("run-digest")
    def run_digest_command():
        from .automations import generate_weekly_digests
        count = generate_weekly_digests(app)
        print(f"Generated {count} digest(s). Existing weekly digests were left unchanged.")

    @app.cli.command("run-nudges")
    def run_nudges_command():
        from .automations import process_due_nudges
        count = process_due_nudges(app)
        print(f"Created {count} follow-up notification(s).")

    @app.cli.command("run-scheduler")
    def run_scheduler_command():
        """Run the weekly-digest and follow-up-nudge jobs in this process (blocking)."""
        from .automations import run_scheduler
        run_scheduler(app)

    if app.config["AUTO_INIT_DB"]:
        with app.app_context():
            db.create_all()
            from .seed import seed_demo
            seed_demo(app)

    # The scheduler is deliberately NOT started here. create_app() also runs for the
    # Flask CLI, for tests and once per WSGI worker, so starting jobs from the factory
    # made the outcome depend on how the process happened to be launched. The process
    # that owns the jobs starts them explicitly instead: `python run.py` (when
    # START_SCHEDULER=true) or `flask --app run.py run-scheduler`.

    return app


@login_manager.user_loader
def load_user(user_id):
    from .models import User
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
