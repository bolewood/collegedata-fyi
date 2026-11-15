"""Browser-fallback policy of PoliteFetcher. Fake transports only: no network, no browser."""

import subprocess
import sys
from pathlib import Path

import pytest

from tools.common.polite_fetch import (
    BLOCKED_BY_ROBOTS, HTTP_ERROR, LOGIN_OR_CAPTCHA, OK, ROBOTS_UNREACHABLE, PoliteFetcher, Response,
)

NOW = 1_800_000_000.0
ROBOTS = "https://a.edu/robots.txt"
PAGE = "https://a.edu/page"
PAGE2 = "https://a.edu/page2"


class Net:
    """Scripted transport: url -> list of responses (last repeats). Records (time, url, headers)."""

    def __init__(self, routes, clock):
        self.routes = {k: list(v) for k, v in routes.items()}
        self.calls = []
        self.clock = clock

    def __call__(self, method, url, headers, timeout):
        self.calls.append((self.clock.t, url, dict(headers)))
        q = self.routes[url]
        r = q.pop(0) if len(q) > 1 else q[0]
        if isinstance(r, Exception):
            raise r
        return r

    @property
    def urls(self):
        return [c[1] for c in self.calls]


class Clock:
    def __init__(self):
        self.t = NOW
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def R(status=200, body=b"", **h):
    return Response(status, {k.replace("_", "-"): v for k, v in h.items()}, body)


def make(plain, browser=None, fallback=True, **kw):
    clock = Clock()
    p = Net(plain, clock)
    b = Net(browser or {}, clock)
    f = PoliteFetcher(
        "scholarships", transport=p, browser_fallback=b if fallback else None,
        clock=clock, sleep=clock.sleep, min_spacing=kw.pop("min_spacing", 2.0), **kw,
    )
    return f, p, b, clock


def test_fallback_on_404_and_403():
    for status in (404, 403, 406):
        f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(status)]}, {PAGE: [R(200, b"<html>dom</html>")]})
        r = f.fetch(PAGE)
        assert r.status == OK and r.transport == "browser" and r.body == b"<html>dom</html>", status
        assert p.urls == [ROBOTS, PAGE] and b.urls == [PAGE]


def test_no_fallback_on_200_500_or_login_redirect():
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(200, b"ok")]})
    r = f.fetch(PAGE)
    assert r.transport == "http" and b.calls == []
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(500)]}, max_retries=1)
    assert f.fetch(PAGE).status == HTTP_ERROR and b.calls == []
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(302, location="https://login.a.edu/sso?x=1")]})
    r = f.fetch(PAGE)
    assert r.status == LOGIN_OR_CAPTCHA and b.calls == []


@pytest.mark.parametrize("hdrs,body", [
    ({"www_authenticate": "Basic"}, b""),
    ({}, b"<div class='g-recaptcha'></div>"),
    ({}, b"please verify you are human captcha"),
])
def test_login_and_captcha_never_retried_in_browser(hdrs, body):
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(403, body, **hdrs)]}, {PAGE: [R(200, b"x")]})
    r = f.fetch(PAGE)
    assert r.status == LOGIN_OR_CAPTCHA and b.calls == []


def test_one_fallback_attempt_per_url_and_failure_reported_as_plain():
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(404)]}, {PAGE: [R(404)]})
    r = f.fetch(PAGE)
    assert r.status == HTTP_ERROR and r.http_status == 404 and "browser fallback also failed" in r.reason
    assert f.browser_hosts == set()  # a failed fallback does not make the host sticky
    f.fetch(PAGE)
    assert len(b.calls) == 1 and p.urls.count(PAGE) == 2  # not tried again in the same run


