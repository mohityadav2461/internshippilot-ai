"""Ashby public job board API: https://api.ashbyhq.com/posting-api/job-board/{board}"""

from __future__ import annotations

from ..http_client import PoliteClient, SourceError
from ..models import RawJob
from .base import json_body, valid_slug

API = "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"


def fetch(config: dict, client: PoliteClient, source_name: str) -> list[RawJob]:
    board = valid_slug(config.get("board"))
    company = str(config.get("company") or board).strip()
    data = json_body(client.get(API.format(board=board)))
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise SourceError("unexpected Ashby payload (no jobs list)")
    out: list[RawJob] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        location = str(job.get("location") or "")
        if not location and isinstance(job.get("secondaryLocations"), list):
            location = ", ".join(str(item.get("location", "")) for item in job["secondaryLocations"] if isinstance(item, dict))
        comp = job.get("compensation")
        stipend = comp.get("summary") if isinstance(comp, dict) and isinstance(comp.get("summary"), str) else None
        out.append(
            RawJob(
                source_name=source_name,
                source_job_id=str(job.get("id") or "") or None,
                company=company,
                title=str(job.get("title") or ""),
                url=str(job.get("jobUrl") or ""),
                apply_url=str(job.get("applyUrl") or "") or None,
                location=location,
                description_html=str(job.get("descriptionHtml") or job.get("descriptionPlain") or ""),
                employment_hint=str(job.get("employmentType") or ""),
                is_remote_flag=bool(job.get("isRemote")),
                posted_at=job.get("publishedAt") or None,
                stipend_text=stipend,
            )
        )
    return out
