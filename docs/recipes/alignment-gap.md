# Alignment gap

**Question:** For schools we can join across CDS SAT scores, College Scorecard
earnings and debt, net price, and endowment, how far is each school's graduate
debt burden from the corpus median — and does the school have the endowment to
close that gap?

Open [`/recipes/alignment-gap`](https://www.collegedata.fyi/recipes/alignment-gap)
for the interactive scatter. Hover any dot for the school name, the gap,
endowment per undergraduate, and instruction as a share of net price. A handful
of schools are labeled on the chart; every school is named on hover or via Find
a school.

## What the recipe computes

Debt **burden** is annual federal loan service as a share of median 10-year
earnings:

```text
burden = median_debt_monthly_payment × 12 / earnings_10yr_median
```

The **alignment gap** is the completer debt that would have to be shed to reach
this corpus's median burden at that school's own earnings, divided across four
years of college so it reads as dollars per year of net price:

```text
gap = median_debt_completers × (1 − median_burden / burden) / 4
```

A positive gap means graduates carry a heavier burden than the median. The
horizontal axis is endowment per undergraduate (`endowment_end / undergraduate_enrollment`),
log scale. Color is instructional expenditure per FTE divided by average net
price. Shares above 100% mean the school spends more on instruction than it
collects from students.

## Join

- College Scorecard 2022-23: earnings, monthly payment, completer debt, average
  net price, endowment, instructional expenditure per FTE
- `institution_directory`: undergraduate enrollment and canonical `school_id`
- Latest 2024-25 or 2025-26 `school_browser_rows` row with a SAT composite
  midpoint (C9). Schools without a published SAT midpoint are out of this
  universe on purpose.

Rebuild:

```bash
python3 tools/scorecard/build_alignment_gap_recipe.py
```

## How to read the quadrants

- **Capacity exists** — burden and endowment both above the median.
- **Constrained** — burden above the median, endowment below it.
- **Endowment absorbs it** — low burden next to large per-student wealth.
- **Earnings do the work** — low burden without unusual wealth.

Scorecard earnings cover federally aided students and describe a cohort that
enrolled about a decade before the CDS SAT row. The join is institutional, not
longitudinal. Median federal debt piles against the borrowing cap, so debt
measures burden, not sticker price.
