"""Generic schema.org JobPosting extraction from pages you have explicitly listed.

Reads <script type="application/ld+json"> blocks. Pages must be listed in config
seed_urls, and robots.txt is enforced by the client. Nothing is crawled beyond
the seed list, and CAPTCHA pages are never bypassed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from ..http_client import PoliteClient
from ..models import RawJob

JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
MAX_SEEDS = 50


def _nodes(payload: Any) -> Iterator[dict]:
    if isinstance(payload, list):
        for item in payload:
            yield from _nodes(item)
    elif isinstance(payload, dict):
        yield payload
        if "@graph" in payload:
            yield from _nodes(payload["@graph"])


def _is_job_posting(node: dict) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "JobPosting" in kinds


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def _location_text(location: Any) -> str:
    if isinstance(location, list):
        location = location[0] if location else None
    if not isinstance(location, dict):
        return ""
    address = location.get("address") if isinstance(location.get("address"), dict) else {}
    country = address.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name")
    parts = [address.get("addressLocality"), address.get("addressRegion"), country]
    return ", ".join(str(p) for p in parts if p)


def _salary_text(base: Any) -> str | None:
    if not isinstance(base, dict):
        return None
    value = base.get("value") if isinstance(base.get("value"), dict) else {}
    currency = str(base.get("currency") or value.get("currency") or "")
    low = value.get("minValue") or value.get("value")
    high = value.get("maxValue")
    unit = str(value.get("unitText") or "").lower()
    if not low:
        return None
    amount = f"{low}-{high}" if high else f"{low}"
    period = {"month": "per month", "year": "per year", "day": "per day", "hour": "per hour"}.get(unit, "")
    return f"{currency} {amount} {period}".strip()


def _to_raw(node: dict, page_url: str, source_name: str) -> RawJob | None:
    org = node.get("hiringOrganization")
    company = str(org.get("name", "")).strip() if isinstance(org, dict) else ""
    if not company:
        return None  # a posting without a named employer cannot be attributed; skip it
    identifier = node.get("identifier")
    source_job_id = None
    if isinstance(identifier, dict) and identifier.get("value"):
        source_job_id = str(identifier["value"])
    remote = node.get("jobLocationType") == "TELECOMMUTE"
    return RawJob(
        source_name=source_name,
        source_job_id=source_job_id,
        company=company,
        title=str(node.get("title") or node.get("name") or ""),
        url=str(node.get("url") or page_url),
        location=_location_text(node.get("jobLocation")) or ("Remote" if remote else ""),
        description_html=str(node.get("description") or ""),
        employment_hint=_as_text(node.get("employmentType")),
        posted_at=node.get("datePosted") or None,
        stipend_text=_salary_text(node.get("baseSalary")),
        is_remote_flag=remote,
    )


def fetch(config: dict, client: PoliteClient, source_name: str) -> list[RawJob]:
    seeds = [str(u) for u in (config.get("seed_urls") or []) if isinstance(u, str)][:MAX_SEEDS]
    out: list[RawJob] = []
    for page_url in seeds:
        html_body = client.get(page_url).text
        for block in JSONLD_RE.findall(html_body):
            try:
                payload = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            for node in _nodes(payload):
                if _is_job_posting(node):
                    raw = _to_raw(node, page_url, source_name)
                    if raw is not None:
                        out.append(raw)
    return out
