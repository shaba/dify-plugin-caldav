"""Pure CalDAV plugin core: a thin wrapper over the `caldav`/`icalendar`
libraries plus parsing and formatting of events and tasks.

The parsing/formatting helpers operate on `icalendar` component objects (or raw
iCalendar text), so they are unit-testable without any network access. The
connection layer (`connection.py`) wraps `caldav.DAVClient` and is the only part
that talks to a server.
"""
