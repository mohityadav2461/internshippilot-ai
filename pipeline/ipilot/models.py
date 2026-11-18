"""Data shapes shared by sources, normalisation and persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class RawJob:
    """A posting exactly as a source reported it, before any cleaning."""

    source_name: str
    company: str
    title: str
    url: str
    location: str = ""
    description_html: str = ""
    employment_hint: str = ""
    posted_at: str | None = None
    source_job_id: str | None = None
    stipend_text: str | None = None
    is_remote_flag: bool | None = None
    apply_url: str | None = None


@dataclass
class NormalizedJob:
    """A cleaned posting. Field names match the public.jobs columns one-to-one."""

    source_name: str
    source_job_id: str | None
    canonical_url: str
    apply_url: str
    dedupe_key: str
    company: str
    title: str
    normalized_company: str
    normalized_title: str
    location: str
    is_remote: bool
    is_internship: bool
    role_category: str
    description: str
    posted_at: str | None
    stipend_text: str | None
    stipend_status: str
    stipend_min_inr: int | None

    def to_row(self, seen_at: str | None = None) -> dict:
        row = asdict(self)
        row["last_seen_at"] = seen_at or datetime.now(timezone.utc).isoformat()
        row["duplicate_urls"] = []
        return row
