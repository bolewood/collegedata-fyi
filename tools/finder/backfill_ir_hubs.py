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

    # Slower recrawl of prior unclear homepage failures:
    python tools/finder/backfill_ir_hubs.py \\
      --from-csv tools/finder/audits/ir-hub-backfill-2026-11/missing_in_scope.csv \\
      --from-review tools/finder/audits/ir-hub-backfill-2026-11/review.csv \\
      --timeout 25 --retries 2 --try-url-variants --resume \\
      --rps 0.5 --school-deadline 360 \\
      --out scratch/ir-hub-backfill/recrawl/review.csv

Do not run this against production archive as part of a PR. Operator
dispatch: GitHub Actions workflow `ops-ir-hub-backfill.yml`.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

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
    MAX_VALIDATION_BYTES,
    _dns_ok,
    _get_bounded,
    html_has_cds_content_or_anchors,
    is_cds_page,
)

ROOT = Path(__file__).parent
SCHOOLS_YAML = ROOT / "schools.yaml"
DEFAULT_OUT = _REPO_ROOT / "scratch" / "ir-hub-backfill" / "review.csv"
REVIEW_FIELDS = ["school_id", "name", "ipeds_id", "cds", "url", "notes"]
RECRAWL_NOTE_MARKERS = (
    "homepage_unreachable",
    "homepage_fail",
    "dns_miss",
    "crawl_error",
)
HTML_RE = re.compile(br"(?is)<!doctype\s+html|<html(?:\s|>)")


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
        selected.append(_identity_row(row, yaml_by_ipeds.get(unitid) or {}))
    selected.sort(
        key=lambda row: (
            0 if row.get("archive_last_outcome") == "no_pdfs_found" else 1,
            str(row.get("name") or "").lower(),
        )
    )
    return selected


def _identity_row(csv_row: dict, yaml_row: dict) -> dict:
    unitid = str(csv_row.get("unitid") or csv_row.get("ipeds_id") or "").strip()
    return {
        "school_id": yaml_row.get("id") or csv_row.get("school_id") or "",
        "name": yaml_row.get("name") or csv_row.get("name") or "",
        "ipeds_id": unitid,
        "domain": yaml_row.get("domain")
        or csv_row.get("website_domain")
        or csv_row.get("domain")
        or "",
        "website_url": csv_row.get("website_url") or "",
        "archive_last_outcome": csv_row.get("archive_last_outcome") or "",
        "coverage_status": csv_row.get("coverage_status") or "",
    }


def select_recrawl_unitids(
    review_rows: list[dict],
    markers: tuple[str, ...] = RECRAWL_NOTE_MARKERS,
) -> set[str]:
    """UNITIDs whose prior review notes look like timeout / DNS / crawl errors."""
    wanted: set[str] = set()
    for row in review_rows:
        if str(row.get("cds") or "") != "unclear":
            continue
        notes = str(row.get("notes") or "")
        if any(marker in notes for marker in markers):
            unitid = str(row.get("ipeds_id") or "").strip()
            if unitid:
                wanted.add(unitid)
    return wanted


def rows_for_unitids(
    csv_rows: list[dict],
    yaml_schools: list[dict],
    unitids: set[str],
) -> list[dict]:
    """Build crawl rows for an explicit UNITID set, ignoring archive-outcome filters."""
    yaml_by_ipeds = {
        str(school.get("ipeds_id") or "").strip('"'): school
        for school in yaml_schools
        if school.get("ipeds_id")
    }
    selected: list[dict] = []
    seen: set[str] = set()
    for row in csv_rows:
        unitid = str(row.get("unitid") or row.get("ipeds_id") or "").strip()
        if not unitid or unitid in seen or unitid not in unitids:
            continue
        seen.add(unitid)
        selected.append(_identity_row(row, yaml_by_ipeds.get(unitid) or {}))
    selected.sort(key=lambda row: str(row.get("name") or "").lower())
    return selected


