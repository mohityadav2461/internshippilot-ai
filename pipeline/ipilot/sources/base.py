"""Shared helpers for source adapters."""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..http_client import SourceError

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,59}$")


def valid_slug(value: object) -> str:
    slug = str(value or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise SourceError(f"invalid board slug {slug!r}")
    return slug


def json_body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError as exc:
        raise SourceError("response is not valid JSON") from exc
