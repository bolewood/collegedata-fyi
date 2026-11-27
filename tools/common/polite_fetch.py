"""Polite, synchronous HTTP fetcher shared by Quadfile monitors.

Behaviour (PRD 036 M4):

* robots.txt per RFC 9309, cached 24 h per host. 4xx on robots.txt means
  "allowed" except 429; a network error, 5xx or 429 means "unreachable" and
  blocks every fetch to that host (the unreachable state is not cached, so the next call retries).
* ``Crawl-delay`` is honoured; requests to one host are strictly serialised and
  spaced by ``max(min_spacing, crawl_delay)``.
* ``User-Agent`` follows the repo form ``quadfile-<token>/<ver> (<url>)``.
* Conditional GET (ETag / Last-Modified) from a caller-supplied dict or JSON file.
* Login walls and CAPTCHAs are refused and never retried.
* 429/5xx/network errors are retried a bounded number of times, honouring
  Retry-After (delta-seconds or HTTP-date).

Browser fallback (off by default, ``browser_fallback=<transport>``): see
``BROWSER_FALLBACK_RULES``. Transport, clock and sleep are injectable so tests
need no network. Standard library only.

Left out of RFC 9309 on purpose: see ``RFC9309_NOT_IMPLEMENTED``.
"""

from __future__ import annotations

import http.client
import json
import logging
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, Mapping, MutableMapping
from urllib.parse import unquote, urljoin, urlsplit

CONTACT_URL = "https://github.com/bolewood/quadfile"
ROBOTS_TTL_SECONDS = 24 * 60 * 60
ROBOTS_MAX_BYTES = 500 * 1024  # RFC 9309 s2.5: parse at least 500 KiB
MAX_REDIRECTS = 5
log = logging.getLogger(__name__)

RFC9309_NOT_IMPLEMENTED = (
    "Sitemap lines are ignored (not needed for access decisions). "
    "Cache-Control/Expires on robots.txt is ignored in favour of a fixed 24 h TTL. "
    "Percent-encoding is normalised by unquoting both sides (unreserved-only "
    "normalisation is not distinguished). Non-UTF-8 robots bytes are decoded "
    "with errors='replace' rather than rejected. A 429 on robots.txt is treated as "
    "unreachable (stricter than RFC 9309 s2.3.1.3, which counts every 4xx as unavailable)."
)

BROWSER_FALLBACK_RULES = (
    "With browser_fallback set, a page that the plain transport answers 403, 404 or "
    "406 (and that is not a login or CAPTCHA challenge) is retried once per URL per "
    "run through the browser transport. A robots.txt the plain transport cannot read "
    "(a network error, a 5xx or another non-2xx other than a clean 404/410; never a "
    "429, which is not retried in the browser) is retried through the browser first: "
    "its rules apply as usual, a Disallow still blocks, a 404/410 there means "
    "allow-all. If it cannot be read there either, the result is robots_unreachable "
    "when the plain answer was unreachable; when the plain answer was a 4xx (allow-all "
    "by RFC 9309) plain fetches keep that reading but the browser is forbidden on that "
    "origin. A browser robots.txt that is an HTML page or a challenge is unreadable. "
    "Logins, SSO redirects, CAPTCHAs and bot challenges are never retried and never "
    "bypassed: the browser loads nothing but the first document and cannot get past "
    "one. A host whose fallback succeeded uses the browser directly for the rest of the "
    "run (browser_hosts), unless the caller passes prefer_http=True for that URL. "
    "Spacing and Crawl-delay apply to browser requests; validators are neither sent nor "
    "stored for them. After a browser error on a sticky host the plain transport is "
    "tried once, and the browser transport is never retried on network errors."
)

# Result statuses.
OK = "ok"
NOT_MODIFIED = "not_modified"
BLOCKED_BY_ROBOTS = "blocked_by_robots"
ROBOTS_UNREACHABLE = "robots_unreachable"
HTTP_ERROR = "http_error"
LOGIN_OR_CAPTCHA = "login_or_captcha"

