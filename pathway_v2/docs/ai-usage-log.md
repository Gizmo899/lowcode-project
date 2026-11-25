# AI-usage log: [YOUR APP NAME]

This log is a graded part of CA2. It feeds the AI Fluency declaration (Delegation, Description, Discernment, Diligence). Add an entry every time AI does something meaningful for your project, including the times it got things wrong. Paste prompts **exactly** as you typed them.

## Tools I used

| Tool | Version or plan | What I used it for |
|---|---|---|
| Claude.ai | free | schema, data layer, web app, tests |

## Log entries

Copy the block below for each entry.

---

### Entry [2]: Generate the initial schema

- **Date:** 2026-11-23
- **Tool:** Claude.ai
- **Task (why I used AI here):** turning my finished `docs/data-model.md` into SQL. I had already decided the tables and the delete rule myself; typing CREATE TABLE statements is the kind of mechanical job AI is good at.
- **Prompt (verbatim):**

  ```text
  Read docs/data-model.md and AGENTS.md.

Create ONE file, schema/001_initial.sql, that builds exactly the tables, fields and rules in
docs/data-model.md, using SQLite syntax.
- Do not change any other file.
- Do not add tables or fields I did not list.
- Use the delete rule I wrote in docs/data-model.md. If it is missing, STOP and ask me.
- Store dates as TEXT in YYYY-MM-DD form.
- Put a short comment on each line that has a rule (NOT NULL, UNIQUE, CHECK, REFERENCES).

After the file, explain each constraint in one line of plain English.
Then list any decision you made that I did not specify.
 ```

What each constraint does

user

id PRIMARY KEY AUTOINCREMENT: every person gets a unique number that is never reused.
full_name NOT NULL: a name is required.
full_name CHECK: the name can't be blank or only spaces.
email NOT NULL: an email is required.
email COLLATE NOCASE UNIQUE: no two accounts share an email, and capital letters are ignored.
password_hash NOT NULL: a password hash is required (never the real password).
phone UNIQUE: no two people share a phone number, and many can leave it empty.
phone CHECK: a blank phone must be stored as NULL, never as empty text.
role NOT NULL: everyone has a role.
role CHECK: the role is only jobseeker or adviser.
assigned_adviser_id REFERENCES user ON DELETE SET NULL: it must point to a real user. If that adviser is deleted, the link empties and the jobseeker stays (Delete rule 2).
Table CHECK: only a jobseeker can have an assigned adviser.
Trigger role_never_changes: a role can't be changed after the account exists.
Triggers adviser_must_be_adviser (insert and update): the linked person must have the role adviser.
Trigger adviser_choice_is_once_only: an adviser can't be switched directly to a different one.

cv

id PRIMARY KEY AUTOINCREMENT: each CV has a unique number.
jobseeker_id NOT NULL: every CV has an owner.
jobseeker_id REFERENCES user ON DELETE CASCADE: the owner must exist, and deleting the jobseeker deletes their CVs (Rule 1).
title NOT NULL and CHECK: a title is required and can't be blank.
file_name NOT NULL: the file name is required.
file_type NOT NULL and CHECK: the type is required and must be pdf, doc or docx.
file_data NOT NULL: the file itself is required.
file_data CHECK (blob): the file must be stored as bytes, so the size check counts bytes.
file_data CHECK (size): the file can't be empty and can't exceed 1,048,576 bytes.
uploaded_at NOT NULL DEFAULT: today's date is filled in automatically.
uploaded_at CHECK: it must be a real YYYY-MM-DD date.
status NOT NULL DEFAULT and CHECK: it starts as waiting_for_review and can only be one of the three stages.
decided_by REFERENCES user ON DELETE SET NULL: it must be a real user. If that adviser is deleted, the CV stays and only this link empties (Rule 3).
decided_at CHECK: if given, it must be a real YYYY-MM-DD date.
comment CHECK: a comment can't be blank, so leave it empty instead.
Table CHECK: waiting means no decision, adviser or comment; approved needs a decision date and no comment; rejected needs a decision date and may have a comment.
Triggers owner_must_be_jobseeker (insert and update): a CV can't belong to an adviser.
Trigger new_cv_starts_waiting: a new CV can't be added already decided.
Trigger decider_must_be_owners_adviser: only the adviser assigned to the CV's owner can be recorded as its decider.
Trigger decision_needs_owners_adviser: when a CV leaves "waiting", the decider must be named and must be the owner's adviser.

