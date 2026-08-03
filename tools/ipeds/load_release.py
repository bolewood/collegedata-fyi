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

from tools.ipeds.mappings import fact_mappings_for_data_year, resolve_fact_mappings_for_columns
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
    parser.add_argument("--display-groups", nargs="*", help="Optional display groups to project/apply, e.g. Costs.")
    parser.add_argument("--apply", action="store_true", help="Upsert into Supabase using service role credentials.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    release_manifest = read_release_manifest(args.data_dir)
    if not release_manifest:
        raise ValueError(
            f"release.json is required in {args.data_dir}; derive loader provenance "
            "from download_release.py rather than assumptions"
        )
    validate_release_manifest(args, release_manifest)
    if not args.access_url and release_manifest.get("access_url"):
        args.access_url = str(release_manifest["access_url"])

    tablesdoc = parse_tablesdoc(args.metadata_xlsx)
    fact_mappings = resolve_fact_mappings_for_columns(fact_mappings_for_data_year(args.data_year), tablesdoc.columns)
    if args.display_groups:
        display_groups = {group.lower() for group in args.display_groups}
        fact_mappings = tuple(mapping for mapping in fact_mappings if mapping.display_group.lower() in display_groups)
    table_names = sorted({mapping.table_name.upper() for mapping in fact_mappings})
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    table_sources: dict[str, dict[str, Any]] = {}
    for table_name in table_names:
        source = find_table_zip(args.data_dir, table_name, release_manifest)
        if source is None:
            print(f"warning: missing {table_name} CSV ZIP in {args.data_dir}", file=sys.stderr)
            continue
        rows = read_table_zip(source)
        rows_by_table[table_name] = rows
        table_sources[table_name] = {
            "path": str(source),
            "row_count": len(rows),
            "sha256": sha256_file(source),
            "data_url": data_url_for_table(
                table_name,
                data_year=args.data_year,
                access_url=args.access_url,
                release_manifest=release_manifest,
            ),
        }

    facts = project_rows_to_facts(
        rows_by_table,
        fact_mappings,
        tablesdoc.columns,
        tablesdoc.value_labels,
        release_id=None,
        collection_year=args.collection_year,
        data_year=args.data_year,
        release_type=args.release_type,
    )

    report = build_report(args, tablesdoc, rows_by_table, table_sources, facts, fact_mappings)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.out_dir / f"ipeds-{args.collection_year}-{args.release_type}-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {report_path}")

    gate_error = projection_gate_error(args, report)
    if gate_error:
        print(f"error: {gate_error}", file=sys.stderr)
        return 2

    if args.apply:
        apply_to_supabase(
            args,
            tablesdoc,
            rows_by_table,
            table_sources,
            facts,
            fact_mappings,
        )
    else:
        print("dry run only; re-run with --apply to write Supabase")
    return 0


def find_table_zip(
    data_dir: Path,
    table_name: str,
    release_manifest: dict[str, Any] | None = None,
) -> Path | None:
    inventory = release_manifest or {}
    has_inventory = (
        "downloaded_tables" in inventory or "access_exported_tables" in inventory
    )
    if has_inventory:
        downloaded_tables = {
            str(value).upper() for value in inventory.get("downloaded_tables", [])
        }
        access_tables = {
            str(value).upper()
            for value in inventory.get("access_exported_tables", [])
        }
        upper_table_name = table_name.upper()
        if upper_table_name in access_tables:
            path = data_dir / f"{upper_table_name}.csv"
            return path if path.exists() else None
        if upper_table_name in downloaded_tables:
            path = data_dir / f"{upper_table_name}.zip"
            return path if path.exists() else None
        return None

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


def read_release_manifest(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "release.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Could not read release manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Release manifest {path} must contain a JSON object")
    return value


