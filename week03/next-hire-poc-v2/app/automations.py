from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update
from .extensions import db
from .models import Application, Digest, Notification, User, utcnow


STAGES = ("saved", "applied", "interview", "offer")


def generate_weekly_digests(app, week_start=None):
    """Create one in-app pipeline digest per active jobseeker for the given week."""
    with app.app_context():
        if week_start is None:
            local_today = datetime.now(ZoneInfo(app.config["APP_TIMEZONE"])).date()
            week_start = local_today - timedelta(days=local_today.weekday())
        created = 0
        jobseekers = User.query.filter_by(role="jobseeker", status="active").all()
        for user in jobseekers:
            existing = Digest.query.filter_by(jobseeker_id=user.id, week_start=week_start).first()
            if existing:
                continue
            open_apps = Application.query.filter_by(jobseeker_id=user.id, outcome=None).all()
            counts = {stage: sum(1 for item in open_apps if item.stage == stage) for stage in STAGES}
            today = datetime.now(ZoneInfo(app.config["APP_TIMEZONE"])).date()
            deadlines = [
                {"application_id": item.id, "company": item.company, "job_title": item.job_title,
                 "deadline": item.deadline.isoformat()}
                for item in open_apps
                if item.deadline and today <= item.deadline <= today + timedelta(days=7)
            ]
            deadlines.sort(key=lambda row: row["deadline"])
            digest = Digest(jobseeker_id=user.id, week_start=week_start, stage_counts=counts,
                            upcoming_deadlines=deadlines, generated_at=utcnow())
            db.session.add(digest)
            created += 1
        db.session.commit()
        return created


def _nudge_conditions(now):
    """Conditions under which an application's follow-up nudge is due and still unsent."""
    return (
        Application.stage == "applied",
        Application.outcome.is_(None),
        Application.nudge_due_at.is_not(None),
        Application.nudge_due_at <= now,
        Application.nudge_sent_at.is_(None),
    )


def _due_application_ids(now):
    """Ids of applications that look due right now. This is only a candidate list:
    another scheduler instance may act on any of them before we do, so every candidate
    must still be claimed with _claim_nudge() before a notification is created."""
    return db.session.execute(
        select(Application.id).where(*_nudge_conditions(now)).order_by(Application.id)
    ).scalars().all()


def _claim_nudge(application_id, now):
    """Atomically claim the nudge for one application.

    A single UPDATE ... WHERE nudge_sent_at IS NULL (plus the due conditions, re-checked
    against the current row) is the claim. The database lets exactly one concurrent
    caller change the row, so exactly one caller sees rowcount == 1. Everyone else gets
    False and must not create a notification. The caller commits the claim together
    with the notification, or rolls both back.
    """
    result = db.session.execute(
        update(Application)
        .where(Application.id == application_id, *_nudge_conditions(now))
        # updated_at is set explicitly to keep the previous behaviour, where the ORM
        # update that stamped nudge_sent_at also refreshed updated_at.
        .values(nudge_sent_at=now, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def process_due_nudges(app, now=None):
    """Create one in-app follow-up notification for every qualifying application.

    Safe to run from several scheduler instances at once: each application is claimed
    with an atomic UPDATE (see _claim_nudge) and the claim and the notification are
    committed together, one application per transaction.
    """
    with app.app_context():
        now = now or utcnow()
        created = 0
        for application_id in _due_application_ids(now):
            try:
                if not _claim_nudge(application_id, now):
                    # Another worker claimed it first, or it stopped qualifying
                    # (stage/outcome/dates edited) since we listed it. Do nothing.
                    db.session.rollback()
                    continue
                item = db.session.get(Application, application_id)
                contact_name = next((contact.name for contact in sorted(item.contacts, key=lambda c: c.id)), None)
                greeting = contact_name or "Hiring Team"
                applied_on = item.date_applied.strftime("%d %b %Y") if item.date_applied else "the application date"
                body = (
                    f"Subject: Following up on my application – {item.job_title}\n\n"
                    f"Dear {greeting},\n\n"
                    f"I applied for the {item.job_title} position at {item.company} on {applied_on} and "
                    "wanted to follow up to confirm that my application was received. I remain\n"
                    "very interested in the role and would welcome the chance to discuss my\n"
                    "experience. Please let me know if you need any further information.\n\n"
                    f"Kind regards,\n{item.jobseeker.full_name}"
                )
                db.session.add(Notification(
                    user_id=item.jobseeker_id,
                    type="follow_up_nudge",
                    application_id=item.id,
                    title=f"No reply yet from {item.company}",
                    body=body,
                    is_read=False,
                ))
                db.session.commit()
                created += 1
            except Exception:
                # Roll back the claim too, so the nudge is retried on the next run
                # instead of being marked as sent without a notification.
                db.session.rollback()
                app.logger.exception("Could not create the follow-up nudge for application %s", application_id)
        return created


def _add_jobs(scheduler, app, timezone):
    scheduler.add_job(lambda: generate_weekly_digests(app), CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=timezone),
                      id="weekly_pipeline_digest", replace_existing=True, max_instances=1)
    scheduler.add_job(lambda: process_due_nudges(app), IntervalTrigger(hours=1, timezone=timezone),
                      id="hourly_follow_up_nudges", replace_existing=True, max_instances=1)


def start_scheduler(app):
    """Start the two PoC jobs on a background thread of the *current* process.

    Called explicitly by run.py (the `python run.py` development entrypoint). It is
    never called from create_app(), so WSGI workers, the Flask CLI and tests do not
    start a scheduler by accident.
    """
    if app.extensions.get("job_tracker_scheduler"):
        return app.extensions["job_tracker_scheduler"]
    timezone = ZoneInfo(app.config["APP_TIMEZONE"])
    scheduler = BackgroundScheduler(timezone=timezone, daemon=True)
    _add_jobs(scheduler, app, timezone)
    scheduler.start()
    app.extensions["job_tracker_scheduler"] = scheduler
    return scheduler


def run_scheduler(app):
    """Run the two PoC jobs in the foreground of a dedicated process until interrupted.

    This is what `flask --app run.py run-scheduler` runs. Use it when the web app is
    served by `flask run` or a WSGI server, and run it in exactly one process.
    """
    timezone = ZoneInfo(app.config["APP_TIMEZONE"])
    scheduler = BlockingScheduler(timezone=timezone)
    _add_jobs(scheduler, app, timezone)
    print(f"Scheduler running (weekly digest: Mondays 08:00, follow-up nudges: hourly, timezone: {timezone}). Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")
