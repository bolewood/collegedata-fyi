#!/usr/bin/env python3
"""Probe URL patterns to discover which schools actually publish a CDS online.

For each school in schools.yaml with scrape_policy == "unknown", tries the
URL pattern ladder against the school's domain. On a hit, updates the entry
with discovery_seed_url and flips scrape_policy to "active".

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
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from collections import defaultdict

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
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
    return select_brave_cds_url(results)


def select_brave_cds_url(results: list[dict]) -> str | None:
    """Pick a discovery seed from Brave web results.

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

    landing = None
    pdf = None
    for r in results:
        link = r.get("url", "")
        if not link or looks_like_template(link):
            continue
        if link.lower().endswith(".pdf"):
            if pdf is None:
                pdf = link
            continue
        desc = r.get("description", "").lower()
        title = r.get("title", "").lower()
        if "common data set" in desc or "common data set" in title:
            if landing is None:
                landing = link
    return landing or pdf


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


def write_probe_summary(
    path: Path | None,
    *,
    probed: int,
    found: int,
    replaced: int,
    budget_remaining: int | None,
    still_stuck: int | None = None,
) -> None:
    if path is None:
        return
    payload = {
        "probed": probed,
        "found": found,
        "replaced": replaced,
        "budget_remaining": budget_remaining,
        "still_stuck": still_stuck if still_stuck is not None else max(0, probed - found),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
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
    args = ap.parse_args()

    data = yaml.safe_load(SCHOOLS_YAML.read_text())
    schools = data.get("schools", [])

    env = {
        "google_api_key": os.environ.get("GOOGLE_API_KEY"),
        "google_cx": os.environ.get("GOOGLE_CX"),
        "brave_api_key": os.environ.get("BRAVE_API_KEY"),
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
        if not targeted and args.cooldown_days > 0 and should_skip(
            school, args.cooldown_days, reprobe_found=reprobe_found
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
        )
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
    )


if __name__ == "__main__":
    main()
