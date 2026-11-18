"""Greenhouse public Job Board API: https://boards-api.greenhouse.io/v1/boards/{board}/jobs"""

from __future__ import annotations

from ..http_client import PoliteClient, SourceError
from ..models import RawJob
from .base import json_body, valid_slug

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"


def fetch(config: dict, client: PoliteClient, source_name: str) -> list[RawJob]:
    board = valid_slug(config.get("board"))
    company = str(config.get("company") or board).strip()
    data = json_body(client.get(API.format(board=board)))
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise SourceError("unexpected Greenhouse payload (no jobs list)")
    out: list[RawJob] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        location = job.get("location")
        out.append(
            RawJob(
                source_name=source_name,
                source_job_id=str(job.get("id") or "") or None,
                company=company,
                title=str(job.get("title") or ""),
                url=str(job.get("absolute_url") or ""),
                location=str(location.get("name", "")) if isinstance(location, dict) else "",
                description_html=str(job.get("content") or ""),
                posted_at=job.get("updated_at") or None,
            )
        )
    return out
