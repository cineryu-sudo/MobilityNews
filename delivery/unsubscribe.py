"""
Unsubscribe request address and mailto link shared by the email body and headers.
"""

from urllib.parse import quote

from config import UNSUBSCRIBE_EMAIL

UNSUBSCRIBE_SUBJECT = "[MobilityNews] 수신 거부 요청"


def build_unsubscribe_mailto() -> str:
    """Return an ASCII-only mailto URL with the request subject prefilled."""
    return f"mailto:{UNSUBSCRIBE_EMAIL}?subject={quote(UNSUBSCRIBE_SUBJECT, safe='')}"