_SSO_HOST_RE = re.compile(
    r"(^|\.)(login|sso|auth|idp|shibboleth|cas|accounts|signin|okta|"
    r"login\.microsoftonline|adfs)\.|okta\.com$|auth0\.com$|onelogin\.com$|"
    r"microsoftonline\.com$|accounts\.google\.com$",
    re.I,
)
_SSO_PATH_RE = re.compile(r"/(login|signin|sign-in|sso|saml2?|cas/login|shibboleth|oauth2?/authorize)(/|$|\?)", re.I)
_CHALLENGE_BODY_RE = re.compile(
    rb"captcha|cf-chl|cf-turnstile|just a moment\.\.\.|attention required|"
    rb"are you a robot|verify you are human|g-recaptcha|h-captcha",
    re.I,
)
_HARD_CHALLENGE_BODY_RE = re.compile(
    rb"captcha|cf-turnstile|are you a robot|verify you are human|g-recaptcha|h-captcha", re.I
)
_FALLBACK_STATUSES = (403, 404, 406)


@dataclass
class Response:
    """What a transport returns. Header names must be lower-case."""

    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


# transport(method, url, headers, timeout) -> Response. Must NOT follow redirects.
Transport = Callable[[str, str, Mapping[str, str], float], Response]


@dataclass
class FetchResult:
    status: str  # one of the module-level status constants
    url: str
    final_url: str | None = None
    http_status: int | None = None
    body: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)
    etag: str | None = None
    last_modified: str | None = None
    reason: str = ""
    attempts: int = 0
    transport: str = "http"  # "http" | "browser": which transport produced the response

    @property
    def ok(self) -> bool:
        return self.status == OK


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # noqa: D401
        return None


def urllib_transport(method: str, url: str, headers: Mapping[str, str], timeout: float) -> Response:
    """Default transport: urllib, redirects not followed, HTTP errors returned."""
    req = urllib.request.Request(url, headers=dict(headers), method=method)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as r:
            return Response(r.status, {k.lower(): v for k, v in r.headers.items()}, r.read())
    except http.client.HTTPException as e:
        raise ConnectionError(f"{type(e).__name__}: {e}") from e
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return Response(e.code, {k.lower(): v for k, v in e.headers.items()}, body)


# ---------------------------------------------------------------- robots.txt

@dataclass
class _Rule:
    allow: bool
    pattern: str
    regex: re.Pattern