job_application

id PRIMARY KEY AUTOINCREMENT: each application has a unique number.
jobseeker_id NOT NULL REFERENCES user ON DELETE CASCADE: it has an owner who must exist, and deleting the jobseeker deletes their applications (Rule 1).
company_name and job_title, NOT NULL and CHECK: both are required and can't be blank.
date_applied NOT NULL and CHECK: it is required and must be a real YYYY-MM-DD date. The future-date ban stays in the app.
status NOT NULL DEFAULT and CHECK: it starts as applied and can only be applied, interview, rejected or withdrawn.
advert_url CHECK: if given, it must start with http:// or https:// and contain no spaces.
notes: optional, no rule.
Triggers owner_must_be_jobseeker (insert and update): an application can't belong to an adviser.
Trigger new_starts_applied: a new application can't be added at any other stage.

follow_up_reminder

id PRIMARY KEY AUTOINCREMENT: each reminder has a unique number.
application_id NOT NULL REFERENCES job_application ON DELETE CASCADE: it belongs to a real application, and deleting the application deletes its reminders.
due_on NOT NULL and CHECK: the due date is required and must be a real date.
status NOT NULL DEFAULT and CHECK: it starts as pending and can only be pending, sent or skipped.
processed_on CHECK: if given, it must be a real date.
created_on NOT NULL DEFAULT and CHECK: today's date is filled in automatically and must be a real date.
Table CHECK: pending means no processed date, and sent or skipped needs one.
Unique index (WHERE status = 'pending'): an application can never have two waiting reminders.

notification

