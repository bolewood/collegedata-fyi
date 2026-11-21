#!/usr/bin/env python3
"""One-off IR-hub crawl for homepage seeds that missed a CDS.

Selects schools whose last archive outcome was no_pdfs_found from a homepage
seed, plus never-checked schools. Fetches the homepage (and at most one About
page plus a handful of IR hub URLs), and writes a review CSV:

    school_id,name,ipeds_id,cds,url,notes

`cds` is yes / no / unclear. This script does not enqueue archive work, does
not call force_urls, and does not write schools.yaml. Uncertain hits stay
in the CSV for a human to review.

Usage:
    python tools/finder/backfill_ir_hubs.py \\
      --from-csv path/to/missing.csv \\
      --out scratch/ir-hub-backfill/review.csv \\
      --limit 25 --rps 0.5

Do not run this against production archive as part of a PR. Operator
dispatch: GitHub Actions workflow `ops-ir-hub-backfill.yml`.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.finder.ir_hubs import (  # noqa: E402
    MAX_ABOUT_PAGES,
    MAX_IR_HUB_URLS,
    collect_ir_hub_candidates,
    extract_about_links,
)
from tools.finder.probe_urls import (  # noqa: E402
    _dns_ok,
    _fetch_html,
    html_has_cds_content_or_anchors,
    is_cds_page,
)

ROOT = Path(__file__).parent
SCHOOLS_YAML = ROOT / "schools.yaml"
DEFAULT_OUT = _REPO_ROOT / "scratch" / "ir-hub-backfill" / "review.csv"


def is_homepage_seed(seed: str, website: str) -> bool:
    """True when the archive seed is the school's marketing homepage."""
    if not seed:
        return True
    if not website:
        return False

    def _norm(url: str) -> str:
        raw = url.strip()
        if not raw:
            return ""
        if "://" not in raw:
            raw = "https://" + raw
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = (parsed.path or "/").rstrip("/") or "/"
        if path in {"/index.html", "/index.shtml", "/index.php", "/pages/default.aspx"}:
            path = "/"
        return f"{host}{path}"

    seed_n = _norm(seed)
    site_n = _norm(website)
    if not seed_n or not site_n:
        return False
    seed_host, _, seed_path = seed_n.partition("/")
    site_host, _, site_path = site_n.partition("/")
    if seed_host != site_host:
        return False
    return seed_path in {"", "/"} or seed_path == site_path


def select_backfill_rows(
    csv_rows: list[dict],
    yaml_schools: list[dict],
    *,
    include_no_pdfs_found: bool = True,
    include_never_checked: bool = True,
) -> list[dict]:
    """Combine the missing-schools CSV with yaml identity for the crawl list."""
    yaml_by_ipeds = {
        str(school.get("ipeds_id") or "").strip('"'): school
        for school in yaml_schools
        if school.get("ipeds_id")
    }
    selected: list[dict] = []
    seen: set[str] = set()
    for row in csv_rows:
        unitid = str(row.get("unitid") or "").strip()
        if not unitid or unitid in seen:
            continue
        outcome = str(row.get("archive_last_outcome") or "").strip()
        coverage = str(row.get("coverage_status") or row.get("discovery_status") or "")
        never = (
            "never_checked" in coverage
            or str(row.get("coverage_status") or "") == "not_checked"
            or not outcome
        )
        want = False
        if include_no_pdfs_found and outcome == "no_pdfs_found":
            seed = str(row.get("latest_seed_url") or "")
            website = str(row.get("website_url") or row.get("website_domain") or "")
            if is_homepage_seed(seed, website):
                want = True
        if include_never_checked and never:
            want = True
        if not want:
            continue
        seen.add(unitid)
        yaml_row = yaml_by_ipeds.get(unitid) or {}
        selected.append(
            {
                "school_id": yaml_row.get("id") or row.get("school_id") or "",
                "name": yaml_row.get("name") or row.get("name") or "",
                "ipeds_id": unitid,
                "domain": yaml_row.get("domain")
                or row.get("website_domain")
                or "",
                "website_url": row.get("website_url") or "",
                "archive_last_outcome": outcome,
                "coverage_status": row.get("coverage_status") or "",
            }
        )
    selected.sort(
        key=lambda row: (
            0 if row.get("archive_last_outcome") == "no_pdfs_found" else 1,
            str(row.get("name") or "").lower(),
        )
    )
    return selected


def classify_page(url: str, html: str) -> str:
    """yes if the page hosts CDS content or anchors, else no."""
    body = html.encode("utf-8", errors="ignore")
    if is_cds_page(body, "text/html") or html_has_cds_content_or_anchors(body):
        return "yes"
    return "no"


