"""Push notifications through ntfy.sh (free, no account needed).

A notification says how many new matches were queued and lists the top few. It never
submits anything, and it never includes contact details, resume text or cover letters.

ntfy topics are public to anyone who knows the name, so NTFY_TOPIC must be long and
random (16 to 64 letters, digits, hyphens or underscores). The app sends nothing if the
topic is missing or malformed.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

import httpx

log = logging.getLogger(__name__)

NTFY_BASE = "https://ntfy.sh"
TOPIC_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
MAX_LISTED = 8
MAX_FIELD_CHARS = 120


def topic_is_valid(topic: str) -> bool:
    return bool(TOPIC_RE.match(topic or ""))


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())[:MAX_FIELD_CHARS]


def format_queue_message(items: Sequence[dict]) -> tuple[str, str]:
    """Return (title, body). The title is ASCII because HTTP headers must be."""
    count = len(items)
    noun = "match" if count == 1 else "matches"
    title = f"{count} new internship {noun} to review"
    lines = [f"{item.get('score', '?')}/100  {_clean(item.get('company'))} - {_clean(item.get('title'))}"
             for item in items[:MAX_LISTED]]
    if count > MAX_LISTED:
        lines.append(f"...and {count - MAX_LISTED} more")
    lines.append("Open Pending Applications to review. Nothing is submitted until you submit it yourself.")
    return title, "\n".join(lines)


def send_ntfy(topic: str, title: str, body: str, *, client: httpx.Client | None = None) -> bool:
    """Post one notification. Returns False on any failure and never raises."""
    if not topic_is_valid(topic):
        if topic:
            log.warning("NTFY_TOPIC is too short or has invalid characters; notifications are off")
        return False
    headers = {"Title": title.encode("ascii", "ignore").decode("ascii") or "InternshipPilot"}
    owned = client is None
    http = client or httpx.Client(timeout=10)
    try:
        response = http.post(f"{NTFY_BASE}/{topic}", content=body.encode("utf-8"), headers=headers)
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log.warning("notification not sent: %s", type(exc).__name__)
        return False
    finally:
        if owned:
            http.close()


def notify_queued(topic: str, items: Sequence[dict], *, client: httpx.Client | None = None) -> bool:
    if not items:
        return False
    title, body = format_queue_message(items)
    return send_ntfy(topic, title, body, client=client)
