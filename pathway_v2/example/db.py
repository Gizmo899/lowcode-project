"""Data layer for the club equipment loans example.

Every part of the app that needs the database goes through get_connection(),
so the foreign-key rule is switched on for EVERY connection, in one place.

Rules this file follows (see AGENTS.md):
  * only ? placeholders in SQL, never f-strings, .format, % or +
  * "not found" returns None so the web layer can send a 404
  * nothing is kept in Python lists between requests: the database is the memory
"""
import os
import sqlite3
from contextlib import closing
from datetime import date

# The database file. Set DATABASE_PATH to use a different file (tests do this).
DB_PATH = os.environ.get("DATABASE_PATH", "app.db")


class InUseError(Exception):
    """Raised when a delete is blocked because other rows still depend on this one."""


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys without this
    return conn


def _one(row):
    return dict(row) if row is not None else None


# ---------------------------------------------------------------- members

def add_member(full_name, email, db_path=None):
    with closing(get_connection(db_path)) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO member (full_name, email) VALUES (?, ?)", (full_name, email))
        return cursor.lastrowid


def get_member(member_id, db_path=None):
    with closing(get_connection(db_path)) as conn:
        return _one(conn.execute("SELECT * FROM member WHERE id = ?", (member_id,)).fetchone())


def list_members(db_path=None):
    with closing(get_connection(db_path)) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM member ORDER BY full_name")]


def delete_member(member_id, db_path=None):
    """Returns True if deleted, False if there was no such member.
    Raises InUseError if the member has loans (ON DELETE RESTRICT)."""
    try:
        with closing(get_connection(db_path)) as conn, conn:
            cursor = conn.execute("DELETE FROM member WHERE id = ?", (member_id,))
            return cursor.rowcount == 1
    except sqlite3.IntegrityError as error:
        raise InUseError("This member has loans on record, so they cannot be deleted.") from error


# ---------------------------------------------------------------- equipment

def add_equipment(tag, name, condition="good", db_path=None):
    with closing(get_connection(db_path)) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO equipment (tag, name, condition) VALUES (?, ?, ?)", (tag, name, condition))
        return cursor.lastrowid


def list_equipment(db_path=None):
    with closing(get_connection(db_path)) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM equipment ORDER BY tag")]


# ---------------------------------------------------------------- loans

def create_loan(member_id, equipment_id, borrowed_on=None, due_on=None, db_path=None):
    borrowed_on = borrowed_on or date.today().isoformat()
    with closing(get_connection(db_path)) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO loan (member_id, equipment_id, borrowed_on, due_on) VALUES (?, ?, ?, ?)",
            (member_id, equipment_id, borrowed_on, due_on))
        return cursor.lastrowid


def return_loan(loan_id, returned_on=None, db_path=None):
    """Returns True if the loan was found and marked returned, False if not found."""
    returned_on = returned_on or date.today().isoformat()
    with closing(get_connection(db_path)) as conn, conn:
        cursor = conn.execute(
            "UPDATE loan SET returned_on = ? WHERE id = ? AND returned_on IS NULL",
            (returned_on, loan_id))
        return cursor.rowcount == 1


def get_loan(loan_id, db_path=None):
    with closing(get_connection(db_path)) as conn:
        return _one(conn.execute(
            "SELECT loan.*, member.full_name, equipment.tag, equipment.name AS equipment_name "
            "FROM loan JOIN member ON member.id = loan.member_id "
            "JOIN equipment ON equipment.id = loan.equipment_id WHERE loan.id = ?",
            (loan_id,)).fetchone())


def list_loans(open_only=False, db_path=None):
    """All loans, newest first. open_only=True shows only items still out."""
    with closing(get_connection(db_path)) as conn:
        rows = conn.execute(
            "SELECT loan.*, member.full_name, equipment.tag, equipment.name AS equipment_name "
            "FROM loan JOIN member ON member.id = loan.member_id "
            "JOIN equipment ON equipment.id = loan.equipment_id "
            "WHERE (? = 0 OR loan.returned_on IS NULL) "
            "ORDER BY loan.borrowed_on DESC, loan.id DESC",
            (1 if open_only else 0,))
        return [dict(r) for r in rows]
