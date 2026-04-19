#!/usr/bin/env python3
"""Force-resolve active schools that have no recent CDS docs in the DB.

Calls the archive-process Edge Function with ?force_school=<id> for each
school in the target set, captures the outcome, and writes a JSONL log so
the failures can be categorised.

Default target set: active schools (scrape_policy = "active" in
schools.yaml) with zero published cds_documents rows for any of the
target years (default 2022-23..2025-26).

Usage:
    python tools/data_quality/force_resolve_missing.py --dry-run
    python tools/data_quality/force_resolve_missing.py --concurrency 4
    python tools/data_quality/force_resolve_missing.py --limit 10  # smoke-test
    python tools/data_quality/force_resolve_missing.py --include-partial  # also retry schools missing 1-3 years
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
import yaml
from dotenv import load_dotenv
from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
DEFAULT_YEARS = ["2022-23", "2023-24", "2024-25", "2025-26"]
DEFAULT_LOG = REPO_ROOT / "tools" / "data_quality" / "force-resolve-results.jsonl"


def load_active_schools_with_hints() -> list[dict]:
    with open(SCHOOLS_YAML) as fp:
        data = yaml.safe_load(fp)
    out = []
    for s in data.get("schools", []):
        if s.get("scrape_policy") != "active":
            continue
        if not s.get("cds_url_hint"):
            continue
        # archive-process explicitly excludes schools with sub_institutions in V1
        if s.get("sub_institutions"):
            continue
        out.append(s)
    return out


def fetch_published_years(sb, school_ids: list[str], years: list[str]) -> dict[str, set[str]]:
    have: dict[str, set[str]] = {sid: set() for sid in school_ids}
    page_size = 1000
    offset = 0
    while True:
        batch = sb.table("cds_documents").select(
            "school_id, cds_year, participation_status"
        ).in_("cds_year", years).range(offset, offset + page_size - 1).execute().data or []
        for row in batch:
            sid = row["school_id"]
            if sid in have and row.get("participation_status") == "published":
                have[sid].add(row["cds_year"])
        if len(batch) < page_size:
            break
        offset += page_size
    return have


def call_force_school(base_url: str, key: str, school_id: str, timeout: int) -> dict:
    started = time.monotonic()
    try:
        resp = requests.post(
            f"{base_url}/functions/v1/archive-process",
            params={"force_school": school_id},
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
        elapsed = time.monotonic() - started
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text[:500]}
        return {
            "school_id": school_id,
            "http_status": resp.status_code,
            "elapsed_sec": round(elapsed, 1),
            "payload": payload,
        }
    except requests.Timeout:
        return {
            "school_id": school_id,
            "http_status": None,
            "elapsed_sec": round(time.monotonic() - started, 1),
            "payload": {"error": "client_timeout"},
        }
    except Exception as e:
        return {
            "school_id": school_id,
            "http_status": None,
            "elapsed_sec": round(time.monotonic() - started, 1),
            "payload": {"error": f"client_exception: {e}"},
        }


def categorise(payload: dict) -> str:
    """Bucket the outcome into a small set of human labels.

    Preferred path (post-PR 2): the API response surfaces a structured
    `outcome` field at the top level (failure path) or under `outcome.outcome`
    (success path). Either is the canonical ProbeOutcome category written by
    the Deno pipeline — no string matching needed.

    Fallback path: pre-PR-2 responses or unexpected shapes still get
    classified by the legacy heuristics so historical JSONL files are
    readable.
    """
    if not isinstance(payload, dict):
        return "unknown"

    # Client-side issues (the Python wrapper, not the API)
    if "error" in payload and "error_class" not in payload:
        err = str(payload.get("error", "")).lower()
        if "client_timeout" in err: return "client_timeout"
        if "not found in archivable" in err: return "not_archivable"
        return "unknown_error"

    # Post-PR-2 structured outcome (failure path)
    if isinstance(payload.get("outcome"), str):
        return payload["outcome"]

    # Post-PR-2 structured outcome (success path: outcome is the
    # ArchiveOutcome object; outcome.outcome is the ProbeOutcome string)
    outcome_obj = payload.get("outcome")
    if isinstance(outcome_obj, dict):
        if isinstance(outcome_obj.get("outcome"), str):
            return outcome_obj["outcome"]
        # Pre-PR-2 ArchiveOutcome only had .action — fall back
        action = outcome_obj.get("action") or ""
        if action:
            if "archived" in action or "saved" in action or "documents" in action:
                return "success"
            if "no_change" in action: return "no_change"
            return f"outcome:{action}"[:40]

    # Legacy fallback for pre-PR-2 error payloads (no structured outcome)
    cls = payload.get("error_class")
    if cls == "PermanentError":
        err = str(payload.get("error", "")).lower()
        if "login.microsoftonline" in err or "saml" in err: return "auth_walled_microsoft"
        if "okta" in err: return "auth_walled_okta"
        if "google.com/sso" in err or "accounts.google.com" in err: return "auth_walled_google"
        if "404" in err or "410" in err: return "dead_url"
        if "no candidate" in err or "no anchors" in err or "no document" in err: return "no_pdfs_found"
        if "magic" in err: return "wrong_content_type"
        return "permanent_other"
    if cls == "TransientError":
        return "transient"
    return f"class:{cls}" if cls else "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Force-resolve active schools with no recent CDS docs")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--years", default=",".join(DEFAULT_YEARS))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180, help="Per-call HTTP timeout (seconds)")
    parser.add_argument("--limit", type=int, default=None, help="Smoke-test: cap the number of schools called")
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="JSONL output path")
    parser.add_argument("--include-partial", action="store_true",
                        help="Also retry schools missing 1-3 of the target years (default: only fully-missing)")
    parser.add_argument("--dry-run", action="store_true", help="Print the target list without calling")
    args = parser.parse_args()

    years = [y.strip() for y in args.years.split(",") if y.strip()]
    log_path = Path(args.log)

    load_dotenv(args.env)
    base_url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb = create_client(base_url, key)

    schools = load_active_schools_with_hints()
    have = fetch_published_years(sb, [s["id"] for s in schools], years)

    targets: list[dict] = []
    for s in schools:
        present = have.get(s["id"], set())
        missing_count = sum(1 for y in years if y not in present)
        if args.include_partial and missing_count >= 1:
            targets.append(s)
        elif (not args.include_partial) and missing_count == len(years):
            targets.append(s)
    targets.sort(key=lambda s: s["id"])

    if args.limit:
        targets = targets[: args.limit]

    print(f"Active schools (no sub-institutions, has hint): {len(schools)}")
    print(f"Target schools to force-resolve: {len(targets)}")
    print(f"Concurrency: {args.concurrency}, per-call timeout: {args.timeout}s")
    print(f"Log: {log_path}")
    if args.dry_run:
        print("\nDry run — first 10 targets:")
        for s in targets[:10]:
            print(f"  {s['id']:<35} {s.get('cds_url_hint', '')}")
        return 0

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fp = open(log_path, "w")

    summary: dict[str, int] = {}
    completed = 0
    started = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {
            ex.submit(call_force_school, base_url, key, s["id"], args.timeout): s
            for s in targets
        }
        for fut in as_completed(futures):
            s = futures[fut]
            res = fut.result()
            res["category"] = categorise(res.get("payload") or {})
            res["school_name"] = s.get("name", "")
            res["cds_url_hint"] = s.get("cds_url_hint", "")
            log_fp.write(json.dumps(res) + "\n")
            log_fp.flush()
            summary[res["category"]] = summary.get(res["category"], 0) + 1
            completed += 1
            elapsed = time.monotonic() - started
            rate = completed / elapsed if elapsed else 0
            remaining = (len(targets) - completed) / rate if rate else 0
            print(
                f"  [{completed}/{len(targets)}] {res['category']:<22} "
                f"{s['id'][:30]:<30} ({res['elapsed_sec']}s)  "
                f"eta={remaining/60:.1f}min",
                flush=True,
            )

    log_fp.close()
    print("\n=== Summary ===")
    for cat, cnt in sorted(summary.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:<25} {cnt}")
    print(f"\nWrote {completed} results to {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
