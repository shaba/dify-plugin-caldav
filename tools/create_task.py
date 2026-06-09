from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from caldav_client.connection import create_task
from caldav_client.events import format_task_line
from tools._common import client_from_credentials, error_message


class CreateTaskTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        calendar = str(tool_parameters.get("calendar") or "").strip()
        summary = str(tool_parameters.get("summary") or "").strip()
        due = str(tool_parameters.get("due") or "").strip() or None
        description = str(tool_parameters.get("description") or "").strip() or None

        if not calendar:
            yield self.create_text_message("Error: the 'calendar' parameter is required")
            return
        if not summary:
            yield self.create_text_message("Error: the 'summary' parameter is required")
            return

        try:
            client = client_from_credentials(self.runtime.credentials)
            task = create_task(
                client, calendar,
                summary=summary, due=due, description=description,
            )
        except Exception as exc:  # noqa: BLE001
            yield self.create_text_message(error_message(exc))
            return

        yield self.create_text_message(
            f"Created task in {calendar}:\n{format_task_line(task)}")
        yield self.create_json_message({"calendar": calendar, "task": task})
