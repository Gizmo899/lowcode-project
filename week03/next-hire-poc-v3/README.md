# Next Hire — Job Application Tracker PoC

A local proof-of-concept implementation of the supplied Job Application Tracker specification. It uses Python 3.11+, Flask, Jinja2, Flask-Login, Flask-WTF, SQLAlchemy, SQLite and APScheduler.

> **Demo only.** The seeded accounts and default development secret are intentionally simple. Do not expose this app to the public internet or use real personal data without a security, privacy and deployment review.

## Included features

- Self-registration and email/password login for jobseekers and career advisers. Passwords are hashed; adviser registration starts as `pending`.
- Admin approval/rejection for advisers.
- Job application create, read, update and delete; all specified application fields, stage progression, outcomes and colour-coded badges.
- CV upload (PDF/DOCX, 5 MB maximum), immutable versions, secure random storage names and authenticated downloads.
- Standalone contact book with many-to-many application linking.
- CV review queue, adviser approval/change-request workflow and immutable review history.
- Adviser read-only access to every active jobseeker's profile, CVs and applications. Contacts are not exposed to advisers.
- Dashboard deadlines, in-app notifications, copyable follow-up templates and weekly pipeline digests.
- Monday 08:00 digest and hourly follow-up nudge scheduler jobs, plus idempotent Flask CLI commands (`run-digest`, `run-nudges`, `run-scheduler`).
- Synthetic demo data and placeholder CV PDFs created automatically on first run.

## Quick start

