#!/usr/bin/env python3
"""Ingest College Transitions CDS mirror into our archive.

Reads catalog.json (produced by fetch.py), cross-references against
cds_documents, and for each (school, year) gap we don't already have,
POSTs the CT Drive URL to archive-process?POST force_urls with
source_provenance='mirror_college_transitions'.

Idempotent — if the row already exists in any provenance, it's
skipped. The mirror never overwrites or refreshes existing data; it's
a gap-filler only. Policy detail lives in tools/mirrors/README.md.

Usage:
    python tools/mirrors/college_transitions/ingest.py --dry-run        # show what would happen
    python tools/mirrors/college_transitions/ingest.py                  # live ingest
    python tools/mirrors/college_transitions/ingest.py --concurrency 4
    python tools/mirrors/college_transitions/ingest.py --limit 10       # smoke-test
    python tools/mirrors/college_transitions/ingest.py --school yale    # one school, all years
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = Path(__file__).resolve().parent / "catalog.json"
DEFAULT_LOG = Path(__file__).resolve().parent / "ingest-log.jsonl"
PROVENANCE_TAG = "mirror_college_transitions"


def fetch_existing_years(sb, school_ids: list[str]) -> dict[str, set[str]]:
    """Return {school_id: {years_we_have}} across ALL provenance values.

    Mirror ingest never overwrites — if a row exists with any provenance
    (school_direct, another mirror, operator_manual), skip.
    """
    have: dict[str, set[str]] = {sid: set() for sid in school_ids}
    page_size = 1000
    offset = 0
    while True:
        batch = sb.table("cds_documents").select(
            "school_id, cds_year, detected_year"
        ).in_("school_id", school_ids).range(
            offset, offset + page_size - 1
        ).execute().data or []
        for row in batch:
            sid = row["school_id"]
            # Count both cds_year and detected_year to avoid re-archiving
            # the same file under a slightly different year label.
            if row.get("cds_year"):
                have[sid].add(row["cds_year"])
            if row.get("detected_year"):
                have[sid].add(row["detected_year"])
        if len(batch) < page_size:
            break
        offset += page_size
    return have


def post_force_urls(
    base_url: str,
    key: str,
    school_id: str,
    school_name: str,
    items: list[dict],
    timeout: int,
) -> dict:
    started = time.monotonic()
    try:
        resp = requests.post(
            f"{base_url}/functions/v1/archive-process",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "school_id": school_id,
                "school_name": school_name,
                "urls": items,
                "source_provenance": PROVENANCE_TAG,
            },
            timeout=timeout,
        )
        elapsed = round(time.monotonic() - started, 1)
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text[:500]}
        return {
            "school_id": school_id,
            "http_status": resp.status_code,
            "elapsed_sec": elapsed,
            "payload": payload,
            "url_count": len(items),
        }
    except requests.Timeout:
        return {
            "school_id": school_id,
            "http_status": None,
            "elapsed_sec": round(time.monotonic() - started, 1),
            "payload": {"error": "client_timeout"},
            "url_count": len(items),
        }
    except Exception as e:
        return {
            "school_id": school_id,
            "http_status": None,
            "elapsed_sec": round(time.monotonic() - started, 1),
            "payload": {"error": f"client_exception: {e}"},
            "url_count": len(items),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest CT mirror catalog into our archive")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--school", default=None, help="Only ingest this one school_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    catalog = json.loads(Path(args.catalog).read_text())
    entries = catalog["entries"]
    if args.school:
        entries = [e for e in entries if e["school_id"] == args.school]
    print(f"CT catalog: {catalog['school_count_matched']} matched schools, "
          f"{catalog['file_count']} files")
    print(f"Filtered to: {len(entries)} schools")

    load_dotenv(args.env)
    base_url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb = create_client(base_url, key)

    have = fetch_existing_years(sb, [e["school_id"] for e in entries])
    have_count = sum(len(v) for v in have.values())
    print(f"Existing cds_documents rows across these schools: {have_count}")

    # URL-shape sanity: CT's table occasionally has malformed entries
    # (e.g., 'http://v/' seen on Bennington 2019-20). Drop these before
    # POST so the edge function doesn't waste a call on DNS errors.
    from urllib.parse import urlparse
    def valid_url(u: str) -> bool:
        try:
            p = urlparse(u)
            return p.scheme in ("http", "https") and bool(p.hostname) and "." in p.hostname
        except Exception:
            return False

    # Build gap list: (school, year, drive_url) we don't have
    tasks: list[dict] = []
    total_ct_pairs = 0
    skipped_have = 0
    skipped_malformed = 0
    for e in entries:
        for year, drive_url in e["years"].items():
            total_ct_pairs += 1
            if year in have.get(e["school_id"], set()):
                skipped_have += 1
                continue
            if not valid_url(drive_url):
                skipped_malformed += 1
                continue
            tasks.append({
                "school_id": e["school_id"],
                "school_name": e["school_name"],
                "year": year,
                "drive_url": drive_url,
            })
    print(f"CT (school, year) pairs: {total_ct_pairs}")
    print(f"  Already in our archive (skip): {skipped_have}")
    print(f"  Malformed URL on CT side (skip): {skipped_malformed}")
    print(f"  Gaps to ingest: {len(tasks)}")

    if args.limit:
        tasks = tasks[: args.limit]
        print(f"  Limited to first {len(tasks)}")

    if args.dry_run:
        print("\n(dry-run; not calling force_urls)")
        print("Sample first 10 gaps:")
        for t in tasks[:10]:
            print(f"  {t['school_id']:<35} {t['year']}  {t['drive_url']}")
        return 0

    # Group tasks by school so each POST covers all years for that school.
    # force_urls in one call handles multiple URLs efficiently.
    by_school: dict[str, list[dict]] = {}
    school_names: dict[str, str] = {}
    for t in tasks:
        by_school.setdefault(t["school_id"], []).append(
            {"url": t["drive_url"], "year": t["year"]}
        )
        school_names[t["school_id"]] = t["school_name"]

    print(f"\nSchools to call: {len(by_school)}")
    print(f"Concurrency: {args.concurrency}, timeout: {args.timeout}s per call\n")

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fp = open(log_path, "w")

    summary = {"ok": 0, "error": 0}
    started = time.monotonic()
    completed = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {
            ex.submit(
                post_force_urls,
                base_url, key, school_id, school_names[school_id], items, args.timeout,
            ): school_id
            for school_id, items in by_school.items()
        }
        for fut in as_completed(futures):
            school_id = futures[fut]
            res = fut.result()
            log_fp.write(json.dumps(res) + "\n")
            log_fp.flush()
            ok = res["http_status"] == 200
            summary["ok" if ok else "error"] += 1
            completed += 1
            elapsed = time.monotonic() - started
            rate = completed / elapsed if elapsed else 0
            eta_min = (len(by_school) - completed) / rate / 60 if rate else 0
            action = (res["payload"] or {}).get("outcome", {}).get("action") or res["payload"].get("error_class") or "?"
            print(
                f"  [{completed}/{len(by_school)}] {school_id[:30]:<30} "
                f"urls={res['url_count']:>2}  http={res['http_status']}  "
                f"{str(action)[:25]:<25} ({res['elapsed_sec']}s)  eta={eta_min:.1f}m",
                flush=True,
            )

    log_fp.close()
    print(f"\n=== Summary ===")
    print(f"  OK: {summary['ok']}")
    print(f"  errors: {summary['error']}")
    print(f"  log: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
