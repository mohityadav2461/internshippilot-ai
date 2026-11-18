"""Command-line entry points. Used by GitHub Actions and by hand: python -m ipilot <command>."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid

from .config import Settings
from .discovery import run_discovery
from .gemini import GeminiScorer, QuotaGuard
from .http_client import PoliteClient
from .prefill import OPEN_STATUSES, run_prefill, validate_resume
from .scoring_runner import run_scoring
from .store import SupabaseStore


def _logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def modes_for(mode: str) -> tuple[bool, bool, bool]:
    """Which steps a pipeline mode runs, as (discover, score, inspect).

    scan is what the frequent scheduled run uses: discover and score only, no browser.
    """
    return (
        mode in ("full", "discover", "scan"),
        mode in ("full", "score", "scan"),
        mode in ("full", "inspect"),
    )


def _gemini(settings: Settings, store: SupabaseStore) -> GeminiScorer | None:
    if not settings.gemini_enabled:
        return None
    import httpx

    guard = QuotaGuard(store, settings.gemini_daily_cap, settings.gemini_run_cap)
    return GeminiScorer(settings.gemini_api_key, settings.gemini_model, guard, httpx.Client(timeout=30))


def cmd_discover(settings: Settings, store: SupabaseStore, only: set[str] | None, trigger: str) -> dict:
    with PoliteClient(settings.user_agent, min_interval_s=settings.min_interval_s,
                      timeout_s=settings.http_timeout_s) as client:
        return run_discovery(store, settings, client, only=only, trigger=trigger)


def cmd_score(settings: Settings, store: SupabaseStore, user_id: str | None) -> dict:
    return run_scoring(store, settings, user_id=user_id, gemini=_gemini(settings, store), trigger="score")


def cmd_inspect(settings: Settings, store: SupabaseStore, limit: int) -> dict:
    from .form_inspector import inspect_url

    results = {"inspected": 0, "failed": 0, "statuses": {}}
    rows = store.pending_inspections(limit)
    with PoliteClient(settings.user_agent, min_interval_s=settings.min_interval_s,
                      timeout_s=settings.http_timeout_s) as client:
        for row in rows:
            job = row.get("jobs") or {}
            url = job.get("apply_url") or ""
            try:
                schema = inspect_url(url, client, settings.user_agent)
            except Exception as exc:  # one bad page must not stop the batch
                schema = {"status": "error", "fields": [], "error": f"{type(exc).__name__}"}
                results["failed"] += 1
            results["statuses"][schema["status"]] = results["statuses"].get(schema["status"], 0) + 1
            store.set_form_schema(row["id"], schema)
            results["inspected"] += 1
    return results


def cmd_prefill(settings: Settings, store: SupabaseStore, application_id: str, resume: str) -> dict:
    try:
        uuid.UUID(application_id)
    except ValueError:
        return {"status": "invalid_id", "message": "Copy the application id from the end of its Pending page address."}
    error = validate_resume(resume)
    if error:
        return {"status": "bad_resume", "message": error}
    application = store.application_for_prefill(application_id)
    if application is None:
        return {"status": "not_found", "message": "No application has that id."}
    if application.get("status") not in OPEN_STATUSES:
        return {"status": "not_pending",
                "message": f"This application is already marked {application.get('status')}, so there is nothing to prefill."}
    return run_prefill(application, settings, resume)


def main(argv: list[str] | None = None) -> int:
    _logging()
    parser = argparse.ArgumentParser(prog="ipilot", description="InternshipPilot AI pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_discover = sub.add_parser("discover", help="fetch, filter, dedupe and store jobs")
    p_discover.add_argument("--sources", default="", help="comma-separated source names (default: all enabled)")
    p_discover.add_argument("--trigger", default="manual")

    p_score = sub.add_parser("score", help="score new jobs for onboarded users and queue strong matches")
    p_score.add_argument("--user", default="", help="limit to one user id")

    p_inspect = sub.add_parser("inspect", help="read-only Playwright inspection of pending application forms")
    p_inspect.add_argument("--limit", type=int, default=5)

    p_pipeline = sub.add_parser("pipeline", help="run the steps for a mode")
    p_pipeline.add_argument("--mode", choices=["full", "scan", "discover", "score", "inspect"], default="full")
    p_pipeline.add_argument("--inspect-limit", type=int, default=5)

    sub.add_parser("health", help="print the source registry and its live health")

    p_prefill = sub.add_parser("prefill", help="open one pending application on this computer and fill it; never submits")
    p_prefill.add_argument("application_id", help="the id at the end of the application's Pending page address")
    p_prefill.add_argument("--resume", default="", help="path to your resume PDF on this computer")

    args = parser.parse_args(argv)
    settings = Settings.from_env()
    logging.info("Connecting to database at: %s", settings.supabase_url)
    try:
        store = SupabaseStore(settings)
    except Exception as exc:  # configuration problem: fail with a clear message, no stack trace
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    failed = False
    if args.command == "discover":
        only = {s.strip() for s in args.sources.split(",") if s.strip()} or None
        result = cmd_discover(settings, store, only, args.trigger)
        failed = result["status"] == "failed"
        print(result)
    elif args.command == "score":
        print(cmd_score(settings, store, args.user or None))
    elif args.command == "inspect":
        print(cmd_inspect(settings, store, args.limit))
    elif args.command == "pipeline":
        run_discover, run_score, run_inspect = modes_for(args.mode)
        if run_discover:
            result = cmd_discover(settings, store, None, "schedule")
            failed = result["status"] == "failed"
            print({"discover": result})
        if run_score:
            print({"score": cmd_score(settings, store, None)})
        if run_inspect:
            print({"inspect": cmd_inspect(settings, store, args.inspect_limit)})
    elif args.command == "health":
        for source in store.enabled_sources():
            print(source["name"], source["status"], source.get("last_error") or "")
    elif args.command == "prefill":
        print(cmd_prefill(settings, store, args.application_id, args.resume))
    return 1 if failed else 0