def test_browser_error_returns_plain_result_without_retries():
    f, p, b, c = make({ROBOTS: [R(404)], PAGE: [R(404)]}, {PAGE: [ConnectionError("no playwright")]})
    r = f.fetch(PAGE)
    assert r.status == HTTP_ERROR and r.http_status == 404 and len(b.calls) == 1
    assert 4.0 not in c.sleeps and 8.0 not in c.sleeps  # spacing only, no backoff loop


def test_robots_disallow_read_via_browser_blocks_and_page_never_fetched():
    f, p, b, _ = make(
        {ROBOTS: [R(500)], PAGE: [R(200)]},
        {ROBOTS: [R(200, b"User-agent: *\nDisallow: /page\n")], PAGE: [R(200)]},
    )
    r = f.fetch(PAGE)
    assert r.status == BLOCKED_BY_ROBOTS
    assert PAGE not in p.urls and PAGE not in b.urls


def test_robots_404_in_browser_allows_and_host_goes_sticky():
    f, p, b, _ = make({ROBOTS: [R(403)], PAGE: [R(200)]}, {ROBOTS: [R(404)], PAGE: [R(200, b"<html>x</html>")]})
    r = f.fetch(PAGE)
    assert r.status == OK and r.transport == "browser"
    assert p.urls == [ROBOTS]  # no plain page request: the host needed the browser for robots


def test_clean_robots_404_does_not_use_the_browser():
    f, p, b, _ = make({ROBOTS: [R(410)], PAGE: [R(200, b"ok")]})
    assert f.fetch(PAGE).status == OK and b.calls == []


def test_host_stickiness_after_successful_fallback():
    f, p, b, _ = make(
        {ROBOTS: [R(404)], PAGE: [R(404)], PAGE2: [R(200, b"plain")]},
        {PAGE: [R(200, b"<html>1</html>")], PAGE2: [R(200, b"<html>2</html>")]},
    )
    assert f.fetch(PAGE).transport == "browser"
    assert f.browser_hosts == {"a.edu"}
    r2 = f.fetch(PAGE2)
    assert r2.transport == "browser" and r2.body == b"<html>2</html>"
    assert PAGE2 not in p.urls  # no doomed plain request


def test_browser_requests_honour_spacing_and_crawl_delay():
    f, p, b, c = make(
        {ROBOTS: [R(200, b"User-agent: *\nCrawl-delay: 7\n")], PAGE: [R(404)]},
        {PAGE: [R(200, b"<html>1</html>")], PAGE2: [R(200, b"<html>2</html>")]},
    )
    f.fetch(PAGE)
    f.fetch(PAGE2)
    times = [t for t, *_ in p.calls + b.calls]
    assert sorted(times)[1] - sorted(times)[0] >= 7 - 1e-9
    spaced = sorted(times)
    assert all(b2 - a >= 7 - 1e-9 for a, b2 in zip(spaced, spaced[1:]))
    assert b.calls[1][0] - b.calls[0][0] >= 7 - 1e-9


def test_no_validators_for_browser_fetches():
    cache = {PAGE: {"etag": '"abc"', "last_modified": "x", "final_url": PAGE}}
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(404)]}, {PAGE: [R(200, b"<html></html>", etag='"zzz"')]}, cache=cache)
    r = f.fetch(PAGE)
    assert r.transport == "browser" and r.etag is None
    assert "If-None-Match" not in b.calls[0][2]
    assert cache[PAGE]["etag"] == '"abc"'  # nothing stored from the browser response


def test_browser_redirect_to_sso_is_refused_not_followed():
    f, p, b, _ = make(
        {ROBOTS: [R(404)], PAGE: [R(404)]},
        {PAGE: [R(302, location="https://login.a.edu/sso?x=1")]},
    )
    r = f.fetch(PAGE)
    assert r.status == LOGIN_OR_CAPTCHA and r.transport == "browser"


