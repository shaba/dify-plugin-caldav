# dify-plugin-caldav

A Dify tool plugin for any CalDAV server (Nextcloud, Radicale, or any other
CalDAV-compatible service). It reads calendars, events and tasks, and can create
new events and tasks. The target server is configured per credential, so a
single installation works with any CalDAV server.

The plugin uses the mature [`caldav`](https://pypi.org/project/caldav/) Python
library for the CalDAV protocol and iCalendar parsing (it pulls in `icalendar`).

## Configuration

- `base_url` (required) — base CalDAV URL of your server. For Nextcloud this is
  `https://example.com/remote.php/dav/`; for Radicale it is typically
  `https://example.com/radicale/`.
- `username` (required) — CalDAV account user name.
- `password` (required, secret) — account password or app password.

Credentials are validated by connecting and listing the account's calendars.

## Tools

### Read

- `list_calendars` — list calendars and task lists (name, URL, supported
  component types).
- `list_events` — list events from a calendar, optionally within a `start`/`end`
  range.
- `search_events` — text search over event summary/description/location within an
  optional range.
- `list_tasks` — list tasks (VTODO), optionally only incomplete ones.

### Write

Writes are gated only by the credential's own CalDAV permissions; there is no
extra toggle.

- `create_event` — create an event (`calendar`, `summary`, `start`, `end`, and
  optional `description`/`location`).
- `create_task` — create a task (`calendar`, `summary`, and optional
  `due`/`description`).

Date-times accept ISO-like forms such as `2026-01-01T10:00`, `2026-01-01 10:00`,
a trailing `Z` for UTC, or a bare `2026-01-01` date. A datetime without an
explicit timezone or offset is interpreted as **UTC**, so pass an offset (e.g.
`2026-01-01T10:00:00+03:00`) when you mean local time, otherwise the event will
be shifted by your UTC offset.

## Known limitations

- **Unbounded list reads.** `list_events` (and `search_events`) called *without*
  a `start`/`end` range pulls the **entire calendar** and filters client-side.
  This is server-agnostic but fetches and parses every event on each call, so
  large calendars are slow and memory-heavy. Pass a `start`/`end` window to bound
  how many events are retrieved.

## Development

This plugin uses [`uv`](https://docs.astral.dev/uv/) with `pyproject.toml` and a
pinned `uv.lock` (there is no `requirements.txt`).

```sh
uv venv && . .venv/bin/activate
uv pip install ruff pytest "caldav>=3,<4"
ruff check .
python -m pytest -q
```

The CalDAV and iCalendar logic lives in the `caldav_client` package. The parsing
and formatting helpers operate on `icalendar` components (or raw iCalendar text)
and are covered by unit tests that feed sample iCalendar strings — no real server
is contacted. The tool and provider classes are thin adapters over the package.

CalDAV is defined in [RFC 4791](https://www.rfc-editor.org/rfc/rfc4791); the
`caldav` library documentation is at <https://caldav.readthedocs.io/>.

## License

Apache-2.0. Copyright © 2026 Alexey Shabalin.

## Repository

<https://github.com/shaba/dify-plugin-caldav> — issues and pull requests welcome.
