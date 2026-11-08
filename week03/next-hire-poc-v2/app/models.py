from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from .extensions import db


def utcnow():
    return datetime.utcnow()


application_contacts = db.Table(
    "application_contacts",
    db.Column("application_id", db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True),
    db.Column("contact_id", db.Integer, db.ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    cvs = db.relationship("CV", back_populates="jobseeker", cascade="all, delete-orphan", foreign_keys="CV.jobseeker_id")
    applications = db.relationship("Application", back_populates="jobseeker", cascade="all, delete-orphan", foreign_keys="Application.jobseeker_id")
    contacts = db.relationship("Contact", back_populates="jobseeker", cascade="all, delete-orphan", foreign_keys="Contact.jobseeker_id")


class CV(db.Model):
    __tablename__ = "cvs"
    id = db.Column(db.Integer, primary_key=True)
    jobseeker_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    version_label = db.Column(db.String(80), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    mime_type = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="submitted")
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_comment = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    jobseeker = db.relationship("User", back_populates="cvs", foreign_keys=[jobseeker_id])
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    applications = db.relationship("Application", back_populates="cv")


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    jobseeker_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company = db.Column(db.String(180), nullable=False)
    job_title = db.Column(db.String(180), nullable=False)
    job_url = db.Column(db.String(500), nullable=True)
    location = db.Column(db.String(180), nullable=True)
    work_mode = db.Column(db.String(20), nullable=True)
    salary_range = db.Column(db.String(120), nullable=True)
    date_applied = db.Column(db.Date, nullable=True)
    deadline = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    stage = db.Column(db.String(20), nullable=False, default="saved")
    outcome = db.Column(db.String(20), nullable=True)
    cv_id = db.Column(db.Integer, db.ForeignKey("cvs.id"), nullable=True)
    cover_letter_ref = db.Column(db.String(180), nullable=True)
    nudge_due_at = db.Column(db.DateTime, nullable=True)
    nudge_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    jobseeker = db.relationship("User", back_populates="applications", foreign_keys=[jobseeker_id])
    cv = db.relationship("CV", back_populates="applications")
    contacts = db.relationship("Contact", secondary=application_contacts, back_populates="applications", lazy="select")
    notifications = db.relationship("Notification", back_populates="application", cascade="all, delete-orphan")


class Contact(db.Model):
    __tablename__ = "contacts"
    id = db.Column(db.Integer, primary_key=True)
    jobseeker_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    company = db.Column(db.String(180), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(80), nullable=True)
    job_title = db.Column(db.String(160), nullable=True)
    linkedin_url = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    jobseeker = db.relationship("User", back_populates="contacts", foreign_keys=[jobseeker_id])
    applications = db.relationship("Application", secondary=application_contacts, back_populates="contacts")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)
    title = db.Column(db.String(240), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")
    application = db.relationship("Application", back_populates="notifications")


class Digest(db.Model):
    __tablename__ = "digests"
    id = db.Column(db.Integer, primary_key=True)
    jobseeker_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start = db.Column(db.Date, nullable=False)
    stage_counts = db.Column(db.JSON, nullable=False)
    upcoming_deadlines = db.Column(db.JSON, nullable=False)
    generated_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    jobseeker = db.relationship("User")
    __table_args__ = (UniqueConstraint("jobseeker_id", "week_start", name="uq_digest_jobseeker_week"),)
