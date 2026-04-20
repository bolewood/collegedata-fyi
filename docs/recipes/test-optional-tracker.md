# Recipe: Test-optional tracker

**Who this is for:** students and parents deciding whether a school is a realistic test-optional option; counselors tracking policy whiplash year over year; reporters covering the post-COVID testing debate.

**What this reveals:** how many students actually submit SAT or ACT scores at each school, year by year — the single most honest signal of how "optional" a test-optional policy really is. Written policy alone does not tell you much: a school can publish "test-optional" on its admissions page while admitting 85% of its class from students who submitted scores. The Common Data Set forces schools to report the actual submission rate of enrolled first-years, which makes the policy measurable.

**CDS sections used:** C.901 (Percent Submitting SAT Scores), C.902 (Percent Submitting ACT Scores), C.801–C.8G (written policy disclosures, as a tiebreaker when submission numbers are ambiguous).

---

## The demo

See [`test-optional-tracker-demo.html`](../../web/public/recipes/test-optional-tracker-demo.html) for the interactive line chart. It shows SAT-submission percentage over time for seven schools pulled directly from the collegedata.fyi corpus: Yale (2009-10 → 2024-25), Caltech (2002-03 → 2020-21), MIT, Princeton, Stanford, Harvard, and Wake Forest. Hover over a point to see the underlying year, SAT submission rate, and (where reported) ACT submission rate. Dashed horizontal reference lines mark the thresholds we use to classify a school's effective policy.

The chart tells three stories that no single school's admissions page would:

1. **Test-optional adoption predates COVID.** Wake Forest's line hovers around 40-50% from 2014-15 onward, years before the pandemic. Yale drifted from 91% (2009-10) to 61% (2017-18) over nearly a decade. The 2020 wave made test-optional the default, but the slope was already visible.
2. **The 2020 inflection is dramatic for some, invisible for others.** Caltech snaps from ~80% to ~45% between 2019-20 and 2020-21 — the year it announced a full test-blind policy. Schools that were already drifting (Yale, Wake Forest) look continuous through that window because the policy change only formalized what was already happening.
3. **The post-COVID reversion is school-specific.** MIT climbs from 70% (2021-22) to 83% (2024-25) after reinstating its testing requirement for the class of 2027. Harvard reinstated testing for the class of 2029 but the 2024-25 CDS still shows only 54% — the reinstatement affects next year's data. Princeton and Stanford have held in the 45-60% range. Each school is its own data point.

## How to read it

We classify a school's *effective* policy each year using combined SAT + ACT submission (capped at 100%):

- **≥ 85% submission → effectively test-required.** Enough of the class submitted scores that not submitting is a meaningful disadvantage.
- **10–85% → genuinely test-optional.** A real fraction of admitted students got in without scores.
- **< 10% → effectively test-blind.** The score is ignored regardless of the written policy.

This is intentionally an *outcome* measure, not a policy measure. A school's written C.801–C.8G disclosure will tell you the declared policy. The submission rate tells you whether that policy is reality.

## How to populate this with all 700+ schools

The seed data in the demo is hand-verified for each of the seven charted schools. To reproduce the full-corpus picture, pull C.901 and C.902 across every year and school in the archive:

```bash
# 1) List every extracted manifest entry for the years you care about
curl 'https://api.collegedata.fyi/rest/v1/cds_manifest?canonical_year=in.(2018-19,2019-20,2020-21,2021-22,2022-23,2023-24,2024-25)&extraction_status=eq.extracted&select=school_id,school_name,canonical_year,document_id' \
  -H 'apikey: <anon key>' -H 'Authorization: Bearer <anon key>' \
  > manifest.json

# 2) For each document, pull the canonical artifact and read values.C.901 and values.C.902
curl 'https://api.collegedata.fyi/rest/v1/cds_artifacts?document_id=eq.<uuid>&kind=eq.canonical&select=notes' \
  -H 'apikey: <anon key>' -H 'Authorization: Bearer <anon key>'
```

The artifact's `notes.values["C.901"].value` is the SAT submission percentage, as a string (e.g. `"54"` means 54%). Divide by 100 if you need a ratio. `notes.values["C.902"].value` is the ACT equivalent.

If you want a single blob rather than per-document queries, the /api page at [collegedata.fyi/api](/api) has the full PostgREST auth and query reference, including how to use `in.(…)` to fetch many documents at once.

## Known caveats

1. **Older records are noisier.** Tier 4 (flattened-PDF) extraction has historically weaker coverage on pre-2018 docs. The Caltech 2010-11 value of 38% in the chart is a plausible extraction-noise outlier inside an otherwise stable ~99% baseline; when you see a single-year spike that contradicts a long-run pattern, cross-check the source PDF on that school's year page.
2. **SAT-only reporters vs ACT-only reporters.** A few schools only fill C.901 (SAT) or only C.902 (ACT) because their regional population is heavily one test or the other. When summing for the bucket classification, we cap the sum at 100% to avoid double-counting students who took both. Individual school lines in the chart show SAT only; the tooltip exposes ACT when reported.
3. **Two versions of "policy."** A school can be formally test-optional (C.801 = Yes, tests considered when submitted) but effectively test-required by submission rate. This is common among highly selective schools — the "test-optional" policy is real, but the accepted students disproportionately self-select for having strong scores. The two measures are complementary, not contradictory.
4. **The 2025-26 corpus is still filling in.** Many schools have not yet published their 2025-26 CDS at time of writing. Expect the 2025-26 points to be sparse until late in the cycle.

## What else to try

- Cross-reference with C.707 "Standardized test scores" basis-for-selection (Very Important / Important / Considered / Not Considered) to see which schools' written policy matches their submission rate.
- Plot *change* in submission percentage 2019-20 → 2024-25 as a single bar chart to see the reversion winners (MIT, Harvard direction-of-travel) vs. committed test-optional peers.
- Compare submission rate against median SAT score — do schools whose SAT median *rose* during test-optional years look like score-submitters self-selected?
- Pull C.801 written-policy text across years for one school to see the exact wording evolution.

## Attribution

Every trajectory in the demo is drawn directly from the collegedata.fyi public API; no number is estimated, interpolated, or summarized. Where a school has no CDS for a given year in our archive, the line is broken (gap), not smoothed. Yale's 2009-10 → 2024-25 continuous series is the richest ground-truth arc in the current corpus.
