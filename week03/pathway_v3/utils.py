"""Shared validation and timestamp helpers."""

import re
from datetime import datetime, timezone
from urllib.parse import quote, urlparse


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


# A deliberately strict email rule. It accepts the addresses people really use and refuses
# anything that could change meaning when the address is put into a mailto: link.
#   name part: letters and digits, joined by single dots, underscores, plus signs, hyphens or
#              apostrophes (so o'brien+jobs@example.ie is fine, but a?bcc=x@example.com is not)
#   domain:    dot-separated labels of letters, digits and inner hyphens, ending in a real-looking
#              ending such as .com or .ie (or an xn-- international ending)
# Spaces, commas, semicolons, quotes, angle brackets, ? & = # % / and non-English letters are not
# accepted. That means a few unusual but technically legal addresses are turned away on purpose.
_EMAIL_PATTERN = re.compile(
    r"(?P<name>[A-Za-z0-9]+(?:[._+'-][A-Za-z0-9]+)*)"
    r"@"
    r"(?P<domain>(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9-]{1,59}))"
)


def valid_email(value):
    """True only for a plain, single email address of the strict shape described above."""
    if not isinstance(value, str) or not value or len(value) > 254:
        return False
    match = _EMAIL_PATTERN.fullmatch(value)
    return bool(match) and len(match.group("name")) <= 64


def mailto_link(value):
    """Return a mailto: link for a valid address, or None.

    Returning None for anything else means a bad address already stored in the database is shown
    as plain text and can never become a link that pre-fills cc, bcc, subject or body.
    """
    value = value.strip() if isinstance(value, str) else ""
    return "mailto:" + quote(value, safe="@+'") if valid_email(value) else None
