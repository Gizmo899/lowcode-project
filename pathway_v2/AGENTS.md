# Project rules for AI coding agents

This file tells any AI coding agent (Cursor, GitHub Copilot, Gemini CLI, Claude Code and others) how to work on this project. Read it before making changes, and follow it every time.

## About this project (the student fills this in)

- **What the app does, in one or two sentences:** A Job Application Tracker. Two kinds of people sign in with email and password: jobseekers and career advisers. Each jobseeker chooses one adviser. Jobseekers record job applications and upload CVs (Word or PDF). Their adviser approves or rejects their CVs and can see their applications, read-only. An adviser only ever sees their own jobseekers' data. Automatic jobs: a follow-up nudge when an application has no reply after 7 days (started by events), a notification when an adviser decides a CV, and a weekly digest every Monday at 8:00 Irish time. All of them appear as in-app notifications.

- **The main things (entities) the app stores:** Users (jobseekers and career advisers share one list, each with a role), CVs, job applications, follow-up reminders and notifications.

- **How they connect:** Each jobseeker has one adviser, chosen once. A jobseeker has many CVs, applications and notifications. An application has follow-up reminders. An adviser decides only the CVs of their own jobseekers: approve, or reject with an optional comment. CVs and applications are not linked to each other.
- **The full data model lives in:** `docs/data-model.md`. Treat it as the source of truth. If the code and that file disagree, stop and ask me.
Also read docs/data-flow.md, docs/threat-analysis.md and docs/data-protection.md. If the code breaks what they say, stop and ask me.

### Decisions I have made (the student fills this in, and keeps it up to date)

| Decision | What I chose | Why |
|---|---|---|
| Deleting a [PARENT] that still has [CHILDREN] | [RESTRICT / CASCADE / SET NULL] | [YOUR REASON IN PLAIN ENGLISH] |
| Deleting a jobseeker who still has CVs, applications or notifications | CASCADE | Data privacy. Nothing should stay in the database after someone deletes their own account, because the data belongs to them. |
| Deleting an adviser who still has jobseekers linked | SET NULL | An adviser who deletes their own profile cannot affect a jobseeker's profile. Jobseekers are the only owners of their data, so it stays after the adviser leaves. |
| Deleting an adviser who has decided CVs | SET NULL | The CVs belong to the jobseekers. Only "decided by" becomes blank. The outcome, date and comment stay. |
| Jobseekers and advisers | One `user` table with a role, one role per person | Both have the same details. An email or phone number can never belong to two accounts. |
| Adviser link | The jobseeker chooses one adviser, once. An adviser sees only their own jobseekers' CVs and applications (notes yes, phone no). | Advisers should only see the data of people who chose them. |
| Where CV files are kept | Inside the database. Word or PDF only, at most 1,048,576 bytes (1 MB). | One place for all the data. |
| Replacing a CV's file | The CV goes back to "waiting for review" | The adviser approved a different file, so the approval no longer applies. |
| Roles enforced by the database | The role never changes. Only jobseekers own CVs, applications and notifications. Only an adviser can be linked to a jobseeker. Only the linked adviser can decide a CV. | Roles must be enforced by the data itself, not only by hiding buttons. |
| Rules the app checks, not the database | Password rules, no future date applied, no move back to "applied", who is signed in, hiding the phone number from advisers | The database cannot see the plain password, today's date, the old value of a field, or who is signed in. |
| Follow-up nudge | Starts from events. Saving an application creates a waiting reminder due 7 days later. Leaving "applied" cancels it. Sending one creates the next, so it repeats every 7 days. | The nudge must be an event, not just a timer. |
| Scheduled jobs | One script, `tools/run_automations.py`, started every hour by the computer's own scheduler. No scheduler library. | It needs no new library and works even when the web app is off. |
| Notifications | In-app messages, not emails: nudge, digest and CV decision. The digest figures are worked out when it is opened. | It keeps things easier. |

The app checks some rules on purpose, because the database cannot: the password rules, no future date applied, no move back to "applied", who is signed in, and hiding the phone number from advisers. Do not move these into the database. The role rules in the table are enforced by the database with triggers. Do not remove them. Write a test for each role rule and each app-checked rule that tries to break it.

## Technology

- Python with **Flask** for the web app, **SQLite** for the database. Use SQLite syntax, never MySQL or PostgreSQL syntax (for example `AUTOINCREMENT`, never `AUTO_INCREMENT`).
- Use only Python's built-in `sqlite3` module. Do not add an ORM (such as SQLAlchemy) unless I ask for one.
- Keep things simple enough that a beginner can read them.

## Database rules

1. **The schema lives in numbered migration files:** `schema/001_initial.sql`, `schema/002_description.sql` and so on. They are applied in order with `python tools/migrate.py app.db`.
2. **Never edit a migration that has already been applied.** To change the database, add a new numbered file. Never "fix" things by deleting the database.
3. **Every database connection must run `PRAGMA foreign_keys = ON`.** Put this in one function, `get_connection()` in `db.py`, and make every part of the app use that function. SQLite ignores foreign keys without it.
4. **Only parameterised queries.** Values always go in through `?` placeholders, for example `conn.execute("SELECT * FROM loan WHERE id = ?", (loan_id,))`. Never build SQL with f-strings, `.format()`, `%` or `+`.
5. **Constraints belong in the database:** `NOT NULL` for required fields, `UNIQUE` for things that must never repeat, `CHECK` for allowed values and limits, `FOREIGN KEY` for every relationship.
6. **Never choose an `ON DELETE` behaviour by yourself.** Whether deleting a parent row blocks (`RESTRICT`), deletes its children (`CASCADE`) or empties the link (`SET NULL`) is a business decision. Ask me, then record my answer and the reason in `docs/data-model.md`.
7. **The database is the app's memory.** Do not store app data in Python lists, dictionaries or global variables. Data must still be there after the app is stopped and started again.
8. Database files (`*.db`) are never committed to Git. Make sure `.gitignore` contains `*.db`.

## Web app rules

- If something is asked for that does not exist (for example `/loans/999`), return a **404 Not Found** page, never a crash (500).
- If the database rejects data (a constraint fails), show the user a friendly message and keep them on the form. Do not show a Python error page.
- **No secrets in code.** Passwords, API keys and secret keys come from environment variables (for example `os.environ["SECRET_KEY"]`), never typed into a `.py` file.
- Every query must be limited by who is signed in. Advisers only load their own linked jobseekers.

## Tests

- Write tests with Python's built-in `unittest` (they must also run under `pytest`).
- For every constraint, write a test that tries to put **bad data** in and checks it is **rejected**: a duplicate, a value the CHECK rule forbids, a missing required field, a row pointing at something that does not exist, and the delete rule in action.
- Write one test that proves data survives closing and reopening the database file.
- Tests must use a temporary database, never the real `app.db`.
- Write a test where an adviser tries to decide the CV of a jobseeker who is not linked to them, and check it is refused.

## How to work with me

- Change only what I asked for. Do not rewrite files I did not mention.
- Explain what you did in plain English. I am not a professional developer.
- **At the end of every reply, list any decision you made that I did not specify** (names, types, limits, delete behaviour, libraries, anything). Use the heading "Decisions I made that you did not specify". If there were none, say so.
