# PRD 012: Browser field expansion after Tier 4 v0.3

**Status:** Backend implemented - frontend filters deferred
**Created:** 2026-04-28
**Author:** Codex + Anthony
**Related:** [PRD 010](010-queryable-data-browser.md), [PRD 011](011-academic-profile-llm-repair.md), [PRD 0111A](0111A-docling-improvement-spike.md), [Extraction Quality](../extraction-quality.md), [Queryable Browser Backend](../queryable-browser-backend.md)

---

## Implementation Update - 2026-04-28

Phase 0 findings were generated in
[`docs/plans/prd-012-phase-0-findings.md`](../plans/prd-012-phase-0-findings.md).
The backend implementation promotes SAT/ACT submission-rate and percentile fields
to nullable, range-checked `school_browser_rows` columns and extends the
`browser-search` contract. GPA and class-rank remain long-form `cds_fields` data
only.

The public `/browse` frontend does not add score filters yet. The backend reports
submit-rate companion metadata for active score filters so a future UI can avoid
presenting score percentiles without denominator context.

Known caveat: the Phase 0 report found XLSX C9 parse errors that look like
schema/template mapping drift. The projection validator prevents invalid score
values from reaching browser columns, and the XLSX mapping audit is tracked in
[`docs/backlog.md`](../backlog.md).

## Context

PRD 010 deliberately kept `school_browser_rows` small. The first browser launch
used only a handful of launch-certified fields:

- applied
- admitted
- first-year enrolled
- acceptance rate
- yield rate
- Scorecard undergraduate enrollment
- Scorecard retention
- Scorecard net price
- Scorecard Pell share

SAT, ACT, GPA, and class-rank fields were explicitly held back as v1.1 candidates
until `2024-25+` answerability improved enough for the public browser to avoid
looking more precise than the extraction quality supported.

Tier 4 v0.3 materially improved overall flattened-PDF coverage. The deterministic
layout-overlay drain completed on 2026-04-28 with:

| Metric | Value |
|---|---:|
| Tier 4 v0.3 successful extracts | 3,337 |
| Tier 4 v0.3 extractor errors | 30 |
| Total extracted fields logged | 941,313 |
| Mean fields per successful Tier 4 PDF | 282.1 |
| Median fields per successful Tier 4 PDF | 212 |
| Max fields in one Tier 4 PDF | 768 |
| Tier 4 PDFs with 500+ fields | 538 |
| Pending Tier 4 PDFs after drain | 0 |

Those numbers justify re-measuring the browser candidate fields. They do **not** by
themselves justify promoting SAT, ACT, GPA, or class-rank fields. Aggregate field
count does not imply C.9xx/C.10xx/C.12xx section coverage. A document can recover
282 fields and still miss every academic-profile field. PRD 012 therefore starts
with a measurement gate, not a schema migration.

## Thesis

The next browser iteration should expand only if the refreshed `cds_fields`
projection proves that the candidate academic-profile fields are answerable in the
current data.

The project should **not** expose all 1,105 CDS fields as browser columns. That is
what `cds_fields` is for. `school_browser_rows` should remain a curated, documented
serving contract for fields that are:

1. user-meaningful in a school search workflow
2. directly backed by stable CDS fields or explicitly documented derived metrics
3. normalized consistently across producers
4. answerable often enough to support filtering without surprising empty results
5. honest about missingness, test-optional behavior, source provenance, and
   submission-rate bias

## Required Pre-Implementation Work

This PRD is not approved for implementation until this section is complete and the
results are written back into this PRD or a linked findings note.

### 1. Refresh the field substrate without expanding columns

Run the projection rebuild unchanged so the long-form `cds_fields` substrate reflects
the v0.3 drain:

```bash
python tools/browser_backend/project_browser_data.py --full-rebuild --apply
```

Before doing that refresh, resolve the stale Tier 4 fallback overlay policy. The
v0.3 extractor is verified in code as `tier4_docling` `producer_version = "0.3.0"`
([`tools/extraction_worker/tier4_extractor.py`](../../tools/extraction_worker/tier4_extractor.py)).

- either skip `tier4_llm_fallback` overlays when the base artifact is
  `tier4_docling` `0.3.0`
- or require fallback artifacts to match the base artifact/version/hash
- or delete and re-run fallback artifacts against v0.3 base artifacts

