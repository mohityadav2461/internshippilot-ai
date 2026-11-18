"""Optional Gemini scoring with hard guards.

* Only a sanitised profile summary plus the posting text are sent. Name, email,
  phone, links and the resume PDF or extracted resume text are never sent.
* Every call is counted in a daily quota ledger, and a per-run cap applies too.
* Any 429, quota error, or 401 / 403 disables AI for the rest of the run. Scoring
  then falls back to deterministic results with the reason recorded in flags.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT_HEADER = (
    "You evaluate how well an internship candidate fits one job posting.\n"
    "Use ONLY the candidate profile and the job text below. Do not invent experience, skills or credentials.\n"
    "Return ONLY a JSON object with these keys:\n"
    "  fit_score: integer 0-100\n"
    "  summary: string, at most 300 characters\n"
    "  strengths: array of up to 4 short strings\n"
    "  gaps: array of up to 4 short strings\n"
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)\+?\d[\d\s().-]{8,}\d(?!\d)")


class AIUnavailable(Exception):
    def __init__(self, reason: str, *, disable: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.disable = disable


@dataclass
class AIScore:
    fit_score: int
    summary: str
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"fit_score": self.fit_score, "summary": self.summary, "strengths": self.strengths, "gaps": self.gaps}


def redact_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[email]", text or "")
    text = _URL_RE.sub("[url]", text)
    return _PHONE_RE.sub("[phone]", text)


def build_profile_summary(profile: dict) -> str:
    """Only fields the candidate typed for matching. No identifiers, links or resume text."""
    projects = profile.get("projects") or []
    project_lines = []
    for project in projects[:6]:
        if not isinstance(project, dict):
            continue
        tech = ", ".join(str(t) for t in (project.get("tech") or [])[:8])
        project_lines.append(f"- {project.get('name', '')} ({tech}): {str(project.get('summary', ''))[:240]}")
    lines = [
        f"Degree: {profile.get('degree', '')} at {profile.get('college', '')}, graduating {profile.get('graduation_year', '')}.",
        f"Skills: {', '.join(str(s) for s in (profile.get('skills') or [])[:40]) or 'not provided'}.",
        "Projects:" if project_lines else "Projects: none listed.",
        *project_lines,
        f"Achievements: {'; '.join(str(a) for a in (profile.get('achievements') or [])[:6]) or 'none listed'}.",
    ]
    return redact_pii("\n".join(lines))[:3000]


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:160] for item in value if str(item).strip()][:4]


def parse_ai_text(text: str) -> AIScore:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AIUnavailable("bad_json") from exc
    if not isinstance(data, dict):
        raise AIUnavailable("bad_json")
    try:
        fit = int(round(float(data["fit_score"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise AIUnavailable("bad_fit_score") from exc
    return AIScore(
        fit_score=max(0, min(100, fit)),
        summary=str(data.get("summary", ""))[:300],
        strengths=_str_list(data.get("strengths")),
        gaps=_str_list(data.get("gaps")),
    )


def parse_ai_response(payload: object) -> AIScore:
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIUnavailable("empty_response") from exc
    return parse_ai_text(text)


def blend(deterministic: int, ai_fit: int, ai_weight: float = 0.4) -> int:
    return max(0, min(100, round((1 - ai_weight) * deterministic + ai_weight * ai_fit)))


class QuotaGuard:
    """Daily ledger (stored via the store) plus a per-run cap. Counts attempts, not successes."""

    def __init__(self, store: object, daily_cap: int, run_cap: int) -> None:
        self._store = store
        self._daily_cap = daily_cap
        self._run_cap = run_cap
        self._run_calls = 0
        self._day_used: int | None = None

    def _load(self) -> int:
        if self._day_used is None:
            self._day_used = int(self._store.ai_calls_today())  # type: ignore[attr-defined]
        return self._day_used

    def exhausted(self) -> bool:
        return self._load() >= self._daily_cap or self._run_calls >= self._run_cap

    def consume(self) -> None:
        self._load()
        self._run_calls += 1
        self._day_used = (self._day_used or 0) + 1
        self._store.increment_ai_calls(1)  # type: ignore[attr-defined]


class GeminiScorer:
    def __init__(self, api_key: str, model: str, guard: QuotaGuard, http: httpx.Client) -> None:
        self._key = api_key
        self._model = model
        self._guard = guard
        self._http = http

    def score(self, profile_summary: str, job_text: str) -> AIScore:
        if self._guard.exhausted():
            raise AIUnavailable("quota_guard_reached", disable=True)
        self._guard.consume()
        prompt = f"{PROMPT_HEADER}\nCANDIDATE PROFILE:\n{profile_summary}\n\nJOB POSTING:\n{redact_pii(job_text)[:4000]}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512, "responseMimeType": "application/json"},
        }
        try:
            resp = self._http.post(
                GEMINI_URL.format(model=self._model),
                headers={"x-goog-api-key": self._key, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
        except httpx.HTTPError as exc:
            raise AIUnavailable("network_error") from exc
        text = resp.text.lower()
        if resp.status_code == 429:
            raise AIUnavailable("rate_limited", disable=True)
        if (resp.status_code in (400, 403) and "quota" in text) or "resource_exhausted" in text:
            raise AIUnavailable("quota_exhausted", disable=True)
        if resp.status_code in (401, 403):
            raise AIUnavailable("auth_rejected", disable=True)
        if resp.status_code >= 500:
            raise AIUnavailable("upstream_error")
        if resp.status_code >= 400:
            raise AIUnavailable(f"http_{resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise AIUnavailable("bad_json") from exc
        return parse_ai_response(payload)


def utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()
