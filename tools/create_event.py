from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from caldav_client.connection import create_event
from caldav_client.events import format_event_line
from tools._common import client_from_credentials, error_message


class CreateEventTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        calendar = str(tool_parameters.get("calendar") or "").strip()
        summary = str(tool_parameters.get("summary") or "").strip()
        start = str(tool_parameters.get("start") or "").strip()
        end = str(tool_parameters.get("end") or "").strip()
        description = str(tool_parameters.get("description") or "").strip() or None
        location = str(tool_parameters.get("location") or "").strip() or None

        if not calendar:
            yield self.create_text_message("Error: the 'calendar' parameter is required")
            return
        if not summary:
            yield self.create_text_message("Error: the 'summary' parameter is required")
            return
        if not start or not end:
            yield self.create_text_message("Error: both 'start' and 'end' are required")
            return

        try:
            client = client_from_credentials(self.runtime.credentials)
            event = create_event(
                client, calendar,
                summary=summary, start=start, end=end,
                description=description, location=location,
            )
        except Exception as exc:  # noqa: BLE001
            yield self.create_text_message(error_message(exc))
            return

        yield self.create_text_message(
            f"Created event in {calendar}:\n{format_event_line(event)}")
        yield self.create_json_message({"calendar": calendar, "event": event})
