# AI-usage log: [YOUR APP NAME]

This log is a graded part of CA2. It feeds the AI Fluency declaration (Delegation, Description, Discernment, Diligence). Add an entry every time AI does something meaningful for your project, including the times it got things wrong. Paste prompts **exactly** as you typed them.

## Tools I used

| Tool | Version or plan | What I used it for |
|---|---|---|
| Claude.ai | free | schema, data layer, tests |

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
