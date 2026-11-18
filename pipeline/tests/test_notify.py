import httpx

from ipilot import scoring_runner
from ipilot.notify import format_queue_message, notify_queued, send_ntfy, topic_is_valid
from tests.fakes import MemoryStore, make_settings
from tests.test_scoring_runner import JOBS, PROFILE

TOPIC = "k3v9q2m7x1p8w5r4t6y0"  # 20 characters, the shape a real topic should have


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_topic_must_be_long_and_url_safe():
    assert topic_is_valid(TOPIC)
    assert not topic_is_valid("short")
    assert not topic_is_valid("has/slash/in/it/0123456789")
    assert not topic_is_valid("")
    assert not topic_is_valid(None)


def test_message_lists_matches_and_states_nothing_is_submitted():
    items = [{"company": "Acme", "title": "ML Intern", "score": 88}]
    title, body = format_queue_message(items)
    assert title == "1 new internship match to review"
    assert "88/100  Acme - ML Intern" in body
    assert "Nothing is submitted until you submit it yourself" in body


def test_long_list_is_capped_with_a_count_of_the_rest():
    items = [{"company": f"Co{i}", "title": "Intern", "score": 75} for i in range(10)]
    title, body = format_queue_message(items)
    assert title == "10 new internship matches to review"
    assert body.count("/100") == 8
    assert "...and 2 more" in body


def test_company_text_cannot_inject_newlines_or_overlong_lines():
    title, body = format_queue_message([{"company": "Evil\nCo" + "x" * 300, "title": "Intern", "score": 70}])
    assert "\n" in body  # the line break we add ourselves
    first_line = body.split("\n")[0]
    assert len(first_line) < 160 and "Evil Co" in first_line


def test_send_posts_to_the_topic_url_with_ascii_title():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["title"] = request.headers["Title"]
        seen["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"id": "x"})

    ok = send_ntfy(TOPIC, "2 new internship matches to review", "Acme - ML Intern", client=_client(handler))
    assert ok is True
    assert seen["url"] == f"https://ntfy.sh/{TOPIC}"
    assert seen["title"] == "2 new internship matches to review"
    assert seen["body"] == "Acme - ML Intern"


def test_non_ascii_title_is_sanitised_for_the_header_and_body_keeps_it():
    seen = {}

    def handler(request):
        seen["title"] = request.headers["Title"]
        seen["body"] = request.content.decode("utf-8")
        return httpx.Response(200)

    send_ntfy(TOPIC, "Intern – ₹ match", "Café Labs - Intern", client=_client(handler))
    assert seen["title"].isascii()
    assert seen["body"] == "Café Labs - Intern"


def test_failed_delivery_returns_false_and_never_raises():
    ok = send_ntfy(TOPIC, "t", "b", client=_client(lambda r: httpx.Response(500)))
    assert ok is False


def test_no_network_call_when_topic_is_missing():
    def handler(request):
        raise AssertionError("must not call the network without a valid topic")

    assert notify_queued("", [{"company": "A", "title": "B", "score": 90}], client=_client(handler)) is False
    assert notify_queued("bad", [{"company": "A", "title": "B", "score": 90}], client=_client(handler)) is False


def test_no_notification_when_nothing_was_queued():
    def handler(request):
        raise AssertionError("no items means no notification")

    assert notify_queued(TOPIC, [], client=_client(handler)) is False


def test_runner_sends_one_notification_per_run_with_all_queued_matches(monkeypatch):
    calls = []
    monkeypatch.setattr(scoring_runner, "notify_queued", lambda topic, items, **kw: calls.append((topic, items)) or True)
    store = MemoryStore(profiles=[dict(PROFILE, ai_consent=False)], jobs=JOBS)
    stats = scoring_runner.run_scoring(store, make_settings(ntfy_topic=TOPIC), gemini=None)
    assert len(calls) == 1
    topic, items = calls[0]
    assert topic == TOPIC
    assert [item["title"] for item in items] == ["Machine Learning Intern"]
    assert stats["notified"] is True


def test_runner_is_silent_without_a_topic(monkeypatch):
    monkeypatch.setattr(scoring_runner, "notify_queued", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    store = MemoryStore(profiles=[dict(PROFILE, ai_consent=False)], jobs=JOBS)
    stats = scoring_runner.run_scoring(store, make_settings(), gemini=None)
    assert stats["queued"] == 1 and stats["notified"] is False
