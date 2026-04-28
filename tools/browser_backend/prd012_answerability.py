#!/usr/bin/env python3
"""Measure PRD 012 academic-profile answerability from public browser tables.

The report intentionally reads the public projection surfaces (`cds_fields`,
`school_browser_rows`, and `cds_manifest`) instead of extraction artifacts. That
keeps it aligned with what API/browser consumers can actually query.

Usage:
    python tools/browser_backend/prd012_answerability.py --write
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.browser_backend.project_browser_data import (
    DIRECT_METRIC_DEFINITIONS,
    metric_value_is_valid,
    parse_year_start,
)

RAW_DIR = REPO_ROOT / ".context" / "prd-012-answerability"
FINDINGS_PATH = REPO_ROOT / "docs" / "plans" / "prd-012-phase-0-findings.md"
PROMOTED_BROWSER_METRICS = [
    "sat_submit_rate",
    "act_submit_rate",
    "sat_composite_p25",
    "sat_composite_p50",
    "sat_composite_p75",
    "sat_ebrw_p25",
    "sat_ebrw_p50",
    "sat_ebrw_p75",
    "sat_math_p25",
    "sat_math_p50",
    "sat_math_p75",
    "act_composite_p25",
    "act_composite_p50",
    "act_composite_p75",
]

HELD_OUT_METRICS = {
    "class_rank": ["C.1001", "C.1002", "C.1003", "C.1006"],
    "gpa": ["C.1201", "C.1202"],
}


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    for path in (REPO_ROOT / ".env", REPO_ROOT / "web" / ".env.local"):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            env.setdefault(key, value.strip().strip("\"'"))
    return env


class RestClient:
    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/")
        self.key = key

    def fetch_all(self, table: str, params: dict[str, str], page_size: int = 1000) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params)
        rows: list[dict[str, Any]] = []
        start = 0
        while True:
            req = urllib.request.Request(
                f"{self.url}/rest/v1/{table}?{query}",
                headers={
                    "apikey": self.key,
                    "authorization": f"Bearer {self.key}",
                    "Range": f"{start}-{start + page_size - 1}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                batch = json.load(response)
            rows.extend(batch)
            if len(batch) < page_size:
                return rows
            start += page_size


def pct(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def is_clean_primary(row: dict[str, Any]) -> bool:
    return row.get("sub_institutional") is None and not row.get("data_quality_flag")


def has_valid_reported_value(row: dict[str, Any], metric: str) -> bool:
    if row.get("value_status") != "reported" or row.get("value_num") is None:
        return False
    definition = DIRECT_METRIC_DEFINITIONS.get(metric)
    if definition is None:
        return True
    try:
        value = Decimal(str(row["value_num"]))
    except Exception:
        return False
    return metric_value_is_valid(value, definition)


def row_key(row: dict[str, Any]) -> tuple[str, Optional[str], str]:
    return (str(row["school_id"]), row.get("sub_institutional"), str(row["canonical_year"]))


def latest_by_school(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        school_id = str(row["school_id"])
        current = latest.get(school_id)
        if current is None or int(row["year_start"]) > int(current["year_start"]):
            latest[school_id] = row
    return latest


def metric_field_ids() -> list[str]:
    return [definition.field_id for definition in DIRECT_METRIC_DEFINITIONS.values()] + [
        field_id
        for family in HELD_OUT_METRICS.values()
        for field_id in family
    ]


def measure(client: RestClient) -> dict[str, Any]:
    browser_rows = client.fetch_all(
        "school_browser_rows",
        {
            "select": "document_id,school_id,sub_institutional,canonical_year,year_start,source_format,producer,data_quality_flag",
            "year_start": "gte.2024",
            "order": "school_id.asc,year_start.desc",
        },
    )
    primary_clean_rows = [row for row in browser_rows if is_clean_primary(row)]
    primary_clean_latest = latest_by_school(primary_clean_rows)
    primary_clean_pdf_flat = [row for row in primary_clean_rows if row.get("source_format") == "pdf_flat"]

    field_ids = metric_field_ids()
    field_rows = client.fetch_all(
        "cds_fields",
        {
            "select": "document_id,school_id,sub_institutional,canonical_year,year_start,field_id,canonical_metric,value_num,value_status,source_format,producer,data_quality_flag",
            "field_id": f"in.({','.join(field_ids)})",
            "year_start": "gte.2024",
            "order": "field_id.asc",
        },
    )

    fields_by_metric = defaultdict(list)
    fields_by_key_metric: dict[tuple[tuple[str, Optional[str], str], str], dict[str, Any]] = {}
    field_to_metric = {
        definition.field_id: metric
        for metric, definition in DIRECT_METRIC_DEFINITIONS.items()
    }
    for row in field_rows:
        metric = field_to_metric.get(str(row["field_id"]), str(row["field_id"]))
        fields_by_metric[metric].append(row)
        fields_by_key_metric[(row_key(row), metric)] = row

    manifest_rows = client.fetch_all(
        "cds_manifest",
        {
            "select": "document_id,school_id,sub_institutional,canonical_year,source_format,extraction_status,data_quality_flag,latest_canonical_artifact_id",
            "canonical_year": "gte.2024-25",
            "order": "school_id.asc",
        },
    )
    manifest_2024 = [
        row for row in manifest_rows
        if (parse_year_start(row.get("canonical_year")) or 0) >= 2024
    ]
    manifest_primary_clean = [row for row in manifest_2024 if is_clean_primary(row)]
    browser_document_ids = {row["document_id"] for row in browser_rows}
    no_selected_result = [
        row for row in manifest_primary_clean
        if row.get("extraction_status") == "extracted" and row.get("document_id") not in browser_document_ids
    ]
    extraction_errors = [
        row for row in manifest_primary_clean
        if row.get("extraction_status") not in {"extracted", None}
    ]

    metrics: dict[str, Any] = {}
    for metric in PROMOTED_BROWSER_METRICS:
        rows = fields_by_metric[metric]
        reported = [row for row in rows if has_valid_reported_value(row, metric)]
        primary_clean_reported = [row for row in reported if is_clean_primary(row)]
        pdf_flat_reported = [
            row for row in primary_clean_reported
            if row.get("source_format") == "pdf_flat"
        ]
        latest_reported = 0
        latest_with_field = set()
        for school_id, latest_row in primary_clean_latest.items():
            field = fields_by_key_metric.get((row_key(latest_row), metric))
            if field and has_valid_reported_value(field, metric):
                latest_reported += 1
            school_rows = [
                row for row in primary_clean_reported
                if str(row["school_id"]) == school_id
            ]
            if school_rows:
                latest_with_field.add(school_id)

        missing_submit_rate = None
        if metric.startswith("sat_") and metric != "sat_submit_rate":
            missing_submit_rate = _missing_companion(primary_clean_reported, fields_by_key_metric, "sat_submit_rate")
        elif metric.startswith("act_") and metric != "act_submit_rate":
            missing_submit_rate = _missing_companion(primary_clean_reported, fields_by_key_metric, "act_submit_rate")

        metrics[metric] = {
            "field_id": DIRECT_METRIC_DEFINITIONS[metric].field_id,
            "reported": len(reported),
            "primary_clean_reported": len(primary_clean_reported),
            "primary_clean_answerability": pct(len(primary_clean_reported), len(primary_clean_rows)),
            "pdf_flat_primary_clean_reported": len(pdf_flat_reported),
            "pdf_flat_answerability": pct(len(pdf_flat_reported), len(primary_clean_pdf_flat)),
            "parse_errors": sum(
                1 for row in rows
                if row.get("value_status") == "parse_error"
                or (row.get("value_status") == "reported" and not has_valid_reported_value(row, metric))
            ),
            "latest_in_window_reported": latest_reported,
            "latest_in_window_answerability": pct(latest_reported, len(primary_clean_latest)),
            "latest_with_field_populated": len(latest_with_field),
            "latest_with_field_answerability": pct(len(latest_with_field), len(primary_clean_latest)),
            "by_source_format": dict(Counter(row.get("source_format") or "unknown" for row in primary_clean_reported)),
            "by_producer": dict(Counter(row.get("producer") or "unknown" for row in primary_clean_reported)),
            "reported_missing_submit_rate_by_producer": missing_submit_rate,
        }

    held_out: dict[str, Any] = {}
    for family, ids in HELD_OUT_METRICS.items():
        rows = [row for field_id in ids for row in fields_by_metric[field_id]]
        reported = [row for row in rows if row.get("value_status") == "reported" and row.get("value_num") is not None]
        held_out[family] = {
            "field_ids": ids,
            "reported": len(reported),
            "primary_clean_reported": sum(1 for row in reported if is_clean_primary(row)),
            "parse_errors": sum(1 for row in rows if row.get("value_status") == "parse_error"),
            "by_source_format": dict(Counter(row.get("source_format") or "unknown" for row in reported if is_clean_primary(row))),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "denominators": {
            "school_browser_rows_2024_plus": len(browser_rows),
            "primary_clean_browser_rows_2024_plus": len(primary_clean_rows),
            "primary_clean_latest_schools_2024_plus": len(primary_clean_latest),
            "primary_clean_pdf_flat_rows_2024_plus": len(primary_clean_pdf_flat),
            "manifest_primary_clean_2024_plus": len(manifest_primary_clean),
            "no_selected_result_extracted_primary_clean": len(no_selected_result),
            "extraction_error_primary_clean": len(extraction_errors),
        },
        "source_formats_primary_clean": dict(Counter(row.get("source_format") or "unknown" for row in primary_clean_rows)),
        "producers_primary_clean": dict(Counter(row.get("producer") or "unknown" for row in primary_clean_rows)),
        "promoted_browser_metrics": metrics,
        "held_out_families": held_out,
        "decision": {
            "promote_to_school_browser_rows": PROMOTED_BROWSER_METRICS,
            "hold_out": {
                "class_rank": "Coverage is useful but denominator semantics remain ambiguous for public filters.",
                "gpa": "Coverage is useful after the v0.3 projection, but GPA scale comparability is unresolved.",
            },
            "latest_semantics": "Keep PRD 010 ranked latest-per-school semantics. Required score fields can select the latest row with the requested field populated, and rows return canonical_year so the source cohort is visible.",
            "submit_rate_policy": "Expose submit rates and companion answerability metadata. Do not enforce a hard-coded default threshold in the backend.",
        },
    }


def _missing_companion(
    reported_rows: list[dict[str, Any]],
    fields_by_key_metric: dict[tuple[tuple[str, Optional[str], str], str], dict[str, Any]],
    companion_metric: str,
) -> dict[str, int]:
    missing: Counter[str] = Counter()
    for row in reported_rows:
        companion = fields_by_key_metric.get((row_key(row), companion_metric))
        if not companion or not has_valid_reported_value(companion, companion_metric):
            missing[str(row.get("producer") or "unknown")] += 1
    return dict(missing)


def render_markdown(report: dict[str, Any]) -> str:
    denominators = report["denominators"]
    lines = [
        "# PRD 012 Phase 0 Findings",
        "",
        f"**Generated:** {report['generated_at']}",
        "",
        "## Decision",
        "",
        "Promote SAT/ACT submission-rate and percentile fields to `school_browser_rows` backend columns. Keep GPA and class-rank out of first-class browser columns.",
        "",
        "This is a backend/API expansion only. The public `/browse` UI should not add default score filters until the UI can pair scores with submit-rate caveats.",
        "",
        "## Denominators",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    for key, value in denominators.items():
        lines.append(f"| `{key}` | {value:,} |")
    lines.extend([
        "",
        "## Promoted SAT/ACT Metrics",
        "",
        "| Metric | Field | Primary clean reported | Primary clean coverage | pdf_flat coverage | Parse errors | Latest-row coverage | Latest-with-field coverage | Missing submit-rate rows |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for metric, item in report["promoted_browser_metrics"].items():
        missing_submit_rate = item["reported_missing_submit_rate_by_producer"]
        missing_total = sum(missing_submit_rate.values()) if isinstance(missing_submit_rate, dict) else 0
        lines.append(
            f"| `{metric}` | `{item['field_id']}` | {item['primary_clean_reported']:,} | "
            f"{fmt_pct(item['primary_clean_answerability'])} | {fmt_pct(item['pdf_flat_answerability'])} | "
            f"{item['parse_errors']:,} | {fmt_pct(item['latest_in_window_answerability'])} | "
            f"{fmt_pct(item['latest_with_field_answerability'])} | {missing_total:,} |"
        )
    lines.extend([
        "",
        "## Held Out",
        "",
    ])
    for family, item in report["held_out_families"].items():
        lines.extend([
            f"### {family}",
            "",
            f"- Field IDs: {', '.join(f'`{field}`' for field in item['field_ids'])}",
            f"- Primary clean reported values across family: {item['primary_clean_reported']:,}",
            f"- Parse errors across family: {item['parse_errors']:,}",
            f"- Source-format mix: `{json.dumps(item['by_source_format'], sort_keys=True)}`",
            "",
        ])
    lines.extend([
        "## Notes",
        "",
        "- SAT/ACT score values describe score submitters, not the full admitted or enrolled class.",
        "- Submit-rate columns are stored fractionally in `0..1` and included beside score fields.",
        "- The backend does not hard-code a submit-rate threshold. `browser-search` reports companion submit-rate missingness for active SAT/ACT score filters.",
        "- GPA remains long-form only because scale comparability is not resolved.",
        "- Class-rank remains long-form only because denominator semantics are ambiguous without a dedicated UI.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="Write raw JSON and markdown findings")
    args = parser.parse_args()

    env = load_env()
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("SUPABASE_ANON_KEY") or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL/SUPABASE_ANON_KEY or web NEXT_PUBLIC equivalents are required")

    report = measure(RestClient(url, key))
    print(json.dumps(report["denominators"], indent=2, sort_keys=True))
    if args.write:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DIR / "report.json"
        raw_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        FINDINGS_PATH.write_text(render_markdown(report) + "\n")
        print(f"wrote {raw_path}")
        print(f"wrote {FINDINGS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
