# Alignment gap

**Question:** How does graduate debt burden compare with non-need merit aid
and with an institution's financial resources when College Scorecard, CDS
H2A, and IPEDS are joined?

Open [`/recipes/alignment-gap`](https://www.collegedata.fyi/recipes/alignment-gap)
for two interactive scatters. Panel A plots the alignment gap (Scorecard)
against estimated non-need merit aid per first-year student (CDS H2A),
colored by endowment per undergraduate (IPEDS). Schools that award no
non-need merit aid sit on a dedicated `$0` rail, off the log scale. Panel B
keeps a broader endowment comparison so schools without a usable H2A row —
including Bard and Grinnell — stay on the page. Both panels measure the gap
against the same 375-school median burden. Hover any dot for the school name.

## What the recipe computes

Debt **burden** is annual federal loan service as a share of median 10-year
earnings:

```text
burden = median_debt_monthly_payment × 12 / earnings_10yr_median
```

The **alignment gap** estimates how much lower median completer debt would
need to be for the school to reach the 375-school median burden at its
existing earnings, expressed per year of enrollment:

```text
gap = median_debt_completers × (1 − median_burden / burden) / 4
```

**Merit aid per first-year student** is the H2A non-need share times the
average non-need grant:

```text
merit_per_fy = non_need_aid_share_first_year_ft × avg_non_need_grant_first_year_ft
```

The diagonal on Panel A is `merit_per_fy = gap`. A published `$0` grant is
kept and plotted on the left rail. The merit sample's own median burden is
disclosed in the methodology so a school that appears in both figures is not
two numbers.

## Join

Panel A starts from `school_merit_profile` (already a CDS H2A × Scorecard
view), then attaches `scorecard_summary.endowment_end` and
`school_browser_rows.undergrad_enrollment_scorecard`. Guards, required:

1. Drop `non_need_aid_share_first_year_ft` outside `[0, 1]`.
2. Drop `avg_non_need_grant_first_year_ft` outside `[0, 80000]`. A published
   `$0` grant is kept.
3. Require `merit_profile_quality` in `strong` or `partial`.
4. Require Scorecard earnings, debt, net price, and endowment.

`merit_profile_quality` is a field-count flag. It does not catch range errors.
The 2026-08-29 build dropped three shares outside 0–100% (Cal State Chico at
12,087%, Dickinson at 104.5%, Illinois Chicago at 153%) and one average grant
above $80,000 (Duke at $85,600) even though all four were flagged `strong`.

Panel B is the endowment recipe: Scorecard 2022-23 debt, earnings, net price,
endowment, and instructional expenditure, joined to directory undergraduate
enrollment (`institution_directory.undergraduate_enrollment`, Scorecard
`enrollment` as fallback) and a 2024-25 or 2025-26 SAT composite midpoint
(C9). Panel A is smaller because it requires usable H2A, not because Panel B
is a superset of it.

The Panel B `scorecard_summary` query matches 2,158 rows. PostgREST
`max-rows` is 1,000: `limit=5000` and `Range: 0-4999` both return HTTP 206
with `Content-Range: 0-999/2158` and no error body. Page with
`limit=1000&offset=0`, then `offset=1000`, then `offset=2000` (or `Range:
0-999`, `1000-1999`, `2000-2999`) until a page is short.

Rebuild:

```bash
python3 tools/scorecard/build_alignment_gap_recipe.py
```

## How to read the panels

- **Merit aid is larger than the gap** — positive gap, merit spend ≥ gap.
- **Merit aid is smaller than the gap** — positive gap, merit spend below it.
  Includes schools that award $0 merit aid and still have a gap.
- **Debt burden is at or below the median** — no positive alignment gap under
  this definition.
- Panel B quadrants split the same gap against endowment per undergraduate:
  higher/lower debt burden × higher/lower endowment. “High endowment” on both
  panels means at or above the 375-school median.

CDS H2A covers first-year full-time students and specifically reports
non-need aid. Some awards that combine need and merit may not appear. Scorecard
earnings cover federally aided students and describe a cohort that enrolled
about a decade before the CDS row. The join is institutional, not longitudinal.
The gap is a comparison measure, not a recommended tuition price.
