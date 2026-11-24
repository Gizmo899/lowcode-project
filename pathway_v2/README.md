# Pathway: Job Application Tracker

A Flask and SQLite app. Jobseekers track their job applications and upload CVs. Each jobseeker chooses one career adviser, who approves or rejects their CVs and can see their applications (read-only).

The design lives in `docs/`: `data-model.md` (the source of truth), `data-flow.md`, `threat-analysis.md` and `data-protection.md`. The project rules for AI coding agents are in `AGENTS.md`.

## Set up and run

Use Python 3.10 or newer. On a Mac type `python3` wherever this guide says `python`.

```text
python -m venv .venv
.venv\Scripts\activate            (Windows)     source .venv/bin/activate     (Mac and Linux)
pip install -r requirements.txt
```

1. Copy `.env.example` to `.env` and put a real secret after `FLASK_SECRET_KEY=` (the file tells you how to make one). Never commit `.env`.
2. Build the database from the files in `schema/`:

```text
python tools/migrate.py app.db
```

3. Start the app:

```text
flask --app wsgi run --debug
```

The database file is `app.db` in the project folder. To use another file, set `DATABASE_PATH`. The app never creates or changes tables by itself: to change the database, add a new numbered file such as `schema/002_description.sql` and run the migration tool again. Never edit a migration that has already been applied.

## Tests

```text
python -m unittest discover -s tests -t .
```

(`python -m pytest` also works if you have pytest installed.) The tests use a temporary database and never touch `app.db`.

## Scheduled automation (follow-up nudges, weekly digest, tidy-up)

Flask cannot run jobs on a timer by itself, so one script, `tools/run_automations.py`, does all the automatic work, and your computer's own scheduler starts it **every hour, on the hour**. See `docs/data-model.md` (section "Automations") for exactly what it does. It works out Irish time itself, so the computer's time zone setting does not matter, and it prints counts only, never personal data.

### Step 1: run it by hand first

```text
python tools/run_automations.py app.db
```

It prints one line of counts. Run it a second time straight away: the second run must create nothing new, because every reminder is marked sent or skipped once it has been processed and the digest checks that it does not already exist today.

### Step 2: schedule it

**Windows (Task Scheduler)**

1. In a terminal type `where python` and copy the first line (the full path to Python). Use the Python inside your `.venv` folder if you made one.
2. Copy the full path of this project's top folder (the one that contains `app.db`).
3. Open **Task Scheduler** and choose **Create Task** (not "Create Basic Task"). On the **General** tab give it a name.
4. **Triggers** tab, **New**: **On a schedule**, **Daily**, start today at `00:00`. Tick **Repeat task every** and choose **1 hour**, **for a duration of** **1 day**.
5. **Actions** tab, **New**, **Start a program**:
   - **Program/script:** the Python path from step 1
   - **Add arguments:** `tools\run_automations.py app.db`
   - **Start in:** the project folder from step 2 (no quotation marks)
6. **Settings** tab: tick **Run task as soon as possible after a scheduled start is missed**.
7. Right-click the task, choose **Run**, and check that **Last Run Result** says it completed successfully.

To stop it: right-click the task and choose **Disable** or **Delete**.

**Mac and Linux (cron)**

1. Type `which python3` and copy the result. In the project's top folder type `pwd` and copy that too.
2. Type `crontab -e` and add this one line, replacing the two paths:

```text
0 * * * * cd /full/path/to/your/project && /full/path/to/python3 tools/run_automations.py app.db >> automations.log 2>&1
```

3. Save, then type `crontab -l` to check it is there. After the next full hour look at `automations.log`.

To stop it: `crontab -e` again and delete the line. On a Mac, if the project is in Documents, Desktop or Downloads, macOS may block cron. Either move the project or give cron access in System Settings, Privacy and Security, Full Disk Access.

### Things to know

- **The computer must be on.** If it is off at 8:00 on Monday the digest is created at the next hourly run that same Monday. If it is off all Monday, that week's digest is skipped.
- Logs are never committed: `*.log` is in `.gitignore`.
- On Windows, Irish time needs the `tzdata` package (`pip install tzdata`). Without it the script falls back to UTC.
