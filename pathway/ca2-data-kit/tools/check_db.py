"""Health check for your database and the Python code that talks to it.

Usage (run from the top folder of your project):
    Mac:      python3 tools/check_db.py app.db --src .
    Windows:  python tools/check_db.py app.db --src .

It reports, in plain English:
  * the tables it found, and for each one: primary key, required (NOT NULL)
    columns, UNIQUE rules, CHECK rules, and foreign keys with their delete rule
  * orphan rows (rows pointing at something that does not exist)
  * your .py files: SQL built by gluing strings together (f-strings,
    .format, % or +), whether PRAGMA foreign_keys is switched on anywhere,
    and lists at the top of a file that might be storing data in memory

A cross means "fix this". A warning sign means "have a look and decide".
The tool exits with code 1 if there is any cross, so you can use it in tests
or GitHub Actions later in the course.
"""
import argparse
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True  # keep tools/ free of __pycache__ folders
sys.path.insert(0, HERE)
from _console import CROSS, TICK, WARN  # noqa: E402

SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".pytest_cache",
             "site-packages", ".idea", ".vscode", "migrations_backup"}

problems = 0
warnings = 0


def ok(text):
    print(f"  {TICK} {text}")


def bad(text):
    global problems
    problems += 1
    print(f"  {CROSS} {text}")


def warn(text):
    global warnings
    warnings += 1
    print(f"  {WARN} {text}")


def note(text):
    print(f"      {text}")


# ---------------------------------------------------------------- database

def check_database(db_path):
    print(f"\nDATABASE: {db_path}")
    if not os.path.exists(db_path):
        bad(f"There is no file called {db_path}. Run tools/migrate.py first, or check the folder you are in.")
        return
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' AND name != 'schema_migrations' ORDER BY name")]
    if not tables:
        bad("No tables found. Did the migration run? Try: python tools/migrate.py " + db_path)
        conn.close()
        return
    ok(f"{len(tables)} table(s) found: {', '.join(tables)}")
    has_log = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
    if has_log:
        applied = [r[0] for r in conn.execute("SELECT filename FROM schema_migrations ORDER BY filename")]
        ok(f"Migrations recorded: {', '.join(applied) if applied else 'none'}")
    else:
        warn("No schema_migrations table, so this database was not built with tools/migrate.py.")

    for table in tables:
        check_table(conn, table)

    print("\nORPHAN ROWS (rows that point at something that does not exist)")
    orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    if not orphans:
        ok("None found.")
    else:
        by_table = {}
        for table, rowid, parent, _ in orphans:
            by_table.setdefault((table, parent), []).append(rowid)
        for (table, parent), rowids in by_table.items():
            shown = ", ".join(str(r) for r in rowids[:10])
            bad(f"{len(rowids)} row(s) in {table} point at a row in {parent} that does not exist "
                f"(row id: {shown}). Foreign keys were not being enforced when these went in.")
    conn.close()


def check_table(conn, table):
    print(f"\nTABLE: {table}")
    quoted = '"' + table.replace('"', '""') + '"'
    columns = conn.execute(f"PRAGMA table_info({quoted})").fetchall()  # table name from sqlite_master, not user input
    # columns: cid, name, type, notnull, default, pk
    pk = [c[1] for c in sorted(columns, key=lambda c: c[5]) if c[5]]
    if pk:
        ok(f"Primary key: {', '.join(pk)}")
    else:
        bad("No primary key. Every table needs one (usually: id INTEGER PRIMARY KEY).")

    required = [c[1] for c in columns if c[3] and not c[5]]
    if required:
        ok(f"Required (NOT NULL): {', '.join(required)}")
    else:
        warn("No NOT NULL columns. Is every field really optional?")

    uniques = []
    for index in conn.execute(f"PRAGMA index_list({quoted})").fetchall():
        # seq, name, unique, origin, partial
        name, unique, origin = index[1], index[2], index[3]
        partial = index[4] if len(index) > 4 else 0
        if unique and origin != "pk":
            cols = [r[2] for r in conn.execute(f'PRAGMA index_info("{name}")')]
            label = ", ".join(cols)
            if partial:
                label += " (only for some rows: a partial index)"
            uniques.append(label)
    if uniques:
        ok(f"UNIQUE: {'; '.join(uniques)}")
    else:
        warn("No UNIQUE rule. Is there anything here that must never be duplicated (email, code, tag)?")

    create_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone()[0] or ""
    checks = len(re.findall(r"\bCHECK\s*\(", create_sql, re.IGNORECASE))
    if checks:
        ok(f"CHECK rules: {checks}")
    else:
        warn("No CHECK rule. Is there a column with a fixed list of allowed values, or a number/date with limits?")

    foreign_keys = conn.execute(f"PRAGMA foreign_key_list({quoted})").fetchall()
    # id, seq, table, from, to, on_update, on_delete, match
    for fk in foreign_keys:
        parent, child_col, parent_col, on_delete = fk[2], fk[3], fk[4] or "id", fk[6].upper()
        where = f"{table}.{child_col} -> {parent}.{parent_col}"
        if on_delete == "CASCADE":
            warn(f"Foreign key {where}, ON DELETE CASCADE: deleting a {parent} silently deletes its "
                 f"{table} rows. Decision needed: was this yours? Write the reason in docs/data-model.md.")
        elif on_delete == "NO ACTION":
            bad(f"Foreign key {where}, no delete rule chosen (NO ACTION is the default). "
                "Decide RESTRICT, CASCADE or SET NULL and write the reason in docs/data-model.md.")
        else:
            ok(f"Foreign key {where}, ON DELETE {on_delete}")
    if not foreign_keys:
        note("(no foreign keys in this table)")


