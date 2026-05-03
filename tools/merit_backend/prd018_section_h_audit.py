#!/usr/bin/env python3
"""PRD 018 Section H answerability audit.

Measures answerability for the financial-aid fields needed by the PRD 018
merit profile before building a public projection. The audit reads the
already-projected public serving tables:

  - school_browser_rows: latest primary 2024+ rows and top-applicant ordering
  - cds_fields: long-form Section H values for those documents

Usage:
    python tools/merit_backend/prd018_section_h_audit.py
    python tools/merit_backend/prd018_section_h_audit.py --limit 365 --output-dir scratch/prd018
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supabase import create_client


PUBLIC_SUPABASE_URL = "https://isduwmygvmdozhpvzaix.supabase.co"


@dataclass(frozen=True)
class TargetMetric:
    key: str
    label: str
    field_ids: tuple[str, ...]
    preferred_kind: str


TARGET_METRICS: tuple[TargetMetric, ...] = (
    TargetMetric(
        "need_grants_total",
        "H1 need-based total scholarships/grants",
        ("H.109",),
        "currency",
    ),
    TargetMetric(
        "non_need_grants_total",
        "H1 non-need-based total scholarships/grants",
        ("H.121",),
        "currency",
    ),
    TargetMetric(
        "aid_recipients_first_year_ft",
        "H2 first-year/full-time students awarded aid",
        ("H.204",),
        "number",
    ),
    TargetMetric(
        "aid_recipients_all_ft",
        "H2 all full-time students awarded aid",
        ("H.217",),
        "number",
    ),
    TargetMetric(
        "avg_aid_package_first_year_ft",
        "H2 average financial-aid package, first-year/full-time",
        ("H.210",),
        "currency",
    ),
    TargetMetric(
        "avg_aid_package_all_ft",
        "H2 average financial-aid package, all full-time",
        ("H.223",),
        "currency",
    ),
    TargetMetric(
        "avg_need_grant_first_year_ft",
        "H2 average need-based scholarship/grant, first-year/full-time",
        ("H.211",),
        "currency",
    ),
    TargetMetric(
        "avg_need_grant_all_ft",
        "H2 average need-based scholarship/grant, all full-time",
        ("H.224",),
        "currency",
    ),
    TargetMetric(
        "avg_need_self_help_first_year_ft",
        "H2 average need-based self-help, first-year/full-time",
        ("H.212",),
        "currency",
    ),
    TargetMetric(
        "avg_need_self_help_all_ft",
        "H2 average need-based self-help, all full-time",
        ("H.225",),
        "currency",
    ),
    TargetMetric(
        "non_need_aid_recipients_first_year_ft",
        "H2A students with non-need institutional grant aid, first-year/full-time",
        ("H.2A01",),
        "number",
    ),
    TargetMetric(
        "avg_non_need_grant_first_year_ft",
        "H2A average non-need institutional grant aid, first-year/full-time",
        ("H.2A02",),
        "currency",
    ),
    TargetMetric(
        "non_need_aid_recipients_all_ft",
        "H2A students with non-need institutional grant aid, all full-time",
        ("H.2A05",),
        "number",
    ),
    TargetMetric(
        "avg_non_need_grant_all_ft",
        "H2A average non-need institutional grant aid, all full-time",
        ("H.2A06",),
        "currency",
    ),
    TargetMetric(
        "institutional_need_aid_nonresident",
        "H6 institutional need-based aid for nonresidents",
        ("H.601",),
        "checkbox",
    ),
    TargetMetric(
        "institutional_non_need_aid_nonresident",
        "H6 institutional non-need aid for nonresidents",
        ("H.602",),
        "checkbox",
    ),
    TargetMetric(
        "avg_international_aid",
        "H6 average institutional aid to nonresidents",
        ("H.605",),
        "currency",
    ),
    TargetMetric(
        "institutional_aid_academics",
        "H14 institutional aid awarded for academics",
        ("H.1401", "H.1411"),
        "checkbox",
    ),
)

FIELD_IDS = tuple(sorted({field_id for metric in TARGET_METRICS for field_id in metric.field_ids}))


@dataclass
class AuditRow:
    document_id: str
    school_id: str
    school_name: str
    canonical_year: str
    producer: str
    applied: int | None
    answerable_count: int
    answerable_pct: float
    core_answerable_count: int
    core_answerable_pct: float
    effective_merit_answerable: bool


def supabase_client(env_path: Path | None):
    if env_path:
        for line in env_path.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or PUBLIC_SUPABASE_URL
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not key:
        raise SystemExit("SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY is required")
    return create_client(url, key)


def fetch_all(query: Any, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = query.range(offset, offset + page_size - 1).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size


def fetch_latest_browser_rows(client: Any) -> list[dict[str, Any]]:
    rows = fetch_all(
        client.table("school_browser_rows")
        .select("document_id,school_id,school_name,canonical_year,year_start,producer,applied")
        .gte("year_start", 2024)
        .is_("sub_institutional", "null")
        .order("school_id", desc=False)
        .order("year_start", desc=True),
    )
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        school_id = str(row["school_id"])
        latest.setdefault(school_id, row)
    return list(latest.values())


def fetch_target_fields(client: Any, document_ids: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    by_document: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for start in range(0, len(document_ids), 100):
        chunk = document_ids[start : start + 100]
        rows = fetch_all(
            client.table("cds_fields")
            .select("document_id,field_id,value_num,value_text,value_bool,value_kind,value_status,producer")
            .in_("document_id", chunk)
            .in_("field_id", list(FIELD_IDS)),
        )
        for row in rows:
            by_document[str(row["document_id"])][str(row["field_id"])] = row
    return by_document


def is_answerable(row: dict[str, Any] | None) -> bool:
    if not row or row.get("value_status") != "reported":
        return False
    if row.get("value_bool") is not None:
        return True
    if row.get("value_num") is not None:
        return True
    text = row.get("value_text")
    return isinstance(text, str) and text.strip() != ""


def numeric_value(row: dict[str, Any] | None) -> float | None:
    if not is_answerable(row):
        return None
    if row.get("value_num") is not None:
        try:
            return float(row["value_num"])
        except (TypeError, ValueError):
            pass
    text = row.get("value_text")
    if not isinstance(text, str):
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def effective_merit_answerable(doc_fields: dict[str, dict[str, Any]]) -> bool:
    """True when the first-year merit figure is directly reported or inferably zero.

    CDS H2A average non-need grant can be blank when the school reports no
    institutional non-need aid. Treat zero H2A recipients or zero H1 non-need
    grant dollars as answerable "no reported merit" rather than an extraction
    miss.
    """

    if is_answerable(doc_fields.get("H.2A02")):
        return True
    recipients = numeric_value(doc_fields.get("H.2A01"))
    if recipients == 0:
        return True
    non_need_total = numeric_value(doc_fields.get("H.121"))
    return non_need_total == 0


def pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 1) if denominator else 0.0


def build_audit(rows: list[dict[str, Any]], fields_by_document: dict[str, dict[str, dict[str, Any]]]) -> list[AuditRow]:
    core_keys = {
        "avg_aid_package_first_year_ft",
        "avg_need_grant_first_year_ft",
        "avg_need_self_help_first_year_ft",
        "avg_non_need_grant_first_year_ft",
        "non_need_aid_recipients_first_year_ft",
    }
    out: list[AuditRow] = []
    for row in rows:
        doc_fields = fields_by_document.get(str(row["document_id"]), {})
        metric_answerable = {
            metric.key: any(is_answerable(doc_fields.get(field_id)) for field_id in metric.field_ids)
            for metric in TARGET_METRICS
        }
        effective_merit = effective_merit_answerable(doc_fields)
        answerable_count = sum(metric_answerable.values())
        core_answerable_count = sum(metric_answerable[key] for key in core_keys)
        if effective_merit and not metric_answerable["avg_non_need_grant_first_year_ft"]:
            core_answerable_count += 1
        out.append(
            AuditRow(
                document_id=str(row["document_id"]),
                school_id=str(row["school_id"]),
                school_name=str(row["school_name"]),
                canonical_year=str(row["canonical_year"]),
                producer=str(row.get("producer") or "unknown"),
                applied=int(row["applied"]) if row.get("applied") is not None else None,
                answerable_count=answerable_count,
                answerable_pct=pct(answerable_count, len(TARGET_METRICS)),
                core_answerable_count=core_answerable_count,
                core_answerable_pct=pct(core_answerable_count, len(core_keys)),
                effective_merit_answerable=effective_merit,
            )
        )
    return out


def metric_summary(rows: list[dict[str, Any]], fields_by_document: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for metric in TARGET_METRICS:
        answerable = 0
        by_producer: Counter[str] = Counter()
        for row in rows:
            doc_fields = fields_by_document.get(str(row["document_id"]), {})
            if any(is_answerable(doc_fields.get(field_id)) for field_id in metric.field_ids):
                answerable += 1
                by_producer[str(row.get("producer") or "unknown")] += 1
        out.append(
            {
                "key": metric.key,
                "label": metric.label,
                "field_ids": list(metric.field_ids),
                "answerable_count": answerable,
                "answerable_pct": pct(answerable, len(rows)),
                "answerable_by_producer": dict(sorted(by_producer.items())),
            }
        )
    return out


def build_summary(rows: list[dict[str, Any]], audited: list[AuditRow], metric_rows: list[dict[str, Any]]) -> dict[str, Any]:
    top_100_docs = {row.document_id for row in sorted(audited, key=lambda row: row.applied or 0, reverse=True)[:100]}
    top_100 = [row for row in audited if row.document_id in top_100_docs]
    producer_counts = Counter(str(row.get("producer") or "unknown") for row in rows)
    core_ready = [row for row in audited if row.core_answerable_pct >= 60]
    broadly_ready = [row for row in audited if row.answerable_pct >= 60]
    effective_merit_ready = [row for row in audited if row.effective_merit_answerable]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "producer_counts": dict(sorted(producer_counts.items())),
        "target_metric_count": len(TARGET_METRICS),
        "core_metric_count": 5,
        "rows_with_core_60pct": len(core_ready),
        "rows_with_core_60pct_pct": pct(len(core_ready), len(audited)),
        "rows_with_all_targets_60pct": len(broadly_ready),
        "rows_with_all_targets_60pct_pct": pct(len(broadly_ready), len(audited)),
        "effective_merit_answerable_count": len(effective_merit_ready),
        "effective_merit_answerable_pct": pct(len(effective_merit_ready), len(audited)),
        "avg_core_answerable_pct": round(sum(row.core_answerable_pct for row in audited) / len(audited), 1) if audited else 0,
        "avg_all_targets_answerable_pct": round(sum(row.answerable_pct for row in audited) / len(audited), 1) if audited else 0,
        "top_100_avg_core_answerable_pct": round(sum(row.core_answerable_pct for row in top_100) / len(top_100), 1) if top_100 else 0,
        "metric_summary": metric_rows,
    }


def write_markdown(summary: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# PRD 018 Section H Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Rows audited: `{summary['row_count']}`",
        f"- Rows with >=60% core merit metrics: `{summary['rows_with_core_60pct']}` (`{summary['rows_with_core_60pct_pct']}%`)",
        f"- Average core answerability: `{summary['avg_core_answerable_pct']}%`",
        f"- Top-100 average core answerability: `{summary['top_100_avg_core_answerable_pct']}%`",
        f"- Rows with >=60% all target metrics: `{summary['rows_with_all_targets_60pct']}` (`{summary['rows_with_all_targets_60pct_pct']}%`)",
        f"- Effective first-year merit answerability: `{summary['effective_merit_answerable_count']}` (`{summary['effective_merit_answerable_pct']}%`)",
        "",
        "## Target Metrics",
        "",
        "| Metric | Field IDs | Answerable | Pct |",
        "|---|---:|---:|---:|",
    ]
    for metric in summary["metric_summary"]:
        lines.append(
            f"| {metric['label']} | `{', '.join(metric['field_ids'])}` | {metric['answerable_count']} | {metric['answerable_pct']}% |"
        )
    lines.append("")
    output_path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=365)
    parser.add_argument("--output-dir", type=Path, default=Path("scratch/prd018"))
    args = parser.parse_args()

    client = supabase_client(args.env)
    rows = fetch_latest_browser_rows(client)
    rows = sorted(rows, key=lambda row: row.get("applied") or 0, reverse=True)
    if args.limit:
        rows = rows[: args.limit]
    fields_by_document = fetch_target_fields(client, [str(row["document_id"]) for row in rows])
    audited = build_audit(rows, fields_by_document)
    metrics = metric_summary(rows, fields_by_document)
    summary = build_summary(rows, audited, metrics)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "section-h-audit.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "rows": [asdict(row) for row in audited],
            },
            indent=2,
        )
    )
    write_markdown(summary, args.output_dir / "section-h-audit.md")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
