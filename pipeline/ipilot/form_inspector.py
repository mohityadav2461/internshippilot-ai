"""READ-ONLY form inspection with Playwright.

Loads an application page in headless Chromium and records the form's field labels
and types. It never fills, clicks, or submits anything. It stops on CAPTCHA or bot
challenges, and it only visits hosts on the allowlist below.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit

from .http_client import PoliteClient

ALLOWED_HOSTS = {
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "job-boards.eu.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
}
CHALLENGE_HINTS = ("g-recaptcha", "h-captcha", "cf-turnstile", "captcha", "are you a robot",
                   "verify you are human")
SKIP_TYPES = {"hidden", "submit", "button", "image", "reset", "password"}

FIELD_JS = """
() => Array.from(document.querySelectorAll('form input, form textarea, form select'))
  .filter(el => !['hidden','submit','button','image','reset','password'].includes((el.type || '').toLowerCase()))
  .map(el => {
    const tag = el.tagName.toLowerCase();
    let label = '';
    if (el.id) {
      const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (l) label = l.innerText;
    }
    if (!label && el.closest('label')) label = el.closest('label').innerText;
    if (!label) label = el.getAttribute('aria-label') || el.placeholder || el.name || '';
    const type = tag === 'textarea' ? 'textarea' : (tag === 'select' ? 'select' : (el.type || 'text').toLowerCase());
    return {
      key: (el.name || el.id || '').slice(0, 120),
      label: label.trim().replace(/\\s+/g, ' ').slice(0, 200),
      type: type,
      required: !!(el.required || el.getAttribute('aria-required') === 'true'),
      options: tag === 'select' ? Array.from(el.options).map(o => o.text.trim()).slice(0, 50) : []
    };
  })
"""


def host_allowed(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS


def detect_challenge(html: str) -> bool:
    lowered = html.lower()
    return any(hint in lowered for hint in CHALLENGE_HINTS)


def inspect_url(url: str, client: PoliteClient, user_agent: str) -> dict:
    """Return a form schema dict. Imports Playwright lazily so unit tests do not need it."""
    if not host_allowed(url):
        return {"status": "host_not_allowed", "fields": [], "inspected_at": _now()}
    if not client.allowed(url):
        return {"status": "robots_disallowed", "fields": [], "inspected_at": _now()}
    from playwright.sync_api import sync_playwright  # imported here on purpose

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            page.route("**/*", lambda route: route.abort()
                       if route.request.resource_type in ("image", "font", "media")
                       else route.continue_())
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
            if detect_challenge(page.content()):
                return {"status": "challenge_detected", "fields": [], "inspected_at": _now()}
            fields = page.evaluate(FIELD_JS)
            fields = [f for f in fields if f.get("type") not in SKIP_TYPES][:80]
            return {"status": "inspected", "fields": fields, "inspected_at": _now(),
                    "host": urlsplit(url).hostname}
        finally:
            browser.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
