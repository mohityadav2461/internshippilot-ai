"""Pure normalisation: canonical URLs, dedupe keys, internship / India / role / stipend detection.

Everything here is deterministic and side-effect free so it can be unit-tested
exhaustively. Heuristics are conservative: when in doubt a posting is marked
unverified rather than guessed.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import NormalizedJob, RawJob

ROLE_CATEGORIES = ("SDE", "Quant", "Analyst", "ML", "DataScience", "Research", "Other")

# Resume tag to use for each role category (mirrored in web/lib/constants.ts).
TAG_FOR_CATEGORY = {
    "SDE": "SDE",
    "Quant": "Quant",
    "Analyst": "Analyst",
    "ML": "ML",
    "DataScience": "ML",
    "Research": "Quant",
    "Other": "SDE",
}

_TRACKING_KEYS = {"gh_src", "ref", "source", "src", "trk", "fbclid", "gclid", "lever-source", "lever-origin"}
_COMPANY_SUFFIXES = {"inc", "llc", "ltd", "limited", "pvt", "private", "corp", "corporation", "co", "india"}

_INDIA_TERMS = (
    "india", "bengaluru", "bangalore", "mumbai", "bombay", "delhi", "new delhi", "gurgaon",
    "gurugram", "noida", "hyderabad", "pune", "chennai", "madras", "kolkata", "calcutta",
    "ahmedabad", "kanpur", "chandigarh", "jaipur", "kochi", "indore", "bhubaneswar",
    "coimbatore", "thiruvananthapuram", "lucknow", "ncr",
)
INDIA_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _INDIA_TERMS) + r")\b", re.IGNORECASE)
_REMOTE_HYBRID_RE = re.compile(r"\b(remote|hybrid|on ?site)\b", re.IGNORECASE)
_INTERN_RE = re.compile(r"\bintern(?:s|ship|ships)?\b", re.IGNORECASE)
_INTERN_DESC_RE = re.compile(
    r"\b(?:summer|winter|fall|spring)?\s*(?:internship|intern)\s+(?:program|position|role|opportunity|opening)\b",
    re.IGNORECASE,
)
_SEASON_OR_YEAR_RE = re.compile(r"20\d\d|\b(summer|winter|fall|spring)\b", re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"\s+[-|\u2013\u2014]\s+")
_PAREN_RE = re.compile(r"[\(\[]([^)\]]*)[\)\]]")
_YEAR_RE = re.compile(r"\b20\d{2}\b")
_SEASON_RE = re.compile(r"\b(summer|winter|fall|spring)\b", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BLOCK_BREAK_RE = re.compile(r"<br\s*/?>|</p>|</li>|</h\d>|</div>", re.IGNORECASE)

_ROLE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Quant", re.compile(r"\bquant\w*|\balgorithmic\b|\btrading\b|\bmarket making\b|\bderivatives?\b|\bstrats?\b", re.I)),
    ("ML", re.compile(
        r"\bmachine learning\b|\bml\b|\bai\b|\bartificial intelligence\b|\bdeep learning\b|\bnlp\b"
        r"|\bcomputer vision\b|\bllms?\b|\bgenerative ai\b|\bapplied scientist\b", re.I)),
    ("DataScience", re.compile(r"\bdata scien\w*|\banalytics scien\w*", re.I)),
    ("Research", re.compile(r"\bresearch\b", re.I)),
    ("Analyst", re.compile(r"\banaly(?:st|sts|tics|tic)\b|\beconomist\b|\bstrategy\b|\boperations\b", re.I)),
    ("SDE", re.compile(
        r"\bsoftware\b|\bsde\b|\bswe\b|\bengineer\w*|\bdeveloper\w*|\bdevelopment\b|\bbackend\b"
        r"|\bback[- ]end\b|\bfront[- ]?end\b|\bfull[- ]?stack\b|\bplatform\b|\bsre\b|\bdevops\b", re.I)),
)

_STIPEND_AMOUNT_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|lakhs?|lpa|l)?\b", re.IGNORECASE)
_STIPEND_HINT_RE = re.compile(
    r"[^.\n]{0,80}(?:stipend|₹|\bINR\b|\bRs\.?\b|\bper month\b|/\s*month)[^.\n]{0,80}", re.IGNORECASE
)
_ANNUAL_RE = re.compile(r"per annum|\bp\.?a\.?\b|/\s*(?:year|yr|annum)|a year|yearly|annual|\blpa\b", re.IGNORECASE)
_MONTHLY_RE = re.compile(r"per month|/\s*month|monthly|\bpm\b|a month|/\s*mo\b", re.IGNORECASE)
_STIPEND_SIGNAL_RE = re.compile(
    r"₹|\brs\.?\b|\binr\b|\brupees?\b|\bstipend\b|\bper month\b|/\s*month|\blpa\b|\blakh", re.IGNORECASE
)


def canonical_url(url: str) -> str:
    """Return a stable https URL: lowercase host, no www, no fragment, no tracking parameters."""
    parts = urlsplit((url or "").strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"not an absolute http(s) URL: {(url or '')[:120]!r}")
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def normalize_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii").lower()
    cleaned = re.sub(r"[^a-z0-9+#]+", " ", folded)
    return _WS_RE.sub(" ", cleaned).strip()


def normalize_company(name: str) -> str:
    tokens = normalize_text(name).split()
    while tokens and tokens[-1] in _COMPANY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def is_india_location(location: str) -> bool:
    return bool(location and INDIA_RE.search(location))


def _is_location_segment(segment: str) -> bool:
    return bool(INDIA_RE.search(segment) or _REMOTE_HYBRID_RE.search(segment))


def normalize_title(title: str) -> str:
    """Collapse location, season and year decorations so the same role matches across sources.

    Role-specific suffixes such as "- Backend" are kept on purpose, so distinct roles stay distinct.
    """
    text = _PAREN_RE.sub(
        lambda m: " " if _is_location_segment(m.group(1)) or _SEASON_OR_YEAR_RE.search(m.group(1)) else m.group(0),
        title or "",
    )
    segments = _SEPARATOR_RE.split(text)
    while len(segments) > 1 and _is_location_segment(segments[-1]):
        segments.pop()
    text = " ".join(segments)
    text = _YEAR_RE.sub(" ", text)
    text = _SEASON_RE.sub(" ", text)
    return normalize_text(text)


def dedupe_key(company: str, title: str) -> str:
    raw = f"{normalize_company(company)}|{normalize_title(title)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def html_to_text(value: str | None, limit: int = 20000) -> str:
    """Turn HTML or entity-escaped HTML into readable plain text."""
    if not value:
        return ""
    text = html.unescape(html.unescape(value))
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = _BLOCK_BREAK_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)[:limit]


def detect_internship(title: str, employment_hint: str, description: str) -> bool:
    if _INTERN_RE.search(title or ""):
        return True
    if employment_hint:
        return bool(_INTERN_RE.search(employment_hint))
    return bool(_INTERN_DESC_RE.search((description or "")[:600]))


def role_from_title(title: str) -> str | None:
    for label, pattern in _ROLE_RULES:
        if pattern.search(title or ""):
            return label
    return None


def classify_role(title: str, description: str = "") -> str:
    """Title first. Fall back to the opening of the description only when the title is silent."""
    found = role_from_title(title)
    if found:
        return found
    head = (description or "")[:400]
    for label, pattern in _ROLE_RULES:
        if pattern.search(head):
            return label
    return "Other"


def stipend_hint(description: str) -> str | None:
    match = _STIPEND_HINT_RE.search(description or "")
    return match.group(0).strip() if match else None


def parse_stipend(text: str | None) -> tuple[str, int | None]:
    """Return (stipend_status, minimum_monthly_inr).

    Only explicit amounts count as verified. Unpaid roles are flagged. Everything else is
    'not_verified' so the UI can say "Stipend not verified" instead of guessing.
    """
    if not text or not text.strip():
        return "not_verified", None
    if re.search(r"\bunpaid\b", text, re.IGNORECASE):
        return "unpaid", 0
    if not _STIPEND_SIGNAL_RE.search(text):
        return "not_verified", None
    annual = bool(_ANNUAL_RE.search(text)) and not _MONTHLY_RE.search(text)
    amounts: list[int] = []
    for match in _STIPEND_AMOUNT_RE.finditer(text):
        number = float(match.group(1).replace(",", ""))
        suffix = (match.group(2) or "").lower()
        if suffix == "k":
            number *= 1000
        elif suffix in {"lakh", "lakhs", "lpa", "l"}:
            number *= 100000
        elif 1990 <= number <= 2100:  # a year, not money
            continue
        if number < 500 or number > 5_000_000:
            continue
        amounts.append(int(number / 12) if annual else int(number))
    if not amounts:
        return "not_verified", None
    return "verified", min(amounts)


def _iso(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).isoformat()
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _clean(value: object) -> str:
    return _WS_RE.sub(" ", str(value or "")).strip()


def to_normalized(raw: RawJob) -> NormalizedJob:
    """Clean one raw posting. Raises ValueError when it cannot be stored safely."""
    title = _clean(raw.title)
    company = _clean(raw.company)
    if not title or not company:
        raise ValueError("posting is missing a title or company")
    apply_source = raw.apply_url or raw.url
    canonical = canonical_url(raw.url or apply_source)
    apply_url = canonical_url(apply_source)
    description = html_to_text(raw.description_html)
    location = _clean(raw.location)
    stipend_text = (raw.stipend_text or stipend_hint(description) or None)
    if stipend_text:
        stipend_text = _clean(stipend_text)[:300]
    stipend_status, stipend_min = parse_stipend(stipend_text)
    return NormalizedJob(
        source_name=raw.source_name,
        source_job_id=(raw.source_job_id or None),
        canonical_url=canonical,
        apply_url=apply_url,
        dedupe_key=dedupe_key(company, title),
        company=company[:200],
        title=title[:300],
        normalized_company=normalize_company(company),
        normalized_title=normalize_title(title),
        location=location[:300],
        is_remote=bool(raw.is_remote_flag) or bool(re.search(r"\bremote\b", location, re.IGNORECASE)),
        is_internship=detect_internship(title, raw.employment_hint, description),
        role_category=classify_role(title, description),
        description=description,
        posted_at=_iso(raw.posted_at),
        stipend_text=stipend_text,
        stipend_status=stipend_status,
        stipend_min_inr=stipend_min,
    )
