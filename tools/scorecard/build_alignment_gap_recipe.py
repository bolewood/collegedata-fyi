#!/usr/bin/env python3
"""Build the checked-in dataset for /recipes/alignment-gap.

Panel B (endowment) joins Scorecard debt, earnings, net price, endowment, and
instructional spend to the latest CDS SAT midpoint and directory undergraduate
enrollment.

Panel A (merit) starts from school_merit_profile — already a CDS H2A ×
Scorecard join — then attaches IPEDS endowment per undergraduate. Merit spend
per first-year student is H2A share × average non-need grant, after range
guards the quality flag does not enforce.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "web/src/lib/alignment-gap-recipe-data.ts"
SOURCE_API_URL = "https://api.collegedata.fyi"
CDS_YEARS = ("2024-25", "2025-26")
PAGE_SIZE = 1000


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def postgrest_get_all(
    base_url: str,
    api_key: str,
    table: str,
    params: Mapping[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page_params = dict(params)
        page_params.update({"limit": str(PAGE_SIZE), "offset": str(offset)})
        query = urllib.parse.urlencode(page_params, safe="(),.")
        url = f"{base_url.rstrip('/')}/rest/v1/{table}?{query}"
        request = urllib.request.Request(
            url,
            headers={"apikey": api_key, "Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                page = json.load(response)
        except urllib.error.HTTPError as exc:
            raise ValueError(f"PostgREST {table} failed with HTTP {exc.code}") from None
        if not isinstance(page, list):
            raise ValueError(f"PostgREST {table} returned a non-row response")
        if not page:
            return rows
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += len(page)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default=date.today().isoformat())
    args = parser.parse_args()
    try:
        date.fromisoformat(args.generated_at)
    except ValueError:
        parser.error("--generated-at must be an ISO date (YYYY-MM-DD)")

    load_env(REPO_ROOT / ".env")
    supabase_url = os.environ.get("SUPABASE_URL", "").strip() or SOURCE_API_URL
    api_key = (
        os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
    )
    if not api_key:
        print("error: SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY is required", file=sys.stderr)
        return 2

    try:
        artifact = build_artifact(supabase_url, api_key, generated_at=args.generated_at)
    except (OSError, ValueError) as exc:
        print(f"error: alignment-gap build failed: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_typescript(artifact), encoding="utf-8")
    print(
        f"wrote {args.out} (panel B {artifact['meta']['schoolCount']} schools, "
        f"panel A {artifact['meritMeta']['schoolCount']} schools, "
        f"merit median burden {artifact['meritMeta']['medianBurden'] * 100:.2f}%)"
    )
    return 0


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def build_artifact(base_url: str, api_key: str, *, generated_at: str) -> dict[str, Any]:
    endowment = build_endowment_panel(base_url, api_key, generated_at=generated_at)
    merit = build_merit_panel(base_url, api_key, generated_at=generated_at)
    return {
        "meta": endowment["meta"],
        "schools": endowment["schools"],
        "meritMeta": merit["meta"],
        "meritSchools": merit["schools"],
    }


def build_endowment_panel(base_url: str, api_key: str, *, generated_at: str) -> dict[str, Any]:
    scorecard_rows = postgrest_get_all(
        base_url,
        api_key,
        "scorecard_summary",
        {
            "select": ",".join(
                [
                    "ipeds_id",
                    "scorecard_data_year",
                    "earnings_10yr_median",
                    "median_debt_monthly_payment",
                    "median_debt_completers",
                    "avg_net_price",
                    "endowment_end",
                    "instructional_expenditure_fte",
                    "enrollment",
                ]
            ),
            "earnings_10yr_median": "gt.0",
            "median_debt_monthly_payment": "gt.0",
            "median_debt_completers": "gt.0",
            "avg_net_price": "gt.0",
            "endowment_end": "gt.0",
            "instructional_expenditure_fte": "gt.0",
            "enrollment": "gt.0",
        },
    )
    directory_rows = postgrest_get_all(
        base_url,
        api_key,
        "institution_directory",
        {"select": "school_id,school_name,ipeds_id,undergraduate_enrollment"},
    )
    browser_rows = postgrest_get_all(
        base_url,
        api_key,
        "school_browser_rows",
        {
            "select": "school_id,canonical_year,year_start,sat_composite_p50,sub_institutional",
            "sat_composite_p50": "not.is.null",
            "canonical_year": f"in.({','.join(CDS_YEARS)})",
            "order": "year_start.desc",
        },
    )

    by_ipeds = {
        row["ipeds_id"]: row
        for row in directory_rows
        if isinstance(row.get("ipeds_id"), str) and row["ipeds_id"]
    }
    sat_by_school: dict[str, dict[str, Any]] = {}
    for row in browser_rows:
        if row.get("sub_institutional") or not row.get("school_id"):
            continue
        sat_by_school.setdefault(row["school_id"], row)

    joined: list[dict[str, Any]] = []
    for score in scorecard_rows:
        directory = by_ipeds.get(score.get("ipeds_id"))
        if not directory:
            continue
        sat = sat_by_school.get(directory["school_id"])
        if not sat:
            continue
        undergrad = directory.get("undergraduate_enrollment") or score.get("enrollment")
        try:
            earnings = float(score["earnings_10yr_median"])
            monthly = float(score["median_debt_monthly_payment"])
            completers = float(score["median_debt_completers"])
            net_price = float(score["avg_net_price"])
            endowment = float(score["endowment_end"])
            instruction = float(score["instructional_expenditure_fte"])
            undergrad_n = float(undergrad)
            sat_mid = float(sat["sat_composite_p50"])
        except (TypeError, ValueError, KeyError):
            continue
        if min(earnings, monthly, completers, net_price, endowment, instruction, undergrad_n, sat_mid) <= 0:
            continue
        burden = (monthly * 12) / earnings
        joined.append(
            {
                "schoolId": directory["school_id"],
                "schoolName": directory["school_name"],
                "cdsYear": sat["canonical_year"],
                "satCompositeP50": int(sat_mid),
                "earnings10yrMedian": int(earnings),
                "medianDebtCompleters": int(completers),
                "medianDebtMonthlyPayment": round(monthly, 2),
                "avgNetPrice": int(net_price),
                "endowmentEnd": int(endowment),
                "instructionalExpenditureFte": int(instruction),
                "undergraduateEnrollment": int(undergrad_n),
                "burden": burden,
                "endowmentPerStudent": endowment / undergrad_n,
                "instructionShare": instruction / net_price,
                "scorecardYear": score.get("scorecard_data_year"),
            }
        )

    if len(joined) < 50:
        raise ValueError(f"alignment-gap join produced only {len(joined)} schools")

    burdens = [row["burden"] for row in joined]
    median_burden = statistics.median(burdens)
    for row in joined:
        row["gap"] = (row["medianDebtCompleters"] * (1 - median_burden / row["burden"])) / 4
    endowments = [row["endowmentPerStudent"] for row in joined]
    median_endowment = statistics.median(endowments)

    def count_quad(pred: Any) -> int:
        return sum(1 for row in joined if pred(row))

    above = count_quad(lambda row: row["gap"] > 0)
    schools = []
    for row in sorted(joined, key=lambda item: item["schoolName"].lower()):
        schools.append(
            {
                "schoolId": row["schoolId"],
                "schoolName": row["schoolName"],
                "cdsYear": row["cdsYear"],
                "satCompositeP50": row["satCompositeP50"],
                "earnings10yrMedian": row["earnings10yrMedian"],
                "medianDebtCompleters": row["medianDebtCompleters"],
                "medianDebtMonthlyPayment": row["medianDebtMonthlyPayment"],
                "avgNetPrice": row["avgNetPrice"],
                "endowmentEnd": row["endowmentEnd"],
                "instructionalExpenditureFte": row["instructionalExpenditureFte"],
                "undergraduateEnrollment": row["undergraduateEnrollment"],
                "burden": round(row["burden"], 6),
                "gap": round(row["gap"], 2),
                "endowmentPerStudent": round(row["endowmentPerStudent"], 2),
                "instructionShare": round(row["instructionShare"], 4),
            }
        )
    scorecard_years = sorted({row["scorecardYear"] for row in joined if row.get("scorecardYear")})

    debts = [row["medianDebtCompleters"] for row in joined]
    debt_counts = {}
    for debt in debts:
        key = int(debt)
        debt_counts[key] = debt_counts.get(key, 0) + 1
    debt_mode_value, debt_mode_count = max(debt_counts.items(), key=lambda item: (item[1], item[0]))

    return {
        "meta": {
            "generatedAt": generated_at,
            "sourceApiUrl": SOURCE_API_URL,
            "scorecardYears": scorecard_years,
            "cdsYears": list(CDS_YEARS),
            "schoolCount": len(schools),
            "sample": "endowment-join",
            "medianBurden": round(median_burden, 6),
            "medianEndowmentPerStudent": round(median_endowment, 2),
            "aboveMedianBurden": above,
            "quadrants": {
                "capacity": count_quad(lambda r: r["gap"] > 0 and r["endowmentPerStudent"] >= median_endowment),
                "constrained": count_quad(lambda r: r["gap"] > 0 and r["endowmentPerStudent"] < median_endowment),
                "absorbs": count_quad(lambda r: r["gap"] <= 0 and r["endowmentPerStudent"] >= median_endowment),
                "earnings": count_quad(lambda r: r["gap"] <= 0 and r["endowmentPerStudent"] < median_endowment),
            },
            "debtMin": int(min(debts)),
            "debtMax": int(max(debts)),
            "debtMode": debt_mode_value,
            "debtModeCount": debt_mode_count,
            "join": (
                "scorecard_summary debt, earnings, net price, endowment, and instructional "
                "spend, joined to institution_directory undergraduate enrollment and the "
                "latest 2024-25 or 2025-26 school_browser_rows SAT composite midpoint"
            ),
        },
        "schools": schools,
    }


def build_merit_panel(base_url: str, api_key: str, *, generated_at: str) -> dict[str, Any]:
    merit_rows = postgrest_get_all(
        base_url,
        api_key,
        "school_merit_profile",
        {
            "select": ",".join(
                [
                    "school_id",
                    "school_name",
                    "ipeds_id",
                    "canonical_year",
                    "merit_profile_quality",
                    "non_need_aid_share_first_year_ft",
                    "avg_non_need_grant_first_year_ft",
                    "earnings_10yr_median",
                    "median_debt_completers",
                    "median_debt_monthly_payment",
                    "avg_net_price",
                ]
            ),
        },
    )
    scorecard_rows = postgrest_get_all(
        base_url,
        api_key,
        "scorecard_summary",
        {
            "select": "ipeds_id,endowment_end,instructional_expenditure_fte,enrollment,scorecard_data_year",
        },
    )
    browser_rows = postgrest_get_all(
        base_url,
        api_key,
        "school_browser_rows",
        {
            "select": "school_id,canonical_year,year_start,undergrad_enrollment_scorecard,sub_institutional",
            "canonical_year": f"in.({','.join(CDS_YEARS)})",
            "order": "year_start.desc",
        },
    )

    score_by_ipeds = {
        row["ipeds_id"]: row
        for row in scorecard_rows
        if isinstance(row.get("ipeds_id"), str) and row["ipeds_id"]
    }
    enroll_by_school: dict[str, Any] = {}
    for row in browser_rows:
        if row.get("sub_institutional") or not row.get("school_id"):
            continue
        enroll_by_school.setdefault(row["school_id"], row.get("undergrad_enrollment_scorecard"))

    exclusions = {
        "universe": len(merit_rows),
        "qualityLimited": 0,
        "qualityMissing": 0,
        "missingH2a": 0,
        "rangeShare": 0,
        "rangeGrant": 0,
        "missingScorecard": 0,
    }
    range_share_schools: list[str] = []
    joined: list[dict[str, Any]] = []

    for row in merit_rows:
        quality = row.get("merit_profile_quality")
        if quality == "limited":
            exclusions["qualityLimited"] += 1
            continue
        if quality != "strong" and quality != "partial":
            exclusions["qualityMissing"] += 1
            continue
        share = _float(row.get("non_need_aid_share_first_year_ft"))
        grant = _float(row.get("avg_non_need_grant_first_year_ft"))
        if share is None or grant is None:
            exclusions["missingH2a"] += 1
            continue
        if not 0 <= share <= 1:
            exclusions["rangeShare"] += 1
            if row.get("school_name"):
                range_share_schools.append(str(row["school_name"]))
            continue
        if not 0 < grant <= 80_000:
            exclusions["rangeGrant"] += 1
            continue
        earnings = _float(row.get("earnings_10yr_median"))
        monthly = _float(row.get("median_debt_monthly_payment"))
        completers = _float(row.get("median_debt_completers"))
        net_price = _float(row.get("avg_net_price"))
        if not earnings or not monthly or not completers or not net_price:
            exclusions["missingScorecard"] += 1
            continue
        if min(earnings, monthly, completers, net_price) <= 0:
            exclusions["missingScorecard"] += 1
            continue
        score = score_by_ipeds.get(row.get("ipeds_id"))
        endowment = _float(score.get("endowment_end")) if score else None
        undergrad = _float(enroll_by_school.get(row.get("school_id"))) or (
            _float(score.get("enrollment")) if score else None
        )
        if not endowment or not undergrad or min(endowment, undergrad) <= 0:
            exclusions["missingScorecard"] += 1
            continue
        burden = (monthly * 12) / earnings
        joined.append(
            {
                "schoolId": row["school_id"],
                "schoolName": row["school_name"],
                "cdsYear": row.get("canonical_year"),
                "meritShare": share,
                "avgMeritGrant": grant,
                "meritPerFirstYear": share * grant,
                "earnings10yrMedian": int(earnings),
                "medianDebtCompleters": int(completers),
                "medianDebtMonthlyPayment": round(monthly, 2),
                "avgNetPrice": int(net_price),
                "endowmentEnd": int(endowment),
                "undergraduateEnrollment": int(undergrad),
                "burden": burden,
                "endowmentPerStudent": endowment / undergrad,
                "scorecardYear": score.get("scorecard_data_year") if score else None,
            }
        )

    if len(joined) < 50:
        raise ValueError(f"alignment-gap merit join produced only {len(joined)} schools")

    accounted = (
        exclusions["qualityLimited"]
        + exclusions["qualityMissing"]
        + exclusions["missingH2a"]
        + exclusions["rangeShare"]
        + exclusions["rangeGrant"]
        + exclusions["missingScorecard"]
        + len(joined)
    )
    if accounted != exclusions["universe"]:
        raise ValueError(
            f"merit exclusion counts sum to {accounted}, universe is {exclusions['universe']}"
        )

    burdens = [row["burden"] for row in joined]
    median_burden = statistics.median(burdens)
    for row in joined:
        row["gap"] = (row["medianDebtCompleters"] * (1 - median_burden / row["burden"])) / 4
    endowments = [row["endowmentPerStudent"] for row in joined]
    terciles = statistics.quantiles(endowments, n=3)
    covers = sum(1 for row in joined if row["gap"] > 0 and row["meritPerFirstYear"] >= row["gap"])
    constrained = sum(1 for row in joined if row["gap"] > 0 and row["meritPerFirstYear"] < row["gap"])
    none = sum(1 for row in joined if row["gap"] <= 0)
    positive = covers + constrained
    if covers + constrained + none != len(joined):
        raise ValueError("merit region counts do not sum to plotted n")

    schools = []
    for row in sorted(joined, key=lambda item: item["schoolName"].lower()):
        schools.append(
            {
                "schoolId": row["schoolId"],
                "schoolName": row["schoolName"],
                "cdsYear": row["cdsYear"],
                "meritShare": round(row["meritShare"], 6),
                "avgMeritGrant": round(row["avgMeritGrant"], 2),
                "meritPerFirstYear": round(row["meritPerFirstYear"], 2),
                "earnings10yrMedian": row["earnings10yrMedian"],
                "medianDebtCompleters": row["medianDebtCompleters"],
                "medianDebtMonthlyPayment": row["medianDebtMonthlyPayment"],
                "avgNetPrice": row["avgNetPrice"],
                "endowmentEnd": row["endowmentEnd"],
                "undergraduateEnrollment": row["undergraduateEnrollment"],
                "burden": round(row["burden"], 6),
                "gap": round(row["gap"], 2),
                "endowmentPerStudent": round(row["endowmentPerStudent"], 2),
            }
        )
    scorecard_years = sorted({row["scorecardYear"] for row in joined if row.get("scorecardYear")})

    return {
        "meta": {
            "generatedAt": generated_at,
            "sourceApiUrl": SOURCE_API_URL,
            "scorecardYears": scorecard_years,
            "cdsYears": list(CDS_YEARS),
            "schoolCount": len(schools),
            "sample": "merit-join",
            "medianBurden": round(median_burden, 6),
            "endowmentTerciles": [round(terciles[0], 2), round(terciles[1], 2)],
            "positiveGap": positive,
            "regions": {
                "covers": covers,
                "constrained": constrained,
                "none": none,
            },
            "coversShare": round(covers / positive, 4) if positive else 0,
            "exclusions": exclusions,
            "rangeShareSchools": sorted(range_share_schools),
            "join": (
                "school_merit_profile CDS H2A non-need share and average grant, joined to "
                "scorecard_summary endowment and school_browser_rows undergraduate enrollment. "
                "Dropped quality limited/missing, missing H2A, share outside [0, 1], average "
                "grant outside (0, 80000], and rows without Scorecard earnings, debt, net "
                "price, and endowment"
            ),
        },
        "schools": schools,
    }


def render_typescript(artifact: dict[str, Any]) -> str:
    meta = json.dumps(artifact["meta"], indent=2)
    schools = json.dumps(artifact["schools"], indent=2)
    merit_meta = json.dumps(artifact["meritMeta"], indent=2)
    merit_schools = json.dumps(artifact["meritSchools"], indent=2)
    return (
        "// Generated by tools/scorecard/build_alignment_gap_recipe.py. Do not edit by hand.\n\n"
        "import type { AlignmentGapMeritRow, AlignmentGapRow } from \"./alignment-gap-recipe-analysis\";\n\n"
        "export const ALIGNMENT_GAP_META = "
        f"{meta} as const;\n\n"
        "export const ALIGNMENT_GAP_SCHOOLS: readonly AlignmentGapRow[] = "
        f"{schools};\n\n"
        "export const ALIGNMENT_GAP_MERIT_META = "
        f"{merit_meta} as const;\n\n"
        "export const ALIGNMENT_GAP_MERIT_SCHOOLS: readonly AlignmentGapMeritRow[] = "
        f"{merit_schools};\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
