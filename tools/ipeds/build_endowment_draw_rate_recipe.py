#!/usr/bin/env python3
"""Build the checked-in dataset for /recipes/endowment-draw-rate.

The command reads only public PostgREST resources. It preserves the source
finance values in the generated artifact, derives a sign-normalized draw rate,
and excludes non-reported or accounting-identity-mismatched rows from sector
statistics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.ipeds.load_release import load_env
from tools.ipeds.reconcile_endowment_scorecard import postgrest_get_all
from tools.finder.identity_guard import validated_unique_school_claim_slug_map

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "web/src/lib/endowment-draw-rate-recipe-data.ts"
DEFAULT_MIN_YEAR = 2020
DEFAULT_MAX_YEAR = 2024
FINANCE_FIELDS = (
    "endowment_value_begin",
    "endowment_value_end",
    "endowment_new_gifts",
    "endowment_investment_return",
    "endowment_spending_distribution",
    "endowment_other_change",
)
IDENTITY_FIELDS = ("institution_name", "control", "state")
DRAW_RATE_THRESHOLDS = (Decimal("0.05"), Decimal("0.07"), Decimal("0.15"))
SOURCE_API_URL = "https://api.collegedata.fyi"


@dataclass(frozen=True)
class FactCell:
    value: Decimal | None
    quality_flag: str
    release_id: str
    release_type: str
    source_table: str
    source_variable: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-year", type=int, default=DEFAULT_MIN_YEAR)
    parser.add_argument("--max-year", type=int, default=DEFAULT_MAX_YEAR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--schools-yaml",
        type=Path,
        default=REPO_ROOT / "tools/finder/schools.yaml",
        help="Identity-guarded canonical school slugs keyed by IPEDS UNITID",
    )
    parser.add_argument(
        "--generated-at",
        default=date.today().isoformat(),
        help="ISO date recorded in the generated artifact (defaults to today)",
    )
    args = parser.parse_args()

    if args.min_year > args.max_year:
        parser.error("--min-year must be less than or equal to --max-year")
    try:
        date.fromisoformat(args.generated_at)
    except ValueError:
        parser.error("--generated-at must be an ISO date (YYYY-MM-DD)")

    load_env(REPO_ROOT / ".env")
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    api_key = (
        os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
    )
    if not supabase_url or not api_key:
        print(
            "error: SUPABASE_URL and SUPABASE_ANON_KEY (or "
            "NEXT_PUBLIC_SUPABASE_ANON_KEY) are required",
            file=sys.stderr,
        )
        return 2

    try:
        inputs = fetch_recipe_inputs(
            supabase_url,
            api_key,
            min_year=args.min_year,
            max_year=args.max_year,
        )
        artifact = build_recipe_artifact(
            finance_rows=inputs["finance_rows"],
            identity_rows=inputs["identity_rows"],
            directory_rows=inputs["directory_rows"],
            release_rows=inputs["release_rows"],
            min_year=args.min_year,
            max_year=args.max_year,
            generated_at=args.generated_at,
            canonical_school_ids=validated_unique_school_claim_slug_map(
                schools_path=args.schools_yaml
            ),
        )
    except (OSError, ValueError) as exc:
        print(f"error: recipe dataset build failed: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_typescript(artifact), encoding="utf-8")
    print(
        f"wrote {args.out} ({artifact['meta']['rowCount']} school-year rows, "
        f"dataset {artifact['meta']['datasetVersion']})"
    )
    return 0


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def fetch_recipe_inputs(
    base_url: str,
    api_key: str,
    *,
    min_year: int,
    max_year: int,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch bounded inputs in index-friendly, timeout-resistant slices."""
    finance_rows: list[dict[str, Any]] = []
    for field_key in FINANCE_FIELDS:
        finance_rows.extend(
            postgrest_get_all(
                base_url,
                api_key,
                "ipeds_facts",
                {
                    "select": (
                        "release_id,ipeds_id,data_year,field_key,value_numeric,"
                        "quality_flag,release_type,source_table,source_variable"
                    ),
                    "field_key": f"eq.{field_key}",
                    "data_year": f"gte.{min_year}",
                    "and": f"(data_year.lte.{max_year},source_table.like.F*_F2)",
                    "public_visible": "eq.true",
                    "order": "ipeds_id.asc,data_year.asc,release_id.asc",
                },
            )
        )

    identity_rows: list[dict[str, Any]] = []
    for field_key in IDENTITY_FIELDS:
        identity_rows.extend(
            postgrest_get_all(
                base_url,
                api_key,
                "ipeds_facts",
                {
                    "select": (
                        "release_id,ipeds_id,data_year,field_key,value_text,"
                        "value_label,quality_flag"
                    ),
                    "field_key": f"eq.{field_key}",
                    "data_year": f"gte.{min_year}",
                    "and": f"(data_year.lte.{max_year})",
                    "public_visible": "eq.true",
                    "order": "ipeds_id.asc,data_year.asc,release_id.asc",
                },
            )
        )

    directory_rows = postgrest_get_all(
        base_url,
        api_key,
        "institution_directory",
        {
            "select": "ipeds_id,school_id,in_scope",
            "order": "ipeds_id.asc",
        },
    )
    release_rows = postgrest_get_all(
        base_url,
        api_key,
        "ipeds_releases",
        {
            "select": (
                "id,collection_year,data_year,release_type,release_date,"
                "metadata_sha256,access_sha256,source_page_url"
            ),
            "data_year": f"gte.{min_year}",
            "and": f"(data_year.lte.{max_year})",
            "order": "data_year.asc,release_type.asc,id.asc",
        },
    )
    return {
        "finance_rows": finance_rows,
        "identity_rows": identity_rows,
        "directory_rows": directory_rows,
        "release_rows": release_rows,
    }


