#!/usr/bin/env python3
"""Probe URL patterns to discover which schools actually publish a CDS online.

For each school in schools.yaml with scrape_policy == "unknown", tries the
URL pattern ladder against the school's domain. On a hit, updates the entry
with discovery_seed_url and flips scrape_policy to "active" only when the
UNITID exists in the IPEDS identity snapshot (otherwise CI fails closed).

Records probe_state per school so we don't re-query paid search APIs for
schools that genuinely don't publish.

Dependencies: pyyaml (stdlib otherwise)

Usage:
    # Pass 1 — pattern ladder only (free, no API key needed)
    python probe_urls.py

    # Pass 2 — search fallback for remaining unknowns
    #   Bing HTML scraping (free, no key):
    python probe_urls.py --search-only --bing-fallback
    #   Brave Search API ($0, free tier 2k/month, needs BRAVE_API_KEY):
    python probe_urls.py --search-only --brave-fallback

    # Other options
    python probe_urls.py --only yale           # single school
    python probe_urls.py --dry-run             # don't write schools.yaml
    python probe_urls.py --rps 2               # faster rate limit
    python probe_urls.py --limit 50            # cap number of schools
    python probe_urls.py --cooldown-days 0     # ignore probe_state cooldown
"""
from __future__ import annotations

import argparse
import html.parser
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from collections import defaultdict
from typing import Callable

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from tools.finder.identity_guard import (  # noqa: E402
    DEFAULT_SNAPSHOT,
    load_identity_snapshot,
    normalize_ipeds,
)
from tools.finder.stuck_pdf_seeds import (  # noqa: E402
    choose_canonical_school,
    is_direct_doc_seed,
)

ROOT = Path(__file__).parent
SCHOOLS_YAML = ROOT / "schools.yaml"

# ── Config ──────────────────────────────────────────────────────────────────

_UA = "collegedata-fyi-finder/0.1 (https://github.com/bolewood/collegedata-fyi)"

# Lenient SSL context — some school sites have dodgy certs
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# URL pattern ladder — ordered roughly by observed frequency.
# Expanded 2026-04-14 after a 50-school dry run returned 1/50 hits,
# with hand-verification showing real CDS pages at patterns we were
# not checking. See the three categories below for what was added.
PATTERNS = [
    # ── Common IR patterns ──
    "/ir/cds/",
    "/institutional-research/common-data-set/",
    "/institutional-research/common-data-set.html",
    "/institutionalresearch/common-data-set/",           # no-hyphen variant (Agnes Scott)
    "/institutionalresearch/common-data-set.html",       # no-hyphen + .html
    "/ir/common-data-set/",                              # spelled-out "common-data-set" under /ir
    "/oir/cds/",
    "/oir/common-data-set/",
    "/ira/cds/",                                         # Carnegie Mellon pattern
    "/common-data-set/",

    # ── Institutional Effectiveness variants ──
    # Several schools file CDS under IE rather than IR (e.g. Allegheny).
    "/institutional-effectiveness/common-data-set/",
    "/institutional-effectiveness/common-data-set.html",
    "/institutional-effectiveness/the-common-data-set/",  # with article prefix
    "/ie/cds/",
    "/oie/cds/",

    # ── Nested under /about/ or /provost/ or /planning/ ──
    "/about/institutional-research/common-data-set/",
    "/about/ir/cds/",
    "/provost/institutional-research/common-data-set/",
    "/provost/oira/common-data-set/",                    # American University
    "/provost/oira/common-data-set.cfm",                 # American U uses ColdFusion
    "/provost/oir/common-data-set/",
    "/provost/oir/common-data-set.cfm",
    "/planning/institutional-research/common-data-set/",

    # ── Facts-and-figures style ──
    "/facts-and-figures/common-data-set/",

    # ── Generic "data" page (for schools like Adelphi whose CDS is
    #    linked from a data hub with no CDS keyword in the path) ──
    "/institutional-research/research/data/",

    # ── IR "other reports" hubs ──
    # Oklahoma (ou.edu/irr/other-reports) posts CDS on a mixed-reports
    # page, not under /ir/cds/. The CDS heading is below the fold.
    "/irr/other-reports",
    "/irr/other-reports/",
    "/irr/common-data-set/",
    "/institutional-research/reports/",
    "/ir/reports/",
    "/iea/university-data",
    "/iea/university-data/",
]

# Subdomains to try. `sites` catches Wordpress-multisite institutions
# like Allegheny (sites.allegheny.edu/institutional-effectiveness/...).
# `oair` catches Tulane (oair.tulane.edu/common-data-set), and is a
# common IR office abbreviation (Office of Assessment and Institutional
# Research).
SUBDOMAINS = ["www", "ir", "oir", "oair", "oira", "irds", "obp", "ira", "sites"]

# Current CDS years to search for (newest first)
CDS_YEARS = ["2025-2026", "2024-2025", "2023-2024"]

# Default cooldown: skip schools probed within this many days
DEFAULT_COOLDOWN_DAYS = 30

# Per-school wall-clock budget for the pattern ladder. Caps the blast
# radius when a base URL accepts TCP but never responds. 60s is enough
# for a fully-live school to probe ~60 URLs at the default 1 rps cadence
# while keeping monthly cron runtime bounded at 2400 schools × 60s / workers.
DEFAULT_SCHOOL_BUDGET_SEC = 60.0

# Search hits and active HTML seeds are untrusted URLs. One MiB is enough to
# inspect a landing page and document magic without downloading a whole CDS.
MAX_VALIDATION_BYTES = 1024 * 1024
VALIDATION_VALID = "valid"
VALIDATION_INVALID = "invalid"
VALIDATION_UNVERIFIABLE = "unverifiable"
TERMINAL_ARCHIVE_STATUSES = {"done", "failed_permanent"}
AUDITABLE_ARCHIVE_OUTCOMES = {
    "dead_url",
    "marked_removed",
    "no_pdfs_found",
    "wrong_content_type",
}
ACTIVE_HTML_AUDIT_LOOKBACK_DAYS = 180


# ── HTTP helpers ────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 10, read_bytes: int = 0,
         extra_headers: dict | None = None) -> tuple[int, dict, bytes]:
    """GET a URL. Returns (status, headers_dict, body_bytes).

    If read_bytes > 0, only reads that many bytes (for content sniffing).
    Returns (-1, {}, b"") on any network/timeout error.
    """
    hdrs = {"User-Agent": _UA}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            status = resp.status
            headers = {k.lower(): v for k, v in resp.getheaders()}
            body = resp.read(read_bytes) if read_bytes else b""
            return status, headers, body
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return -1, {}, b""


