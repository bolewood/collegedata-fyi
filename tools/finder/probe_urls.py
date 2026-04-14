#!/usr/bin/env python3
"""Probe URL patterns to discover which schools actually publish a CDS online.

For each school in schools.yaml with scrape_policy == "unknown", tries the
URL pattern ladder against the school's domain. On a hit, updates the entry
with cds_url_hint and flips scrape_policy to "active".

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

import yaml

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
    """GET a URL and read the full body. For API/search responses."""
    hdrs = {"User-Agent": _UA}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            status = resp.status
            headers = {k.lower(): v for k, v in resp.getheaders()}
            body = resp.read()
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
        text = content[:5000].decode("utf-8", errors="ignore").lower()
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


def should_skip(school: dict, cooldown_days: float) -> bool:
    """Return True if this school was probed recently and came back not_found."""
    ps = school.get("probe_state")
    if not ps:
        return False
    if ps.get("last_result") == "found":
        return True  # already found, nothing to do
    last = ps.get("last_probed_at", "")
    return _days_since(last) < cooldown_days


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

def probe_school(domain: str, rps: float) -> tuple[str | None, int]:
    """Try URL patterns against a domain.

    Returns (first_working_url_or_None, patterns_tried_count).

    Uses a DNS short-circuit: before probing any base, we check whether
    the hostname resolves at all. Bases that return NXDOMAIN are skipped
    entirely, which saves ~150 probes per school for the common case of
    schools that only have www.X.edu and maybe ir.X.edu live. DNS
    results are cached per-session via `_dns_ok`.
    """
    if not domain:
        return None, 0

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
        for pattern in PATTERNS:
            url = base.rstrip("/") + pattern
            tried += 1
            status, headers, body = _get(url, timeout=10, read_bytes=5000)
            if status == 200:
                ct = headers.get("content-type", "")
                if is_cds_page(body, ct):
                    return url, tried
            time.sleep(delay)

    # Year-specific PDF patterns (only against naked + www, which almost
    # always resolve, so no DNS check needed here).
    for base in [f"https://{domain}", f"https://www.{domain}"]:
        host = base.replace("https://", "").split("/")[0]
        if not _dns_ok(host):
            continue
        for year in CDS_YEARS:
            pdf_patterns = [
                f"/ir/cds/CDS_{year}.pdf",
                f"/ir/cds/cds_{year}.pdf",
                f"/ir/CDS-{year}.pdf",
                f"/institutional-research/CDS-{year}.pdf",
                f"/common-data-set/CDS_{year}.pdf",
            ]
            for pat in pdf_patterns:
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


def brave_search(domain: str, api_key: str) -> str | None:
    """Use Brave Search API to find CDS PDFs for a school.

    Free tier: 2,000 queries/month. Paid: $0.003/query.
    Independent index, no domain pre-registration.
    """
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
    # Prefer PDFs when present, but accept CDS landing pages as fallback.
    landing_fallback = None
    for r in results:
        link = r.get("url", "")
        if not link:
            continue
        if link.lower().endswith(".pdf"):
            return link
        desc = r.get("description", "").lower()
        title = r.get("title", "").lower()
        if "common data set" in desc or "common data set" in title:
            if landing_fallback is None:
                landing_fallback = link

    return landing_fallback


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
        url, patterns_tried = probe_school(domain, args.rps)

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
        url = brave_search(domain, env["brave_api_key"])
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

    if url:
        if not args.dry_run:
            school["cds_url_hint"] = url
            school["scrape_policy"] = "active"
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
    }


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
    ap.add_argument("--only", help="Only probe this school id")
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
    args = ap.parse_args()

    data = yaml.safe_load(SCHOOLS_YAML.read_text())
    schools = data.get("schools", [])

    env = {
        "google_api_key": os.environ.get("GOOGLE_API_KEY"),
        "google_cx": os.environ.get("GOOGLE_CX"),
        "brave_api_key": os.environ.get("BRAVE_API_KEY"),
    }

    # ── Build candidate list (apply all filters up front) ──
    name_filter = args.name_contains.lower() if args.name_contains else None
    candidates: list[dict] = []
    skipped = 0

    for school in schools:
        sid = school.get("id", "")
        policy = school.get("scrape_policy", "unknown")
        name = school.get("name", sid)

        if args.only and sid != args.only:
            continue
        if not args.only and policy != "unknown":
            continue
        if name_filter and name_filter not in name.lower():
            continue
        if not args.only and args.cooldown_days > 0 and should_skip(school, args.cooldown_days):
            skipped += 1
            continue

        candidates.append(school)
        if args.limit and len(candidates) >= args.limit:
            break

    total = len(candidates)
    print(f"Probing {total} schools with {args.workers} workers (rps={args.rps} per worker)")
    if skipped:
        print(f"Skipped {skipped} schools due to {args.cooldown_days}-day cooldown")
    if total == 0:
        print("Nothing to probe. Exiting.")
        return

    # ── Threadpool execution ──
    found = 0
    failed = 0
    completed = 0

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
                if result["url"]:
                    found += 1
                    tag = f"[{result['method']}] " if result["method"] != "pattern" else ""
                    print(f"{prefix} {result['name']} ({result['domain']}) ... {tag}FOUND: {result['url']}")
                else:
                    failed += 1
                    print(f"{prefix} {result['name']} ({result['domain']}) ... not found")

                # Periodic save so Ctrl-C doesn't lose hours of probes
                if not args.dry_run and args.save_every > 0 and completed % args.save_every == 0:
                    _save_yaml(data)
                    print(f"  [checkpoint saved at {completed}/{total}]")
        except KeyboardInterrupt:
            print(f"\n[interrupted at {completed}/{total}] — cancelling pending workers")
            executor.shutdown(wait=False, cancel_futures=True)
            if not args.dry_run:
                _save_yaml(data)
                print(f"  [partial progress saved to {SCHOOLS_YAML}]")
            print(f"\nProbed: {completed}, Found: {found}, Not found: {failed}")
            return

    print(f"\nProbed: {completed}, Found: {found}, Not found: {failed}", end="")
    if skipped:
        print(f", Skipped (cooldown): {skipped}", end="")
    print()

    if not args.dry_run and completed > 0:
        _save_yaml(data)
        print(f"Updated {SCHOOLS_YAML}")


if __name__ == "__main__":
    main()
