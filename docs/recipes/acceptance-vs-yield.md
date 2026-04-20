# Recipe: Acceptance rate vs yield

**Who this is for:** students and parents building a target list; counselors who want to calibrate reach/match/safety; anyone curious which schools are truly selective vs. just hard to get into.

**What this reveals:** the gap between how selective a school *looks* on paper (acceptance rate) and how selective it actually *is* in practice (yield, the share of admitted students who actually enroll). A school can have a 6% acceptance rate and still lose most of its admits to cross-admit peers. A school can have a 20% acceptance rate and capture nearly everyone it admits. Both facts matter for understanding the admissions market, and neither is visible from acceptance rate alone.

**CDS sections used:** C1 (applications, admissions, enrollment), B1 (full-time undergraduate enrollment), B22 (retention rate, as a secondary context signal).

---

## The demo

See [`acceptance-vs-yield-demo.html`](../../web/public/recipes/acceptance-vs-yield-demo.html) for the interactive scatter plot. It currently shows three schools seeded from the ground-truth fixtures in the repo: Harvard (2024-25), Dartmouth (2024-25), and Harvey Mudd (2025-26). The points are arranged with acceptance rate on the x-axis and yield on the y-axis, sized by full-time undergraduate enrollment. Hover over a dot for the underlying numbers.

Three points isn't enough to see the pattern across the whole admissions market. The XLSX starter ([`acceptance-vs-yield-starter.xlsx`](../../web/public/recipes/acceptance-vs-yield-starter.xlsx)) is designed to be populated from the public API; instructions are below.

## How to read it

The plot divides roughly into four quadrants:

- **Top-left — selective and desired.** Low acceptance, high yield. Harvard sits here: 3.65% accept rate and 83.60% yield. Schools in this quadrant are both hard to get into and hard to turn down, usually because their market position is strong enough that most admits don't have meaningfully better options.
- **Top-right — loved despite openness.** Higher acceptance but strong yield. Often state flagships, religious-fit schools, or institutions with strong regional pull. Admits know what they're getting and most of them come.
- **Bottom-left — selective but second-choice.** Hard to get into, but most admits choose somewhere else. Often cross-admit peers of top-left schools — they admit strong students who would also get into the Harvards of the world, and lose the cross-admit battle. Dartmouth at 5.40% / 69.12% is edge-of-this-quadrant; it wins a solid majority of its admits but loses some to HYPS peers.
- **Bottom-right — accessible and optional.** Admits freely, captures a smaller share. Common safety-school territory. Harvey Mudd at 12.30% / 36.51% is here — a top-tier STEM liberal arts college with a specific fit, so its admits often accept offers from MIT, Caltech, Stanford instead.

## How to populate this with all 700+ schools

The XLSX ships with three ground-truth rows pre-filled and formulas wired for acceptance rate, yield, and total UG. Add rows by pulling data from the API. The API-Queries tab in the XLSX has copy-pasteable examples; the two most useful for this recipe:

```bash
# 1) Get the list of schools with a 2024-25 CDS document
curl 'https://api.collegedata.fyi/rest/v1/cds_manifest?canonical_year=eq.2024-25&select=school_id,school_name,ipeds_id' \
  > schools-2024-25.json

# 2) Pull the C1 and B1 fields we need, for all those schools
curl 'https://api.collegedata.fyi/rest/v1/cds_fields?canonical_year=eq.2024-25&field_id=in.(c1_total_applied,c1_total_admitted,c1_total_enrolled,b1_ft_total_ug_men,b1_ft_total_ug_women,b22_retention_pct)' \
  > fields-2024-25.json
```

The Field Reference tab in the XLSX documents exactly which field IDs to pull. Join on `school_id` and paste the values into the spreadsheet; the formulas compute acceptance rate, yield, and total UG automatically.

## Known caveats

Corpus-wide coverage on C1 is currently 50-60% for Tier 4 flattened PDFs (see [`docs/extraction-quality.md`](../extraction-quality.md) for the per-section breakdown). That means this recipe produces a clean scatter plot for the ~400-500 schools whose C1 extraction is complete, and leaves gaps for the rest. Tier 1 (XLSX) and Tier 2 (fillable PDF) schools have near-100% C1 coverage; Tier 4 schools are hit-or-miss until the cleaner or an LLM fallback reaches those cells. Flag any school with suspiciously round or missing numbers and check the source PDF.

A few things to keep in mind when interpreting:

1. **C1 "total" vs. residency splits.** Some schools publish their C1 totals only by residency (in-state/out-of-state/international) rather than as a single total row. The field `c1_total_applied` should be the sum; verify against the source PDF if a school's number looks off.
2. **Gender-split vs total sums.** `c1_total_applied` is the schema's top-level, but some schools only fill gender splits. The formulas in the XLSX expect `c1_total_*` — if your school only has gender-split rows, sum them first.
3. **CDS year alignment.** Most schools are on a 2024-25 cycle in the current corpus; a few (Harvey Mudd is an example) are on 2025-26. Pick one year when comparing.
4. **Yield is sensitive to waitlist timing.** Some schools admit heavily from the waitlist after the initial round. Their C1 C2 (wait-list) section adds detail, but the yield number in C1 is the final post-waitlist figure.

## What else to try

Once you have the data in the sheet, some natural follow-ups:

- Plot acceptance rate vs. retention (B22) instead of yield, to see academic stickiness separately from admissions desirability.
- Add SAT 50th percentile (C9) as dot color to layer in selectivity-by-test-score.
- Compare the same school year-over-year to see whether it's getting more or less selective. The API supports `canonical_year=in.(2022-23,2023-24,2024-25)` for trend analysis.
- Cross-reference with IPEDS Carnegie classification to filter by peer set (R1 universities, liberal arts colleges, regional comprehensives).

## Attribution

All three seed data points come from hand-verified ground-truth fixtures in [`tools/extraction-validator/ground_truth/`](../../tools/extraction-validator/ground_truth/). Numbers are transcribed directly from source PDFs on the dates noted in each fixture, and the scorers in [`tools/extraction-validator/`](../../tools/extraction-validator/) ensure extraction output matches these ground-truth values to within the reported accuracy.
