#!/usr/bin/env python3
"""Diagnose why Brave Search fallback is returning nothing useful.

Runs Brave Search API queries for 5 hand-verified known-publisher schools
(all confirmed via WebSearch in the overnight-run post-mortem) and prints
the raw API response alongside what probe_urls.py's brave_search() would
extract. Tries four query variants per school to see which one (if any)
actually returns useful results.

Dependencies: stdlib only. Needs BRAVE_API_KEY in env.

Usage:
    export BRAVE_API_KEY="your-key-from-brave-dashboard"
    python tools/finder/debug_brave.py

    # Show the full JSON response from Brave for each query (verbose):
    python tools/finder/debug_brave.py --raw

    # Test a different school instead:
    python tools/finder/debug_brave.py --domain yale.edu

Results indicate one of three failure modes:
  1. BRAVE_API_KEY missing or invalid → no responses, fix auth first
  2. Brave returns nothing for any variant → Brave's index is too thin for
     our corpus; fall back to Bing HTML scraping instead
  3. Brave returns results but our parser misses them → patch the parser
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
UA = "collegedata-fyi-debug/0.1"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# 5 hand-verified known publishers from the overnight post-mortem.
# Every one of these was confirmed via WebSearch to have a live CDS URL,
# and every one returned "not found" from the pattern ladder.
TEST_SCHOOLS = [
    {
        "name": "Tulane University",
        "domain": "tulane.edu",
        "known_url": "https://oair.tulane.edu/common-data-set",
        "known_fixable": "add oair subdomain to ladder (already patched)",
    },
    {
        "name": "American University",
        "domain": "american.edu",
        "known_url": "https://www.american.edu/provost/oira/common-data-set.cfm",
        "known_fixable": "add .cfm pattern to ladder (already patched)",
    },
    {
        "name": "Villanova University",
        "domain": "villanova.edu",
        "known_url": "https://www.villanova.edu/content/dam/villanova/provost/decision_support/2024-2025-CDS_v2.pdf",
        "known_fixable": "no — custom DAM path",
    },
    {
        "name": "Bentley University",
        "domain": "bentley.edu",
        "known_url": "https://www.bentley.edu/offices/business-intelligence-and-enrollment-systems/reports",
        "known_fixable": "no — custom office path with no CDS keyword in URL",
    },
    {
        "name": "Babson College",
        "domain": "babson.edu",
        "known_url": "https://www.babson.edu/media/babson/assets/rankings/babson-college-common-data-set.pdf",
        "known_fixable": "no — custom DAM path",
    },
]


# Four query variants to try. The first is what probe_urls.py uses today.
QUERY_VARIANTS = [
    {
        "label": "current (site + filetype:pdf + quoted)",
        "template": 'site:{domain} filetype:pdf "Common Data Set"',
    },
    {
        "label": "no filetype (site + quoted)",
        "template": 'site:{domain} "Common Data Set"',
    },
    {
        "label": "loose (site + unquoted)",
        "template": 'site:{domain} common data set',
    },
    {
        "label": "broad (no site, domain in body)",
        "template": '{domain} "common data set"',
    },
]


def brave_query(q, api_key):
    """Call the Brave Search API. Returns (status, parsed_json, raw_text)."""
    params = urllib.parse.urlencode({"q": q, "count": 10})
    url = f"{BRAVE_ENDPOINT}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                import gzip
                body = gzip.decompress(body)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = {}
            return resp.status, data, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, {}, str(e)
    except (urllib.error.URLError, OSError) as e:
        return -1, {}, str(e)


def extract_with_current_parser(data, domain):
    """Replicate probe_urls.py's brave_search extraction logic."""
    results = data.get("web", {}).get("results", [])
    for r in results:
        link = r.get("url", "")
        if link.lower().endswith(".pdf"):
            return link
        desc = r.get("description", "").lower()
        title = r.get("title", "").lower()
        if "common data set" in desc or "common data set" in title:
            return link
    return None


def summarize_results(data, domain):
    """Extract the top results with key fields for display."""
    results = data.get("web", {}).get("results", [])
    summary = []
    for r in results[:5]:
        summary.append({
            "url": r.get("url", ""),
            "title": r.get("title", "")[:80],
            "description": r.get("description", "")[:100],
            "is_pdf": r.get("url", "").lower().endswith(".pdf"),
            "mentions_cds_in_desc": "common data set" in r.get("description", "").lower(),
            "mentions_cds_in_title": "common data set" in r.get("title", "").lower(),
        })
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--raw", action="store_true",
                    help="Print the full JSON response from Brave for each query")
    ap.add_argument("--domain", help="Test a specific domain instead of the 5 defaults")
    args = ap.parse_args()

    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        print("ERROR: BRAVE_API_KEY is not set in the environment.")
        print("       export BRAVE_API_KEY='your-key-from-brave-dashboard'")
        sys.exit(1)

    print(f"Using BRAVE_API_KEY ending in ...{api_key[-6:]}")
    print()

    if args.domain:
        schools = [{"name": args.domain, "domain": args.domain, "known_url": "(unknown)", "known_fixable": "n/a"}]
    else:
        schools = TEST_SCHOOLS

    for school in schools:
        print("=" * 80)
        print(f"SCHOOL: {school['name']} ({school['domain']})")
        print(f"  Known CDS URL: {school['known_url']}")
        print(f"  Fixable: {school['known_fixable']}")
        print()

        for variant in QUERY_VARIANTS:
            q = variant["template"].format(domain=school["domain"])
            print(f"  ── Query: [{variant['label']}]")
            print(f"     {q}")

            status, data, raw_text = brave_query(q, api_key)

            if status != 200:
                print(f"     RESPONSE: HTTP {status} — {raw_text[:200]}")
                print()
                continue

            # How many results total?
            total = len(data.get("web", {}).get("results", []))
            print(f"     RESPONSE: HTTP 200, {total} results")

            # Top 5 summarized
            for i, r in enumerate(summarize_results(data, school["domain"])):
                flags = []
                if r["is_pdf"]:
                    flags.append("PDF")
                if r["mentions_cds_in_title"]:
                    flags.append("CDS-in-title")
                if r["mentions_cds_in_desc"]:
                    flags.append("CDS-in-desc")
                flag_str = f"[{' '.join(flags)}]" if flags else "[no-cds-signal]"
                print(f"       {i+1}. {flag_str}")
                print(f"          url:   {r['url'][:100]}")
                print(f"          title: {r['title']}")
                if r["description"]:
                    print(f"          desc:  {r['description']}")

            # What would probe_urls.py's current parser return?
            extracted = extract_with_current_parser(data, school["domain"])
            if extracted:
                print(f"     CURRENT PARSER WOULD RETURN: {extracted}")
            else:
                print(f"     CURRENT PARSER RETURNS: None")

            if args.raw:
                print()
                print("     RAW JSON (truncated to 2KB):")
                print("     " + raw_text[:2000].replace("\n", "\n     "))

            print()

        print()


if __name__ == "__main__":
    main()
