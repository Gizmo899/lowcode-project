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


## Scheduled automation (follow-up nudges and weekly digest)

Your app has two automatic jobs: the follow-up nudge and the weekly pipeline digest. Flask cannot run jobs on a timer by itself, so **one script**, `tools/run_automations.py`, does both, and your computer's own scheduler starts it **every hour, on the hour**. `docs/data-model.md` (section "Automations") says exactly what the script does.

The script is not written yet. Follow these steps once it exists. Always use the same `app.db` that your app uses, and run everything from the top folder of your project.

### Step 1: run it by hand first

```text
python tools/run_automations.py app.db
```

(Mac: `python3`.) It should finish without an error. Run it a second time straight away: the second run must create **no new** notifications, because the app remembers what it has already sent. If it creates duplicates, fix that before you schedule anything.

### Step 2: schedule it

Pick your computer.

**Windows (Task Scheduler)**

1. Open a terminal and type `where python`. Copy the first line. This is the full path to Python (for example `C:\Users\you\AppData\Local\Programs\Python\Python312\python.exe`).
2. Type `cd` on its own and copy the result, or copy the folder path from File Explorer. This is the full path to your project's top folder (the one that contains `app.db`).
3. Open the Start menu, search for **Task Scheduler** and open it. In the right-hand panel click **Create Task** (not "Create Basic Task").
4. **General** tab: give it a name, for example `Job tracker automations`.
5. **Triggers** tab, click **New**. Choose **On a schedule**, **Daily**, starting today at `00:00`. Tick **Repeat task every** and choose **1 hour**, **for a duration of** **1 day**. Click OK.
6. **Actions** tab, click **New**, action **Start a program**:
   - **Program/script:** the Python path from step 1
   - **Add arguments:** `tools\run_automations.py app.db`
   - **Start in:** the project folder from step 2 (no quotation marks)
7. **Settings** tab: tick **Run task as soon as possible after a scheduled start is missed**.
8. Click OK. Right-click your new task and choose **Run** to test it, then check that the **Last Run Result** column says `The operation completed successfully.`

To stop it: right-click the task and choose **Disable** (or **Delete**).

**Mac and Linux (cron)**

1. In a terminal, type `which python3` and copy the result (the full path to Python). Then go to your project's top folder and type `pwd` and copy that too.
2. Type `crontab -e` to open your schedule.
3. Add this one line at the end, replacing the two paths with the ones you copied:

```text
0 * * * * cd /full/path/to/your/project && /full/path/to/python3 tools/run_automations.py app.db >> automations.log 2>&1
```

   This means: at minute 0 of every hour, go to the project folder and run the script, and write anything it prints (including errors) to `automations.log`.
4. Save and close. Type `crontab -l` to check the line is there.
5. After the next full hour, open `automations.log` to see what happened. An empty or missing log with no errors usually means nothing was due.

To stop it: type `crontab -e` again and delete the line.

On a Mac, if your project is inside Documents, Desktop or Downloads, macOS may block cron from reading it. If the log shows "Operation not permitted", either move the project to another folder or give cron access in System Settings > Privacy & Security > Full Disk Access.

### Things to know

- **Your computer must be on.** If it is off at 8:00 on Monday, the digest is created at the next hourly run that same Monday. If it is off for the whole of Monday, that week's digest is skipped. Cron on a Mac does not catch up after sleep.
- **Time zone:** the script works out Irish time (Europe/Dublin) by itself, so the computer's own time zone setting does not matter.
- **Running twice is safe.** Each follow-up reminder is marked as sent or skipped once it has been processed, and the script checks whether a digest already exists today, so a double run creates nothing extra.
- **Do not commit the log.** Add this line to `.gitignore`, next to `*.db` and `__pycache__/`:

```text
*.log
```
