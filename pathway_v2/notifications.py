"""Private in-app notification centre (jobseekers only)."""

from flask import Blueprint, abort, flash, redirect, render_template, session, url_for

from db import get_connection, get_notification, list_notifications, mark_notification_read
from security import role_required

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.get("")
@role_required("jobseeker")
def jobseeker_list():
    return render_template("notifications.html", notifications=list_notifications(get_connection(), session["user_id"]))


@bp.post("/<int:notification_id>/read")
@role_required("jobseeker")
def mark_read(notification_id):
    conn = get_connection()
    if get_notification(conn, notification_id, session["user_id"]) is None:
        abort(404)
    mark_notification_read(conn, notification_id, session["user_id"])
    conn.commit()
    flash("Notification marked as read.", "success")
    return redirect(url_for("notifications.jobseeker_list"))
