#!/usr/bin/env python3
"""Load an official NCES/IPEDS release into the PRD 021 schema.

Dry run is the default: parse metadata, read selected table CSV ZIPs, project
curated facts, and write a JSON report under scratch/ipeds/. Use --apply only
after reviewing the report and the target database.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import zipfile
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.ipeds.mappings import MVP_FACT_MAPPINGS
from tools.ipeds.metadata import DATA_GENERATOR_URL, TablesDoc, normalize_release_date_text, parse_tablesdoc, sha256_file
from tools.ipeds.project import project_rows_to_facts

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "scratch" / "ipeds"
ACCESS_PAGE_URL = "https://nces.ed.gov/ipeds/use-the-data/download-access-database"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-xlsx", required=True, type=Path, help="Official IPEDS Tablesdoc workbook.")
    parser.add_argument("--data-dir", required=True, type=Path, help="Directory containing table CSV ZIP downloads.")
    parser.add_argument("--collection-year", required=True, help="Release collection year, e.g. 2024-25.")
    parser.add_argument("--data-year", required=True, type=int, help="IPEDS data year used in table names, e.g. 2024.")
    parser.add_argument("--release-type", default="provisional", choices=["preliminary", "provisional", "final"])
    parser.add_argument("--release-date", help="Normalized official release date, YYYY-MM-DD. Month-level releases use the first day of the month.")
    parser.add_argument("--release-date-text", help='Raw official release date text, e.g. "March 2026".')
    parser.add_argument("--metadata-url", required=True)
    parser.add_argument("--access-url")
    parser.add_argument("--apply", action="store_true", help="Upsert into Supabase using service role credentials.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    tablesdoc = parse_tablesdoc(args.metadata_xlsx)
    table_names = sorted({mapping.table_name.upper() for mapping in MVP_FACT_MAPPINGS})
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    table_sources: dict[str, dict[str, Any]] = {}

    for table_name in table_names:
        source = find_table_zip(args.data_dir, table_name)
        if source is None:
            print(f"warning: missing {table_name} CSV ZIP in {args.data_dir}", file=sys.stderr)
            continue
        rows = read_table_zip(source)
        rows_by_table[table_name] = rows
        table_sources[table_name] = {
            "path": str(source),
            "row_count": len(rows),
            "sha256": sha256_file(source),
            "data_url": DATA_GENERATOR_URL.format(year=args.data_year, table_name=table_name),
        }

    facts = project_rows_to_facts(
        rows_by_table,
        MVP_FACT_MAPPINGS,
        tablesdoc.columns,
        tablesdoc.value_labels,
        release_id=None,
        collection_year=args.collection_year,
        data_year=args.data_year,
        release_type=args.release_type,
    )

    report = build_report(args, tablesdoc, rows_by_table, table_sources, facts)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.out_dir / f"ipeds-{args.collection_year}-{args.release_type}-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {report_path}")

    if args.apply:
        apply_to_supabase(args, tablesdoc, rows_by_table, table_sources, facts)
    else:
        print("dry run only; re-run with --apply to write Supabase")
    return 0


def find_table_zip(data_dir: Path, table_name: str) -> Path | None:
    candidates = [
        data_dir / f"{table_name}.zip",
        data_dir / f"{table_name}.csv",
        data_dir / f"{table_name.lower()}.zip",
        data_dir / f"{table_name.lower()}.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(data_dir.glob(f"{table_name}*")) + sorted(data_dir.glob(f"{table_name.lower()}*"))
    return matches[0] if matches else None


def read_table_zip(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return [{k.upper(): v for k, v in row.items()} for row in csv.DictReader(f)]
    with zipfile.ZipFile(path) as zf:
        csv_name = next((name for name in zf.namelist() if name.lower().endswith(".csv")), None)
        if csv_name is None:
            raise ValueError(f"{path} does not contain a CSV file")
        with zf.open(csv_name) as raw:
            text = (line.decode("utf-8-sig") for line in raw)
            return [{k.upper(): v for k, v in row.items()} for row in csv.DictReader(text)]


def build_report(
    args: argparse.Namespace,
    tablesdoc: TablesDoc,
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_sources: dict[str, dict[str, Any]],
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    facts_by_group: dict[str, int] = {}
    quality_counts: dict[str, int] = {}
    for fact in facts:
        facts_by_group[fact["display_group"]] = facts_by_group.get(fact["display_group"], 0) + 1
        quality_counts[fact["quality_flag"]] = quality_counts.get(fact["quality_flag"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collection_year": args.collection_year,
        "data_year": args.data_year,
        "release_type": args.release_type,
        **release_date_report(args),
        "metadata_xlsx": str(args.metadata_xlsx),
        "metadata_sha256": sha256_file(args.metadata_xlsx),
        "source_tables_requested": sorted({mapping.table_name.upper() for mapping in MVP_FACT_MAPPINGS}),
        "source_tables_loaded": table_sources,
        "metadata_counts": {
            "tables": len(tablesdoc.tables),
            "columns": len(tablesdoc.columns),
            "value_labels": len(tablesdoc.value_labels),
        },
        "raw_row_counts": {table: len(rows) for table, rows in sorted(rows_by_table.items())},
        "fact_count": len(facts),
        "facts_by_group": facts_by_group,
        "quality_counts": quality_counts,
        "sample_facts": facts[:20],
    }


def apply_to_supabase(
    args: argparse.Namespace,
    tablesdoc: TablesDoc,
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_sources: dict[str, dict[str, Any]],
    facts: list[dict[str, Any]],
) -> None:
    load_env(REPO_ROOT / ".env")
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit("supabase package is required for --apply") from exc

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for --apply")

    client = create_client(supabase_url, service_key)
    release_date, release_date_precision = release_date_metadata(args)
    release_notes = {
        "loader": "tools/ipeds/load_release.py",
        "mapping_count": len(MVP_FACT_MAPPINGS),
    }
    if args.release_date_text:
        release_notes["release_date_text"] = args.release_date_text
    if release_date_precision:
        release_notes["release_date_precision"] = release_date_precision
    if release_date:
        release_notes["release_probe_due_on"] = add_months(release_date, 10)

    release_payload = {
        "collection_year": args.collection_year,
        "data_year": args.data_year,
        "release_type": args.release_type,
        "source_page_url": ACCESS_PAGE_URL,
        "metadata_url": args.metadata_url,
        "metadata_sha256": sha256_file(args.metadata_xlsx),
        "access_url": args.access_url,
        "notes": release_notes,
    }
    if release_date:
        release_payload["release_date"] = release_date
    release_result = client.table("ipeds_releases").upsert(
        release_payload,
        on_conflict="collection_year,release_type,metadata_sha256",
    ).execute()
    release_id = release_result.data[0]["id"]

    table_payloads = []
    for table in tablesdoc.tables:
        source = table_sources.get(table.table_name.upper(), {})
        table_payloads.append({
            "release_id": release_id,
            "table_name": table.table_name.upper(),
            "survey_component": table.survey_component,
            "year_coverage": table.year_coverage,
            "table_number": table.table_number,
            "table_title": table.table_title,
            "description": table.description,
            "table_release": table.table_release,
            "table_release_date": table.table_release_date,
            "data_url": source.get("data_url"),
            "row_count": source.get("row_count"),
            "source_sha256": source.get("sha256"),
            "loaded_at": datetime.now(timezone.utc).isoformat() if source else None,
        })
    batch_upsert(client, "ipeds_tables", table_payloads, "release_id,table_name")

    batch_upsert(client, "ipeds_columns", [
        {"release_id": release_id, **{**asdict(column), "table_name": column.table_name.upper(), "var_name": column.var_name.upper()}}
        for column in tablesdoc.columns
    ], "release_id,table_name,var_name")
    batch_upsert(client, "ipeds_value_labels", [
        {"release_id": release_id, **{**asdict(label), "table_name": label.table_name.upper(), "var_name": label.var_name.upper()}}
        for label in tablesdoc.value_labels
    ], "release_id,table_name,var_name,code_value")

    raw_payloads = []
    for table_name, rows in rows_by_table.items():
        for row in rows:
            unitid = row.get("UNITID")
            if unitid in (None, ""):
                continue
            raw_payloads.append({
                "release_id": release_id,
                "table_name": table_name,
                "unitid": int(float(unitid)),
                "row_data": row,
            })
    batch_upsert(client, "ipeds_raw_rows", raw_payloads, "release_id,table_name,unitid")

    fact_payloads = []
    for fact in facts:
        payload = dict(fact)
        payload["release_id"] = release_id
        fact_payloads.append(payload)
    batch_upsert(client, "ipeds_facts", fact_payloads, "release_id,unitid,field_key,source_table,source_variable")
    try:
        refreshed = client.rpc("refresh_ipeds_browser_source_modes").execute()
        print(f"refreshed browser source modes: {refreshed.data}")
    except Exception as exc:  # pragma: no cover - defensive around optional post-load helper.
        print(f"warning: could not refresh browser source modes: {exc}", file=sys.stderr)
    print(f"applied release {release_id}: {len(raw_payloads)} raw rows, {len(fact_payloads)} facts")


def batch_upsert(client: Any, table: str, rows: list[dict[str, Any]], on_conflict: str, size: int = 500) -> None:
    deduped = dedupe_rows(rows, on_conflict)
    for start in range(0, len(deduped), size):
        client.table(table).upsert(deduped[start : start + size], on_conflict=on_conflict).execute()


def dedupe_rows(rows: list[dict[str, Any]], on_conflict: str) -> list[dict[str, Any]]:
    keys = [key.strip() for key in on_conflict.split(",")]
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        seen[tuple(row.get(key) for key in keys)] = row
    return list(seen.values())


def release_date_metadata(args: argparse.Namespace) -> tuple[str | None, str | None]:
    if args.release_date:
        date.fromisoformat(args.release_date)
        precision = "month" if args.release_date.endswith("-01") and args.release_date_text else "day"
        return args.release_date, precision
    return normalize_release_date_text(args.release_date_text)


def release_date_report(args: argparse.Namespace) -> dict[str, str | None]:
    release_date, precision = release_date_metadata(args)
    return {
        "release_date": release_date,
        "release_date_text": args.release_date_text,
        "release_date_precision": precision,
        "release_probe_due_on": add_months(release_date, 10) if release_date else None,
    }


def add_months(value: str, months: int) -> str:
    parsed = date.fromisoformat(value)
    month_index = parsed.month - 1 + months
    year = parsed.year + month_index // 12
    month = month_index % 12 + 1
    day = min(parsed.day, days_in_month(year, month))
    return f"{year:04d}-{month:02d}-{day:02d}"


def days_in_month(year: int, month: int) -> int:
    if month == 2:
        if year % 400 == 0 or (year % 4 == 0 and year % 100 != 0):
            return 29
        return 28
    if month in {4, 6, 9, 11}:
        return 30
    return 31


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    raise SystemExit(main())
