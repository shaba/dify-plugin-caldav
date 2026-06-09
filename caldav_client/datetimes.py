"""Date/time parsing and formatting helpers (pure, no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from .errors import InvalidDateTime

# Accepted input formats for user/LLM supplied date-times. Order matters: the
# most specific format is tried first.
_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)
_DATE_FORMATS = ("%Y-%m-%d", "%Y%m%d")


def parse_datetime(value: str) -> datetime:
    """Parse a user/LLM supplied date or date-time into an aware datetime.

    Accepts ISO-like forms with or without a trailing ``Z``. A bare date is
    interpreted as midnight. Naive results are assumed to be UTC so that the
    `caldav` library always receives timezone-aware values.
    """
    raw = str(value or "").strip()
    if not raw:
        raise InvalidDateTime("empty date/time value")

    text = raw
    tz = None
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1]
        tz = timezone.utc

    for fmt in _DATETIME_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=tz or timezone.utc)
        except ValueError:
            continue
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(text, fmt)
            return d.replace(tzinfo=tz or timezone.utc)
        except ValueError:
            continue

    # Last resort: rely on datetime.fromisoformat for offset-aware strings.
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidDateTime(
            f"cannot parse date/time {raw!r}; use e.g. 2026-01-01T10:00 or 2026-01-01"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_date(value: str) -> date:
    """Parse a bare date (for a task ``due`` without a time component)."""
    return parse_datetime(value).date()


def is_date_only(value: str | None) -> bool:
    """True when the value is an all-day DATE with no time component.

    An all-day value carries a date but no time, in either the hyphenated
    ``YYYY-MM-DD`` or the compact ``YYYYMMDD`` form. The discriminator is the
    absence of a time separator: a date-time always contains a ``T`` (ISO) or a
    ``:`` (``HH:MM``). This is the single source of truth shared by the
    connection layer (deciding all-day vs timed input) and the event formatter
    (rendering inclusive all-day end dates).
    """
    text = (value or "").strip()
    return bool(text) and "T" not in text and "t" not in text and ":" not in text


def format_dt(value: object) -> str:
    """Format an iCalendar datetime/date value into a compact human string.

    Handles ``datetime`` (UTC normalised, no microseconds), ``date`` (all-day),
    and falls back to ``str`` for anything else (already-formatted strings).
    """
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M") + ("Z" if value.tzinfo is not None else "")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value or "").strip()
    return text
