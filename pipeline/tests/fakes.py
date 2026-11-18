"""In-memory stand-ins for the Supabase store and Settings, used by the test suite."""

from __future__ import annotations

from ipilot.config import Settings


def make_settings(**overrides) -> Settings:
    base = dict(
        supabase_url="https://example.supabase.co",
        supabase_service_key="s" * 40,
        gemini_api_key="",
        gemini_model="gemini-2.5-flash",
        gemini_daily_cap=40,
        gemini_run_cap=25,
        ai_enabled=True,
        contact_url="https://example.com/bot",
        contact_email="bot@example.com",
        min_interval_s=0.0,
        http_timeout_s=5.0,
        stale_after_days=21,
        consecutive_failure_limit=5,
    )
    base.update(overrides)
    return Settings(**base)


class MemoryStore:
    """Implements the subset of SupabaseStore used by discovery, scoring and inspection."""

    def __init__(self, sources=None, profiles=None, jobs=None) -> None:
        self.sources = [dict(s) for s in (sources or [])]
        self.profiles = list(profiles or [])
        self.jobs = [dict(j) for j in (jobs or [])]
        self.scores: list[dict] = []
        self.applications: list[dict] = []
        self.runs: dict[str, dict] = {}
        self.ai_calls = 0
        self._next = 1

    def _id(self, prefix: str) -> str:
        self._next += 1
        return f"{prefix}{self._next}"

    # runs
    def create_run(self, trigger):
        run_id = self._id("run")
        self.runs[run_id] = {"trigger": trigger, "status": "running"}
        return run_id

    def finish_run(self, run_id, status, stats, errors):
        self.runs[run_id].update(status=status, stats=stats, errors=errors)

    # sources
    def enabled_sources(self):
        return [s for s in self.sources if s.get("enabled", True)]

    def update_source(self, source_id, data):
        for source in self.sources:
            if source["id"] == source_id:
                source.update(data)

    # jobs
    def jobs_by_dedupe_keys(self, keys):
        return {j["dedupe_key"]: j for j in self.jobs if j["dedupe_key"] in keys}

    def jobs_by_canonical_urls(self, urls):
        return {j["canonical_url"]: j for j in self.jobs if j["canonical_url"] in urls}

    def insert_jobs(self, rows):
        for row in rows:
            if any(j["canonical_url"] == row["canonical_url"] for j in self.jobs):
                continue
            self.jobs.append({**row, "id": self._id("job"), "is_active": row.get("is_active", True)})

    def touch_job(self, job_id, data):
        for job in self.jobs:
            if job["id"] == job_id:
                job.update(data)

    def deactivate_stale(self, cutoff_iso):
        count = 0
        for job in self.jobs:
            if job.get("is_active") and job.get("last_seen_at", "") < cutoff_iso:
                job["is_active"] = False
                count += 1
        return count

    def active_jobs(self, limit=2000):
        return [j for j in self.jobs if j.get("is_active", True)][:limit]

    # profiles and scoring
    def onboarded_profiles(self):
        return [p for p in self.profiles if p.get("onboarding_complete")]

    def scored_job_ids(self, user_id, version):
        return {s["job_id"] for s in self.scores if s["user_id"] == user_id and s["scoring_version"] == version}

    def upsert_scores(self, rows):
        for row in rows:
            exists = any(s["user_id"] == row["user_id"] and s["job_id"] == row["job_id"]
                         and s["scoring_version"] == row["scoring_version"] for s in self.scores)
            if not exists:
                self.scores.append(dict(row))

    def queue_applications(self, rows):
        added = 0
        for row in rows:
            exists = any(a["user_id"] == row["user_id"] and a["job_id"] == row["job_id"] for a in self.applications)
            if not exists:
                self.applications.append({**row, "id": self._id("app"), "form_schema": None})
                added += 1
        return added

    # inspection
    def pending_inspections(self, limit):
        out = []
        for app in self.applications:
            if app.get("form_schema") is None and app["status"] in ("pending_review", "approved_manual"):
                job = next((j for j in self.jobs if j["id"] == app["job_id"]), {})
                out.append({"id": app["id"], "status": app["status"], "jobs": {"apply_url": job.get("apply_url", "")}})
        return out[:limit]

    def set_form_schema(self, app_id, schema):
        for app in self.applications:
            if app["id"] == app_id:
                app["form_schema"] = schema

    # quota ledger
    def ai_calls_today(self):
        return self.ai_calls

    def increment_ai_calls(self, n):
        self.ai_calls += n
