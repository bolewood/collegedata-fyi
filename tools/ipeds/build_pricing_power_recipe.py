#!/usr/bin/env python3
"""Build the checked-in dataset for /recipes/acceptance-vs-yield (College Pricing Power).

Panel A plots IPEDS ADM2024 raw applicant/admitted/enrolled counts from
school_facts_unified. Rates are computed with Decimal from those counts — never
from the integer-rounded DRVADM admit_rate_total / yield_rate_total fields.

Panel B joins Panel A yield to College Scorecard debt, earnings, net price, and
instructional spend. CDS 2024-25 C1 rates are tooltip-only cross-checks.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.finder.identity_guard import validated_unique_school_claim_slug_map
from tools.ipeds.load_release import load_env
from tools.ipeds.reconcile_endowment_scorecard import postgrest_get_all

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "web/src/lib/pricing-power-recipe-data.ts"
SOURCE_API_URL = "https://api.collegedata.fyi"
IPEDS_CYCLE = "fall 2024 (ADM2024)"
ADM_SOURCE_TABLE = "ADM2024"
CDS_YEAR = "2024-25"
ADM_COUNT_FIELDS = ("applicants_total", "admissions_total", "enrolled_total")
ROUNDED_RATE_FIELDS = frozenset({"admit_rate_total", "yield_rate_total"})
SCORECARD_FIELDS = (
    "earnings_10yr_median",
    "median_debt_monthly_payment",
    "median_debt_completers",
    "avg_net_price",
    "instructional_expenditure_fte",
)
SYRACUSE_SCHOOL_ID = "syracuse-university"
SYRACUSE_IPEDS_ID = "196413"
RATE_PLACES = Decimal("0.0001")
MONEY_PLACES = Decimal("1")
CENTS_PLACES = Decimal("0.01")
PANEL_A_MIN = 1700
PANEL_A_MAX = 2000
PANEL_B_MIN = 1500
PANEL_B_MAX = 1750
SYRACUSE_BURDEN_MIN = Decimal("0.041")
SYRACUSE_BURDEN_MAX = Decimal("0.043")
MIN_DISTINCT_YIELDS = 100
# Figure 2's y-axis tops out at 16% and clamps silently; must match
# YieldDebtBurdenChart.tsx (BURDEN_MAX) so a regen that produces a higher
# burden fails here instead of misplotting the school at the axis edge.
BURDEN_AXIS_MAX = Decimal("0.16")
# Worked-example anchors the page requires at module scope (requirePanelB in
# recipes/acceptance-vs-yield/page.tsx). Missing anchors should fail the
# builder run, not the later next build.
REQUIRED_PANEL_B_ANCHORS = (
    SYRACUSE_SCHOOL_ID,
    "fordham-university",
    "american-university",
    "southern-methodist-university",
)
PANEL_A_QUADRANTS = (
    "lowerAcceptanceHigherYield",
    "higherAcceptanceHigherYield",
    "lowerAcceptanceLowerYield",
    "higherAcceptanceLowerYield",
)
PANEL_B_QUADRANTS = (
    "higherYieldHigherBurden",
    "lowerYieldHigherBurden",
    "higherYieldLowerBurden",
    "lowerYieldLowerBurden",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
    try:
        date.fromisoformat(args.generated_at)
    except ValueError:
        parser.error("--generated-at must be an ISO date (YYYY-MM-DD)")

    load_builder_env()
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    api_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
    )
    if not supabase_url or not api_key:
        print(
            "error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or "
            "SUPABASE_ANON_KEY) are required",
            file=sys.stderr,
        )
        return 2

    try:
        inputs = fetch_recipe_inputs(supabase_url, api_key)
        artifact = build_recipe_artifact(
            fact_rows=inputs["fact_rows"],
            current_fact_rows=inputs["current_fact_rows"],
            directory_rows=inputs["directory_rows"],
            scorecard_rows=inputs["scorecard_rows"],
            browser_rows=inputs["browser_rows"],
            generated_at=args.generated_at,
            canonical_school_ids=validated_unique_school_claim_slug_map(
                schools_path=args.schools_yaml
            ),
            validate=True,
        )
    except (OSError, ValueError) as exc:
        print(f"error: pricing-power build failed: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_typescript(artifact), encoding="utf-8")
    meta = artifact["meta"]
    print(
        f"wrote {args.out} (panel A {meta['panelACount']}, "
        f"panel B {meta['panelBCount']}, "
        f"median yield {meta['medianYield'] * 100:.2f}%, "
        f"median burden {meta['medianBurden'] * 100:.2f}%)"
    )
    print(
        "join misses: directory "
        f"{meta['joinMisses']['directory']}, scorecard "
        f"{meta['joinMisses']['scorecard']}"
    )
    print(f"exclusions: {meta['exclusions']}")
    return 0


def load_builder_env() -> None:
    for path in (REPO_ROOT / ".env", REPO_ROOT.parent / ".env"):
        load_env(path)


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return None
    return parsed if parsed.is_finite() else None


def parse_count(value: Any) -> Decimal | None:
    parsed = parse_decimal(value)
    if parsed is None or parsed != parsed.to_integral_value():
        return None
    return parsed


def round_rate(value: Decimal, places: Decimal = RATE_PLACES) -> Decimal:
    return value.quantize(places)


def rate_json(value: Decimal) -> float:
    return float(format(round_rate(value), "f"))


def money_json(value: Decimal) -> int:
    return int(value.quantize(MONEY_PLACES))


def cents_json(value: Decimal) -> float:
    return float(format(value.quantize(CENTS_PLACES), "f"))


def acceptance_rate(admitted: Decimal, applied: Decimal) -> Decimal:
    if applied <= 0:
        raise ValueError("acceptance rate requires a positive applicant count")
    return admitted / applied


def yield_rate(enrolled: Decimal, admitted: Decimal) -> Decimal:
    if admitted <= 0:
        raise ValueError("yield rate requires a positive admitted count")
    return enrolled / admitted


def debt_burden(monthly_payment: Decimal, earnings: Decimal) -> Decimal:
    if monthly_payment <= 0 or earnings <= 0:
        raise ValueError("burden requires positive monthly payment and earnings")
    return (monthly_payment * Decimal(12)) / earnings


def instruction_net_price_ratio(instruction: Decimal, net_price: Decimal) -> Decimal:
    if instruction <= 0 or net_price <= 0:
        raise ValueError("instruction/net-price ratio requires positive inputs")
    return instruction / net_price


def panel_a_quadrant(
    acceptance: Decimal,
    yield_value: Decimal,
    median_acceptance: Decimal,
    median_yield: Decimal,
) -> str:
    lower_acceptance = acceptance < median_acceptance
    higher_yield = yield_value >= median_yield
    if lower_acceptance and higher_yield:
        return "lowerAcceptanceHigherYield"
    if not lower_acceptance and higher_yield:
        return "higherAcceptanceHigherYield"
    if lower_acceptance and not higher_yield:
        return "lowerAcceptanceLowerYield"
    return "higherAcceptanceLowerYield"


def panel_b_quadrant(
    yield_value: Decimal,
    burden: Decimal,
    median_yield: Decimal,
    median_burden: Decimal,
) -> str:
    higher_yield = yield_value >= median_yield
    higher_burden = burden >= median_burden
    if higher_yield and higher_burden:
        return "higherYieldHigherBurden"
    if not higher_yield and higher_burden:
        return "lowerYieldHigherBurden"
    if higher_yield and not higher_burden:
        return "higherYieldLowerBurden"
    return "lowerYieldLowerBurden"


def fetch_recipe_inputs(base_url: str, api_key: str) -> dict[str, list[dict[str, Any]]]:
    """Fetch ADM2024 counts, directory, Scorecard, and CDS C1 cross-checks."""
    fact_select = (
        "school_id,school_name,ipeds_id,in_scope,field_key,value_numeric,"
        "source_table,data_year,quality_flag"
    )
    current_select = "ipeds_id,school_id,field_key,value_numeric,source_table,data_year"
    fact_rows: list[dict[str, Any]] = []
    current_fact_rows: list[dict[str, Any]] = []
    for field_key in ADM_COUNT_FIELDS:
        fact_rows.extend(
            postgrest_get_all(
                base_url,
                api_key,
                "school_facts_unified",
                {
                    "select": fact_select,
                    "field_key": f"eq.{field_key}",
                    "source_table": f"eq.{ADM_SOURCE_TABLE}",
                    "order": "ipeds_id.asc",
                },
            )
        )
        current_fact_rows.extend(
            postgrest_get_all(
                base_url,
                api_key,
                "ipeds_current_facts",
                {
                    "select": current_select,
                    "field_key": f"eq.{field_key}",
                    "source_table": f"eq.{ADM_SOURCE_TABLE}",
                    "order": "ipeds_id.asc",
                },
            )
        )

    directory_rows = postgrest_get_all(
        base_url,
        api_key,
        "institution_directory",
        {
            "select": "ipeds_id,school_id,school_name,in_scope",
            "order": "ipeds_id.asc",
        },
    )
    scorecard_rows = postgrest_get_all(
        base_url,
        api_key,
        "scorecard_summary",
        {
            "select": ",".join(
                ("ipeds_id", "scorecard_data_year", *SCORECARD_FIELDS)
            ),
            "order": "ipeds_id.asc",
        },
    )
    browser_rows = postgrest_get_all(
        base_url,
        api_key,
        "school_browser_rows",
        {
            "select": (
                "school_id,ipeds_id,canonical_year,sub_institutional,"
                "acceptance_rate,yield_rate,updated_at"
            ),
            "canonical_year": f"eq.{CDS_YEAR}",
            "sub_institutional": "is.null",
            "acceptance_rate": "not.is.null",
            "yield_rate": "not.is.null",
            # school_id tiebreaker keeps offset pagination stable when many
            # rows share an updated_at timestamp.
            "order": "updated_at.desc,school_id.asc",
        },
    )
    return {
        "fact_rows": fact_rows,
        "current_fact_rows": current_fact_rows,
        "directory_rows": directory_rows,
        "scorecard_rows": scorecard_rows,
        "browser_rows": browser_rows,
    }


def _normalize_ipeds(value: Any) -> str:
    return str(value or "").strip()


def index_adm_counts(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Pivot long-format ADM count rows by ipeds_id."""
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        field_key = str(row.get("field_key") or "")
        if field_key in ROUNDED_RATE_FIELDS:
            raise ValueError(
                "refusing integer-rounded DRVADM rate fields in the plotted series"
            )
        if field_key not in ADM_COUNT_FIELDS:
            continue
        source_table = str(row.get("source_table") or "")
        if source_table and source_table != ADM_SOURCE_TABLE:
            continue
        ipeds_id = _normalize_ipeds(row.get("ipeds_id"))
        if not ipeds_id:
            continue
        school = indexed.setdefault(
            ipeds_id,
            {
                "ipedsId": ipeds_id,
                "schoolId": str(row.get("school_id") or "") or None,
                "schoolName": str(row.get("school_name") or "") or None,
                "inScope": row.get("in_scope"),
                "counts": {},
            },
        )
        if row.get("school_id") and not school["schoolId"]:
            school["schoolId"] = str(row["school_id"])
        if row.get("school_name") and not school["schoolName"]:
            school["schoolName"] = str(row["school_name"])
        if school["inScope"] is None and row.get("in_scope") is not None:
            school["inScope"] = row.get("in_scope")
        count = parse_count(row.get("value_numeric"))
        existing = school["counts"].get(field_key)
        if existing is not None and existing != count:
            raise ValueError(f"conflicting ADM2024 {field_key} for ipeds_id {ipeds_id}")
        school["counts"][field_key] = count
    return indexed


