"""Strict filters. The global gate (internship + India) runs at discovery time.
Per-user filters (stipend, roles, city) run at scoring time and are editable in Settings."""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import ROLE_CATEGORIES, is_india_location

DEFAULT_ROLES = ("SDE", "Quant", "Analyst", "ML", "DataScience", "Research")


def _clamp_int(value: object, default: int, low: int, high: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


@dataclass(frozen=True)
class UserFilters:
    min_stipend_inr: int = 10000
    locations: tuple[str, ...] = ("India",)
    allow_stipend_unverified: bool = True
    roles: tuple[str, ...] = DEFAULT_ROLES
    min_score_to_show: int = 50
    auto_queue_score: int = 70

    @classmethod
    def from_dict(cls, data: dict | None) -> "UserFilters":
        raw = data or {}
        roles = tuple(
            role for role in (raw.get("roles") or DEFAULT_ROLES)
            if role in ROLE_CATEGORIES and role != "Other"
        )
        locations = tuple(
            str(item).strip() for item in (raw.get("locations") or ["India"]) if str(item).strip()
        ) or ("India",)
        return cls(
            min_stipend_inr=_clamp_int(raw.get("min_stipend_inr"), 10000, 0, 1_000_000),
            locations=locations,
            allow_stipend_unverified=bool(raw.get("allow_stipend_unverified", True)),
            roles=roles or DEFAULT_ROLES,
            min_score_to_show=_clamp_int(raw.get("min_score_to_show"), 50, 0, 100),
            auto_queue_score=_clamp_int(raw.get("auto_queue_score"), 70, 0, 100),
        )


@dataclass
class Decision:
    passes: bool
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def _location_ok(location: str, locations: tuple[str, ...]) -> bool:
    if not is_india_location(location):
        return False
    lowered = location.lower()
    for wanted in locations:
        item = wanted.strip().lower()
        if item == "india" or item in lowered:
            return True
    return False


def evaluate_job(job: dict, filters: UserFilters) -> Decision:
    """Apply the per-user strict filters. Internships only, always."""
    reasons: list[str] = []
    flags: list[str] = []
    if not job.get("is_internship"):
        reasons.append("not an internship")
    if job.get("role_category") not in filters.roles:
        reasons.append(f"role {job.get('role_category')} is not a target role")
    if not _location_ok(str(job.get("location") or ""), filters.locations):
        reasons.append("location is outside India or the selected cities")

    status = job.get("stipend_status") or "not_verified"
    amount = job.get("stipend_min_inr")
    if status == "unpaid":
        reasons.append("unpaid internship")
    elif status == "verified" and amount is not None:
        if amount < filters.min_stipend_inr:
            reasons.append(f"stipend Rs {amount:,} is below the Rs {filters.min_stipend_inr:,} minimum")
    else:
        if filters.allow_stipend_unverified:
            flags.append("Stipend not verified")
        else:
            reasons.append("stipend not disclosed")
    return Decision(passes=not reasons, reasons=reasons, flags=flags)
