# Project rules for AI coding agents

This file tells any AI coding agent (Cursor, GitHub Copilot, Gemini CLI, Claude Code and others) how to work on this project. Read it before making changes, and follow it every time.

## About this project (the student fills this in)

- **What the app does, in one or two sentences:** It is a Job Application Tracker.  It has to be accessed by two users with sign-in and log-in options: Jobseekers and Career advisers.
It has to give the possibility to create job application to jobseekers, to add CVs and contact details in the core app.
It has to report a weekly pipeline digest as a scheduled automation.
It has to give the chance of a follow-up nudge if there is no reply from employers as a triggered automation after a job application.
As approval steps, careers advisers have to be able to sign off the jobseekers'CV.

- **The main things (entities) the app stores:** Jobseekers, Career advisers, CVs, job applications.

- **How they connect:** A jobseeker can fill the job application and upload his CVs for tracking purpose.  Career advisers can check those CVs, approving or rejecting them.  Advisers can also see the job application read-only.
- **The full data model lives in:** `docs/data-model.md`. Treat it as the source of truth. If the code and that file disagree, stop and ask me.

### Decisions I have made (the student fills this in, and keeps it up to date)

| Decision | What I chose | Why |
|---|---|---|
| Deleting a [PARENT] that still has [CHILDREN] | [RESTRICT / CASCADE / SET NULL] | [YOUR REASON IN PLAIN ENGLISH] |
| [ANOTHER DECISION] | [WHAT YOU CHOSE] | [WHY] |

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

## Tests

- Write tests with Python's built-in `unittest` (they must also run under `pytest`).
- For every constraint, write a test that tries to put **bad data** in and checks it is **rejected**: a duplicate, a value the CHECK rule forbids, a missing required field, a row pointing at something that does not exist, and the delete rule in action.
- Write one test that proves data survives closing and reopening the database file.
- Tests must use a temporary database, never the real `app.db`.

## How to work with me

- Change only what I asked for. Do not rewrite files I did not mention.
- Explain what you did in plain English. I am not a professional developer.
- **At the end of every reply, list any decision you made that I did not specify** (names, types, limits, delete behaviour, libraries, anything). Use the heading "Decisions I made that you did not specify". If there were none, say so.
