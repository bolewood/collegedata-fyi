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
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

try:
    import requests
except ImportError:  # pragma: no cover - optional in pure unit-test environments
    requests = None  # type: ignore[assignment]

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.finder.identity_guard import (  # noqa: E402
    resolve_canonical_school_id,
    validated_canonical_alias_slug_map,
    validated_unique_school_claim_slug_map,
)

DEFAULT_CATALOG = Path(__file__).resolve().parent / "catalog.json"
DEFAULT_LOG = Path(__file__).resolve().parent / "ingest-log.jsonl"
PROVENANCE_TAG = "mirror_college_transitions"


def canonicalize_catalog_entries(
    entries: Iterable[Mapping[str, Any]],
    *,
    canonical_by_ipeds: Mapping[str, str] | None = None,
    canonical_by_alias: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Resolve every catalog entry's school_id to its canonical public slug."""
    by_ipeds = (
        dict(canonical_by_ipeds)
        if canonical_by_ipeds is not None
        else validated_unique_school_claim_slug_map()
    )
    by_alias = (
        dict(canonical_by_alias)
        if canonical_by_alias is not None
        else validated_canonical_alias_slug_map()
    )
    merged: dict[str, dict[str, Any]] = {}
    for raw in entries:
        entry = dict(raw)
        canonical_id = resolve_canonical_school_id(
            entry.get("school_id"),
            ipeds_id=entry.get("ipeds_id"),
            canonical_by_ipeds=by_ipeds,
            canonical_by_alias=by_alias,
        )
        entry["school_id"] = canonical_id
        existing = merged.get(canonical_id)
        if existing is None:
            entry["years"] = dict(entry.get("years") or {})
            merged[canonical_id] = entry
        else:
            combined_years = dict(existing.get("years") or {})
            for year, url in (entry.get("years") or {}).items():
                combined_years.setdefault(year, url)
            existing["years"] = combined_years
    return [merged[key] for key in sorted(merged)]


def valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and "." in parsed.hostname
        )
    except Exception:
        return False


def build_ingest_tasks(
    entries: Iterable[Mapping[str, Any]],
    existing_years: Mapping[str, set[str]],
    *,
    canonical_by_ipeds: Mapping[str, str] | None = None,
    canonical_by_alias: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build gap tasks after resolving every entry and existing row to canonical slugs."""
    by_ipeds = (
        dict(canonical_by_ipeds)
        if canonical_by_ipeds is not None
        else validated_unique_school_claim_slug_map()
    )
    by_alias = (
        dict(canonical_by_alias)
        if canonical_by_alias is not None
        else validated_canonical_alias_slug_map()
    )
    canonical_entries = canonicalize_catalog_entries(
        entries,
        canonical_by_ipeds=by_ipeds,
        canonical_by_alias=by_alias,
    )
    canonical_have: dict[str, set[str]] = {}
    for raw_sid, years in existing_years.items():
        canonical_sid = resolve_canonical_school_id(
            raw_sid,
            canonical_by_ipeds=by_ipeds,
            canonical_by_alias=by_alias,
        )
        canonical_have.setdefault(canonical_sid, set()).update(years)

    tasks: list[dict[str, Any]] = []
    total_ct_pairs = 0
    skipped_have = 0
    skipped_malformed = 0
    for entry in canonical_entries:
        sid = entry["school_id"]
        for year, drive_url in (entry.get("years") or {}).items():
            total_ct_pairs += 1
            if year in canonical_have.get(sid, set()):
                skipped_have += 1
                continue
            if not valid_url(drive_url):
                skipped_malformed += 1
                continue
            tasks.append(
                {
                    "school_id": sid,
                    "school_name": entry["school_name"],
                    "year": year,
                    "drive_url": drive_url,
                }
            )
    return tasks, {
        "total_ct_pairs": total_ct_pairs,
        "skipped_have": skipped_have,
        "skipped_malformed": skipped_malformed,
    }


def fetch_existing_years(
    sb,
    school_ids: list[str],
    *,
    canonical_by_alias: Mapping[str, str] | None = None,
) -> dict[str, set[str]]:
    """Return {canonical_school_id: {years_we_have}} across ALL provenance values.

    Mirror ingest never overwrites — if a row exists with any provenance
    (school_direct, another mirror, operator_manual), skip.
    """
    by_alias = (
        dict(canonical_by_alias)
        if canonical_by_alias is not None
        else validated_canonical_alias_slug_map()
    )
    canonical_ids = [
        resolve_canonical_school_id(sid, canonical_by_alias=by_alias)
        for sid in school_ids
    ]
    have: dict[str, set[str]] = {sid: set() for sid in canonical_ids}
    query_ids = sorted(
        set(canonical_ids)
        | {
            alias
            for alias, target in by_alias.items()
            if target in have
        }
    )
    if not query_ids:
        return have
    page_size = 1000
    offset = 0
    while True:
        batch = sb.table("cds_documents").select(
            "school_id, cds_year, detected_year"
        ).in_("school_id", query_ids).is_("removed_at", "null").range(
            offset, offset + page_size - 1
        ).execute().data or []
        for row in batch:
            sid = resolve_canonical_school_id(
                row["school_id"],
                canonical_by_alias=by_alias,
            )
            have.setdefault(sid, set())
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
    *,
    canonical_by_ipeds: Mapping[str, str] | None = None,
    canonical_by_alias: Mapping[str, str] | None = None,
) -> dict:
    by_ipeds = (
        dict(canonical_by_ipeds)
        if canonical_by_ipeds is not None
        else validated_unique_school_claim_slug_map()
    )
    by_alias = (
        dict(canonical_by_alias)
        if canonical_by_alias is not None
        else validated_canonical_alias_slug_map()
    )
    school_id = resolve_canonical_school_id(
        school_id,
        canonical_by_ipeds=by_ipeds,
        canonical_by_alias=by_alias,
    )
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

    canonical_by_ipeds = validated_unique_school_claim_slug_map()
    canonical_by_alias = validated_canonical_alias_slug_map()
    catalog = json.loads(Path(args.catalog).read_text())
    entries = canonicalize_catalog_entries(
        catalog["entries"],
        canonical_by_ipeds=canonical_by_ipeds,
        canonical_by_alias=canonical_by_alias,
    )
    if args.school:
        target_school = resolve_canonical_school_id(
            args.school,
            canonical_by_ipeds=canonical_by_ipeds,
            canonical_by_alias=canonical_by_alias,
        )
        entries = [e for e in entries if e["school_id"] == target_school]
    print(f"CT catalog: {catalog['school_count_matched']} matched schools, "
          f"{catalog['file_count']} files")
    print(f"Filtered to: {len(entries)} schools")

    if load_dotenv is not None:
        load_dotenv(args.env)
    base_url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb = create_client(base_url, key)

    have = fetch_existing_years(
        sb,
        [e["school_id"] for e in entries],
        canonical_by_alias=canonical_by_alias,
    )
    have_count = sum(len(v) for v in have.values())
    print(f"Existing cds_documents rows across these schools: {have_count}")

    tasks, stats = build_ingest_tasks(
        entries,
        have,
        canonical_by_ipeds=canonical_by_ipeds,
        canonical_by_alias=canonical_by_alias,
    )
    print(f"CT (school, year) pairs: {stats['total_ct_pairs']}")
    print(f"  Already in our archive (skip): {stats['skipped_have']}")
    print(f"  Malformed URL on CT side (skip): {stats['skipped_malformed']}")
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