def _get_full(url: str, timeout: int = 10,
              extra_headers: dict | None = None) -> tuple[int, dict, bytes]:
    """GET a URL and read the full body. For API/search responses.

    Transparently decompresses gzip responses. Callers that send
    `Accept-Encoding: gzip` (Brave API does) would otherwise see
    raw gzip bytes where they expect text/JSON and silently fail.
    """
    hdrs = {"User-Agent": _UA}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            status = resp.status
            headers = {k.lower(): v for k, v in resp.getheaders()}
            body = resp.read()
            if headers.get("content-encoding", "").lower() == "gzip":
                import gzip
                body = gzip.decompress(body)
            return status, headers, body
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return -1, {}, b""


def _head(url: str, timeout: int = 10) -> tuple[int, dict]:
    """HEAD a URL. Returns (status, headers_dict)."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            headers = {k.lower(): v for k, v in resp.getheaders()}
            return resp.status, headers
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return -1, {}


def _get_bounded(
    url: str,
    timeout: int = 15,
    max_bytes: int = MAX_VALIDATION_BYTES,
) -> tuple[int, dict, bytes, str, bool]:
    """Fetch at most max_bytes for content validation.

    Unlike `_get`, HTTP status is preserved. Callers must distinguish a
    definitive miss (404/410 or successful non-CDS content) from a transient
    or access-controlled response that cannot safely demote an existing seed.
    """
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            status = resp.status
            headers = {k.lower(): v for k, v in resp.getheaders()}
            content = bytearray()
            read = getattr(resp, "read1", resp.read)
            while len(content) <= max_bytes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("validation fetch deadline exceeded")
                try:
                    resp.fp.raw._sock.settimeout(remaining)
                except (AttributeError, OSError):
                    pass
                chunk = read(min(64 * 1024, max_bytes + 1 - len(content)))
                if not chunk:
                    break
                content.extend(chunk)
            return (
                status,
                headers,
                bytes(content[:max_bytes]),
                resp.geturl(),
                len(content) > max_bytes,
            )
    except urllib.error.HTTPError as exc:
        headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return exc.code, headers, b"", exc.geturl() or url, False
    except (urllib.error.URLError, OSError, ValueError):
        return -1, {}, b"", url, False


class _CdsContentParser(html.parser.HTMLParser):
    """Collect link targets and text without executing untrusted HTML."""

    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_link: int | None = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        target = ""
        if tag == "a":
            target = values.get("href", "")
        elif tag in {"embed", "iframe", "source"}:
            target = values.get("src", "")
        elif tag == "object":
            target = values.get("data", "")
        if target:
            self.links.append((target, ""))
            self._current_link = len(self.links) - 1 if tag == "a" else None

    def handle_endtag(self, tag):
        if tag == "a":
            self._current_link = None

    def handle_data(self, data):
        if self._current_link is None:
            return
        target, text = self.links[self._current_link]
        self.links[self._current_link] = (target, text + " " + data)


def html_has_cds_content_or_anchors(content: bytes) -> bool:
    """Require real CDS content or a CDS/document link, not snippet text."""
    text = content.decode("utf-8", errors="ignore")
    normalized = re.sub(r"\s+", " ", text).lower()
    has_cds_phrase = bool(re.search(r"common\s+data\s+set", normalized))

    parser = _CdsContentParser()
    try:
        parser.feed(text)
    except (AssertionError, ValueError):
        return False

    for target, label in parser.links:
        combined = urllib.parse.unquote(f"{target} {label}").lower()
        path = urllib.parse.unquote(urllib.parse.urlparse(target).path).lower()
        is_document = bool(re.search(r"\.(pdf|xlsx|docx)(?:$|[?#])", path))
        cds_signal = bool(re.search(r"(?:\bcds\b|common[-_\s]*data[-_\s]*set)", combined))
        year_signal = bool(re.search(r"20\d{2}\s*[-–_]\s*(?:20)?\d{2}", combined))
        contextual_target = bool(
            re.search(
                (
                    r"(?:\bcds\b|common[-_]?data[-_]?set)"
                    r"[-_/\s]*(?:committee|definition|faq|glossary|overview|policy)"
                    r"(?:[-_/\s]|$)"
                ),
                combined,
            )
        )
        if (
            cds_signal
            and not contextual_target
            and target
            and not target.startswith("#")
        ):
            return True
        if is_document:
            if has_cds_phrase and year_signal:
                return True

    # A CDS can itself be HTML rather than a landing page. Require multiple
    # canonical form signals so an IR mission page mentioning CDS in navigation
    # does not qualify as the dataset.
    form_signals = sum(
        marker in normalized
        for marker in (
            "first-time, first-year",
            "first time, first year",
            "applicants",
            "enrolled",
            "tuition",
            "degrees conferred",
        )
    )
    return has_cds_phrase and form_signals >= 3


def validate_cds_url(url: str) -> tuple[str, str]:
    """Return (valid|invalid|unverifiable, reason) for a fetched URL."""
    status, headers, body, final_url, truncated = _get_bounded(url)
    if status < 0:
        return VALIDATION_UNVERIFIABLE, "network_error"
    if status in {401, 403, 405, 408, 425, 429} or status >= 500:
        return VALIDATION_UNVERIFIABLE, f"http_{status}"
    if status < 200 or status >= 300:
        return VALIDATION_INVALID, f"http_{status}"

    content_type = headers.get("content-type", "").lower()
    stripped = body.lstrip()
    final_path = urllib.parse.urlparse(final_url).path.lower()
    if stripped.startswith(b"%PDF-"):
        return VALIDATION_VALID, "pdf_magic"
    if stripped.startswith(b"PK\x03\x04") and (
        re.search(r"\.(xlsx|docx)$", final_path)
        or "spreadsheet" in content_type
        or "wordprocessingml" in content_type
    ):
        return VALIDATION_VALID, "office_magic"

    looks_html = "html" in content_type or bool(
        re.search(br"(?is)<!doctype\s+html|<html(?:\s|>)", body[:4096])
    )
    if looks_html:
        if looks_like_news_or_blog(final_url):
            return VALIDATION_INVALID, "contextual_page_path"
        if html_has_cds_content_or_anchors(body):
            return VALIDATION_VALID, "html_cds"
        if truncated:
            return VALIDATION_UNVERIFIABLE, "html_validation_window_exhausted"
        return VALIDATION_INVALID, "html_without_cds_content_or_anchors"
    return VALIDATION_INVALID, "unsupported_content"


def is_cds_page(content: bytes, content_type: str) -> bool:
    """Check if response content looks like a CDS page or PDF."""
    ct = content_type.lower()
    if "pdf" in ct:
        return True
    if "html" in ct:
        # OU's /irr/other-reports puts the CDS heading ~8KB into the page,
        # below Facts-at-a-Glance. 5KB was enough for dedicated CDS pages
        # and missed mixed IR hubs.
        text = content[:32_000].decode("utf-8", errors="ignore").lower()
        return "common data set" in text
    return False


# ── DNS short-circuit (skip bases whose hostname doesn't resolve) ──────────
# Most schools don't have `sites.X.edu`, `oira.X.edu`, `irds.X.edu`, etc.
# Probing those subdomains hits a TCP/SSL timeout which is slow. A cheap
# DNS lookup (~100ms for NXDOMAIN) lets us skip entire bases that don't
# exist. Results are cached per-session so the same host is only resolved
# once even if multiple workers probe schools on the same domain.

_dns_cache: dict[str, bool] = {}
_dns_cache_lock = Lock()


def _dns_ok(host: str) -> bool:
    """Return True if `host` resolves in DNS. Cached per-session."""
    with _dns_cache_lock:
        cached = _dns_cache.get(host)
    if cached is not None:
        return cached
    try:
        socket.gethostbyname(host)
        ok = True
    except (socket.gaierror, socket.herror, OSError):
        ok = False
    with _dns_cache_lock:
        _dns_cache[host] = ok
    return ok


# ── probe_state helpers ─────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_since(iso_str: str) -> float:
    """Days elapsed since an ISO timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except (ValueError, TypeError):
        return 999  # treat unparseable as "very old"


