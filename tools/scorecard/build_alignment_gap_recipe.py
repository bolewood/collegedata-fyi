#!/usr/bin/env python3
"""Build the checked-in dataset for /recipes/alignment-gap.

Joins public Scorecard debt, earnings, net price, endowment, and instructional
spend to the latest CDS SAT midpoint and directory undergraduate enrollment.
The alignment gap is completer debt that would have to be shed to reach the
corpus median debt burden, divided across four years of college.
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
        f"wrote {args.out} ({artifact['meta']['schoolCount']} schools, "
        f"median burden {artifact['meta']['medianBurden'] * 100:.2f}%)"
    )
    return 0


def build_artifact(base_url: str, api_key: str, *, generated_at: str) -> dict[str, Any]:
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

    return {
        "meta": {
            "generatedAt": generated_at,
            "sourceApiUrl": SOURCE_API_URL,
            "scorecardYears": scorecard_years,
            "cdsYears": list(CDS_YEARS),
            "schoolCount": len(schools),
            "medianBurden": round(median_burden, 6),
            "medianEndowmentPerStudent": round(median_endowment, 2),
            "aboveMedianBurden": above,
            "quadrants": {
                "capacity": count_quad(lambda r: r["gap"] > 0 and r["endowmentPerStudent"] >= median_endowment),
                "constrained": count_quad(lambda r: r["gap"] > 0 and r["endowmentPerStudent"] < median_endowment),
                "absorbs": count_quad(lambda r: r["gap"] <= 0 and r["endowmentPerStudent"] >= median_endowment),
                "earnings": count_quad(lambda r: r["gap"] <= 0 and r["endowmentPerStudent"] < median_endowment),
            },
            "join": (
                "scorecard_summary debt, earnings, net price, endowment, and instructional "
                "spend, joined to institution_directory undergraduate enrollment and the "
                "latest 2024-25 or 2025-26 school_browser_rows SAT composite midpoint"
            ),
        },
        "schools": schools,
    }


def render_typescript(artifact: dict[str, Any]) -> str:
    meta = json.dumps(artifact["meta"], indent=2)
    schools = json.dumps(artifact["schools"], indent=2)
    return (
        "// Generated by tools/scorecard/build_alignment_gap_recipe.py. Do not edit by hand.\n\n"
        "import type { AlignmentGapRow } from \"./alignment-gap-recipe-analysis\";\n\n"
        "export const ALIGNMENT_GAP_META = "
        f"{meta} as const;\n\n"
        "export const ALIGNMENT_GAP_SCHOOLS: readonly AlignmentGapRow[] = "
        f"{schools};\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
