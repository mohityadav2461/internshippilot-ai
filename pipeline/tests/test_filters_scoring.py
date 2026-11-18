from ipilot.filters import UserFilters, evaluate_job
from ipilot.scoring import band_for, score_deterministic

PROFILE = {"skills": ["Python", "SQL", "PyTorch", "Econometrics"]}


def job(**overrides):
    base = {
        "title": "Machine Learning Intern",
        "description": "Python, PyTorch and time series forecasting. Summer 2027, 3 months.",
        "company": "Acme",
        "location": "Bengaluru, India",
        "is_internship": True,
        "role_category": "ML",
        "stipend_status": "verified",
        "stipend_min_inr": 15000,
    }
    base.update(overrides)
    return base


def test_filter_defaults_match_brief():
    f = UserFilters.from_dict(None)
    assert f.min_stipend_inr == 10000
    assert set(f.roles) == {"SDE", "Quant", "Analyst", "ML", "DataScience", "Research"}


def test_filter_sanitises_user_input():
    f = UserFilters.from_dict({"roles": ["Other", "ML", "bogus"], "min_stipend_inr": "15000"})
    assert f.roles == ("ML",)
    assert f.min_stipend_inr == 15000


def test_unpaid_and_below_minimum_are_rejected_with_reason():
    f = UserFilters.from_dict(None)
    assert "unpaid internship" in evaluate_job(job(stipend_status="unpaid", stipend_min_inr=0), f).reasons[0]
    decision = evaluate_job(job(stipend_min_inr=8000), f)
    assert not decision.passes and "below" in decision.reasons[0]


def test_undisclosed_stipend_passes_with_visible_flag():
    decision = evaluate_job(job(stipend_status="not_verified", stipend_min_inr=None), UserFilters.from_dict(None))
    assert decision.passes
    assert "Stipend not verified" in decision.flags


def test_undisclosed_stipend_can_be_excluded_in_settings():
    f = UserFilters.from_dict({"allow_stipend_unverified": False})
    assert not evaluate_job(job(stipend_status="not_verified", stipend_min_inr=None), f).passes


def test_location_rules():
    assert not evaluate_job(job(location="Remote - USA"), UserFilters.from_dict(None)).passes
    assert evaluate_job(job(location="Bengaluru, India"), UserFilters.from_dict({"locations": ["Bengaluru"]})).passes
    assert not evaluate_job(job(location="Bengaluru, India"), UserFilters.from_dict({"locations": ["Pune"]})).passes


def test_bands_follow_the_brief():
    assert band_for(85) == "Excellent"
    assert band_for(84) == "Good"
    assert band_for(70) == "Good"
    assert band_for(69) == "Moderate"
    assert band_for(50) == "Moderate"
    assert band_for(49) == "Low"


def test_strong_match_scores_high_with_transparent_components():
    result = score_deterministic(job(), PROFILE, UserFilters.from_dict(None))
    assert 0 <= result.score <= 100
    assert result.components["role_fit"]["points"] == 30
    assert set(result.components) == {"role_fit", "skill_match", "background", "logistics", "stipend"}
    assert "python" in [s.lower() for s in result.matched_skills]
    assert result.best_resume_tag == "ML"
    assert result.score >= 70


def test_description_only_role_gets_lower_role_points():
    result = score_deterministic(job(title="Summer Intern", role_category="SDE"), PROFILE, UserFilters.from_dict(None))
    assert result.components["role_fit"]["points"] == 20


def test_unverified_stipend_is_flagged_and_scored_lower():
    verified = score_deterministic(job(), PROFILE, UserFilters.from_dict(None))
    unknown = score_deterministic(job(stipend_status="not_verified", stipend_min_inr=None), PROFILE,
                                  UserFilters.from_dict(None))
    assert unknown.score < verified.score
    assert "Stipend not verified" in unknown.flags
