"""Connection-layer tests with a fully mocked `caldav` server.

We build fake principal/calendar/object structures that mimic the small slice of
the `caldav` API the wrapper uses (`principal()`, `calendars()`, `calendar.name`,
`calendar.url`, `calendar.search()`, `calendar.events()`,
`calendar.add_event()`, `calendar.add_todo()` and `obj.icalendar_component`).
No network is involved.
"""

from datetime import date, datetime

import pytest
from icalendar import Calendar

from caldav_client import connection
from caldav_client.connection import (
    create_event,
    create_task,
    list_calendars,
    list_events,
    list_tasks,
    search_events,
)
from caldav_client.errors import CalDAVError, CalendarNotFound


def _component(ics, name):
    cal = Calendar.from_ical(ics)
    return next(c for c in cal.walk() if c.name == name)


class FakeObject:
    def __init__(self, component):
        self.icalendar_component = component


class FakeCalendar:
    def __init__(self, name, url, events=None, todos=None, components=("VEVENT",)):
        self.name = name
        self.url = url
        self._events = events or []
        self._todos = todos or []
        self._components = list(components)
        self.added_events = []
        self.added_todos = []
        self.search_calls = []

    def get_supported_components(self):
        return self._components

    def events(self):
        return list(self._events)

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        if kwargs.get("todo"):
            todos = list(self._todos)
            if not kwargs.get("include_completed", True):
                todos = [t for t in todos
                         if (t.icalendar_component.get("status") or "").upper() != "COMPLETED"]
            return todos
        # Mirror the real caldav 2.x/3.x contract: recurrence expansion is only
        # allowed with a closed date range, so the wrapper must not set
        # expand=True unless both bounds are present.
        if kwargs.get("expand") and (not kwargs.get("start") or not kwargs.get("end")):
            raise ValueError("can't expand without a date range")
        return list(self._events)

    def add_event(self, *, dtstart, dtend, summary, **extra):
        # Mirror caldav: a `date` (not datetime) start/end yields a VALUE=DATE
        # all-day VEVENT, a datetime yields a timed one.
        if isinstance(dtstart, datetime):
            when = (
                f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%SZ')}\n"
                f"DTEND:{dtend.strftime('%Y%m%dT%H%M%SZ')}\n"
            )
        else:
            when = (
                f"DTSTART;VALUE=DATE:{dtstart.strftime('%Y%m%d')}\n"
                f"DTEND;VALUE=DATE:{dtend.strftime('%Y%m%d')}\n"
            )
        ics = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//EN\nBEGIN:VEVENT\n"
            f"UID:new@example.com\nSUMMARY:{summary}\n"
            f"{when}"
        )
        if extra.get("location"):
            ics += f"LOCATION:{extra['location']}\n"
        if extra.get("description"):
            ics += f"DESCRIPTION:{extra['description']}\n"
        ics += "END:VEVENT\nEND:VCALENDAR\n"
        obj = FakeObject(_component(ics, "VEVENT"))
        self.added_events.append(obj)
        return obj

    def add_todo(self, *, summary, **extra):
        ics = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//EN\nBEGIN:VTODO\n"
            f"UID:newtodo@example.com\nSUMMARY:{summary}\nSTATUS:NEEDS-ACTION\n"
        )
        due = extra.get("due")
        if due is not None:
            ics += f"DUE;VALUE=DATE:{due.strftime('%Y%m%d')}\n"
        if extra.get("description"):
            ics += f"DESCRIPTION:{extra['description']}\n"
        ics += "END:VTODO\nEND:VCALENDAR\n"
        obj = FakeObject(_component(ics, "VTODO"))
        self.added_todos.append(obj)
        return obj


class FakePrincipal:
    def __init__(self, calendars):
        self._calendars = calendars

    def calendars(self):
        return list(self._calendars)


class FakeClient:
    def __init__(self, calendars, url="https://dav.example.com/", url_lookup=None):
        self._principal = FakePrincipal(calendars)
        self.url = url
        # Calendars resolvable only via client.calendar(url=...) (not listed
        # by the principal) — used to exercise the direct-URL fallback.
        self._url_lookup = {u.rstrip("/"): cal for u, cal in (url_lookup or {}).items()}
        self.calendar_url_calls = []

    def principal(self):
        return self._principal

    def calendar(self, *, url):
        self.calendar_url_calls.append(url)
        cal = self._url_lookup.get(url.rstrip("/"))
        if cal is None:
            raise RuntimeError("not found")
        return cal


@pytest.fixture
def meeting_obj(event_meeting_ics):
    return FakeObject(_component(event_meeting_ics, "VEVENT"))


@pytest.fixture
def allday_obj(event_allday_ics):
    return FakeObject(_component(event_allday_ics, "VEVENT"))


@pytest.fixture
def open_task_obj(task_open_ics):
    return FakeObject(_component(task_open_ics, "VTODO"))


