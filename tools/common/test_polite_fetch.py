"""Tests for polite_fetch. No network, no real sleeping."""

import json
from email.utils import format_datetime
from datetime import datetime, timezone

from tools.common.polite_fetch import (
    BLOCKED_BY_ROBOTS, HTTP_ERROR, LOGIN_OR_CAPTCHA, NOT_MODIFIED, OK,
    ROBOTS_UNREACHABLE, PoliteFetcher, Response, parse_retry_after,
)

NOW = 1_800_000_000.0


class Fake:
    """Scripted transport + fake clock/sleep. Routes: url -> list of responses."""

    def __init__(self, routes):
        self.routes = {k: list(v) for k, v in routes.items()}
        self.calls = []  # (time, url, headers)
        self.t = NOW
        self.sleeps = []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def transport(self, method, url, headers, timeout):
        self.calls.append((self.t, url, dict(headers)))
        q = self.routes[url]
        r = q.pop(0) if len(q) > 1 else q[0]
        if isinstance(r, Exception):
            raise r
        return r

    def fetcher(self, **kw):
        kw.setdefault("min_spacing", 2.0)
        return PoliteFetcher("scholarships", transport=self.transport, clock=self.clock, sleep=self.sleep, **kw)


def R(status=200, body=b"", **h):
    return Response(status, {k.replace("_", "-"): v for k, v in h.items()}, body)


ROBOTS = "https://a.edu/robots.txt"
PAGE = "https://a.edu/page"


def test_user_agent_form():
    f = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"x")]}).fetcher()
    assert f.user_agent == "collegedata-fyi-scholarships/0.1 (https://github.com/bolewood/collegedata-fyi)"
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"x")]})
    fk.fetcher().fetch(PAGE)
    assert all(c[2]["User-Agent"].startswith("collegedata-fyi-scholarships/") for c in fk.calls)


def test_ok_and_robots_4xx_allows():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"hello")]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == OK and r.body == b"hello"


def test_robots_disallow_blocks_without_fetching_page():
    fk = Fake({ROBOTS: [R(200, b"User-agent: *\nDisallow: /page\n")], PAGE: [R(200)]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == BLOCKED_BY_ROBOTS
    assert [c[1] for c in fk.calls] == [ROBOTS]


def test_robots_specific_agent_beats_star_and_allow_longest_wins():
    txt = b"User-agent: *\nDisallow: /\n\nUser-agent: collegedata-fyi-scholarships\nDisallow: /private\nAllow: /private/ok$\n"
    fk = Fake({ROBOTS: [R(200, txt)], PAGE: [R(200)], "https://a.edu/private/ok": [R(200)], "https://a.edu/private/x": [R(200)]})
    f = fk.fetcher()
    assert f.fetch(PAGE).status == OK
    assert f.fetch("https://a.edu/private/ok").status == OK
    assert f.fetch("https://a.edu/private/x").status == BLOCKED_BY_ROBOTS


def test_robots_wildcard_and_end_anchor():
    txt = b"User-agent: *\nDisallow: /*.pdf$\n"
    fk = Fake({ROBOTS: [R(200, txt)], "https://a.edu/x.pdf": [R(200)], "https://a.edu/x.pdf?a=1": [R(200)]})
    f = fk.fetcher()
    assert f.fetch("https://a.edu/x.pdf").status == BLOCKED_BY_ROBOTS
    assert f.fetch("https://a.edu/x.pdf?a=1").status == OK


def test_robots_unreachable_5xx_and_network_error_block():
    for first in (R(503), OSError("down")):
        fk = Fake({ROBOTS: [first], PAGE: [R(200)]})
        r = fk.fetcher().fetch(PAGE)
        assert r.status == ROBOTS_UNREACHABLE
        assert [c[1] for c in fk.calls] == [ROBOTS]


def test_robots_cached_24h_then_refetched():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200)]})
    f = fk.fetcher()
    f.fetch(PAGE); f.fetch(PAGE)
    assert [c[1] for c in fk.calls].count(ROBOTS) == 1
    fk.t += 24 * 3600 + 1
    f.fetch(PAGE)
    assert [c[1] for c in fk.calls].count(ROBOTS) == 2


def test_crawl_delay_spacing_and_min_spacing():
    fk = Fake({ROBOTS: [R(200, b"User-agent: *\nCrawl-delay: 10\n")], PAGE: [R(200)], "https://a.edu/p2": [R(200)]})
    f = fk.fetcher(min_spacing=2.0)
    f.fetch(PAGE); f.fetch("https://a.edu/p2")
    times = [c[0] for c in fk.calls]  # robots, page, p2
    assert times[2] - times[1] >= 10.0
    assert times[1] - times[0] >= 10.0  # page request spaced after robots fetch