def should_skip(school: dict, cooldown_days: float, *, reprobe_found: bool = False) -> bool:
    """Return True if this school should not be probed this run.

    `last_result: found` used to skip forever — that froze PDF seeds in
    place (OU). Re-probe runs pass reprobe_found=True. Satellite campuses
    that inherited a sibling's URL stay skipped until an operator
    explicitly includes them.
    """
    ps = school.get("probe_state")
    if not ps:
        return False
    last = ps.get("last_result")
    if last == "shared_parent_seed" and not reprobe_found:
        return True
    if last == "found" and not reprobe_found:
        return True
    probed_at = ps.get("last_probed_at", "")
    return _days_since(probed_at) < cooldown_days


def should_replace_seed(existing: str | None, new: str | None) -> bool:
    """Listing pages replace year-specific PDFs; PDFs do not replace listings."""
    if not new:
        return False
    if not existing:
        return True
    existing_doc = is_direct_doc_seed(existing)
    new_doc = is_direct_doc_seed(new)
    if existing_doc and not new_doc:
        return True
    if not existing_doc:
        return False
    return False


def clear_shared_parent_seed(school: dict, keeper_id: str) -> None:
    school.pop("discovery_seed_url", None)
    school.pop("cds_url_hint", None)
    school["scrape_policy"] = "unknown"
    record_probe(school, "shared_parent_seed", "shared_parent", 0, False)
    note = (
        f"Cleared identical seed also assigned to {keeper_id}; "
        "Brave site:domain search is not campus-specific."
    )
    existing = school.get("notes") or ""
    if note not in existing:
        school["notes"] = f"{existing} {note}".strip() if existing else note


def dedupe_identical_seeds(schools: list[dict]) -> list[tuple[str, str]]:
    """Keep one owner per identical discovery_seed_url; clear the rest."""
    by_url: dict[str, list[dict]] = defaultdict(list)
    for school in schools:
        seed = school.get("discovery_seed_url") or ""
        if seed:
            by_url[seed].append(school)
    cleared: list[tuple[str, str]] = []
    for _url, group in by_url.items():
        if len(group) < 2:
            continue
        keeper = choose_canonical_school(group)
        for school in group:
            if school.get("id") == keeper.get("id"):
                continue
            clear_shared_parent_seed(school, keeper.get("id") or "")
            cleared.append((school.get("id") or "", keeper.get("id") or ""))
    return cleared


def record_probe(school: dict, result: str, method: str,
                 patterns_tried: int = 0, search_tried: bool = False):
    """Write probe_state into the school dict."""
    ps = school.get("probe_state", {})
    ps["last_probed_at"] = _now_iso()
    ps["last_result"] = result         # "found" or "not_found"
    ps["last_method"] = method         # "pattern", "bing_html", "brave", "google"
    ps["patterns_tried"] = patterns_tried
    ps["search_fallback_tried"] = search_tried or ps.get("search_fallback_tried", False)
    school["probe_state"] = ps


# ── Pattern ladder ──────────────────────────────────────────────────────────

