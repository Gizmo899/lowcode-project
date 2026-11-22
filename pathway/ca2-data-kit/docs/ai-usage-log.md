# AI-usage log: [YOUR APP NAME]

This log is a graded part of CA2. It feeds the AI Fluency declaration (Delegation, Description, Discernment, Diligence). Add an entry every time AI does something meaningful for your project, including the times it got things wrong. Paste prompts **exactly** as you typed them.

## Tools I used

| Tool | Version or plan | What I used it for |
|---|---|---|
| [e.g. Cursor / Claude Code / GitHub Copilot / Gemini / ChatGPT] | [free / paid / version] | [schema, data layer, tests ...] |

## Log entries

Copy the block below for each entry.

---

### Entry [N]: [short title]

- **Date:** [YYYY-MM-DD]
- **Tool:** [tool and model, if shown]
- **Task (why I used AI here):** [what you delegated, and why you chose AI for it]
- **Prompt (verbatim):**

  ```text
  [paste the exact prompt]
  ```

- **What it produced:** [files changed or created, in one or two lines]
- **Decision:** Accepted / Modified / Rejected
- **Why:** [what made you accept, change or throw it away]
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