id PRIMARY KEY AUTOINCREMENT: each notification has a unique number.
user_id NOT NULL REFERENCES user ON DELETE CASCADE: it has an owner who must exist, and deleting the jobseeker deletes their notifications.
kind NOT NULL and CHECK: it is required and must be nudge, digest or cv_decision.
message NOT NULL and CHECK: it is required and can't be blank.
created_at NOT NULL and CHECK: it is required, supplied by the app, and must be a real date.
is_read NOT NULL DEFAULT 0 and CHECK: it starts unread and can only be 0 or 1.
Triggers owner_must_be_jobseeker (insert and update): a notification can't belong to an adviser.
  ```

- **What it produced:** `schema/001_initial.sql` with 5 tables (user, cv, job_application, follow_up_reminder, notification)
- **Decision:** Modified
- **Why:** The SQlite file included AUTOINCREMENT in INTEGER PRIMARY KEY.  I removed AUTOINCREMENT, so now SQLite gives each new row the highest id that currently exists, plus 1. If the newest row has been deleted, its number can be used again.
- **What I checked:** I verified it read it field by field and noticed the difference with data-model
- **Decisions the AI made that I did not specify:** 
| Foreign keys: I did not put PRAGMA foreign_keys = ON in the file, because your rules say it lives in get_connection() in db.py.
| Triggers: the role rules need 14 triggers, because SQLite can't express them with CHECK. The one extra index is the "one waiting reminder" rule, not a performance index.
| Starting stages: I enforced "a new CV starts as waiting" and "a new application starts as applied" with insert triggers. Your data model states both as rules.
| Decision trigger: at the moment a CV is decided, decided_by must be filled in and must be the owner's adviser. After that it may become blank, as the data model says.
| File check: I added typeof(file_data) = 'blob', which isn't in the data model. Without it, text could slip past the size check, because text length counts characters, not bytes.
| Date check: a date is valid only if SQLite gives it back unchanged. That rejects 2026-02-30, 15/11/2026 and dates with a time.
| Date default: the automatic dates use date('now'), which is UTC. Irish time is ahead of UTC in summer, so for the first hour after midnight the date can be one day behind. The app can supply the Irish date instead.
| URL check: http:// and https:// match in any capitals, and only spaces are refused, not tabs or line breaks.
| Email check: NOCASE only ignores capitals for the English letters A to Z.
| Length limits: I set none on names, titles or notes.
| Once-only adviser choice: the database blocks switching straight from one adviser to another. It can't tell a jobseeker emptying their own link from the delete rule doing it, so the app must not let jobseekers empty it.
| Raw error text: SQLite's raw error text includes my -- comments for CHECK rules, so the app must show friendly messages, as AGENTS.md says.
| Comments: continuation lines inside a multi-line rule share the comment on the line above.
- **Commit:** git commit -m "Add initial schema from data model"

### Entry 3: Rewrite Flask web app basing on SQLite schema

- **Date:** 2026-11-24
- **Tool:** Claude.ai
- **Task (why I used AI here):** rewriting my flask web app 'pathway' moving it onto SQLite schema '001_initial.sql'. 
- **Prompt (verbatim):**

  ```text
  Rewrite my Flask task routes to use this SQLite schema. Use parameterised queries with ? placeholders — never string formatting or f-strings in SQL. Enable PRAGMA foreign_keys = ON on each connection. Return a 404 if a task id does not exist.
  ```

- **What it produced:** `pathway_v2` web app updated
- **Decision:** Accepted
- **Why:** The app runs correctly on the browser and it has a memory. It has passed all the 114 tests.
- **What I checked:** I ran `python tools/migrate.py app.db`, then ran `python app.py` and checked it on the browser.  I stored some data inside the app to check if it has a memory, and it worked out.
- **Decisions the AI made that I did not specify:** 
| Scope: I moved the whole app, not just one set of routes, because a partial move can't work (applications point at the new user table). I treated "task" as job application.
| Database file: the default is now app.db in the project folder, overridable with DATABASE_PATH.
| Connection function: get_connection(path=None) gives one connection per web request and a fresh one for scripts and tests.
| Tidy-up job: I implemented it with the proposed 90-day periods, marked GUESS in your docs.
Reminder dates: reminders are due date_applied plus 7 days, and each next one is due 7 days after it was sent. Editing the date applied does not move a waiting reminder.
| Digest timing: the digest notification is created at the first hourly run on Monday from 8:00 Irish time, and the figures live on a new /digest page.
| Choosing an adviser: a jobseeker must pick an adviser at sign-up if any exist, and can pick one later from the profile when none was chosen or the adviser has left.
| Passwords: a capital letter means A to Z only, so an accented capital doesn't count.
| Adviser pages: advisers don't give a phone number, and I removed their empty notifications page. They can decide only a CV that is still waiting. A comment on an approval is refused with a message.
| Messages and uploads: sign-up now says an email or phone is "already in use". The upload limit is 1 MB for the file, and the request limit is 100 KB larger so the form fits. The file-content checks from the old app are kept.
| Windows: Irish time uses Python's built-in zoneinfo, which needs the tzdata package on Windows. I noted this in the README.
| Privacy page: I rewrote its text to match docs/data-protection.md
- **Commit:** -

### Entry 4: Write tests-constraints

- **Date:** 2026-11-24
- **Tool:** Claude.ai
- **Task (why I used AI here):** Write tests in tests/test_constraints.py using Python's built-in unittest.
- **Prompt (verbatim):**

  ```text
Read AGENTS.md, docs/data-model.md, 001_initial_1.sql and db.py.

Write tests in tests/test_constraints.py using Python's built-in unittest (they must also run
with pytest). Each test must create a fresh temporary database by running the files in
schema/ in number order, and must never touch app.db.