Old fallback artifacts were produced against older markdown/config outputs. Mixing
them into v0.3 base values would create rows whose deterministic and fallback values
refer to different source serializations.

### 2. Confirm schema-version semantics

The current Tier 4 extractor writes values keyed into the repo's canonical schema
contract, which is currently the 2025-26 schema for the full field set. PRD 012 must
not silently assume that `C.901`, `C.916`, or `C.1201` mean the same thing for
2024-25 documents unless that mapping is verified.

Acceptable paths:

- scope the first browser expansion to `year_start >= 2025`
- or produce a 2024-25 to 2025-26 academic-profile mapping note
- or spot-check a sample of 2024-25 source PDFs for every promoted field family

Until this is done, all candidate field tables below are field IDs in the 2025-26
canonical schema contract, not a blanket cross-year promise.

### 3. Measure section-specific answerability

Run an answerability report for each candidate field ID over the refreshed
projection.

Minimum report dimensions:

- overall `2024-25+` primary rows
- `2025-26+` primary rows
- primary rows only (`sub_institutional IS NULL`) as the main denominator
- sub-institutional rows as a separate reported dimension
- latest-per-school rows
- latest-in-window-with-field-populated rows
- source format (`xlsx`, `pdf_fillable`, `pdf_flat`, `pdf_scanned`, `html`)
- producer (`tier1_xlsx`, `tier2_acroform`, `tier4_docling`, `tier6_html`)
- data-quality flag bucket
- parse-error count
- plausible-range violation count
- count of documents with extraction errors or no selected result
- count of rows with reported SAT/ACT percentile but null submit rate, by producer
- pre-v0.3 vs v0.3 Tier 4 delta for the candidate field families, where possible

The denominator must be explicit. For launch-readiness, exclude rows with any
`data_quality_flag` from the primary answerability denominator, but report those
excluded counts separately. Blank templates and low-coverage/wrong-file rows should
not quietly depress or inflate field-quality claims.

Documents without a selected extraction result are absent from `school_browser_rows`
today. For answerability, report them separately as "no selected result" rather than
including them as all-null browser rows. This keeps the serving table clean while
making the corpus denominator explicit. The 30 v0.3 extractor errors are extractor
dead-letter cases, not zero-field successes, and should be counted in that separate
bucket.

Academic-profile latest-row semantics must also be measured before implementation.
For each candidate field, compute answerability under both:

1. latest year in the allowed window
2. latest year in the allowed window where the field is populated

The decision memo must choose one semantics before any migration or UI work. If the
browser uses latest-with-field semantics, result rows must display the source CDS
year for that field so the UI does not silently mix cohorts.

### 4. Compare v0.3 against prior Tier 4 artifacts

PRD 010's selected-result logic prefers deterministic producer families in this
order:

1. `tier1_xlsx`
2. `tier2_acroform`
3. `tier6_html`
4. `tier4_docling`

This ordering is implemented in both the database helper view
`cds_selected_extraction_result` (migration
`20260426120000_queryable_browser_backend.sql`) and the Python projection worker's
`BASE_PRODUCER_RANK`.

So v0.3 Tier 4 does **not** replace Tier 1/Tier 2 just by being newer in the browser
projection. However, within the `tier4_docling` family, the newest artifact wins.
Before promoting new browser columns, produce a v0.2 -> v0.3 comparison for the
candidate field families and explicitly inspect regressions.

## Candidate Fields

These are candidates, not pre-approved migration columns. The migration must be
shrunk or expanded based on the measurement report.

### Candidate: SAT/ACT submission and percentile fields

| Metric | Field | Meaning | Storage |
|---|---|---|---|
| `sat_submit_rate` | `C.901` | Percent submitting SAT scores | fractional `0..1` |
| `act_submit_rate` | `C.902` | Percent submitting ACT scores | fractional `0..1` |
| `sat_composite_p25` | `C.905` | SAT Composite 25th percentile | integer |
| `sat_composite_p50` | `C.906` | SAT Composite 50th percentile | integer |
| `sat_composite_p75` | `C.907` | SAT Composite 75th percentile | integer |
| `sat_ebrw_p25` | `C.908` | SAT EBRW 25th percentile | integer |
| `sat_ebrw_p50` | `C.909` | SAT EBRW 50th percentile | integer |
| `sat_ebrw_p75` | `C.910` | SAT EBRW 75th percentile | integer |
| `sat_math_p25` | `C.911` | SAT Math 25th percentile | integer |
| `sat_math_p50` | `C.912` | SAT Math 50th percentile | integer |
| `sat_math_p75` | `C.913` | SAT Math 75th percentile | integer |
| `act_composite_p25` | `C.914` | ACT Composite 25th percentile | integer |
| `act_composite_p50` | `C.915` | ACT Composite 50th percentile | integer |
| `act_composite_p75` | `C.916` | ACT Composite 75th percentile | integer |

