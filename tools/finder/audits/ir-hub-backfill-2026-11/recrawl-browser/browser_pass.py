"""Browser pass over schools that answer 403 to the finder user agent.

Same crawl as tools/finder/backfill_ir_hubs.py (homepage, one About page, up
to six IR hub URLs, yes/no/unclear), but each page is loaded in headless
Chromium. Review-only: writes a CSV, archives nothing.

Stops, per school, at anything that is not an ordinary page:
  - robots.txt disallows the URL for all agents -> "robots_disallow"
  - a visual CAPTCHA or an interstitial challenge page -> "challenge"
  - any status other than 200 -> "http_<status>"
Nothing is clicked, solved or waited out.

usage (repo root, a Python with tools/finder/requirements-headless.txt installed):
  python tools/finder/audits/ir-hub-backfill-2026-11/recrawl-browser/browser_pass.py \\
      tools/finder/audits/ir-hub-backfill-2026-11/recrawl-mac/review.csv <out.csv> [limit]
"""
from __future__ import annotations

import csv
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import tools.finder.backfill_ir_hubs as b  # noqa: E402
from tools.finder.headless_archive import is_waf_captcha_bytes  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
CHALLENGE_MARKERS = (
    "just a moment...",
    "checking your browser",
    "attention required! | cloudflare",
    "verify you are human",
    "pardon our interruption",
    "request unsuccessful. incapsula",
    "access denied",
    "are you a robot",
    "px-captcha",
)
MIN_GAP_SECONDS = 3.0

page = None
ctx = None
last_request_at = 0.0
robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def pace() -> None:
    global last_request_at
    wait = MIN_GAP_SECONDS - (time.monotonic() - last_request_at)
    if wait > 0:
        time.sleep(wait)
    last_request_at = time.monotonic()


def robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in robots_cache:
        parser = None
        try:
            pace()
            resp = ctx.request.get(origin + "/robots.txt", timeout=15_000)
            if resp.status == 200 and "html" not in (resp.headers.get("content-type") or ""):
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(resp.text().splitlines())
        except Exception:
            parser = None
        robots_cache[origin] = parser
    parser = robots_cache[origin]
    return True if parser is None else parser.can_fetch("*", url)


def browser_fetch(url: str, timeout: int):
    cleaned = b.sanitize_url(url)
    if not cleaned:
        return None, "empty_url"
    if not robots_allows(cleaned):
        return None, f"robots_disallow:{cleaned}"
    pace()
    try:
        resp = page.goto(cleaned, wait_until="domcontentloaded", timeout=timeout * 1000)
    except Exception as exc:
        kind = "timeout" if "Timeout" in type(exc).__name__ else "network"
        return None, f"{kind}:{cleaned}"
    if resp is None:
        return None, f"network:{cleaned}"
    status = resp.status
    try:
        html = page.content()
    except Exception:
        html = ""
    head = html[:6000].lower()
    if is_waf_captcha_bytes(html.encode("utf-8", "ignore")[:20000], "text/html") or any(
        marker in head for marker in CHALLENGE_MARKERS
    ):
        return None, f"challenge:{cleaned}"
    if status != 200:
        return None, f"http_{status}:{cleaned}"
    content_type = (resp.headers.get("content-type") or "").lower()
    if "html" not in content_type:
        return None, f"not_html:{cleaned}"
    return (page.url or cleaned, html), ""


def main() -> int:
    global page, ctx
    prior, out = Path(sys.argv[1]), Path(sys.argv[2])
    wanted = set()
    for row in csv.DictReader(prior.open(newline="", encoding="utf-8")):
        if row["cds"] == "unclear" and "homepage_fail:http_403" in row["notes"]:
            wanted.add(row["ipeds_id"].strip())
    csv_rows = list(csv.DictReader(
        (ROOT / "tools/finder/audits/ir-hub-backfill-2026-11/missing_in_scope.csv").open(newline="", encoding="utf-8")
    ))
    schools = yaml.safe_load((ROOT / "tools/finder/schools.yaml").read_text()).get("schools", [])
    selected = b.rows_for_unitids(csv_rows, schools, wanted)
    done = b.load_existing_review(out)
    results = [done[r["ipeds_id"]] for r in selected if r["ipeds_id"] in done]
    remaining = [r for r in selected if r["ipeds_id"] not in done]
    if len(sys.argv) > 3:
        remaining = remaining[: int(sys.argv[3])]
    print(f"browser pass: {len(remaining)} to load ({len(results)} already done)", flush=True)

    b.fetch_html_with_reason = browser_fetch  # crawl_school looks this up at call time
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        for index, row in enumerate(remaining, start=len(results) + 1):
            try:
                result = b.crawl_school(row, rps=0, timeout=25, retries=0, variants=False)
            except Exception as exc:
                result = b._review_row(row, "unclear", notes=f"crawl_error:{type(exc).__name__}")
            results.append(result)
            b.write_review_csv(out, results)
            print(f"[{index}/{len(selected)}] {result['name']} ... {result['cds']} {result.get('url') or ''} | {result['notes'][:90]}", flush=True)
        browser.close()
    counts: dict[str, int] = {}
    for r in results:
        counts[r["cds"]] = counts.get(r["cds"], 0) + 1
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
