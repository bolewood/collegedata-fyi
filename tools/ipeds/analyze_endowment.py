#!/usr/bin/env python3
"""Audit IPEDS Finance Part H values before an endowment backfill.

The report keeps raw federal values intact and separately computes corpus sign
counts, accounting-identity checks, and sign-normalized draw-rate summaries.
It does not infer restricted-fund borrowing or financial distress.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.ipeds.load_release import find_table_zip, read_release_manifest, read_table_zip
from tools.ipeds.metadata import sha256_file
from tools.ipeds.project import coerce_decimal, normalize_unitid

DEFAULT_FIXTURE_UNITIDS = "201195,148131,231420,203580,152080"
FIXTURE_SCHOOL_NAMES = {
    201195: "Baldwin Wallace University",
    148131: "Quincy University",
    231420: "Averett University",
    203580: "Lake Erie College",
    152080: "University of Notre Dame",
}
ENDOWMENT_COMPONENT_VARIABLES = (
    "F2H03A",
    "F2H03B",
    "F2H03C",
    "F2H03D",
)
ACCOUNTING_IDENTITY_FORMULA = (
    "(F2H02 - F2H01) = " + " + ".join(ENDOWMENT_COMPONENT_VARIABLES)
)
PART_H_VARIABLES = (
    "F2H01",
    "F2H02",
    *ENDOWMENT_COMPONENT_VARIABLES,
)
DRAW_RATE_THRESHOLDS = (Decimal("0.05"), Decimal("0.07"), Decimal("0.15"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path, help="Directory containing one F####_F2 CSV or ZIP.")
    parser.add_argument(
        "--unitids",
        default=DEFAULT_FIXTURE_UNITIDS,
        help="Comma-separated UNITIDs to include as fixture observations.",
    )
    parser.add_argument("--out", required=True, type=Path, help="JSON report destination.")
    args = parser.parse_args()

    release_manifest = read_release_manifest(args.data_dir)
    source = find_finance_source(args.data_dir, release_manifest)
    source_table = source.stem.upper()
    rows = read_table_zip(source)
    unitids = parse_unitids(args.unitids)
    report = analyze_endowment_rows(rows, source_table=source_table, fixture_unitids=unitids)
    report["source_file"] = str(source)
    report["source_sha256"] = sha256_file(source)
    report["release"] = {
        key: release_manifest.get(key)
        for key in (
            "collection_year",
            "data_year",
            "release_type",
            "release_date",
            "release_date_text",
            "metadata_url",
            "access_url",
            "source_mode",
        )
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    sign_counts = report["spending_sign_counts"]
    identity = report["accounting_identity"]
    print(
        "spending signs: "
        f"negative={sign_counts['negative']} positive={sign_counts['positive']} zero={sign_counts['zero']}"
    )
    print(
        "end-minus-beginning identity: "
        f"{identity['matching']}/{identity['eligible']}"
    )
    missing_fixtures = [
        fixture["unitid"] for fixture in report["fixtures"] if not fixture["found"]
    ]
    if missing_fixtures:
        print(
            "error: requested fixture UNITID(s) missing from Finance source: "
            + ", ".join(str(unitid) for unitid in missing_fixtures),
            file=sys.stderr,
        )
        return 2
    return 0


def find_finance_source(
    data_dir: Path,
    release_manifest: dict[str, Any] | None = None,
) -> Path:
    manifest = release_manifest or read_release_manifest(data_dir)
    if not manifest:
        raise SystemExit(
            f"release.json is required in {data_dir}; analyze the downloader's exact inventory"
        )
    inventory = {
        str(table_name).upper()
        for key in ("downloaded_tables", "access_exported_tables")
        for table_name in manifest.get(key, [])
    }
    finance_tables = sorted(
        table_name
        for table_name in inventory
        if re.fullmatch(r"F\d{4}_F2", table_name)
    )
    if not finance_tables:
        raise SystemExit(f"release.json lists no F####_F2 source in {data_dir}")
    if len(finance_tables) > 1:
        raise SystemExit(
            "Expected one Finance F2 source in release.json; found: "
            + ", ".join(finance_tables)
        )
    table_name = finance_tables[0]
    source = find_table_zip(data_dir, table_name, manifest)
    if source is None:
        raise SystemExit(
            f"release.json lists {table_name}, but its recorded artifact is missing in {data_dir}"
        )
    return source


def parse_unitids(value: str) -> list[int]:
    unitids: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            unitids.append(int(item))
        except ValueError as exc:
            raise SystemExit(f"Invalid UNITID: {item}") from exc
    return unitids


def analyze_endowment_rows(
    rows: list[dict[str, Any]],
    *,
    source_table: str,
    fixture_unitids: Iterable[int],
) -> dict[str, Any]:
    normalized_rows = [{str(key).upper(): value for key, value in row.items()} for row in rows]
    rows_by_unitid = {
        unitid: row
        for row in normalized_rows
        if (unitid := normalize_unitid(row.get("UNITID"))) is not None
    }

    spending_values = [value for row in normalized_rows if (value := decimal_value(row, "F2H03C")) is not None]
    draw_rates = [
        abs(spending) / beginning
        for row in normalized_rows
        if (beginning := decimal_value(row, "F2H01")) is not None
        and beginning > 0
        and (spending := decimal_value(row, "F2H03C")) is not None
    ]
    status_counts: dict[str, dict[str, int]] = {}
    reporting_flag_columns_present: list[str] = []
    for variable in PART_H_VARIABLES:
        flag_variable = f"X{variable}"
        if any(flag_variable in row for row in normalized_rows):
            reporting_flag_columns_present.append(flag_variable)
        counter = Counter(
            str(row.get(flag_variable)).strip()
            for row in normalized_rows
            if row.get(flag_variable) not in (None, "")
        )
        if counter:
            status_counts[variable] = dict(sorted(counter.items()))

    accounting_identity = endowment_identity_summary(normalized_rows)

    fixtures = []
    for unitid in fixture_unitids:
        row = rows_by_unitid.get(unitid)
        if row is None:
            fixtures.append({
                "unitid": unitid,
                "school_name": FIXTURE_SCHOOL_NAMES.get(unitid),
                "found": False,
            })
            continue
        beginning = decimal_value(row, "F2H01")
        spending = decimal_value(row, "F2H03C")
        values = {
            variable: decimal_to_json(decimal_value(row, variable))
            for variable in PART_H_VARIABLES
        }
        statuses = {
            variable: row.get(f"X{variable}")
            for variable in PART_H_VARIABLES
            if row.get(f"X{variable}") not in (None, "")
        }
        fixtures.append({
            "unitid": unitid,
            "school_name": FIXTURE_SCHOOL_NAMES.get(unitid),
            "found": True,
            "values": values,
            "statuses": statuses,
            "draw_rate": decimal_to_json(abs(spending) / beginning)
            if beginning is not None and beginning > 0 and spending is not None
            else None,
            "end_minus_begin_equals_components": endowment_identity_matches(row),
            "accounting_identity_residual": decimal_to_json(
                endowment_identity_residual(row)
            ),
        })

    rows_with_mapped_values = sum(
        1
        for row in normalized_rows
        if any(decimal_value(row, variable) is not None for variable in PART_H_VARIABLES)
    )
    return {
        "source_table": source_table.upper(),
        "data_year": infer_data_year(source_table),
        "methodology": {
            "draw_rate": "abs(F2H03C) / F2H01 when F2H01 > 0",
            "warning": (
                "This is an independent metric from public federal data. It does not identify "
                "restricted-endowment borrowing, donor-intent violations, or financial distress."
            ),
        },
        "row_count": len(normalized_rows),
        "part_h_value_reporters": sum(
            1
            for row in normalized_rows
            if decimal_value(row, "F2H01") is not None and decimal_value(row, "F2H02") is not None
        ),
        "rows_with_mapped_part_h_values": rows_with_mapped_values,
        "rows_without_mapped_part_h_values": len(normalized_rows) - rows_with_mapped_values,
        "blank_part_h_representation": (
            "Rows with no mapped Part H numeric values project to no Endowment facts; "
            "no synthetic not_applicable facts are created."
        ),
        "component_reporters": sum(
            1
            for row in normalized_rows
            if all(
                decimal_value(row, variable) is not None
                for variable in ENDOWMENT_COMPONENT_VARIABLES
            )
        ),
        "reporting_flag_columns_present": reporting_flag_columns_present,
        "status_counts_by_variable": status_counts,
        "spending_sign_counts": {
            "negative": sum(value < 0 for value in spending_values),
            "positive": sum(value > 0 for value in spending_values),
            "zero": sum(value == 0 for value in spending_values),
            "reported_numeric": len(spending_values),
        },
        "accounting_identity": accounting_identity,
        "draw_rate_distribution": draw_rate_distribution(draw_rates),
        "fixtures": fixtures,
    }


def decimal_value(row: dict[str, Any], variable: str) -> Decimal | None:
    return coerce_decimal(row.get(variable))


def endowment_identity_matches(row: dict[str, Any]) -> bool | None:
    residual = endowment_identity_residual(row)
    return None if residual is None else residual == 0


def endowment_identity_residual(row: dict[str, Any]) -> Decimal | None:
    beginning = decimal_value(row, "F2H01")
    ending = decimal_value(row, "F2H02")
    components = [
        decimal_value(row, variable)
        for variable in ENDOWMENT_COMPONENT_VARIABLES
    ]
    if beginning is None or ending is None or any(value is None for value in components):
        return None
    return ending - beginning - sum(components, Decimal(0))


def endowment_identity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = 0
    matching = 0
    mismatch_unitids: list[int] = []
    mismatch_samples: list[dict[str, Any]] = []
    for row in rows:
        residual = endowment_identity_residual(row)
        if residual is None:
            continue
        eligible += 1
        if residual == 0:
            matching += 1
        elif len(mismatch_samples) < 25:
            unitid = normalize_unitid(row.get("UNITID"))
            if unitid is not None:
                mismatch_unitids.append(unitid)
            mismatch_samples.append({
                "unitid": unitid,
                "residual": decimal_to_json(residual),
                "F2H01": decimal_to_json(decimal_value(row, "F2H01")),
                "F2H02": decimal_to_json(decimal_value(row, "F2H02")),
                "components": {
                    variable: decimal_to_json(decimal_value(row, variable))
                    for variable in ENDOWMENT_COMPONENT_VARIABLES
                },
            })
    return {
        "formula": ACCOUNTING_IDENTITY_FORMULA,
        "eligible": eligible,
        "matching": matching,
        "mismatching": eligible - matching,
        "mismatch_unitids_sample": mismatch_unitids,
        "mismatch_samples": mismatch_samples,
    }


def draw_rate_distribution(draw_rates: list[Decimal]) -> dict[str, Any]:
    sorted_rates = sorted(draw_rates)
    count = len(sorted_rates)
    result: dict[str, Any] = {
        "eligible": count,
        "median": decimal_to_json(quantile(sorted_rates, Decimal("0.5"))),
        "p25": decimal_to_json(quantile(sorted_rates, Decimal("0.25"))),
        "p75": decimal_to_json(quantile(sorted_rates, Decimal("0.75"))),
        "p95": decimal_to_json(quantile(sorted_rates, Decimal("0.95"))),
    }
    for threshold in DRAW_RATE_THRESHOLDS:
        label = f"above_{int(threshold * 100)}pct"
        above = sum(rate > threshold for rate in sorted_rates)
        result[label] = {
            "count": above,
            "share": decimal_to_json(Decimal(above) / Decimal(count)) if count else None,
        }
    return result


def quantile(values: list[Decimal], probability: Decimal) -> Decimal | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = probability * Decimal(len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - Decimal(lower)
    return values[lower] + (values[upper] - values[lower]) * fraction


def decimal_to_json(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(round(value, 10))


def infer_data_year(source_table: str) -> int | None:
    match = re.fullmatch(r"F\d{2}(\d{2})_F2", source_table.upper())
    return 2000 + int(match.group(1)) if match else None


if __name__ == "__main__":
    raise SystemExit(main())
