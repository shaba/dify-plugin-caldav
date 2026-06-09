from caldav_client.events import (
    event_to_dict,
    format_calendars,
    format_event_line,
    format_events,
    format_task_line,
    format_tasks,
    is_task_done,
    iter_components,
    task_to_dict,
)


def _event(ics):
    return event_to_dict(iter_components(ics, "VEVENT")[0])


def _task(ics):
    return task_to_dict(iter_components(ics, "VTODO")[0])


def test_event_to_dict_timed(event_meeting_ics):
    ev = _event(event_meeting_ics)
    assert ev["summary"] == "Team sync"
    assert ev["start"] == "2026-01-15 10:00Z"
    assert ev["end"] == "2026-01-15 11:00Z"
    assert ev["location"] == "Room A"
    assert ev["status"] == "CONFIRMED"


def test_event_to_dict_allday(event_allday_ics):
    ev = _event(event_allday_ics)
    assert ev["start"] == "2026-01-01"
    assert ev["status"] == "TENTATIVE"


def test_task_open(task_open_ics):
    t = _task(task_open_ics)
    assert t["summary"] == "Write report"
    assert t["due"] == "2026-01-20"
    assert t["completed"] is False
    assert is_task_done(t) is False


def test_task_done(task_done_ics):
    t = _task(task_done_ics)
    assert t["completed"] is True
    assert is_task_done(t) is True


def test_format_event_line(event_meeting_ics):
    line = format_event_line(_event(event_meeting_ics))
    assert line.startswith("- 2026-01-15 10:00Z - 2026-01-15 11:00Z: Team sync")
    assert "@ Room A" in line
    assert "{" not in line  # compact text, not JSON


def test_format_event_line_shows_non_confirmed_status(event_allday_ics):
    line = format_event_line(_event(event_allday_ics))
    assert "[TENTATIVE]" in line


def test_format_event_line_single_allday_omits_exclusive_end(event_allday_ics):
    # DTSTART 2026-01-01 / DTEND 2026-01-02 is a single all-day event; the
    # exclusive iCal end must not be rendered as a second day.
    line = format_event_line(_event(event_allday_ics))
    assert "2026-01-01" in line
    assert "2026-01-02" not in line


def test_format_event_line_multiday_allday_shows_inclusive_end():
    ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//EN\nBEGIN:VEVENT\n"
        "UID:trip@example.com\nSUMMARY:Trip\n"
        "DTSTART;VALUE=DATE:20260101\nDTEND;VALUE=DATE:20260104\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    line = format_event_line(_event(ics))
    # exclusive DTEND 2026-01-04 -> inclusive last day 2026-01-03
    assert "2026-01-01 - 2026-01-03" in line
    assert "2026-01-04" not in line


def test_format_events_empty():
    assert format_events([]) == "No events found."


def test_format_events_header(event_meeting_ics):
    text = format_events([_event(event_meeting_ics)], header="1 event(s):")
    assert text.startswith("1 event(s):")
    assert "Team sync" in text


def test_format_task_line(task_open_ics):
    line = format_task_line(_task(task_open_ics))
    assert line.startswith("- [ ] Write report")
    assert "(due 2026-01-20)" in line


def test_format_task_line_done(task_done_ics):
    line = format_task_line(_task(task_done_ics))
    assert line.startswith("- [x] Pay invoice")


def test_format_tasks_empty():
    assert format_tasks([]) == "No tasks found."


def test_format_calendars():
    text = format_calendars([
        {"name": "Personal", "components": ["VEVENT"]},
        {"name": "Todo", "components": ["VTODO"]},
    ])
    assert "2 calendar(s):" in text
    assert "- Personal (VEVENT)" in text
    assert "- Todo (VTODO)" in text
    assert format_calendars([]) == "No calendars found."
