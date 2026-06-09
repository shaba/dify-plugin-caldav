"""Parsing and formatting of VEVENT / VTODO components (pure, no network).

Functions here accept either an `icalendar` component (a ``VEVENT``/``VTODO``
subcomponent) or raw iCalendar text, so they can be unit-tested by feeding
sample iCalendar strings without touching a server.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from icalendar import Calendar

from .datetimes import format_dt, is_date_only


def _decoded(component: Any, key: str) -> Any:
    """Return the python value of an iCalendar property, or None."""
    raw = component.get(key)
    if raw is None:
        return None
    # icalendar properties expose .dt for date/time and str() for text.
    dt = getattr(raw, "dt", None)
    if dt is not None:
        return dt
    return str(raw)


def _text(component: Any, key: str) -> str:
    value = _decoded(component, key)
    return "" if value is None else str(value).strip()


def iter_components(ical_text: str, name: str) -> list[Any]:
    """Parse raw iCalendar text and return all subcomponents of a given name."""
    cal = Calendar.from_ical(ical_text)
    return [c for c in cal.walk() if c.name == name]


def event_to_dict(component: Any) -> dict[str, Any]:
    """Flatten a VEVENT component into a plain dict of primitive values."""
    return {
        "uid": _text(component, "uid"),
        "summary": _text(component, "summary"),
        "start": format_dt(_decoded(component, "dtstart")),
        "end": format_dt(_decoded(component, "dtend")),
        "location": _text(component, "location"),
        "description": _text(component, "description"),
        "status": _text(component, "status"),
    }


def task_to_dict(component: Any) -> dict[str, Any]:
    """Flatten a VTODO component into a plain dict of primitive values."""
    status = _text(component, "status")
    completed = _decoded(component, "completed")
    percent = _decoded(component, "percent-complete")
    # CANCELLED tasks are closed, not open work: treat them as "done" for the
    # purpose of incomplete-task filtering so they are not surfaced as todo.
    is_done = (
        status.upper() in ("COMPLETED", "CANCELLED")
        or completed is not None
        or str(percent or "").strip() == "100"
    )
    return {
        "uid": _text(component, "uid"),
        "summary": _text(component, "summary"),
        "due": format_dt(_decoded(component, "due")),
        "status": status,
        "completed": bool(is_done),
        "description": _text(component, "description"),
    }


def is_task_done(task: dict[str, Any]) -> bool:
    return bool(task.get("completed"))


def _display_end(start: str | None, end: str | None) -> str | None:
    """Map an iCalendar (exclusive) all-day DTEND to an inclusive display.

    Per RFC 5545 the DTEND of an all-day VEVENT is exclusive, so a one-day
    holiday has DTEND = day after DTSTART. Show the inclusive last day instead,
    and omit the end entirely for a single-day all-day event.
    """
    if not (is_date_only(start) and is_date_only(end)):
        return end
    try:
        inclusive = date.fromisoformat(end) - timedelta(days=1)
    except ValueError:
        return end
    if inclusive <= date.fromisoformat(start):
        return None
    return inclusive.isoformat()


def format_event_line(event: dict[str, Any]) -> str:
    """One compact line for an event listing."""
    start = event.get("start")
    when = start or "?"
    end = _display_end(start, event.get("end"))
    if end:
        when = f"{when} - {end}"
    parts = [f"- {when}: {event.get('summary') or '(no title)'}"]
    location = event.get("location")
    if location:
        parts.append(f"@ {location}")
    status = event.get("status")
    if status and status.upper() != "CONFIRMED":
        parts.append(f"[{status}]")
    return " ".join(parts)


def format_events(events: list[dict[str, Any]], *, header: str | None = None) -> str:
    if not events:
        return "No events found."
    lines = [header] if header else [f"{len(events)} event(s):"]
    lines.extend(format_event_line(e) for e in events)
    return "\n".join(lines)


def format_task_line(task: dict[str, Any]) -> str:
    """One compact line for a task listing."""
    mark = "[x]" if task.get("completed") else "[ ]"
    parts = [f"- {mark} {task.get('summary') or '(no title)'}"]
    due = task.get("due")
    if due:
        parts.append(f"(due {due})")
    status = task.get("status")
    if status and status.upper() not in ("NEEDS-ACTION", "COMPLETED"):
        parts.append(f"[{status}]")
    return " ".join(parts)


def format_tasks(tasks: list[dict[str, Any]], *, header: str | None = None) -> str:
    if not tasks:
        return "No tasks found."
    lines = [header] if header else [f"{len(tasks)} task(s):"]
    lines.extend(format_task_line(t) for t in tasks)
    return "\n".join(lines)


def format_calendars(calendars: list[dict[str, Any]]) -> str:
    if not calendars:
        return "No calendars found."
    lines = [f"{len(calendars)} calendar(s):"]
    for cal in calendars:
        name = cal.get("name") or "(unnamed)"
        comps = cal.get("components") or []
        suffix = f" ({', '.join(comps)})" if comps else ""
        lines.append(f"- {name}{suffix}")
    return "\n".join(lines)
