import httpx
import pytest

from ipilot.gemini import (
    AIUnavailable, GeminiScorer, QuotaGuard, blend, build_profile_summary, parse_ai_response, redact_pii,
)
from tests.fakes import MemoryStore


def payload(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_redaction_removes_contact_details():
    text = "Mail me at jane.doe@iitk.ac.in or +91 98765 43210, portfolio https://jane.dev/work"
    out = redact_pii(text)
    assert "@" not in out and "98765" not in out and "jane.dev" not in out
    assert "[email]" in out and "[phone]" in out and "[url]" in out


def test_profile_summary_never_includes_identifiers():
    profile = {"full_name": "Jane Doe", "email": "jane@x.com", "phone": "+919876543210",
               "linkedin_url": "https://linkedin.com/in/jane", "degree": "BS Economics",
               "college": "IIT Kanpur", "graduation_year": 2028, "skills": ["Python"],
               "projects": [{"name": "Forecasting", "tech": ["Python"], "summary": "Demand model"}],
               "achievements": []}
    summary = build_profile_summary(profile)
    assert "Jane Doe" not in summary and "jane@x.com" not in summary and "linkedin" not in summary
    assert "Python" in summary and "Forecasting" in summary


def test_parse_clamps_score_and_truncates_lists():
    parsed = parse_ai_response(payload('{"fit_score": 150, "summary": "ok", "strengths": ["a","b","c","d","e"], "gaps": []}'))
    assert parsed.fit_score == 100
    assert len(parsed.strengths) == 4


def test_parse_rejects_non_json_and_missing_score():
    with pytest.raises(AIUnavailable, match="bad_json"):
        parse_ai_response(payload("not json"))
    with pytest.raises(AIUnavailable, match="bad_fit_score"):
        parse_ai_response(payload('{"summary": "x"}'))


def test_blend_weights_deterministic_majority():
    assert blend(80, 90) == 84
    assert blend(100, 100) == 100


def test_quota_guard_blocks_before_any_http_call():
    store = MemoryStore()
    store.ai_calls = 40
    guard = QuotaGuard(store, daily_cap=40, run_cap=25)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=payload('{"fit_score": 50}'))

    scorer = GeminiScorer("k", "gemini-2.5-flash", guard, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(AIUnavailable) as info:
        scorer.score("summary", "job")
    assert info.value.reason == "quota_guard_reached"
    assert calls["n"] == 0


def test_successful_call_is_counted_and_parsed():
    store = MemoryStore()
    guard = QuotaGuard(store, daily_cap=40, run_cap=25)
    handler = lambda r: httpx.Response(200, json=payload('{"fit_score": 77, "summary": "Good", "strengths": ["x"], "gaps": []}'))
    scorer = GeminiScorer("k", "gemini-2.5-flash", guard, httpx.Client(transport=httpx.MockTransport(handler)))
    result = scorer.score("summary", "job text")
    assert result.fit_score == 77
    assert store.ai_calls == 1


@pytest.mark.parametrize("status, reason, disables", [
    (429, "rate_limited", True),
    (403, "auth_rejected", True),
    (500, "upstream_error", False),
])
def test_error_classification(status, reason, disables):
    store = MemoryStore()
    guard = QuotaGuard(store, daily_cap=40, run_cap=25)
    handler = lambda r: httpx.Response(status, text="{}")
    scorer = GeminiScorer("k", "gemini-2.5-flash", guard, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(AIUnavailable) as info:
        scorer.score("s", "j")
    assert info.value.reason == reason
    assert info.value.disable is disables


def test_resource_exhausted_disables_ai_for_run():
    store = MemoryStore()
    guard = QuotaGuard(store, daily_cap=40, run_cap=25)
    handler = lambda r: httpx.Response(429, text='{"error":{"status":"RESOURCE_EXHAUSTED"}}')
    scorer = GeminiScorer("k", "gemini-2.5-flash", guard, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(AIUnavailable) as info:
        scorer.score("s", "j")
    assert info.value.disable is True
