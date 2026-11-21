# Pathway — Job Application Tracker PoC

A beginner-friendly Flask and SQLite application for jobseekers and career advisers. The application implements the uploaded Product and Technical Specification v1.0 dated 20 November 2026.

## Requirements

- Python 3.10 or newer
- Flask 3.x (installed from `requirements.txt`)
- No ORM and no third-party scheduler

## Run locally

From this directory:

```bash
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the dependencies (Flask and python-dotenv):

```bash
pip install -r requirements.txt
```

Create a session secret. The app **will not start** without one, because it uses the secret to sign login cookies and anyone who knows the secret can pretend to be any user. Generate a long random value:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Then give it to the app in either of these ways. A real environment variable wins over `.env` if both are set.

**Option A: a `.env` file (simplest).** Copy `.env.example` to `.env` in this folder and paste the value after `FLASK_SECRET_KEY=`. The app reads `.env` automatically.

**Option B: an environment variable.**

```bash
# macOS / Linux
export FLASK_SECRET_KEY="paste-the-generated-value-here"

# Windows PowerShell
$env:FLASK_SECRET_KEY = "paste-the-generated-value-here"
```

The app refuses to run if the secret is missing, shorter than 32 characters, or one of the example values that appeared in earlier versions of this project. Use a different secret for each deployment. Changing the secret signs everyone out.

Start the app:

```bash
python app.py
```

Open `http://127.0.0.1:5000` in a browser. The SQLite database and private CV directory are created automatically in `instance/` on first start. You can also initialise the schema explicitly (this needs the secret to be set too, because it starts the app):

```bash
flask --app app init-db
```

For a production deployment, set `COOKIE_SECURE=1`, provide a strong, unique `FLASK_SECRET_KEY` from the deployment environment (the app will not start without one), serve the app through HTTPS and a production WSGI server, and keep `instance/` outside the public web root. Do not enable Flask debug mode on a shared or deployed instance.

## Test the application

```bash
python -m unittest discover -s tests -v
```

The tests use temporary SQLite databases and synthetic accounts/files.

## Accounts and core journeys

1. Register a **Career Adviser** account.
2. Register a **Jobseeker** account and select that adviser. If no adviser exists, a jobseeker may register in `awaiting_adviser` state and select one later from their profile.
3. As a jobseeker, add applications, upload a PDF/DOC/DOCX CV and review notifications.
4. Sign in as the assigned adviser to view the jobseeker's contact details, CV and applications. Submit a CV decision with comments.
5. The adviser workspace is read-only for application records.

Email addresses are checked strictly: letters and digits before the `@`, optionally joined by single `.`, `_`, `+`, `-` or `'`, and a normal domain after it. Unusual but technically legal addresses (for example ones with `?`, `&`, `=` or non-English letters) are refused on purpose, because they can change what an email link does. Changing the email address on a profile page asks for your current password.

The application intentionally has only the two specified roles. An account's role cannot be changed. A jobseeker's first adviser assignment cannot be changed. An adviser account cannot be closed while jobseekers remain assigned to it.

## Scheduled automations

The automation entry point is `run_automations.py`. It runs:

- The weekly jobseeker pipeline digest, deduplicated by jobseeker and ISO week.
- All due seven-day reminders, sending a nudge only when the related application is still `Applied`.

Default schedule: **every Monday at 09:00 server-local time**. Add this cron entry on Linux/macOS after replacing the project path and Python path:

```cron
0 9 * * 1 cd /absolute/path/job_tracker && /absolute/path/job_tracker/.venv/bin/python run_automations.py >> automation.log 2>&1
```

On Windows, create a Task Scheduler task with a weekly Monday 09:00 trigger and the action `python C:\absolute\path\job_tracker\run_automations.py`, using the project directory as the working directory.

The automation script does not need `FLASK_SECRET_KEY`, because it never serves a web page or signs a cookie, so it runs from cron without any environment variables.

Run the task manually at any time to test it:

```bash
python run_automations.py
```

Repeated executions in the same ISO week do not create a second weekly digest. Reminder rows are marked `sent` or `skipped` after processing. To test a seven-day reminder without waiting, change a test reminder's `due_at` to a timestamp in the past in the test database, then run the script.

## Files and storage

- `schema.sql` defines the SQLite tables, indexes, checks and adviser-assignment triggers.
- `db.py` creates request-scoped connections and enables `PRAGMA foreign_keys = ON` for every connection.
- `private_uploads/cv` is configured under `instance/`, outside Flask's public `static/` directory.
- CV filenames are generated UUIDs. Original filenames are retained as display metadata only.
- CV download requires an authenticated owner or the owner's assigned adviser.
- Uploads are limited to 5 MB by default and validated using file signatures / document structure as well as extension and MIME allow-list checks.

## Evidence and PoC limitations

See `docs/architecture.md`, `docs/erd.mmd` and `docs/dfd-level-1.mmd` for the ERD, Level-1 DFD, CRUD matrix, STRIDE assessment and proposed GDPR assessment.

This is a proof-of-concept baseline, not a production-readiness or legal-compliance certification. Before using real personal data, the organisation must approve its lawful basis, privacy notice, retention and backup policy, adviser account-closure operations, hosting safeguards and incident response. Malware scanning, production rate limiting at the reverse proxy, password reset, email verification, audit-grade application status history and a complete data-subject-rights workflow are outside this PoC.
