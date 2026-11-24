"""Build or update the database from the numbered files in schema/.

Usage (from the top folder of the project):
    python tools/migrate.py app.db

Each file in schema/ (001_initial.sql, 002_...sql) is applied once, in order. The tool remembers
which files it has already applied, in a small bookkeeping table called schema_migration.
Never edit a migration that has been applied: add a new numbered file instead.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_connection  # noqa: E402  (needs the path line above)

SCHEMA_DIR = ROOT / "schema"


def apply_migrations(database_path, schema_dir=SCHEMA_DIR):
    """Apply every migration that has not been applied yet. Returns the file names applied now."""
    conn = get_connection(database_path)
    applied_now = []
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migration ("
            "filename TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (date('now')))"
        )
        conn.commit()
        already = {row["filename"] for row in conn.execute("SELECT filename FROM schema_migration")}
        for path in sorted(Path(schema_dir).glob("[0-9][0-9][0-9]_*.sql")):
            if path.name in already:
                continue
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migration (filename) VALUES (?)", (path.name,))
            conn.commit()
            applied_now.append(path.name)
    finally:
        conn.close()
    return applied_now


def main(argv):
    if len(argv) != 2:
        print("Usage: python tools/migrate.py app.db")
        return 2
    try:
        applied = apply_migrations(argv[1])
    except Exception as error:  # show a plain message, not a traceback
        print(f"Migration failed: {error}")
        print("Nothing was recorded for the file that failed. Fix the file, or if this was the very first run, delete the new database file and run again.")
        return 1
    if applied:
        for name in applied:
            print(f"Applied {name}")
    else:
        print("The database is already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
