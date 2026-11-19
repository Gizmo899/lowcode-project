"""Apply your schema files to a SQLite database, in order, exactly once each.

Usage (run from the top folder of your project):
    Mac:      python3 tools/migrate.py app.db
    Windows:  python tools/migrate.py app.db      (or: py tools/migrate.py app.db)

Options:
    --schema FOLDER   where the .sql files live (default: schema)

How it works:
  * Files are named like schema/001_initial.sql, schema/002_add_due_date.sql.
    They run in number order.
  * Every file that runs is recorded in a table called schema_migrations,
    together with a fingerprint (checksum) of its contents.
  * Next time, files already recorded are skipped.
  * If you EDIT a file that has already been applied, the fingerprint no
    longer matches and this tool refuses to continue. Never edit an applied
    migration: add a new numbered file instead.

Standard library only. Works on Windows and Mac with Python 3.10 or newer.
"""
import argparse
import hashlib
import os
import re
import sqlite3
import sys

sys.dont_write_bytecode = True  # keep tools/ free of __pycache__ folders
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _console import CROSS, TICK  # noqa: E402

NAME_PATTERN = re.compile(r"^(\d+)_[\w\-]+\.sql$")


def find_migrations(schema_dir):
    """Return a list of (number, filename) sorted by number."""
    if not os.path.isdir(schema_dir):
        raise SystemExit(
            f"{CROSS} I cannot find a folder called '{schema_dir}'.\n"
            "  Run this from the top folder of your project (the one that contains schema/).\n"
            "  Check where you are with: pwd"
        )
    found, ignored = [], []
    for name in os.listdir(schema_dir):
        if not name.lower().endswith(".sql"):
            continue
        match = NAME_PATTERN.match(name)
        if match:
            found.append((int(match.group(1)), name))
        else:
            ignored.append(name)
    for name in ignored:
        print(f"  (ignoring {name}: migration files must look like 001_description.sql)")
    numbers = [n for n, _ in found]
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        raise SystemExit(
            f"{CROSS} Two files share the same number: {duplicates}. Give each migration its own number."
        )
    return sorted(found)


def checksum(path):
    with open(path, "rb") as handle:
        data = handle.read().replace(b"\r\n", b"\n")  # same result on Windows and Mac
    return hashlib.sha256(data).hexdigest()


def migrate(db_path, schema_dir="schema", quiet=False):
    """Apply pending migrations. Returns the list of filenames applied."""
    say = (lambda *a: None) if quiet else print
    migrations = find_migrations(schema_dir)
    if not migrations:
        raise SystemExit(f"{CROSS} No migration files found in '{schema_dir}'.")

    conn = sqlite3.connect(db_path, isolation_level=None)  # we manage BEGIN/COMMIT ourselves
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " filename TEXT PRIMARY KEY,"
        " checksum TEXT NOT NULL,"
        " applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()
    already = dict(conn.execute("SELECT filename, checksum FROM schema_migrations"))

    # Safety check first: has anyone edited a file that was already applied?
    for _, name in migrations:
        if name in already and already[name] != checksum(os.path.join(schema_dir, name)):
            conn.close()
            raise SystemExit(
                f"{CROSS} {name} has been changed since it was applied to {db_path}.\n"
                "  Never edit a migration that has already run. Put the file back the way it was\n"
                "  (git checkout -- schema/" + name + ") and write the change as a NEW numbered file."
            )

    applied = []
    for _, name in migrations:
        if name in already:
            say(f"  {TICK} {name} (already applied, skipped)")
            continue
        path = os.path.join(schema_dir, name)
        with open(path, encoding="utf-8") as handle:
            sql = handle.read()
        try:
            conn.execute("BEGIN")
            # Run each statement inside one transaction so a failing file
            # leaves the database exactly as it was.
            for statement in split_statements(sql):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (filename, checksum) VALUES (?, ?)",
                (name, checksum(path)),
            )
            conn.commit()
        except sqlite3.Error as error:
            conn.rollback()
            conn.close()
            raise SystemExit(
                f"{CROSS} {name} failed and was NOT applied: {error}\n"
                "  Nothing from this file was saved. Fix the file, then run this again."
            )
        applied.append(name)
        say(f"  {TICK} {name} applied")

    conn.close()
    return applied


def split_statements(sql):
    """Split a .sql file into complete statements using SQLite's own parser."""
    statements, buffer = [], ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            if buffer.strip():
                statements.append(buffer.strip())
            buffer = ""
    if buffer.strip() and not buffer.strip().startswith("--"):
        statements.append(buffer.strip())
    return statements


def main():
    parser = argparse.ArgumentParser(description="Apply schema/NNN_*.sql files in order, once each.")
    parser.add_argument("database", help="the database file, for example app.db (created if missing)")
    parser.add_argument("--schema", default="schema", help="folder holding the .sql files (default: schema)")
    args = parser.parse_args()

    print(f"Migrating {args.database} using files in {args.schema}/")
    applied = migrate(args.database, args.schema)
    if applied:
        print(f"{TICK} Done. {len(applied)} new migration(s) applied.")
    else:
        print(f"{TICK} Done. The database was already up to date.")


if __name__ == "__main__":
    main()