def _compile_pattern(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    body = ".*".join(re.escape(p) for p in pattern.split("*"))
    return re.compile("^" + body + ("$" if anchored else ""))


def _norm_path(p: str) -> str:
    return unquote(p)


class RobotsPolicy:
    """Parsed robots.txt for one product token."""

    def __init__(self, text: str | None, product_token: str):
        self.rules: list[_Rule] = []
        self.crawl_delay: float | None = None
        if text is not None:
            self._parse(text, product_token.lower())

    @staticmethod
    def allow_all(product_token: str = "") -> "RobotsPolicy":
        return RobotsPolicy(None, product_token)

    def _parse(self, text: str, token: str) -> None:
        groups: list[tuple[list[str], list[tuple[str, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[str, str]] = []
        in_rules = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip()
            if key == "user-agent":
                if in_rules:
                    groups.append((agents, rules))
                    agents, rules, in_rules = [], [], False
                agents.append(val.lower())
            elif key in ("allow", "disallow", "crawl-delay"):
                in_rules = True
                rules.append((key, val))
        if agents:
            groups.append((agents, rules))

        # RFC 9309 2.2.1: the most specific (longest) matching product token wins;
        # all groups naming that agent are merged; else fall back to "*".
        best, best_len = [], -1
        star: list[tuple[str, str]] = []
        for ags, rs in groups:
            for a in ags:
                if a == "*":
                    star.extend(rs)
                elif a == token:
                    if len(a) > best_len:
                        best, best_len = [], len(a)
                    if len(a) == best_len:
                        best.extend(rs)
        chosen = best if best_len >= 0 else star
        for key, val in chosen:
            if key == "crawl-delay":
                try:
                    d = float(val)
                    if math.isfinite(d) and d >= 0 and self.crawl_delay is None:
                        self.crawl_delay = d
                except ValueError:
                    pass
            elif val == "":
                continue  # empty Disallow = allow all; empty Allow = no-op
            else:
                pat = _norm_path(val)
                self.rules.append(_Rule(key == "allow", pat, _compile_pattern(pat)))

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        path = _norm_path(path)
        best: _Rule | None = None
        for r in self.rules:
            if r.regex.match(path):
                # longest pattern wins; on a tie, Allow wins (RFC 9309 2.2.2)
                if best is None or len(r.pattern) > len(best.pattern) or (
                    len(r.pattern) == len(best.pattern) and r.allow and not best.allow
                ):
                    best = r
        return True if best is None else best.allow


# ------------------------------------------------------------------- fetcher

def parse_retry_after(value: str | None, now: float) -> float | None:
    """Seconds to wait from a Retry-After header (delta-seconds or HTTP-date)."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, dt.timestamp() - now)


def make_user_agent(product_token: str, version: str = "0.1", contact_url: str = CONTACT_URL) -> str:
    token = product_token.removeprefix("collegedata-fyi-").removeprefix("quadfile-")
    return f"quadfile-{token}/{version} ({contact_url})"


class PoliteFetcher:
    def __init__(
        self,
        product_token: str,
        *,
        version: str = "0.1",
        contact_url: str = CONTACT_URL,
        cache: MutableMapping[str, dict] | str | Path | None = None,
        min_spacing: float = 2.0,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        max_retry_after: float = 300.0,
        max_crawl_delay: float = 300.0,
        timeout: float = 30.0,
        transport: Transport = urllib_transport,
        browser_fallback: Transport | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.user_agent = make_user_agent(product_token, version, contact_url)
        # robots product token: the bare name without version (RFC 9309 2.2.1).
        self.robots_token = self.user_agent.split("/", 1)[0]
        self.min_spacing = min_spacing
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_retry_after = max_retry_after
        self.max_crawl_delay = max_crawl_delay
        self.timeout = timeout
        self._transport, self._clock, self._sleep = transport, clock, sleep
        self._browser = browser_fallback
        self.browser_hosts: set[str] = set()  # hosts that needed the browser this run
        self._fallback_tried: set[str] = set()  # URLs (and robots.txt URLs) already retried
        self._no_browser: set[str] = set()  # origins whose robots.txt the browser may not be used on
        self._cache_path: Path | None = None
        if isinstance(cache, (str, Path)):
            self._cache_path = Path(cache)
            loaded: object = {}
            try:
                loaded = json.loads(self._cache_path.read_text())
            except FileNotFoundError:
                pass
            except (OSError, ValueError) as e:
                log.warning("polite_fetch: unreadable cache %s (%s); starting empty", self._cache_path, e)
            if not isinstance(loaded, dict):
                log.warning("polite_fetch: cache %s is not a JSON object; starting empty", self._cache_path)
                loaded = {}
            self.cache: MutableMapping[str, dict] = loaded
        else:
            self.cache = cache if cache is not None else {}
        self._robots: dict[str, tuple[float, RobotsPolicy]] = {}
        self._last_request: dict[str, float] = {}
        self._host_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._cache_lock = threading.Lock()

    # -- internals
    def _lock(self, host: str) -> threading.Lock:
        with self._locks_guard:
            return self._host_locks.setdefault(host, threading.Lock())

    @staticmethod
    def _host(url: str) -> str:
        return (urlsplit(url).hostname or "").lower()

    @staticmethod
    def _origin(url: str) -> str:
        p = urlsplit(url)
        return f"{p.scheme}://{p.netloc.lower()}"

    def close(self) -> None:
        """Release the browser transport, if it has a close()."""
        closer = getattr(self._browser, "close", None)
        if callable(closer):
            closer()

    def _spaced_request(
        self, url: str, headers: Mapping[str, str], delay: float, transport: Transport | None = None
    ) -> Response:
        """One request, serialised per host and spaced. Caller holds no lock."""
        origin = self._host(url)
        with self._lock(origin):
            last = self._last_request.get(origin)
            if last is not None:
                wait = last + delay - self._clock()
                if wait > 0:
                    self._sleep(wait)
            try:
                return (transport or self._transport)("GET", url, headers, self.timeout)
            finally:
                self._last_request[origin] = self._clock()

    def _read_robots(
        self, origin: str, delay: float, transport: Transport | None
    ) -> tuple[RobotsPolicy | None, str, str]:
        """One robots.txt read. Returns (policy, kind, challenge); challenge is "none",
        "soft" (a bot wall) or "hard" (login or CAPTCHA); any challenge keeps the browser away; kind is "read",
        "missing" (clean 404/410 or a redirect loop: allow-all), "denied" (another
        4xx except 429: allow-all by RFC 9309), "throttled" (429, policy None) or
        "unreachable" (policy None). A browser read counts as "read" only when it is
        not an HTML page or a challenge: a bot manager's 200 interstitial is not
        robots.txt."""
        url = origin + "/robots.txt"
        headers = {"User-Agent": self.user_agent, "Accept": "text/plain, */*;q=0.1"}
        for _ in range(MAX_REDIRECTS + 1):
            try:
                resp = self._spaced_request(url, headers, delay, transport)
            except (OSError, ValueError):
                return None, "unreachable", "none"
            if resp.status in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                url = urljoin(url, resp.headers["location"])
                if urlsplit(url).scheme not in ("http", "https"):
                    return None, "unreachable", "none"
                continue
            if 200 <= resp.status < 300:
                if transport is not None and (
                    "html" in resp.headers.get("content-type", "").lower()
                    or resp.body.lstrip()[:1] == b"<"
                    or resp.headers.get("cf-mitigated")
                    or _CHALLENGE_BODY_RE.search(resp.body[:65536])
                    or self._is_hard_challenge(resp)
                ):
                    return None, "unreachable", "none"
                text = resp.body[:ROBOTS_MAX_BYTES].decode("utf-8-sig", errors="replace")
                return RobotsPolicy(text, self.robots_token), "read", "none"
            challenged = "none"
            if self._is_challenge(resp):
                challenged = "hard" if self._is_hard_challenge(resp) else "soft"
            if resp.status == 429:
                return None, "throttled", challenged  # rate-limited: never cache as allow
            if resp.status in (404, 410):
                return RobotsPolicy.allow_all(), "missing", challenged
            if 400 <= resp.status < 500:
                return RobotsPolicy.allow_all(), "denied", challenged
            return None, "unreachable", challenged  # 5xx or unexpected
        return RobotsPolicy.allow_all(), "missing", "none"  # redirect loop >5 hops treated as 404 (RFC 9309 2.3.1.2)

    def _get_robots(self, origin: str) -> RobotsPolicy | None:
        """Policy for origin, or None when robots.txt is unreachable."""
        hit = self._robots.get(origin)
        if hit and self._clock() - hit[0] < ROBOTS_TTL_SECONDS:
            return hit[1]
        host = self._host(origin)
        prev_delay = min(self._delay_for(hit[1]), self.max_crawl_delay) if hit else self.min_spacing
        if self._browser is not None and host in self.browser_hosts:
            policy, kind, _ = self._read_robots(origin, prev_delay, self._browser)
            if kind not in ("read", "missing"):
                policy = None  # a 4xx here is not allow-all: nobody read this origin's robots.txt
        else:
            policy, kind, challenge = self._read_robots(origin, prev_delay, None)
            rurl = origin + "/robots.txt"
            if self._browser is not None and kind in ("denied", "unreachable"):
                # The plain client could not read robots.txt: ask the browser once. Its
                # rules apply. If it cannot read the file either, an unreachable plain
                # answer stays unreachable; a plain 4xx keeps its RFC 9309 allow-all for
                # plain fetches, but the browser is forbidden on this origin. A login,
                # CAPTCHA or bot challenge is never retried in the browser.
                if challenge != "none" or rurl in self._fallback_tried:
                    bkind = "unreadable"
                else:
                    self._fallback_tried.add(rurl)
                    bpolicy, bkind, _ = self._read_robots(origin, prev_delay, self._browser)
                    if bkind in ("read", "missing"):
                        policy = bpolicy
                        self.browser_hosts.add(host)
                if bkind not in ("read", "missing"):
                    if kind == "denied":
                        self._no_browser.add(origin)
                    else:
                        policy = None
        if policy is None:
            return None
        self._robots[origin] = (self._clock(), policy)
        return policy

    def _delay_for(self, policy: RobotsPolicy) -> float:
        return max(self.min_spacing, policy.crawl_delay or 0.0)

    def _remember(self, url: str, entry: dict) -> None:
        """Store validators and persist atomically (temp file + os.replace)."""
        with self._cache_lock:
            self.cache[url] = entry
            if self._cache_path is None:
                return
            tmp = self._cache_path.with_name(self._cache_path.name + f".{os.getpid()}.tmp")
            try:
                self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(json.dumps(self.cache, indent=2, sort_keys=True))
                os.replace(tmp, self._cache_path)
            except OSError as e:
                log.warning("polite_fetch: could not save cache %s: %s", self._cache_path, e)
                try:
                    tmp.unlink()
                except OSError:
                    pass

    @staticmethod
    def _is_sso_redirect(url: str) -> bool:
        p = urlsplit(url)
        return bool(_SSO_HOST_RE.search(p.hostname or "") or _SSO_PATH_RE.search(p.path))

    @staticmethod
    def _is_hard_challenge(resp: Response) -> bool:
        """Login or CAPTCHA signals (401, www-authenticate, CAPTCHA markers in the
        body), on any status: such a response is never retried in the browser."""
        if resp.status == 401 or resp.headers.get("www-authenticate"):
            return True
        return bool(_HARD_CHALLENGE_BODY_RE.search(resp.body[:65536]))

    @staticmethod
    def _is_challenge(resp: Response) -> bool:
        if resp.status in (401, 403, 429, 503):
            if resp.headers.get("www-authenticate") or resp.headers.get("cf-mitigated"):
                return True
            if _CHALLENGE_BODY_RE.search(resp.body[:65536]):
                return True
            if resp.status == 401:
                return True
        return False

    @staticmethod
    def _browser_failed(plain: FetchResult, why: str, attempts: int) -> FetchResult:
        """The browser retry did not help: report the plain result, noting the retry."""
        plain.reason = f"{plain.reason}; browser fallback also failed ({why})"
        plain.attempts = attempts
        return plain

    # -- public API
    def fetch(self, url: str, prefer_http: bool = False) -> FetchResult:
        """GET url politely. Never raises on network/HTTP problems.

        prefer_http: try the plain transport first even on a host that already needed
        the browser (the 403/404/406 fallback still applies). Callers use it for a
        URL whose last good fetch was plain, so its transport stays stable."""
        current = url
        attempts = 0
        retries = 0
        redirects = 0
        plain_failure: FetchResult | None = None  # set while a browser retry is in flight
        plain_after_browser_error = False
        while True:
            origin = self._origin(current)
            policy = self._get_robots(origin)
            if policy is None:
                return FetchResult(ROBOTS_UNREACHABLE, url, current, reason=f"robots.txt unreachable for {origin}", attempts=attempts)
            if not policy.allowed(current):
                return FetchResult(BLOCKED_BY_ROBOTS, url, current, reason=f"disallowed by robots.txt for {origin}", attempts=attempts)

            if policy.crawl_delay is not None and policy.crawl_delay > self.max_crawl_delay:
                return FetchResult(HTTP_ERROR, url, current, reason=f"Crawl-delay {policy.crawl_delay:.0f}s exceeds cap {self.max_crawl_delay:.0f}s", attempts=attempts)

            use_browser = (
                self._browser is not None
                and not prefer_http
                and not plain_after_browser_error
                and self._host(current) in self.browser_hosts
            )
            via = "browser" if (use_browser or plain_failure is not None) else "http"
            headers = {"User-Agent": self.user_agent, "Accept": "*/*"}
            cached = self.cache.get(url)
            if via == "browser" or not isinstance(cached, dict) or current != cached.get("final_url", url):
                cached = None  # validators belong to the resource they came from; none for the browser
            if cached:
                if cached.get("etag"):
                    headers["If-None-Match"] = cached["etag"]
                if cached.get("last_modified"):
                    headers["If-Modified-Since"] = cached["last_modified"]

            attempts += 1
            try:
                resp = self._spaced_request(
                    current, headers, self._delay_for(policy), self._browser if via == "browser" else None
                )
            except ValueError as e:
                if plain_failure is not None:
                    return self._browser_failed(plain_failure, f"invalid response: {e}", attempts)
                return FetchResult(HTTP_ERROR, url, current, reason=f"invalid request/response: {e}", attempts=attempts, transport=via)
            except OSError as e:
                if plain_failure is not None:
                    return self._browser_failed(plain_failure, f"browser error: {e}", attempts)
                if via == "browser":
                    # Sticky host and the browser failed: no browser retries; one plain try.
                    plain_after_browser_error = True
                    continue
                if retries < self.max_retries:
                    self._sleep(self.backoff_base * (2**retries))
                    retries += 1
                    continue
                return FetchResult(HTTP_ERROR, url, current, reason=f"network error: {e}", attempts=attempts, transport=via)

            if resp.status in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                nxt = urljoin(current, resp.headers["location"])
                if urlsplit(nxt).scheme not in ("http", "https"):
                    return FetchResult(HTTP_ERROR, url, current, resp.status, reason=f"redirect to non-HTTP target {nxt[:80]!r}", attempts=attempts)
                if self._is_sso_redirect(nxt) and not self._is_sso_redirect(current):
                    return FetchResult(LOGIN_OR_CAPTCHA, url, nxt, resp.status, reason="redirect to login/SSO host", attempts=attempts, transport=via)
                redirects += 1
                if redirects > MAX_REDIRECTS:
                    return FetchResult(HTTP_ERROR, url, current, resp.status, reason="too many redirects", attempts=attempts)
                current = nxt
                continue

            if self._is_challenge(resp):
                return FetchResult(LOGIN_OR_CAPTCHA, url, current, resp.status, headers=resp.headers, reason="login or CAPTCHA challenge; not retried", attempts=attempts, transport=via)

            if (
                via == "http"
                and self._browser is not None
                and resp.status in _FALLBACK_STATUSES
                and current not in self._fallback_tried
                and self._origin(current) not in self._no_browser
            ):
                if self._is_hard_challenge(resp):
                    return FetchResult(LOGIN_OR_CAPTCHA, url, current, resp.status, headers=resp.headers, reason="login or CAPTCHA challenge; not retried", attempts=attempts)
                # The plain client was refused or told "not found": one retry through the browser.
                self._fallback_tried.add(current)
                plain_failure = FetchResult(HTTP_ERROR, url, current, resp.status, resp.body, resp.headers, reason=f"HTTP {resp.status}", attempts=attempts)
                continue

            if resp.status == 304:
                c = cached or {}
                return FetchResult(NOT_MODIFIED, url, current, 304, headers=resp.headers, etag=c.get("etag"), last_modified=c.get("last_modified"), attempts=attempts)

            if 200 <= resp.status < 300:
                if via == "browser":
                    if plain_failure is not None:
                        self.browser_hosts.add(self._host(current))  # the fallback worked: stay on the browser for this host
                    return FetchResult(OK, url, current, resp.status, resp.body, resp.headers, attempts=attempts, transport="browser")
                etag, lm = resp.headers.get("etag"), resp.headers.get("last-modified")
                if etag or lm:
                    self._remember(url, {"etag": etag, "last_modified": lm, "final_url": current})
                return FetchResult(OK, url, current, resp.status, resp.body, resp.headers, etag, lm, attempts=attempts)

            if plain_failure is not None:
                return self._browser_failed(plain_failure, f"browser got HTTP {resp.status}", attempts)

            if resp.status in (429, 500, 502, 503, 504):
                if retries >= self.max_retries:
                    return FetchResult(HTTP_ERROR, url, current, resp.status, headers=resp.headers, reason="retries exhausted", attempts=attempts, transport=via)
                ra = parse_retry_after(resp.headers.get("retry-after"), self._clock())
                if ra is not None and ra > self.max_retry_after:
                    return FetchResult(HTTP_ERROR, url, current, resp.status, headers=resp.headers, reason=f"Retry-After {ra:.0f}s exceeds cap", attempts=attempts, transport=via)
                self._sleep(ra if ra is not None else self.backoff_base * (2**retries))
                retries += 1
                continue

            return FetchResult(HTTP_ERROR, url, current, resp.status, resp.body, resp.headers, reason=f"HTTP {resp.status}", attempts=attempts, transport=via)