def validate_release_manifest(
    args: argparse.Namespace,
    release_manifest: dict[str, Any],
) -> None:
    """Refuse to label downloaded data with provenance that contradicts its manifest."""
    if not release_manifest:
        return

    comparisons = {
        "collection_year": args.collection_year,
        "data_year": args.data_year,
        "release_type": args.release_type,
        "metadata_url": args.metadata_url,
    }
    for key, actual in comparisons.items():
        expected = release_manifest.get(key)
        if expected is not None and actual != expected:
            raise ValueError(
                f"Loader {key}={actual!r} does not match release.json {key}={expected!r}"
            )

    manifest_date_text = release_manifest.get("release_date_text")
    if manifest_date_text and args.release_date_text != manifest_date_text:
        raise ValueError(
            "Loader --release-date-text must be re-passed from release.json on every run "
            f"(expected {manifest_date_text!r}, got {args.release_date_text!r})"
        )

    manifest_release_date = release_manifest.get("release_date")
    if manifest_release_date:
        effective_release_date = args.release_date or normalize_release_date_text(
            args.release_date_text
        )[0]
        if effective_release_date != manifest_release_date:
            raise ValueError(
                "Loader release date does not match release.json "
                f"(expected {manifest_release_date!r}, got {effective_release_date!r})"
            )

    manifest_access_url = release_manifest.get("access_url")
    if args.access_url and manifest_access_url and args.access_url != manifest_access_url:
        raise ValueError(
            "Loader --access-url does not match the release.json Access source URL"
        )


def data_url_for_table(
    table_name: str,
    *,
    data_year: int,
    access_url: str | None,
    release_manifest: dict[str, Any],
) -> str:
    access_tables = {
        str(value).upper()
        for value in release_manifest.get("access_exported_tables", [])
    }
    if table_name.upper() in access_tables:
        manifest_access_url = release_manifest.get("access_url")
        resolved_access_url = access_url or (
            str(manifest_access_url) if manifest_access_url else None
        )
        if not resolved_access_url:
            raise ValueError(
                f"{table_name} was exported from Access but no Access source URL is available"
            )
        return resolved_access_url
    return DATA_GENERATOR_URL.format(year=data_year, table_name=table_name)


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
    fact_mappings: tuple[Any, ...],
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
        "source_tables_requested": sorted({mapping.table_name.upper() for mapping in fact_mappings}),
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


def projection_gate_error(
    args: argparse.Namespace,
    report: dict[str, Any],
) -> str | None:
    requested_groups = {group.lower() for group in (args.display_groups or [])}
    if "endowment" not in requested_groups:
        return None
    endowment_facts = report.get("facts_by_group", {}).get("Endowment", 0)
    if endowment_facts <= 0:
        return (
            "--display-groups Endowment projected zero facts; this is a failed "
            "endowment run, not a successful no-op"
        )
    return None


