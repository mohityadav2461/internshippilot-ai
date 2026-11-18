import httpx

from ipilot.discovery import run_discovery
from ipilot.http_client import PoliteClient
from tests.fakes import MemoryStore, make_settings

GREENHOUSE = {"jobs": [
    {"id": 101, "title": "Software Engineer Intern", "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
     "location": {"name": "Bengaluru, India"}, "content": "&lt;p&gt;Python services. Summer 2027, 2 months&lt;/p&gt;",
     "updated_at": "2026-11-01T10:00:00Z"},
    {"id": 102, "title": "Data Science Intern", "absolute_url": "https://boards.greenhouse.io/acme/jobs/102",
     "location": {"name": "Remote - USA"}, "content": "<p>Internship</p>", "updated_at": "2026-11-01T10:00:00Z"},
    {"id": 103, "title": "Senior Platform Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/103",
     "location": {"name": "Bengaluru, India"}, "content": "Full time", "updated_at": "2026-11-01T10:00:00Z"},
]}
LEVER = [{
    "id": "abc", "text": "Software Engineer Intern", "hostedUrl": "https://jobs.lever.co/acme/abc",
    "categories": {"location": "Bengaluru, India", "commitment": "Internship"},
    "descriptionPlain": "Python", "createdAt": 1793000000000,
}]


def transport(extra=None):
    def handler(request):
        host, path = request.url.host, request.url.path
        if path == "/robots.txt":
            return httpx.Response(404)
        if host == "boards-api.greenhouse.io" and extra and "/broken/" in path:
            return httpx.Response(500, text="boom")
        if host == "boards-api.greenhouse.io":
            return httpx.Response(200, json=GREENHOUSE)
        if host == "api.lever.co":
            return httpx.Response(200, json=LEVER)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def sources():
    return [
        {"id": "s1", "name": "greenhouse:acme", "adapter": "greenhouse", "enabled": True,
         "config": {"board": "acme", "company": "Acme"}, "consecutive_failures": 0},
        {"id": "s2", "name": "lever:acme", "adapter": "lever", "enabled": True,
         "config": {"company_slug": "acme", "company": "Acme"}, "consecutive_failures": 0},
    ]


def test_discovery_gates_dedupes_and_merges_across_sources():
    store = MemoryStore(sources=sources())
    client = PoliteClient("bot", min_interval_s=0, backoff_s=0, transport=transport())
    result = run_discovery(store, make_settings(), client)

    assert result["status"] == "success"
    assert result["rejected"] == {"not_india": 1, "not_internship": 1}
    assert len(store.jobs) == 1, "same company and title across two boards must become one job"
    job = store.jobs[0]
    assert job["canonical_url"] == "https://boards.greenhouse.io/acme/jobs/101"
    assert job["duplicate_urls"] == ["https://jobs.lever.co/acme/abc"]
    assert all(s["status"] == "ok" for s in store.sources)


def test_rerun_is_idempotent():
    store = MemoryStore(sources=sources())
    client = PoliteClient("bot", min_interval_s=0, backoff_s=0, transport=transport())
    run_discovery(store, make_settings(), client)
    second = run_discovery(store, make_settings(), client)
    assert len(store.jobs) == 1
    assert second["new"] == 0


def test_failing_source_is_recorded_then_disabled_at_limit():
    failing = [{"id": "s9", "name": "greenhouse:broken", "adapter": "greenhouse", "enabled": True,
                "config": {"board": "broken", "company": "Broken"}, "consecutive_failures": 0}]
    store = MemoryStore(sources=failing)
    client = PoliteClient("bot", min_interval_s=0, backoff_s=0, transport=transport(extra={"boards-api.greenhouse.io"}))
    settings = make_settings(consecutive_failure_limit=1)
    result = run_discovery(store, settings, client)
    source = store.sources[0]
    assert result["status"] == "failed"
    assert source["enabled"] is False and source["status"] == "disabled"
    assert "HTTP 500" in source["last_error"]