Write one test for EACH of these, each one trying to put BAD data in and checking it is REJECTED:
- a duplicate value in a UNIQUE field
- a value that breaks a CHECK rule
- a missing value in a required (NOT NULL) field
- a row pointing at a [PARENT] that does not exist (foreign key), using db.get_connection()
- my delete rule: [RESTRICT: deleting a parent with children is blocked / CASCADE: the
  children are deleted too / SET NULL: the children's link is emptied]
Also write:
- one test that saves a record, closes the connection, opens the file again and finds it
- one test that asking for an id that does not exist returns None (not an error)

Do not change my app, db.py or the schema to make a test pass. If a test fails, tell me why.
Tell me the exact command to run the tests on [Windows / Mac].
Then list any decision you made that I did not specify.
  ```

- **What it produced:** `tests_constraints.py`
- **Decision:** Accepted
- **Why:** All 10 tests pass, both with unittest and with pytest, and app.db was never created. No test failed, so there is nothing to explain.
- **What I checked:** 
| UNIQUE: a duplicate email (also with different capitals) and a duplicate phone number are rejected.
| CHECK: a role that doesn't exist, a CV file type that isn't allowed, a file over 1 MB, an impossible date, a read flag of 2 and an impossible reminder date are all rejected.
| NOT NULL: eight different missing required values are rejected, for example a user with no name and a CV with no file.
| Foreign key: a reminder pointing at an application that doesn't exist is rejected. I used this one because a foreign key from a CV or application to a missing user is stopped by a trigger first, which wouldn't prove the foreign key works.
| Delete rules: your three rules each have a test: a jobseeker's children are deleted, an adviser's jobseekers stay with the link emptied, and the CVs an adviser decided keep their outcome, date and comment.
| Persistence: a saved record is found again after the connection is closed and the file is reopened.
| Not found: nine lookup functions return None for an id that doesn't exist.
- **Decisions the AI made that I did not specify:** 
| Placeholders: I read the parent as user, because jobseekers and advisers are the parents, and tested all three of your delete rules.
| Building the database: each test builds its database by running the files in schema/ in order, inside the test itself. It does not use tools/migrate.py, so the tests don't depend on that tool.
| Raw connection: I added one extra test that opens a plain sqlite3.connect on purpose, only to show an orphan row gets in without the pragma. It's the only connection in the tests that doesn't use get_connection(). Delete it if you prefer.
| Error text: the tests check SQLite's own wording, for example "UNIQUE constraint failed: user.email". That is stable, but a very different SQLite version could word it differently.
| Safety guard: each test asserts that its database path is not app.db.
| Test style: each category test tries several bad rows as sub-tests, with a label for each. Passwords in the tests are a made-up hash string, never a real password.
| Overlap: tests/test_schema.py already covers these rules and more. I left it alone, and this file is the one-per-type set you asked for.
- **Commit:** `Add project/task schema with constraints; parameterised queries`


### Entry 5: Fixing the connection cleanup

- **Date:** 2026-11-25
- **Tool:** Claude.ai
- **Task (why I used AI here):** The test closes its original connection, opens a replacement connection, closes that replacement, and then opens a third connection. However, the test cleanup handler still refers to the original connection. The third connection is therefore left open, preventing Windows from deleting test.db when the temporary directory is cleaned up.
- **Prompt (verbatim):**

  ```text
I ran "python -m unittest -v" on this flask app. It has found this error: ERROR: test_data_survives_closing_and_reopening_the_database_file (tests.test_schema.PersistenceTests.test_data_survives_closing_and_reopening_the_database_file)

Can you fix this issue creating a new app with the fixed code or leaked test connection in a .zip archive?
This is the complete error message:

Traceback (most recent call last):
File "C:\Users\Fabio\AppData\Local\Python\pythoncore-3.15-64\Lib\shutil.py", line 701, in _rmtree_unsafe
os.unlink(fullname)
^^^^^^^^^^
PermissionError: [WinError 32] Impossibile accedere al file. Il file è utilizzato da un altro processo: 'C:\\Users\\Fabio\\AppData\\Local\\Temp\\tmpt5lilq9d\\test.db'  During handling of the above exception, another exception occurred:  Traceback (most recent call last): File "C:\Users\Fabio\AppData\Local\Python\pythoncore-3.15-64\Lib\tempfile.py", line 1055, in cleanup self._rmtree(self.name, ignore_errors=self._ignore_cleanup_errors) ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ File "C:\Users\Fabio\AppData\Local\Python\pythoncore-3.15-64\Lib\tempfile.py", line 1035, in _rmtree _shutil.rmtree(name, onexc=onexc, dir_fd=dir_fd, _onexc_kwargs=True) ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ File "C:\Users\Fabio\AppData\Local\Python\pythoncore-3.15-64\Lib\shutil.py", line 859, in rmtree _rmtree_impl(path, dir_fd, onexc) ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^ File "C:\Users\Fabio\AppData\Local\Python\pythoncore-3.15-64\Lib\shutil.py", line 705, in _rmtree_unsafe onexc(os.unlink, fullname, err) ~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^ File "C:\Users\Fabio\AppData\Local\Python\pythoncore-3.15-64\Lib\tempfile.py", line 1002, in onexc _os.unlink(base, dir_fd=dir_fd) ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^ PermissionError: [WinError 32] Impossibile accedere al file. Il file è utilizzato da un altro processo: 'C:\\Users\\Fabio\\AppData\\Local\\Temp\\tmpt5lilq9d\\test.db'
  ```

- **What it produced:** `tests_helpers.py` and `tests/test_schema.py`
- **Decision:** Accepted
- **Why:** `tests/helpers.py`: cleanup now calls `self.close_connection()`, which closes whatever connection is currently on `self.conn` (safe to call twice), so a swapped-in connection is never left open.
- **What I checked:** I verified there are no remaining open handles on the database file at cleanup time (by checking /proc/self/fd during teardown), and no unclosed database warnings appear anywhere in the suite. The full suite passes: 124 tests, OK, run from a fresh copy of the packaged zip. Both python -m unittest -v and python -m unittest tests.test_schema -v work.
- **Decisions the AI made that I did not specify:** none
- **Commit:** `"Add constraint tests (UNIQUE, CHECK, NOT NULL, FK, delete rule, persistence)"`

---


## Worked example (from the club equipment loans demo in Session 5)

### Entry 2: Generate the initial schema

- **Date:** 2026-11-11
- **Tool:** Claude Code
- **Task (why I used AI here):** turning my finished `docs/data-model.md` into SQL. I had already decided the tables and the delete rule myself; typing CREATE TABLE statements is the kind of mechanical job AI is good at.
- **Prompt (verbatim):**

  ```text
  Read docs/data-model.md and AGENTS.md. Create ONE file, schema/001_initial.sql, that builds
  exactly the tables, fields and rules in docs/data-model.md, using SQLite syntax. Do not
  change any other file. Do not add tables or fields I did not list. After the file, explain
  each constraint in one line of plain English, then list any decision you made that I did
  not specify.
  ```

- **What it produced:** `schema/001_initial.sql` with three tables (member, equipment, loan).
- **Decision:** Modified
- **Why:** it wrote `ON DELETE CASCADE` on both foreign keys even though my data model says RESTRICT. Cascade would wipe a member's loan history if they left the club, and the committee needs that history for insurance. I changed both to `ON DELETE RESTRICT`. It also added `AUTOINCREMENT`, which SQLite does not need here; I left that in and noted it.
- **What I checked:** read the SQL field by field against my data model (checklist in the lab guide), ran `python tools/migrate.py app.db`, then tried three bad inserts with `tools/sql.py`. The orphan loan got in until I used `--fk`, which led to the PRAGMA rule in AGENTS.md.
- **Decisions the AI made that I did not specify:** CASCADE on both foreign keys (changed), AUTOINCREMENT on ids (kept), `DEFAULT (date('now'))` on borrowed_on (kept).
- **Commit:** `Add initial schema from data model (delete rule: RESTRICT)`

> The tool responses in this worked example are illustrative of what agents commonly do. Your log must describe what YOUR tool actually did.
