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
    assert f.user_agent == "quadfile-scholarships/0.1 (https://github.com/bolewood/quadfile)"
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"x")]})
    fk.fetcher().fetch(PAGE)
    assert all(c[2]["User-Agent"].startswith("quadfile-scholarships/") for c in fk.calls)


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
    txt = b"User-agent: *\nDisallow: /\n\nUser-agent: quadfile-scholarships\nDisallow: /private\nAllow: /private/ok$\n"
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


def test_conditional_get_survives_redirect():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(301, location="/moved")],
               "https://a.edu/moved": [R(200, b"v1", etag='"r1"'), R(304)]})
    f = fk.fetcher()
    assert f.fetch(PAGE).status == OK
    r = f.fetch(PAGE)
    assert r.status == NOT_MODIFIED
    assert fk.calls[-1][1] == "https://a.edu/moved"
    assert fk.calls[-1][2]["If-None-Match"] == '"r1"'


def test_requests_hold_the_host_lock_and_http_https_share_it():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200)], "http://a.edu/robots.txt": [R(404)], "http://a.edu/x": [R(200)]})
    f = fk.fetcher()
    held = []
    orig = fk.transport

    def checking(method, url, headers, timeout):
        held.append(f._host_locks["a.edu"].locked())
        return orig(method, url, headers, timeout)

    f._transport = checking
    f.fetch(PAGE); f.fetch("http://a.edu/x")
    assert held and all(held)
    t = [c[0] for c in fk.calls]
    assert all(b - a >= 2.0 for a, b in zip(t, t[1:]))  # http and https spaced as one host


def test_refresh_of_robots_uses_known_crawl_delay():
    fk = Fake({ROBOTS: [R(200, b"User-agent: *\nCrawl-delay: 20\n")], PAGE: [R(200)]})
    f = fk.fetcher()
    f.fetch(PAGE)
    fk.t += 24 * 3600 + 1
    n = len(fk.calls)
    f.fetch(PAGE)
    assert fk.calls[n][1] == ROBOTS
    # the refresh was issued 24h later so it needed no wait; the page after it is 20 s later
    assert fk.calls[n + 1][0] - fk.calls[n][0] >= 20.0


def test_default_transport_wraps_http_client_errors(monkeypatch):
    import http.client
    import urllib.request
    from tools.common import polite_fetch as pf

    class Op:
        def open(self, *a, **k):
            raise http.client.IncompleteRead(b"x")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a: Op())
    try:
        pf.urllib_transport("GET", "https://a.edu/", {}, 1)
    except OSError:
        pass
    else:
        raise AssertionError("expected OSError subclass")


# ---------------------------------------------------------------- review round

import os
import time as _time

import pytest

from tools.common.polite_fetch import RobotsPolicy

TOKEN = "quadfile-scholarships"


def test_m1_utf8_bom_in_robots_does_not_drop_first_group():
    fk = Fake({ROBOTS: [R(200, b"\xef\xbb\xbfUser-agent: *\nDisallow: /\n")], PAGE: [R(200)]})
    assert fk.fetcher().fetch(PAGE).status == BLOCKED_BY_ROBOTS


def test_m2_robots_429_is_unreachable_and_not_cached():
    fk = Fake({ROBOTS: [R(429, retry_after="5"), R(200, b"User-agent: *\nDisallow: /\n")], PAGE: [R(200)]})
    f = fk.fetcher()
    assert f.fetch(PAGE).status == ROBOTS_UNREACHABLE
    assert [c[1] for c in fk.calls] == [ROBOTS]
    assert f.fetch(PAGE).status == BLOCKED_BY_ROBOTS  # refetched, real file honoured
    assert [c[1] for c in fk.calls].count(ROBOTS) == 2


@pytest.mark.parametrize("status", [429, 503])
def test_m3_captcha_body_on_429_503_not_retried(status):
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(status, b"<div class='g-recaptcha'></div>"), R(200)]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == LOGIN_OR_CAPTCHA
    assert [c[1] for c in fk.calls].count(PAGE) == 1


