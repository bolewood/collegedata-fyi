#!/usr/bin/env python3
"""Probe URL patterns to discover which schools actually publish a CDS online.

For each school in schools.yaml with scrape_policy == "unknown", tries the
URL pattern ladder from seed_urls.md against the school's domain. On a hit,
updates the entry with cds_url_hint and flips scrape_policy to "active".

Usage:
    pip install pyyaml --break-system-packages

    # Probe all unknown schools (polite: 1 req/sec)
    python probe_urls.py

    # Probe a specific school by id
    python probe_urls.py --only yale

    # Dry run — print results but don't update schools.yaml
    python probe_urls.py --dry-run

    # Adjust rate limit (requests per second)
    python probe_urls.py --rps 2

    # Also try Google dork via Custom Search API (requires GOOGLE_API_KEY
    # and GOOGLE_CX env vars)
    python probe_urls.py --google-fallback
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
SCHOOLS_YAML = ROOT / "schools.yaml"

# Shared opener with custom User-Agent
_UA = "collegedata-fyi-finder/0.1 (https://github.com/bolewood/collegedata-fyi)"
# Lenient SSL context — some school sites have dodgy certs
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# URL pattern ladder — ordered by frequency in the wild
PATTERNS = [
    "/ir/cds/",
    "/institutional-research/common-data-set/",
    "/facts-and-figures/common-data-set/",
    "/oir/cds/",
    "/common-data-set/",
    "/data/campus/general/cds.html",
    "/registrar/cds.pdf",
    "/budget/cds/",
]

# Also try these subdomains
SUBDOMAINS = ["www", "ir", "oir", "oira", "irds", "obp", "ira"]

# Current CDS years to search for (newest first)
CDS_YEARS = ["2025-2026", "2024-2025", "2023-2024"]

def _get(url: str, timeout: int = 10, read_bytes: int = 0) -> tuple[int, dict, bytes]:
    """GET a URL. Returns (status, headers_dict, body_bytes).

    If read_bytes > 0, only reads that many bytes of the body (for content
    sniffing).  Returns (-1, {}, b"") on any network/timeout error.
    """
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            status = resp.status
            headers = {k.lower(): v for k, v in resp.getheaders()}
            body = resp.read(read_bytes) if read_bytes else b""
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


def probe_school(domain: str, rps: float) -> str | None:
    """Try URL patterns against a domain. Returns the first working URL or None."""
    if not domain:
        return None

    bases = [f"https://{domain}"]
    for sub in SUBDOMAINS:
        bases.append(f"https://{sub}.{domain}")

    delay = 1.0 / rps if rps > 0 else 1.0

    for base in bases:
        for pattern in PATTERNS:
            url = base.rstrip("/") + pattern
            status, headers, body = _get(url, timeout=10, read_bytes=5000)
            if status == 200:
                ct = headers.get("content-type", "")
                if is_cds_page(body, ct):
                    return url
            time.sleep(delay)

    # Try year-specific PDF patterns
    for base in [f"https://{domain}", f"https://www.{domain}"]:
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
                status, headers = _head(url, timeout=10)
                if status == 200:
                    ct = headers.get("content-type", "")
                    if "pdf" in ct.lower():
                        return url
                time.sleep(delay)

    return None


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Only probe this school id")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rps", type=float, default=1.0,
                    help="Max requests per second (default: 1)")
    ap.add_argument("--google-fallback", action="store_true",
                    help="Try Google Custom Search API if probes fail")
    ap.add_argument("--limit", type=int, default=0,
                    help="Max schools to probe (0=all)")
    args = ap.parse_args()

    data = yaml.safe_load(SCHOOLS_YAML.read_text())
    schools = data.get("schools", [])

    google_api_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CX")

    probed = 0
    found = 0
    failed = 0

    for school in schools:
        sid = school.get("id", "")
        policy = school.get("scrape_policy", "unknown")

        if args.only and sid != args.only:
            continue
        if not args.only and policy != "unknown":
            continue
        if args.limit and probed >= args.limit:
            break

        domain = school.get("domain", "")
        name = school.get("name", sid)
        probed += 1

        print(f"[{probed:>4}] {name} ({domain}) ... ", end="", flush=True)

        url = probe_school(domain, args.rps)

        if not url and args.google_fallback and google_api_key and google_cx:
            url = google_dork(domain, google_api_key, google_cx)

        if url:
            found += 1
            print(f"FOUND: {url}")
            if not args.dry_run:
                school["cds_url_hint"] = url
                school["scrape_policy"] = "active"
        else:
            failed += 1
            print("not found")

    print(f"\nProbed: {probed}, Found: {found}, Not found: {failed}")

    if not args.dry_run and found > 0:
        # Write back — preserve structure
        SCHOOLS_YAML.write_text(yaml.dump(data, default_flow_style=False,
                                          sort_keys=False, allow_unicode=True))
        print(f"Updated {SCHOOLS_YAML}")


if __name__ == "__main__":
    main()
