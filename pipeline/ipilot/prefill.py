"""Local prefill helper. Runs on YOUR computer, in a visible browser window.

It opens one application page on a job-board host from the allowlist, fills the fields it
can match from your saved answers, and attaches your resume PDF from your own disk.

It never clicks submit, never logs in, never solves or skips a CAPTCHA or bot check, never
fills an answer that is marked for you, and never visits a site outside the allowlist.
You read every field and press submit yourself.
"""

from __future__ import annotations

import os
import re

from .config import Settings
from .form_inspector import detect_challenge, host_allowed
from .http_client import PoliteClient

MAX_RESUME_BYTES = 5 * 1024 * 1024
PLACEHOLDER_MARK = "[ADD"
OPEN_STATUSES = {"pending_review", "approved_manual", "opened"}
SKIP_TYPES = {"file", "submit", "button", "image", "reset", "hidden", "password", "checkbox", "radio"}
HIGHLIGHT = "3px solid #d93025"

# Lists the form's controls, tags each with data-ipilot-id so Python can address it, and
# reads the same label rules the inspector uses. Read-only apart from that attribute.
DOM_SCAN_JS = r"""
() => Array.from(document.querySelectorAll('form input, form textarea, form select'))
  .map((el, i) => {
    el.setAttribute('data-ipilot-id', String(i));
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
      id: i,
      key: (el.name || el.id || '').slice(0, 120),
      label: label.trim().replace(/\s+/g, ' ').slice(0, 200),
      type: type,
      required: !!(el.required || el.getAttribute('aria-required') === 'true'),
      options: tag === 'select' ? Array.from(el.options).map(o => o.text.trim()).slice(0, 50) : []
    };
  })
"""


def normalise(text: object) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split())


def validate_resume(path: str) -> str | None:
    """Return an error message, or None when the file is a usable PDF (or no file was given)."""
    if not path:
        return None
    if not os.path.isfile(path):
        return "resume file not found"
    if not path.lower().endswith(".pdf"):
        return "resume must be a .pdf file"
    size = os.path.getsize(path)
    if size == 0 or size > MAX_RESUME_BYTES:
        return "resume must be between 1 byte and 5 MB"
    with open(path, "rb") as handle:
        if handle.read(5) != b"%PDF-":
            return "file is not a valid PDF"
    return None


def fillable_answers(form_answers: list | None) -> list[dict]:
    """Only answers the profile really supports: no flags for a person, no placeholders, no files."""
    out: list[dict] = []
    for answer in form_answers or []:
        if not isinstance(answer, dict) or answer.get("needs_human") or answer.get("type") == "file":
            continue
        value = answer.get("answer")
        if not isinstance(value, str) or not value.strip() or PLACEHOLDER_MARK in value:
            continue
        out.append(answer)
    return out


def match_fields(fields: list[dict], answers: list[dict]) -> list[tuple[dict, dict]]:
    """Pair each form control with at most one answer: by field name first, then by label."""
    by_key = {a["key"]: a for a in answers if a.get("key")}
    by_label: dict[str, dict] = {}
    for answer in answers:
        by_label.setdefault(normalise(answer.get("label")), answer)
    pairs: list[tuple[dict, dict]] = []
    used: set[int] = set()
    for field in fields:
        if field.get("type") in SKIP_TYPES:
            continue
        answer = by_key.get(field.get("key") or "") if field.get("key") else None
        if answer is None:
            answer = by_label.get(normalise(field.get("label")))
        if answer is None or id(answer) in used:
            continue
        used.add(id(answer))
        pairs.append((field, answer))
    return pairs


def fill_page(page, fields: list[dict], answers: list[dict], resume_path: str = "") -> dict:
    """Fill matched fields and attach the resume. Never clicks submit or any other button."""
    filled: list[str] = []
    skipped: list[str] = []
    filled_ids: set[int] = set()
    for field, answer in match_fields(fields, answers):
        label = field.get("label") or field.get("key") or "field"
        value = str(answer["answer"]).strip()
        locator = page.locator(f'[data-ipilot-id="{field["id"]}"]')
        try:
            if field["type"] == "select":
                option = next((o for o in field.get("options", []) if normalise(o) == normalise(value)), None)
                if option is None:
                    skipped.append(label)
                    continue
                locator.select_option(label=option)
            else:
                locator.fill(value)
            filled.append(label)
            filled_ids.add(field["id"])
        except Exception:  # one control failing must not stop the rest  # noqa: BLE001
            skipped.append(label)

    file_inputs = page.locator('input[type="file"]')
    needs_you: list[str] = []
    if file_inputs.count() > 0:
        if resume_path:
            file_inputs.first.set_input_files(resume_path)
            filled.append("Resume")
        else:
            needs_you.append("Resume (attach it yourself)")

    for field in fields:
        if field.get("required") and field.get("type") not in SKIP_TYPES and field["id"] not in filled_ids:
            needs_you.append(field.get("label") or field.get("key") or "field")
            try:
                page.locator(f'[data-ipilot-id="{field["id"]}"]').evaluate(
                    f"el => {{ el.style.outline = '{HIGHLIGHT}'; }}")
            except Exception:  # noqa: BLE001 - highlighting is cosmetic
                pass
    return {"filled": filled, "skipped": skipped, "needs_you": needs_you}


def run_prefill(application: dict, settings: Settings, resume_path: str = "", *,
                wait_seconds: int = 3600) -> dict:
    job = application.get("jobs") or {}
    url = str(job.get("apply_url") or "")
    if not host_allowed(url):
        return {"status": "host_not_allowed",
                "message": "This helper only works on Greenhouse, Lever and Ashby application pages."}
    with PoliteClient(settings.user_agent, min_interval_s=settings.min_interval_s,
                      timeout_s=settings.http_timeout_s) as client:
        if not client.allowed(url):
            return {"status": "robots_disallowed", "message": "robots.txt does not allow this page."}

    from playwright.sync_api import sync_playwright  # imported here so tests need no browser

    form_answers = application.get("form_answers") or []
    human_labels = [a.get("label") or a.get("key") or "question" for a in form_answers
                    if isinstance(a, dict) and a.get("needs_human") and a.get("type") != "file"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        try:
            page = browser.new_context(user_agent=settings.user_agent).new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
            if detect_challenge(page.content()):
                return {"status": "challenge_detected",
                        "message": "This page shows a CAPTCHA or bot check. Fill it in yourself."}
            fields = page.evaluate(DOM_SCAN_JS)
            result = fill_page(page, fields, fillable_answers(form_answers), resume_path)
            result["status"] = "filled"
            result["answer_yourself"] = human_labels
            try:
                # Keep the window open while you review. Closing it ends the session.
                page.wait_for_event("close", timeout=wait_seconds * 1000)
            except Exception:  # noqa: BLE001 - timeout just means the window stayed open too long
                pass
            return result
        finally:
            browser.close()