def test_disabled_by_default_changes_nothing():
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(404)]}, fallback=False)
    r = f.fetch(PAGE)
    assert r.status == HTTP_ERROR and r.http_status == 404 and r.reason == "HTTP 404" and r.transport == "http"
    assert b.calls == []
    # a plain 403 robots.txt is still allow-all with the fallback off
    f, p, b, _ = make({ROBOTS: [R(403)], PAGE: [R(200, b"ok")]}, fallback=False)
    assert f.fetch(PAGE).status == OK
    f, p, b, _ = make({ROBOTS: [R(500)], PAGE: [R(200)]}, fallback=False)
    assert f.fetch(PAGE).status == ROBOTS_UNREACHABLE


def test_importing_browser_transport_does_not_import_playwright():
    code = "import sys; import tools.common.browser_transport; assert 'playwright' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True, cwd=Path(__file__).resolve().parents[2])


def test_browser_transport_without_playwright_raises_connection_error(monkeypatch):
    from tools.common.browser_transport import BrowserTransport

    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with pytest.raises(ConnectionError, match="playwright is not installed"):
        BrowserTransport()("GET", PAGE, {"User-Agent": "x"}, 5)

def test_bot_wall_is_never_retried_in_the_browser():
    wall = R(403, b"<title>Just a moment...</title>", cf_mitigated="challenge")
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [wall]}, {PAGE: [R(200, b"<html>page</html>")]})
    r = f.fetch(PAGE)
    assert r.status == LOGIN_OR_CAPTCHA and b.calls == []


@pytest.mark.parametrize("status", [404, 406])
def test_captcha_body_on_404_or_406_is_not_retried_in_browser(status):
    f, p, b, _ = make({ROBOTS: [R(404)], PAGE: [R(status, b"<div class='g-recaptcha'></div>")]}, {PAGE: [R(200, b"x")]})
    r = f.fetch(PAGE)
    assert r.status == LOGIN_OR_CAPTCHA and b.calls == []


def test_robots_unreachable_in_both_stays_unreachable_for_every_url():
    f, p, b, _ = make({ROBOTS: [R(500)], PAGE: [R(404)], PAGE2: [R(404)]}, {ROBOTS: [R(503)], PAGE: [R(200)], PAGE2: [R(200)]})
    assert f.fetch(PAGE).status == ROBOTS_UNREACHABLE
    assert f.fetch(PAGE2).status == ROBOTS_UNREACHABLE
    assert b.urls == [ROBOTS]  # the browser read robots once
    assert PAGE not in p.urls + b.urls and PAGE2 not in p.urls + b.urls


def test_robots_429_is_not_retried_in_the_browser():
    f, p, b, _ = make({ROBOTS: [R(429, b"", retry_after="120")], PAGE: [R(200)]}, {ROBOTS: [R(200, b"")]})
    assert f.fetch(PAGE).status == ROBOTS_UNREACHABLE and b.calls == []


def test_plain_robots_403_keeps_allow_all_for_plain_but_forbids_the_browser():
    f, p, b, _ = make(
        {ROBOTS: [R(403)], PAGE: [R(200, b"ok")], PAGE2: [R(404)]},
        {ROBOTS: [R(503)], PAGE: [R(200, b"<html>x</html>")], PAGE2: [R(200, b"<html>x</html>")]},
    )
    r = f.fetch(PAGE)
    assert r.status == OK and r.transport == "http"  # reachable as it is without the fallback
    r2 = f.fetch(PAGE2)
    assert r2.status == HTTP_ERROR and r2.http_status == 404
    assert b.urls == [ROBOTS]  # the browser never fetched a page on that origin


def test_plain_robots_403_captcha_forbids_browser_without_calling_it():
    f, p, b, _ = make({ROBOTS: [R(403, b"<div class='g-recaptcha'></div>")], PAGE: [R(404)]}, {ROBOTS: [R(200, b"")], PAGE: [R(200)]})
    r = f.fetch(PAGE)
    assert r.status == HTTP_ERROR and b.calls == []


