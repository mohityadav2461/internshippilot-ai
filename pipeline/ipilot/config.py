"""Runtime configuration. Every secret comes from the environment; nothing is hard-coded."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


def sanitize_supabase_url(raw: str) -> str:
    url = raw.strip().strip("'\"<>[]() \t\r\n")
    # If someone pasted dashboard URL: https://supabase.com/dashboard/project/<ref>
    m = re.search(r"supabase\.com/dashboard/project/([a-z0-9_-]+)", url)
    if m:
        return f"https://{m.group(1)}.supabase.co"

    # Remove repeated protocol
    while url.startswith("https://https://") or url.startswith("http://https://"):
        url = url[8:] if url.startswith("https://https://") else url[7:]

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    # Remove any stray angle brackets or brackets in middle: e.g. https://<ref>.supabase.co
    url = url.replace("<", "").replace(">", "").replace("[", "").replace("]", "")

    # Common typo: .supabase.com instead of .supabase.co
    if ".supabase.com" in url:
        url = url.replace(".supabase.com", ".supabase.co")

    url = url.rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-8]

    return url


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    return float(raw) if raw else default


def sanitize_key(raw: str) -> str:
    key = raw.strip().strip("'\"<>[]() \t\r\n")
    for prefix in ("secret--", "secret-", "secret:", "default--", "default-", "default:", "key:"):
        if key.startswith(prefix):
            key = key[len(prefix):].strip()
    return key


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_key: str
    gemini_api_key: str
    gemini_model: str
    gemini_daily_cap: int
    gemini_run_cap: int
    ai_enabled: bool
    contact_url: str
    contact_email: str
    min_interval_s: float
    http_timeout_s: float
    stale_after_days: int
    consecutive_failure_limit: int
    ntfy_topic: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        url = sanitize_supabase_url(os.getenv("SUPABASE_URL", ""))
        key = sanitize_key(os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

        return cls(
            supabase_url=url,
            supabase_service_key=key,
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "").strip() or "gemini-2.5-flash",
            gemini_daily_cap=_env_int("GEMINI_DAILY_CALL_CAP", 40),
            gemini_run_cap=_env_int("GEMINI_RUN_CALL_CAP", 25),
            ai_enabled=_env_bool("AI_ENABLED", True),
            contact_url=os.getenv("SCRAPER_CONTACT_URL", "").strip() or "https://github.com/",
            contact_email=os.getenv("SCRAPER_CONTACT_EMAIL", "").strip(),
            min_interval_s=_env_float("REQUEST_MIN_INTERVAL_SECONDS", 2.0),
            http_timeout_s=_env_float("HTTP_TIMEOUT_SECONDS", 20.0),
            stale_after_days=_env_int("STALE_JOB_DAYS", 21),
            consecutive_failure_limit=_env_int("SOURCE_FAILURE_LIMIT", 5),
            ntfy_topic=os.getenv("NTFY_TOPIC", "").strip(),
        )

    def require_database(self) -> None:
        if "YOUR-PROJECT-REF" in self.supabase_url:
            raise ConfigError("SUPABASE_URL contains placeholder 'YOUR-PROJECT-REF'. Update it in GitHub Secrets with your real Supabase URL.")
        if not self.supabase_url.startswith("https://"):
            raise ConfigError("SUPABASE_URL must be an https:// URL")
        if len(self.supabase_service_key) < 20:
            raise ConfigError("SUPABASE_SERVICE_ROLE_KEY is missing or too short")

    @property
    def gemini_enabled(self) -> bool:
        return self.ai_enabled and bool(self.gemini_api_key)

    @property
    def user_agent(self) -> str:
        contact = self.contact_email or self.contact_url
        return f"InternshipPilotBot/1.0 (+{self.contact_url}; {contact})"
