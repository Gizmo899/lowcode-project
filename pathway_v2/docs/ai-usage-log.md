# AI-usage log: Pathway

This log is a graded part of CA2. It feeds the AI Fluency declaration (Delegation, Description, Discernment, Diligence). Add an entry every time AI does something meaningful for your project, including the times it got things wrong. Paste prompts **exactly** as you typed them.

## Tools I used

| Tool | Version or plan | What I used it for |
|---|---|---|
| Claude.ai | free | schema, data layer, web app, tests, fixing |

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
- **Tool:** ChatGPT
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


### Entry 6: Generating table of unspecified decision made by agent

- **Date:** 2026-11-25
- **Tool:** Claude.ai
- **Task (why I used AI here):** I asked Claude.ai about `prompts/05-what-did-you-decide.md` "Decisions I made that you did not specify"
- **Prompt (verbatim):**

  ```text
Do not change any files. Look back over everything you have done in this conversation and
in this project today.

List every decision you made that I did not explicitly specify. Include names you chose,
data types, limits, default values, delete behaviour (ON DELETE), error handling, libraries,
file locations, and anything you removed or rewrote.

Give me a table with these columns:
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |

Then tell me which ONE of these decisions you think I should check first, and why.

- `Database Design`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| Table and field names |	cv, job_application, follow_up_reminder, notification; assigned_adviser_id, decided_by, file_data, advert_url, due_on, is_read, kind |	Plural names; the old app's names |	Readable and consistent |	The app and docs must use these exact names, and a rename needs a new migration |
| Stored words	| Roles jobseeker/adviser. CV: waiting_for_review/approved/rejected. Applications: applied/interview/rejected/withdrawn. Reminders: pending/sent/skipped. Notifications: nudge/digest/cv_decision |	Capitalised words; the old app's words	| Lowercase with underscores is easy to check	| Anything stored under the old words no longer matches |
| Data types |	Ids are INTEGER, most fields are TEXT, CV files are BLOB, is_read is 0/1, dates are date-only text (your rule) |	Timestamps with times; a true/false type |	SQLite has no date or boolean type |	No time-of-day ordering within a day |
| Date checks and defaults |	A date is valid only if SQLite returns it unchanged. uploaded_at and created_on default to today's date in UTC |	Irish date; full timestamps |	Simple, and it catches 2026-02-30 |	UTC can be a day behind Irish time for an hour after midnight in summer. The app passes the Irish date in practice |
| Email, phone, password rules in the database |	Email ignores capitals (English letters only). Phone is unique and blank means empty. No email or phone format rule. password_hash is only NOT NULL |	Format checks; a hash length check |	You said "unique" and "capitals ignored" |	Odd emails pass the database (the app checks them), and an empty hash would be accepted |
| Text lengths |	None in the database. The app limits name 120, phone 40, company and job title 160, CV title 120, notes and comment 4,000, link 2,048 |	Limits as CHECK rules |	Most numbers come from the old app |	A direct database write skips them |
| Advert link rule |	Must start http:// or https:// in any capitals, and have no spaces. Tabs and line breaks aren't checked |	Stricter |	Your wording |	Odd links get through |
| CV file type check |	Extra typeof = blob rule, and the file can't be empty |	Size check only |	Text would otherwise slip past the byte limit |	None found |
- `Delete behaviour`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| Reminders when their application is deleted | CASCADE (marked GUESS, not explicitly confirmed) | RESTRICT; SET NULL | Follows your privacy reason and the old app | Low. A reminder is useless without its application |
| Rule 3 reason wording | "The comment stays because it is part of the jobseeker's CV record" (marked GUESS) | Your own words | I wrote it from your answer | The reason on record isn't yours |
- `Database rules versus app rules`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| Role rules as 14 triggers | The role never changes, only jobseekers own CVs, applications and notifications, only an adviser can be linked or decide, and a decision must name the owner's adviser. New CVs and applications must start as waiting or applied | CHECK rules (can't do this); app-only | You asked for roles enforced by the data | Triggers are hidden logic and harder for a beginner to read |
| One waiting reminder per application | A partial unique index | App check | Makes a double run harmless | None found |
| Adviser choice "once only" | The database blocks switching, but allows emptying the link (matches the old app; GUESS) | Block emptying too | The delete rule needs emptying | A direct database edit could empty it and re-choose. The app prevents this |
| Rules left to the app | Future date, no move back to "applied", password rules, real Word/PDF content, hiding the phone | Triggers | Your answers | Skipped if someone bypasses the app |
- `Automations`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| Nudge timing | First due 7 days after the date applied. After each send, the next is due 7 days later. Editing the date applied doesn't move a waiting reminder | Count from when it was saved; send once (the old app) | Your repeat rule | An old application entered late nudges at once, and a ghosted one nudges every week with no cap |
| Events done in app code, not by triggers | Marked GUESS | Database triggers | Matches the old app, easier to read | A change made directly in the database wouldn't create or cancel a reminder |
| CV decision notification | Message names the CV and outcome, not the comment | Include the comment | Keeps personal text out of notifications | None found |
| Digest | Created at the first hourly run on Monday from 8:00 Irish time, once per Monday, only for jobseekers with applications. Figures on a new /digest page | Catch up on later days | Your Monday 8:00 rule | If the computer is off all Monday, that week is skipped |
| Tidy-up job (new, not asked for) | The hourly script deletes read notifications and sent or skipped reminders older than 90 days | No automatic deletion; other periods | Your data protection requirement needs a retention period | It deletes data by itself using numbers I invented, and the privacy page tells users "90 days" |
| 30-day log and backup retention | Written in data-protection.md, but nothing enforces it | Add log rotation | I needed a period for the document | The document claims something the code doesn't do |
| Scheduling | One script, tools/run_automations.py, every hour, taking the database path, printing counts as JSON, using a throwaway secret key | A scheduler library | Your option B | The cron and Task Scheduler steps are untested on a real machine |
| Irish time | Python's zoneinfo for Europe/Dublin. Without tzdata (Windows) it silently uses UTC | Require tzdata | No new library | On Windows, the digest hour and "no future date" shift by an hour in summer |
- `Who sees what, and how the app behaves`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| Who can register as an adviser | Anyone, as in the old app. I didn't add a control | Invitation code; manual accounts; approval | I left it open (open point A) | A fake adviser chosen by a jobseeker could see that jobseeker's CVs and notes |
| Choosing an adviser | Required at sign-up if advisers exist. Can be done later if none was chosen or the adviser left, and that choice is once only too | Always optional | Matches the old app | Low |
| Advisers' own phone | Not collected | Optional | The old app hid it | Low |
| CV rules | Several CVs per jobseeker. An adviser decides a waiting CV once. A comment on an approval is refused. Renaming doesn't reset the decision | Allow re-deciding; one current CV | Simplest fit with the data model | An adviser can't fix a mistaken decision |
| Application form | Stage can't be chosen on a new application. After leaving "applied", that option disappears. Date picker stops at today | Show every stage | Enforces your "no move back" rule | None found |
| Password details | Capital letter means A to Z only. Special means not a letter, digit or space | Count accented capitals | Your wording | An accented capital alone is refused |
| Sign-up message | Now says "that email is already in use" (the old app was vague) | Vague message | The threat analysis says it's unavoidable | It reveals which emails have accounts |
| Sessions and cookies | Kept the old settings: 8 hours, SameSite Lax, Secure by environment setting | Stricter | Not asked to change | None new |
- `Error handling`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| Rejected data | Roll back, show a mapped friendly message, never the raw database text. Unknown cases get a generic message | Show the raw message | Your AGENTS.md rule | Generic message is less helpful |
| Error pages | Not yours, or missing, gives 404. Wrong role gives 403. An unsigned-in download gives 401. A second adviser choice gives 403 | Always 404 | Mostly the old app | 403 versus 404 can reveal which pages exist |
- `Code, libraries and file location`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| get_connection(path=None) | One connection per web request inside the app, a new one for scripts and tests; foreign keys on, rows by column name, wait up to 5 seconds when locked | Default app.db in the project folder, or DATABASE_PATH as a fixed path with no waiting | One function everywhere, as your rules ask | app.db replaces the old default path |
| Where SQL lives | Only in db.py and tools/migrate.py; functions take the owner or adviser id, so the check is in the query | SQL in routes | Safer and tested | db.py is long |
| tools/migrate.py | I wrote it; it remembers applied files in a schema_migration table and runs each file as one script | The kit's tool; PRAGMA user_version | You didn't upload the kit's | A failure part-way leaves a half-built database |
| Libraries | None added; requirements.txt unchanged; pytest not required | APScheduler | Your "no new libraries" habit | None
Output location | pathway_v3/ and a zip in the outputs area; your original zip untouched | Editing your folder in place | Safe to compare | You must copy it over yourself |
| Upload request limit | 1 MB plus 100,000 bytes, with an environment override | Exactly 1 MB | The form's own overhead needs room | Slightly bigger requests are accepted before the exact check |
- `What I removed or rewrote`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| Whole-app port | Rewrote app.py, utils.py, 7 route and automation modules and 12 templates, and added digest.html | Only the application routes | A partial port can't work | Large change, though 124 tests pass |
| Features dropped | Failed sign-in limiting, run history, CV version history and separate review records, the awaiting-adviser column, the adviser notifications page, the init-db command, CVs on disk, the 5 MB limit, the block on advisers closing accounts, required phone, joined dates, the "Successful" card (now "Interviews") | Add tables for them | None of these tables are in your data model | Weaker sign-in protection, lost history, and no old data carried over |
| Files not carried over | Old schema.sql, architecture.md, both diagrams, the old README and tests, .env, the live database, private_uploads | Keep them | They describe the old structure | You only have them in your original zip |
| .gitignore | Rewrote it, fixing the leading space before *.db, and added *.log | Leave it | The old rule probably didn't work | None |
| Privacy page | Rewrote the text to match data-protection.md | Leave it | The old text was out of date | It's a public statement built on my guessed numbers |
- `Documents and tests`
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |
| Flow diagram, threat analysis, data protection | 9 flows, 4 trust boundaries, 2 data stores. Lawful basis "contract", you or your institution as controller, retention numbers as proposals | Different boundaries; consent | A first draft you could correct | Legal wording isn't checked |
| Edits to your data-model.md | Replaced the "known differences" section and added a change-log row | Leave it | The old section described code that no longer exists | You didn't ask me to edit it |
| AGENTS.md text | I drafted the wording and the reasons in rows 3 to 12, and reversed my earlier "no triggers" note | Your words | You asked how to update it | Reasons in your table aren't yours |
| Tests | 124 tests in five files, including one raw-connection demo. They assert SQLite's wording. I broke rules on purpose in temporary copies to check the tests | Fewer tests | AGENTS.md requires constraint tests | Exact error wording could differ in another SQLite version |

- **Which one to check first**
Check who may register as an adviser. Everything else on this list either follows your answers, is easy to see in the app, or is low-stakes. This one decides whether the role protection protects anything. All the database rules and tests pass, but anyone can still register as an adviser.
 ```

- **What it produced:** table of decisions made by Claude.ai
- **Decision:** Accepetd
- **Why:** It is a list of decision made by Claude.ai to adapt the Flask app `pathway` to the database. Nothing to modify.
- **What I checked:** none
- **Commit:** `Store data in SQLite: db.py with foreign keys on, parameterised queries, constraint tests`

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
