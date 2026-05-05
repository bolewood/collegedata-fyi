#!/usr/bin/env python3
"""Audit PRD 019 watchlist freshness and propose targeted re-drains.

The change-intelligence projector can only tell a useful story when each
watchlist school has pairable selected-primary rows for the comparison years.
This operator script answers three questions:

1. Which watchlist schools have prior/latest browser rows?
2. Which missing rows already have archived documents that can be re-drained?
3. Which selected Tier 4 rows were produced by an older cleaner version?
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - operator venvs include PyYAML.
    yaml = None

from supabase import Client, create_client


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WATCHLIST = REPO_ROOT / "data" / "watchlists" / "top_200_change_intelligence.yaml"
DEFAULT_OUT_DIR = REPO_ROOT / ".context" / "reports" / "prd019-top200-freshness"
CURRENT_TIER4_VERSION = "0.3.4"
REDRAIN_FORMATS = {"pdf_flat", "pdf_scanned"}
BAD_FLAGS = {"wrong_file", "blank_template", "low_coverage"}


@dataclass(frozen=True)
class WatchSchool:
    school_id: str
    segment: str
    ordinal: int


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def load_env(path: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    for candidate in (
        path,
        REPO_ROOT / ".env",
        Path("/Users/santhonys/Projects/Owen/colleges/collegedata-fyi/.env"),
    ):
        if candidate:
            for key, value in read_env_file(candidate).items():
                env.setdefault(key, value)
    return env


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read watchlist files")
    return yaml.safe_load(path.read_text()) or {}


def load_watchlist(path: Path) -> list[WatchSchool]:
    raw = load_yaml(path)
    schools: list[WatchSchool] = []
    for ordinal, item in enumerate(raw.get("schools") or [], start=1):
        if isinstance(item, str):
            schools.append(WatchSchool(item, "", ordinal))
        elif isinstance(item, dict) and item.get("school_id"):
            schools.append(
                WatchSchool(
                    school_id=str(item["school_id"]),
                    segment=str(item.get("segment") or ""),
                    ordinal=ordinal,
                ),
            )
    return schools


def create_supabase_client(env: dict[str, str]) -> Client:
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise SystemExit("Missing SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/ANON key")
    return create_client(url, key)


def chunks(values: list[str], size: int = 80) -> list[list[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def fetch_browser_rows(
    client: Client,
    school_ids: list[str],
    from_year: int,
    to_year: int,
) -> list[dict[str, Any]]:
    columns = [
        "document_id",
        "school_id",
        "school_name",
        "sub_institutional",
        "canonical_year",
        "year_start",
        "source_format",
        "producer",
        "producer_version",
        "data_quality_flag",
        "archive_url",
        "applied",
        "admitted",
        "enrolled_first_year",
        "acceptance_rate",
        "yield_rate",
        "sat_submit_rate",
        "act_submit_rate",
        "sat_composite_p25",
        "sat_composite_p75",
        "act_composite_p25",
        "act_composite_p75",
    ]
    rows: list[dict[str, Any]] = []
    for page_ids in chunks(school_ids):
        page = (
            client.table("school_browser_rows")
            .select(",".join(columns))
            .in_("school_id", page_ids)
            .gte("year_start", from_year)
            .lte("year_start", to_year)
            .is_("sub_institutional", "null")
            .execute()
            .data
            or []
        )
        rows.extend(page)
    return rows


def fetch_documents(client: Client, school_ids: list[str]) -> list[dict[str, Any]]:
    columns = [
        "id",
        "school_id",
        "school_name",
        "sub_institutional",
        "cds_year",
        "detected_year",
        "source_format",
        "extraction_status",
        "participation_status",
        "data_quality_flag",
        "source_provenance",
        "discovered_at",
        "updated_at",
        "source_url",
    ]
    rows: list[dict[str, Any]] = []
    for page_ids in chunks(school_ids):
        page = (
            client.table("cds_documents")
            .select(",".join(columns))
            .in_("school_id", page_ids)
            .is_("sub_institutional", "null")
            .execute()
            .data
            or []
        )
        rows.extend(page)
    return rows


def year_start(value: Any) -> int | None:
    if not value:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def doc_year(doc: dict[str, Any]) -> int | None:
    return year_start(doc.get("detected_year") or doc.get("cds_year"))


def row_rank(row: dict[str, Any]) -> tuple[int, int, str]:
    bad = 1 if row.get("data_quality_flag") in BAD_FLAGS else 0
    provenance = 0 if row.get("source_provenance") in ("school_direct", "operator_manual") else 1
    return bad, provenance, str(row.get("document_id") or "")


def select_browser_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("sub_institutional") is not None:
            continue
        if row.get("year_start") is None:
            continue
        grouped.setdefault((str(row["school_id"]), int(row["year_start"])), []).append(row)
    return {key: sorted(values, key=row_rank)[0] for key, values in grouped.items()}


def useful_field_count(row: dict[str, Any] | None) -> int:
    if not row:
        return 0
    keys = [
        "applied",
        "admitted",
        "enrolled_first_year",
        "acceptance_rate",
        "yield_rate",
        "sat_submit_rate",
        "act_submit_rate",
        "sat_composite_p25",
        "sat_composite_p75",
        "act_composite_p25",
        "act_composite_p75",
    ]
    return sum(1 for key in keys if row.get(key) is not None)


def version_tuple(value: Any) -> tuple[int, ...]:
    parts = []
    for part in str(value or "").split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def best_doc_for_year(docs: list[dict[str, Any]], target_year: int) -> dict[str, Any] | None:
    candidates = [doc for doc in docs if doc_year(doc) == target_year]
    if not candidates:
        return None

    def rank(doc: dict[str, Any]) -> tuple[int, int, int, str]:
        status_priority = {
            "extraction_pending": 0,
            "failed": 1,
            "extracted": 2,
            "not_applicable": 3,
        }.get(str(doc.get("extraction_status") or ""), 4)
        format_priority = 0 if doc.get("source_format") in REDRAIN_FORMATS else 1
        bad = 1 if doc.get("data_quality_flag") in BAD_FLAGS else 0
        discovered = str(doc.get("discovered_at") or "")
        return status_priority, format_priority, bad, discovered

    return sorted(candidates, key=rank)[0]


def needs_tier4_redrain(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    return (
        row.get("producer") == "tier4_docling"
        and version_tuple(row.get("producer_version")) < version_tuple(CURRENT_TIER4_VERSION)
    )


def target_doc_ids_for_school(
    school_id: str,
    docs: list[dict[str, Any]],
    prior: dict[str, Any] | None,
    latest: dict[str, Any] | None,
    from_year: int,
    to_year: int,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    pairable = bool(prior and latest)

    for year, row in ((from_year, prior), (to_year, latest)):
        if needs_tier4_redrain(row):
            doc_id = str(row.get("document_id") or "")
            if doc_id and doc_id not in seen:
                targets.append({
                    "document_id": doc_id,
                    "school_id": school_id,
                    "year_start": year,
                    "priority_class": "pairable_stale" if pairable else "stale_unpairable",
                    "reason": "selected_tier4_stale",
                    "source_format": row.get("source_format") or "",
                    "producer_version": row.get("producer_version") or "",
                })
                seen.add(doc_id)
            continue

        if row:
            continue

        doc = best_doc_for_year(docs, year)
        if not doc:
            continue
        if doc.get("source_format") not in REDRAIN_FORMATS:
            continue
        doc_id = str(doc.get("id") or "")
        if doc_id and doc_id not in seen:
            targets.append({
                "document_id": doc_id,
                "school_id": school_id,
                "year_start": year,
                "priority_class": "latest_gap" if year == to_year else "prior_gap",
                "reason": f"missing_browser_row_{doc.get('extraction_status') or 'unknown'}",
                "source_format": doc.get("source_format") or "",
                "producer_version": "",
            })
            seen.add(doc_id)

    return targets


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, Any], rows: list[dict[str, Any]], targets: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PRD 019 watchlist freshness audit",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Watchlist schools: {summary['watchlist_size']}",
        f"- Prior-year rows: {summary['with_prior']}",
        f"- Latest-year rows: {summary['with_latest']}",
        f"- Pairable rows: {summary['pairable']} ({summary['pairable_pct']:.1%})",
        f"- Pairable with >=3 useful launch fields in both years: {summary['pairable_useful']} ({summary['pairable_useful_pct']:.1%})",
        f"- Targeted redrain documents: {summary['target_document_count']}",
        "",
        "## Redrain Targets",
        "",
    ]
    if targets:
        lines.extend([
            "| Priority | School | Year | Reason | Format | Document ID |",
            "|---:|---|---:|---|---|---|",
        ])
        for index, target in enumerate(targets[:100], start=1):
            lines.append(
                f"| {index} | {target['school_id']} | {target['year_start']} | "
                f"{target['priority_class']} / {target['reason']} | "
                f"{target['source_format']} | `{target['document_id']}` |"
            )
    else:
        lines.append("No targetable Tier 4 documents found.")

    lines.extend([
        "",
        "## Watchlist Detail",
        "",
        "| # | School | Segment | Prior | Latest | Useful Prior | Useful Latest | Status |",
        "|---:|---|---|---|---|---:|---:|---|",
    ])
    for row in rows:
        lines.append(
            f"| {row['ordinal']} | {row['school_id']} | {row['segment']} | "
            f"{row['prior_status']} | {row['latest_status']} | "
            f"{row['prior_useful_fields']} | {row['latest_useful_fields']} | {row['status']} |"
        )
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=None)
    parser.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    parser.add_argument("--from-year", type=int, default=2024)
    parser.add_argument("--to-year", type=int, default=2025)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--redrain-limit", type=int, default=25)
    args = parser.parse_args()

    watchlist = load_watchlist(args.watchlist)
    school_ids = [school.school_id for school in watchlist]
    client = create_supabase_client(load_env(args.env))

    browser_rows = fetch_browser_rows(client, school_ids, args.from_year, args.to_year)
    documents = fetch_documents(client, school_ids)
    selected = select_browser_rows(browser_rows)
    docs_by_school: dict[str, list[dict[str, Any]]] = {}
    for doc in documents:
        docs_by_school.setdefault(str(doc["school_id"]), []).append(doc)

    detail_rows: list[dict[str, Any]] = []
    redrain_targets: list[dict[str, Any]] = []
    for school in watchlist:
        prior = selected.get((school.school_id, args.from_year))
        latest = selected.get((school.school_id, args.to_year))
        prior_useful = useful_field_count(prior)
        latest_useful = useful_field_count(latest)
        school_docs = docs_by_school.get(school.school_id, [])
        target_docs = target_doc_ids_for_school(
            school.school_id,
            school_docs,
            prior,
            latest,
            args.from_year,
            args.to_year,
        )
        redrain_targets.extend({**target, "ordinal": school.ordinal} for target in target_docs)

        if prior and latest and prior_useful >= 3 and latest_useful >= 3:
            status = "pairable_useful"
        elif prior and latest:
            status = "pairable_sparse"
        elif target_docs:
            status = "targetable_gap"
        else:
            status = "archive_gap"

        detail_rows.append({
            "ordinal": school.ordinal,
            "school_id": school.school_id,
            "segment": school.segment,
            "prior_document_id": prior.get("document_id") if prior else "",
            "latest_document_id": latest.get("document_id") if latest else "",
            "prior_status": f"{prior.get('producer')}@{prior.get('producer_version')}" if prior else "missing",
            "latest_status": f"{latest.get('producer')}@{latest.get('producer_version')}" if latest else "missing",
            "prior_useful_fields": prior_useful,
            "latest_useful_fields": latest_useful,
            "prior_doc_candidates": sum(1 for doc in school_docs if doc_year(doc) == args.from_year),
            "latest_doc_candidates": sum(1 for doc in school_docs if doc_year(doc) == args.to_year),
            "status": status,
        })

    priority_order = {
        "latest_gap": 0,
        "prior_gap": 1,
        "pairable_stale": 2,
        "stale_unpairable": 3,
    }
    redrain_targets.sort(key=lambda row: (
        priority_order.get(str(row["priority_class"]), 9),
        int(row["ordinal"]),
        0 if row["year_start"] == args.to_year else 1,
        row["reason"],
    ))
    limited_targets = redrain_targets[:args.redrain_limit]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "watchlist": str(args.watchlist),
        "from_year": args.from_year,
        "to_year": args.to_year,
        "watchlist_size": len(watchlist),
        "with_prior": sum(1 for row in detail_rows if row["prior_document_id"]),
        "with_latest": sum(1 for row in detail_rows if row["latest_document_id"]),
        "pairable": sum(1 for row in detail_rows if row["prior_document_id"] and row["latest_document_id"]),
        "pairable_useful": sum(1 for row in detail_rows if row["status"] == "pairable_useful"),
        "target_document_count": len(limited_targets),
        "all_target_document_count": len(redrain_targets),
        "target_document_ids": [row["document_id"] for row in limited_targets],
    }
    summary["pairable_pct"] = summary["pairable"] / summary["watchlist_size"] if summary["watchlist_size"] else 0
    summary["pairable_useful_pct"] = summary["pairable_useful"] / summary["watchlist_size"] if summary["watchlist_size"] else 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(detail_rows, args.out_dir / "freshness-detail.csv")
    write_csv(limited_targets, args.out_dir / "redrain-targets.csv")
    (args.out_dir / "redrain-document-ids.txt").write_text(
        ",".join(summary["target_document_ids"]) + "\n",
    )
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write_markdown(summary, detail_rows, limited_targets, args.out_dir / "freshness-audit.md")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
