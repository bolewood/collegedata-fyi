#!/usr/bin/env python3
"""Audit selected extraction keys against a declared CDS schema.

Read-only. The selected-result view is fully and stably paged, then the exact
selected artifact IDs for the requested schema are fetched in bounded chunks.
The script compares the observed value-key union with the schema's canonical
question numbers; it never calls a mutating method or RPC.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "data_quality"))

from run_data_integrity_audit import (  # noqa: E402
    ReadOnlyPostgrest,
    load_env,
    sha256_json,
    utc_now,
)


def schema_field_ids(schema: Mapping[str, Any]) -> set[str]:
    fields = schema.get("fields")
    if not isinstance(fields, list):
        raise ValueError("schema fields must be a list")
    result = {
        str(field["question_number"])
        for field in fields
        if isinstance(field, Mapping) and field.get("question_number")
    }
    declared = schema.get("field_count")
    if declared != len(result):
        raise ValueError(
            f"schema declares {declared!r} fields but has {len(result)} unique IDs"
        )
    return result


def summarize_alignment(
    schema_ids: set[str], artifact_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    hits: Counter[str] = Counter()
    outside: Counter[str] = Counter()
    empty_artifacts = 0
    for row in artifact_rows:
        values = row.get("values")
        if not isinstance(values, Mapping) or not values:
            empty_artifacts += 1
            continue
        for field_id in values:
            if field_id in schema_ids:
                hits[str(field_id)] += 1
            else:
                outside[str(field_id)] += 1
    zero_hit = sorted(schema_ids - hits.keys())
    return {
        "selected_artifacts": len(artifact_rows),
        "empty_artifacts": empty_artifacts,
        "schema_fields": len(schema_ids),
        "schema_fields_with_at_least_one_hit": len(hits),
        "schema_fields_with_zero_hits": len(zero_hit),
        "zero_hit_field_ids": zero_hit,
        "observed_keys_outside_schema": len(outside),
        "outside_schema_field_ids": dict(sorted(outside.items())),
        "interpretation": (
            "A zero-hit synthesized field is an audit candidate, not proof that the field "
            "is invalid: a small selected corpus can legitimately contain no reported value. "
            "An outside key is a schema-coverage discrepancy and is counted with its document hits."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument(
        "--schema", type=Path, default=REPO_ROOT / "schemas" / "cds_schema_2023_24.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    env = load_env(args.env)
    base_url = env.get("SUPABASE_URL")
    api_key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not api_key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 2

    schema = json.loads(args.schema.read_text())
    schema_version = str(schema["schema_version"])
    ids = schema_field_ids(schema)
    started = utc_now()
    client = ReadOnlyPostgrest(base_url, api_key)
    selected, selected_page = client.paginate(
        f"cds_selected_extraction_result.schema_{schema_version}",
        "cds_selected_extraction_result",
        {
            "select": "document_id,base_artifact_id,base_schema_version",
            "base_schema_version": f"eq.{schema_version}",
            "order": "document_id.asc",
        },
        unique_key=lambda row: row["document_id"],
    )
    artifact_ids = [str(row["base_artifact_id"]) for row in selected]
    artifacts, artifact_page = client.fetch_id_chunks(
        f"cds_artifacts.selected_schema_{schema_version}",
        "cds_artifacts",
        artifact_ids,
        {"select": "id,document_id,values:notes->values"},
        unique_key=lambda row: row["id"],
        chunk_size=25,
    )
    report = {
        "label": f"Selected artifact alignment with CDS schema {schema_version}",
        "run_started_at": started,
        "run_finished_at": utc_now(),
        "schema": {
            "path": str(args.schema.relative_to(REPO_ROOT)),
            "schema_version": schema_version,
            "field_ids_sha256": sha256_json(sorted(ids)),
        },
        "pagination": {"selected_results": selected_page, "artifacts": artifact_page},
        "alignment": summarize_alignment(ids, artifacts),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), **report["alignment"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