def index_directory(
    rows: Iterable[Mapping[str, Any]],
    canonical_school_ids: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    directory: dict[str, dict[str, Any]] = {}
    for row in rows:
        ipeds_id = _normalize_ipeds(row.get("ipeds_id"))
        if not ipeds_id:
            continue
        directory[ipeds_id] = {
            "schoolId": (
                canonical_school_ids.get(ipeds_id)
                or str(row.get("school_id") or "")
                or None
            ),
            "schoolName": str(row.get("school_name") or "") or None,
            "inScope": row.get("in_scope") is True,
        }
    return directory


def index_scorecard(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        ipeds_id = _normalize_ipeds(row.get("ipeds_id"))
        if not ipeds_id:
            continue
        indexed[ipeds_id] = row
    return indexed


def index_cds_crosscheck(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], int]:
    """Return (by_ipeds, by_school_id, unique_school_count) after latest-row wins."""
    by_ipeds: dict[str, dict[str, Any]] = {}
    by_school: dict[str, dict[str, Any]] = {}
    unique_schools: set[str] = set()
    ordered = sorted(
        rows,
        key=lambda row: str(row.get("updated_at") or ""),
        reverse=True,
    )
    for row in ordered:
        if row.get("sub_institutional"):
            continue
        if str(row.get("canonical_year") or "") != CDS_YEAR:
            continue
        acceptance = parse_decimal(row.get("acceptance_rate"))
        yield_value = parse_decimal(row.get("yield_rate"))
        if acceptance is None or yield_value is None:
            continue
        parsed = {
            "cdsAcceptanceRate": rate_json(acceptance),
            "cdsYieldRate": rate_json(yield_value),
            "cdsYear": CDS_YEAR,
        }
        school_id = str(row.get("school_id") or "")
        ipeds_id = _normalize_ipeds(row.get("ipeds_id"))
        if school_id:
            unique_schools.add(school_id)
            by_school.setdefault(school_id, parsed)
        if ipeds_id:
            by_ipeds.setdefault(ipeds_id, parsed)
    return by_ipeds, by_school, len(unique_schools)


def _positive_scorecard(row: Mapping[str, Any]) -> dict[str, Decimal] | None:
    values: dict[str, Decimal] = {}
    for field in SCORECARD_FIELDS:
        parsed = parse_decimal(row.get(field))
        if parsed is None or parsed <= 0:
            return None
        values[field] = parsed
    return values


def build_recipe_artifact(
    *,
    fact_rows: Iterable[Mapping[str, Any]],
    directory_rows: Iterable[Mapping[str, Any]],
    scorecard_rows: Iterable[Mapping[str, Any]],
    browser_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    current_fact_rows: Iterable[Mapping[str, Any]] | None = None,
    canonical_school_ids: Mapping[str, str] | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    canonical_school_ids = canonical_school_ids or {}
    unified = index_adm_counts(fact_rows)
    current = index_adm_counts(current_fact_rows or [])
    directory = index_directory(directory_rows, canonical_school_ids)
    scorecard = index_scorecard(scorecard_rows)
    cds_by_ipeds, cds_by_school, cds_unique = index_cds_crosscheck(browser_rows)

    exclusions = {
        "missingZeroCounts": 0,
        "admittedGtApplied": 0,
        "enrolledGtAdmitted": 0,
        "outOfScope": 0,
        "missingNonpositiveScorecard": 0,
    }
    join_misses = {"directory": 0, "scorecard": 0}

    out_of_scope_ids: set[str] = set()
    current_ids = set(current) | set(unified)
    for ipeds_id in current_ids:
        directory_row = directory.get(ipeds_id)
        unified_row = unified.get(ipeds_id)
        if directory_row is not None:
            in_scope = directory_row["inScope"] is True
        elif unified_row is not None:
            # school_facts_unified is the in-scope serving view; an explicit
            # False still excludes, but a missing flag is treated as in-scope.
            in_scope = unified_row.get("inScope") is not False
        else:
            join_misses["directory"] += 1
            continue
        if not in_scope:
            out_of_scope_ids.add(ipeds_id)
    exclusions["outOfScope"] = len(out_of_scope_ids)

    panel_a_exact: list[dict[str, Any]] = []
    for ipeds_id, school in sorted(unified.items()):
        if ipeds_id in out_of_scope_ids:
            continue
        directory_row = directory.get(ipeds_id)
        if directory_row is None and school.get("inScope") is not True:
            # Unified rows are already in-scope; missing directory is a join miss
            # only when we cannot name or key the school.
            if not school.get("schoolId"):
                join_misses["directory"] += 1
                continue
        counts = school["counts"]
        applied = counts.get("applicants_total")
        admitted = counts.get("admissions_total")
        enrolled = counts.get("enrolled_total")
        if (
            applied is None
            or admitted is None
            or enrolled is None
            or applied <= 0
            or admitted <= 0
            or enrolled <= 0
        ):
            exclusions["missingZeroCounts"] += 1
            continue
        if admitted > applied:
            exclusions["admittedGtApplied"] += 1
            continue
        if enrolled > admitted:
            exclusions["enrolledGtAdmitted"] += 1
            continue
        school_id = (
            (directory_row or {}).get("schoolId")
            or canonical_school_ids.get(ipeds_id)
            or school.get("schoolId")
        )
        school_name = (
            school.get("schoolName")
            or (directory_row or {}).get("schoolName")
            or school_id
        )
        if not school_id or not school_name:
            join_misses["directory"] += 1
            continue
        exact_acceptance = acceptance_rate(admitted, applied)
        exact_yield = yield_rate(enrolled, admitted)
        panel_a_exact.append(
            {
                "schoolId": school_id,
                "name": school_name,
                "ipedsId": ipeds_id,
                "applied": int(applied),
                "admitted": int(admitted),
                "enrolled": int(enrolled),
                "acceptanceExact": exact_acceptance,
                "yieldExact": exact_yield,
                "acceptanceRate": round_rate(exact_acceptance),
                "yieldRate": round_rate(exact_yield),
            }
        )

    if not panel_a_exact:
        raise ValueError("pricing-power Panel A produced no schools")

    panel_b_exact: list[dict[str, Any]] = []
    for row in panel_a_exact:
        score = scorecard.get(row["ipedsId"])
        if score is None:
            join_misses["scorecard"] += 1
            continue
        values = _positive_scorecard(score)
        if values is None:
            exclusions["missingNonpositiveScorecard"] += 1
            continue
        burden = debt_burden(
            values["median_debt_monthly_payment"],
            values["earnings_10yr_median"],
        )
        ratio = instruction_net_price_ratio(
            values["instructional_expenditure_fte"],
            values["avg_net_price"],
        )
        panel_b_exact.append(
            {
                **row,
                "burdenExact": burden,
                "ratioExact": ratio,
                "burden": round_rate(burden),
                "medianDebt": money_json(values["median_debt_completers"]),
                "monthlyPayment": cents_json(values["median_debt_monthly_payment"]),
                "earnings10yr": money_json(values["earnings_10yr_median"]),
                "avgNetPrice": money_json(values["avg_net_price"]),
                "instructionFte": money_json(values["instructional_expenditure_fte"]),
                "instructionNetPriceRatio": round_rate(ratio),
                "scorecardYear": score.get("scorecard_data_year"),
            }
        )
    if not panel_b_exact and validate:
        raise ValueError("pricing-power Panel B produced no schools")

    median_acceptance = statistics.median(row["acceptanceRate"] for row in panel_a_exact)
    median_yield = statistics.median(row["yieldRate"] for row in panel_a_exact)
    if panel_b_exact:
        median_yield_b = statistics.median(row["yieldRate"] for row in panel_b_exact)
        median_burden = statistics.median(row["burden"] for row in panel_b_exact)
    else:
        median_yield_b = Decimal(0)
        median_burden = Decimal(0)
    median_acceptance_s = round_rate(median_acceptance)
    median_yield_s = round_rate(median_yield)
    median_yield_b_s = round_rate(median_yield_b)
    median_burden_s = round_rate(median_burden)

    quadrants_a = {key: 0 for key in PANEL_A_QUADRANTS}
    for row in panel_a_exact:
        quadrants_a[
            panel_a_quadrant(
                row["acceptanceRate"],
                row["yieldRate"],
                median_acceptance_s,
                median_yield_s,
            )
        ] += 1
    quadrants_b = {key: 0 for key in PANEL_B_QUADRANTS}
    for row in panel_b_exact:
        quadrants_b[
            panel_b_quadrant(
                row["yieldRate"],
                row["burden"],
                median_yield_b_s,
                median_burden_s,
            )
        ] += 1
    if sum(quadrants_a.values()) != len(panel_a_exact):
        raise ValueError("Panel A quadrant counts do not sum to panelACount")
    if sum(quadrants_b.values()) != len(panel_b_exact):
        raise ValueError("Panel B quadrant counts do not sum to panelBCount")

    panel_b_by_ipeds = {row["ipedsId"]: row for row in panel_b_exact}
    schools: list[dict[str, Any]] = []
    for row in sorted(panel_a_exact, key=lambda item: item["name"].casefold()):
        serialized: dict[str, Any] = {
            "schoolId": row["schoolId"],
            "name": row["name"],
            "ipedsId": row["ipedsId"],
            "applied": row["applied"],
            "admitted": row["admitted"],
            "enrolled": row["enrolled"],
            "acceptanceRate": rate_json(row["acceptanceRate"]),
            "yieldRate": rate_json(row["yieldRate"]),
        }
        cds = cds_by_ipeds.get(row["ipedsId"]) or cds_by_school.get(row["schoolId"])
        if cds:
            serialized.update(cds)
        panel_b = panel_b_by_ipeds.get(row["ipedsId"])
        if panel_b:
            serialized.update(
                {
                    "burden": rate_json(panel_b["burden"]),
                    "medianDebt": panel_b["medianDebt"],
                    "monthlyPayment": panel_b["monthlyPayment"],
                    "earnings10yr": panel_b["earnings10yr"],
                    "avgNetPrice": panel_b["avgNetPrice"],
                    "instructionFte": panel_b["instructionFte"],
                    "instructionNetPriceRatio": rate_json(
                        panel_b["instructionNetPriceRatio"]
                    ),
                }
            )
        schools.append(serialized)

    scorecard_years = sorted(
        {
            str(row["scorecardYear"])
            for row in panel_b_exact
            if row.get("scorecardYear")
        }
    )
    cds_attached = sum(1 for row in schools if "cdsAcceptanceRate" in row)
    distinct_yields = {row["yieldRate"] for row in schools}

    meta = {
        "generatedAt": generated_at,
        "sourceApiUrl": SOURCE_API_URL,
        "ipedsCycle": IPEDS_CYCLE,
        "scorecardYears": scorecard_years,
        "panelACount": len(schools),
        "panelBCount": len(panel_b_exact),
        "medianAcceptance": rate_json(median_acceptance_s),
        "medianYield": rate_json(median_yield_s),
        "medianYieldB": rate_json(median_yield_b_s),
        "medianBurden": rate_json(median_burden_s),
        "quadrantsA": quadrants_a,
        "quadrantsB": quadrants_b,
        "cdsCrosscheckCount": cds_unique,
        "cdsAttachedCount": cds_attached,
        "annotationSchoolId": SYRACUSE_SCHOOL_ID,
        "annotationIpedsId": SYRACUSE_IPEDS_ID,
        "exclusions": exclusions,
        "joinMisses": join_misses,
    }
    if validate:
        _assert_build_invariants(schools, panel_b_exact, meta, distinct_yields)
    return {"meta": meta, "schools": schools}


def _assert_build_invariants(
    schools: list[dict[str, Any]],
    panel_b: list[dict[str, Any]],
    meta: Mapping[str, Any],
    distinct_yields: set[Any],
) -> None:
    panel_a_ids = {row["schoolId"] for row in schools}
    panel_b_ids = {row["schoolId"] for row in panel_b}
    if SYRACUSE_SCHOOL_ID not in panel_a_ids or SYRACUSE_IPEDS_ID not in {
        row["ipedsId"] for row in schools
    }:
        raise ValueError("Syracuse University is missing from Panel A")
    if SYRACUSE_SCHOOL_ID not in panel_b_ids:
        raise ValueError("Syracuse University is missing from Panel B")
    syracuse = next(row for row in panel_b if row["schoolId"] == SYRACUSE_SCHOOL_ID)
    burden = syracuse["burdenExact"]
    if burden < SYRACUSE_BURDEN_MIN or burden > SYRACUSE_BURDEN_MAX:
        raise ValueError(
            f"Syracuse burden {burden} is outside "
            f"[{SYRACUSE_BURDEN_MIN}, {SYRACUSE_BURDEN_MAX}]"
        )
    if not PANEL_A_MIN <= meta["panelACount"] <= PANEL_A_MAX:
        raise ValueError(
            f"Panel A count {meta['panelACount']} is outside "
            f"[{PANEL_A_MIN}, {PANEL_A_MAX}]"
        )
    if not PANEL_B_MIN <= meta["panelBCount"] <= PANEL_B_MAX:
        raise ValueError(
            f"Panel B count {meta['panelBCount']} is outside "
            f"[{PANEL_B_MIN}, {PANEL_B_MAX}]"
        )
    if len(distinct_yields) <= MIN_DISTINCT_YIELDS:
        raise ValueError(
            f"only {len(distinct_yields)} distinct yield values; "
            "refusing integer-rounded rate series"
        )
    for row in panel_b:
        if row["burdenExact"] > BURDEN_AXIS_MAX:
            raise ValueError(
                f"{row['schoolId']} burden {row['burdenExact']} exceeds the "
                f"Figure 2 axis maximum {BURDEN_AXIS_MAX}"
            )
    missing_anchors = [
        school_id
        for school_id in REQUIRED_PANEL_B_ANCHORS
        if school_id not in panel_b_ids
    ]
    if missing_anchors:
        raise ValueError(
            "required Panel B anchor school(s) missing: "
            + ", ".join(missing_anchors)
        )


def render_typescript(artifact: Mapping[str, Any]) -> str:
    meta = json.dumps(artifact["meta"], indent=2, ensure_ascii=False)
    school_lines = [
        "  " + json.dumps(school, ensure_ascii=False, separators=(",", ":"))
        for school in artifact["schools"]
    ]
    schools = "[\n" + ",\n".join(school_lines) + "\n]"
    return f"""// Generated by tools/ipeds/build_pricing_power_recipe.py. Do not edit by hand.

import type {{ PricingPowerSchool }} from "./pricing-power-recipe-analysis";

export const PRICING_POWER_ANNOTATION_SCHOOL_ID = "{SYRACUSE_SCHOOL_ID}" as const;
export const PRICING_POWER_ANNOTATION_IPEDS_ID = "{SYRACUSE_IPEDS_ID}" as const;

export const PRICING_POWER_META = {meta} as const;

export const PRICING_POWER_SCHOOLS: readonly PricingPowerSchool[] = {schools};
"""


if __name__ == "__main__":
    raise SystemExit(main())