def index_finance_rows(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, int], dict[str, FactCell]]:
    indexed: dict[tuple[str, int], dict[str, FactCell]] = defaultdict(dict)
    for row in rows:
        ipeds_id = str(row.get("ipeds_id") or "").strip()
        year = parse_decimal(row.get("data_year"))
        field_key = str(row.get("field_key") or "")
        if not ipeds_id or year is None or year != year.to_integral_value():
            continue
        if field_key not in FINANCE_FIELDS:
            continue
        key = (ipeds_id, int(year))
        cell = FactCell(
            value=parse_decimal(row.get("value_numeric")),
            quality_flag=str(row.get("quality_flag") or ""),
            release_id=str(row.get("release_id") or ""),
            release_type=str(row.get("release_type") or ""),
            source_table=str(row.get("source_table") or ""),
            source_variable=str(row.get("source_variable") or ""),
        )
        existing = indexed[key].get(field_key)
        if existing is not None and existing != cell:
            raise ValueError(
                f"conflicting public facts for {ipeds_id} FY{int(year)} {field_key}"
            )
        indexed[key][field_key] = cell
    return dict(indexed)


def index_identity_rows(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, int], dict[str, str]]:
    indexed: dict[tuple[str, int], dict[str, str]] = defaultdict(dict)
    for row in rows:
        ipeds_id = str(row.get("ipeds_id") or "").strip()
        year = parse_decimal(row.get("data_year"))
        field_key = str(row.get("field_key") or "")
        if (
            not ipeds_id
            or year is None
            or year != year.to_integral_value()
            or field_key not in IDENTITY_FIELDS
            or str(row.get("quality_flag") or "") != "reported"
        ):
            continue
        value = str(row.get("value_text") or "").strip()
        if not value:
            value = str(row.get("value_label") or "").strip()
        if not value:
            continue
        key = (ipeds_id, int(year))
        existing = indexed[key].get(field_key)
        if existing is not None and existing != value:
            raise ValueError(
                f"conflicting public identity facts for {ipeds_id} FY{int(year)} {field_key}"
            )
        indexed[key][field_key] = value
    return dict(indexed)