def apply_to_supabase(
    args: argparse.Namespace,
    tablesdoc: TablesDoc,
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_sources: dict[str, dict[str, Any]],
    facts: list[dict[str, Any]],
    fact_mappings: tuple[Any, ...],
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
    metadata_sha256 = sha256_file(args.metadata_xlsx)
    existing_release_result = (
        client.table("ipeds_releases")
        .select("id,notes,release_date")
        .eq("collection_year", args.collection_year)
        .eq("release_type", args.release_type)
        .eq("metadata_sha256", metadata_sha256)
        .limit(1)
        .execute()
    )
    existing_release = existing_release_result.data[0] if existing_release_result.data else {}
    existing_notes = existing_release.get("notes") if isinstance(existing_release, dict) else None
    release_notes = build_release_notes(
        args,
        existing_notes if isinstance(existing_notes, dict) else None,
        release_date=release_date,
        release_date_precision=release_date_precision,
    )
    validate_release_priority(
        client,
        data_year=args.data_year,
        release_type=args.release_type,
        release_date=release_date,
        existing_release_id=(
            str(existing_release["id"]) if existing_release.get("id") else None
        ),
        existing_release_date=(
            str(existing_release["release_date"])
            if existing_release.get("release_date")
            else None
        ),
    )

    release_payload = {
        "collection_year": args.collection_year,
        "data_year": args.data_year,
        "release_type": args.release_type,
        "source_page_url": ACCESS_PAGE_URL,
        "metadata_url": args.metadata_url,
        "metadata_sha256": metadata_sha256,
        "notes": release_notes,
    }
    if args.access_url:
        release_payload["access_url"] = args.access_url
    if release_date:
        release_payload["release_date"] = release_date
    release_result = client.table("ipeds_releases").upsert(
        release_payload,
        on_conflict="collection_year,release_type,metadata_sha256",
    ).execute()
    release_id = release_result.data[0]["id"]

    loaded_table_names = set(table_sources)
    table_payloads = build_loaded_table_payloads(
        tablesdoc,
        table_sources,
        release_id=release_id,
        loaded_at=datetime.now(timezone.utc).isoformat(),
    )
    batch_upsert(client, "ipeds_tables", table_payloads, "release_id,table_name")

    batch_upsert(client, "ipeds_columns", [
        {"release_id": release_id, **{**asdict(column), "table_name": column.table_name.upper(), "var_name": column.var_name.upper()}}
        for column in tablesdoc.columns
        if column.table_name.upper() in loaded_table_names
    ], "release_id,table_name,var_name")
    batch_upsert(client, "ipeds_value_labels", [
        {"release_id": release_id, **{**asdict(label), "table_name": label.table_name.upper(), "var_name": label.var_name.upper()}}
        for label in tablesdoc.value_labels
        if label.table_name.upper() in loaded_table_names
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
    loaded_fact_mappings = tuple(
        mapping
        for mapping in fact_mappings
        if mapping.table_name.upper() in loaded_table_names
    )
    prune_release_scope(
        client,
        release_id=release_id,
        rows_by_table=rows_by_table,
        facts=facts,
        fact_mappings=loaded_fact_mappings,
        selected_display_groups=(
            {mapping.display_group for mapping in fact_mappings}
            if args.display_groups
            else None
        ),
    )
    supersede_lower_priority_facts(
        client,
        release_id=release_id,
        data_year=args.data_year,
        release_type=args.release_type,
        field_keys={mapping.field_key for mapping in loaded_fact_mappings},
    )
    refresh_post_load_serving_views(client)
    print(f"applied release {release_id}: {len(raw_payloads)} raw rows, {len(fact_payloads)} facts")


def build_release_notes(
    args: argparse.Namespace,
    existing_notes: dict[str, Any] | None,
    *,
    release_date: str | None,
    release_date_precision: str | None,
) -> dict[str, Any]:
    """Merge loader notes so targeted reruns do not erase release provenance."""
    notes = dict(existing_notes or {})
    notes.update({
        "loader": "tools/ipeds/load_release.py",
        "mapping_count": len(fact_mappings_for_data_year(args.data_year)),
    })
    if args.display_groups:
        notes["last_display_groups"] = sorted(set(args.display_groups))
    if args.release_date_text:
        notes["release_date_text"] = args.release_date_text
    if release_date_precision:
        notes["release_date_precision"] = release_date_precision
    if release_date:
        notes["release_probe_due_on"] = add_months(release_date, 10)
    return notes


def build_loaded_table_payloads(
    tablesdoc: TablesDoc,
    table_sources: dict[str, dict[str, Any]],
    *,
    release_id: str,
    loaded_at: str,
) -> list[dict[str, Any]]:
    """Build provenance rows only for tables loaded in the current run."""
    metadata_by_name = {table.table_name.upper(): table for table in tablesdoc.tables}
    missing_metadata = sorted(set(table_sources) - set(metadata_by_name))
    if missing_metadata:
        raise ValueError(
            "Loaded table(s) are absent from Tablesdoc metadata: " + ", ".join(missing_metadata)
        )

    payloads: list[dict[str, Any]] = []
    for table_name, source in sorted(table_sources.items()):
        table = metadata_by_name[table_name]
        payloads.append({
            "release_id": release_id,
            "table_name": table_name,
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
            "loaded_at": loaded_at,
        })
    return payloads


def refresh_post_load_serving_views(client: Any) -> None:
    refreshed = client.rpc("refresh_ipeds_current_facts_cache").execute()
    print(f"refreshed current IPEDS facts cache: {refreshed.data}")
    try:
        browser_modes = client.rpc("refresh_ipeds_browser_source_modes").execute()
        print(f"refreshed browser source modes: {browser_modes.data}")
    except Exception as exc:  # pragma: no cover - optional browser metadata helper.
        print(f"warning: could not refresh browser source modes: {exc}", file=sys.stderr)


def prune_release_scope(
    client: Any,
    *,
    release_id: str,
    rows_by_table: dict[str, list[dict[str, Any]]],
    facts: list[dict[str, Any]],
    fact_mappings: tuple[Any, ...],
    selected_display_groups: set[str] | None,
) -> None:
    """Prune stale rows after replacement data is durable, at selected scope."""
    for table_name, rows in rows_by_table.items():
        expected_unitids = {
            int(float(row["UNITID"]))
            for row in rows
            if row.get("UNITID") not in (None, "")
        }
        existing_unitids = select_unitids(
            client,
            "ipeds_raw_rows",
            release_id=release_id,
            table_name=table_name,
        )
        stale_unitids = sorted(
            unitid for unitid in existing_unitids if unitid not in expected_unitids
        )
        delete_unitids(
            client,
            "ipeds_raw_rows",
            stale_unitids,
            release_id=release_id,
            table_name=table_name,
        )

    expected_facts: set[tuple[int, str, str, str]] = set()
    for fact in facts:
        expected_facts.add((
            int(fact["unitid"]),
            str(fact["field_key"]),
            str(fact["source_table"]).upper(),
            str(fact["source_variable"]).upper(),
        ))
    existing_facts = select_fact_inventory(
        client,
        release_id=release_id,
        table_names={mapping.table_name.upper() for mapping in fact_mappings},
        display_groups=selected_display_groups,
    )
    stale_by_mapping: dict[tuple[str, str, str], list[int]] = {}
    for existing in existing_facts:
        if existing in expected_facts:
            continue
        unitid, field_key, source_table, source_variable = existing
        stale_by_mapping.setdefault(
            (field_key, source_table, source_variable), []
        ).append(unitid)
    for key, stale_unitids in sorted(stale_by_mapping.items()):
        delete_unitids(
            client,
            "ipeds_facts",
            sorted(set(stale_unitids)),
            release_id=release_id,
            field_key=key[0],
            source_table=key[1],
            source_variable=key[2],
        )


def delete_unitids(
    client: Any,
    table: str,
    unitids: list[int],
    **filters: Any,
) -> None:
    for start in range(0, len(unitids), 500):
        query = client.table(table).delete()
        for column, value in filters.items():
            query = query.eq(column, value)
        query.in_("unitid", unitids[start : start + 500]).execute()


def select_unitids(client: Any, table: str, **filters: Any) -> set[int]:
    unitids: set[int] = set()
    start = 0
    page_size = 1000
    while True:
        query = client.table(table).select("unitid")
        for column, value in filters.items():
            query = query.eq(column, value)
        page = (
            query.order("unitid", desc=False)
            .range(start, start + page_size - 1)
            .execute()
        ).data or []
        unitids.update(
            int(row["unitid"])
            for row in page
            if row.get("unitid") is not None
        )
        if len(page) < page_size:
            return unitids
        start += page_size


def select_fact_inventory(
    client: Any,
    *,
    release_id: str,
    table_names: set[str],
    display_groups: set[str] | None,
) -> set[tuple[int, str, str, str]]:
    inventory: set[tuple[int, str, str, str]] = set()
    if display_groups == set():
        return inventory
    page_size = 1000
    for table_name in sorted(table_names):
        start = 0
        while True:
            query = (
                client.table("ipeds_facts")
                .select("unitid,field_key,source_table,source_variable")
                .eq("release_id", release_id)
                .eq("source_table", table_name)
            )
            if display_groups is not None:
                query = query.in_("display_group", sorted(display_groups))
            page = (
                query.order("unitid", desc=False)
                .order("field_key", desc=False)
                .order("source_variable", desc=False)
                .range(start, start + page_size - 1)
                .execute()
            ).data or []
            inventory.update(
                (
                    int(row["unitid"]),
                    str(row["field_key"]),
                    str(row["source_table"]).upper(),
                    str(row["source_variable"]).upper(),
                )
                for row in page
                if row.get("unitid") is not None
            )
            if len(page) < page_size:
                break
            start += page_size
    return inventory


def validate_release_priority(
    client: Any,
    *,
    data_year: int,
    release_type: str,
    release_date: str | None,
    existing_release_id: str | None,
    existing_release_date: str | None,
) -> None:
    """Reject downgrades and ambiguous same-priority revisions before writes."""
    priority = {"preliminary": 1, "provisional": 2, "final": 3}
    current_priority = priority[release_type]
    if existing_release_date and (
        release_date is None or release_date < existing_release_date
    ):
        raise ValueError(
            f"Cannot roll back the existing {release_type} release for {data_year} "
            f"from {existing_release_date} to {release_date}"
        )
    releases = (
        client.table("ipeds_releases")
        .select("id,release_type,release_date")
        .eq("data_year", data_year)
        .execute()
    ).data or []
    higher = [
        row
        for row in releases
        if priority.get(str(row.get("release_type")), 0) > current_priority
    ]
    if higher:
        release_labels = ", ".join(
            sorted({str(row.get("release_type")) for row in higher})
        )
        raise ValueError(
            f"Cannot apply {release_type} data for {data_year} after a higher-priority "
            f"release is loaded: {release_labels}"
        )

    equal_peers = [
        row
        for row in releases
        if str(row.get("id")) != existing_release_id
        and priority.get(str(row.get("release_type")), 0) == current_priority
    ]
    if not equal_peers:
        return
    peer_dates = [
        str(row["release_date"])
        for row in equal_peers
        if row.get("release_date")
    ]
    if (
        release_date is None
        or len(peer_dates) != len(equal_peers)
        or any(release_date <= peer_date for peer_date in peer_dates)
    ):
        raise ValueError(
            f"Cannot determine that this {release_type} release for {data_year} is newer "
            "than the already-loaded same-priority revision"
        )


def supersede_lower_priority_facts(
    client: Any,
    *,
    release_id: str,
    data_year: int,
    release_type: str,
    field_keys: set[str],
) -> None:
    """Hide superseded same-year facts so final blank values cannot fall back."""
    priority = {"preliminary": 1, "provisional": 2, "final": 3}
    current_priority = priority[release_type]
    releases = (
        client.table("ipeds_releases")
        .select("id,release_type")
        .eq("data_year", data_year)
        .execute()
    ).data or []
    superseded_ids = sorted(
        str(row["id"])
        for row in releases
        if row.get("id") != release_id
        and priority.get(str(row.get("release_type")), 0) <= current_priority
        and row.get("id")
    )
    if not superseded_ids or not field_keys:
        return
    (
        client.table("ipeds_facts")
        .update({"public_visible": False})
        .in_("release_id", superseded_ids)
        .in_("field_key", sorted(field_keys))
        .execute()
    )


def batch_upsert(client: Any, table: str, rows: list[dict[str, Any]], on_conflict: str, size: int = 500) -> None:
    deduped = dedupe_rows(rows, on_conflict)
    for start in range(0, len(deduped), size):
        upsert_chunk(client, table, deduped[start : start + size], on_conflict)


def upsert_chunk(client: Any, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    try:
        client.table(table).upsert(rows, on_conflict=on_conflict).execute()
    except Exception as exc:
        if len(rows) > 1 and is_statement_timeout(exc):
            midpoint = len(rows) // 2
            upsert_chunk(client, table, rows[:midpoint], on_conflict)
            upsert_chunk(client, table, rows[midpoint:], on_conflict)
            return
        raise


def is_statement_timeout(exc: Exception) -> bool:
    return "57014" in str(exc) or "statement timeout" in str(exc).lower()


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
