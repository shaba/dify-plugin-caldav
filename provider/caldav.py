from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from caldav_client.connection import connect, list_calendars
from caldav_client.errors import redact_credentials


class CalDAVProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        base_url = str(credentials.get("base_url") or "").strip()
        username = str(credentials.get("username") or "").strip()
        password = str(credentials.get("password") or "")
        if not base_url:
            raise ToolProviderCredentialValidationError(
                "base_url is required (e.g. https://example.com/remote.php/dav/)")
        if not username:
            raise ToolProviderCredentialValidationError("username is required")
        if not password:
            raise ToolProviderCredentialValidationError("password is required")
        try:
            client = connect(base_url, username, password, timeout=15)
            list_calendars(client)
        except Exception as exc:  # noqa: BLE001
            safe_url = redact_credentials(base_url)
            raise ToolProviderCredentialValidationError(
                f"CalDAV server is not reachable at {safe_url}: "
                f"{redact_credentials(exc)}") from exc
