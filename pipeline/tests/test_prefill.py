import pytest

from ipilot.cli import cmd_prefill, modes_for
from ipilot.prefill import (
    DOM_SCAN_JS,
    fill_page,
    fillable_answers,
    match_fields,
    normalise,
    run_prefill,
    validate_resume,
)
from tests.fakes import make_settings

ANSWERS = [
    {"key": "first_name", "label": "First Name", "type": "text", "answer": "Test Student", "needs_human": False},
    {"key": "email", "label": "Email", "type": "email", "answer": "student@example.test", "needs_human": False},
    {"key": "phone", "label": "Phone", "type": "tel", "answer": "+91 90000 00000", "needs_human": False},
    {"key": "why", "label": "Why are you interested in this role?", "type": "textarea",
     "answer": "[ADD YOUR OWN MOTIVATION: write this yourself]", "needs_human": True},
    {"key": "auth", "label": "Are you authorized to work in India?", "type": "text",
     "answer": None, "needs_human": True},
    {"key": "level", "label": "Current year", "type": "select", "answer": "third year", "needs_human": False},
    {"key": "resume", "label": "Resume/CV", "type": "file", "answer": None, "needs_human": True},
]

FIXTURE = """<!doctype html><html><body>
<form id="application_form" onsubmit="window.submitted = true; return false;">
  <label for="first_name">First Name *</label><input id="first_name" name="first_name" type="text" required>
  <label for="email">Email *</label><input id="email" name="email" type="email" required>
  <label for="phone">Phone</label><input id="phone" name="phone" type="tel">
  <label for="why">Why are you interested in this role?</label><textarea id="why" name="why" required></textarea>
  <label for="auth">Are you authorized to work in India?</label><input id="auth" name="auth" type="text" required>
  <label for="level">Current year</label>
  <select id="level" name="level"><option>First year</option><option>Third year</option></select>
  <label for="resume">Resume/CV</label><input id="resume" name="resume_file" type="file">
  <button type="submit" id="go">Submit application</button>
</form></body></html>"""


def test_normalise_ignores_case_punctuation_and_required_markers():
    assert normalise("First Name *") == "first name"
    assert normalise("Resume/CV:") == "resume cv"
    assert normalise(None) == ""


def test_fillable_answers_drops_flagged_placeholder_empty_and_file_answers():
    kept = [a["key"] for a in fillable_answers(ANSWERS)]
    assert kept == ["first_name", "email", "phone", "level"]


def test_fillable_answers_tolerates_malformed_entries():
    assert fillable_answers(None) == []
    assert fillable_answers(["not a dict", {"answer": 5, "key": "x"}]) == []


def test_match_fields_pairs_by_key_then_label_and_uses_each_answer_once():
    fields = [
        {"id": 0, "key": "first_name", "label": "First Name *", "type": "text"},
        {"id": 1, "key": "", "label": "Email", "type": "email"},
        {"id": 2, "key": "unrelated", "label": "Email", "type": "email"},
        {"id": 3, "key": "resume_file", "label": "Resume", "type": "file"},
    ]
    pairs = match_fields(fields, fillable_answers(ANSWERS))
    matched = [(f["id"], a["key"]) for f, a in pairs]
    assert (0, "first_name") in matched
    assert (1, "email") in matched
    assert all(f["type"] != "file" for f, _ in pairs)
    # the second "Email" control must not reuse the same answer
    assert len({a["key"] for _, a in pairs}) == len(pairs)


def test_resume_validation(tmp_path):
    assert validate_resume("") is None
    assert validate_resume(str(tmp_path / "missing.pdf")) == "resume file not found"
    text_file = tmp_path / "cv.pdf"
    text_file.write_bytes(b"hello")
    assert validate_resume(str(text_file)) == "file is not a valid PDF"
    wrong_ext = tmp_path / "cv.docx"
    wrong_ext.write_bytes(b"%PDF-1.4 ok")
    assert validate_resume(str(wrong_ext)) == "resume must be a .pdf file"
    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-" + b"0" * (5 * 1024 * 1024))
    assert validate_resume(str(big)) == "resume must be between 1 byte and 5 MB"
    good = tmp_path / "cv.pdf"
    good.write_bytes(b"%PDF-1.4\n%%EOF")
    assert validate_resume(str(good)) is None


def test_non_allowlisted_host_is_refused_before_any_browser_starts():
    application = {"jobs": {"apply_url": "https://www.linkedin.com/jobs/view/123"}, "form_answers": ANSWERS}
    result = run_prefill(application, make_settings())
    assert result["status"] == "host_not_allowed"


def test_prefill_command_rejects_bad_input_without_database_calls():
    class NoDatabase:
        def application_for_prefill(self, _):
            raise AssertionError("must not query the database for a bad id")

    assert cmd_prefill(make_settings(), NoDatabase(), "not-a-uuid", "")["status"] == "invalid_id"
    assert cmd_prefill(make_settings(), NoDatabase(), "6f1c2a3e-1111-4222-8333-444455556666",
                       "/no/such/file.pdf")["status"] == "bad_resume"


def test_pipeline_modes_map_to_the_right_steps():
    assert modes_for("scan") == (True, True, False)
    assert modes_for("full") == (True, True, True)
    assert modes_for("inspect") == (False, False, True)


# ---- browser tests: a local page stands in for a company form ------------------------

@pytest.fixture
def form_page(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception as exc:  # no browser installed in this environment
            pytest.skip(f"chromium unavailable: {exc}")
        page = browser.new_page()
        path = tmp_path / "form.html"
        path.write_text(FIXTURE, encoding="utf-8")
        page.goto(path.as_uri())
        yield page
        browser.close()


def test_fill_page_fills_verified_answers_and_leaves_flagged_ones_empty(form_page, tmp_path):
    resume = tmp_path / "cv.pdf"
    resume.write_bytes(b"%PDF-1.4\n%%EOF")
    fields = form_page.evaluate(DOM_SCAN_JS)
    result = fill_page(form_page, fields, fillable_answers(ANSWERS), str(resume))

    assert form_page.input_value("#first_name") == "Test Student"
    assert form_page.input_value("#email") == "student@example.test"
    assert form_page.input_value("#phone") == "+91 90000 00000"
    assert form_page.input_value("#level") == "Third year"  # matched case-insensitively to an option
    assert form_page.input_value("#why") == ""  # flagged for you: never typed
    assert form_page.input_value("#auth") == ""  # no answer: never guessed
    assert form_page.evaluate("document.querySelector('#resume').files.length") == 1
    assert "Resume" in result["filled"]
    assert "Are you authorized to work in India?" in result["needs_you"]
    assert "Why are you interested in this role?" in result["needs_you"]


def test_fill_page_never_submits_the_form(form_page):
    fields = form_page.evaluate(DOM_SCAN_JS)
    fill_page(form_page, fields, fillable_answers(ANSWERS), "")
    assert form_page.evaluate("window.submitted === true") is False