def test_plain_robots_403_then_browser_disallow_blocks():
    f, p, b, _ = make({ROBOTS: [R(403)], PAGE: [R(200)]}, {ROBOTS: [R(200, b"User-agent: *\nDisallow: /page\n", content_type="text/plain")], PAGE: [R(200)]})
    assert f.fetch(PAGE).status == BLOCKED_BY_ROBOTS
    assert PAGE not in p.urls + b.urls


@pytest.mark.parametrize("resp", [
    R(200, b"<html><body>Page not found</body></html>", content_type="text/html"),
    R(200, b"  <!doctype html><title>x</title>", content_type="text/plain"),
    R(200, b"Just a moment...", cf_mitigated="challenge"),
])
def test_browser_robots_that_is_html_or_a_challenge_is_not_read(resp):
    f, p, b, _ = make({ROBOTS: [R(500)], PAGE: [R(200)]}, {ROBOTS: [resp], PAGE: [R(200)]})
    r = f.fetch(PAGE)
    assert r.status == ROBOTS_UNREACHABLE and f.browser_hosts == set()
    assert PAGE not in p.urls + b.urls


def test_sticky_host_other_origin_with_unreadable_robots_is_unreachable():
    other = "http://a.edu/page"
    f, p, b, _ = make(
        {ROBOTS: [R(404)], PAGE: [R(404)], "http://a.edu/robots.txt": [R(200)], other: [R(200)]},
        {PAGE: [R(200, b"<html>1</html>")], "http://a.edu/robots.txt": [R(403, b"<div class='g-recaptcha'></div>")], other: [R(200)]},
    )
    assert f.fetch(PAGE).transport == "browser"
    r = f.fetch(other)
    assert r.status == ROBOTS_UNREACHABLE  # not allow-all, and the page is not fetched
    assert other not in p.urls + b.urls


def test_prefer_http_ignores_stickiness_but_keeps_the_403_404_fallback():
    f, p, b, _ = make(
        {ROBOTS: [R(404)], PAGE: [R(404)], PAGE2: [R(200, b"plain")]},
        {PAGE: [R(200, b"<html>1</html>")], PAGE2: [R(200, b"<html>2</html>")]},
    )
    assert f.fetch(PAGE).transport == "browser"
    r = f.fetch(PAGE2, prefer_http=True)
    assert r.transport == "http" and r.body == b"plain" and b.urls == [PAGE]
    f2, p2, b2, _ = make({ROBOTS: [R(404)], PAGE: [R(404)], PAGE2: [R(404)]}, {PAGE: [R(200, b"<html>1</html>")], PAGE2: [R(200, b"<html>2</html>")]})
    f2.fetch(PAGE)
    r2 = f2.fetch(PAGE2, prefer_http=True)
    assert r2.transport == "browser" and p2.urls.count(PAGE2) == 1


def test_browser_error_on_sticky_host_tries_plain_once_without_browser_retries():
    f, p, b, c = make(
        {ROBOTS: [R(404)], PAGE: [R(404)], PAGE2: [R(200, b"plain")]},
        {PAGE: [R(200, b"<html>1</html>")], PAGE2: [ConnectionError("timeout")]},
    )
    assert f.fetch(PAGE).transport == "browser"
    r = f.fetch(PAGE2)
    assert r.status == OK and r.transport == "http" and r.body == b"plain"
    assert b.urls.count(PAGE2) == 1  # no browser retries
    f2, p2, b2, c2 = make(
        {ROBOTS: [R(404)], PAGE: [R(404)], PAGE2: [OSError("down")]},
        {PAGE: [R(200, b"<html>1</html>")], PAGE2: [ConnectionError("timeout")]},
        max_retries=2,
    )
    f2.fetch(PAGE)
    r2 = f2.fetch(PAGE2)
    assert r2.status == HTTP_ERROR and b2.urls.count(PAGE2) == 1 and p2.urls.count(PAGE2) == 3  # plain keeps its retries
