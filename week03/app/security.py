from functools import wraps
from flask import abort
from flask_login import current_user, login_required


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles or current_user.status != "active":
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


jobseeker_required = role_required("jobseeker")
adviser_required = role_required("adviser")
admin_required = role_required("admin")