def crawl_school(row: dict, rps: float) -> dict:
    """Fetch homepage + IR hubs. Never writes. Returns a review row."""
    delay = 1.0 / rps if rps > 0 else 1.0
    domain = str(row.get("domain") or "")
    website = str(row.get("website_url") or "")
    start_urls = []
    if website:
        start_urls.append(website if "://" in website else f"https://{website}")
    if domain:
        start_urls.extend([f"https://www.{domain}/", f"https://{domain}/"])

    homepage_url = ""
    homepage_html = ""
    notes: list[str] = []
    for url in start_urls:
        host = urlparse(url).hostname or ""
        if host and not _dns_ok(host):
            notes.append(f"dns_miss:{host}")
            continue
        fetched = _fetch_html(url)
        time.sleep(delay)
        if fetched:
            homepage_url, homepage_html = fetched
            break
        notes.append(f"homepage_fail:{url}")

    if not homepage_html:
        return {
            "school_id": row.get("school_id") or "",
            "name": row.get("name") or "",
            "ipeds_id": row.get("ipeds_id") or "",
            "cds": "unclear",
            "url": "",
            "notes": "homepage_unreachable " + " ".join(notes),
        }

    if classify_page(homepage_url, homepage_html) == "yes":
        return {
            "school_id": row.get("school_id") or "",
            "name": row.get("name") or "",
            "ipeds_id": row.get("ipeds_id") or "",
            "cds": "yes",
            "url": homepage_url,
            "notes": "cds_on_homepage",
        }

    about_pages: list[tuple[str, str]] = []
    for about_url in extract_about_links(homepage_html, homepage_url)[:MAX_ABOUT_PAGES]:
        fetched = _fetch_html(about_url)
        time.sleep(delay)
        if not fetched:
            notes.append(f"about_fail:{about_url}")
            continue
        about_final, about_html = fetched
        about_pages.append((about_final, about_html))
        if classify_page(about_final, about_html) == "yes":
            return {
                "school_id": row.get("school_id") or "",
                "name": row.get("name") or "",
                "ipeds_id": row.get("ipeds_id") or "",
                "cds": "yes",
                "url": about_final,
                "notes": "cds_on_about_page",
            }

    hubs = collect_ir_hub_candidates(
        homepage_html,
        homepage_url,
        about_pages=about_pages,
        domain=domain,
        include_well_known=True,
        include_subdomains=True,
        limit=MAX_IR_HUB_URLS,
    )
    unclear = False
    for hub in hubs:
        host = urlparse(hub).hostname or ""
        if host and not _dns_ok(host):
            continue
        fetched = _fetch_html(hub)
        time.sleep(delay)
        if not fetched:
            notes.append(f"hub_fail:{hub}")
            unclear = True
            continue
        final_url, html = fetched
        verdict = classify_page(final_url, html)
        if verdict == "yes":
            return {
                "school_id": row.get("school_id") or "",
                "name": row.get("name") or "",
                "ipeds_id": row.get("ipeds_id") or "",
                "cds": "yes",
                "url": final_url,
                "notes": "cds_on_ir_hub",
            }

    return {
        "school_id": row.get("school_id") or "",
        "name": row.get("name") or "",
        "ipeds_id": row.get("ipeds_id") or "",
        "cds": "unclear" if unclear and not hubs else "no",
        "url": homepage_url,
        "notes": " ".join(notes) or "no_cds_on_ir_hubs",
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="IR-hub backfill review crawl. Does not publish or archive."
    )
    ap.add_argument("--from-csv", type=Path, required=True,
                    help="missing-schools CSV with archive_last_outcome / website_url")
    ap.add_argument("--schools-yaml", type=Path, default=SCHOOLS_YAML)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=0, help="Max schools (0=all)")
    ap.add_argument("--rps", type=float, default=0.5,
                    help="Requests per second (default 0.5, polite)")
    ap.add_argument("--only", help="Comma-separated school ids or UNITIDs")
    ap.add_argument("--summary-json", type=Path)
    args = ap.parse_args()

    csv_rows = list(csv.DictReader(args.from_csv.open(newline="", encoding="utf-8")))
    yaml_schools = yaml.safe_load(args.schools_yaml.read_text()).get("schools", [])
    selected = select_backfill_rows(csv_rows, yaml_schools)
    if args.only:
        wanted = {part.strip() for part in args.only.split(",") if part.strip()}
        selected = [
            row for row in selected
            if row.get("school_id") in wanted or row.get("ipeds_id") in wanted
        ]
    if args.limit:
        selected = selected[: args.limit]

    print(f"IR-hub backfill: {len(selected)} schools, rps={args.rps}", flush=True)
    print("This run writes a review CSV only. It does not archive or edit yaml.",
          flush=True)

    results: list[dict] = []
    for index, row in enumerate(selected, start=1):
        result = crawl_school(row, args.rps)
        results.append(result)
        print(
            f"[{index}/{len(selected)}] {result['name']} ... "
            f"{result['cds']} {result.get('url') or ''}",
            flush=True,
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["school_id", "name", "ipeds_id", "cds", "url", "notes"],
        )
        writer.writeheader()
        writer.writerows(results)

    counts = {"yes": 0, "no": 0, "unclear": 0}
    for result in results:
        counts[str(result.get("cds") or "unclear")] = (
            counts.get(str(result.get("cds") or "unclear"), 0) + 1
        )
    summary = {
        "schools": len(results),
        "yes": counts.get("yes", 0),
        "no": counts.get("no", 0),
        "unclear": counts.get("unclear", 0),
        "out": str(args.out),
        "published": False,
    }
    print(json.dumps(summary, indent=2))
    if args.summary_json:
        args.summary_json.write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
