"""Lever public postings API: https://api.lever.co/v0/postings/{company}?mode=json"""

from __future__ import annotations

from ..http_client import PoliteClient, SourceError
from ..models import RawJob
from .base import json_body, valid_slug

API = "https://api.lever.co/v0/postings/{company}?mode=json"


def fetch(config: dict, client: PoliteClient, source_name: str) -> list[RawJob]:
    slug = valid_slug(config.get("company_slug"))
    company = str(config.get("company") or slug).strip()
    data = json_body(client.get(API.format(company=slug)))
    if not isinstance(data, list):
        raise SourceError("unexpected Lever payload (not a list)")
    out: list[RawJob] = []
    for posting in data:
        if not isinstance(posting, dict):
            continue
        cats = posting.get("categories") if isinstance(posting.get("categories"), dict) else {}
        location = cats.get("location") or ", ".join(str(x) for x in (cats.get("allLocations") or []))
        out.append(
            RawJob(
                source_name=source_name,
                source_job_id=str(posting.get("id") or "") or None,
                company=company,
                title=str(posting.get("text") or ""),
                url=str(posting.get("hostedUrl") or ""),
                apply_url=str(posting.get("applyUrl") or "") or None,
                location=str(location or ""),
                description_html=str(posting.get("descriptionPlain") or posting.get("description") or ""),
                employment_hint=str(cats.get("commitment") or ""),
                is_remote_flag=str(posting.get("workplaceType") or "").lower() == "remote",
                posted_at=posting.get("createdAt"),
            )
        )
    return out