def probe_school(domain: str, rps: float, max_seconds: float = DEFAULT_SCHOOL_BUDGET_SEC) -> tuple[str | None, int]:
    """Try URL patterns against a domain.

    Returns (first_working_url_or_None, patterns_tried_count).

    Uses a DNS short-circuit: before probing any base, we check whether
    the hostname resolves at all. Bases that return NXDOMAIN are skipped
    entirely, which saves ~150 probes per school for the common case of
    schools that only have www.X.edu and maybe ir.X.edu live. DNS
    results are cached per-session via `_dns_ok`.

    `max_seconds` is a per-school wall-clock budget. When a base URL
    accepts TCP but never responds, the per-URL timeout (10s) stacks
    across ~200 pattern combinations and a single school can wedge a
    worker for ~33 minutes. The deadline check short-circuits pattern
    probing once the budget is exhausted and returns whatever we have.
    """
    if not domain:
        return None, 0

    start = time.monotonic()
    def deadline_exceeded() -> bool:
        return (time.monotonic() - start) >= max_seconds

    candidate_bases = [f"https://{domain}"]
    for sub in SUBDOMAINS:
        candidate_bases.append(f"https://{sub}.{domain}")

    # Filter to bases whose host actually resolves. This is the main
    # speedup vs the naive approach of HTTP-probing every base.
    live_bases = []
    for base in candidate_bases:
        host = base.replace("https://", "").split("/")[0]
        if _dns_ok(host):
            live_bases.append(base)

    delay = 1.0 / rps if rps > 0 else 1.0
    tried = 0

    for base in live_bases:
        if deadline_exceeded():
            return None, tried
        for pattern in PATTERNS:
            if deadline_exceeded():
                return None, tried
            url = base.rstrip("/") + pattern
            tried += 1
            status, headers, body = _get(url, timeout=10, read_bytes=32_000)
            if status == 200:
                ct = headers.get("content-type", "")
                if is_cds_page(body, ct):
                    return url, tried
            time.sleep(delay)

    # Year-specific PDF patterns (only against naked + www, which almost
    # always resolve, so no DNS check needed here).
    for base in [f"https://{domain}", f"https://www.{domain}"]:
        if deadline_exceeded():
            return None, tried
        host = base.replace("https://", "").split("/")[0]
        if not _dns_ok(host):
            continue
        for year in CDS_YEARS:
            if deadline_exceeded():
                return None, tried
            pdf_patterns = [
                f"/ir/cds/CDS_{year}.pdf",
                f"/ir/cds/cds_{year}.pdf",
                f"/ir/CDS-{year}.pdf",
                f"/institutional-research/CDS-{year}.pdf",
                f"/common-data-set/CDS_{year}.pdf",
            ]
            for pat in pdf_patterns:
                if deadline_exceeded():
                    return None, tried
                url = base.rstrip("/") + pat
                tried += 1
                status, headers = _head(url, timeout=10)
                if status == 200:
                    ct = headers.get("content-type", "")
                    if "pdf" in ct.lower():
                        return url, tried
                time.sleep(delay)

    return None, tried


# ── Search fallbacks ────────────────────────────────────────────────────────

class _BingResultParser(html.parser.HTMLParser):
    """Extract result URLs from Bing search HTML."""

    def __init__(self):
        super().__init__()
        self.urls: list[str] = []
        self._in_result = False

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            d = dict(attrs)
            href = d.get("href", "")
            # Bing result links start with http and aren't bing.com internal
            if href.startswith("http") and "bing.com" not in href:
                self.urls.append(href)


def bing_html_search(domain: str) -> str | None:
    """Scrape Bing search results HTML for CDS PDFs.

    Free, no API key. Uses a realistic browser User-Agent to avoid
    CAPTCHA. May break if Bing changes their HTML structure.
    """
    query = f'site:{domain} filetype:pdf "Common Data Set"'
    params = urllib.parse.urlencode({"q": query})
    url = f"https://www.bing.com/search?{params}"

    # Use a browser-like User-Agent for HTML scraping
    browser_ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    status, headers, body = _get_full(url, timeout=15,
                                       extra_headers={"User-Agent": browser_ua})
    if status != 200:
        return None

    text = body.decode("utf-8", errors="ignore")

    # Strategy 1: look for PDF URLs in the HTML
    pdf_urls = re.findall(r'https?://[^\s"<>]+\.pdf', text, re.IGNORECASE)
    for purl in pdf_urls:
        # Filter to the target domain
        if domain in purl.lower():
            return purl

    # Strategy 2: parse <a> tags and look for CDS-related links
    parser = _BingResultParser()
    parser.feed(text)
    for result_url in parser.urls:
        lower = result_url.lower()
        if domain in lower and ("common-data" in lower or "cds" in lower):
            return result_url

    return None


def brave_search(domain: str, api_key: str, tracker: dict | None = None) -> str | None:
    """Use Brave Search API to find CDS PDFs for a school.

    Free tier: 2,000 queries/month. Paid: $0.003/query.
    Independent index, no domain pre-registration.
    """
    if tracker is not None:
        with tracker["lock"]:
            budget = tracker.get("budget")
            if budget is not None and tracker["calls"] >= budget:
                print("  [brave] budget exhausted — skipping remaining queries", flush=True)
                return None
            tracker["calls"] += 1
    # NOTE: do not add `filetype:pdf` here. Many schools publish CDS as an
    # HTML landing page (oair.tulane.edu/common-data-set) or a .cfm page
    # (american.edu/provost/oira/common-data-set.cfm), not a raw PDF.
    # Hand-verified via Brave web UI on 2026-04-14: the filetype restriction
    # returned 0 hits for Tulane while the un-restricted query returned the
    # live landing page as result #1. The overnight $5 Brave run burned
    # quota for 0 finds because of this one word.
    query = f'site:{domain} "Common Data Set"'
    params = urllib.parse.urlencode({"q": query, "count": 10})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"

    status, headers, body = _get_full(
        url, timeout=15,
        extra_headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        },
    )
    if status != 200:
        # Surface quota exhaustion (402) and rate limiting (429) instead
        # of silently returning None like the previous version did.
        if status in (402, 429):
            print(f"  [brave] HTTP {status} — quota/rate limit hit", flush=True)
        return None

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None

    results = data.get("web", {}).get("results", [])
    for candidate in brave_cds_candidates(results, domain):
        validation, _reason = validate_cds_url(candidate)
        if validation == VALIDATION_VALID:
            return candidate
    return None


def host_belongs_to_domain(url: str, domain: str) -> bool:
    """True when the URL is on the school's own host, not a random search hit."""
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    domain = domain.lower().removeprefix("www.")
    if not host or not domain:
        return False
    return host == domain or host.endswith("." + domain)


def looks_like_search_junk(url: str) -> bool:
    """Brave sometimes returns rewritten search-result URLs, not IR pages."""
    path = (urllib.parse.urlparse(url).path or "").lower()
    return "+" in path and "common+data" in path


def looks_like_article_slug(url: str) -> bool:
    """Drop SEO/blog slugs that matched 'Common Data Set' in a snippet."""
    parts = [p for p in (urllib.parse.urlparse(url).path or "").lower().split("/") if p]
    # Brave hits often append a page index ("/does-harvard-accept-2-9-gpa/5/").
    while parts and re.fullmatch(r"\d+", parts[-1]):
        parts.pop()
    if not parts:
        return False
    last = parts[-1]
    if re.search(r"cds|common[-_]?data", last):
        return False
    if re.match(r"^(does|what|why|how|should|is|can|will)-", last):
        return True
    return last.count("-") >= 5