def test_min_spacing_default_applies_per_host_only():
    other = "https://b.edu/page"
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200)], "https://b.edu/robots.txt": [R(404)], other: [R(200)]})
    f = fk.fetcher()
    f.fetch(PAGE); f.fetch(other)
    t = {c[1]: c[0] for c in fk.calls}
    assert t[PAGE] - t[ROBOTS] >= 2.0
    assert t[other] - t["https://b.edu/robots.txt"] >= 2.0
    assert t["https://b.edu/robots.txt"] == t[PAGE]  # different host: no wait


def test_conditional_get_304_and_cache_dict():
    cache = {}
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"v1", etag='"e1"', last_modified="Mon, 01 Jan 2026 00:00:00 GMT"), R(304)]})
    f = fk.fetcher(cache=cache)
    r1 = f.fetch(PAGE)
    assert r1.status == OK and r1.etag == '"e1"'
    assert cache[PAGE]["etag"] == '"e1"'
    r2 = f.fetch(PAGE)
    assert r2.status == NOT_MODIFIED and r2.body is None and r2.etag == '"e1"'
    h = fk.calls[-1][2]
    assert h["If-None-Match"] == '"e1"' and h["If-Modified-Since"] == "Mon, 01 Jan 2026 00:00:00 GMT"


def test_cache_json_file_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"v1", etag='"e9"'), R(304)]})
    fk.fetcher(cache=p).fetch(PAGE)
    assert json.loads(p.read_text())[PAGE]["etag"] == '"e9"'
    fk2 = Fake({ROBOTS: [R(404)], PAGE: [R(304)]})
    r = fk2.fetcher(cache=p).fetch(PAGE)
    assert r.status == NOT_MODIFIED
    assert fk2.calls[-1][2]["If-None-Match"] == '"e9"'


def test_retry_after_seconds():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(429, retry_after="30"), R(200, b"ok")]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == OK and r.attempts == 2
    assert 30.0 in fk.sleeps


def test_retry_after_http_date():
    when = datetime.fromtimestamp(NOW + 45, tz=timezone.utc)
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(503, retry_after=format_datetime(when, usegmt=True)), R(200)]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == OK
    assert any(abs(s - 45) < 3 for s in fk.sleeps)
    assert parse_retry_after("garbage", NOW) is None
    assert parse_retry_after(format_datetime(datetime.fromtimestamp(NOW - 100, tz=timezone.utc), usegmt=True), NOW) == 0.0


def test_retries_bounded_then_http_error():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(500)]})
    r = fk.fetcher(max_retries=2).fetch(PAGE)
    assert r.status == HTTP_ERROR and r.http_status == 500
    assert [c[1] for c in fk.calls].count(PAGE) == 3


def test_retry_after_over_cap_gives_up():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(429, retry_after="99999")]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == HTTP_ERROR and [c[1] for c in fk.calls].count(PAGE) == 1


def test_plain_404_is_http_error_no_retry():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(404)]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == HTTP_ERROR and r.http_status == 404 and r.attempts == 1


def test_network_error_retried_then_ok():
    fk = Fake({ROBOTS: [R(404)], PAGE: [OSError("reset"), R(200, b"ok")]})
    assert fk.fetcher().fetch(PAGE).status == OK


def test_login_and_captcha_refused_never_retried():
    cases = [
        R(401),
        R(403, www_authenticate="Basic realm=x"),
        R(403, b"<div class='g-recaptcha'></div>"),
        R(403, cf_mitigated="challenge"),
        R(429, cf_mitigated="challenge", retry_after="5"),
    ]
    for resp in cases:
        fk = Fake({ROBOTS: [R(404)], PAGE: [resp, R(200)]})
        r = fk.fetcher().fetch(PAGE)
        assert r.status == LOGIN_OR_CAPTCHA, resp
        assert [c[1] for c in fk.calls].count(PAGE) == 1


def test_plain_403_is_http_error():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(403, b"forbidden")]})
    assert fk.fetcher().fetch(PAGE).status == HTTP_ERROR


def test_redirect_to_sso_host_refused_without_following():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(302, location="https://sso.a.edu/login?next=x")]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == LOGIN_OR_CAPTCHA
    assert all("sso.a.edu" not in c[1] for c in fk.calls)


def test_redirect_followed_and_robots_checked_on_target():
    dst = "https://b.edu/final"
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(301, location=dst)],
               "https://b.edu/robots.txt": [R(200, b"User-agent: *\nDisallow: /final\n")], dst: [R(200)]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == BLOCKED_BY_ROBOTS


def test_redirect_ok():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(301, location="/moved")], "https://a.edu/moved": [R(200, b"z")]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == OK and r.final_url == "https://a.edu/moved"
