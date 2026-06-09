from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from caldav_client.connection import search_events
from caldav_client.events import format_events
from tools._common import client_from_credentials, error_message


class SearchEventsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        calendar = str(tool_parameters.get("calendar") or "").strip()
        query = str(tool_parameters.get("query") or "").strip()
        start = str(tool_parameters.get("start") or "").strip() or None
        end = str(tool_parameters.get("end") or "").strip() or None

        if not calendar:
            yield self.create_text_message("Error: the 'calendar' parameter is required")
            return
        if not query:
            yield self.create_text_message("Error: the 'query' parameter is required")
            return

        try:
            client = client_from_credentials(self.runtime.credentials)
            events = search_events(client, calendar, query, start=start, end=end)
        except Exception as exc:  # noqa: BLE001
            yield self.create_text_message(error_message(exc))
            return

        header = f"{len(events)} event(s) matching \"{query}\" in {calendar}:"
        yield self.create_text_message(format_events(events, header=header))
        yield self.create_json_message({
            "calendar": calendar,
            "query": query,
            "count": len(events),
            "events": events,
        })
