"""Polite HTTP client.

* Identifies itself with a contact URL (SCRAPER_CONTACT_URL / EMAIL).
* Honours robots.txt for every host. A fetch error on robots.txt is treated as
  "disallowed for now", which is the conservative choice.
* Throttles per host and backs off on 429 / 503 with Retry-After.
* Refuses, and never bypasses, CAPTCHA or bot-challenge pages.
"""

from __future__ import annotations

import logging
import time
from urllib import robotparser
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

BOT_TOKEN = "InternshipPilotBot"
ROBOTS_TTL_S = 24 * 3600
ROBOTS_ERROR_TTL_S = 3600
MAX_BYTES = 3_000_000
CHALLENGE_MARKERS = ("captcha", "cf-chl-", "are you a robot", "verify you are human", "datadome", "perimeterx")


class SourceError(Exception):
    """A transient or structural failure for one source."""


class SourceBlocked(SourceError):
    """robots.txt disallows the URL, or the site presents an access challenge. Never bypassed."""


def looks_like_challenge(body: str) -> bool:
    lowered = body[:20000].lower()
    return any(marker in lowered for marker in CHALLENGE_MARKERS)


def _require_http_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise SourceError(f"refusing non-http URL: {url[:120]}")


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("Retry-After", "").strip()
    return float(raw) if raw.isdigit() else None


class PoliteClient:
    def __init__(
        self,
        user_agent: str,
        *,
        min_interval_s: float = 2.0,
        timeout_s: float = 20.0,
        transport: httpx.BaseTransport | None = None,
        max_bytes: int = MAX_BYTES,
        backoff_s: float = 2.0,
    ) -> None:
        self._http = httpx.Client(
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json, text/html, application/xml;q=0.9, */*;q=0.5",
            },
            timeout=timeout_s,
            follow_redirects=True,
            transport=transport,
        )
        self._min_interval = min_interval_s
        self._max_bytes = max_bytes
        self._backoff = backoff_s
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, tuple[float, robotparser.RobotFileParser]] = {}

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _throttle(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            wait = self._min_interval - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_hit[host] = time.monotonic()

    def _robots_parser(self, url: str) -> robotparser.RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        now = time.monotonic()
        cached = self._robots.get(origin)
        if cached and now < cached[0]:
            return cached[1]

        parser = robotparser.RobotFileParser()
        ttl = ROBOTS_TTL_S
        self._throttle(parts.netloc)
        try:
            resp = self._http.get(f"{origin}/robots.txt", timeout=10)
            if resp.status_code == 200:
                parser.parse(resp.text.splitlines())
            elif resp.status_code in (401, 403):
                parser.parse(["User-agent: *", "Disallow: /"])
            elif resp.status_code >= 500:
                parser.parse(["User-agent: *", "Disallow: /"])
                ttl = ROBOTS_ERROR_TTL_S
            else:
                parser.parse([])  # no robots.txt means no restrictions published
        except httpx.HTTPError:
            parser.parse(["User-agent: *", "Disallow: /"])
            ttl = ROBOTS_ERROR_TTL_S
        self._robots[origin] = (now + ttl, parser)
        return parser

    def allowed(self, url: str) -> bool:
        _require_http_url(url)
        return self._robots_parser(url).can_fetch(BOT_TOKEN, url)

    def get(self, url: str, *, max_retries: int = 2) -> httpx.Response:
        _require_http_url(url)
        host = urlsplit(url).netloc
        if not self.allowed(url):
            raise SourceBlocked(f"robots.txt disallows fetching from {host}")
        for attempt in range(max_retries + 1):
            self._throttle(host)
            try:
                resp = self._http.get(url)
            except httpx.HTTPError as exc:
                if attempt < max_retries:
                    time.sleep(self._backoff * (2**attempt))
                    continue
                raise SourceError(f"network error: {type(exc).__name__}") from exc
            if resp.status_code in (429, 503) and attempt < max_retries:
                wait = _retry_after_seconds(resp) or self._backoff * (2 ** (attempt + 1))
                time.sleep(min(wait, 60))
                continue
            if resp.status_code in (401, 403):
                if looks_like_challenge(resp.text):
                    raise SourceBlocked("access challenge (CAPTCHA or bot protection) detected; not bypassed")
                raise SourceBlocked(f"HTTP {resp.status_code} from {host}")
            if resp.status_code >= 400:
                raise SourceError(f"HTTP {resp.status_code} from {host}")
            if len(resp.content) > self._max_bytes:
                raise SourceError("response exceeds the size limit")
            return resp
        raise SourceError("retries exhausted")
