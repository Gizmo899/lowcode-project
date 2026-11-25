"""Shared validation and timestamp helpers."""

import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


APPLICATION_STATUSES = ("applied", "interview", "rejected", "withdrawn")
CV_DECISIONS = ("approved", "rejected")
MAX_CV_BYTES = 1_048_576  # 1 MB, the limit in docs/data-model.md
REMINDER_DAYS = 7         # a follow-up nudge is due this many days after the date applied

try:
    IRISH_TIME = ZoneInfo("Europe/Dublin")
except ZoneInfoNotFoundError:  # Windows without the tzdata package: fall back to UTC
    IRISH_TIME = timezone.utc


def irish_now():
    """The current date and time in Ireland (the digest and the date rules use Irish time)."""
    return datetime.now(IRISH_TIME)


def irish_today():
    return irish_now().date()


def add_days(iso_date, days):
    """iso_date is YYYY-MM-DD text. Returns YYYY-MM-DD text."""
    return (date.fromisoformat(iso_date) + timedelta(days=days)).isoformat()


def password_problems(password):
    """Return a list of plain-English problems with a new password (empty list = fine).

    Rules from docs/data-model.md: at least 8 characters, at least 1 capital letter, at least
    1 special character, no spaces. A special character is anything that is not a letter or a
    digit, so accented letters (like é) are allowed but do not count as special.
    """
    problems = []
    if len(password) < 8:
        problems.append("Use a password with at least 8 characters.")
    if not any("A" <= character <= "Z" for character in password):
        problems.append("Include at least one capital letter.")
    if not any(not character.isalnum() and not character.isspace() for character in password):
        problems.append("Include at least one special character, such as ! ? # or -.")
    if any(character.isspace() for character in password):
        problems.append("Do not use spaces in your password.")
    return problems


def valid_http_url(value):
    if " " in (value or ""):
        return False
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