def sanitize_url(url: str) -> str:
    """Add a scheme if missing and percent-encode spaces in the path."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        return raw
    path = quote(unquote(parsed.path or "/"), safe="/%")
    query = quote(unquote(parsed.query), safe="=&%")
    return urlunparse(
        (parsed.scheme, parsed.netloc, path, "", query, parsed.fragment)
    )


def homepage_start_urls(
    website: str,
    domain: str,
    *,
    variants: bool = False,
) -> list[str]:
    """Homepage candidates. With variants, also try http and www/non-www."""
    urls: list[str] = []

    def add(raw: str) -> None:
        cleaned = sanitize_url(raw)
        if cleaned and cleaned not in urls:
            urls.append(cleaned)

    if website:
        add(website)
        if variants:
            parsed = urlparse(sanitize_url(website))
            host = parsed.hostname or ""
            path = parsed.path or "/"
            scheme = parsed.scheme or "https"
            if host.startswith("www."):
                add(f"{scheme}://{host[4:]}{path}")
            elif host:
                add(f"{scheme}://www.{host}{path}")
            other = "http" if scheme == "https" else "https"
            if host:
                add(f"{other}://{host}{path}")
                if host.startswith("www."):
                    add(f"{other}://{host[4:]}{path}")
                else:
                    add(f"{other}://www.{host}{path}")
    if domain:
        add(f"https://www.{domain}/")
        add(f"https://{domain}/")
        if variants:
            add(f"http://www.{domain}/")
            add(f"http://{domain}/")
    return urls


def classify_page(url: str, html: str) -> str:
    """yes if the page hosts CDS content or anchors, else no."""
    body = html.encode("utf-8", errors="ignore")
    if is_cds_page(body, "text/html") or html_has_cds_content_or_anchors(body):
        return "yes"
    return "no"


def dns_ok_bounded(host: str, timeout: float = 2.0) -> bool:
    """Bound DNS so a black-holed resolver cannot stall a school."""
    if not host:
        return False
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_dns_ok, host)
    try:
        return bool(future.result(timeout=timeout))
    except Exception:
        return False
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _get_bounded_worker(url: str, timeout: int, conn) -> None:
    """Child process for a single fetch so hung TLS can be SIGKILL'd."""
    import socket

    socket.setdefaulttimeout(timeout)
    try:
        conn.send(
            _get_bounded(url, timeout=timeout, max_bytes=MAX_VALIDATION_BYTES)
        )
    except Exception as exc:
        conn.send(exc)
    finally:
        conn.close()


def get_bounded_or_kill(url: str, timeout: int):
    """Like `_get_bounded`, but kill the worker if it ignores the socket timeout."""
    parent, child = mp.Pipe(duplex=False)
    proc = mp.Process(
        target=_get_bounded_worker, args=(url, timeout, child), daemon=True,
    )
    proc.start()
    child.close()
    if parent.poll(timeout + 3.0):
        result = parent.recv()
        proc.join(2)
        if isinstance(result, Exception):
            raise result
        return result
    proc.terminate()
    proc.join(3)
    if proc.is_alive():
        proc.kill()
        proc.join(2)
    return -1, {}, b"", url, False


def fetch_html_with_reason(
    url: str,
    timeout: int,
) -> tuple[tuple[str, str] | None, str]:
    """Fetch HTML. On failure, return a short reason for the review notes."""
    cleaned = sanitize_url(url)
    if not cleaned:
        return None, "empty_url"
    started = time.monotonic()
    try:
        status, headers, body, final_url, _truncated = get_bounded_or_kill(
            cleaned, timeout,
        )
    except Exception as exc:
        return None, f"{type(exc).__name__}:{cleaned}"
    elapsed = time.monotonic() - started
    if status == -1:
        kind = "timeout" if elapsed >= timeout * 0.8 else "network"
        return None, f"{kind}:{cleaned}"
    if status != 200:
        return None, f"http_{status}:{cleaned}"
    content_type = headers.get("content-type", "").lower()
    looks_html = "html" in content_type or bool(HTML_RE.search(body[:4096]))
    if not looks_html:
        return None, f"not_html:{cleaned}"
    return (final_url or cleaned, body.decode("utf-8", errors="ignore")), ""


class RequestPacer:
    """Keep request *starts* at or below rps. Timeouts make the run slower."""

    def __init__(self, rps: float) -> None:
        self.slot = (1.0 / rps) if rps > 0 else 0.0
        self.next_at = 0.0

    def wait(self) -> None:
        if self.slot <= 0:
            return
        now = time.monotonic()
        wait = self.next_at - now
        if wait > self.slot + 0.5:
            wait = 0
            self.next_at = now
        if wait > 0:
            time.sleep(wait)
        self.next_at = time.monotonic() + self.slot


def fetch_with_retries(
    url: str,
    *,
    timeout: int,
    retries: int,
    backoff: float,
    pacer: RequestPacer,
) -> tuple[tuple[str, str] | None, str]:
    """Retry timeouts/network errors with exponential backoff. Do not retry HTTP 4xx."""
    last_reason = ""
    attempts = max(1, retries + 1)
    for attempt in range(attempts):
        pacer.wait()
        fetched, reason = fetch_html_with_reason(url, timeout)
        if fetched:
            return fetched, ""
        last_reason = reason
        kind = reason.split(":", 1)[0]
        if kind not in {"timeout", "network"} or attempt == attempts - 1:
            break
        time.sleep(backoff * (2 ** attempt))
    return None, last_reason


