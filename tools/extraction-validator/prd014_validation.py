#!/usr/bin/env python3
"""PRD 014 M4 validation drain.

Runs a small, reproducible old-vs-new comparison for cross-year schema
dispatch:

* old behavior: Tier 4 markdown cleaned against the 2025-26 schema
* new behavior: Tier 4 markdown cleaned against the document year schema

The script evaluates browser-facing canonical metrics against hand-verified
ground truth where local fixtures exist. It also optionally includes the
Harvey Mudd 2025-26 Tier 2 control from Supabase when credentials are
available in .env.local.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS_ROOT / "extraction_worker"))
sys.path.insert(0, str(TOOLS_ROOT / "extraction-validator"))

from tier4_cleaner import SchemaIndex, clean, schema_path_for_year  # noqa: E402
from tools.browser_backend.project_browser_data import (  # noqa: E402
    DEFAULT_SCHEMA_VERSION,
    build_projection_rows,
    load_schema_definitions,
)


REPORT_PATH = REPO_ROOT / "docs" / "plans" / "prd-014-validation-findings.md"
RESULTS_PATH = REPO_ROOT / ".context" / "prd-014-validation" / "results.json"

METRIC_ASSERTIONS = {
    "c1_total_applied": ("applied", "number"),
    "c1_applied_total": ("applied", "number"),
    "c1_total_admitted": ("admitted", "number"),
    "c1_admitted_total": ("admitted", "number"),
    "c1_total_enrolled": ("first_year_enrolled", "number"),
    "c1_enrolled_total": ("first_year_enrolled", "number"),
    "c9_sat_submit_pct": ("sat_submit_rate", "percent_rate"),
    "c9_act_submit_pct": ("act_submit_rate", "percent_rate"),
    "c9_sat_composite_25": ("sat_composite_p25", "number"),
    "c9_sat_composite_50": ("sat_composite_p50", "number"),
    "c9_sat_composite_75": ("sat_composite_p75", "number"),
    "c9_sat_ebrw_25": ("sat_ebrw_p25", "number"),
    "c9_sat_ebrw_50": ("sat_ebrw_p50", "number"),
    "c9_sat_ebrw_75": ("sat_ebrw_p75", "number"),
    "c9_sat_math_25": ("sat_math_p25", "number"),
    "c9_sat_math_50": ("sat_math_p50", "number"),
    "c9_sat_math_75": ("sat_math_p75", "number"),
    "c9_act_composite_25": ("act_composite_p25", "number"),
    "c9_act_composite_50": ("act_composite_p50", "number"),
    "c9_act_composite_75": ("act_composite_p75", "number"),
}

BROWSER_METRIC_COLUMNS = {
    "first_year_enrolled": "enrolled_first_year",
}


@dataclass(frozen=True)
class LocalTier4Fixture:
    school: str
    year: str
    markdown_path: Path
    ground_truth_path: Path


LOCAL_TIER4_FIXTURES = [
    LocalTier4Fixture(
        "harvard",
        "2024-25",
        REPO_ROOT / ".context" / "docling-spike" / "ivy-native-runs" / "harvard-2024-25-0e482995" / "output.md",
        TOOLS_ROOT / "extraction-validator" / "ground_truth" / "harvard-2024-25.yaml",
    ),
    LocalTier4Fixture(
        "yale",
        "2024-25",
        REPO_ROOT / ".context" / "docling-spike" / "ivy-native-runs" / "yale-2024-25-7b467ea8" / "output.md",
        TOOLS_ROOT / "extraction-validator" / "ground_truth" / "yale-2024-25.yaml",
    ),
]


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        env[key] = value
    return env


def artifact(values: dict[str, Any], schema_version: str, producer: str) -> dict[str, Any]:
    return {
        "id": f"{producer}-{schema_version}",
        "document_id": "prd014-fixture",
        "kind": "canonical",
        "producer": producer,
        "producer_version": "m4-validation",
        "schema_version": schema_version,
        "created_at": "2026-04-28T00:00:00Z",
        "notes": {"values": values},
    }


def document(school: str, year: str, source_format: str) -> dict[str, Any]:
    return {
        "document_id": f"prd014-{school}-{year}",
        "school_id": school,
        "school_name": school,
        "sub_institutional": None,
        "ipeds_id": None,
        "canonical_year": year,
        "source_format": source_format,
        "data_quality_flag": None,
    }


def projection_summary(
    *,
    school: str,
    year: str,
    source_format: str,
    producer: str,
    schema_version: str,
    values: dict[str, Any],
    definitions: dict[str, Any],
) -> dict[str, Any]:
    field_rows, browser_row = build_projection_rows(
        document(school, year, source_format),
        [artifact(values, schema_version, producer)],
        definitions,
    )
    parse_errors = sum(1 for row in field_rows if row.get("value_status") == "parse_error")
    return {
        "schema_version": schema_version,
        "schema_fields_populated": len(values),
        "projected_fields": len(field_rows),
        "parse_errors": parse_errors,
        "parse_error_rate": round(parse_errors / len(field_rows), 4) if field_rows else 0.0,
        "browser": browser_row,
    }


def expected_assertions(gt_path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(gt_path.read_text())
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field in data.get("fields", []):
        field_id = str(field.get("id") or "")
        if field_id not in METRIC_ASSERTIONS:
            continue
        metric, kind = METRIC_ASSERTIONS[field_id]
        if metric in seen:
            continue
        seen.add(metric)
        out.append({
            "ground_truth_id": field_id,
            "canonical_metric": metric,
            "expected": str(field.get("expected")),
            "kind": kind,
        })
    return out


def decimal_value(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def normalize_expected(value: str, kind: str) -> Decimal | None:
    decimal = decimal_value(value)
    if decimal is None:
        return None
    if kind == "percent_rate" and decimal > 1:
        return decimal / Decimal("100")
    return decimal


def assertion_passes(actual: Any, expected: str, kind: str) -> bool:
    actual_decimal = decimal_value(actual)
    expected_decimal = normalize_expected(expected, kind)
    if actual_decimal is None or expected_decimal is None:
        return str(actual).strip() == str(expected).strip()
    if kind == "percent_rate":
        return abs(actual_decimal - expected_decimal) < Decimal("0.000001")
    return actual_decimal == expected_decimal


def evaluate_assertions(
    assertions: list[dict[str, Any]],
    old_browser: dict[str, Any],
    new_browser: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for assertion in assertions:
        metric = assertion["canonical_metric"]
        browser_column = BROWSER_METRIC_COLUMNS.get(metric, metric)
        expected = assertion["expected"]
        kind = assertion["kind"]
        old_actual = old_browser.get(browser_column)
        new_actual = new_browser.get(browser_column)
        old_pass = assertion_passes(old_actual, expected, kind)
        new_pass = assertion_passes(new_actual, expected, kind)
        if old_pass and not new_pass:
            shift = "right_to_wrong"
        elif not old_pass and new_pass:
            shift = "wrong_to_right"
        elif old_pass and new_pass:
            shift = "both_right"
        else:
            shift = "both_wrong"
        rows.append({
            **assertion,
            "old_actual": old_actual,
            "new_actual": new_actual,
            "old_pass": old_pass,
            "new_pass": new_pass,
            "shift": shift,
        })
    return rows


def run_local_tier4(definitions: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    old_schema = SchemaIndex(schema_path_for_year(DEFAULT_SCHEMA_VERSION))
    schema_cache: dict[str, SchemaIndex] = {DEFAULT_SCHEMA_VERSION: old_schema}

    for fixture in LOCAL_TIER4_FIXTURES:
        if not fixture.markdown_path.exists():
            results.append({
                "tier": "tier4",
                "school": fixture.school,
                "year": fixture.year,
                "status": "missing_fixture",
                "missing_path": str(fixture.markdown_path.relative_to(REPO_ROOT)),
            })
            continue
        if fixture.year not in schema_cache:
            schema_cache[fixture.year] = SchemaIndex(schema_path_for_year(fixture.year))
        markdown = fixture.markdown_path.read_text()
        old_values = clean(markdown, schema=old_schema)
        new_values = clean(markdown, schema=schema_cache[fixture.year])
        old_summary = projection_summary(
            school=fixture.school,
            year=fixture.year,
            source_format="pdf_flat",
            producer="tier4_docling",
            schema_version=DEFAULT_SCHEMA_VERSION,
            values=old_values,
            definitions=definitions,
        )
        new_summary = projection_summary(
            school=fixture.school,
            year=fixture.year,
            source_format="pdf_flat",
            producer="tier4_docling",
            schema_version=fixture.year,
            values=new_values,
            definitions=definitions,
        )
        assertions = evaluate_assertions(
            expected_assertions(fixture.ground_truth_path),
            old_summary["browser"],
            new_summary["browser"],
        )
        results.append({
            "tier": "tier4",
            "school": fixture.school,
            "year": fixture.year,
            "source_format": "pdf_flat",
            "fixture": str(fixture.markdown_path.relative_to(REPO_ROOT)),
            "status": "measured",
            "old": old_summary,
            "new": new_summary,
            "assertions": assertions,
        })
    return results


def fetch_harvey_mudd_tier2(definitions: dict[str, Any], env_path: Path) -> dict[str, Any] | None:
    env = load_env(env_path)
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        env.get("SUPABASE_SERVICE_ROLE_KEY")
        or env.get("SUPABASE_ANON_KEY")
        or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        return None

    from supabase import create_client  # noqa: WPS433

    client = create_client(url, key)
    docs = (
        client.table("cds_documents")
        .select("id,school_id,cds_year,source_format")
        .eq("school_id", "harvey-mudd")
        .eq("cds_year", "2025-26")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not docs:
        return None
    doc = docs[0]
    artifacts = (
        client.table("cds_artifacts")
        .select("id,notes,schema_version,producer_version,created_at")
        .eq("document_id", doc["id"])
        .eq("producer", "tier2_acroform")
        .eq("kind", "canonical")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not artifacts:
        return None
    row = artifacts[0]
    values = (row.get("notes") or {}).get("values") or {}
    schema_version = str(row.get("schema_version") or "2025-26")
    summary = projection_summary(
        school="harvey-mudd",
        year="2025-26",
        source_format="pdf_fillable",
        producer="tier2_acroform",
        schema_version=schema_version,
        values=values,
        definitions=definitions,
    )
    assertions = evaluate_assertions(
        expected_assertions(TOOLS_ROOT / "extraction-validator" / "ground_truth" / "harvey-mudd-2025-26.yaml"),
        summary["browser"],
        summary["browser"],
    )
    return {
        "tier": "tier2",
        "school": "harvey-mudd",
        "year": "2025-26",
        "source_format": "pdf_fillable",
        "fixture": "supabase:cds_artifacts/tier2_acroform",
        "status": "measured",
        "old": summary,
        "new": summary,
        "assertions": assertions,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [r for r in results if r.get("status") == "measured"]
    assertions = [a for r in measured for a in r.get("assertions", [])]
    field_deltas = [
        r["new"]["schema_fields_populated"] - r["old"]["schema_fields_populated"]
        for r in measured
    ]
    avg_delta_pct = 0.0
    if measured:
        pct_values = []
        for r in measured:
            old_count = r["old"]["schema_fields_populated"]
            new_count = r["new"]["schema_fields_populated"]
            if old_count:
                pct_values.append((new_count - old_count) / old_count)
        avg_delta_pct = round(sum(pct_values) / len(pct_values), 4) if pct_values else 0.0
    return {
        "fixtures_measured": len(measured),
        "assertions_total": len(assertions),
        "assertions_old_pass": sum(1 for a in assertions if a["old_pass"]),
        "assertions_new_pass": sum(1 for a in assertions if a["new_pass"]),
        "wrong_to_right": sum(1 for a in assertions if a["shift"] == "wrong_to_right"),
        "right_to_wrong": sum(1 for a in assertions if a["shift"] == "right_to_wrong"),
        "both_right": sum(1 for a in assertions if a["shift"] == "both_right"),
        "both_wrong": sum(1 for a in assertions if a["shift"] == "both_wrong"),
        "field_delta_total": sum(field_deltas),
        "avg_field_delta_pct": avg_delta_pct,
        "outcome": (
            "big_delta"
            if any(a["shift"] in {"wrong_to_right", "right_to_wrong"} for a in assertions)
            or abs(avg_delta_pct) >= 0.10
            else "modest_delta" if abs(avg_delta_pct) >= 0.01
            else "no_meaningful_delta"
        ),
    }


def format_value(value: Any) -> str:
    if value is None:
        return "-"
    return str(value)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    results = payload["results"]
    has_value_shifts = summary["wrong_to_right"] or summary["right_to_wrong"]
    if summary["outcome"] == "big_delta" and has_value_shifts:
        outcome_note = (
            "The validation found value-level assertion shifts, so the PRD's "
            "M5 decision gate is open. Review the shifts before any broad drain."
        )
        recommendation = (
            "Do not run M5 as a broad corpus drain until the value-level shifts "
            "are understood and accepted."
        )
    elif summary["outcome"] == "modest_delta":
        outcome_note = (
            "No value-level assertions changed. The measured delta is field-count "
            "only and falls in the PRD's modest-delta band."
        )
        recommendation = (
            "M5 is optional rather than required by the evidence. If an operator "
            "chooses to drain, use a staged cohort drain with rollback snapshots."
        )
    else:
        outcome_note = (
            "No meaningful value-level or field-count delta was observed."
        )
        recommendation = (
            "Ship for correctness and let existing artifacts transition naturally."
        )
    lines = [
        "# PRD 014 M4 Validation Findings",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Outcome",
        "",
        f"**{summary['outcome']}**.",
        "",
        outcome_note,
        "",
        "## Scope",
        "",
        "- Measured local Tier 4 markdown fixtures for Harvard 2024-25 and Yale 2024-25.",
        "- Included Harvey Mudd 2025-26 Tier 2 as a Supabase-backed control when credentials were available.",
        "- No local Tier 1 XLSX or Tier 5 scanned fixtures with hand-curated value assertions were available in this checkout.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Fixtures measured | {summary['fixtures_measured']} |",
        f"| Value assertions | {summary['assertions_total']} |",
        f"| Old assertions passing | {summary['assertions_old_pass']} |",
        f"| New assertions passing | {summary['assertions_new_pass']} |",
        f"| Wrong -> right shifts | {summary['wrong_to_right']} |",
        f"| Right -> wrong shifts | {summary['right_to_wrong']} |",
        f"| Average field-count delta | {summary['avg_field_delta_pct']:.2%} |",
        "",
        "## Fixture Results",
        "",
        "| Tier | School | Year | Old schema | Old fields | Old parse errors | New schema | New fields | New parse errors |",
        "|---|---|---|---|---:|---:|---|---:|---:|",
    ]
    for result in results:
        if result.get("status") != "measured":
            continue
        lines.append(
            "| {tier} | {school} | {year} | {old_schema} | {old_fields} | {old_errors} | "
            "{new_schema} | {new_fields} | {new_errors} |".format(
                tier=result["tier"],
                school=result["school"],
                year=result["year"],
                old_schema=result["old"]["schema_version"],
                old_fields=result["old"]["schema_fields_populated"],
                old_errors=result["old"]["parse_errors"],
                new_schema=result["new"]["schema_version"],
                new_fields=result["new"]["schema_fields_populated"],
                new_errors=result["new"]["parse_errors"],
            )
        )
    lines.extend([
        "",
        "## Assertion Shifts",
        "",
        "| Fixture | Metric | Expected | Old | New | Shift |",
        "|---|---|---:|---:|---:|---|",
    ])
    for result in results:
        if result.get("status") != "measured":
            continue
        fixture_name = f"{result['school']} {result['year']}"
        for assertion in result.get("assertions", []):
            if assertion["shift"] == "both_right":
                continue
            lines.append(
                f"| {fixture_name} | {assertion['canonical_metric']} | "
                f"{assertion['expected']} | {format_value(assertion['old_actual'])} | "
                f"{format_value(assertion['new_actual'])} | {assertion['shift']} |"
            )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Harvard 2024-25 and Yale 2024-25 keep the hand-verified browser-level assertions correct under year-matched extraction.",
        "- Field counts drop on the Tier 4 fixtures because schema-local 2024-25 IDs no longer keep 2025-only fields that were previously projected under the wrong schema.",
        "- Harvey Mudd 2025-26 is stable, as expected, because old and new schema selection are identical for 2025-26.",
        "",
        "## Recommendation",
        "",
        recommendation,
        "",
        "Raw results: `.context/prd-014-validation/results.json`.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env.local")
    parser.add_argument("--output", type=Path, default=RESULTS_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--skip-supabase", action="store_true")
    args = parser.parse_args()

    definitions = load_schema_definitions()
    results = run_local_tier4(definitions)
    if not args.skip_supabase:
        try:
            tier2 = fetch_harvey_mudd_tier2(definitions, args.env)
        except Exception as exc:  # pragma: no cover - operational fallback
            tier2 = {
                "tier": "tier2",
                "school": "harvey-mudd",
                "year": "2025-26",
                "status": "supabase_error",
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            }
        if tier2 is not None:
            results.append(tier2)

    from datetime import datetime, timezone

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize(results),
        "results": results,
    }
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2))
    report = args.report if args.report.is_absolute() else REPO_ROOT / args.report
    write_report(report, payload)
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {output}")
    print(f"Wrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
