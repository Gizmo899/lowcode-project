"""SQLite connection helpers and database initialisation."""

import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db():
    """Return the request-scoped SQLite connection, creating it when needed."""
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path, detect_types=sqlite3.PARSE_DECLTYPES)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        g.db = connection
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    schema_path = Path(current_app.root_path) / "schema.sql"
    connection = get_db()
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    connection.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
