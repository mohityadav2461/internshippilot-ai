from ipilot.gemini import AIScore, AIUnavailable
from ipilot.scoring_runner import run_scoring
from tests.fakes import MemoryStore, make_settings

PROFILE = {
    "id": "u1", "onboarding_complete": True, "ai_consent": True,
    "skills": ["Python", "SQL", "PyTorch", "Econometrics"],
    "degree": "BS Economics", "college": "IIT Kanpur", "graduation_year": 2028,
    "projects": [], "achievements": [],
    "filters": {"min_stipend_inr": 10000, "roles": ["SDE", "ML", "Analyst", "Quant", "DataScience", "Research"]},
}


def base_job(job_id, **overrides):
    job = {"id": job_id, "title": "Machine Learning Intern", "company": "Acme",
           "location": "Bengaluru, India", "description": "Python, PyTorch, time series forecasting, econometrics. Summer 2027, 3 months.",
           "is_internship": True, "role_category": "ML", "stipend_status": "verified",
           "stipend_min_inr": 15000, "is_active": True, "apply_url": f"https://boards.greenhouse.io/acme/{job_id}"}
    job.update(overrides)
    return job


JOBS = [
    base_job("j1"),
    base_job("j2", title="Software Engineer Intern", role_category="SDE", stipend_status="unpaid", stipend_min_inr=0),
    base_job("j3", title="Marketing Intern", role_category="Other"),
    base_job("j4", title="Software Engineer Intern", role_category="SDE", stipend_status="not_verified",
             stipend_min_inr=None, description="Build APIs in Python."),
]


class FakeGemini:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, 0

    def score(self, summary, text):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_scoring_filters_scores_and_queues_strong_matches():
    store = MemoryStore(profiles=[dict(PROFILE, ai_consent=False)], jobs=JOBS)
    stats = run_scoring(store, make_settings(), gemini=None)
    scored_ids = {s["job_id"] for s in store.scores}
    assert scored_ids == {"j1", "j4"}, "unpaid and non-target roles are excluded before scoring"
    assert stats["queued"] == 1
    assert [a["job_id"] for a in store.applications] == ["j1"]
    assert all(a["status"] == "pending_review" for a in store.applications)


def test_scoring_is_idempotent_across_runs():
    store = MemoryStore(profiles=[dict(PROFILE, ai_consent=False)], jobs=JOBS)
    run_scoring(store, make_settings(), gemini=None)
    second = run_scoring(store, make_settings(), gemini=None)
    assert second["scored"] == 0 and second["queued"] == 0
    assert len(store.scores) == 2 and len(store.applications) == 1


def test_gemini_blend_is_recorded_and_method_marked():
    store = MemoryStore(profiles=[PROFILE], jobs=[base_job("j1")])
    gemini = FakeGemini(result=AIScore(90, "Strong fit", ["Python"], ["Scale"]))
    run_scoring(store, make_settings(), gemini=gemini)
    row = store.scores[0]
    assert row["method"] == "hybrid_gemini"
    assert row["reasoning"]["ai"]["fit_score"] == 90
    assert gemini.calls == 1


def test_ai_failure_falls_back_to_deterministic_with_reason_flag():
    store = MemoryStore(profiles=[PROFILE], jobs=[base_job("j1")])
    gemini = FakeGemini(error=AIUnavailable("rate_limited", disable=True))
    stats = run_scoring(store, make_settings(), gemini=gemini)
    row = store.scores[0]
    assert row["method"] == "deterministic"
    assert "ai_fallback:rate_limited" in row["flags"]
    assert stats["ai_fallbacks"] == {"rate_limited": 1}


def test_ai_is_never_called_without_user_consent():
    store = MemoryStore(profiles=[dict(PROFILE, ai_consent=False)], jobs=[base_job("j1")])
    gemini = FakeGemini(result=AIScore(90, "x", [], []))
    run_scoring(store, make_settings(), gemini=gemini)
    assert gemini.calls == 0
