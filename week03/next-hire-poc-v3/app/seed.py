from datetime import timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash
from .extensions import db
from .models import Application, Contact, CV, Digest, User, utcnow
from .timeutils import local_midnight_to_utc, local_today


def _placeholder_pdf(label):
    # Small, valid-enough PDF placeholder for the local demo. It contains no real CV data.
    text = label.replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(out)


def seed_demo(app=None):
    """Insert the specified synthetic demo accounts and records once."""
    if User.query.first():
        return
    admin = User(full_name="Demo Admin", email="admin@example.com", password_hash=generate_password_hash("admin123"), role="admin", status="active")
    adviser = User(full_name="Alex Adviser", email="adviser1@example.com", password_hash=generate_password_hash("adviser123"), role="adviser", status="active")
    pending = User(full_name="Pending Adviser", email="adviser2@example.com", password_hash=generate_password_hash("adviser123"), role="adviser", status="pending")
    seeker1 = User(full_name="Jamie Jobseeker", email="jobseeker1@example.com", password_hash=generate_password_hash("jobseeker123"), role="jobseeker", status="active")
    seeker2 = User(full_name="Taylor Jobseeker", email="jobseeker2@example.com", password_hash=generate_password_hash("jobseeker123"), role="jobseeker", status="active")
    db.session.add_all([admin, adviser, pending, seeker1, seeker2])
    db.session.flush()

    upload_dir = Path(app.config["UPLOAD_DIR"] if app else "instance/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    cvs = []
    for title, version, status, comment in [
        ("Product CV", "v1", "submitted", None),
        ("Product CV", "v2", "approved", "Clear impact statements and a stronger skills section. Approved."),
        ("Product CV", "v3", "changes_requested", "Please add measurable outcomes to the two most recent roles and tighten the profile summary."),
    ]:
        filename = f"demo-{seeker1.id}-{version}.pdf"
        (upload_dir / filename).write_bytes(_placeholder_pdf(f"Demo placeholder: {title} {version}"))
        cv = CV(jobseeker_id=seeker1.id, title=title, version_label=version,
                original_filename=f"product-cv-{version}.pdf", stored_filename=filename,
                mime_type="application/pdf", status=status,
                reviewer_id=adviser.id if status != "submitted" else None,
                reviewed_at=utcnow() if status != "submitted" else None,
                review_comment=comment,
                uploaded_at=utcnow() - timedelta(days={"v1": 5, "v2": 12, "v3": 2}[version]))
        db.session.add(cv)
        cvs.append(cv)
    db.session.flush()

    today = local_today()
    j1_specs = [
        ("Northstar Analytics", "Junior Data Analyst", "saved", None, today - timedelta(days=1), today + timedelta(days=2), "https://example.com/jobs/northstar", "Dublin", "hybrid", "€38k–€45k", "Tailor the project examples."),
        ("Brightside Studio", "Marketing Executive", "applied", None, today - timedelta(days=8), today + timedelta(days=6), "https://example.com/jobs/brightside", "Dublin", "on_site", "€34k–€40k", "Demo nudge: applied eight days ago."),
        ("Loop Labs", "Product Associate", "interview", None, today - timedelta(days=14), today + timedelta(days=4), None, "Remote", "remote", "€42k–€48k", "Prepare product sense examples."),
        ("Orchid Systems", "Business Analyst", "offer", "accepted", today - timedelta(days=28), today - timedelta(days=5), None, "Dublin", "hybrid", "€48k–€55k", "Accepted offer."),
        ("Blue Peak", "Operations Coordinator", "saved", "rejected", None, today + timedelta(days=5), None, "Cork", "on_site", None, "Closed example: rejected."),
        ("Atlas Works", "Project Assistant", "applied", "withdrawn", today - timedelta(days=20), None, None, "Galway", "hybrid", "€32k–€36k", "Withdrew after accepting another interview."),
        ("Riverbank Group", "Graduate Consultant", "interview", "no_reply", today - timedelta(days=35), None, None, "Dublin", "on_site", "€36k–€42k", "No reply after interview."),
        ("Cedar Health", "Service Designer", "offer", None, today - timedelta(days=4), today + timedelta(days=7), None, "Remote", "remote", "€45k–€52k", "Offer stage; decision pending."),
    ]
    seeker1_apps = []
    for idx, spec in enumerate(j1_specs):
        company, title, stage, outcome, applied, deadline, job_url, location, mode, salary, notes = spec
        app_row = Application(jobseeker_id=seeker1.id, company=company, job_title=title, stage=stage,
                              outcome=outcome, date_applied=applied, deadline=deadline,
                              job_url=job_url, location=location, work_mode=mode,
                              salary_range=salary, notes=notes,
                              cv_id=cvs[1].id if idx in (1, 2, 7) else (cvs[0].id if idx == 3 else None),
                              cover_letter_ref="Product role cover letter – Oct 2026" if idx in (1, 2) else None,
                              created_at=utcnow() - timedelta(days=idx + 2),
                              updated_at=utcnow() - timedelta(days=idx))
        if stage == "applied" and outcome is None:
            app_row.nudge_due_at = local_midnight_to_utc(applied + timedelta(days=7))
        db.session.add(app_row)
        seeker1_apps.append(app_row)

    j2_specs = [
        ("Harbour Finance", "Accounts Assistant", "saved", None),
        ("Mosaic Tech", "Customer Success Associate", "applied", None),
        ("Greenline Energy", "Research Assistant", "interview", None),
        ("Paper Kite", "Office Administrator", "offer", "rejected"),
        ("Westward", "Support Analyst", "applied", "no_reply"),
        ("Fable Foods", "Sales Coordinator", "offer", None),
    ]
    seeker2_apps = []
    for idx, (company, title, stage, outcome) in enumerate(j2_specs):
        applied = today - timedelta(days=idx * 3 + 1) if stage != "saved" else None
        deadline = today + timedelta(days=idx + 3) if idx in (0, 2, 5) else None
        row = Application(jobseeker_id=seeker2.id, company=company, job_title=title, stage=stage,
                          outcome=outcome, date_applied=applied, deadline=deadline,
                          location="Dublin", work_mode="hybrid", notes="Synthetic sample application.")
        if stage == "applied" and outcome is None:
            row.nudge_due_at = local_midnight_to_utc(applied + timedelta(days=7))
        db.session.add(row)
        seeker2_apps.append(row)
    db.session.flush()

    contacts = [
        Contact(jobseeker_id=seeker1.id, name="Morgan Lee", company="Brightside Studio", email="morgan@example.com", phone="+353 1 555 0101", job_title="Talent Partner", linkedin_url="https://www.linkedin.com/in/example-morgan", notes="Primary recruitment contact."),
        Contact(jobseeker_id=seeker1.id, name="Avery Quinn", company="Loop Labs", email="avery@example.com", phone="+353 1 555 0102", job_title="Product Lead", notes="Interview panel contact."),
        Contact(jobseeker_id=seeker1.id, name="Riley Chen", company="Northstar Analytics", email="riley@example.com", job_title="Hiring Manager"),
        Contact(jobseeker_id=seeker1.id, name="Sam Patel", company="Orchid Systems", email="sam@example.com", job_title="People Operations"),
    ]
    db.session.add_all(contacts)
    db.session.flush()
    seeker1_apps[1].contacts.append(contacts[0])
    seeker1_apps[2].contacts.append(contacts[1])
    seeker1_apps[0].contacts.append(contacts[2])
    seeker1_apps[3].contacts.append(contacts[3])
    seeker1_apps[7].contacts.append(contacts[0])

    # One example notification plus the specified pre-generated weekly digest.
    week_start = today - timedelta(days=today.weekday())
    existing = Digest.query.filter_by(jobseeker_id=seeker1.id, week_start=week_start).first()
    if not existing:
        open_rows = [row for row in seeker1_apps if row.outcome is None]
        counts = {stage: sum(1 for row in open_rows if row.stage == stage) for stage in ("saved", "applied", "interview", "offer")}
        deadlines = [
            {"application_id": row.id, "company": row.company, "job_title": row.job_title, "deadline": row.deadline.isoformat()}
            for row in open_rows if row.deadline and today <= row.deadline <= today + timedelta(days=7)
        ]
        deadlines.sort(key=lambda row: row["deadline"])
        db.session.add(Digest(jobseeker_id=seeker1.id, week_start=week_start,
                              stage_counts=counts, upcoming_deadlines=deadlines, generated_at=utcnow()))
    db.session.commit()
