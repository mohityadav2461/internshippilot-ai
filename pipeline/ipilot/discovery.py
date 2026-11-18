"""Discovery orchestration: fetch, gate, deduplicate, persist, and record per-source health."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx

from .config import Settings
from .http_client import PoliteClient, SourceBlocked, SourceError
from .models import NormalizedJob
from .normalize import is_india_location, to_normalized
from .sources import ADAPTERS

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def discovery_gate(job: NormalizedJob) -> str | None:
    """Global rules that apply to every user: internships only, India only."""
    if not job.is_internship:
        return "not_internship"
    if not is_india_location(job.location):
        return "not_india"
    return None


def persist_jobs(store, items: list[NormalizedJob]) -> dict:
    """Idempotently store jobs. Duplicates merge into the existing row instead of creating a second one."""
    if not items:
        return {"new": 0, "merged": 0}

    first_by_url: dict[str, NormalizedJob] = {}
    for job in items:
        first_by_url.setdefault(job.canonical_url, job)

    by_key: dict[str, NormalizedJob] = {}
    extra_urls: dict[str, set[str]] = defaultdict(set)
    for job in first_by_url.values():
        if job.dedupe_key in by_key:
            extra_urls[job.dedupe_key].add(job.canonical_url)
        else:
            by_key[job.dedupe_key] = job

    existing_by_key = store.jobs_by_dedupe_keys(list(by_key))
    existing_by_url = store.jobs_by_canonical_urls([j.canonical_url for j in by_key.values()])

    now = _now()
    new_rows: list[dict] = []
    merged = 0
    for key, job in by_key.items():
        existing = existing_by_key.get(key) or existing_by_url.get(job.canonical_url)
        if existing is None:
            row = job.to_row(now)
            row["duplicate_urls"] = sorted(extra_urls.get(key, set()))
            new_rows.append(row)
            continue
        merged += 1
        known = set(existing.get("duplicate_urls") or [])
        urls = known | extra_urls.get(key, set())
        if job.canonical_url != existing["canonical_url"]:
            urls.add(job.canonical_url)
        patch: dict = {"last_seen_at": now, "is_active": True}
        if urls != known:
            patch["duplicate_urls"] = sorted(urls)
        store.touch_job(existing["id"], patch)

    store.insert_jobs(new_rows)
    return {"new": len(new_rows), "merged": merged}


def update_source_health(store, source: dict, *, ok: bool, found: int, error: str | None,
                         blocked: bool, failure_limit: int) -> bool:
    """Record health for one source. Returns False when the source was auto-disabled."""
    now = _now()
    data: dict = {"last_run_at": now}
    enabled = True
    if ok:
        data.update({"status": "ok", "last_success_at": now, "last_jobs_found": found,
                     "consecutive_failures": 0, "last_error": None})
    else:
        failures = int(source.get("consecutive_failures") or 0) + 1
        data.update({"status": "blocked" if blocked else "error", "consecutive_failures": failures,
                     "last_error": (error or "unknown error")[:500]})
        if failures >= failure_limit:
            enabled = False
            data.update({"enabled": False, "status": "disabled"})
            log.warning("source %s disabled after %d consecutive failures", source.get("name"), failures)
    store.update_source(source["id"], data)
    return enabled


def run_discovery(store, settings: Settings, client: PoliteClient, *,
                  only: set[str] | None = None, trigger: str = "manual") -> dict:
    run_id = store.create_run(trigger)
    rejected: dict[str, int] = {}
    errors: list[dict] = []
    stats: dict = {"sources_run": 0, "fetched": 0, "accepted": 0, "new": 0, "merged": 0,
                   "stale_deactivated": 0}
    collected: list[NormalizedJob] = []
    try:
        for source in store.enabled_sources():
            name = source["name"]
            if only and name not in only:
                continue
            stats["sources_run"] += 1
            try:
                adapter = ADAPTERS.get(source["adapter"])
                if adapter is None:
                    raise SourceError(f"unknown adapter {source['adapter']!r}")
                raw_jobs = adapter(source.get("config") or {}, client, name)
                accepted = 0
                for raw in raw_jobs:
                    stats["fetched"] += 1
                    try:
                        job = to_normalized(raw)
                    except ValueError:
                        rejected["invalid_record"] = rejected.get("invalid_record", 0) + 1
                        continue
                    reason = discovery_gate(job)
                    if reason:
                        rejected[reason] = rejected.get(reason, 0) + 1
                        continue
                    collected.append(job)
                    accepted += 1
                stats["accepted"] += accepted
                update_source_health(store, source, ok=True, found=len(raw_jobs), error=None,
                                     blocked=False, failure_limit=settings.consecutive_failure_limit)
            except SourceBlocked as exc:
                errors.append({"source": name, "error": str(exc)[:300], "blocked": True})
                update_source_health(store, source, ok=False, found=0, error=str(exc), blocked=True,
                                     failure_limit=settings.consecutive_failure_limit)
            except (SourceError, httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                message = f"{type(exc).__name__}: {exc}"
                errors.append({"source": name, "error": message[:300], "blocked": False})
                update_source_health(store, source, ok=False, found=0, error=message, blocked=False,
                                     failure_limit=settings.consecutive_failure_limit)

        persisted = persist_jobs(store, collected)
        stats.update(persisted)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.stale_after_days)).isoformat()
        stats["stale_deactivated"] = store.deactivate_stale(cutoff)
        stats["rejected"] = rejected
        succeeded = stats["sources_run"] - len(errors)
        status = "success" if not errors else ("partial" if succeeded > 0 else "failed")
        store.finish_run(run_id, status, stats, errors)
        return {"status": status, "errors": errors, **stats}
    except Exception as exc:
        stats["rejected"] = rejected
        errors.append({"source": "pipeline", "error": f"{type(exc).__name__}: {str(exc)[:250]}"})
        store.finish_run(run_id, "failed", stats, errors)
        raise
