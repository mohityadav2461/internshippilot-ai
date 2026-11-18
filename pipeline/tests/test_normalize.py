from ipilot.models import RawJob
from ipilot.normalize import (
    canonical_url, classify_role, dedupe_key, detect_internship, html_to_text,
    is_india_location, normalize_title, parse_stipend, to_normalized,
)


def test_canonical_url_strips_tracking_and_fragments():
    assert canonical_url("http://www.Example.com/jobs/1/?utm_source=x&b=2&a=1#top") == \
        "https://example.com/jobs/1?a=1&b=2"


def test_canonical_url_removes_lever_tracking_param():
    assert canonical_url("https://jobs.lever.co/acme/abc?lever-source=LinkedIn") == \
        "https://jobs.lever.co/acme/abc"


def test_canonical_url_rejects_non_http_schemes():
    try:
        canonical_url("javascript:alert(1)")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_dedupe_key_collapses_company_suffix_and_location_decorations():
    a = dedupe_key("Acme Technologies Pvt Ltd", "SDE Intern (Remote) 2027")
    b = dedupe_key("Acme Technologies", "SDE Intern")
    assert a == b


def test_dedupe_key_keeps_distinct_role_suffixes_apart():
    assert dedupe_key("Acme", "SDE Intern - Backend") != dedupe_key("Acme", "SDE Intern - Frontend")


def test_location_segment_is_dropped_from_title():
    assert normalize_title("SDE Intern - Bengaluru") == normalize_title("SDE Intern")


def test_parse_stipend_monthly_and_ranges():
    assert parse_stipend("₹10,000 per month") == ("verified", 10000)
    assert parse_stipend("Rs. 8,000/month") == ("verified", 8000)
    assert parse_stipend("₹15k-20k/month") == ("verified", 15000)


def test_parse_stipend_converts_annual_to_monthly():
    assert parse_stipend("₹12 LPA") == ("verified", 100000)


def test_parse_stipend_flags_unpaid_and_unknown():
    assert parse_stipend("Unpaid internship") == ("unpaid", 0)
    assert parse_stipend(None) == ("not_verified", None)
    assert parse_stipend("Competitive") == ("not_verified", None)


def test_parse_stipend_ignores_years_and_durations():
    assert parse_stipend("Summer 2027, 2-3 months, stipend ₹10000 per month") == ("verified", 10000)


def test_internship_detection():
    assert detect_internship("Software Engineer Intern", "", "")
    assert not detect_internship("International Sales Manager", "", "")
    assert not detect_internship("Backend Engineer", "Full-time", "")
    assert detect_internship("Backend Engineer", "", "This summer internship program offers mentorship")


def test_role_classification_order():
    assert classify_role("Quant Research Intern") == "Quant"
    assert classify_role("Machine Learning Engineer Intern") == "ML"
    assert classify_role("Data Science Intern") == "DataScience"
    assert classify_role("Business Analyst Intern") == "Analyst"
    assert classify_role("Software Engineer Intern") == "SDE"
    assert classify_role("Marketing Intern") == "Other"


def test_india_location_uses_word_boundaries():
    assert is_india_location("Bengaluru, Karnataka, India")
    assert not is_india_location("Indianapolis, IN")
    assert not is_india_location("Remote - USA")
    assert not is_india_location("")


def test_html_to_text_decodes_and_strips_tags():
    text = html_to_text("&lt;p&gt;Build backend services&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;")
    assert "Build backend services" in text
    assert "Python" in text
    assert "<" not in text


def test_to_normalized_end_to_end():
    raw = RawJob(
        source_name="test", company="Acme", title="SDE Intern",
        url="https://boards.greenhouse.io/acme/jobs/1?gh_src=abc",
        location="Bengaluru, India",
        description_html="&lt;p&gt;Python services. Stipend ₹20,000 per month&lt;/p&gt;",
    )
    job = to_normalized(raw)
    assert job.canonical_url == "https://boards.greenhouse.io/acme/jobs/1"
    assert job.is_internship and job.role_category == "SDE"
    assert (job.stipend_status, job.stipend_min_inr) == ("verified", 20000)
    assert len(job.dedupe_key) == 40