@pytest.fixture
def done_task_obj(task_done_ics):
    return FakeObject(_component(task_done_ics, "VTODO"))


@pytest.fixture
def client(meeting_obj, allday_obj, open_task_obj, done_task_obj):
    cal = FakeCalendar(
        "Personal",
        "https://dav.example.com/cal/personal/",
        events=[meeting_obj, allday_obj],
        todos=[open_task_obj, done_task_obj],
        components=["VEVENT", "VTODO"],
    )
    return FakeClient([cal])


def test_connect_builds_davclient(monkeypatch):
    captured = {}

    def fake_dav(**kwargs):
        captured.update(kwargs)
        return "CLIENT"

    monkeypatch.setattr(connection.caldav, "DAVClient", fake_dav)
    out = connection.connect("https://dav.example.com/", "alice", "secret", timeout=15)
    assert out == "CLIENT"
    assert captured["url"] == "https://dav.example.com/"
    assert captured["username"] == "alice"
    assert captured["password"] == "secret"
    assert captured["timeout"] == 15


def test_connect_requires_base_url():
    with pytest.raises(CalDAVError):
        connection.connect("", "alice", "secret")


def test_list_calendars(client):
    cals = list_calendars(client)
    assert cals[0]["name"] == "Personal"
    assert "VTODO" in cals[0]["components"]


def test_list_events_sorted(client):
    events = list_events(client, "Personal")
    assert {e["summary"] for e in events} == {"Team sync", "Company holiday"}
    # sorted by start string: all-day 2026-01-01 before 2026-01-15
    assert events[0]["summary"] == "Company holiday"


def test_list_events_with_range_uses_search(client):
    events = list_events(client, "Personal", start="2026-01-01", end="2026-02-01")
    assert events  # FakeCalendar.search returns the events
    cal = client.principal().calendars()[0]
    assert cal.search_calls[-1].get("expand") is True


def test_list_events_one_sided_range_does_not_expand(client):
    # Only a start bound: expansion needs a closed window, so the wrapper must
    # not set expand=True (the real caldav searcher would raise otherwise).
    events = list_events(client, "Personal", start="2026-01-01")
    assert events
    cal = client.principal().calendars()[0]
    last = cal.search_calls[-1]
    assert "expand" not in last
    assert last.get("start") is not None and last.get("end") is None


def test_list_events_only_end_does_not_expand(client):
    events = list_events(client, "Personal", end="2026-02-01")
    assert events
    cal = client.principal().calendars()[0]
    assert "expand" not in cal.search_calls[-1]


def test_find_calendar_by_url(client):
    events = list_events(client, "https://dav.example.com/cal/personal/")
    assert events


def test_find_calendar_not_found(client):
    with pytest.raises(CalendarNotFound):
        list_events(client, "Nonexistent")


def test_find_calendar_rejects_foreign_url(client):
    # An LLM-supplied URL on a different host must not be fetched with the
    # configured credentials (SSRF guard).
    with pytest.raises(CalendarNotFound):
        list_events(client, "http://169.254.169.254/latest/meta-data/")
    assert client.calendar_url_calls == []


def test_find_calendar_same_origin_url_fallback(meeting_obj):
    # A same-origin URL that is not in the principal's calendar list still
    # resolves via the direct client.calendar(url=...) fallback.
    hidden = FakeCalendar(
        "Hidden",
        "https://dav.example.com/cal/hidden/",
        events=[meeting_obj],
    )
    principal_cal = FakeCalendar("Other", "https://dav.example.com/cal/other/")
    fake = FakeClient(
        [principal_cal],
        url_lookup={"https://dav.example.com/cal/hidden/": hidden},
    )
    events = list_events(fake, "https://dav.example.com/cal/hidden/")
    assert events
    assert fake.calendar_url_calls == ["https://dav.example.com/cal/hidden/"]


def test_search_events_text(client):
    assert len(search_events(client, "Personal", "team")) == 1
    assert search_events(client, "Personal", "team")[0]["summary"] == "Team sync"
    assert search_events(client, "Personal", "zzz") == []
    # empty query returns all
    assert len(search_events(client, "Personal", "")) == 2


def test_search_events_matches_location(client):
    assert len(search_events(client, "Personal", "room a")) == 1


def test_list_tasks_all(client):
    tasks = list_tasks(client, "Personal")
    assert len(tasks) == 2


def test_list_tasks_only_incomplete(client):
    tasks = list_tasks(client, "Personal", only_incomplete=True)
    assert len(tasks) == 1
    assert tasks[0]["summary"] == "Write report"