SAT/ACT percentiles should never be presented as pure selectivity measures. In the
test-optional era, they describe score submitters. A school with a 15% submit rate
can report very high percentiles for a highly self-selected subset of students.

Promotion rule:

- SAT/ACT percentile display must always pair the percentile with submit rate when
  submit rate is available.
- Percentile filters must either include a submit-rate threshold in the same UI
  control or show an explicit low-submission warning.
- The default submit-rate guard must be chosen empirically from the Phase 0
  submit-rate distribution; do not hard-code `0.50` before measurement.
- If the empirical distribution suggests any binary guard would hide too many
  highly selective test-optional schools, prefer a default-visible low-submission
  badge over default exclusion.
- If submit rate is missing, percentile values may display with a "submit rate
  unknown" badge but should not power default score filters.

### Candidate: class rank

| Metric | Field | Meaning | Storage |
|---|---|---|---|
| `top_tenth_pct` | `C.1001` | Percent in top tenth of high-school class | fractional `0..1` |
| `top_quarter_pct` | `C.1002` | Percent in top quarter | fractional `0..1` |
| `top_half_pct` | `C.1003` | Percent in top half | fractional `0..1` |
| `class_rank_submit_rate` | `C.1006` | Percent submitting class rank | fractional `0..1` |

Class-rank fields are not approved for first promotion. Blank or low class-rank
values can mean several different things: no value published, parser miss, applicant
high schools do not rank, or an explicit school policy. `class_rank_submit_rate`
helps but does not fully solve the interpretation problem; a highly selective school
can look weak on top-tenth share if only a small fraction of admits come from ranking
high schools. These fields should stay in `cds_fields` and school-detail surfaces
until a UI can communicate the denominator clearly.

### Candidate: average high-school GPA

| Metric | Field | Meaning | Storage |
|---|---|---|---|
| `avg_hs_gpa` | `C.1201` | Average high-school GPA of students submitting GPA | decimal |
| `hs_gpa_submit_rate` | `C.1202` | Percent submitting high-school GPA | fractional `0..1` |

GPA is **not** approved for first promotion yet. Although the CDS asks for GPA on a
4.0 scale, schools can report weighted, nonstandard, or otherwise ambiguous GPA
values. A permissive range check such as `0..4.5` would hide scale problems rather
than solve them.

GPA can be promoted only if one of these is true:

- the source explicitly states a 4.0 scale and the extractor captures that evidence
- values above 4.0 are treated as `unknown_scale` or excluded from browser filtering
- the UI displays GPA as an unnormalized reported value and does not allow
  cross-school GPA filtering

Under the third path, GPA should **not** enter `school_browser_rows`. It can appear
in `cds_fields` and school-detail UI as a reported source value, but the curated
browser row model should reserve first-class columns for fields that can support
responsible filtering or sorting.

### Keep in `cds_fields` only for now

The following fields should remain queryable through `cds_fields` but should not be
first-class browser columns yet:

- SAT distribution buckets (`C.932`-`C.952`)
- ACT distribution buckets (`C.953`-`C.987`)
- GPA distribution buckets (`C.1101`-`C.1130`)
- ACT Math/English/Writing/Science/Reading percentiles unless a user workflow
  specifically needs them

They add a lot of width and interpretation burden to the browser. The direct field
substrate can support analysts who need them without turning the public browser into
a 100-column spreadsheet.

## Promotion Gates

Promotion thresholds are intentionally provisional. The point is to prevent a field
from becoming a public filter just because it is easy to add.