def _review_row(
    row: dict,
    cds: str,
    url: str = "",
    notes: str = "",
) -> dict:
    return {
        "school_id": row.get("school_id") or "",
        "name": row.get("name") or "",
        "ipeds_id": row.get("ipeds_id") or "",
        "cds": cds,
        "url": url,
        "notes": notes,
    }


def crawl_school(
    row: dict,
    rps: float,
    *,
    timeout: int = 10,
    retries: int = 0,
    backoff: float = 2.0,
    variants: bool = False,
) -> dict:
    """Fetch homepage + IR hubs. Never writes. Returns a review row."""
    pacer = RequestPacer(rps)
    domain = str(row.get("domain") or "")
    website = str(row.get("website_url") or "")
    start_urls = homepage_start_urls(website, domain, variants=variants)

    homepage_url = ""
    homepage_html = ""
    notes: list[str] = []
    dns_tried: set[str] = set()
    timeout_hosts: set[str] = set()
    for index, url in enumerate(start_urls):
        host = urlparse(url).hostname or ""
        if host and host not in dns_tried:
            dns_tried.add(host)
            if not dns_ok_bounded(host):
                notes.append(f"dns_miss:{host}")
                continue
        elif host and f"dns_miss:{host}" in notes:
            continue
        if host in timeout_hosts:
            notes.append(f"skip_after_timeout:{url}")
            continue
        # Retries apply to the first homepage URL; later http/www variants
        # are extra chances, not 3x each on a black-holed host.
        fetched, reason = fetch_with_retries(
            url,
            timeout=timeout,
            retries=retries if index == 0 else 0,
            backoff=backoff,
            pacer=pacer,
        )
        if fetched:
            homepage_url, homepage_html = fetched
            break
        notes.append(f"homepage_fail:{reason}")
        if reason.startswith("timeout:") and host:
            timeout_hosts.add(host)

    if not homepage_html:
        return _review_row(row, "unclear", notes="homepage_unreachable " + " ".join(notes))

    if classify_page(homepage_url, homepage_html) == "yes":
        return _review_row(row, "yes", homepage_url, "cds_on_homepage")

    about_pages: list[tuple[str, str]] = []
    for about_url in extract_about_links(homepage_html, homepage_url)[:MAX_ABOUT_PAGES]:
        fetched, reason = fetch_with_retries(
            about_url, timeout=timeout, retries=0, backoff=backoff, pacer=pacer,
        )
        if not fetched:
            notes.append(f"about_fail:{reason}")
            continue
        about_final, about_html = fetched
        about_pages.append((about_final, about_html))
        if classify_page(about_final, about_html) == "yes":
            return _review_row(row, "yes", about_final, "cds_on_about_page")

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
        host = urlparse(sanitize_url(hub)).hostname or ""
        if host and not dns_ok_bounded(host):
            continue
        fetched, reason = fetch_with_retries(
            hub, timeout=timeout, retries=0, backoff=backoff, pacer=pacer,
        )
        if not fetched:
            notes.append(f"hub_fail:{reason}")
            unclear = True
            continue
        final_url, html = fetched
        if classify_page(final_url, html) == "yes":
            return _review_row(row, "yes", final_url, "cds_on_ir_hub")

    return _review_row(
        row,
        "unclear" if unclear and not hubs else "no",
        homepage_url,
        " ".join(notes) or "no_cds_on_ir_hubs",
    )


def _crawl_worker(row: dict, conn, kwargs: dict) -> None:
    try:
        conn.send(crawl_school(row, **kwargs))
    except Exception as exc:
        conn.send(_review_row(row, "unclear", notes=f"crawl_error:{type(exc).__name__}"))
    finally:
        conn.close()


def crawl_school_bounded(row: dict, deadline: float, kwargs: dict) -> dict:
    """Kill a school that ignores socket timeouts (stuck TLS/connect)."""
    if deadline <= 0:
        return crawl_school(row, **kwargs)
    parent, child = mp.Pipe(duplex=False)
    # Not a daemon: each fetch runs in its own child process, and a daemonic
    # process may not start children (every fetch then failed with
    # AssertionError). A school killed at its deadline can leave one fetch
    # child behind; that child ends on its own within the request timeout.
    proc = mp.Process(target=_crawl_worker, args=(row, child, kwargs), daemon=False)
    proc.start()
    child.close()
    proc.join(deadline)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            proc.kill()
            proc.join(2)
        return _review_row(row, "unclear", notes="school_deadline_exceeded")
    if parent.poll(1):
        return parent.recv()
    return _review_row(row, "unclear", notes="school_deadline_no_result")


