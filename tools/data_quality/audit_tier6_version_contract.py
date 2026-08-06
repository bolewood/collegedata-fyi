#!/usr/bin/env python3
"""Measure Tier 6 producer/idempotency exposure without mutating data."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "data_quality"))

from run_data_integrity_audit import ReadOnlyPostgrest, load_env, utc_now  # noqa: E402


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    with_sha = 0
    for row in rows:
        notes = row.get("notes") if isinstance(row.get("notes"), Mapping) else {}
        source_artifact = (
            notes.get("source_artifact")
            if isinstance(notes.get("source_artifact"), Mapping)
            else {}
        )
        if notes.get("source_sha256") or source_artifact.get("sha256"):
            with_sha += 1
    return {
        "canonical_artifacts": len(rows),
        "documents": len({str(row.get("document_id")) for row in rows}),
        "producer_versions": dict(sorted(Counter(str(row.get("producer_version")) for row in rows).items())),
        "artifacts_with_source_sha_provenance": with_sha,
        "artifacts_without_source_sha_provenance": len(rows) - with_sha,
        "interpretation": (
            "Current artifacts without source SHA do not suppress a re-extraction when the current "
            "source SHA is known. After a SHA-tagged artifact is written, however, cleaner-only "
            "changes require a Tier 6 producer-version bump to avoid the idempotency skip."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    env = load_env(args.env)
    base_url = env.get("SUPABASE_URL")
    api_key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not api_key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 2

    started = utc_now()
    rows, pagination = ReadOnlyPostgrest(base_url, api_key).paginate(
        "cds_artifacts.tier6_html",
        "cds_artifacts",
        {
            "select": "id,document_id,producer_version,schema_version,notes",
            "kind": "eq.canonical",
            "producer": "eq.tier6_html",
            "order": "id.asc",
        },
        unique_key=lambda row: row["id"],
    )
    report = {
        "label": "Tier 6 producer-version/idempotency contract",
        "run_started_at": started,
        "run_finished_at": utc_now(),
        "pagination": pagination,
        "result": summarize(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), **report["result"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
