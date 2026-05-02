#!/usr/bin/env python3
"""PRD 016B Phase 0 answerability audit.

Measures ED-count answerability across current 2024-25+ primary
school_browser_rows. For Tier 4 rows, re-runs the current checkout's
tier4_cleaner against stored artifact markdown so resolver improvements can be
measured before a projection migration.

Usage:
    python tools/browser_backend/prd016b_phase0_audit.py --limit 25
    python tools/browser_backend/prd016b_phase0_audit.py --output-dir scratch/admission-strategy-coverage
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "browser_backend"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "extraction_worker"))

import project_browser_data as pbd  # noqa: E402
from tier4_cleaner import clean as clean_tier4  # noqa: E402


CANONICAL_ED_APPLICANTS = "C.2110"
CANONICAL_ED_ADMITTED = "C.2111"
PUBLIC_SUPABASE_URL = "https://isduwmygvmdozhpvzaix.supabase.co"
PUBLIC_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlzZHV3bXlndm1kb3pocHZ6YWl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDk3NTksImV4cCI6MjA5MTY4NTc1OX0."
    "fYZOIHyrOWzidgc-CVxWCY5Fe9pQk12-6YjDIS6y9qs"
)


@dataclass
class AuditRow:
    document_id: str
    school_id: str
    school_name: str
    canonical_year: str
    producer: str
    applied: int | None
    admitted: int | None
    ed_offered: bool | None
    ea_offered: bool | None
    ea_restrictive: bool | None
    ed_applicants: int | None
    ed_admitted: int | None
    ed_has_second_deadline: bool
    ed_answerable: bool
    verifier_rejection: str | None


def decimal_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(Decimal(str(value).replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def bool_from_text(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"yes", "true", "1", "x"}:
        return True
    if text in {"no", "false", "0"}:
        return False
    return None


def record_value(record: Any) -> Any:
    return pbd.display_value(record)


def canonical_values(schema_version: str, values: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field_id, record in values.items():
        canonical_field_id, _kind = pbd.field_equivalence(schema_version, field_id)
        if canonical_field_id and canonical_field_id not in out:
            out[canonical_field_id] = record_value(record)
    return out


def has_second_deadline(schema_version: str, values: dict[str, Any]) -> bool:
    raw = {field_id: record_value(record) for field_id, record in values.items()}
    if schema_version == "2024-25":
        return bool(raw.get("C.2104") or raw.get("C.2105"))
    return bool(raw.get("C.2106") or raw.get("C.2107") or raw.get("C.2108") or raw.get("C.2109"))


def selected_values_with_tier4_rerun(
    selected: pbd.SelectedExtractionResult,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    values = dict(selected.values)
    if selected.base_producer != "tier4_docling":
        return values

    base = next(
        (artifact for artifact in artifacts if str(artifact.get("id")) == selected.base_artifact_id),
        None,
    )
    notes = base.get("notes") if base else None
    markdown = notes.get("markdown") if isinstance(notes, dict) else None
    if not isinstance(markdown, str) or not markdown.strip():
        return values

    for field_id in [
        "C.2101",
        "C.2102",
        "C.2103",
        "C.2104",
        "C.2105",
        "C.2106",
        "C.2107",
        "C.2108",
        "C.2109",
        "C.2110",
        "C.2111",
        "C.2201",
        "C.2202",
        "C.2203",
        "C.2204",
        "C.2205",
        "C.2206",
    ]:
        values.pop(field_id, None)

    refreshed = clean_tier4(markdown, canonical_year=selected.schema_version)
    for field_id, record in refreshed.items():
        values[field_id] = record
    return values


def fetch_browser_rows(client: Any, limit: int | None) -> list[dict[str, Any]]:
    select_cols = (
        "document_id,school_id,school_name,canonical_year,year_start,producer,"
        "applied,admitted,acceptance_rate,ed_offered,ea_offered,ea_restrictive,"
        "ed_applicants,ed_admitted,ed_has_second_deadline"
    )
    page_size = 1000
    offset = 0
    rows: list[dict[str, Any]] = []
    while True:
        query = (
            client.table("school_browser_rows")
            .select(select_cols)
            .gte("year_start", 2024)
            .is_("sub_institutional", "null")
            .order("year_start", desc=True)
            .range(offset, offset + page_size - 1)
        )
        result = query.execute()
        batch = result.data or []
        rows.extend(batch)
        if limit and len(rows) >= limit:
            return rows[:limit]
        if len(batch) < page_size:
            return rows
        offset += page_size


def audit_row(client: Any, row: dict[str, Any]) -> AuditRow | None:
    ed_offered = row.get("ed_offered")
    if not isinstance(ed_offered, bool):
        ed_offered = bool_from_text(ed_offered)
    ea_offered = row.get("ea_offered")
    if not isinstance(ea_offered, bool):
        ea_offered = bool_from_text(ea_offered)
    ea_restrictive = row.get("ea_restrictive")
    if not isinstance(ea_restrictive, bool):
        ea_restrictive = bool_from_text(ea_restrictive)
    ed_applicants = decimal_int(row.get("ed_applicants"))
    ed_admitted = decimal_int(row.get("ed_admitted"))
    applied = decimal_int(row.get("applied"))
    admitted = decimal_int(row.get("admitted"))
    verifier_rejection = None
    if ed_applicants is not None and ed_admitted is not None:
        if ed_admitted > ed_applicants:
            verifier_rejection = "ed_admitted_gt_ed_applicants"
        elif admitted is not None and admitted > 0 and ed_admitted > admitted:
            verifier_rejection = "ed_admitted_gt_c1_admitted"

    return AuditRow(
        document_id=str(row["document_id"]),
        school_id=str(row["school_id"]),
        school_name=str(row["school_name"]),
        canonical_year=str(row["canonical_year"]),
        producer=str(row.get("producer") or "unknown"),
        applied=applied,
        admitted=admitted,
        ed_offered=ed_offered,
        ea_offered=ea_offered,
        ea_restrictive=ea_restrictive,
        ed_applicants=ed_applicants,
        ed_admitted=ed_admitted,
        ed_has_second_deadline=bool(row.get("ed_has_second_deadline")),
        ed_answerable=(
            ed_applicants is not None
            and ed_admitted is not None
            and verifier_rejection is None
        ),
        verifier_rejection=verifier_rejection,
    )


def pct(numerator: int, denominator: int) -> float | None:
    return round((numerator / denominator) * 100, 1) if denominator else None


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * frac, 4)


def build_summary(rows: list[AuditRow]) -> dict[str, Any]:
    by_producer = Counter(row.producer for row in rows)
    answerable_by_producer = Counter(row.producer for row in rows if row.ed_answerable)
    verifier_rejections = Counter(row.verifier_rejection for row in rows if row.verifier_rejection)
    top_200 = sorted(rows, key=lambda row: row.applied or 0, reverse=True)[:200]
    ed_offered_rows = [row for row in rows if row.ed_offered is True]
    ea_offered_rows = [row for row in rows if row.ea_offered is True]
    early_plan_offered_rows = [
        row for row in rows if row.ed_offered is True or row.ea_offered is True
    ]
    top_200_ed_offered = [row for row in top_200 if row.ed_offered is True]
    top_200_ea_offered = [row for row in top_200 if row.ea_offered is True]
    top_200_early_plan_offered = [
        row for row in top_200 if row.ed_offered is True or row.ea_offered is True
    ]
    ed_share_values = [
        row.ed_admitted / row.admitted
        for row in rows
        if row.ed_answerable and row.ed_admitted is not None and row.admitted and row.admitted > 0
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "ed_answerable_count": sum(row.ed_answerable for row in rows),
        "ed_answerable_pct": pct(sum(row.ed_answerable for row in rows), len(rows)),
        "ed_offered_true_count": len(ed_offered_rows),
        "ed_offered_true_answerable_count": sum(row.ed_answerable for row in ed_offered_rows),
        "ed_offered_true_answerable_pct": pct(
            sum(row.ed_answerable for row in ed_offered_rows),
            len(ed_offered_rows),
        ),
        "ea_offered_true_count": len(ea_offered_rows),
        "early_plan_offered_true_count": len(early_plan_offered_rows),
        "early_plan_offered_true_answerable_count": sum(
            row.ed_answerable for row in early_plan_offered_rows
        ),
        "early_plan_offered_true_answerable_pct": pct(
            sum(row.ed_answerable for row in early_plan_offered_rows),
            len(early_plan_offered_rows),
        ),
        "producer_counts": dict(sorted(by_producer.items())),
        "producer_answerability": {
            producer: {
                "answerable": answerable_by_producer[producer],
                "total": by_producer[producer],
                "pct": pct(answerable_by_producer[producer], by_producer[producer]),
            }
            for producer in sorted(by_producer)
        },
        "ed_offered_counts": dict(Counter(str(row.ed_offered) for row in rows)),
        "ea_offered_counts": dict(Counter(str(row.ea_offered) for row in rows)),
        "ea_restrictive_counts": dict(Counter(str(row.ea_restrictive) for row in rows)),
        "ed_second_deadline_count": sum(row.ed_has_second_deadline for row in rows),
        "ed_second_deadline_pct": pct(sum(row.ed_has_second_deadline for row in rows), len(rows)),
        "top_200_row_count": len(top_200),
        "top_200_answerable_count": sum(row.ed_answerable for row in top_200),
        "top_200_answerable_pct": pct(sum(row.ed_answerable for row in top_200), len(top_200)),
        "top_200_ed_offered_true_count": len(top_200_ed_offered),
        "top_200_ed_offered_true_answerable_count": sum(row.ed_answerable for row in top_200_ed_offered),
        "top_200_ed_offered_true_answerable_pct": pct(
            sum(row.ed_answerable for row in top_200_ed_offered),
            len(top_200_ed_offered),
        ),
        "top_200_ea_offered_true_count": len(top_200_ea_offered),
        "top_200_early_plan_offered_true_count": len(top_200_early_plan_offered),
        "top_200_early_plan_offered_true_answerable_count": sum(
            row.ed_answerable for row in top_200_early_plan_offered
        ),
        "top_200_early_plan_offered_true_answerable_pct": pct(
            sum(row.ed_answerable for row in top_200_early_plan_offered),
            len(top_200_early_plan_offered),
        ),
        "ed_share_of_admitted_distribution": {
            "count": len(ed_share_values),
            "p25": quantile(ed_share_values, 0.25),
            "p50": quantile(ed_share_values, 0.5),
            "p75": quantile(ed_share_values, 0.75),
            "p90": quantile(ed_share_values, 0.9),
        },
        "verifier_rejections": dict(sorted(verifier_rejections.items())),
    }


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    producer_lines = "\n".join(
        f"| {producer} | {stats['answerable']} | {stats['total']} | {stats['pct']}% |"
        for producer, stats in summary["producer_answerability"].items()
    )
    gate_pct = summary["top_200_ed_offered_true_answerable_pct"]
    gate_decision = (
        "- Card eligibility floor: **cleared for migration**. Current answerability clears the draft 70% top-200 ED-offered gate."
        if gate_pct is not None and gate_pct >= 70
        else "- Card eligibility floor: **blocked for migration**. Current answerability is below the draft 70% top-200 ED-offered gate."
    )
    path.write_text(
        "\n".join(
            [
                "# PRD 016B Phase 0 Findings",
                "",
                f"Generated: `{summary['generated_at']}`",
                "",
                "## Summary",
                "",
                f"- Rows audited: `{summary['row_count']}`",
                f"- ED-count answerability: `{summary['ed_answerable_count']}` / `{summary['row_count']}` (`{summary['ed_answerable_pct']}%`)",
                f"- ED-offered answerability: `{summary['ed_offered_true_answerable_count']}` / `{summary['ed_offered_true_count']}` (`{summary['ed_offered_true_answerable_pct']}%`)",
                f"- EA-offered rows: `{summary['ea_offered_true_count']}`",
                f"- ED-or-EA-offered rows: `{summary['early_plan_offered_true_count']}`; ED-count answerable for `{summary['early_plan_offered_true_answerable_count']}` (`{summary['early_plan_offered_true_answerable_pct']}%`)",
                f"- Top-200-by-applicants answerability: `{summary['top_200_answerable_count']}` / `{summary['top_200_row_count']}` (`{summary['top_200_answerable_pct']}%`)",
                f"- Top-200 ED-offered answerability: `{summary['top_200_ed_offered_true_answerable_count']}` / `{summary['top_200_ed_offered_true_count']}` (`{summary['top_200_ed_offered_true_answerable_pct']}%`)",
                f"- Top-200 EA-offered rows: `{summary['top_200_ea_offered_true_count']}`",
                f"- Top-200 ED-or-EA-offered rows: `{summary['top_200_early_plan_offered_true_count']}`; ED-count answerable for `{summary['top_200_early_plan_offered_true_answerable_count']}` (`{summary['top_200_early_plan_offered_true_answerable_pct']}%`)",
                f"- ED second-deadline signal: `{summary['ed_second_deadline_count']}` rows (`{summary['ed_second_deadline_pct']}%`)",
                f"- ED share of admitted distribution: `{summary['ed_share_of_admitted_distribution']}`",
                f"- Verifier rejections: `{summary['verifier_rejections']}`",
                "",
                "## Producer Answerability",
                "",
                "| Producer | Answerable | Total | Pct |",
                "|---|---:|---:|---:|",
                producer_lines,
                "",
                "## Threshold Decisions",
                "",
                gate_decision,
                "- Class-composition emphasis threshold: use the measured p75 ED-share value as the candidate loud-emphasis threshold once answerability clears.",
                "- Verifier policy: suppress the affected block, not the document; rejection examples need spot audit before migration.",
                "",
            ]
        )
    )


def make_read_client() -> Any:
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit("Missing dependency: pip install supabase") from exc

    env = {**pbd.load_env(), **dict(__import__("os").environ)}
    url = (
        env.get("SUPABASE_URL")
        or env.get("NEXT_PUBLIC_SUPABASE_URL")
        or PUBLIC_SUPABASE_URL
    )
    key = (
        env.get("SUPABASE_SERVICE_ROLE_KEY")
        or env.get("SUPABASE_ANON_KEY")
        or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        or PUBLIC_SUPABASE_ANON_KEY
    )
    return create_client(url, key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--limit", type=int, help="Limit rows for a smoke audit")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "scratch" / "admission-strategy-coverage",
    )
    args = parser.parse_args()

    client = make_read_client()
    browser_rows = fetch_browser_rows(client, args.limit)
    rows = [
        audited
        for source_row in browser_rows
        if (audited := audit_row(client, source_row)) is not None
    ]
    summary = build_summary(rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "prd016b_phase0_rows.json").write_text(
        json.dumps([asdict(row) for row in rows], indent=2, sort_keys=True)
    )
    (args.output_dir / "prd016b_phase0_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
    write_markdown(REPO_ROOT / "docs" / "plans" / "prd-016b-phase-0-findings.md", summary)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
