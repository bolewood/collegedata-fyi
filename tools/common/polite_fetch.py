"""Polite, synchronous HTTP fetcher shared by collegedata.fyi monitors.

Behaviour (PRD 036 M4):

* robots.txt per RFC 9309, cached 24 h per host. 4xx on robots.txt means
  "allowed" except 429; a network error, 5xx or 429 means "unreachable" and
  blocks every fetch to that host (the unreachable state is not cached, so the next call retries).
* ``Crawl-delay`` is honoured; requests to one host are strictly serialised and
  spaced by ``max(min_spacing, crawl_delay)``.
* ``User-Agent`` follows the repo form ``collegedata-fyi-<token>/<ver> (<url>)``.
* Conditional GET (ETag / Last-Modified) from a caller-supplied dict or JSON file.
* Login walls and CAPTCHAs are refused and never retried.
* 429/5xx/network errors are retried a bounded number of times, honouring
  Retry-After (delta-seconds or HTTP-date).

Transport, clock and sleep are injectable so tests need no network. Standard
library only.

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

CONTACT_URL = "https://github.com/bolewood/collegedata-fyi"
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
    token = product_token.removeprefix("collegedata-fyi-")
    return f"collegedata-fyi-{token}/{version} ({contact_url})"


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

    def _spaced_request(self, url: str, headers: Mapping[str, str], delay: float) -> Response:
        """One request, serialised per host and spaced. Caller holds no lock."""
        origin = self._host(url)
        with self._lock(origin):
            last = self._last_request.get(origin)
            if last is not None:
                wait = last + delay - self._clock()
                if wait > 0:
                    self._sleep(wait)
            try:
                return self._transport("GET", url, headers, self.timeout)
            finally:
                self._last_request[origin] = self._clock()

    def _get_robots(self, origin: str) -> RobotsPolicy | None:
        """Policy for origin, or None when robots.txt is unreachable."""
        hit = self._robots.get(origin)
        if hit and self._clock() - hit[0] < ROBOTS_TTL_SECONDS:
            return hit[1]
        url = origin + "/robots.txt"
        headers = {"User-Agent": self.user_agent, "Accept": "text/plain, */*;q=0.1"}
        prev_delay = min(self._delay_for(hit[1]), self.max_crawl_delay) if hit else self.min_spacing
        policy: RobotsPolicy | None = None
        for _ in range(MAX_REDIRECTS + 1):
            try:
                resp = self._spaced_request(url, headers, prev_delay)
            except (OSError, ValueError):
                return None
            if resp.status in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                url = urljoin(url, resp.headers["location"])
                if urlsplit(url).scheme not in ("http", "https"):
                    return None
                continue
            if 200 <= resp.status < 300:
                text = resp.body[:ROBOTS_MAX_BYTES].decode("utf-8-sig", errors="replace")
                policy = RobotsPolicy(text, self.robots_token)
            elif resp.status == 429:
                return None  # rate-limited: treat as unreachable, never cache as allow
            elif 400 <= resp.status < 500:
                policy = RobotsPolicy.allow_all()
            else:
                return None  # 5xx or unexpected: unreachable
            break
        else:
            policy = RobotsPolicy.allow_all()  # redirect loop >5 hops treated as 404 (RFC 9309 2.3.1.2)
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
    def _is_challenge(resp: Response) -> bool:
        if resp.status in (401, 403, 429, 503):
            if resp.headers.get("www-authenticate") or resp.headers.get("cf-mitigated"):
                return True
            if _CHALLENGE_BODY_RE.search(resp.body[:65536]):
                return True
            if resp.status == 401:
                return True
        return False

    # -- public API
    def fetch(self, url: str) -> FetchResult:
        """GET url politely. Never raises on network/HTTP problems."""
        current = url
        attempts = 0
        retries = 0
        redirects = 0
        while True:
            origin = self._origin(current)
            policy = self._get_robots(origin)
            if policy is None:
                return FetchResult(ROBOTS_UNREACHABLE, url, current, reason=f"robots.txt unreachable for {origin}", attempts=attempts)
            if not policy.allowed(current):
                return FetchResult(BLOCKED_BY_ROBOTS, url, current, reason=f"disallowed by robots.txt for {origin}", attempts=attempts)

            if policy.crawl_delay is not None and policy.crawl_delay > self.max_crawl_delay:
                return FetchResult(HTTP_ERROR, url, current, reason=f"Crawl-delay {policy.crawl_delay:.0f}s exceeds cap {self.max_crawl_delay:.0f}s", attempts=attempts)

            headers = {"User-Agent": self.user_agent, "Accept": "*/*"}
            cached = self.cache.get(url)
            if not isinstance(cached, dict) or current != cached.get("final_url", url):
                cached = None  # validators belong to the resource they came from
            if cached:
                if cached.get("etag"):
                    headers["If-None-Match"] = cached["etag"]
                if cached.get("last_modified"):
                    headers["If-Modified-Since"] = cached["last_modified"]

            attempts += 1
            try:
                resp = self._spaced_request(current, headers, self._delay_for(policy))
            except ValueError as e:
                return FetchResult(HTTP_ERROR, url, current, reason=f"invalid request/response: {e}", attempts=attempts)
            except OSError as e:
                if retries < self.max_retries:
                    self._sleep(self.backoff_base * (2**retries))
                    retries += 1
                    continue
                return FetchResult(HTTP_ERROR, url, current, reason=f"network error: {e}", attempts=attempts)

            if resp.status in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                nxt = urljoin(current, resp.headers["location"])
                if urlsplit(nxt).scheme not in ("http", "https"):
                    return FetchResult(HTTP_ERROR, url, current, resp.status, reason=f"redirect to non-HTTP target {nxt[:80]!r}", attempts=attempts)
                if self._is_sso_redirect(nxt) and not self._is_sso_redirect(current):
                    return FetchResult(LOGIN_OR_CAPTCHA, url, nxt, resp.status, reason="redirect to login/SSO host", attempts=attempts)
                redirects += 1
                if redirects > MAX_REDIRECTS:
                    return FetchResult(HTTP_ERROR, url, current, resp.status, reason="too many redirects", attempts=attempts)
                current = nxt
                continue

            if self._is_challenge(resp):
                return FetchResult(LOGIN_OR_CAPTCHA, url, current, resp.status, headers=resp.headers, reason="login or CAPTCHA challenge; not retried", attempts=attempts)

            if resp.status == 304:
                c = cached or {}
                return FetchResult(NOT_MODIFIED, url, current, 304, headers=resp.headers, etag=c.get("etag"), last_modified=c.get("last_modified"), attempts=attempts)

            if 200 <= resp.status < 300:
                etag, lm = resp.headers.get("etag"), resp.headers.get("last-modified")
                if etag or lm:
                    self._remember(url, {"etag": etag, "last_modified": lm, "final_url": current})
                return FetchResult(OK, url, current, resp.status, resp.body, resp.headers, etag, lm, attempts=attempts)

            if resp.status in (429, 500, 502, 503, 504):
                if retries >= self.max_retries:
                    return FetchResult(HTTP_ERROR, url, current, resp.status, headers=resp.headers, reason="retries exhausted", attempts=attempts)
                ra = parse_retry_after(resp.headers.get("retry-after"), self._clock())
                if ra is not None and ra > self.max_retry_after:
                    return FetchResult(HTTP_ERROR, url, current, resp.status, headers=resp.headers, reason=f"Retry-After {ra:.0f}s exceeds cap", attempts=attempts)
                self._sleep(ra if ra is not None else self.backoff_base * (2**retries))
                retries += 1
                continue

            return FetchResult(HTTP_ERROR, url, current, resp.status, resp.body, resp.headers, reason=f"HTTP {resp.status}", attempts=attempts)
