"""Deterministic 0-100 scoring with transparent per-component reasoning.

Components (max points): role fit 30, skill match 35, IITK BS Economics background 15,
logistics 10 (India verified, summer / 2-3 month and 2027 signals), stipend 10.
Bands: 85-100 Excellent, 70-84 Good, 50-69 Moderate, below 50 Low.
The Gemini blend (see scoring_runner) can adjust the final number, and the method is stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .filters import UserFilters
from .normalize import TAG_FOR_CATEGORY, role_from_title

SCORING_VERSION = "v1"

BACKGROUND_TERMS = (
    "econometrics", "economics", "statistics", "probability", "finance", "quantitative",
    "forecasting", "regression", "causal", "time series", "portfolio", "risk", "markets",
)
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "javascript": ("js",),
    "typescript": ("ts",),
    "postgresql": ("postgres",),
    "machine learning": ("ml",),
    "node.js": ("node", "nodejs", "node js"),
    "react": ("react.js", "reactjs"),
    "pytorch": ("torch",),
}
_DURATION_RE = re.compile(r"\b(?:2|3|two|three)\s*(?:-|to|–)?\s*(?:3\s*)?months?\b|\bsummer\b", re.IGNORECASE)
_START_RE = re.compile(r"\b2027\b")


def band_for(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Moderate"
    return "Low"


@dataclass
class ScoreResult:
    score: int
    band: str
    components: dict
    matched_skills: list[str]
    background_terms: list[str]
    flags: list[str] = field(default_factory=list)
    best_resume_tag: str = "SDE"

    def reasoning(self) -> dict:
        return {
            "components": self.components,
            "matched_skills": self.matched_skills,
            "background_terms": self.background_terms,
        }


def _mentions(text: str, skill: str) -> bool:
    key = skill.strip().lower()
    if not key:
        return False
    for alias in (key, *SKILL_ALIASES.get(key, ())):
        if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text):
            return True
    return False


def score_deterministic(job: dict, profile: dict, filters: UserFilters) -> ScoreResult:
    text = f"{job.get('title', '')}\n{job.get('description', '')}".lower()
    category = job.get("role_category") or "Other"
    flags: list[str] = []

    title_role = role_from_title(job.get("title", ""))
    role_points = 30 if title_role == category else 20
    role_note = "title matches role category" if title_role == category else "role category inferred from description"

    skills = [str(s).strip() for s in (profile.get("skills") or []) if str(s).strip()]
    matched = [skill for skill in dict.fromkeys(skills) if _mentions(text, skill)]
    skill_points = min(35, round(35 * len(matched) / 5))
    if not skills:
        flags.append("Add skills to your profile to improve matching")

    background = [term for term in BACKGROUND_TERMS if re.search(r"\b" + re.escape(term) + r"\b", text)]
    background_points = min(15, 3 * len(background))

    logistics_points = 4  # India location is verified by the hard filter
    duration_hit = bool(_DURATION_RE.search(text))
    start_hit = bool(_START_RE.search(text))
    logistics_points += 3 if duration_hit else 0
    logistics_points += 3 if start_hit else 0
    logistics_points = min(10, logistics_points)

    status = job.get("stipend_status")
    amount = job.get("stipend_min_inr")
    if status == "verified" and amount is not None and amount >= filters.min_stipend_inr:
        stipend_points = 10
        stipend_note = "verified stipend meets your minimum"
    elif status == "not_verified":
        stipend_points = 4
        stipend_note = "stipend not disclosed"
        flags.append("Stipend not verified")
    else:
        stipend_points = 0
        stipend_note = "stipend below minimum or unpaid"

    total = max(0, min(100, role_points + skill_points + background_points + logistics_points + stipend_points))
    components = {
        "role_fit": {"points": role_points, "max": 30, "note": role_note},
        "skill_match": {"points": skill_points, "max": 35, "note": f"{len(matched)} profile skill(s) appear in the posting"},
        "background": {"points": background_points, "max": 15, "note": f"{len(background)} IITK BS Economics signal(s) in the posting"},
        "logistics": {"points": logistics_points, "max": 10, "note": "India verified" + ("; duration or summer mentioned" if duration_hit else "") + ("; 2027 mentioned" if start_hit else "")},
        "stipend": {"points": stipend_points, "max": 10, "note": stipend_note},
    }
    return ScoreResult(
        score=total,
        band=band_for(total),
        components=components,
        matched_skills=matched,
        background_terms=background,
        flags=list(dict.fromkeys(flags)),
        best_resume_tag=TAG_FOR_CATEGORY.get(category, "SDE"),
    )
