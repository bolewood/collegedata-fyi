#!/usr/bin/env python3
"""Audit 2023-24 / 2024-25 B1 enrollment gender mapping quality.

Compares stored tier4_docling cleaner values against a fresh clean() of the
artifact markdown using the current Tier 4 cleaner. Useful after schema-year
B1 mapping fixes (see PR #168).

Examples:
  python tools/data_quality/audit_b1_gender_2024.py
  python tools/data_quality/audit_b1_gender_2024.py --apply-improvements
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "extraction_worker"))

from supabase import create_client  # noqa: E402
from tier4_cleaner import SchemaIndex, clean  # noqa: E402


YEARS = ("2023-24", "2024-25")


def is_b1(qn: str) -> bool:
    if not qn.startswith("B."):
        return False
    try:
        n = int(qn.split(".", 1)[1])
    except ValueError:
        return False
    return 101 <= n <= 195


def b1_map(values: dict) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for k, v in (values or {}).items():
        if not is_b1(k):
            continue
        out[k] = v.get("value") if isinstance(v, dict) else (None if v is None else str(v))
    return out


def classify(old_b1: dict, new_b1: dict) -> str:
    if not old_b1 and not new_b1:
        return "no_b1"
    if old_b1 and not new_b1:
        return "lose"
    if old_b1 == new_b1:
        return "unchanged"
    gains = False
    for qn in ("B.149", "B.150", "B.193", "B.194", "B.195"):
        if new_b1.get(qn) and not old_b1.get(qn):
            gains = True
    if old_b1.get("B.102") and new_b1.get("B.102") and old_b1["B.102"] != new_b1["B.102"]:
        gains = True
    ratio = len(new_b1) / max(len(old_b1), 1)
    if ratio < 0.5 and not gains:
        return "shrink_risky"
    if gains or ratio >= 1.0 or len(new_b1) >= len(old_b1):
        return "improve"
    return "changed_other"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-improvements", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "scratch" / "b1-wider-audit" / "audit_b1_gender_2024.json",
    )
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    client = create_client(url, key)
    schemas = {
        year: SchemaIndex(ROOT / "schemas" / f"cds_schema_{year.replace('-', '_')}.json")
        for year in YEARS
    }

    doc_ids: set[tuple[str, str, str]] = set()
    for year in YEARS:
        offset = 0
        while True:
            batch = (
                client.table("cds_fields")
                .select("document_id,school_id,canonical_year,field_id")
                .eq("canonical_year", year)
                .like("field_id", "B.1%")
                .range(offset, offset + 999)
                .execute()
            ).data or []
            for row in batch:
                try:
                    n = int(row["field_id"].split(".", 1)[1])
                except Exception:
                    continue
                if 101 <= n <= 195:
                    doc_ids.add(
                        (row["document_id"], row["school_id"], row["canonical_year"])
                    )
            if len(batch) < 1000:
                break
            offset += 1000

    decisions: Counter[str] = Counter()
    plan = []
    residuals = []

    for doc_id, school, year in sorted(doc_ids, key=lambda x: x[1]):
        arts = (
            client.table("cds_artifacts")
            .select("id,producer,notes")
            .eq("document_id", doc_id)
            .eq("kind", "canonical")
            .execute()
        ).data or []
        art = next(
            (
                a
                for a in arts
                if (a.get("notes") or {}).get("markdown")
                and a.get("producer") == "tier4_docling"
            ),
            None,
        )
        if art is None:
            art = next(
                (a for a in arts if (a.get("notes") or {}).get("markdown")),
                None,
            )
        if art is None:
            decisions["no_artifact_markdown"] += 1
            residuals.append(
                {
                    "school_id": school,
                    "cds_year": year,
                    "document_id": doc_id,
                    "reason": "no_artifact_markdown",
                }
            )
            continue

        notes = art["notes"] or {}
        md = notes.get("markdown") or ""
        old_b1 = b1_map(notes.get("values") or {})
        new_values = clean(md, schema=schemas[year], canonical_year=year)
        new_b1 = b1_map(new_values)
        decision = classify(old_b1, new_b1)
        decisions[decision] += 1
        row = {
            "document_id": doc_id,
            "school_id": school,
            "cds_year": year,
            "artifact_id": art["id"],
            "decision": decision,
            "old_b1_count": len(old_b1),
            "new_b1_count": len(new_b1),
            "old_B.102": old_b1.get("B.102"),
            "new_B.102": new_b1.get("B.102"),
            "old_B.149": old_b1.get("B.149"),
            "new_B.149": new_b1.get("B.149"),
            "old_B.150": old_b1.get("B.150"),
            "new_B.150": new_b1.get("B.150"),
        }
        if decision == "improve":
            plan.append({**row, "new_values": new_values, "notes": notes})
        elif decision != "unchanged":
            residuals.append(row)

    applied = []
    if args.apply_improvements and plan:
        from browser_backend.project_browser_data import (  # noqa: WPS433
            load_schema_definitions,
            project_document_id,
        )

        definitions = load_schema_definitions()
        for row in plan:
            new_notes = deepcopy(row["notes"])
            new_notes["values"] = row["new_values"]
            new_notes["recleaned_at"] = datetime.now(timezone.utc).isoformat()
            new_notes["reclean_reason"] = "audit_b1_gender_2024"
            if isinstance(new_notes.get("stats"), dict):
                new_notes["stats"]["total_fields"] = len(row["new_values"])
            client.table("cds_artifacts").update({"notes": new_notes}).eq(
                "id", row["artifact_id"]
            ).execute()
            project_document_id(client, row["document_id"], definitions, apply=True)
            applied.append({k: v for k, v in row.items() if k not in ("new_values", "notes")})
        try:
            client.rpc("refresh_public_serving_caches", {}).execute()
        except Exception:
            pass

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "decisions": dict(decisions),
        "plan_count": len(plan),
        "applied_count": len(applied),
        "residuals": [
            {k: v for k, v in r.items() if k not in ("new_values", "notes")}
            for r in residuals
        ],
        "plan": [
            {k: v for k, v in r.items() if k not in ("new_values", "notes")} for r in plan
        ],
        "applied": applied,
    }
    args.output.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"decisions": dict(decisions), "plan_count": len(plan), "applied_count": len(applied), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
