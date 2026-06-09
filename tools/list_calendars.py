from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from caldav_client.connection import list_calendars
from caldav_client.events import format_calendars
from tools._common import client_from_credentials, error_message


class ListCalendarsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            client = client_from_credentials(self.runtime.credentials)
            calendars = list_calendars(client)
        except Exception as exc:  # noqa: BLE001
            yield self.create_text_message(error_message(exc))
            return

        yield self.create_text_message(format_calendars(calendars))
        yield self.create_json_message({"count": len(calendars), "calendars": calendars})