def test_m4_validators_not_sent_to_a_different_redirect_target():
    new = "https://b.edu/new"
    fk = Fake({ROBOTS: [R(404)], "https://b.edu/robots.txt": [R(404)],
               PAGE: [R(301, location="/moved"), R(301, location=new)],
               "https://a.edu/moved": [R(200, b"v1", last_modified="Mon, 01 Jun 2026 00:00:00 GMT")],
               new: [R(200, b"different")]})
    f = fk.fetcher()
    assert f.fetch(PAGE).status == OK
    n = len(fk.calls)
    r = f.fetch(PAGE)
    assert r.status == OK and r.body == b"different"
    for _, url, h in fk.calls[n:]:
        assert "If-Modified-Since" not in h and "If-None-Match" not in h, url


def test_s1_cache_file_atomic_and_bad_json_shapes(tmp_path, monkeypatch):
    p = tmp_path / "c.json"
    p.write_text("[]")  # valid JSON, not an object
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"v", etag='"a"')]})
    assert fk.fetcher(cache=p).fetch(PAGE).status == OK
    assert json.loads(p.read_text())[PAGE]["etag"] == '"a"'
    assert [x.name for x in tmp_path.iterdir()] == ["c.json"]  # no temp litter

    # a failed replace leaves the previous file intact and does not raise
    before = p.read_text()
    fk2 = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"v", etag='"b"')]})
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    assert fk2.fetcher(cache=p).fetch(PAGE).status == OK
    assert p.read_text() == before


def test_s1_cache_serialised_under_lock(tmp_path, monkeypatch):
    from tools.common import polite_fetch as pf
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(200, b"v", etag='"a"')]})
    f = fk.fetcher(cache=tmp_path / "c.json")
    seen = []
    real = pf.json.dumps
    monkeypatch.setattr(pf.json, "dumps", lambda *a, **k: (seen.append(f._cache_lock.locked()), real(*a, **k))[1])
    f.fetch(PAGE)
    assert seen == [True]


@pytest.mark.parametrize("loc", ["data:text/plain,hi", "ftp://a.edu/x"])
def test_s2_non_http_redirect_refused(loc):
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(302, location=loc)]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == HTTP_ERROR
    assert [c[1] for c in fk.calls] == [ROBOTS, PAGE]


def test_s2_non_http_robots_redirect_is_unreachable():
    fk = Fake({ROBOTS: [R(302, location="ftp://a.edu/robots.txt")], PAGE: [R(200)]})
    assert fk.fetcher().fetch(PAGE).status == ROBOTS_UNREACHABLE


def test_s2_value_error_from_transport_does_not_escape():
    fk = Fake({ROBOTS: [R(404)], PAGE: [UnicodeEncodeError("ascii", "é", 0, 1, "bad")]})
    assert fk.fetcher().fetch(PAGE).status == HTTP_ERROR
    fk = Fake({ROBOTS: [ValueError("bad")], PAGE: [R(200)]})
    assert fk.fetcher().fetch(PAGE).status == ROBOTS_UNREACHABLE


def test_s3_naive_retry_after_date_read_as_utc(monkeypatch):
    if not hasattr(_time, "tzset"):
        pytest.skip("no tzset")
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    _time.tzset()
    try:
        asctime = _time.asctime(_time.gmtime(NOW + 45))
        assert abs(parse_retry_after(asctime, NOW) - 45) < 2
    finally:
        monkeypatch.undo()
        _time.tzset()


def test_s4_infinite_crawl_delay_ignored_and_huge_one_refused():
    fk = Fake({ROBOTS: [R(200, b"User-agent: *\nCrawl-delay: inf\n")], PAGE: [R(200)]})
    assert fk.fetcher().fetch(PAGE).status == OK
    assert all(s != float("inf") for s in fk.sleeps)
    fk = Fake({ROBOTS: [R(200, b"User-agent: *\nCrawl-delay: 86400\n")], PAGE: [R(200)]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == HTTP_ERROR and "Crawl-delay" in r.reason
    assert [c[1] for c in fk.calls] == [ROBOTS]


def test_s5_network_errors_bounded():
    fk = Fake({ROBOTS: [R(404)], PAGE: [OSError("down")]})
    r = fk.fetcher(max_retries=2).fetch(PAGE)
    assert r.status == HTTP_ERROR and r.attempts == 3


def test_s5_redirect_loop_bounded():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(301, location="/b")], "https://a.edu/b": [R(301, location="/page")]})
    r = fk.fetcher().fetch(PAGE)
    assert r.status == HTTP_ERROR and "redirect" in r.reason
    assert len(fk.calls) <= 7


