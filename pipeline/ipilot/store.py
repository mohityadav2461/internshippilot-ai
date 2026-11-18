"""Supabase PostgREST persistence using the service role key (server and CI only)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .config import Settings
from .gemini import utc_day

CHUNK = 200


class StoreError(RuntimeError):
    pass


def _chunks(items: list, size: int = CHUNK):
    for index in range(0, len(items), size):
        yield items[index:index + size]


class SupabaseStore:
    def __init__(self, settings: Settings, http: httpx.Client | None = None) -> None:
        settings.require_database()
        self._base = f"{settings.supabase_url}/rest/v1"
        self._http = http or httpx.Client(
            timeout=settings.http_timeout_s,
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def _check(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise StoreError(f"Supabase {resp.status_code}: {resp.text[:300]}")

    def select(self, table: str, **params: str) -> list[dict]:
        resp = self._http.get(f"{self._base}/{table}", params=params)
        self._check(resp)
        return resp.json()

    def insert(self, table: str, rows: list[dict], *, on_conflict: str | None = None,
               ignore_duplicates: bool = False, return_rows: bool = False) -> list[dict]:
        out: list[dict] = []
        for chunk in _chunks(rows):
            prefer = ["return=representation" if return_rows else "return=minimal"]
            params = {}
            if on_conflict:
                params["on_conflict"] = on_conflict
                prefer.append("resolution=ignore-duplicates" if ignore_duplicates else "resolution=merge-duplicates")
            resp = self._http.post(f"{self._base}/{table}", params=params, json=chunk,
                                   headers={"Prefer": ",".join(prefer)})
            self._check(resp)
            if return_rows:
                out.extend(resp.json())
        return out

    def patch(self, table: str, data: dict, *, filters: dict[str, str], return_rows: bool = False) -> list[dict]:
        resp = self._http.patch(
            f"{self._base}/{table}", params=filters, json=data,
            headers={"Prefer": "return=representation" if return_rows else "return=minimal"},
        )
        self._check(resp)
        return resp.json() if return_rows else []

    @staticmethod
    def _in(values: list[str]) -> str:
        """PostgREST list filter. Every value is double-quoted so commas and parentheses in URLs are safe."""
        quoted = ",".join('"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values)
        return f"in.({quoted})"

    # ---- pipeline runs ----------------------------------------------------
    def create_run(self, trigger: str) -> str:
        rows = self.insert("pipeline_runs", [{"trigger": trigger, "status": "running"}], return_rows=True)
        return str(rows[0]["id"])

    def finish_run(self, run_id: str, status: str, stats: dict, errors: list[dict]) -> None:
        self.patch("pipeline_runs", {
            "status": status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
            "errors": errors,
        }, filters={"id": f"eq.{run_id}"})

    # ---- sources ----------------------------------------------------------
    def enabled_sources(self) -> list[dict]:
        return self.select("job_sources", select="*", enabled="eq.true", order="name.asc")

    def update_source(self, source_id: str, data: dict) -> None:
        self.patch("job_sources", data, filters={"id": f"eq.{source_id}"})

    # ---- jobs -------------------------------------------------------------
    def jobs_by_dedupe_keys(self, keys: list[str]) -> dict[str, dict]:
        found: dict[str, dict] = {}
        for chunk in _chunks(keys, 100):
            rows = self.select("jobs", select="id,dedupe_key,canonical_url,duplicate_urls",
                               dedupe_key=self._in(chunk), limit="1000")
            found.update({row["dedupe_key"]: row for row in rows})
        return found

    def jobs_by_canonical_urls(self, urls: list[str]) -> dict[str, dict]:
        found: dict[str, dict] = {}
        for chunk in _chunks(urls, 50):
            rows = self.select("jobs", select="id,dedupe_key,canonical_url,duplicate_urls",
                               canonical_url=self._in(chunk), limit="1000")
            found.update({row["canonical_url"]: row for row in rows})
        return found

    def insert_jobs(self, rows: list[dict]) -> None:
        self.insert("jobs", rows, on_conflict="canonical_url", ignore_duplicates=True)

    def touch_job(self, job_id: str, data: dict) -> None:
        self.patch("jobs", data, filters={"id": f"eq.{job_id}"})

    def deactivate_stale(self, cutoff_iso: str) -> int:
        rows = self.patch("jobs", {"is_active": False},
                          filters={"is_active": "eq.true", "last_seen_at": f"lt.{cutoff_iso}"},
                          return_rows=True)
        return len(rows)

    def active_jobs(self, limit: int = 2000) -> list[dict]:
        return self.select("jobs", select="*", is_active="eq.true",
                           order="last_seen_at.desc", limit=str(limit))

    # ---- profiles and scoring --------------------------------------------
    def onboarded_profiles(self) -> list[dict]:
        return self.select("profiles", select="*", onboarding_complete="eq.true")

    def scored_job_ids(self, user_id: str, version: str) -> set[str]:
        rows = self.select("job_scores", select="job_id", user_id=f"eq.{user_id}",
                           scoring_version=f"eq.{version}", limit="5000")
        return {row["job_id"] for row in rows}

    def upsert_scores(self, rows: list[dict]) -> None:
        self.insert("job_scores", rows, on_conflict="user_id,job_id,scoring_version", ignore_duplicates=True)

    def queue_applications(self, rows: list[dict]) -> int:
        inserted = self.insert("applications", rows, on_conflict="user_id,job_id",
                               ignore_duplicates=True, return_rows=True)
        return len(inserted)

    # ---- inspection -------------------------------------------------------
    def pending_inspections(self, limit: int) -> list[dict]:
        return self.select(
            "applications",
            select="id,status,jobs(apply_url,canonical_url)",
            form_schema="is.null",
            status="in.(pending_review,approved_manual)",
            order="created_at.asc",
            limit=str(limit),
        )

    def application_for_prefill(self, application_id: str) -> dict | None:
        rows = self.select(
            "applications",
            select="id,status,form_answers,cover_letter,jobs(apply_url,company,title)",
            id=f"eq.{application_id}",
            limit="1",
        )
        return rows[0] if rows else None

    def set_form_schema(self, application_id: str, schema: dict) -> None:
        self.patch("applications", {"form_schema": schema}, filters={"id": f"eq.{application_id}"})

    # ---- quota ledger -----------------------------------------------------
    def ai_calls_today(self) -> int:
        rows = self.select("ai_usage_daily", select="calls", day=f"eq.{utc_day()}")
        return int(rows[0]["calls"]) if rows else 0

    def increment_ai_calls(self, n: int) -> None:
        current = self.ai_calls_today()
        self.insert("ai_usage_daily", [{"day": utc_day(), "calls": current + n}],
                    on_conflict="day", ignore_duplicates=False)