def may_mark_active(
    school: dict,
    official_records: dict[str, dict[str, str]] | None,
) -> bool:
    """Refuse scrape_policy=active when identity_guard would fail CI.

    Missing UNITIDs are warnings while the school stays unknown. Flipping
    them to active (the Sept 2 Continents States Brave miss) turns the
    next seed PR red.
    """
    if official_records is None:
        return True
    ipeds_id = normalize_ipeds(school.get("ipeds_id"))
    return bool(ipeds_id and ipeds_id in official_records)


def looks_like_news_or_blog(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = (parsed.path or "").lower()
    if re.search(
        r"/(news|blog|stories|noteworthy|careers?|jobs?|oldstudents)(?:[-_/]|$)",
        path,
    ):
        return True
    if re.search(r"(?:^|[-_/])thesis(?:[-_./]|$)", path):
        return True
    return "page=" in (parsed.query or "").lower()


def looks_like_non_cds_document(url: str) -> bool:
    """A PDF/XLSX/DOCX whose filename does not mention CDS is usually a miss."""
    path = (urllib.parse.urlparse(url).path or "").lower()
    if not re.search(r"\.(pdf|xlsx|docx)$", path):
        return False
    return not re.search(r"cds|common[-_]?data", path)


def brave_cds_candidates(results: list[dict], domain: str | None = None) -> list[str]:
    """Return plausible Brave candidates in listing-before-document order.

    Prefer an HTML listing over a year-specific PDF. A PDF seed locks the
    archive resolver onto one file — OU's 2023-24 Combined.pdf instead of
    ou.edu/irr/other-reports, which lists every year plus section PDFs.
    Landing pages still have to mention "Common Data Set" in title or
    description so random IR homepages do not win.

    Reject URL paths that look like the CDS Initiative's template /
    definitions / instructions documents rather than a school's filled-out
    data. Filter added 2026-04-14 after Amherst's hint turned out to be
    the definitions PDF.
    """
    bad_keywords = ("definition", "definitions", "template", "instructions",
                    "blank", "glossary")

    def looks_like_template(url_str: str) -> bool:
        p = url_str.lower()
        return any(kw in p for kw in bad_keywords)

    landing: list[str] = []
    documents: list[str] = []
    seen: set[str] = set()
    for r in results:
        link = r.get("url", "")
        if not link or link in seen or looks_like_template(link):
            continue
        if looks_like_search_junk(link):
            continue
        if looks_like_article_slug(link) or looks_like_news_or_blog(link):
            continue
        if looks_like_non_cds_document(link):
            continue
        if domain and not host_belongs_to_domain(link, domain):
            continue
        seen.add(link)
        if link.lower().endswith(".pdf"):
            documents.append(link)
            continue
        desc = r.get("description", "").lower()
        title = r.get("title", "").lower()
        if "common data set" in desc or "common data set" in title:
            landing.append(link)
    return landing + documents


def select_brave_cds_url(results: list[dict], domain: str | None = None) -> str | None:
    """Return the first syntactically plausible Brave candidate.

    Production discovery uses `brave_search`, which bounded-fetches every
    candidate and continues through alternatives. This helper stays useful for
    diagnostics that only inspect Brave ranking.
    """
    candidates = brave_cds_candidates(results, domain)
    return candidates[0] if candidates else None


def google_dork(domain: str, api_key: str, cx: str) -> str | None:
    """Use Google Custom Search API to find CDS PDFs for a school."""
    query = f'site:{domain} filetype:pdf "Common Data Set"'
    params = urllib.parse.urlencode({"key": api_key, "cx": cx, "q": query, "num": 3})
    url = f"https://www.googleapis.com/customsearch/v1?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read())
            for item in data.get("items", []):
                link = item.get("link", "")
                if link.lower().endswith(".pdf"):
                    return link
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        pass
    return None


# ── Per-school worker ──────────────────────────────────────────────────────

def process_school(school: dict, args: argparse.Namespace,
                   env: dict) -> dict:
    """Probe a single school. Mutates `school` in place when a hit is found.

    This function is the threadpool worker. It must be thread-safe: it
    mutates the school dict it was given (different workers receive
    different dicts, so no contention), and it only reads from module-
    level state that's already thread-safe (PATTERNS, SUBDOMAINS,
    _SSL_CTX, _dns_cache with lock).

    Returns a result dict with keys: name, domain, url (or None), method,
    patterns_tried, search_tried.
    """
    domain = school.get("domain", "")
    name = school.get("name", school.get("id", ""))

    url = None
    method = "pattern"
    last_attempted_method = "pattern"
    patterns_tried = 0
    search_tried = False

    # Step 1: Pattern ladder
    if not args.search_only:
        url, patterns_tried = probe_school(domain, args.rps, args.school_budget_sec)

    # Step 2: Bing HTML scraping (free)
    if not url and args.bing_fallback:
        search_tried = True
        last_attempted_method = "bing_html"
        url = bing_html_search(domain)
        if url:
            method = "bing_html"
        time.sleep(1.0)  # polite pause between Bing scrapes

    # Step 3: Brave Search API (free tier / cheap)
    if not url and args.brave_fallback and env.get("brave_api_key"):
        search_tried = True
        last_attempted_method = "brave"
        url = brave_search(domain, env["brave_api_key"], env.get("brave_tracker"))
        if url:
            method = "brave"
        time.sleep(0.5)

    # Step 4: Google CSE (legacy, limited)
    if not url and args.google_fallback and env.get("google_api_key") and env.get("google_cx"):
        search_tried = True
        last_attempted_method = "google"
        url = google_dork(domain, env["google_api_key"], env["google_cx"])
        if url:
            method = "google"

    # Telemetry: when a search fallback was attempted and failed, record
    # the LAST attempted method so probe_state.last_method reflects what
    # was actually tried — not the default "pattern". Otherwise you can't
    # tell from schools.yaml which not-found schools were Brave-tried vs
    # pattern-only-tried, which matters for cooldown decisions and for
    # knowing whether to re-try with a different fallback next run.
    if not url and search_tried:
        method = last_attempted_method

    replaced = False
    official_records = env.get("official_records")
    if url and not may_mark_active(school, official_records):
        print(
            f"  skip activate {school.get('id')}: UNITID "
            f"{school.get('ipeds_id')} is not in the IPEDS identity snapshot",
            file=sys.stderr,
        )
        url = None
        method = last_attempted_method if search_tried else method
    if url:
        existing = school.get("discovery_seed_url") or school.get("cds_url_hint")
        if should_replace_seed(existing, url):
            replaced = True
            if not args.dry_run:
                school["discovery_seed_url"] = url
                school["scrape_policy"] = "active"
        if not args.dry_run:
            record_probe(school, "found", method, patterns_tried, search_tried)
    else:
        if not args.dry_run:
            record_probe(school, "not_found", method, patterns_tried, search_tried)

    return {
        "name": name,
        "domain": domain,
        "url": url,
        "method": method,
        "patterns_tried": patterns_tried,
        "search_tried": search_tried,
        "replaced": replaced,
    }


def _chunks(values: list[str], size: int = 100) -> list[list[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def fetch_latest_terminal_archive_rows(
    schools: list[dict],
    *,
    supabase_url: str,
    service_role_key: str,
) -> list[dict]:
    """Read bounded latest terminal outcomes for active HTML seeds.

    The existing RPC is index-backed and returns one terminal row per school.
    Active queue rows are excluded so an old terminal result cannot demote a
    seed while a newer attempt is ready or processing.
    """
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("supabase package is required for --audit-active-html") from exc

    school_ids = [
        str(school.get("id"))
        for school in schools
        if school.get("id")
        and school.get("scrape_policy") == "active"
        and (school.get("discovery_seed_url") or school.get("cds_url_hint"))
        and not is_direct_doc_seed(
            school.get("discovery_seed_url") or school.get("cds_url_hint")
        )
    ]
    if not school_ids:
        return []

    sb = create_client(supabase_url, service_role_key)
    since = (
        datetime.now(timezone.utc)
        - timedelta(days=ACTIVE_HTML_AUDIT_LOOKBACK_DAYS)
    ).isoformat()
    terminal_rows: list[dict] = []
    for ids in _chunks(school_ids):
        terminal = sb.rpc(
            "latest_archive_terminal_rows",
            {
                "p_since": since,
                "p_school_ids": ids,
            },
        ).execute()
        for row in terminal.data or []:
            terminal_rows.append(dict(row))

    return [
        row
        for row in terminal_rows
        if not row.get("active_work")
        and row.get("last_outcome") in AUDITABLE_ARCHIVE_OUTCOMES
        and row.get("status") in TERMINAL_ARCHIVE_STATUSES
        and row.get("cds_url_hint")
    ]


def fetch_active_archive_school_ids(
    school_ids: list[str],
    *,
    supabase_url: str,
    service_role_key: str,
) -> set[str]:
    """Recheck active work in bulk immediately before seed mutation."""
    if not school_ids:
        return set()
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("supabase package is required for active-work recheck") from exc

    sb = create_client(supabase_url, service_role_key)
    active_ids: set[str] = set()
    for ids in _chunks(list(dict.fromkeys(school_ids))):
        active = (
            sb.table("archive_queue")
            .select("school_id")
            .in_("school_id", ids)
            .in_("status", ["ready", "processing"])
            .execute()
        )
        active_ids.update(
            str(row.get("school_id"))
            for row in active.data or []
            if row.get("school_id")
        )
    return active_ids


def audit_active_html_seeds(
    schools: list[dict],
    archive_rows: list[dict],
    *,
    dry_run: bool = False,
    workers: int = 8,
    active_recheck: Callable[[list[str]], set[str]] | None = None,
) -> list[dict]:
    """Demote definitively invalid active HTML seeds after archive failure.

    Network errors, 403/405, rate limits, and 5xx responses are unverifiable
    and never remove a seed. The latest archive result is a second independent
    gate, limiting the monthly audit to seeds the archive pipeline already
    classified as a terminal URL/content miss.
    """
    latest: dict[str, dict] = {}
    for row in archive_rows:
        sid = str(row.get("school_id") or "")
        if not sid:
            continue
        previous = latest.get(sid)
        if previous is None or str(row.get("processed_at") or "") > str(
            previous.get("processed_at") or ""
        ):
            latest[sid] = row

    candidates: list[tuple[dict, str, str, dict]] = []
    for school in schools:
        sid = str(school.get("id") or "")
        seed = school.get("discovery_seed_url") or school.get("cds_url_hint") or ""
        row = latest.get(sid)
        if (
            school.get("scrape_policy") != "active"
            or not seed
            or is_direct_doc_seed(seed)
            or row is None
            or row.get("status") not in TERMINAL_ARCHIVE_STATUSES
            or row.get("last_outcome") not in AUDITABLE_ARCHIVE_OUTCOMES
            or str(row.get("cds_url_hint") or "").strip() != seed.strip()
        ):
            continue
        candidates.append((school, sid, seed, row))

    if not candidates:
        return []

    # Each validation has a bounded network timeout. Parallel validation keeps
    # the monthly audit's worst case below the workflow deadline even if every
    # active school is slow, while mutation remains serial and deterministic.
    with ThreadPoolExecutor(
        max_workers=max(1, min(workers, len(candidates)))
    ) as executor:
        validations = executor.map(
            validate_cds_url,
            (seed for _school, _sid, seed, _row in candidates),
        )

    audited: list[tuple[dict, dict]] = []
    for (school, sid, seed, row), (validation, reason) in zip(
        candidates,
        validations,
    ):
        result = {
            "school_id": sid,
            "url": seed,
            "archive_outcome": row.get("last_outcome"),
            "validation": validation,
            "reason": reason,
            "demoted": validation == VALIDATION_INVALID,
        }
        audited.append((school, result))

    invalid_ids = [
        str(result["school_id"])
        for _school, result in audited
        if result["demoted"]
    ]
    active_ids = active_recheck(invalid_ids) if active_recheck else set()
    for school, result in audited:
        if str(result["school_id"]) in active_ids:
            result["demoted"] = False
            result["reason"] = "active_work_started"
        if not result["demoted"] or dry_run:
            continue
        school.pop("discovery_seed_url", None)
        school.pop("cds_url_hint", None)
        school["scrape_policy"] = "unknown"
        record_probe(school, "not_found", "active_html_audit", 0, False)
    return [result for _school, result in audited]


def write_probe_summary(
    path: Path | None,
    *,
    probed: int,
    found: int,
    replaced: int,
    budget_remaining: int | None,
    still_stuck: int | None = None,
    audited: int = 0,
    demoted: int = 0,
) -> None:
    if path is None:
        return
    payload = {
        "probed": probed,
        "found": found,
        "replaced": replaced,
        "budget_remaining": budget_remaining,
        "still_stuck": still_stuck if still_stuck is not None else max(0, probed - found),
        "audited": audited,
        "demoted": demoted,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _save_yaml(data: dict) -> None:
    """Dump data back to schools.yaml. Caller ensures single-threaded call."""
    SCHOOLS_YAML.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    # Force line buffering on stdout. Python block-buffers stdout when it's
    # piped to another process (like `tee`), which holds output until an
    # 8KB buffer fills. For long-running probes this makes the tool look
    # stuck for 10-20 minutes even though it's working fine. Line buffering
    # flushes per-print, so the tee'd log grows in real time.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass  # stdout isn't a TextIOWrapper (replaced?) — silently skip

    ap = argparse.ArgumentParser(
        description="Discover CDS URLs for schools in schools.yaml")
    ap.add_argument("--only", help="Only probe this school id, or comma-separated ids")
    ap.add_argument("--ids-file", type=Path,
                    help="Probe only the school ids listed in this file (one per line)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print results but don't update schools.yaml")
    ap.add_argument("--rps", type=float, default=1.0,
                    help="Max requests per second per worker (default: 1). "
                         "Effective total rate is --rps × --workers, but spread "
                         "across many hosts so per-host rate stays polite.")
    ap.add_argument("--workers", type=int, default=4,
                    help="Concurrent school workers (default: 4). IO-bound so "
                         "Python threads are fine. Higher values finish faster "
                         "but raise aggregate DNS / HTTP load.")
    ap.add_argument("--bing-fallback", action="store_true",
                    help="Try Bing HTML scraping if pattern ladder fails")
    ap.add_argument("--brave-fallback", action="store_true",
                    help="Try Brave Search API if pattern ladder fails (BRAVE_API_KEY)")
    ap.add_argument("--google-fallback", action="store_true",
                    help="Try Google Custom Search API (GOOGLE_API_KEY + GOOGLE_CX)")
    ap.add_argument("--search-only", action="store_true",
                    help="Skip pattern ladder, only use search fallbacks")
    ap.add_argument("--cooldown-days", type=float, default=DEFAULT_COOLDOWN_DAYS,
                    help=f"Skip schools probed within N days (default: {DEFAULT_COOLDOWN_DAYS}, 0=ignore)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Max schools to probe (0=all)")
    ap.add_argument("--name-contains", metavar="TEXT",
                    help="Only probe schools whose name contains TEXT (case-insensitive). "
                         "Useful for targeting subsets like --name-contains 'University of' "
                         "to bias toward schools more likely to publish.")
    ap.add_argument("--save-every", type=int, default=50,
                    help="Save schools.yaml every N completed schools so a "
                         "Ctrl-C doesn't lose progress (default: 50)")
    ap.add_argument("--include-active-no-hint", action="store_true",
                    help="Also probe schools marked scrape_policy=active that "
                         "have no discovery_seed_url. Used to resolve seed-list "
                         "entries that were marked active on faith but never "
                         "got a URL — populates their seeds without demoting.")
    ap.add_argument("--reprobe-pdf-seeds", action="store_true",
                    help="Also re-probe active schools whose seed is a PDF/XLSX/"
                         "DOCX. Needed because last_result=found otherwise skips "
                         "them forever and weekly archive never finds listings.")
    ap.add_argument("--brave-budget", type=int, default=1800,
                    help="Max Brave Search API calls this run (default 1800, "
                         "under the 2000/month free tier). 0 means unlimited.")
    ap.add_argument("--school-budget-sec", type=float, default=DEFAULT_SCHOOL_BUDGET_SEC,
                    help=f"Per-school wall-clock budget for the pattern "
                         f"ladder in seconds (default: {DEFAULT_SCHOOL_BUDGET_SEC}). "
                         f"Caps the damage when a base URL accepts TCP but "
                         f"never responds and would otherwise wedge a worker "
                         f"for ~33 minutes cycling through pattern × subdomain "
                         f"× year combinations.")
    ap.add_argument("--summary-json", type=Path,
                    help="Write probed/found/replaced/budget_remaining for pipeline heartbeats.")
    ap.add_argument(
        "--audit-active-html",
        action="store_true",
        help="Validate active HTML seeds whose latest archive result is a "
             "terminal URL/content miss; definitively invalid seeds are "
             "demoted before normal discovery continues.",
    )
    ap.add_argument(
        "--audit-report-json",
        type=Path,
        help="Write per-seed active HTML validation results.",
    )
    args = ap.parse_args()

    data = yaml.safe_load(SCHOOLS_YAML.read_text())
    schools = data.get("schools", [])

    try:
        _, official_records = load_identity_snapshot(DEFAULT_SNAPSHOT)
    except (OSError, ValueError) as exc:
        print(f"identity snapshot unavailable ({exc}); will not flip scrape_policy", file=sys.stderr)
        official_records = {}
    env = {
        "google_api_key": os.environ.get("GOOGLE_API_KEY"),
        "google_cx": os.environ.get("GOOGLE_CX"),
        "brave_api_key": os.environ.get("BRAVE_API_KEY"),
        "official_records": official_records,
        "brave_tracker": {
            "calls": 0,
            "budget": None if args.brave_budget == 0 else args.brave_budget,
            "lock": Lock(),
        },
    }
    if args.brave_fallback and not env["brave_api_key"]:
        print("BRAVE_API_KEY is not set; --brave-fallback will find nothing.",
              file=sys.stderr)

    only_ids: set[str] | None = None
    if args.only:
        only_ids = {s.strip() for s in args.only.split(",") if s.strip()}
    if args.ids_file:
        file_ids = {
            line.strip()
            for line in args.ids_file.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        only_ids = file_ids if only_ids is None else only_ids | file_ids
    targeted = only_ids is not None
    reprobe_found = targeted or args.reprobe_pdf_seeds

    audited_results: list[dict] = []
    demoted_ids: set[str] = set()
    if args.audit_active_html:
        audit_schools = [
            school
            for school in schools
            if only_ids is None or str(school.get("id") or "") in only_ids
        ]
        supabase_url = os.environ.get("SUPABASE_URL")
        service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not service_role_key:
            ap.error(
                "--audit-active-html requires SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY"
            )
        archive_rows = fetch_latest_terminal_archive_rows(
            audit_schools,
            supabase_url=supabase_url,
            service_role_key=service_role_key,
        )
        active_recheck = lambda ids: fetch_active_archive_school_ids(
            ids,
            supabase_url=supabase_url,
            service_role_key=service_role_key,
        )
        audited_results = audit_active_html_seeds(
            audit_schools,
            archive_rows,
            dry_run=args.dry_run,
            active_recheck=active_recheck,
        )
        demoted_ids = {
            str(result["school_id"])
            for result in audited_results
            if result["demoted"] and not args.dry_run
        }
        for result in audited_results:
            print(
                f"[active-html-audit] {result['school_id']} "
                f"{result['validation']} ({result['reason']})"
            )
        print(
            f"Active HTML audit: {len(audited_results)} checked, "
            f"{sum(bool(result['demoted']) for result in audited_results)} "
            f"{'would be demoted' if args.dry_run else 'demoted'}"
        )
        if args.audit_report_json:
            args.audit_report_json.parent.mkdir(parents=True, exist_ok=True)
            args.audit_report_json.write_text(
                json.dumps(audited_results, indent=2, sort_keys=True) + "\n"
            )

    # ── Build candidate list (apply all filters up front) ──
    name_filter = args.name_contains.lower() if args.name_contains else None
    candidates: list[dict] = []
    skipped = 0

    for school in schools:
        sid = school.get("id", "")
        policy = school.get("scrape_policy", "unknown")
        name = school.get("name", sid)
        seed = school.get("discovery_seed_url") or school.get("cds_url_hint") or ""

        if only_ids is not None and sid not in only_ids:
            continue
        if not targeted and policy != "unknown":
            # Allow through active-but-no-hint entries when the caller asks
            # for them. These are hand-curated seed-list rows that were
            # marked active on faith but never got a URL resolved, so
            # downstream has nothing to fetch. Running them through the
            # probe populates discovery_seed_url without touching scrape_policy.
            # Both names checked so legacy YAML rows (pre-PR-5) still match.
            allow_active_no_hint = (
                args.include_active_no_hint
                and policy == "active"
                and not seed
            )
            allow_pdf_reprobe = (
                args.reprobe_pdf_seeds
                and policy == "active"
                and is_direct_doc_seed(seed)
            )
            if not allow_active_no_hint and not allow_pdf_reprobe:
                continue
        if name_filter and name_filter not in name.lower():
            continue
        if (
            sid not in demoted_ids
            and not targeted
            and args.cooldown_days > 0
            and should_skip(
                school, args.cooldown_days, reprobe_found=reprobe_found
            )
        ):
            skipped += 1
            continue

        candidates.append(school)
        if args.limit and len(candidates) >= args.limit:
            break

    total = len(candidates)
    print(f"Probing {total} schools with {args.workers} workers (rps={args.rps} per worker)")
    if skipped:
        print(f"Skipped {skipped} schools due to {args.cooldown_days}-day cooldown")
    tracker = env.get("brave_tracker") or {}
    def budget_remaining() -> int | None:
        budget = tracker.get("budget")
        if budget is None:
            return None
        return max(0, int(budget) - int(tracker.get("calls") or 0))
    if total == 0:
        print("Nothing to probe. Exiting.")
        write_probe_summary(
            args.summary_json,
            probed=0,
            found=0,
            replaced=0,
            budget_remaining=budget_remaining(),
            still_stuck=0,
            audited=len(audited_results),
            demoted=len(demoted_ids),
        )
        if demoted_ids and not args.dry_run:
            _save_yaml(data)
            print(f"Updated {SCHOOLS_YAML}")
        return

    # ── Threadpool execution ──
    found = 0
    failed = 0
    completed = 0
    replaced = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all schools; keep a mapping so we can attribute results
        futures = {executor.submit(process_school, s, args, env): s for s in candidates}

        try:
            for future in as_completed(futures):
                completed += 1
                try:
                    result = future.result()
                except Exception as e:
                    school = futures[future]
                    print(f"[{completed:>5}/{total}] {school.get('name', school.get('id', '?'))} ... EXCEPTION: {type(e).__name__}: {e}")
                    failed += 1
                    continue

                prefix = f"[{completed:>5}/{total}]"
                if result.get("replaced"):
                    replaced += 1
                if result["url"]:
                    found += 1
                    tag = f"[{result['method']}] " if result["method"] != "pattern" else ""
                    print(f"{prefix} {result['name']} ({result['domain']}) ... {tag}FOUND: {result['url']}")
                else:
                    failed += 1
                    print(f"{prefix} {result['name']} ({result['domain']}) ... not found")

                # Periodic save so Ctrl-C doesn't lose hours of probes
                if not args.dry_run and args.save_every > 0 and completed % args.save_every == 0:
                    dedupe_identical_seeds(schools)
                    _save_yaml(data)
                    print(f"  [checkpoint saved at {completed}/{total}]")
        except KeyboardInterrupt:
            print(f"\n[interrupted at {completed}/{total}] — cancelling pending workers")
            executor.shutdown(wait=False, cancel_futures=True)
            if not args.dry_run:
                dedupe_identical_seeds(schools)
                _save_yaml(data)
                print(f"  [partial progress saved to {SCHOOLS_YAML}]")
            print(f"\nProbed: {completed}, Found: {found}, Not found: {failed}")
            write_probe_summary(
                args.summary_json,
                probed=completed,
                found=found,
                replaced=replaced,
                budget_remaining=budget_remaining(),
                audited=len(audited_results),
                demoted=len(demoted_ids),
            )
            return

    print(f"\nProbed: {completed}, Found: {found}, Not found: {failed}", end="")
    if skipped:
        print(f", Skipped (cooldown): {skipped}", end="")
    print()
    if tracker.get("calls"):
        print(f"Brave API calls this run: {tracker['calls']}")

    if not args.dry_run and completed > 0:
        cleared = dedupe_identical_seeds(schools)
        if cleared:
            print(f"Cleared {len(cleared)} duplicate seed(s) shared across UNITIDs")
        _save_yaml(data)
        print(f"Updated {SCHOOLS_YAML}")
    write_probe_summary(
        args.summary_json,
        probed=completed,
        found=found,
        replaced=replaced,
        budget_remaining=budget_remaining(),
        audited=len(audited_results),
        demoted=len(demoted_ids),
    )


if __name__ == "__main__":
    main()
