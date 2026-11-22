# Prompt 03: Wire the database into my app

**When:** Lab 2. **Writes code?** Yes: `db.py` and the parts of your app that store data.

## Why this prompt is shaped like this

This is the prompt most likely to go wrong, because the agent is now editing your real app. So the **constraints** are the longest: one connection function with the PRAGMA, `?` placeholders only, 404 for not found, and "do not rewrite files I did not mention". **Context** points at three files (AGENTS.md, the data model, the schema) so it does not invent new tables. **Specificity** shows the exact shape of a safe query rather than describing it. If the result is not right, use **iteration** from Session 2: paste the actual error or the actual line back to the agent, rather than starting a new chat.

## The prompt

```text
Read AGENTS.md, docs/data-model.md and schema/001_initial.sql. Then look at how my app
currently stores its data: [NAME THE FILE, e.g. app.py, and how it stores data now, e.g.
"a Python list called tasks" or "I don't know, please find it and tell me before changing it"].

Make my app store its data in the SQLite database instead:
1. Create db.py with a get_connection() function that opens the database file (path from the
   environment variable DATABASE_PATH, default app.db), sets row_factory to sqlite3.Row,
   and runs PRAGMA foreign_keys = ON. Every database access in the app must use this function.
2. In db.py, write simple functions to create, read, list, update and delete [MY MAIN
   ENTITIES]. Use ? placeholders for every value, e.g.
   conn.execute("SELECT * FROM loan WHERE id = ?", (loan_id,))
   Never build SQL with f-strings, .format(), % or +.
3. When something is not found, the function returns None and the route returns a 404 page.
4. When the database rejects data (sqlite3.IntegrityError), show a friendly message on the
   form instead of crashing.
5. Remove any Python lists or dictionaries that were holding app data.
6. Do not create or change tables: the schema is managed by tools/migrate.py.
7. Do not rewrite files or features I did not mention. Do not add new libraries.

When you are done, list every file you changed and what you changed in each, in plain English.
Then list any decision you made that I did not specify.
```

## After it answers

1. Run your app. Add a record through the app itself.
2. **Stop the app** (Ctrl+C) and start it again. Is the record still there? If yes, your app has a memory.
3. Run `python tools/check_db.py app.db --src .` (Mac: `python3`). Fix every cross.
4. Commit: `git add .` then `git commit -m "Store data in SQLite via db.py (PRAGMA on, parameterised queries)"`.
