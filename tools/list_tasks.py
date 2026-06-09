from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from caldav_client.connection import list_tasks
from caldav_client.events import format_tasks
from tools._common import client_from_credentials, error_message


class ListTasksTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        calendar = str(tool_parameters.get("calendar") or "").strip()
        only_incomplete = bool(tool_parameters.get("only_incomplete") or False)

        if not calendar:
            yield self.create_text_message("Error: the 'calendar' parameter is required")
            return

        try:
            client = client_from_credentials(self.runtime.credentials)
            tasks = list_tasks(client, calendar, only_incomplete=only_incomplete)
        except Exception as exc:  # noqa: BLE001
            yield self.create_text_message(error_message(exc))
            return

        suffix = " (incomplete only)" if only_incomplete else ""
        header = f"{len(tasks)} task(s) in {calendar}{suffix}:"
        yield self.create_text_message(format_tasks(tasks, header=header))
        yield self.create_json_message({
            "calendar": calendar,
            "count": len(tasks),
            "tasks": tasks,
        })
