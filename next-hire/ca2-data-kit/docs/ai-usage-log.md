# AI-usage log: Next-hire

This log is a graded part of CA2. It feeds the AI Fluency declaration (Delegation, Description, Discernment, Diligence). Add an entry every time AI does something meaningful for your project, including the times it got things wrong. Paste prompts **exactly** as you typed them.

## Tools I used

| Tool | Version or plan | What I used it for |
|---|---|---|
| [e.g. Cursor / Claude Code / GitHub Copilot / Gemini / ChatGPT] | [free / paid / version] | [schema, data layer, tests ...] |

## Log entries

Copy the block below for each entry.

---

### Entry [N]: Generate the initial schema

- **Date:** 2026-11-18
- **Tool:** Claude.ai
- **Task (why I used AI here):** turning my finished `docs/data-model.md` into SQL. I had already decided the tables and the delete rule myself; typing CREATE TABLE statements is the kind of mechanical job AI is good at.
- **Prompt (verbatim):**

  ```text
  Read data-model.md

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

id PRIMARY KEY AUTOINCREMENT: every user gets a unique number that is never reused.
NOT NULL on full_name, email, password_hash, phone, role, must_change_password: these can never be left empty.
full_name CHECK: not blank, at most 30 characters.
email UNIQUE: two accounts can’t share an email.
email CHECK: already lower case, exactly one “@”, and a dot somewhere after it.
phone UNIQUE: two accounts can’t share a phone number.
phone CHECK: must be +353 followed by 8 to 10 digits.
role CHECK: only jobseeker, career_adviser or admin.
Unique index user_one_admin: at most one user can have the role admin.
approval_status CHECK: an adviser must be waiting or approved; a jobseeker or the admin must have nothing.
must_change_password DEFAULT and CHECK: starts at 0 and can only be 0 or 1.
temp_password_expires_at CHECK: holds a real YYYY-MM-DD HH:MM:SS exactly when must_change_password is 1, and is empty when it is 0.
linkedin_url CHECK: if given, it starts with http:// or https://, has no spaces, and contains linkedin.com.
city CHECK: if given, not blank and at most 20 characters.
Trigger user_admin_cannot_be_deleted: any attempt to delete the admin is refused.

cv

id PRIMARY KEY AUTOINCREMENT: unique number, never reused.
NOT NULL on jobseeker_id, title, file_name, file_data, review_status: always required.
jobseeker_id REFERENCES … ON DELETE CASCADE: the CV belongs to a real user, and deleting that user deletes the CV.
title CHECK: not blank, at most 30 characters.
file_name CHECK: ends in .pdf, .doc or .docx, in any letter case.
file_data CHECK: at most 5,242,880 bytes.
jobseeker_note CHECK: at most 200 characters.
uploaded_on CHECK: if given, a real YYYY-MM-DD date (no month 13, no 31 February).
review_status DEFAULT and CHECK: starts as waiting_for_review and must be one of the five allowed values.
reviewer_id REFERENCES … ON DELETE SET NULL: points to a real user, and if that user is deleted the link is emptied.
picked_up_at CHECK: if given, a real YYYY-MM-DD HH:MM:SS.
reviewed_on CHECK: if given, a real YYYY-MM-DD date.
review_comment CHECK: at most 200 characters.
Table CHECK (matching rule): the status decides which of reviewer, picked-up time, review date and comment must be filled or empty, exactly as in your table.

application

id PRIMARY KEY AUTOINCREMENT: unique number, never reused.
NOT NULL on jobseeker_id, job_title, company, applied_on, progress: always required.
jobseeker_id REFERENCES … ON DELETE CASCADE: the application belongs to a real user, and deleting that user deletes it.
job_title CHECK: not blank, at most 40 characters.
company CHECK: not blank, at most 30 characters.
applied_on CHECK: a real YYYY-MM-DD date.
progress DEFAULT and CHECK: starts as applied and must be one of the five allowed values.
location CHECK: if given, at most 20 characters.
advert_url CHECK: if given, starts with http:// or https:// and has no spaces.
note CHECK: if given, at most 200 characters.
 

- **What it produced:**  `schema/001_initial.sql` with three tables (user, cv, career application)
- **Decision:** Modified
- **Why:** The problems were rules the data model promised ("a trigger or Python") that the SQL did not enforce, such as "The owner must be a jobseeker" and "the reviewer must be an approved adviser" were marked "Python or trigger". The SQL had neither.  
The data model mentioned safety-net triggers (one-way approval, no CV edits, admin protection). The SQL did not have them.
A few checks that were too loose: emails like @x.ie, a b@x.ie and a@.; a name made only of a new line; an empty CV file; a file called .pdf; a file saved as text; any file-name length were all accepted.
- **What I checked:** [how you verified it: read it field by field, ran tools/check_db.py, ran the tests, restarted the app ...]
- **Decisions the AI made that I did not specify:** [paste the answer to prompt 05, or "none"]
- **Commit:** [the commit message or hash where this landed]

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
