# tools

Each tool is a pair: `<tool>.yaml` (identity + description.llm + parameters) and
`<tool>.py` (`class <Tool>(Tool)` with `_invoke(...) -> Generator[ToolInvokeMessage]`).
Register every tool in `provider/caldav.yaml` under `tools:`.

Read tools: `list_calendars`, `list_events`, `search_events`, `list_tasks`.
Write tools: `create_event`, `create_task`. Writes are gated only by the
credential's own CalDAV permissions, with no extra toggle.

`_common.py` holds the shared credential-to-client helper. The actual CalDAV and
iCalendar logic lives in the `caldav_client` package; the tool classes are thin
adapters over it.
