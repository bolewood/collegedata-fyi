"""BrowserTransport route handler with fake browser, page and route objects. No network, no Playwright."""

import pytest

from tools.common.browser_transport import BrowserTransport

URL = "https://a.edu/page"


class FakeApiResponse:
    def __init__(self, status=200, headers=None, body=b""):
        self.status, self.headers, self._body = status, headers or {}, body

    def body(self):
        return self._body


class FakeFrame:
    pass


class FakeRequest:
    def __init__(self, url, resource_type="document", navigation=False, frame=None):
        self.url, self.resource_type, self._nav, self.frame = url, resource_type, navigation, frame

    def is_navigation_request(self):
        return self._nav


class FakeRoute:
    def __init__(self, request, api=None):
        self.request, self.api = request, api
        self.actions = []
        self.fetch_kwargs = None

    def fetch(self, **kw):
        self.fetch_kwargs = kw
        self.actions.append("fetch")
        return self.api

    def fulfill(self, **kw):
        self.actions.append("fulfill")

    def abort(self, *a):
        self.actions.append("abort")

    def continue_(self, *a):
        self.actions.append("continue")


class FakePage:
    """goto() replays scripted requests through the registered route handler."""

    def __init__(self, script, dom=b"<html>dom</html>"):
        self.main_frame, self.script, self.dom = FakeFrame(), script, dom
        self.handler = None
        self.routes = []

    def route(self, pattern, handler):
        assert pattern == "**/*"
        self.handler = handler

    def goto(self, url, wait_until=None, timeout=None):
        assert wait_until == "load"
        for make in self.script:
            route = make(self)
            self.routes.append(route)
            self.handler(route)

    def content(self):
        return self.dom.decode()

    def wait_for_timeout(self, ms):
        pass


class FakeContext:
    def __init__(self, page):
        self.page, self.closed = page, False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    version = "148.0"

    def __init__(self, page):
        self.page, self.contexts, self.ua = page, [], None

    def new_context(self, user_agent=None):
        self.ua = user_agent
        ctx = FakeContext(self.page)
        self.contexts.append(ctx)
        return ctx


def nav(api):
    return lambda page: FakeRoute(FakeRequest(URL, "document", True, page.main_frame), api)


def sub(rtype, url="https://cdn.other.com/x.js", navigation=False, frame=None):
    return lambda page: FakeRoute(FakeRequest(url, rtype, navigation, frame or page.main_frame))


def run(script, api_dom=b"<html>dom</html>"):
    page = FakePage(script, api_dom)
    t = BrowserTransport()
    t._browser = FakeBrowser(page)
    resp = t("GET", URL, {"User-Agent": "collegedata-fyi-x/0.1 (u)"}, 5)
    return resp, page, t


HTML = FakeApiResponse(200, {"Content-Type": "text/html; charset=iso-8859-1", "Content-Length": "9", "Content-Encoding": "gzip"}, b"raw")


def test_html_returns_rendered_dom_with_rewritten_headers():
    resp, page, t = run([nav(HTML)])
    assert resp.status == 200 and resp.body == b"<html>dom</html>"
    assert resp.headers["content-type"] == "text/html; charset=utf-8"
    assert "content-length" not in resp.headers and "content-encoding" not in resp.headers
    r = page.routes[0]
    assert r.fetch_kwargs == {"max_redirects": 0} and r.actions == ["fetch", "fulfill"]
    assert t._browser.contexts[0].closed
    assert "collegedata-fyi-x/0.1" in t._browser.ua and "Chrome/148.0" in t._browser.ua


@pytest.mark.parametrize("rtype", ["script", "xhr", "fetch", "stylesheet", "image", "font", "media", "websocket", "document", "other"])
def test_every_subresource_is_aborted(rtype):
    resp, page, _ = run([nav(HTML), sub(rtype), sub(rtype, "https://a.edu/api/awards.json")])
    assert [r.actions for r in page.routes[1:]] == [["abort"], ["abort"]]


def test_iframe_navigation_is_aborted_and_not_fetched():
    resp, page, _ = run([nav(HTML), sub("document", "https://tags.example/f.html", True, FakeFrame())])
    assert page.routes[1].actions == ["abort"]


def test_later_main_frame_navigation_is_aborted_and_never_recaptured():
    sso = FakeApiResponse(200, {"content-type": "text/html"}, b"login page")
    resp, page, _ = run([
        nav(FakeApiResponse(403, {"content-type": "text/html", "x-first": "1"}, b"first")),
        nav(sso),  # meta refresh / location= / challenge reload
    ])
    assert page.routes[1].actions == ["abort"] and page.routes[1].fetch_kwargs is None
    assert resp.status == 403 and resp.headers["x-first"] == "1"


def test_3xx_is_returned_not_followed():
    redirect = FakeApiResponse(302, {"Location": "https://a.edu/other"}, b"")
    resp, page, _ = run([nav(redirect)])
    assert resp.status == 302 and resp.headers["location"] == "https://a.edu/other" and resp.body == b""
    assert page.routes[0].actions == ["fetch", "abort"]


def test_non_html_returns_raw_body_without_rendering():
    for ctype, body in (("text/plain", b"User-agent: *\nDisallow: /x\n"), ("application/pdf", b"%PDF-1.4 x")):
        resp, page, _ = run([nav(FakeApiResponse(200, {"Content-Type": ctype}, body))])
        assert resp.body == body and resp.headers["content-type"] == ctype
        assert page.routes[0].actions == ["fetch", "abort"]


def test_navigation_error_after_capture_is_ignored_and_before_capture_raises():
    class Boom(FakePage):
        def goto(self, *a, **k):
            super().goto(*a, **k)
            raise RuntimeError("Download is starting")

    page = Boom([nav(FakeApiResponse(200, {"content-type": "application/pdf"}, b"%PDF"))])
    t = BrowserTransport()
    t._browser = FakeBrowser(page)
    assert t("GET", URL, {}, 5).body == b"%PDF"
    page2 = Boom([])
    t2 = BrowserTransport()
    t2._browser = FakeBrowser(page2)
    with pytest.raises(ConnectionError):
        t2("GET", URL, {}, 5)
    assert t2._browser.contexts[0].closed