def test_s5_robots_redirect_loop_bounded_and_followed():
    fk = Fake({ROBOTS: [R(301, location="/r2")], "https://a.edu/r2": [R(301, location="/robots.txt")], PAGE: [R(200)]})
    assert fk.fetcher().fetch(PAGE).status == OK  # loop treated as unavailable-allowed per RFC 9309
    assert len(fk.calls) <= 8
    fk = Fake({ROBOTS: [R(301, location="https://a.edu/other")],
               "https://a.edu/other": [R(200, b"User-agent: *\nDisallow: /page\n")], PAGE: [R(200)]})
    assert fk.fetcher().fetch(PAGE).status == BLOCKED_BY_ROBOTS


def test_s5_robots_refresh_waits_known_crawl_delay():
    fk = Fake({ROBOTS: [R(200, b"User-agent: *\nCrawl-delay: 20\n")], PAGE: [R(200)]})
    f = fk.fetcher()
    f.fetch(PAGE)
    fk.t = NOW + 24 * 3600 - 5
    f.fetch(PAGE)  # inside TTL: no robots request
    page_t = fk.calls[-1][0]
    fk.t += 6  # now past the TTL
    f.fetch(PAGE)
    robots_calls = [c for c in fk.calls if c[1] == ROBOTS]
    assert len(robots_calls) == 2
    assert robots_calls[1][0] - page_t >= 20.0


def test_s5_same_host_login_path_redirect_refused():
    fk = Fake({ROBOTS: [R(404)], PAGE: [R(302, location="https://a.edu/user/login")]})
    assert fk.fetcher().fetch(PAGE).status == LOGIN_OR_CAPTCHA


def _pol(text):
    return RobotsPolicy(text, TOKEN)


def test_s6_rfc9309_matching_rules():
    u = lambda path: "https://a.edu" + path
    # equal-length Allow/Disallow: Allow wins
    assert _pol("User-agent: *\nDisallow: /p\nAllow: /p\n").allowed(u("/p"))
    assert _pol("User-agent: *\nAllow: /p\nDisallow: /p\n").allowed(u("/p"))
    # longer pattern beats shorter regardless of type
    assert not _pol("User-agent: *\nAllow: /p\nDisallow: /p/q\n").allowed(u("/p/q"))
    # first Crawl-delay wins
    assert _pol("User-agent: *\nCrawl-delay: 3\nCrawl-delay: 9\n").crawl_delay == 3
    # split groups for the same agent are merged
    pol = _pol(f"User-agent: {TOKEN}\nDisallow: /a\n\nUser-agent: *\nDisallow: /z\n\nUser-agent: {TOKEN}\nDisallow: /b\n")
    assert not pol.allowed(u("/a")) and not pol.allowed(u("/b")) and pol.allowed(u("/z"))
    # agent names are case-insensitive
    assert not _pol("User-agent: Quadfile-Scholarships\nDisallow: /\n").allowed(u("/x"))
    assert not _pol("USER-AGENT: *\nDISALLOW: /\n").allowed(u("/x"))
    # percent-encoding equivalence
    assert not _pol("User-agent: *\nDisallow: /%7Euser\n").allowed(u("/~user"))
    assert not _pol("User-agent: *\nDisallow: /~user\n").allowed(u("/%7Euser"))
    # empty Disallow allows everything
    assert _pol("User-agent: *\nDisallow:\n").allowed(u("/x"))


def test_s6_robots_truncated_at_500_kib():
    body = b"#" + b"x" * (500 * 1024) + b"\nUser-agent: *\nDisallow: /\n"
    fk = Fake({ROBOTS: [R(200, body)], PAGE: [R(200)]})
    assert fk.fetcher().fetch(PAGE).status == OK
