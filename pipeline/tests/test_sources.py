import httpx

from ipilot.http_client import PoliteClient
from ipilot.sources import ADAPTERS
from ipilot.sources.greenhouse import fetch as greenhouse
from ipilot.sources.lever import fetch as lever
from ipilot.sources.ashby import fetch as ashby
from ipilot.sources.jsonld import fetch as jsonld
from ipilot.sources.rss import fetch as rss

UA = "InternshipPilotBot/1.0 (+https://example.com; bot@example.com)"


def client_with(routes: dict):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        key = f"{request.url.host}{request.url.path}"
        for pattern, response in routes.items():
            if key.startswith(pattern):
                return response
        return httpx.Response(404, text="not routed")
    return PoliteClient(UA, min_interval_s=0, backoff_s=0, transport=httpx.MockTransport(handler))


def test_registry_covers_all_adapters():
    assert set(ADAPTERS) == {"greenhouse", "lever", "ashby", "rss", "jsonld_pages"}


def test_greenhouse_parses_public_board_payload():
    payload = {"jobs": [{
        "id": 101, "title": "Software Engineer Intern",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/101?gh_src=x",
        "location": {"name": "Bengaluru, India"},
        "content": "&lt;p&gt;Build backend services&lt;/p&gt;",
        "updated_at": "2026-11-01T10:00:00Z",
    }]}
    with client_with({"boards-api.greenhouse.io": httpx.Response(200, json=payload)}) as client:
        jobs = greenhouse({"board": "acme", "company": "Acme"}, client, "gh:acme")
    assert len(jobs) == 1
    assert jobs[0].company == "Acme" and jobs[0].location == "Bengaluru, India"
    assert jobs[0].source_job_id == "101"


def test_greenhouse_rejects_bad_slug_before_any_request():
    with client_with({}) as client:
        try:
            greenhouse({"board": "../../etc"}, client, "gh:bad")
        except Exception as exc:
            assert "invalid board slug" in str(exc)
            return
    raise AssertionError("expected a slug error")


def test_lever_parses_postings_and_converts_epoch_ms():
    payload = [{
        "id": "abc", "text": "Data Analyst Intern", "hostedUrl": "https://jobs.lever.co/acme/abc",
        "applyUrl": "https://jobs.lever.co/acme/abc/apply",
        "categories": {"location": "Pune, India", "commitment": "Internship"},
        "descriptionPlain": "Analytics work", "createdAt": 1793000000000, "workplaceType": "onsite",
    }]
    with client_with({"api.lever.co": httpx.Response(200, json=payload)}) as client:
        jobs = lever({"company_slug": "acme", "company": "Acme"}, client, "lever:acme")
    assert jobs[0].employment_hint == "Internship"
    assert jobs[0].apply_url.endswith("/apply")
    assert jobs[0].posted_at is not None


def test_ashby_parses_board_and_compensation_summary():
    payload = {"jobs": [{
        "id": "r1", "title": "ML Intern", "location": "Bengaluru, India", "jobUrl": "https://jobs.ashbyhq.com/acme/r1",
        "applyUrl": "https://jobs.ashbyhq.com/acme/r1/application", "descriptionPlain": "Model work",
        "employmentType": "Intern", "isRemote": False, "publishedAt": "2026-11-02T00:00:00Z",
        "compensation": {"summary": "₹15,000 per month"},
    }]}
    with client_with({"api.ashbyhq.com": httpx.Response(200, json=payload)}) as client:
        jobs = ashby({"board": "acme", "company": "Acme"}, client, "ashby:acme")
    assert jobs[0].stipend_text == "₹15,000 per month"
    assert jobs[0].employment_hint == "Intern"


def test_rss_parses_items_with_configured_company_and_location():
    feed = """<?xml version="1.0"?><rss><channel><title>Feed</title>
      <item><title>Analyst Intern</title><link>https://careers.example.org/jobs/7</link>
      <description>Work with data</description><pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate></item>
    </channel></rss>"""
    with client_with({"careers.example.org": httpx.Response(200, text=feed)}) as client:
        jobs = rss({"feed_urls": ["https://careers.example.org/feed.xml"], "company": "Example Co", "location": "India"},
                   client, "rss:x")
    assert jobs[0].company == "Example Co" and jobs[0].location == "India"


def test_jsonld_extracts_job_postings_and_skips_unnamed_employers():
    page = """<html><script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
      {"@type":"JobPosting","title":"Quant Intern","url":"https://jobs.example.org/quant",
       "hiringOrganization":{"@type":"Organization","name":"Fund Co"},
       "jobLocation":{"@type":"Place","address":{"addressLocality":"Mumbai","addressCountry":"India"}},
       "description":"<p>Research</p>","employmentType":"INTERN",
       "baseSalary":{"@type":"MonetaryAmount","currency":"INR","value":{"@type":"QuantitativeValue","value":20000,"unitText":"MONTH"}}},
      {"@type":"JobPosting","title":"Anonymous role"}
    ]}</script></html>"""
    with client_with({"jobs.example.org": httpx.Response(200, text=page)}) as client:
        jobs = jsonld({"seed_urls": ["https://jobs.example.org/listing"]}, client, "jsonld:x")
    assert len(jobs) == 1
    assert jobs[0].company == "Fund Co" and jobs[0].location == "Mumbai, India"
    assert jobs[0].stipend_text == "INR 20000 per month"