1. Use Python 3.11 or newer.
2. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   # macOS / Linux
   source .venv/bin/activate
   # Windows PowerShell
   # .venv\\Scripts\\Activate.ps1
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`. For a local demo, the defaults work. Change `SECRET_KEY` before any non-demo use.
4. Start the application:

   ```bash
   python run.py
   ```

5. Open http://127.0.0.1:5000.

The SQLite database is created at `instance/app.db`; uploaded files are stored in `instance/uploads/`. The app creates tables and inserts seed data automatically on first run. To initialise explicitly:

```bash
flask --app run.py init-db
```

## Demo accounts

| Role | Email | Password | Notes |
|---|---|---|---|
| Admin | `admin@example.com` | `admin123` | Approve/reject advisers |
| Adviser | `adviser1@example.com` | `adviser123` | Active adviser; review queue and jobseeker profiles |
| Adviser | `adviser2@example.com` | `adviser123` | Pending adviser; login is blocked until approved |
| Jobseeker | `jobseeker1@example.com` | `jobseeker123` | Rich sample pipeline, three CV states, contacts and a nudge-ready application |
| Jobseeker | `jobseeker2@example.com` | `jobseeker123` | Second synthetic jobseeker profile and pipeline |

All records and CV files are synthetic placeholders. Do not replace them with real personal data in a shared demo.

## Demonstrating the flows

### Jobseeker

1. Sign in as `jobseeker1@example.com`.
2. Review Overview and Upcoming deadlines.
3. Open Applications; sort by deadline or date applied, inspect outcomes, edit a record, or add an application.
4. Open Contacts to add/edit contacts, then link/unlink them from an application detail page.
5. Open My CVs. Existing sample versions show Submitted, Approved and Changes requested states. Uploading a new PDF/DOCX creates a new Submitted version.
6. Open Digest to view the pre-generated pipeline snapshot.
7. Run `flask --app run.py run-nudges` to create the seeded eight-day-old Applied application's follow-up notification. Open Notifications and use Copy message.

### Adviser

1. Sign in as `adviser1@example.com`.
2. Open Review queue. Review a Submitted CV and either approve it or request changes (a comment is mandatory for changes).
3. Open Jobseekers to inspect profiles, CV history and read-only application details. Adviser views do not expose contacts.

### Admin

1. Sign in as `admin@example.com`.
2. Open Pending advisers. The seeded `adviser2@example.com` account is awaiting approval. Approve it, then sign in as that adviser.
3. New adviser registrations also appear in this queue.

## Automations

- **Weekly digest:** APScheduler generates one digest per active jobseeker each Monday at 08:00 in `APP_TIMEZONE` (default `UTC`). It is stored in SQLite and shown in-app; no email is sent.
- **Follow-up nudge:** the hourly job selects applications whose `nudge_due_at` has passed, where stage is still `applied`, outcome is empty and no nudge has already been sent. It creates one in-app notification and stamps `nudge_sent_at`. `nudge_due_at` is the start (00:00) of the day `NUDGE_DELAY_DAYS` after the applied date **in `APP_TIMEZONE`**, stored as UTC like every other timestamp, so nudges become due at local midnight rather than at 00:00 UTC. Existing rows keep their old value until the application's stage or applied date is next changed.
- **Run on demand:**

  ```bash
  flask --app run.py run-digest
  flask --app run.py run-nudges
  ```

Both jobs are safe to re-run. Weekly digests are unique by jobseeker/week. Nudges are sent once per application: each one is claimed with an atomic database update (`nudge_sent_at IS NULL` is part of the `UPDATE ... WHERE`) and committed together with its notification, so two scheduler instances running at the same time cannot both send it.

### Who starts the scheduler

The scheduler is never started by the app factory. It starts only where you ask for it:

| How you run the app | Scheduler |
|---|---|
| `python run.py` | Started in that process when `START_SCHEDULER=true` (the default). Set `START_SCHEDULER=false` to turn it off. |
| `flask --app run.py run`, gunicorn or another WSGI server | **Not started.** Run `flask --app run.py run-scheduler` in one separate process. |
| `flask --app run.py init-db` / `run-digest` / `run-nudges` | Not started. |

`run-scheduler` blocks until you press Ctrl+C. Run it in exactly one process; the nudge claim keeps a second copy from sending duplicates, but it would still waste work and add noise to the logs.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | Development-only fallback | Flask session signing; set a long random value |
| `DATABASE_URL` | Local SQLite at `instance/app.db` | SQLAlchemy database URI |
| `UPLOAD_DIR` | `instance/uploads` | Private CV file storage |
| `MAX_UPLOAD_MB` | `5` | Maximum CV file size |
| `APP_TIMEZONE` | `UTC` | IANA timezone name (e.g. `Europe/Dublin`). Defines "today" for default application dates and dashboard deadlines, the weekly digest week, follow-up nudge due times and the scheduler. An invalid value stops the app at startup |
| `NUDGE_DELAY_DAYS` | `7` | Days after application date before follow-up |
| `AUTO_INIT_DB` | `true` | Create and seed database on first app startup |
| `START_SCHEDULER` | `true` | Start the APScheduler jobs inside `python run.py`. Ignored by `flask run`, WSGI servers and the CLI; use `run-scheduler` for those |

To run without background jobs, set `START_SCHEDULER=false`. The app factory never starts the scheduler, so automated tests and CLI commands are unaffected by this setting.

## Tests

The project includes a small standard-library `unittest` smoke suite. With dependencies installed:

```bash
python -m unittest discover -s tests -v
```

## Project layout

```text
job-tracker/
├── app/
│   ├── auth/                 # registration and authentication
│   ├── jobseeker/            # applications, contacts, CVs, dashboard
│   ├── adviser/              # CV review and read-only profiles
│   ├── admin/                # adviser approval
│   ├── automations.py        # scheduled jobs and idempotent workers
│   ├── models.py             # SQLAlchemy schema
│   ├── timeutils.py          # "today" and local-day→UTC conversion (APP_TIMEZONE)
│   ├── templates/            # Jinja2 server-rendered pages
│   └── static/               # responsive CSS and copy helper
├── instance/uploads/         # private CV storage; ignored by git
├── tests/
├── run.py
├── requirements.txt
└── .env.example
```

## PoC limitations

As specified, this PoC does not send email, provide password resets or email verification, offer data export/account deletion, provide calendar views, or implement analytics. In production, serve the app with a production WSGI server and run the jobs in a single dedicated process (`flask --app run.py run-scheduler`) or a proper worker/queue. Add rate limiting, secure production secrets, stricter operational logging, malware scanning and a full security/privacy review before handling real CVs.
