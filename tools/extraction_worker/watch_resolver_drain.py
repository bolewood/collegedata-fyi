"""
One-shot progress report for the corpus-wide resolver-upgrade re-enqueue.

Shows:
  - Queue status distribution for a given run_id
  - Drain rate since last check (if a previous run is in ~/.gstack/)
  - Recent wins: schools where this run added new cds_documents rows

Usage:
    python tools/extraction_worker/watch_resolver_drain.py
    python tools/extraction_worker/watch_resolver_drain.py --run-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

_TOOLS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_ROOT / "extraction_worker"))
from worker import load_env

from supabase import create_client


DEFAULT_RUN_ID = "4fb98e04-a75e-484e-bb7c-5980ff0d7c0a"


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--run-id", default=DEFAULT_RUN_ID,
                    help="archive_queue.enqueued_run_id to watch")
    ap.add_argument("--env", default=".env")
    args = ap.parse_args()

    env = load_env(Path(args.env))
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    # Queue status distribution.
    rows = sb.table("archive_queue").select("status,school_id,processed_at,last_error")\
        .eq("enqueued_run_id", args.run_id).execute()
    statuses = Counter(r["status"] for r in rows.data)

    total = len(rows.data)
    done = statuses.get("done", 0)
    ready = statuses.get("ready", 0)
    in_flight = statuses.get("in_flight", 0)
    failed_p = statuses.get("failed_permanent", 0)
    failed_t = statuses.get("failed_transient", 0)

    processed = done + failed_p + failed_t
    pct = 100.0 * processed / total if total else 0.0
    eta_min = ready * 30 / 60

    print(f"Run: {args.run_id}")
    print(f"  Total queued:       {total}")
    print(f"  Done:               {done}")
    print(f"  Failed permanent:   {failed_p}")
    print(f"  Failed transient:   {failed_t}")
    print(f"  In flight:          {in_flight}")
    print(f"  Ready (pending):    {ready}")
    print(f"  Progress:           {processed}/{total}  ({pct:.1f}%)")
    print(f"  Est. drain time:    {eta_min:.0f} min  ({eta_min/60:.1f} h)")
    print()

    # Last 10 processed schools.
    recent = sorted(
        (r for r in rows.data if r.get("processed_at")),
        key=lambda r: r["processed_at"],
        reverse=True,
    )[:10]
    if recent:
        print(f"Last 10 processed (for this run):")
        for r in recent:
            icon = "✓" if r["status"] == "done" else "✗"
            err = f"  {r['last_error']}" if r.get("last_error") else ""
            print(f"  {icon} {r['processed_at'][:19]}  {r['school_id']:<45} {r['status']}{err}")
    print()

    # Corpus-wide totals.
    r = sb.table("cds_documents").select("id", count="exact").limit(1).execute()
    total_docs = r.count or 0
    r = sb.table("cds_documents").select("id", count="exact")\
        .eq("extraction_status", "extraction_pending").limit(1).execute()
    pending_ext = r.count or 0
    r = sb.table("cds_documents").select("id", count="exact")\
        .eq("extraction_status", "extracted").limit(1).execute()
    extracted = r.count or 0

    print(f"Corpus:")
    print(f"  cds_documents total:           {total_docs}")
    print(f"  extraction_status=extracted:   {extracted}")
    print(f"  extraction_status=pending:     {pending_ext}")
    print()

    # Rows added today (local or since the run started).
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    r = sb.table("cds_documents").select("school_id,cds_year,source_url,created_at")\
        .gte("created_at", one_hour_ago).order("created_at", desc=True).limit(30).execute()
    if r.data:
        print(f"Most recent {len(r.data)} cds_documents inserts (last 2 hours):")
        by_school = Counter(row["school_id"] for row in r.data)
        for sid, n in by_school.most_common(10):
            print(f"  +{n:>2}  {sid}")


if __name__ == "__main__":
    main()
