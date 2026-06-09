from __future__ import annotations

import re


class CalDAVError(Exception):
    pass


class CalendarNotFound(CalDAVError):
    pass


class InvalidDateTime(CalDAVError):
    pass


# Matches the userinfo portion of a URL (``scheme://user:pass@host``). The
# password (and username) are stripped before any error string reaches the
# LLM/end-user, in case an operator configured base_url with embedded
# credentials. caldav's DAVError formats as "<Class> at '<url>', reason ..."
# so the raw URL can otherwise be echoed back verbatim.
_USERINFO_RE = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)[^/@\s]*@")


def redact_credentials(text: object) -> str:
    """Strip ``user:pass@`` userinfo from any URL embedded in a message."""
    return _USERINFO_RE.sub(r"\g<scheme>", str(text))