def test_list_tasks_only_incomplete_excludes_cancelled(meeting_obj):
    cancelled_ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//EN\nBEGIN:VTODO\n"
        "UID:cancelled@example.com\nSUMMARY:Abandoned task\nSTATUS:CANCELLED\n"
        "END:VTODO\nEND:VCALENDAR\n"
    )
    open_ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//EN\nBEGIN:VTODO\n"
        "UID:open@example.com\nSUMMARY:Real task\nSTATUS:NEEDS-ACTION\n"
        "END:VTODO\nEND:VCALENDAR\n"
    )
    cal = FakeCalendar(
        "Tasks",
        "https://dav.example.com/cal/tasks/",
        todos=[FakeObject(_component(cancelled_ics, "VTODO")),
               FakeObject(_component(open_ics, "VTODO"))],
        components=["VTODO"],
    )
    fake = FakeClient([cal])
    tasks = list_tasks(fake, "Tasks", only_incomplete=True)
    assert [t["summary"] for t in tasks] == ["Real task"]


def test_create_event(client):
    ev = create_event(
        client, "Personal",
        summary="New meeting", start="2026-03-01T09:00", end="2026-03-01T10:00",
        location="HQ", description="kickoff",
    )
    assert ev["summary"] == "New meeting"
    assert ev["location"] == "HQ"
    assert ev["start"] == "2026-03-01 09:00Z"


def test_create_event_requires_summary(client):
    with pytest.raises(CalDAVError):
        create_event(client, "Personal", summary="  ", start="2026-03-01T09:00",
                     end="2026-03-01T10:00")


def test_create_event_end_after_start(client):
    with pytest.raises(CalDAVError):
        create_event(client, "Personal", summary="x", start="2026-03-01T10:00",
                     end="2026-03-01T09:00")


def test_create_task_with_due(client):
    t = create_task(client, "Personal", summary="Buy milk", due="2026-03-05",
                    description="2 liters")
    assert t["summary"] == "Buy milk"
    assert t["due"] == "2026-03-05"
    assert t["completed"] is False


def test_create_task_requires_summary(client):
    with pytest.raises(CalDAVError):
        create_task(client, "Personal", summary="")


def test_create_event_passes_aware_datetimes(client):
    create_event(client, "Personal", summary="tz", start="2026-03-01T09:00",
                 end="2026-03-01T10:00")
    cal = client.principal().calendars()[0]
    # the wrapper must hand timezone-aware datetimes to caldav
    added = cal.added_events[-1]
    dtstart = added.icalendar_component.get("dtstart").dt
    assert isinstance(dtstart, datetime)


def test_create_event_allday_uses_value_date(client):
    # Bare dates for both bounds must create an all-day (VALUE=DATE) event,
    # handing datetime.date objects (not midnight datetimes) to caldav.
    ev = create_event(client, "Personal", summary="Vacation",
                      start="2026-04-01", end="2026-04-03")
    cal = client.principal().calendars()[0]
    added = cal.added_events[-1]
    dtstart = added.icalendar_component.get("dtstart").dt
    assert isinstance(dtstart, date) and not isinstance(dtstart, datetime)
    assert ev["start"] == "2026-04-01"


def test_create_event_allday_single_day(client):
    # A single all-day day (start == end) was previously rejected; it must now
    # succeed, advancing the exclusive DTEND to the following day.
    create_event(client, "Personal", summary="Holiday",
                 start="2026-04-01", end="2026-04-01")
    cal = client.principal().calendars()[0]
    added = cal.added_events[-1]
    dtend = added.icalendar_component.get("dtend").dt
    assert dtend == date(2026, 4, 2)


def test_create_event_allday_end_before_start_rejected(client):
    with pytest.raises(CalDAVError):
        create_event(client, "Personal", summary="x",
                     start="2026-04-03", end="2026-04-01")


def test_same_origin_normalizes_default_ports():
    # An explicit :443 (https) must count as the same origin as no port.
    assert connection._same_origin("https://dav.example.com/", "https://dav.example.com:443/cal/x/")
    assert connection._same_origin("https://dav.example.com:443/", "https://dav.example.com/cal/x/")
    assert connection._same_origin("http://dav.example.com/", "http://dav.example.com:80/cal/x/")
    # A genuinely different port is still a different origin.
    assert not connection._same_origin("https://dav.example.com/", "https://dav.example.com:8443/x/")


def test_find_calendar_same_origin_explicit_port(meeting_obj):
    # A same-server calendar URL carrying an explicit :443 must resolve via the
    # direct-URL fallback rather than being rejected as foreign.
    hidden = FakeCalendar("Hidden", "https://dav.example.com/cal/hidden/",
                          events=[meeting_obj])
    principal_cal = FakeCalendar("Other", "https://dav.example.com/cal/other/")
    fake = FakeClient(
        [principal_cal],
        url_lookup={"https://dav.example.com:443/cal/hidden/": hidden},
    )
    events = list_events(fake, "https://dav.example.com:443/cal/hidden/")
    assert events
    assert fake.calendar_url_calls == ["https://dav.example.com:443/cal/hidden/"]
