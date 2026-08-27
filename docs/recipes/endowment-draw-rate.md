# Recipe: Endowment draw-rate tracker

**Who this is for:** IR, college-finance reporters, trustees. IPEDS F2 Part H estimate.

**Source:** NCES IPEDS Finance form F2, Part H. The interactive recipe is an independent estimate
from public federal data; it is not a reproduction of audited-financial-statement analysis.

Open [`/recipes/endowment-draw-rate`](https://www.collegedata.fyi/recipes/endowment-draw-rate) for
the fiscal-year distribution and school picker.

## What the recipe computes

IPEDS Part H reports beginning and ending endowment net assets and four components of the annual
change: new gifts, investment return, spending distribution for current use, and other changes.
Component detail begins in fiscal year 2020, so that is the honest floor for this analysis.

For each historically private not-for-profit F2 reporter-year, the generator requires:

1. all six Part H values to be present and reported rather than imputed;
2. a positive beginning-of-year endowment value; and
3. the reported accounting identity to balance exactly:

```text
F2H02 - F2H01 = F2H03A + F2H03B + F2H03C + F2H03D
```

The draw rate is then:

```text
draw rate = abs(F2H03C) / F2H01
```

The absolute value is intentional. FY2020 and FY2021 mix positive and negative conventions for
the spending line. Raw federal values remain unchanged in `ipeds_facts`; normalization happens
only in this derived artifact. Rows that fail a gate remain in the school history with an
exclusion reason and `drawRate: null`, but do not enter percentiles or threshold shares.

## Current generated result

Dataset version: `ipeds-endowment-283292ca75a4abda`, generated August 10, 2026.

| Fiscal year | Eligible / reporters | Median | Above 5% | Above 7% | Above 15% | Release |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| FY2020 | 1,335 / 1,336 | 4.0% | 25.5% | 9.9% | 2.8% | final |
| FY2021 | 1,331 / 1,333 | 4.1% | 28.6% | 9.7% | 2.5% | final |
| FY2022 | 1,316 / 1,317 | 3.5% | 16.9% | 7.0% | 1.3% | final |
| FY2023 | 1,303 / 1,304 | 4.3% | 32.8% | 13.7% | 4.0% | final |
| FY2024 | 1,287 / 1,290 | 4.4% | 34.3% | 16.4% | 4.6% | provisional |

“Above” means strictly greater than the threshold. Small endowments are not removed: they are a
substantively important population, but the school view adds a volatility note below $5 million.

## Bucket membership lists

Each threshold cell in the interactive table opens the complete list of schools in that
fiscal-year bucket, sorted from the highest reported draw rate to the lowest. A school enters a
list only when its school-year point has a non-null draw rate and no exclusion reason, and its
rate is strictly greater than the threshold. The buckets are cumulative: a school above 15% also
appears in the above-7% and above-5% lists for the same year.

The lists retain schools without a current directory page as unlinked archive entries. They also
mark school-years with a beginning value below $5 million because a single transfer can move a
small denominator by whole percentage points. The neutral disclaimer appears above the table and
inside every open list because the ratio cannot identify why reported spending occurred or, by
itself, establish fiscal irresponsibility. It also keeps the legal comparison qualified: some
states' UPMIFA statutes presume imprudence only above a 7% rate measured against a multi-year
average value, which differs from the single-year rate shown here.

## How to reproduce it

The checked-in generator makes bounded, paginated public PostgREST requests one field at a time,
which avoids the timeout risk of asking Postgres to sort the entire finance subset in one call:

```bash
python3 -m tools.ipeds.build_endowment_draw_rate_recipe \
  --min-year 2020 \
  --max-year 2024 \
  --generated-at 2026-08-03
```

It reads `SUPABASE_URL` and `SUPABASE_ANON_KEY` (or
`NEXT_PUBLIC_SUPABASE_ANON_KEY`) from the environment and writes
`web/src/lib/endowment-draw-rate-recipe-data.ts`. The output includes source release IDs and
SHA-256 metadata fingerprints; its dataset version is a hash of the derived rows, summaries, and
source-release records.

The underlying finance query shape is:

```bash
curl 'https://api.collegedata.fyi/rest/v1/ipeds_facts?field_key=eq.endowment_spending_distribution&data_year=gte.2020&and=(data_year.lte.2024,source_table.like.F*_F2)&public_visible=eq.true&select=release_id,ipeds_id,data_year,field_key,value_numeric,quality_flag,release_type,source_table,source_variable&order=ipeds_id.asc,data_year.asc,release_id.asc' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'
```

Repeat that request for `endowment_value_begin`, `endowment_value_end`,
`endowment_new_gifts`, `endowment_investment_return`, and `endowment_other_change`. Join historical
`institution_name`, `control`, and `state` facts on `(ipeds_id, data_year)`; keep `control = 2`.
The generator source contains the exact pagination, validation, quantile, and rendering logic.

## Why this differs from the WSJ/Perspective analysis

The August 2, 2026 Wall Street Journal report says roughly 200 private colleges are borrowing from
restricted endowments and that the share drawing faster than 7% nearly doubled from 2016 to 2025.
Perspective Data Science built that work from audited financial statements. This IPEDS artifact
instead estimates a related spending ratio for 1,287 eligible FY2024 reporters, of which 211
(16.4%) were above 7%.

Those numbers are not equivalent:

- IPEDS `F2H03C` does not distinguish donor-restricted endowment from board-designated
  quasi-endowment and cannot identify restricted-fund borrowing.
- This population, source, and accounting treatment differ from an audited-statement dataset.
- IPEDS has no spending-distribution variable before FY2020, so the WSJ&apos;s FY2016 starting point
  cannot be reconstructed.
- FY2025 IPEDS Finance data is not yet published; FY2024 is currently provisional.

The recipe therefore presents the federal result on its own terms and does not use divergence
from the published analysis as a pass/fail test.

## Interpretation and caveats

Typical endowment payout policies often target roughly 4–5%. Some states&apos; UPMIFA statutes include
a presumption above 7%, but that optional provision is adopted only in a minority of states and
uses a multi-year average value. This recipe uses one year&apos;s beginning value. Crossing 7% here
does not establish a UPMIFA violation, donor-intent problem, financial distress, or misconduct.

The generated artifact contains 6,580 school-year rows across 1,357 historical institutions.
There are 263 institutions without a current public school page. Raw IPEDS history can retain
reporters that later closed or left the current directory, so the recipe intentionally includes
them and labels their histories “historical/raw API only” instead of inventing a current page.

When NCES replaces FY2024 provisional Finance data with a final release, regenerate this artifact,
review the changed dataset hash and sector summaries, and note the new version here. Never silently
overwrite the published figures.
