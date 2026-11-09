"""One place that decides what "today" is and how local days become stored instants.

The convention used across the app:

* Calendar notions a person experiences ("today", deadlines, the digest week) are
  evaluated in APP_TIMEZONE, via ``local_today()``.
* Instants stored in DateTime columns are naive UTC (see ``models.utcnow()``).
* When a local calendar day has to become a stored instant (the follow-up nudge due
  time), ``local_midnight_to_utc()`` does the conversion, so the stored value can be
  compared directly with ``utcnow()``.

Do not call ``date.today()`` anywhere in the app: it uses the server's own timezone,
which is unrelated to APP_TIMEZONE.
"""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app


def app_timezone(app=None):
    """The configured APP_TIMEZONE as a ZoneInfo. Pass ``app`` when there is no app context."""
    if app is None:
        app = current_app
    return ZoneInfo(app.config["APP_TIMEZONE"])


def validate_app_timezone(app):
    """Fail at startup, with a clear message, if APP_TIMEZONE is not a valid IANA name.

    "Today" is now needed on ordinary page views, so a bad value must not be allowed to
    surface later as a 500 on the dashboard.
    """
    name = app.config["APP_TIMEZONE"]
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise RuntimeError(
            f"APP_TIMEZONE={name!r} is not a valid IANA timezone name "
            "(for example 'UTC' or 'Europe/Dublin'). On Windows you may also need: pip install tzdata"
        ) from exc


def _now_utc():
    # Separate function so tests can control the clock.
    return datetime.now(timezone.utc)


def local_today(app=None):
    """Today's calendar date in APP_TIMEZONE."""
    return _now_utc().astimezone(app_timezone(app)).date()


def local_midnight_to_utc(day, app=None):
    """The naive-UTC instant at which ``day`` begins (00:00) in APP_TIMEZONE.

    Handles daylight-saving changes. In the rare zones where midnight itself is skipped
    by a DST change, the result is the first valid moment after the gap.
    """
    local_start = datetime.combine(day, time.min, tzinfo=app_timezone(app))
    return local_start.astimezone(timezone.utc).replace(tzinfo=None)
