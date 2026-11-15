"""Headless-browser transport for ``PoliteFetcher`` (PRD 036 fallback).

Some school sites answer a plain HTTP client with 403/404 while serving the same
public page to a browser. ``BrowserTransport`` has the ``Transport`` signature and
returns the same ``Response`` as ``urllib_transport``, so ``PoliteFetcher`` applies
its own robots.txt, crawl-delay, redirect and login/CAPTCHA rules to it unchanged.

* Playwright is imported lazily, on the first request. Nothing else in the repo
  needs it installed.
* Redirects are NOT followed by the browser. The main-frame navigation is fetched
  with ``max_redirects=0``; a 3xx is returned as a ``Response`` with its
  ``location`` (and the navigation aborted), so the fetcher can run its robots and
  SSO checks on every hop, exactly as for urllib.
* HTML: the body is the rendered DOM (``page.content()``) as UTF-8 bytes.
  Anything else (PDF, text/plain such as robots.txt): the response body bytes.
* The User-Agent is Chromium-shaped with the fetcher's project UA appended.
* Every request except the first main-frame navigation is aborted: no scripts,
  XHR, fetch, iframes, images or stylesheets from any host, and no later navigation
  (meta refresh, ``location=``, a challenge's reload) in any frame. Only the one
  document the fetcher asked for, and checked against robots, is fetched. Inline
  scripts in that document still run, so the DOM is what the page renders without
  loading anything else. Consequence: a page that needs JavaScript ends up
  unreachable or unreadable text, and this fallback does not get past a bot
  challenge (those pages need scripts).
* One browser, one thread: the Playwright sync API is thread-bound, so calls are
  serialised by an internal lock. Call ``close()`` when done.

It is a transport only. It never decides whether a request is allowed.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping

from tools.common.polite_fetch import Response

_HTML_TYPES = ("text/html", "application/xhtml")


class BrowserTransport:
    def __init__(self, *, navigation_timeout: float | None = None, wait_after_load: float = 0.0):
        self._navigation_timeout = navigation_timeout
        self._wait_after_load = wait_after_load
        self._lock = threading.Lock()
        self._pw: Any = None
        self._browser: Any = None
        self.requests = 0  # main-document requests made (for tests and budgets)

    def _start(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ConnectionError("playwright is not installed (pip install -r tools/scholarships/monitor-requirements.txt)") from e
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(headless=True)
        except Exception as e:
            self.close()
            raise ConnectionError(f"could not launch headless chromium: {e}") from e

    def close(self) -> None:
        with_errors = (self._browser, self._pw)
        self._browser = self._pw = None
        for obj, stop in zip(with_errors, ("close", "stop")):
            if obj is not None:
                try:
                    getattr(obj, stop)()
                except Exception:
                    pass

    def __call__(self, method: str, url: str, headers: Mapping[str, str], timeout: float) -> Response:
        with self._lock:
            try:
                return self._get(url, headers, timeout)
            except ConnectionError:
                raise
            except Exception as e:  # playwright errors are not OSError; the fetcher expects OSError
                raise ConnectionError(f"browser fetch failed: {type(e).__name__}: {e}") from e

    def _get(self, url: str, headers: Mapping[str, str], timeout: float) -> Response:
        self._start()
        self.requests += 1
        ua = headers.get("User-Agent")
        if ua:  # a browser-shaped UA that still names this project, so the site can see who is reading
            ua = f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{self._browser.version} Safari/537.36 {ua}"
        ctx = self._browser.new_context(user_agent=ua) if ua else self._browser.new_context()
        try:
            captured: dict[str, Any] = {}
            page = ctx.new_page()
            ms = (self._navigation_timeout or timeout) * 1000

            def handler(route: Any) -> None:
                req = route.request
                if "status" in captured or captured.get("started") or not (
                    req.is_navigation_request() and req.frame == page.main_frame
                ):
                    route.abort()  # only the first main-frame navigation is ever fetched
                    return
                captured["started"] = True
                r = route.fetch(max_redirects=0)
                hdrs = {k.lower(): v for k, v in r.headers.items()}
                captured.update(status=r.status, headers=hdrs, body=None)
                ctype = hdrs.get("content-type", "").lower()
                if 300 <= r.status < 400 or not any(t in ctype for t in _HTML_TYPES):
                    captured["body"] = b"" if 300 <= r.status < 400 else r.body()
                    route.abort()  # redirects are the fetcher's to follow; non-HTML needs no rendering
                else:
                    route.fulfill(response=r)

            page.route("**/*", handler)
            try:
                page.goto(url, wait_until="load", timeout=ms)
            except Exception:
                if "status" not in captured:
                    raise  # never reached the document
            if "status" not in captured:
                raise ConnectionError("no navigation response captured")
            captured.pop("started", None)
            if captured["body"] is None:
                if self._wait_after_load:
                    page.wait_for_timeout(self._wait_after_load * 1000)
                captured["body"] = page.content().encode("utf-8")
                captured["headers"]["content-type"] = "text/html; charset=utf-8"
                captured["headers"].pop("content-length", None)
                captured["headers"].pop("content-encoding", None)
            return Response(captured["status"], captured["headers"], captured["body"])
        finally:
            ctx.close()