def write_review_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path | None, rows: list[dict], out: Path) -> dict:
    counts = {"yes": 0, "no": 0, "unclear": 0}
    for row in rows:
        counts[str(row.get("cds") or "unclear")] = (
            counts.get(str(row.get("cds") or "unclear"), 0) + 1
        )
    summary = {
        "schools": len(rows),
        "yes": counts.get("yes", 0),
        "no": counts.get("no", 0),
        "unclear": counts.get("unclear", 0),
        "out": str(out),
        "published": False,
    }
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def load_existing_review(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    found: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            unitid = str(row.get("ipeds_id") or "").strip()
            if unitid:
                found[unitid] = {field: row.get(field) or "" for field in REVIEW_FIELDS}
    return found


def main() -> int:
    ap = argparse.ArgumentParser(
        description="IR-hub backfill review crawl. Does not publish or archive."
    )
    ap.add_argument("--from-csv", type=Path, required=True,
                    help="missing-schools CSV with archive_last_outcome / website_url")
    ap.add_argument("--from-review", type=Path,
                    help="Prior review.csv; recrawl unclear timeout/DNS/crawl_error rows")
    ap.add_argument("--schools-yaml", type=Path, default=SCHOOLS_YAML)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=0, help="Max schools (0=all)")
    ap.add_argument("--rps", type=float, default=0.5,
                    help="Requests per second (default 0.5, polite)")
    ap.add_argument("--only", help="Comma-separated school ids or UNITIDs")
    ap.add_argument("--summary-json", type=Path)
    ap.add_argument("--timeout", type=int, default=10,
                    help="Per-request HTTP timeout in seconds (default 10)")
    ap.add_argument("--retries", type=int, default=0,
                    help="Retries on timeout/network errors (default 0)")
    ap.add_argument("--backoff", type=float, default=2.0,
                    help="Initial retry backoff seconds; doubles each retry")
    ap.add_argument("--try-url-variants", action="store_true",
                    help="Try https/http and www/non-www homepage variants")
    ap.add_argument("--resume", action="store_true",
                    help="Skip UNITIDs already present in --out")
    ap.add_argument("--school-deadline", type=float, default=0,
                    help="Kill one school after N seconds (0=disabled)")
    args = ap.parse_args()

    csv_rows = list(csv.DictReader(args.from_csv.open(newline="", encoding="utf-8")))
    yaml_schools = yaml.safe_load(args.schools_yaml.read_text()).get("schools", [])
    if args.from_review:
        review_rows = list(
            csv.DictReader(args.from_review.open(newline="", encoding="utf-8"))
        )
        unitids = select_recrawl_unitids(review_rows)
        selected = rows_for_unitids(csv_rows, yaml_schools, unitids)
    else:
        selected = select_backfill_rows(csv_rows, yaml_schools)
    if args.only:
        wanted = {part.strip() for part in args.only.split(",") if part.strip()}
        selected = [
            row for row in selected
            if row.get("school_id") in wanted or row.get("ipeds_id") in wanted
        ]
    if args.limit:
        selected = selected[: args.limit]

    done_by_id: dict[str, dict] = {}
    if args.resume:
        done_by_id = load_existing_review(args.out)
    remaining = [
        row for row in selected
        if str(row.get("ipeds_id") or "") not in done_by_id
    ]
    results = [done_by_id[str(row.get("ipeds_id") or "")] for row in selected
               if str(row.get("ipeds_id") or "") in done_by_id]

    crawl_kwargs = {
        "rps": args.rps,
        "timeout": args.timeout,
        "retries": args.retries,
        "backoff": args.backoff,
        "variants": args.try_url_variants,
    }
    print(
        f"IR-hub backfill: {len(remaining)} to crawl "
        f"({len(results)} already in --out), rps={args.rps}, "
        f"timeout={args.timeout}s, retries={args.retries}, "
        f"variants={args.try_url_variants}",
        flush=True,
    )
    print("This run writes a review CSV only. It does not archive or edit yaml.",
          flush=True)

    write_review_csv(args.out, results)
    total = len(results) + len(remaining)
    for index, row in enumerate(remaining, start=len(results) + 1):
        result = crawl_school_bounded(row, args.school_deadline, crawl_kwargs)
        results.append(result)
        write_review_csv(args.out, results)
        summary = write_summary(args.summary_json, results, args.out)
        print(
            f"[{index}/{total}] {result['name']} ... "
            f"{result['cds']} {result.get('url') or ''}",
            flush=True,
        )

    summary = write_summary(args.summary_json, results, args.out)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
