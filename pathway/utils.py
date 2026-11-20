"""Shared validation and timestamp helpers."""

from datetime import datetime, timezone
from urllib.parse import urlparse


APPLICATION_STATUSES = ("Applied", "Successful", "Unsuccessful", "Withdrawn")
CV_DECISIONS = ("approved", "rejected")


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalise_timestamp(value):
    """Convert an aware datetime to the UTC ISO-8601 format used in SQLite."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def valid_http_url(value):
    try:
        parsed = urlparse((value or "").strip())
        # Accessing .port also validates malformed port values.
        _ = parsed.port
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False
