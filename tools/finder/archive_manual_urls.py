"""
Batch-archive the Playwright-collected CDS URLs in manual_urls.yaml.

For each school with status=ok in the sidecar, POSTs the URL list to
archive-process's force_urls mode. Each URL becomes one cds_documents row
(or an unchanged_verified if already archived).

Usage:
    tools/extraction_worker/.venv/bin/python \\
        tools/finder/archive_manual_urls.py \\
          --sidecar tools/finder/manual_urls.yaml

    # Dry run (print what would be sent, don't hit the API)
    ... --dry-run

    # Just one school
    ... --only columbia

    # Skip already-archived schools (by default we skip them)
    ... --include-already-archived
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import yaml
from pathlib import Path

_TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_TOOLS_ROOT / "extraction_worker"))
from worker import load_env

import httpx
from supabase import create_client


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--sidecar", type=Path,
                    default=Path("tools/finder/manual_urls.yaml"))
    ap.add_argument("--env", default=".env")
    ap.add_argument("--only", help="Run for one specific school_id")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print payloads without calling archive-process")
    ap.add_argument("--include-already-archived", action="store_true",
                    help="Process schools that already have >= 5 cds_documents rows")
    ap.add_argument("--sleep", type=float, default=1.0,
                    help="Seconds between school POSTs (politeness + rate limit)")
    args = ap.parse_args()

    env = load_env(Path(args.env))
    url = env["SUPABASE_URL"]
    key = env["SUPABASE_SERVICE_ROLE_KEY"]

    data = yaml.safe_load(args.sidecar.read_text())
    all_schools = data["schools"]

    # Filter to ok schools with anchors.
    targets = [
        (sid, info) for sid, info in all_schools.items()
        if info["status"] == "ok" and info["anchors"]
    ]
    if args.only:
        targets = [t for t in targets if t[0] == args.only]

    if not targets:
        print(f"No targets found (sidecar={args.sidecar}, only={args.only}).",
              file=sys.stderr)
        return 1

    # Pre-query existing doc counts so we can skip already-well-covered schools.
    if not args.include_already_archived and not args.dry_run:
        sb = create_client(url, key)
        already = {}
        for sid, _ in targets:
            r = sb.table("cds_documents").select("id", count="exact")\
                .eq("school_id", sid).limit(1).execute()
            already[sid] = r.count or 0
        skipped_well_covered = [sid for sid, n in already.items() if n >= 5]
        if skipped_well_covered:
            print(
                f"Skipping {len(skipped_well_covered)} school(s) already ≥5 docs: "
                f"{skipped_well_covered}", file=sys.stderr,
            )
        targets = [t for t in targets if t[0] not in skipped_well_covered]

    print(f"Processing {len(targets)} school(s).\n", file=sys.stderr)

    total_candidates = 0
    total_inserted = 0
    total_unchanged = 0
    total_failed_schools = 0

    for i, (sid, info) in enumerate(targets, 1):
        # Prefer document-like anchors (PDF/XLSX/DOCX). Drop subpage URLs and
        # hash-only fragments. The archiver will still try them if asked, but
        # subpages need the two-hop walk the resolver does, not the direct
        # download this path performs. Pass year alongside each URL so the
        # archiver doesn't collapse multiple Box/Drive opaque-id URLs onto
        # the same cds_year=unknown row (unique constraint collision).
        items: list[dict] = []
        seen = set()
        for a in info["anchors"]:
            u = a["url"].split("#")[0]
            if u in seen:
                continue
            seen.add(u)
            lower = u.lower()
            if (a.get("is_document")
                    or "drive.google.com" in lower
                    or "box.com" in lower
                    or "dropbox.com" in lower):
                item = {"url": u}
                if a.get("year"):
                    item["year"] = a["year"]
                items.append(item)

        if not items:
            print(f"  [{i:>3}/{len(targets)}] {sid:<45} no document anchors → skip",
                  file=sys.stderr)
            continue

        payload = {"school_id": sid, "urls": items}
        print(f"  [{i:>3}/{len(targets)}] {sid:<45} POST {len(items)} urls",
              file=sys.stderr, flush=True)

        if args.dry_run:
            print(f"      DRY: {json.dumps(payload)[:200]}", file=sys.stderr)
            continue

        try:
            t0 = time.time()
            resp = httpx.post(
                f"{url}/functions/v1/archive-process",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            dur = time.time() - t0
            body = resp.json() if resp.content else {}
            if resp.status_code != 200:
                total_failed_schools += 1
                err = body.get("error") or body.get("error_class") or "?"
                print(f"      status={resp.status_code}  ERROR {err}",
                      file=sys.stderr)
                continue
            outcome = body.get("outcome", {})
            cands = outcome.get("candidates", [])
            ins = sum(1 for c in cands if c.get("action") == "inserted")
            unch = sum(1 for c in cands if c.get("action") == "unchanged_verified")
            total_candidates += len(cands)
            total_inserted += ins
            total_unchanged += unch
            print(
                f"      status=200  candidates={len(cands)}  +{ins}  "
                f"unchanged={unch}  ({dur:.1f}s)",
                file=sys.stderr,
            )
        except Exception as e:
            total_failed_schools += 1
            print(f"      EXCEPTION: {type(e).__name__}: {e}", file=sys.stderr)
        time.sleep(args.sleep)

    print("\n==== Summary ====", file=sys.stderr)
    print(f"Schools processed:    {len(targets)}", file=sys.stderr)
    print(f"Schools failed:       {total_failed_schools}", file=sys.stderr)
    print(f"Total candidates:     {total_candidates}", file=sys.stderr)
    print(f"Inserted:             {total_inserted}", file=sys.stderr)
    print(f"Unchanged/verified:   {total_unchanged}", file=sys.stderr)
    return 0 if total_failed_schools == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
