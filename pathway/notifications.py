"""Private in-app notification centre."""

from flask import Blueprint, abort, flash, redirect, render_template, session, url_for

from db import get_db
from security import role_required
from utils import utc_now

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.get("")
@role_required("jobseeker")
def jobseeker_list():
    return _list_for_current_user()


@bp.get("/adviser")
@role_required("career_adviser")
def adviser_list():
    return _list_for_current_user()


def _list_for_current_user():
    db = get_db()
    notifications = db.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("notifications.html", notifications=notifications)


@bp.post("/<int:notification_id>/read")
def mark_read(notification_id):
    if not session.get("user_id"):
        abort(401)
    db = get_db()
    cursor = db.execute(
        "UPDATE notifications SET read_at = ? WHERE id = ? AND user_id = ? AND read_at IS NULL",
        (utc_now(), notification_id, session["user_id"]),
    )
    db.commit()
    if cursor.rowcount == 0:
        exists = db.execute(
            "SELECT id FROM notifications WHERE id = ? AND user_id = ?",
            (notification_id, session["user_id"]),
        ).fetchone()
        if not exists:
            abort(404)
    flash("Notification marked as read.", "success")
    if session.get("role") == "career_adviser":
        return redirect(url_for("notifications.adviser_list"))
    return redirect(url_for("notifications.jobseeker_list"))
