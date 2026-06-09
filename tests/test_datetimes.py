from datetime import date, datetime, timedelta, timezone

import pytest

from caldav_client.datetimes import format_dt, is_date_only, parse_date, parse_datetime
from caldav_client.errors import InvalidDateTime, redact_credentials


def test_parse_datetime_iso_z():
    dt = parse_datetime("2026-01-01T10:00:00Z")
    assert dt == datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def test_parse_datetime_space_and_no_seconds():
    assert parse_datetime("2026-01-01 10:00").hour == 10
    assert parse_datetime("2026-01-01T10:00").tzinfo is timezone.utc


def test_parse_bare_date_is_midnight():
    dt = parse_datetime("2026-01-01")
    assert (dt.hour, dt.minute) == (0, 0)
    assert parse_date("2026-01-01") == date(2026, 1, 1)


def test_parse_offset_aware():
    dt = parse_datetime("2026-01-01T10:00:00+02:00")
    assert dt.utcoffset().total_seconds() == 7200


def test_parse_datetime_invalid():
    with pytest.raises(InvalidDateTime):
        parse_datetime("not-a-date")
    with pytest.raises(InvalidDateTime):
        parse_datetime("")


def test_format_dt_variants():
    assert format_dt(datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)) == "2026-01-01 10:00Z"
    assert format_dt(date(2026, 1, 1)) == "2026-01-01"
    assert format_dt(None) == ""
    assert format_dt("already") == "already"


def test_format_dt_non_utc_is_normalized_to_utc():
    # A non-UTC TZID datetime is deliberately normalised to UTC and rendered
    # with a trailing Z. Berlin winter (UTC+1): 10:00 local -> 09:00Z. This
    # pins the documented behaviour (the value is numerically correct; the
    # local wall-clock is intentionally not preserved).
    berlin = timezone(timedelta(hours=1))
    aware = datetime(2026, 1, 15, 10, 0, tzinfo=berlin)
    assert format_dt(aware) == "2026-01-15 09:00Z"
    # And a positive offset that crosses midnight backwards.
    tokyo = timezone(timedelta(hours=9))
    crosses = datetime(2026, 1, 15, 5, 0, tzinfo=tokyo)
    assert format_dt(crosses) == "2026-01-14 20:00Z"


@pytest.mark.parametrize(
    "value,expected",
    [
        # All-day DATE values (no time component), both accepted forms.
        ("2026-01-01", True),
        ("20260101", True),
        ("  2026-01-01  ", True),
        # Date-times carry a time separator and are NOT date-only.
        ("2026-01-01T10:00", False),
        ("2026-01-01t10:00", False),
        ("2026-01-01 10:00", False),
        ("2026-01-01T10:00:00Z", False),
        ("2026-01-01T10:00:00+03:00", False),
        # Empty / None.
        ("", False),
        ("   ", False),
        (None, False),
    ],
)
def test_is_date_only(value, expected):
    # Single source of truth shared by connection.py and events.py: an all-day
    # DATE has no time separator (no T/:), in either YYYY-MM-DD or YYYYMMDD form.
    assert is_date_only(value) is expected


def test_is_date_only_is_the_only_implementation():
    # Guard against the historical duplication: both adapters must import the
    # consolidated helper from datetimes, not redefine their own.
    from caldav_client import connection, events

    assert connection.is_date_only is is_date_only
    assert events.is_date_only is is_date_only
    assert not hasattr(connection, "_is_date_only")
    assert not hasattr(events, "_is_date_only")


def test_redact_credentials_strips_userinfo():
    assert redact_credentials("error at 'https://u:p@host/cal/'") == "error at 'https://host/cal/'"
    assert redact_credentials("https://user@host/x") == "https://host/x"
    # No userinfo: untouched.
    assert redact_credentials("https://host/x") == "https://host/x"
    assert redact_credentials("no url here") == "no url here"
