"""Connection layer wrapping `caldav.DAVClient`.

This is the only module that performs network I/O. It turns live `caldav`
objects into the plain dicts produced by :mod:`caldav_client.events`, so the
rest of the code (and the unit tests) deal only with primitive data.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

import caldav

from .datetimes import is_date_only, parse_date, parse_datetime
from .errors import CalDAVError, CalendarNotFound
from .events import event_to_dict, is_task_done, task_to_dict


def connect(base_url: str, username: str, password: str, *, timeout: int = 30) -> caldav.DAVClient:
    """Create a DAVClient. Does not perform any request yet."""
    if not base_url:
        raise CalDAVError("base_url is required")
    return caldav.DAVClient(
        url=base_url.strip(),
        username=(username or "").strip() or None,
        password=password or None,
        timeout=timeout,
    )


def _component_set(calendar: Any) -> list[str]:
    try:
        comps = calendar.get_supported_components()
    except Exception:  # noqa: BLE001 - server may not advertise this
        return []
    return [str(c) for c in (comps or [])]


def list_calendars(client: caldav.DAVClient) -> list[dict[str, Any]]:
    principal = client.principal()
    result = []
    for cal in principal.calendars():
        result.append({
            "name": str(cal.name or ""),
            "url": str(cal.url),
            "components": _component_set(cal),
        })
    return result


_DEFAULT_PORTS = {"https": 443, "http": 80}


def _origin(split) -> tuple[str | None, str | None, int | None]:
    """(scheme, host, port) with the scheme's default port made explicit."""
    port = split.port if split.port is not None else _DEFAULT_PORTS.get(split.scheme)
    return (split.scheme or None, split.hostname, port)


def _same_origin(base_url: Any, target_url: str) -> bool:
    """True if target_url has the same scheme+host(+port) as the configured base.

    Implicit default ports (https:443, http:80) are normalised before comparing
    so that an explicit ``:443``/``:80`` on either side still counts as the same
    origin.
    """
    base = urlsplit(str(base_url or ""))
    other = urlsplit(target_url)
    return bool(base.scheme) and _origin(base) == _origin(other)


def _find_calendar(client: caldav.DAVClient, calendar: str) -> Any:
    """Resolve a calendar by display name or URL."""
    principal = client.principal()
    target = (calendar or "").strip()
    if not target:
        raise CalendarNotFound("calendar name or URL is required")
    cals = principal.calendars()
    for cal in cals:
        if str(cal.name or "") == target or str(cal.url).rstrip("/") == target.rstrip("/"):
            return cal
    # Fall back to a direct lookup. An explicit URL is only honoured when it
    # points at the same server as the configured base_url; this prevents an
    # LLM-supplied calendar URL from turning the authenticated session into an
    # SSRF request against an arbitrary internal host.
    if "://" in target:
        if not _same_origin(getattr(client, "url", None), target):
            raise CalendarNotFound(
                f"calendar URL {target!r} is not on the configured CalDAV server"
            )
        try:
            return client.calendar(url=target)
        except Exception as exc:  # noqa: BLE001
            raise CalendarNotFound(f"calendar {target!r} not found") from exc
    # A bare name that matched no calendar above does not exist. The library's
    # principal.calendar(cal_id=...) would build a Calendar without contacting
    # the server, deferring the failure to an opaque later error, so reject here.
    raise CalendarNotFound(f"calendar {target!r} not found")


def _objects_to_dicts(objects: list[Any], parse) -> list[dict[str, Any]]:
    result = []
    for obj in objects:
        component = obj.icalendar_component
        if component is None:
            continue
        result.append(parse(component))
    return result


def list_events(
    client: caldav.DAVClient,
    calendar: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    cal = _find_calendar(client, calendar)
    kwargs: dict[str, Any] = {"event": True}
    if start:
        kwargs["start"] = parse_datetime(start)
    if end:
        kwargs["end"] = parse_datetime(end)
    if "start" in kwargs or "end" in kwargs:
        # Recurrence expansion requires a closed window: the caldav searcher
        # rejects expand=True unless BOTH start and end are given, and an
        # open-ended expansion is ill-defined anyway. Only expand when both
        # bounds are present; otherwise do a plain (non-expanded) search.
        if "start" in kwargs and "end" in kwargs:
            kwargs["expand"] = True
        objects = cal.search(**kwargs)
    else:
        objects = cal.events()
    events = _objects_to_dicts(objects, event_to_dict)
    events.sort(key=lambda e: e.get("start") or "")
    return events


def search_events(
    client: caldav.DAVClient,
    calendar: str,
    query: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    # Text matching is done client-side for portability: CalDAV server-side
    # text-match support is weak and inconsistent across servers, so we fetch
    # and filter locally. For large calendars, pass a start/end window to bound
    # how many events are retrieved before filtering.
    events = list_events(client, calendar, start=start, end=end)
    needle = (query or "").strip().lower()
    if not needle:
        return events
    return [
        e for e in events
        if needle in (e.get("summary") or "").lower()
        or needle in (e.get("description") or "").lower()
        or needle in (e.get("location") or "").lower()
    ]


def list_tasks(
    client: caldav.DAVClient,
    calendar: str,
    *,
    only_incomplete: bool = False,
) -> list[dict[str, Any]]:
    cal = _find_calendar(client, calendar)
    objects = cal.search(todo=True, include_completed=not only_incomplete)
    tasks = _objects_to_dicts(objects, task_to_dict)
    if only_incomplete:
        tasks = [t for t in tasks if not is_task_done(t)]
    return tasks


def create_event(
    client: caldav.DAVClient,
    calendar: str,
    *,
    summary: str,
    start: str,
    end: str,
    description: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    if not (summary or "").strip():
        raise CalDAVError("summary is required")
    cal = _find_calendar(client, calendar)
    # An all-day event is requested when BOTH bounds are bare dates (no time
    # component). In that case hand `datetime.date` objects to caldav so it
    # emits DTSTART;VALUE=DATE / DTEND;VALUE=DATE instead of a timed VEVENT.
    if is_date_only(start) and is_date_only(end):
        dstart = parse_date(start)
        dend = parse_date(end)
        # RFC 5545 DTEND for all-day events is exclusive. Treat a single day
        # (end == start, as the description's "2026-01-01" example implies) as a
        # one-day event by advancing DTEND to the following day.
        if dend == dstart:
            dend = dstart + timedelta(days=1)
        if dend <= dstart:
            raise CalDAVError("end must be on or after start")
        dtstart: Any = dstart
        dtend: Any = dend
    else:
        dtstart = parse_datetime(start)
        dtend = parse_datetime(end)
        if dtend <= dtstart:
            raise CalDAVError("end must be after start")
    extra: dict[str, Any] = {}
    if description:
        extra["description"] = description
    if location:
        extra["location"] = location
    event = cal.add_event(dtstart=dtstart, dtend=dtend, summary=summary.strip(), **extra)
    return event_to_dict(event.icalendar_component)


def create_task(
    client: caldav.DAVClient,
    calendar: str,
    *,
    summary: str,
    due: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    if not (summary or "").strip():
        raise CalDAVError("summary is required")
    cal = _find_calendar(client, calendar)
    extra: dict[str, Any] = {}
    if due:
        # A bare date stays a date (all-day due); a date-time stays a datetime.
        # parse_datetime always returns a datetime, so the only distinction is
        # whether the input carried a time component.
        extra["due"] = parse_date(due) if is_date_only(due) else parse_datetime(due)
    if description:
        extra["description"] = description
    todo = cal.add_todo(summary=summary.strip(), **extra)
    return task_to_dict(todo.icalendar_component)