# ---------------------------------------------------------------- source code

SQL_WORD = (r"(SELECT\s.*?\bFROM\b|INSERT\s+INTO\b|UPDATE\s+\S+\s+SET\b|DELETE\s+FROM\b|"
            r"REPLACE\s+INTO\b|CREATE\s+TABLE\b|DROP\s+TABLE\b|ALTER\s+TABLE\b)")
GLUED_SQL = [
    # cursor.execute(f"..."), conn.execute(f'...')
    (re.compile(r"\.execute(?:many|script)?\(\s*[rR]?[fF][\"']"), "an f-string inside execute()"),
    # sql = f"SELECT ... {x}"
    (re.compile(r"[fF][\"']{1,3}\s*" + SQL_WORD, re.IGNORECASE), "an f-string that builds SQL"),
    # "SELECT ...".format(...)   (double- or single-quoted)
    (re.compile(r'"\s*' + SQL_WORD + r'[^"]*"\s*\.format\(', re.IGNORECASE), ".format() on SQL"),
    (re.compile(r"'\s*" + SQL_WORD + r"[^']*'\s*\.format\(", re.IGNORECASE), ".format() on SQL"),
    # "SELECT ... %s" % value
    (re.compile(r'"\s*' + SQL_WORD + r'[^"]*"\s*%\s*[\w(]', re.IGNORECASE), "% formatting on SQL"),
    (re.compile(r"'\s*" + SQL_WORD + r"[^']*'\s*%\s*[\w(]", re.IGNORECASE), "% formatting on SQL"),
    # "SELECT ... " + value
    (re.compile(r'"\s*' + SQL_WORD + r'[^"]*"\s*\+', re.IGNORECASE), "+ joining strings into SQL"),
    (re.compile(r"'\s*" + SQL_WORD + r"[^']*'\s*\+", re.IGNORECASE), "+ joining strings into SQL"),
    # execute("..." + x) or execute(sql + x)
    (re.compile(r"\.execute\([^)]*[\"']\s*\+\s*\w"), "+ joining strings inside execute()"),
]
PRAGMA_ON = re.compile(r"PRAGMA\s+foreign_keys\s*=\s*(ON|1|TRUE)", re.IGNORECASE)
TOP_LEVEL_LIST = re.compile(r"^([a-z_][a-z0-9_]*)\s*(?::\s*[^=]+)?=\s*\[")


def python_files(src):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        if os.path.abspath(root) == HERE:  # do not scan the kit tools themselves
            continue
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(root, name)


def check_source(src):
    print(f"\nSOURCE CODE: the {os.path.basename(os.path.abspath(src))} folder")
    files = list(python_files(src))
    if not files:
        warn("No .py files found. Is --src pointing at your project folder?")
        return
    ok(f"{len(files)} Python file(s) scanned")

    glued, pragma_files, lists = [], [], []
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        rel = os.path.relpath(path, src)
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern, label in GLUED_SQL:
                if pattern.search(line):
                    glued.append((rel, number, label, stripped))
                    break
            if PRAGMA_ON.search(line.split("#")[0]):
                pragma_files.append(f"{rel}:{number}")
            match = TOP_LEVEL_LIST.match(line)
            if match and not os.path.basename(path).startswith("test"):
                lists.append((rel, number, match.group(1)))

    if glued:
        for rel, number, label, text in glued:
            bad(f"{rel} line {number}: SQL built with {label}. Use ? placeholders instead.")
            note(text[:100])
    else:
        ok("No SQL built from glued-together strings (f-strings, .format, %, +).")

    if pragma_files:
        ok(f"PRAGMA foreign_keys = ON is set in: {', '.join(pragma_files)}")
        note("Make sure EVERY connection goes through that code, not just one of them.")
    else:
        bad("No .py file switches on PRAGMA foreign_keys. SQLite will ignore your foreign keys.")

    if lists:
        for rel, number, name in lists:
            warn(f"{rel} line {number}: a list called '{name}' at the top of the file. "
                 "If it holds your app's data, that data disappears when the app restarts.")
    else:
        ok("No lists at the top of a file that look like in-memory storage.")


def main():
    parser = argparse.ArgumentParser(description="Plain-English health check for a SQLite database and its code.")
    parser.add_argument("database", help="the database file, for example app.db")
    parser.add_argument("--src", default=None, help="your project folder to scan for .py files (for example: .)")
    args = parser.parse_args()

    print("CA2 data layer check")
    print("====================")
    check_database(args.database)
    if args.src:
        check_source(args.src)
    else:
        print("\n(Add --src . to scan your Python code as well.)")

    print("\nSUMMARY")
    if problems:
        print(f"  {CROSS} {problems} thing(s) to fix, {warnings} thing(s) to look at.")
    else:
        print(f"  {TICK} Nothing to fix. {warnings} thing(s) to look at.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
