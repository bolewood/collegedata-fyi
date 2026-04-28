"""
Build a cross-year canonical CDS diff and optionally synthesize PDF tags.

This is for canonical schemas produced from Answer Sheet tabs, not the older
structural schemas handled by diff.py. It compares a source year to a target
reference year and emits:

  - field-level equivalence classifications
  - derived metric formulas needed by projection code
  - optional pdf_tag updates for source fields with validated semantic matches

Usage:
    python tools/schema_builder/canonical_diff.py \
      schemas/cds_schema_2024_25.json \
      schemas/cds_schema_2025_26.json \
      schemas/cds_schema_2024_25-to-2025_26.diff.json \
      --source-pdf schemas/templates/cds_2024-25_template.pdf \
      --update-source-schema
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pypdf


SIGNATURE_KEYS = [
    "question",
    "section",
    "subsection",
    "category",
    "student_group",
    "cohort",
    "residency",
    "unit_load",
    "gender",
    "value_type",
]

ACADEMIC_PROFILE_FIELDS = [
    "C.901",
    "C.902",
    "C.905",
    "C.906",
    "C.907",
    "C.908",
    "C.909",
    "C.910",
    "C.911",
    "C.912",
    "C.913",
    "C.914",
    "C.915",
    "C.916",
    "C.1201",
    "C.1202",
]

DERIVED_METRICS = [
    {
        "canonical_metric": "applied",
        "canonical_field_id": "C.116",
        "equivalence_kind": "derived",
        "per_year_formulas": {
            "2024-25": "C.101 + C.102 + C.103 + C.104",
            "2025-26": "C.116",
        },
    },
    {
        "canonical_metric": "admitted",
        "canonical_field_id": "C.117",
        "equivalence_kind": "derived",
        "per_year_formulas": {
            "2024-25": "C.105 + C.106 + C.107 + C.108",
            "2025-26": "C.117",
        },
    },
    {
        "canonical_metric": "first_year_enrolled",
        "canonical_field_id": "C.118",
        "equivalence_kind": "derived",
        "per_year_formulas": {
            "2024-25": "C.109 + C.110 + C.111 + C.112 + C.113 + C.114 + C.115 + C.116",
            "2025-26": "C.118",
        },
    },
]


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = value.lower().strip()
    replacements = [
        (r"\bpercent submitting\b", "submitting"),
        (r"\bpercent\b", ""),
        (r"\bmales\b", "men"),
        (r"\bfemales\b", "women"),
        (r"\bstudents of unknown sex\b", "unknown gender"),
        (r"\bunknown sex\b", "unknown gender"),
        (r"\bfirst year\b", "first-year"),
        (r"\bwebsite\b", "web site"),
        (r"\be mail\b", "email"),
        (r"\btenths\b", "tenth"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def signature(field: dict[str, Any]) -> tuple[str, ...]:
    return tuple(normalize_text(field.get(key)) for key in SIGNATURE_KEYS)


def index_unique_by_signature(
    fields: list[dict[str, Any]],
    allowed_pdf_tags: set[str] | None,
) -> tuple[dict[tuple[str, ...], dict[str, Any]], dict[tuple[str, ...], list[dict[str, Any]]]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for field in fields:
        pdf_tag = field.get("pdf_tag")
        if allowed_pdf_tags is not None and pdf_tag not in allowed_pdf_tags:
            continue
        grouped[signature(field)].append(field)

    unique = {sig: items[0] for sig, items in grouped.items() if len(items) == 1}
    ambiguous = {sig: items for sig, items in grouped.items() if len(items) > 1}
    return unique, ambiguous


def load_pdf_field_names(pdf_path: Path | None) -> set[str]:
    if pdf_path is None:
        return set()
    reader = pypdf.PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}
    return set(fields)


def classify_source_field(
    source_field: dict[str, Any],
    target_field: dict[str, Any] | None,
) -> str:
    if target_field is not None:
        return "direct"
    if source_field.get("gender") == "Another Gender":
        return "unmapped"
    return "preserved-only"


def build_diff(
    source_schema: dict[str, Any],
    target_schema: dict[str, Any],
    source_pdf_tags: set[str] | None = None,
) -> dict[str, Any]:
    source_pdf_tags = source_pdf_tags or set()
    target_fields = target_schema["fields"]
    source_fields = source_schema["fields"]

    matched_pdf_tags = {
        field["pdf_tag"]
        for field in target_fields
        if field.get("pdf_tag") and field["pdf_tag"] in source_pdf_tags
    }
    target_by_signature, ambiguous_target_signatures = index_unique_by_signature(
        target_fields,
        matched_pdf_tags if source_pdf_tags else None,
    )

    field_records = []
    pdf_tags_assigned = 0
    for source_field in source_fields:
        target_field = target_by_signature.get(signature(source_field))
        kind = classify_source_field(source_field, target_field)
        pdf_tag = target_field.get("pdf_tag") if target_field else None
        if pdf_tag:
            pdf_tags_assigned += 1
        field_records.append(
            {
                "field_id": source_field["question_number"],
                "question": source_field.get("question"),
                "canonical_field_id": target_field["question_number"] if target_field else None,
                "target_question": target_field.get("question") if target_field else None,
                "equivalence_kind": kind,
                "pdf_tag": pdf_tag,
                "schema_version": source_schema.get("schema_version"),
            }
        )

    target_field_ids = {record["canonical_field_id"] for record in field_records}
    target_only = [
        {
            "field_id": field["question_number"],
            "question": field.get("question"),
            "equivalence_kind": "unmapped",
            "schema_version": target_schema.get("schema_version"),
        }
        for field in target_fields
        if field["question_number"] not in target_field_ids
    ]

    kind_counts = Counter(record["equivalence_kind"] for record in field_records)
    academic_profile = {
        field_id: next(
            (
                record["equivalence_kind"]
                for record in field_records
                if record["field_id"] == field_id
            ),
            None,
        )
        for field_id in ACADEMIC_PROFILE_FIELDS
    }

    return {
        "source_schema_version": source_schema.get("schema_version"),
        "target_schema_version": target_schema.get("schema_version"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "source_fields": len(source_fields),
            "target_fields": len(target_fields),
            "source_pdf_fields": len(source_pdf_tags),
            "source_pdf_fields_matching_target_pdf_tags": len(matched_pdf_tags),
            "source_schema_pdf_tags_assigned": pdf_tags_assigned,
            "ambiguous_target_signatures": len(ambiguous_target_signatures),
            "equivalence_kind_counts": dict(sorted(kind_counts.items())),
            "target_only_fields": len(target_only),
        },
        "academic_profile_fields": academic_profile,
        "derived_metrics": DERIVED_METRICS,
        "fields": field_records,
        "target_only_fields": target_only,
    }


def update_source_schema_pdf_tags(source_schema_path: Path, diff: dict[str, Any]) -> int:
    schema = json.loads(source_schema_path.read_text())
    tags_by_id = {
        record["field_id"]: record["pdf_tag"]
        for record in diff["fields"]
        if record.get("pdf_tag")
    }
    updated = 0
    for field in schema["fields"]:
        pdf_tag = tags_by_id.get(field["question_number"])
        if pdf_tag and field.get("pdf_tag") != pdf_tag:
            field["pdf_tag"] = pdf_tag
            field["computed"] = False
            updated += 1
    source_schema_path.write_text(json.dumps(schema, indent=2) + "\n")
    return updated


def render_markdown(diff: dict[str, Any]) -> str:
    summary = diff["summary"]
    counts = summary["equivalence_kind_counts"]
    lines = [
        f"# CDS canonical schema diff: {diff['source_schema_version']} to {diff['target_schema_version']}",
        "",
        f"_Generated {diff['generated_at']}_",
        "",
        "## Summary",
        "",
        f"- Source fields: {summary['source_fields']}",
        f"- Target fields: {summary['target_fields']}",
        f"- Source PDF fields matching target pdf_tags: {summary['source_pdf_fields_matching_target_pdf_tags']} / {summary['source_pdf_fields']}",
        f"- Source schema pdf_tags assigned by semantic validation: {summary['source_schema_pdf_tags_assigned']}",
        f"- Direct fields: {counts.get('direct', 0)}",
        f"- Preserved-only fields: {counts.get('preserved-only', 0)}",
        f"- Unmapped fields: {counts.get('unmapped', 0)}",
        f"- Target-only fields: {summary['target_only_fields']}",
        "",
        "## Derived Browser Metrics",
        "",
        "| Metric | Canonical field | 2024-25 formula | 2025-26 formula |",
        "|---|---|---|---|",
    ]
    for metric in diff["derived_metrics"]:
        formulas = metric["per_year_formulas"]
        lines.append(
            f"| {metric['canonical_metric']} | {metric['canonical_field_id']} | "
            f"`{formulas['2024-25']}` | `{formulas['2025-26']}` |"
        )

    lines.extend(
        [
            "",
            "## Academic Profile Fields",
            "",
            "| Field | Classification |",
            "|---|---|",
        ]
    )
    for field_id, kind in diff["academic_profile_fields"].items():
        lines.append(f"| {field_id} | {kind or 'missing'} |")

    unmapped = [record for record in diff["fields"] if record["equivalence_kind"] == "unmapped"]
    if unmapped:
        lines.extend(["", "## Unmapped Source Fields", ""])
        for record in unmapped[:100]:
            lines.append(f"- `{record['field_id']}` {record['question']}")
        if len(unmapped) > 100:
            lines.append(f"- ... {len(unmapped) - 100} more")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("source_schema", type=Path)
    parser.add_argument("target_schema", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--source-pdf", type=Path, default=None)
    parser.add_argument(
        "--update-source-schema",
        action="store_true",
        help="Write validated synthesized pdf_tags back to the source schema",
    )
    args = parser.parse_args()

    source_schema = json.loads(args.source_schema.read_text())
    target_schema = json.loads(args.target_schema.read_text())
    source_pdf_tags = load_pdf_field_names(args.source_pdf)
    diff = build_diff(source_schema, target_schema, source_pdf_tags)

    if args.update_source_schema:
        updated = update_source_schema_pdf_tags(args.source_schema, diff)
        diff["summary"]["source_schema_pdf_tags_written"] = updated

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(diff, indent=2) + "\n")
    args.output_json.with_suffix(".md").write_text(render_markdown(diff))

    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_json.with_suffix('.md')}")
    for key, value in diff["summary"].items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
