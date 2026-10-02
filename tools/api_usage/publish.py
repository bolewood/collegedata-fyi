#!/usr/bin/env python3
"""Publish public usage rows (PRD 033 M1).

Copies ready days from the private usage aggregates into usage_public_daily
and complete months into usage_public_school_months, through
api_usage_publish_pending() in Postgres, which applies the privacy rules.
Then scans everything published with usage_public_violations() and fails
if any rule is broken.

A day is ready once its unique downloads are counted and every hour has a
reconciled window. Days rewritten by a later run are republished.

The repository is public, so logs and --out-json carry counts only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.api_usage import classify  # noqa: E402
from tools.api_usage.ingest_gateway_logs import Db, IngestError  # noqa: E402

# Days per RPC call, so one call stays well under the statement timeout.
BATCH_DAYS = 31
# Stop after this many calls; 90 days of retention need at most 3.
MAX_CALLS = 12


class PublishError(RuntimeError):
    pass


def run(db: Db, method_version: int = classify.DOWNLOADS_METHOD_VERSION) -> dict:
    report = {"method_version": method_version, "days_published": 0, "months_published": 0,
              "days_waiting": 0, "calls": 0}
    for _ in range(MAX_CALLS):
        result = db.rpc("api_usage_publish_pending", {
            "p_method_version": method_version,
            "p_limit": BATCH_DAYS,
        })
        if not isinstance(result, dict):
            raise PublishError("api_usage_publish_pending returned no summary")
        report["calls"] += 1
        report["days_published"] += int(result.get("days_published") or 0)
        report["months_published"] += int(result.get("months_published") or 0)
        report["days_waiting"] = int(result.get("days_waiting") or 0)
        if int(result.get("days_published") or 0) < BATCH_DAYS:
            break
    else:
        raise PublishError(f"still publishing after {MAX_CALLS} calls")

    violations = db.rpc("usage_public_violations", {})
    if not isinstance(violations, dict):
        raise PublishError("usage_public_violations returned no summary")
    report["violations"] = {key: int(value or 0) for key, value in sorted(violations.items())}
    broken = [key for key, value in report["violations"].items() if value]
    if broken:
        raise PublishError("published usage breaks privacy rules: " + ", ".join(broken))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-json", type=Path, help="counts-only report")
    args = parser.parse_args(argv)

    try:
        db = Db(os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
        report = run(db)
    except (PublishError, IngestError) as exc:
        print(f"::error::usage publish failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — never let a traceback print row data
        print(f"::error::usage publish failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