def normalize_draw_rate(
    cells: Mapping[str, FactCell],
) -> tuple[Decimal | None, str | None]:
    """Return (rate, exclusion reason) for one reporter-year."""
    if any(field not in cells for field in FINANCE_FIELDS):
        return None, "incomplete_components"
    if any(cells[field].quality_flag != "reported" for field in FINANCE_FIELDS):
        return None, "non_reported_input"
    if any(cells[field].value is None for field in FINANCE_FIELDS):
        return None, "incomplete_components"

    values = {field: cells[field].value for field in FINANCE_FIELDS}
    beginning = values["endowment_value_begin"]
    ending = values["endowment_value_end"]
    spending = values["endowment_spending_distribution"]
    assert beginning is not None and ending is not None and spending is not None
    if beginning <= 0:
        return None, "nonpositive_beginning_value"

    component_total = sum(
        (
            values[field]
            for field in (
                "endowment_new_gifts",
                "endowment_investment_return",
                "endowment_spending_distribution",
                "endowment_other_change",
            )
            if values[field] is not None
        ),
        Decimal(0),
    )
    if ending - beginning != component_total:
        return None, "accounting_identity_mismatch"

    return abs(spending) / beginning, None


def quantile(values: Iterable[Decimal], fraction: Decimal) -> Decimal | None:
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * Decimal(len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - Decimal(lower)
    return ordered[lower] * (Decimal(1) - weight) + ordered[upper] * weight


def number_json(value: Decimal | None, *, places: int | None = None) -> int | float | None:
    if value is None:
        return None
    if places is not None:
        value = value.quantize(Decimal(1).scaleb(-places))
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def build_recipe_artifact(
    *,
    finance_rows: Iterable[Mapping[str, Any]],
    identity_rows: Iterable[Mapping[str, Any]],
    directory_rows: Iterable[Mapping[str, Any]],
    release_rows: Iterable[Mapping[str, Any]],
    min_year: int,
    max_year: int,
    generated_at: str,
    canonical_school_ids: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    finance = index_finance_rows(finance_rows)
    identity = index_identity_rows(identity_rows)
    canonical_school_ids = canonical_school_ids or {}
    directory = {
        str(row.get("ipeds_id") or ""): {
            "schoolId": (
                canonical_school_ids.get(str(row.get("ipeds_id") or ""))
                or str(row.get("school_id") or "")
                or None
            ),
            "inScope": row.get("in_scope") is True,
        }
        for row in directory_rows
        if str(row.get("ipeds_id") or "")
    }

    latest_names: dict[str, str] = {}
    latest_states: dict[str, str] = {}
    for (ipeds_id, year), values in sorted(identity.items(), key=lambda item: item[0][1]):
        if min_year <= year <= max_year:
            if values.get("institution_name"):
                latest_names[ipeds_id] = values["institution_name"]
            if values.get("state"):
                latest_states[ipeds_id] = values["state"]

    artifact_rows: list[dict[str, Any]] = []
    exact_rates_by_year: dict[int, list[Decimal]] = defaultdict(list)
    exclusions_by_year: dict[int, Counter[str]] = defaultdict(Counter)
    reporters_by_year: Counter[int] = Counter()
    used_release_ids: set[str] = set()
    for (ipeds_id, year), cells in sorted(finance.items()):
        if year < min_year or year > max_year:
            continue
        identity_values = identity.get((ipeds_id, year), {})
        if identity_values.get("control") != "2":
            continue
        reporters_by_year[year] += 1
        rate, exclusion_reason = normalize_draw_rate(cells)
        if rate is not None:
            exact_rates_by_year[year].append(rate)
        if exclusion_reason:
            exclusions_by_year[year][exclusion_reason] += 1

        beginning = cells.get("endowment_value_begin")
        ending = cells.get("endowment_value_end")
        spending = cells.get("endowment_spending_distribution")
        source = spending or beginning or ending or next(iter(cells.values()))
        used_release_ids.update(cell.release_id for cell in cells.values() if cell.release_id)
        directory_row = directory.get(ipeds_id, {})
        artifact_rows.append({
            "ipedsId": ipeds_id,
            "schoolId": directory_row.get("schoolId"),
            "hasCurrentSchoolPage": bool(
                directory_row.get("schoolId") and directory_row.get("inScope")
            ),
            "schoolName": (
                identity_values.get("institution_name")
                or latest_names.get(ipeds_id)
                or f"IPEDS institution {ipeds_id}"
            ),
            "state": identity_values.get("state") or latest_states.get(ipeds_id),
            "year": year,
            "beginningValue": number_json(beginning.value if beginning else None),
            "endingValue": number_json(ending.value if ending else None),
            "spendingDistribution": number_json(spending.value if spending else None),
            "drawRate": number_json(rate, places=8),
            "exclusionReason": exclusion_reason,
            "releaseType": source.release_type,
            "sourceTable": source.source_table,
            "sourceVariable": source.source_variable,
        })

    year_summaries = []
    for year in range(min_year, max_year + 1):
        rates = exact_rates_by_year[year]
        release_types = sorted({
            row["releaseType"] for row in artifact_rows if row["year"] == year
        })
        thresholds: dict[str, Any] = {}
        for threshold in DRAW_RATE_THRESHOLDS:
            count = sum(rate > threshold for rate in rates)
            label = str(int(threshold * 100))
            thresholds[f"above{label}Count"] = count
            thresholds[f"above{label}Share"] = number_json(
                Decimal(count) / Decimal(len(rates)) if rates else None,
                places=8,
            )
        year_summaries.append({
            "year": year,
            "releaseType": release_types[0] if len(release_types) == 1 else "mixed",
            "reporters": reporters_by_year[year],
            "eligible": len(rates),
            "excluded": reporters_by_year[year] - len(rates),
            "exclusions": dict(sorted(exclusions_by_year[year].items())),
            "p10": number_json(quantile(rates, Decimal("0.10")), places=8),
            "p25": number_json(quantile(rates, Decimal("0.25")), places=8),
            "median": number_json(quantile(rates, Decimal("0.50")), places=8),
            "p75": number_json(quantile(rates, Decimal("0.75")), places=8),
            "p90": number_json(quantile(rates, Decimal("0.90")), places=8),
            **thresholds,
        })
    empty_years = [
        summary["year"] for summary in year_summaries if summary["eligible"] == 0
    ]
    if empty_years:
        raise ValueError(
            "no eligible private nonprofit Part H rows for fiscal year(s): "
            + ", ".join(str(year) for year in empty_years)
        )

    source_releases = []
    for release in release_rows:
        release_id = str(release.get("id") or "")
        if release_id not in used_release_ids:
            continue
        source_releases.append({
            "id": release_id,
            "collectionYear": str(release.get("collection_year") or ""),
            "dataYear": int(release.get("data_year")),
            "releaseType": str(release.get("release_type") or ""),
            "releaseDate": release.get("release_date"),
            "metadataSha256": release.get("metadata_sha256"),
            "accessSha256": release.get("access_sha256"),
            "sourcePageUrl": release.get("source_page_url"),
        })
    source_releases.sort(key=lambda row: (row["dataYear"], row["id"]))
    found_release_ids = {row["id"] for row in source_releases}
    missing_release_ids = sorted(used_release_ids - found_release_ids)
    if missing_release_ids:
        raise ValueError(
            "public release metadata is missing for selected release ID(s): "
            + ", ".join(missing_release_ids)
        )

    school_ids = {row["ipedsId"] for row in artifact_rows}
    schools_without_page = {
        row["ipedsId"] for row in artifact_rows if not row["hasCurrentSchoolPage"]
    }
    version_payload = {
        "rows": artifact_rows,
        "yearSummaries": year_summaries,
        "sourceReleases": source_releases,
    }
    dataset_hash = hashlib.sha256(
        json.dumps(
            version_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    latest_summary = year_summaries[-1]
    meta = {
        "datasetVersion": f"ipeds-endowment-{dataset_hash}",
        "generatedAt": generated_at,
        "source": "NCES IPEDS Finance, private not-for-profit F2 reporters",
        "sourceApiUrl": SOURCE_API_URL,
        "minYear": min_year,
        "maxYear": max_year,
        "latestReleaseType": latest_summary["releaseType"],
        "rowCount": len(artifact_rows),
        "schoolCount": len(school_ids),
        "schoolsWithoutCurrentPage": len(schools_without_page),
        "formula": "abs(F2H03C) / F2H01",
        "population": (
            "Historically private not-for-profit institutions reporting IPEDS Finance F2 "
            "Part H; sector statistics require a positive beginning value and internally "
            "consistent reported components"
        ),
        "sourceReleases": source_releases,
    }
    return {"meta": meta, "yearSummaries": year_summaries, "rows": artifact_rows}


def render_typescript(artifact: Mapping[str, Any]) -> str:
    meta = json.dumps(artifact["meta"], indent=2, ensure_ascii=False)
    summaries = json.dumps(artifact["yearSummaries"], indent=2, ensure_ascii=False)
    schools_by_id: dict[str, dict[str, Any]] = {}
    for row in artifact["rows"]:
        school = schools_by_id.setdefault(row["ipedsId"], {
            "ipedsId": row["ipedsId"],
            "schoolId": row["schoolId"],
            "hasCurrentSchoolPage": row["hasCurrentSchoolPage"],
            "schoolName": row["schoolName"],
            "state": row["state"],
            "history": [],
        })
        school["schoolName"] = row["schoolName"]
        school["state"] = row["state"]
        school["history"].append([
            row["year"],
            row["beginningValue"],
            row["endingValue"],
            row["spendingDistribution"],
            row["drawRate"],
            row["exclusionReason"],
            row["releaseType"],
            row["sourceTable"],
        ])
    school_lines = [
        "  " + json.dumps(school, ensure_ascii=False, separators=(",", ":"))
        for school in sorted(
            schools_by_id.values(),
            key=lambda item: (item["schoolName"].casefold(), item["ipedsId"]),
        )
    ]
    schools = "[\n" + ",\n".join(school_lines) + "\n]"
    return f"""// Generated by tools/ipeds/build_endowment_draw_rate_recipe.py. Do not edit by hand.

export type EndowmentDrawRateYearSummary = {{
  year: number;
  releaseType: string;
  reporters: number;
  eligible: number;
  excluded: number;
  exclusions: Record<string, number>;
  p10: number | null;
  p25: number | null;
  median: number | null;
  p75: number | null;
  p90: number | null;
  above5Count: number;
  above5Share: number | null;
  above7Count: number;
  above7Share: number | null;
  above15Count: number;
  above15Share: number | null;
}};

export type EndowmentDrawRatePoint = readonly [
  year: number,
  beginningValue: number | null,
  endingValue: number | null,
  spendingDistribution: number | null,
  drawRate: number | null,
  exclusionReason: string | null,
  releaseType: string,
  sourceTable: string,
];

export type EndowmentDrawRateSchool = {{
  ipedsId: string;
  schoolId: string | null;
  hasCurrentSchoolPage: boolean;
  schoolName: string;
  state: string | null;
  history: readonly EndowmentDrawRatePoint[];
}};

export const ENDOWMENT_DRAW_RATE_META = {meta} as const;

export const ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES = {summaries} satisfies readonly EndowmentDrawRateYearSummary[];

export const ENDOWMENT_DRAW_RATE_SCHOOLS = {schools} satisfies readonly EndowmentDrawRateSchool[];
"""


if __name__ == "__main__":
    raise SystemExit(main())
