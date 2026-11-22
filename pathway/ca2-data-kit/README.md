# CA2 Data Layer Kit (Session 5)

This kit helps you give **your own CA2 app** a proper memory: a designed data model, a database with rules that protect it, code that uses it safely, and the evidence to prove it. Everything here uses only what comes with Python (3.10 or newer). You do not need to install anything else, and you do not need the `sqlite3` command-line program.

## What is in the box

| Item | What it is for |
|---|---|
| `AGENTS.md` | Project rules for your AI coding agent (Cursor, Copilot, Gemini CLI and others read this file automatically). You fill in the top section about your app. |
| `CLAUDE.md` | One line that makes Claude Code read `AGENTS.md` too. |
| `docs/data-model.md` | Template for your data model. You write this **before** any SQL. |
| `docs/ai-usage-log.md` | Template for your CA2 AI-usage log, with a worked example entry. |
| `prompts/01` to `05` | The five prompts for tonight, each with a note on why it is shaped that way. |
| `tools/migrate.py` | Builds and updates your database from `schema/*.sql` files, in order, once each. |
| `tools/sql.py` | Runs one SQL statement and tells you in plain English what happened. |
| `tools/check_db.py` | A health check for your database and your code, with ticks and crosses. |
| `example/` | The worked example from the session (club equipment loans). Read it, do not copy it into your repo. |

## What to copy into your CA2 repo, in this order

Your CA2 repo is the folder you have been building since Session 3. Copy these into its **top folder** (the one with `.git` in it and, usually, `app.py`):

1. `AGENTS.md` and `CLAUDE.md`. If you already have one of these files, do not overwrite it: paste the contents of ours onto the end of yours.
2. The `tools` folder, as it is.
3. The `prompts` folder, as it is.
4. The `docs` folder. If you already have a `docs` folder, copy just the two files into it.
5. Create an empty folder called `schema`. Your agent will put `001_initial.sql` in it.
6. Open `.gitignore` (create it if it is missing) and make sure it contains the two lines `*.db` and `__pycache__/`. Databases never go into Git.

Then commit the kit on its own, so your history shows where it came from:

```text
git add AGENTS.md CLAUDE.md tools prompts docs .gitignore
git commit -m "Add Session 5 data layer kit (rules, tools, templates)"
```

Do **not** copy `example/` into your repo. It is there to look at.

## The order of work tonight

1. Paper sketch of your data.
2. Prompt 01: the agent interviews you and drafts `docs/data-model.md`. You correct it and decide the delete rule. **Commit.**
3. Prompt 02: the agent writes `schema/001_initial.sql`. You check it field by field.
4. `python tools/migrate.py app.db` builds the database. **Commit.**
5. Try three bad inserts with `tools/sql.py`. Predict first. (Wait for the class discussion.)
6. Prompt 03: the agent wires the database into your app. Restart test. `tools/check_db.py`. **Commit.**
7. Prompt 04: tests that prove the rules work. **Commit.**
8. Prompt 05: what did the agent decide that you did not? Into the AI-usage log. **Commit, push, pull request.**

The Lab Guide PDF walks through every step and shows the output you should expect.

## Which command: python, python3 or py?

| Computer | Try this first | If that fails |
|---|---|---|
| Windows | `python` | `py` |
| Mac | `python3` | (`python` usually does not exist on a Mac) |

Wherever the guide says `python`, Mac users type `python3`.

## The three tools at a glance

```text
python tools/migrate.py app.db                       build or update the database
python tools/sql.py app.db "SELECT * FROM member"    run one SQL statement
python tools/sql.py app.db "..." --fk                same, with foreign keys switched on
python tools/check_db.py app.db --src .              health check of database and code
```

Run them from the top folder of your project. If one says it cannot find something, check where you are with `pwd`.
