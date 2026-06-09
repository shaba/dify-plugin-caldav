"""Shared credential extraction for CalDAV tools."""

from __future__ import annotations

from typing import Any

from caldav_client.connection import connect
from caldav_client.errors import redact_credentials


def error_message(exc: object) -> str:
    """User/LLM-facing error text with any embedded URL credentials stripped."""
    return f"CalDAV error: {redact_credentials(exc)}"


def client_from_credentials(credentials: dict[str, Any]):
    base_url = str(credentials.get("base_url") or "").strip()
    username = str(credentials.get("username") or "").strip()
    password = str(credentials.get("password") or "")
    if not base_url:
        raise ValueError("the plugin base_url is not configured")
    return connect(base_url, username, password)