| Promotion level | Minimum bar |
|---|---|
| Add to `cds_metric_aliases` / `cds_fields` alias | direct field exists in current schema, schema-version semantics are documented, parses deterministically |
| Add to `school_browser_rows` | meaningful reported count in scoped primary rows, no systemic range failures, and acceptable source-format coverage |
| Add as visible table column / CSV export | at least 25% reported among scoped primary rows and field-specific caveats can be displayed clearly |
| Add as default filter control | at least 40% reported among scoped primary rows, at least 15% among `pdf_flat`, and filter semantics do not mostly measure missingness |

Rationale:

- 25% display/export means a user will see values often enough for the column to
  be useful without implying universal coverage.
- 40% filter means the filter has enough answerability to discriminate schools
  rather than mostly filter on missing data.
- the `pdf_flat` floor prevents XLSX/fillable publishers from carrying a metric
  that remains unusable for the dominant source format.

Parse-error rate must be below 2% of reported-looking values. A metric needs at
least 50 stratified spot checks before it is called launch-certified, including at
least 30 `pdf_flat` Tier 4 examples because that is the dominant source format. The
spot check should report precision/recall for the candidate field family, not just
examples that look right.

## Data Semantics

### Percent and rate values

All percent/rate columns must store fractional values in `0..1`, matching PRD 010.

Examples:

- source `58%` -> `0.58`
- source `58` in a CDS percent field -> `0.58`
- source `0.58` -> `0.58`

### Score and GPA numeric values

If score fields are promoted:

- SAT composite: integer, plausible range `400..1600`
- SAT sections: integer, plausible range `200..800`
- ACT composite: integer, plausible range `1..36`
- non-integer SAT/ACT values should round to nearest integer only if the source is
  visibly a decimal rendering artifact such as `1450.0`; otherwise reject as a parse
  error for the serving column

If GPA fields are later promoted:

- GPA should use `numeric(3,2)` if it is constrained to a 4.0-ish scale
- values above 4.0 must not silently pass as comparable cross-school GPAs
- `hs_gpa_submit_rate` should display beside GPA wherever GPA appears

### Missingness and blank filters

The current projection supports `reported`, `missing`, `not_applicable`, and
`parse_error`. Academic-profile UI copy should avoid implying that blank SAT/ACT/GPA
fields always mean "school does not use this."

For browser filters:

- `is blank` means value is null, regardless of reason
- `is missing` should be reserved for missing extraction/source values if richer
  status values are added later
- `is not reported` should include not-applicable/not-used style statuses if those
  statuses are added later
- submit-rate guards apply only to numeric comparison filters on percentile fields
  (`=`, `!=`, `>`, `>=`, `<`, `<=`), not to `is blank` / `is not blank`

Until richer statuses exist, answerability metadata must report null counts and
parse-error counts explicitly.

### Composite caveat

Some schools report SAT EBRW/Math but not SAT Composite. PRD 012 should not silently
derive SAT composite from components. If a composite filter is added, the UX must
state that it applies to schools reporting SAT Composite and that section-only
reporters are excluded.

A future derived metric such as `sat_component_sum_p50_v1` can be considered, but it
must live in the derived serving layer, not `cds_metric_aliases`.

## Implementation Plan

### Phase 0: Measurement and decision memo

1. Resolve fallback overlay semantics.
2. Refresh the projection unchanged.
3. Run the answerability report.
4. Produce a decision memo with:
   - promoted fields
   - omitted fields and reasons
   - source-format/producers breakdown
   - 2024-25 schema compatibility decision
   - v0.3 regression review
   - UI caveats required for each promoted field

Save raw report data under `.context/prd-012-answerability/` and write the decision
memo to `docs/plans/prd-012-phase-0-findings.md`. No schema migration should be
written until this memo exists.

### Phase 1: Conditional schema migration

Add only the columns that clear Phase 0.

Column type guidance:

- rates: `numeric(4,3)` or `numeric(5,4)`, with explicit `0..1` checks
- SAT/ACT scores: integer with plausible-range checks
- GPA: hold out unless scale semantics are solved; if solved, `numeric(3,2)` with
  explicit scale policy

Do not add single-column indexes preemptively. `school_browser_rows` is small enough
that indexes should be added only after a measured slow query or after moving ranking
into SQL shows a concrete need.

### Phase 2: Projection worker

1. Extend `DIRECT_METRIC_ALIASES` only for promoted direct fields.
2. Keep derived metrics out of `cds_metric_aliases`.
3. Extend `build_browser_row()` to populate the promoted columns.
4. Preserve fractional percent normalization for submit rates.
5. Treat aliases as additive public API surface; consumers should be able to ignore
   unknown alias keys.
