import httpx
import pytest

from ipilot.http_client import PoliteClient, SourceBlocked, SourceError

UA = "InternshipPilotBot/1.0 (+https://example.com; bot@example.com)"


def client_for(handler):
    return PoliteClient(UA, min_interval_s=0, backoff_s=0, transport=httpx.MockTransport(handler))


def test_robots_disallow_blocks_fetch():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, text="ok")

    with client_for(handler) as client:
        with pytest.raises(SourceBlocked):
            client.get("https://site.example/private/job")
        assert client.get("https://site.example/public/job").text == "ok"


def test_missing_robots_means_allowed():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="hello")

    with client_for(handler) as client:
        assert client.get("https://site.example/anything").text == "hello"


def test_captcha_challenge_is_refused_not_bypassed():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(403, text="<div class='g-recaptcha'>Please complete the captcha</div>")

    with client_for(handler) as client:
        with pytest.raises(SourceBlocked, match="not bypassed"):
            client.get("https://site.example/jobs")


def test_rate_limit_is_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, text="done")

    with client_for(handler) as client:
        assert client.get("https://site.example/jobs").text == "done"
    assert calls["n"] == 2


def test_non_http_urls_are_refused():
    with client_for(lambda r: httpx.Response(200)) as client:
        with pytest.raises(SourceError):
            client.get("file:///etc/passwd")


def test_server_error_is_a_source_error():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(500)

    with client_for(handler) as client:
        with pytest.raises(SourceError, match="HTTP 500"):
            client.get("https://site.example/jobs")
