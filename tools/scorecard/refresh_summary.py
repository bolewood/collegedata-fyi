#!/usr/bin/env python3
"""Refresh scorecard_summary from the College Scorecard Most-Recent
Institution-Level CSV.

The Scorecard CSV has ~3,400 columns; this script selects only the
~43 that the scorecard_summary table carries and upserts one row per
UNITID. Designed to run once per year after each Scorecard release
(typically October).

Usage:
    # Dry run — parse the CSV and print a row count + sample without
    # writing anything.
    python tools/scorecard/refresh_summary.py \\
      --csv ~/Downloads/Most-Recent-Cohorts-Institution.csv \\
      --data-year 2022-23

    # Apply — upserts into scorecard_summary via service-role client.
    python tools/scorecard/refresh_summary.py \\
      --csv ~/Downloads/Most-Recent-Cohorts-Institution.csv \\
      --data-year 2022-23 \\
      --apply

Requirements:
  - pip install pandas supabase python-dotenv
  - .env file at repo root with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY

Scorecard downloads:
  https://collegescorecard.ed.gov/data/
Data dictionary:
  https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# Scorecard CSV column → scorecard_summary column.
# When a field has separate public / private-nonprofit variants, both
# Scorecard columns are listed and we pick the one populated per row.
# Source of truth: scorecard-summary-table-v2-plan.md.
COLUMN_MAP: dict[str, str | tuple[str, str]] = {
    "school_name":                    "INSTNM",
    "earnings_6yr_median":            "MD_EARN_WNE_P6",
    "earnings_8yr_median":            "MD_EARN_WNE_P8",
    "earnings_10yr_median":           "MD_EARN_WNE_P10",
    "earnings_10yr_p25":              "PCT25_EARN_WNE_P10",
    "earnings_10yr_p75":              "PCT75_EARN_WNE_P10",
    "median_debt_completers":         "GRAD_DEBT_MDN",
    "median_debt_noncompleters":      "WDRAW_DEBT_MDN",
    "median_debt_monthly_payment":    "GRAD_DEBT_MDN10YR",
    "cumulative_debt_p90":            "CUML_DEBT_P90",
    # PELL_DEBT_MDN is the March-2026 rename of GRAD_DEBT_MDN_PELL.
    # The non-Pell-debt counterpart was removed entirely from the
    # Scorecard data dictionary, hence no median_debt_non_pell here —
    # see migration 20260420180000_scorecard_pell_remap.sql.
    "median_debt_pell":               "PELL_DEBT_MDN",
    "avg_net_price":                  ("NPT4_PUB", "NPT4_PRIV"),
    "net_price_0_30k":                ("NPT41_PUB", "NPT41_PRIV"),
    "net_price_30k_48k":              ("NPT42_PUB", "NPT42_PRIV"),
    "net_price_48k_75k":              ("NPT43_PUB", "NPT43_PRIV"),
    "net_price_75k_110k":             ("NPT44_PUB", "NPT44_PRIV"),
    "net_price_110k_plus":            ("NPT45_PUB", "NPT45_PRIV"),
    "graduation_rate_4yr":            "C100_4",
    "graduation_rate_6yr":            "C150_4",
    "graduation_rate_8yr":            "C200_4",
    "grad_rate_pell":                 "C150_4_PELL",
    # C150_4_NONPELL was removed from the Scorecard data dictionary
    # (split into C150_4_LOANNOPELL + C150_4_NOLOANNOPELL); no clean
    # synthesis without per-cohort weights, so the column was dropped
    # — see migration 20260420180000_scorecard_pell_remap.sql.
    "transfer_out_rate":              "TRANS_4",
    "repayment_rate_3yr":             "RPY_3YR_RT",
    "default_rate_3yr":               "CDR3",
    "enrollment":                     "UGDS",
    "pell_grant_rate":                "PCTPELL",
    "federal_loan_rate":              "PCTFLOAN",
    "first_generation_share":         "PAR_ED_PCT_1STGEN",
    "median_family_income":           "MD_FAMINC",
    "female_share":                   "FEMALE",
    "retention_rate_ft":              "RET_FT4",
    "carnegie_basic":                 "CCBASIC",
    "locale":                         "LOCALE",
    "endowment_end":                  "ENDOWEND",
    "instructional_expenditure_fte":  "INEXPFTE",
    "faculty_salary_avg":             "AVGFACSAL",
}

# Boolean flags from 0/1 integer columns.
BOOL_MAP: dict[str, str] = {
    "historically_black": "HBCU",
    "predominantly_black": "PBI",
    "hispanic_serving": "HSI",
}

# Integer columns (avoid "37.0" strings from pandas floats; cast to int).
INT_COLS = {
    "earnings_6yr_median", "earnings_8yr_median", "earnings_10yr_median",
    "earnings_10yr_p25", "earnings_10yr_p75",
    "median_debt_completers", "median_debt_noncompleters",
    "cumulative_debt_p90", "median_debt_pell", "median_debt_non_pell",
    "avg_net_price", "net_price_0_30k", "net_price_30k_48k",
    "net_price_48k_75k", "net_price_75k_110k", "net_price_110k_plus",
    "enrollment", "median_family_income", "carnegie_basic", "locale",
    "endowment_end", "instructional_expenditure_fte", "faculty_salary_avg",
}

# Numeric (float) columns. Scorecard ships rates as 0-1 decimals already.
NUMERIC_COLS = {
    "median_debt_monthly_payment",
    "graduation_rate_4yr", "graduation_rate_6yr", "graduation_rate_8yr",
    "grad_rate_pell", "grad_rate_non_pell", "transfer_out_rate",
    "repayment_rate_3yr", "default_rate_3yr",
    "pell_grant_rate", "federal_loan_rate", "first_generation_share",
    "female_share", "retention_rate_ft",
}


def _coerce(value: Any, col: str) -> Any:
    """Cast a raw CSV value to the correct target type, or None for missing
    values. Scorecard uses NULL, 'NULL', and 'PrivacySuppressed' as missing
    indicators — we treat all three as None."""
    import pandas as pd  # lazy import so --help works without the dep

    if pd.isna(value):
        return None
    if isinstance(value, str):
        s = value.strip()
        if s in {"", "NULL", "PrivacySuppressed"}:
            return None
        value = s
    if col in INT_COLS:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    if col in NUMERIC_COLS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return value


def _coerce_bool(value: Any) -> bool | None:
    """Scorecard boolean flags are 0/1 integers (sometimes 'NULL')."""
    import pandas as pd
    if pd.isna(value):
        return None
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return None


def build_row(raw: dict[str, Any], data_year: str) -> dict[str, Any] | None:
    """Transform one Scorecard CSV row into a scorecard_summary row, or
    None if the row is missing a UNITID.

    UNITIDs are zero-padded to 6 characters to match the canonical NCES
    format. Without this, an IPEDS ID like '001234' in schools.yaml would
    not match '1234' emitted by int() → str() coercion in the upsert,
    causing the cds_scorecard LEFT JOIN to silently miss those schools."""
    unitid = raw.get("UNITID")
    import pandas as pd  # noqa: F401 — reused via _coerce
    if unitid is None or (isinstance(unitid, float) and unitid != unitid):
        return None
    try:
        ipeds_num = int(float(unitid))
    except (TypeError, ValueError):
        return None
    if ipeds_num <= 0:
        return None
    # Canonical IPEDS format: zero-padded to at least 6 digits. Larger
    # values (some branch campuses exceed 6 digits) pass through as-is.
    ipeds = f"{ipeds_num:06d}"

    out: dict[str, Any] = {
        "ipeds_id": ipeds,
        "scorecard_data_year": data_year,
    }
    for target, source in COLUMN_MAP.items():
        if isinstance(source, tuple):
            # Pick whichever of (public, private) is populated.
            pub, priv = source
            val = raw.get(pub)
            if val is None or (isinstance(val, float) and val != val) or str(val).strip() in {"", "NULL", "PrivacySuppressed"}:
                val = raw.get(priv)
        else:
            val = raw.get(source)
        out[target] = _coerce(val, target)

    for target, source in BOOL_MAP.items():
        out[target] = _coerce_bool(raw.get(source))

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Path to Most-Recent-Cohorts-Institution.csv")
    parser.add_argument("--data-year", required=True, help="Scorecard vintage, e.g. 2022-23")
    parser.add_argument("--apply", action="store_true", help="Write to Supabase (otherwise dry run)")
    parser.add_argument("--env", default=str(REPO_ROOT / ".env"), help=".env path")
    parser.add_argument("--batch-size", type=int, default=500, help="Upsert batch size")
    parser.add_argument("--only-cds", action="store_true",
                        help="Only load rows whose ipeds_id is referenced in cds_documents")
    args = parser.parse_args()

    try:
        import pandas as pd
    except ImportError:
        print("pandas not installed. pip install pandas", file=sys.stderr)
        return 1

    csv_path = Path(args.csv).expanduser()
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    print(f"Reading {csv_path} ...", file=sys.stderr)
    # Read everything as object (strings) so we control the coercion
    # path per column. pandas guesses wrong on columns with mixed
    # NULL/numeric values.
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    print(f"  {len(df):,} rows x {len(df.columns):,} cols", file=sys.stderr)

    # Schema-drift guard. If Scorecard renames a column between releases
    # (they do — the data dictionary is versioned), silent NULLs are the
    # worst outcome. Abort loudly with the missing columns listed so the
    # operator knows to update COLUMN_MAP before continuing.
    required_cols: set[str] = {"UNITID"}
    for src in COLUMN_MAP.values():
        if isinstance(src, tuple):
            required_cols.update(src)
        else:
            required_cols.add(src)
    required_cols.update(BOOL_MAP.values())
    missing = sorted(required_cols - set(df.columns))
    if missing:
        print(
            f"ERROR: Scorecard CSV is missing {len(missing)} columns that "
            "COLUMN_MAP / BOOL_MAP expect. This is usually a schema rename "
            "in a new Scorecard release. Update the map in refresh_summary.py "
            "and re-run. Missing: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    rows: list[dict[str, Any]] = []
    for raw in df.to_dict(orient="records"):
        row = build_row(raw, args.data_year)
        if row is not None:
            rows.append(row)
    print(f"Built {len(rows):,} summary rows.", file=sys.stderr)

    # Dedupe by ipeds_id. Scorecard's institution-level CSV is supposed
    # to be unique by UNITID, but a single duplicate would fail an entire
    # 500-row upsert batch with "ON CONFLICT DO UPDATE command cannot
    # affect row a second time". Last-write-wins is fine; record
    # dropped count so the operator can follow up if the number is
    # unexpectedly large.
    deduped: dict[str, dict[str, Any]] = {}
    for r in rows:
        deduped[r["ipeds_id"]] = r
    if len(deduped) != len(rows):
        print(
            f"Deduped {len(rows) - len(deduped):,} rows with duplicate UNITID "
            "(keeping last occurrence).",
            file=sys.stderr,
        )
    rows = list(deduped.values())

    if not args.apply:
        import json
        print("\n--- DRY RUN — sample row (first UNITID) ---", file=sys.stderr)
        print(json.dumps(rows[0] if rows else {}, indent=2, default=str))
        print(f"\nUse --apply to write {len(rows):,} rows to scorecard_summary.", file=sys.stderr)
        return 0

    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(args.env)
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb = create_client(url, key)

    if args.only_cds:
        # Shortlist to just the IPEDS IDs referenced by cds_documents.
        # Page through in chunks of 1000 with a stable .order() — without
        # an ORDER BY, PostgREST pagination can miss or duplicate rows
        # under concurrent writes to cds_documents.
        cds_ipeds: set[str] = set()
        offset = 0
        while True:
            resp = (
                sb.table("cds_documents")
                .select("ipeds_id")
                .not_.is_("ipeds_id", "null")
                .order("id")
                .range(offset, offset + 999)
                .execute()
            )
            batch = resp.data or []
            for r in batch:
                if r.get("ipeds_id"):
                    cds_ipeds.add(str(r["ipeds_id"]))
            if len(batch) < 1000:
                break
            offset += 1000
        before = len(rows)
        rows = [r for r in rows if r["ipeds_id"] in cds_ipeds]
        print(f"--only-cds: kept {len(rows):,}/{before:,} rows.", file=sys.stderr)

    # Upsert in batches. Supabase's Python client POSTs a single array per call.
    written = 0
    for i in range(0, len(rows), args.batch_size):
        chunk = rows[i : i + args.batch_size]
        sb.table("scorecard_summary").upsert(chunk, on_conflict="ipeds_id").execute()
        written += len(chunk)
        print(f"  wrote {written:,} / {len(rows):,}", file=sys.stderr)
    print(f"Done. {written:,} scorecard_summary rows upserted.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
