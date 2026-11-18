from ipilot.form_inspector import detect_challenge, host_allowed


def test_only_allowlisted_https_application_hosts_are_inspected():
    assert host_allowed("https://boards.greenhouse.io/acme/jobs/1")
    assert host_allowed("https://jobs.lever.co/acme/abc/apply")
    assert not host_allowed("http://boards.greenhouse.io/acme/jobs/1")
    assert not host_allowed("https://internshala.com/apply")
    assert not host_allowed("https://evil.example.com/boards.greenhouse.io")


def test_challenge_markers_are_detected():
    assert detect_challenge('<div class="g-recaptcha" data-sitekey="x"></div>')
    assert detect_challenge("<p>Verify you are human to continue</p>")
    assert not detect_challenge("<form><input name='email'></form>")