6. Add tests for:
   - promoted aliases are direct fields
   - derived metrics are still excluded from aliases
   - submit rates are fractional
   - invalid SAT/ACT/GPA values do not write misleading browser values
   - non-artifact decimal score values such as `1450.5` produce `parse_error` in
     `cds_fields` and a null serving column
   - `sub_institutional` is preserved

### Phase 3: API/search contract

Extend `browser-search` only for promoted columns.

Requirements:

- include answerability metadata for any active academic-profile filters
- keep the PRD 010 latest-per-school required-field semantics
- make section-only/composite-only SAT behavior explicit in answerability metadata
- make `is blank` semantics explicit in tests

For sparse academic-profile fields, evaluate whether "latest year in window with
field populated" is a better default than "latest year in window." Do not silently
drop schools with rich prior-year academic-profile data if the current-year document
omits the field without surfacing that fact.

This evaluation is not optional for Phase 3; it must use the Phase 0 report and pick
one behavior before `browser-search` changes land.

### Phase 4: Frontend

Add an "Academic profile" section to `/browse` only after Phase 0 confirms enough
answerability.

Possible first UI controls if they clear the gate:

- SAT Composite 50th percentile min/max, paired with SAT submit-rate guard
- ACT Composite 50th percentile min/max, paired with ACT submit-rate guard
- "has SAT profile" / "has ACT profile" toggles

GPA should not be a cross-school filter until scale semantics are solved.

Display rules:

- score percentiles must render with submit rate where available
- low submit rate, threshold chosen from Phase 0 rather than hard-coded in this PRD,
  must render with a warning badge if not excluded by the filter itself
- missing submit rate should render as "submit rate unknown"
- percentile values should be described as reported submitter profile, not as the
  whole enrolled/admitted class

## Separate Hot Fix

The existing school-page key-stat mapping should be fixed outside this PRD:

- ACT Composite should use `C.914` and `C.916` for 25th/75th percentile.
- The current code appears to reference `C.921` and `C.923`, which are ACT English
  50th percentile and ACT Writing 25th percentile in the 2025-26 schema.

That should ship as a small bug-fix PR with a regression test for
canonical-field-to-display mapping. It should not wait for this multi-phase browser
expansion.

## Verification

Backend:

```bash
python3 -m unittest tools/browser_backend/project_browser_data_test.py
python3 -m py_compile tools/browser_backend/project_browser_data.py tools/browser_backend/project_browser_data_test.py
deno test supabase/functions/_shared/*.test.ts supabase/functions/browser-search/*.test.ts
```

Frontend:

```bash
cd web
npm exec tsc -- --noEmit
npm run build
```

Data checks:

- answerability report before and after projection
- report rows with percentile values but missing submit rates
- latest-per-school query with each promoted academic-profile filter
- latest-with-field query comparison for each promoted academic-profile filter
- CSV export includes promoted columns with fractional labels for rates
- spot-check at least 50 source documents, including at least 30 `pdf_flat` Tier 4
  examples
- regression report for v0.2 -> v0.3 Tier 4 candidate fields

## Open Questions

1. Which candidate fields actually clear the answerability gate after v0.3?
2. Does the first promotion scope to `year_start >= 2025`, or can 2024-25 field-ID
   compatibility be verified enough to keep `year_start >= 2024`?
3. What submit-rate threshold, if any, is justified by the Phase 0 distribution?
4. Should academic-profile search use latest-in-window or latest-in-window-with-field
   semantics after both are measured?
5. Should section-only SAT reporters get a derived `sat_component_sum_*_v1` metric
   later, or is explicit exclusion clearer?

## Recommendation

Proceed only through the measurement gate now.

The v0.3 extraction drain gives enough coverage to justify measuring SAT/ACT/GPA and
class-rank answerability. It does not yet justify a fixed migration list or public UI
filters. The safest path is:

1. resolve stale fallback and selected-artifact semantics
2. refresh projection unchanged
3. measure section-specific answerability by source format and producer
4. measure both latest-window semantics
5. confirm schema-version mapping
6. promote only fields that clear the gate
7. expose UI filters only where the missingness and submission-rate caveats can be
   made visible

This keeps the API useful while preserving the browser's credibility.
