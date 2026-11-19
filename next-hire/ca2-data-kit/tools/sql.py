"""Run ONE SQL statement against your database and say plainly what happened.

Usage (run from the top folder of your project):
    Mac:      python3 tools/sql.py app.db "SELECT * FROM member"
    Windows:  python tools/sql.py app.db "SELECT * FROM member"

Put the SQL inside double quotes, and use single quotes for text values
inside it, for example:
    python3 tools/sql.py app.db "INSERT INTO member (full_name, email) VALUES ('Aoife Byrne', 'aoife@example.com')"

Every run opens a brand-new, plain connection to the database, exactly the
way SQLite behaves out of the box. Nothing is switched on for you.

Option:
    --fk   switch on foreign-key checking for this connection
           (PRAGMA foreign_keys = ON) before running your statement.

You do not need the sqlite3 command-line program: this uses the SQLite that
is built into Python.
"""
import argparse
import os
import re
import sqlite3
import sys

sys.dont_write_bytecode = True  # keep tools/ free of __pycache__ folders
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _console import CROSS, TICK  # noqa: E402


def explain(error):
    """Turn a SQLite error message into a plain-English sentence."""
    text = str(error)
    rules = [
        (r"UNIQUE constraint failed: (.+)",
         "Rejected by the UNIQUE rule. A row with the same value already exists in {0}. Duplicates are not allowed."),
        (r"CHECK constraint failed: (.+)",
         "Rejected by the CHECK rule. The value broke this rule: {0}"),
        (r"NOT NULL constraint failed: (.+)",
         "Rejected by the NOT NULL rule. {0} is required and you left it empty."),
        (r"FOREIGN KEY constraint failed",
         "Rejected by the FOREIGN KEY rule. The row points to something that does not exist, "
         "or something else still depends on the row you tried to change or delete."),
        (r"no such table: (.+)",
         "There is no table called '{0}'. Check the spelling, or run tools/migrate.py first."),
        (r"no such column: (.+)",
         "There is no column called '{0}'. Check the spelling against your schema file."),
        (r"table (\S+) has no column named (\S+)",
         "Table {0} has no column called '{1}'. Check the spelling against your schema file."),
        (r"database is locked",
         "The database is busy. Another program has it open (often DB Browser with unsaved "
         "changes, or your running app). Close or save there, then try again."),
        (r'near "(.+)": syntax error',
         "SQL grammar problem near '{0}'. Check quotes, commas and brackets."),
    ]
    for pattern, sentence in rules:
        match = re.search(pattern, text)
        if match:
            return sentence.format(*match.groups())
    return text


def show_rows(cursor, rows, limit=50):
    names = [d[0] for d in cursor.description]
    widths = [len(n) for n in names]
    shown = rows[:limit]
    for row in shown:
        for i, value in enumerate(row):
            widths[i] = min(max(widths[i], len(str(value))), 30)
    line = " | ".join(n.ljust(widths[i]) for i, n in enumerate(names))
    print(line)
    print("-" * len(line))
    for row in shown:
        print(" | ".join(str(v)[:30].ljust(widths[i]) for i, v in enumerate(row)))
    if len(rows) > limit:
        print(f"... and {len(rows) - limit} more")


def main():
    parser = argparse.ArgumentParser(description="Run one SQL statement and explain the result.")
    parser.add_argument("database", help="the database file, for example app.db")
    parser.add_argument("statement", help='the SQL, inside double quotes')
    parser.add_argument("--fk", action="store_true", help="switch on PRAGMA foreign_keys for this run")
    args = parser.parse_args()

    if not os.path.exists(args.database):
        print(f"{CROSS} There is no file called {args.database} here. Run tools/migrate.py first, "
              "or check you are in the right folder.")
        sys.exit(1)

    # A fresh, plain connection: SQLite's defaults, nothing extra.
    conn = sqlite3.connect(args.database, isolation_level=None)
    if args.fk:
        conn.execute("PRAGMA foreign_keys = ON")
    mode = "foreign keys ON (--fk)" if args.fk else "plain connection, SQLite defaults"
    print(f"[{mode}]")

    try:
        cursor = conn.execute(args.statement)
        if cursor.description:  # a SELECT (or anything else that returns rows)
            rows = cursor.fetchall()
            show_rows(cursor, rows)
            print(f"{TICK} OK ({len(rows)} rows)")
        else:
            count = cursor.rowcount if cursor.rowcount >= 0 else 0
            print(f"{TICK} OK ({count} rows)")
    except sqlite3.Error as error:
        print(f"{CROSS} {explain(error)}")
        print(f"  (SQLite said: {error})")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
