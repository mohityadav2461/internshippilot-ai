"""Scores every onboarded user's new jobs and queues strong matches for human review.

Idempotent: a (user, job, scoring_version) triple is scored once, and the queue never
re-adds a job the user has already acted on. Nothing here submits an application.
"""

from __future__ import annotations

import logging
import re

from .config import Settings
from .filters import UserFilters, evaluate_job
from .gemini import AIUnavailable, GeminiScorer, blend, build_profile_summary
from .notify import notify_queued
from .scoring import SCORING_VERSION, band_for, score_deterministic

log = logging.getLogger(__name__)

AI_MIN_DETERMINISTIC = 55  # only plausible matches are worth a Gemini call
QUEUE_BANDS = ("Excellent", "Good")


def _reason_key(reason: str) -> str:
    return re.sub(r"[\d,]+", "#", reason)


def job_text(job: dict) -> str:
    return "\n".join(str(job.get(k) or "") for k in ("title", "company", "location", "description"))


def run_scoring(store, settings: Settings, *, user_id: str | None = None,
                gemini: GeminiScorer | None = None, trigger: str = "score") -> dict:
    run_id = store.create_run(trigger)
    stats: dict = {"users": 0, "scored": 0, "filtered": {}, "queued": 0,
                   "ai_hybrid": 0, "ai_fallbacks": {}, "ai_enabled": gemini is not None,
                   "notified": False}
    queued_all: list[dict] = []
    errors: list[dict] = []
    try:
        profiles = store.onboarded_profiles()
        if user_id:
            profiles = [p for p in profiles if p["id"] == user_id]
        jobs = store.active_jobs(limit=2000)

        for profile in profiles:
            stats["users"] += 1
            filters = UserFilters.from_dict(profile.get("filters"))
            done = store.scored_job_ids(profile["id"], SCORING_VERSION)
            ai_allowed = gemini is not None and profile.get("ai_consent") is True
            summary = build_profile_summary(profile) if ai_allowed else ""

            scored = []
            for job in jobs:
                if job["id"] in done:
                    continue
                decision = evaluate_job(job, filters)
                if not decision.passes:
                    for reason in decision.reasons:
                        key = _reason_key(reason)
                        stats["filtered"][key] = stats["filtered"].get(key, 0) + 1
                    continue
                scored.append((job, score_deterministic(job, profile, filters), decision))

            scored.sort(key=lambda item: item[1].score, reverse=True)
            rows: list[dict] = []
            queue: list[dict] = []
            for job, det, decision in scored:
                final = det.score
                method = "deterministic"
                reasoning = det.reasoning()
                flags = list(dict.fromkeys(det.flags + decision.flags))
                if ai_allowed and det.score >= AI_MIN_DETERMINISTIC:
                    try:
                        ai = gemini.score(summary, job_text(job))  # type: ignore[union-attr]
                        final = blend(det.score, ai.fit_score)
                        method = "hybrid_gemini"
                        reasoning["ai"] = ai.as_dict()
                        stats["ai_hybrid"] += 1
                    except AIUnavailable as exc:
                        flags.append(f"ai_fallback:{exc.reason}")
                        stats["ai_fallbacks"][exc.reason] = stats["ai_fallbacks"].get(exc.reason, 0) + 1
                        if exc.disable:
                            ai_allowed = False
                band = band_for(final)
                rows.append({
                    "user_id": profile["id"],
                    "job_id": job["id"],
                    "score": final,
                    "band": band,
                    "method": method,
                    "scoring_version": SCORING_VERSION,
                    "reasoning": reasoning,
                    "flags": flags,
                    "best_resume_tag": det.best_resume_tag,
                })
                if final >= filters.auto_queue_score and band in QUEUE_BANDS:
                    queue.append({"user_id": profile["id"], "job_id": job["id"],
                                  "status": "pending_review", "score": final})
                    queued_all.append({"company": job.get("company"), "title": job.get("title"), "score": final})

            store.upsert_scores(rows)
            stats["scored"] += len(rows)
            stats["queued"] += store.queue_applications(queue) if queue else 0

        if queued_all and settings.ntfy_topic:
            stats["notified"] = notify_queued(settings.ntfy_topic, queued_all)

        status = "success"
        store.finish_run(run_id, status, stats, errors)
        return {"status": status, **stats}
    except Exception as exc:
        errors.append({"source": "scoring", "error": f"{type(exc).__name__}: {str(exc)[:250]}"})
        store.finish_run(run_id, "failed", stats, errors)
        raise
