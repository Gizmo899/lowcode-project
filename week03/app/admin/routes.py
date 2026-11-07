from flask import Blueprint, abort, flash, redirect, render_template, url_for
from ..extensions import db
from ..models import User
from ..security import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/advisers")
@admin_required
def advisers():
    pending = User.query.filter_by(role="adviser", status="pending").order_by(User.created_at.asc()).all()
    recently_decided = User.query.filter(User.role == "adviser", User.status.in_(["active", "rejected"])).order_by(User.created_at.desc()).limit(10).all()
    return render_template("admin/advisers.html", pending=pending, recently_decided=recently_decided)


@bp.post("/advisers/<int:user_id>/<decision>")
@admin_required
def adviser_decision(user_id, decision):
    user = User.query.filter_by(id=user_id, role="adviser", status="pending").first_or_404()
    if decision not in ("approve", "reject"):
        abort(400)
    user.status = "active" if decision == "approve" else "rejected"
    db.session.commit()
    flash(f"{user.full_name}'s adviser account was {user.status}.", "success")
    return redirect(url_for("admin.advisers"))
