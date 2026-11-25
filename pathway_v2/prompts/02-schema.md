# Prompt 02: Generate the schema from my data model

**When:** Lab 1, after you have corrected and committed `docs/data-model.md`. **Writes code?** One SQL file only.

## Why this prompt is shaped like this

**Context:** the agent works from your own data model, so it is translating your design, not inventing one. **Specificity:** one named file, SQLite syntax, dates as TEXT. **Constraints:** change nothing else, add nothing you did not list, stop and ask if the delete rule is missing. Asking for "decisions I did not specify" catches the silent choices (the classic one is `ON DELETE CASCADE`). Session 2's lesson on hallucination still applies: the agent's explanation can be wrong too, so you read the SQL yourself.

## The prompt

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

## After it answers

1. Do **not** accept it yet. Open `schema/001_initial.sql` next to `docs/data-model.md` and go through the checklist in the lab guide, field by field.
2. Fix anything that does not match your design (by hand, or by telling the agent exactly what to change).
3. Copy the prompt and the list of decisions into `docs/ai-usage-log.md`.
4. Apply it: `python tools/migrate.py app.db` (Mac: `python3`).
5. Commit: `git add schema docs` then `git commit -m "Add initial schema from data model"`.
