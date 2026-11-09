from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
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


def process_due_nudges(app, now=None):
    """Create one in-app follow-up notification for every qualifying application."""
    with app.app_context():
        now = now or utcnow()
        due = Application.query.filter(
            Application.stage == "applied",
            Application.outcome.is_(None),
            Application.nudge_due_at.isnot(None),
            Application.nudge_due_at <= now,
            Application.nudge_sent_at.is_(None),
        ).all()
        created = 0
        for item in due:
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
            item.nudge_sent_at = now
            created += 1
        db.session.commit()
        return created


def start_scheduler(app):
    """Start the two idempotent in-process PoC jobs."""
    if app.extensions.get("job_tracker_scheduler"):
        return app.extensions["job_tracker_scheduler"]
    timezone = ZoneInfo(app.config["APP_TIMEZONE"])
    scheduler = BackgroundScheduler(timezone=timezone, daemon=True)
    scheduler.add_job(lambda: generate_weekly_digests(app), CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=timezone),
                      id="weekly_pipeline_digest", replace_existing=True, max_instances=1)
    scheduler.add_job(lambda: process_due_nudges(app), IntervalTrigger(hours=1, timezone=timezone),
                      id="hourly_follow_up_nudges", replace_existing=True, max_instances=1)
    scheduler.start()
    app.extensions["job_tracker_scheduler"] = scheduler
    return scheduler
