# PRD 012: Browser field expansion after Tier 4 v0.3

**Status:** Draft
**Created:** 2026-04-28
**Author:** Codex + Anthony
**Related:** [PRD 010](010-queryable-data-browser.md), [PRD 011](011-academic-profile-llm-repair.md), [PRD 0111A](0111A-docling-improvement-spike.md), [Extraction Quality](../extraction-quality.md), [Queryable Browser Backend](../queryable-browser-backend.md)

---

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

Tier 4 v0.3 materially changes that calculus. The deterministic layout-overlay
drain completed on 2026-04-28 with:

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

Field count is still coverage, not ground truth. But the v0.3 drain moved the
project from "hide most academic-profile fields until repair" to "measure
answerability and promote the fields that clear a public-browser bar."

## Thesis

The next browser iteration should expand the curated serving layer, but only after
the refreshed `cds_fields` projection proves that the candidate fields are
answerable in the current `2024-25+` data.

The project should **not** expose all 1,105 CDS fields as browser columns. That is
what `cds_fields` is for. `school_browser_rows` should remain a curated, documented
serving contract for fields that are:

1. user-meaningful in a school search workflow
2. directly backed by stable CDS fields or explicitly documented derived metrics
3. normalized consistently across producers
4. answerable often enough to support filtering without surprising empty results
5. honest about missingness, test-optional behavior, and source provenance

## Goals

1. Refresh `cds_fields` and `school_browser_rows` after the Tier 4 v0.3 drain.
2. Measure answerability for SAT, ACT, GPA, and class-rank candidate fields across
   `2024-25+` primary rows.
3. Add a conservative set of academic-profile columns to `school_browser_rows`.
4. Preserve PRD 010's direct-vs-derived metric split:
   - `cds_metric_aliases.canonical_metric` is for direct field aliases only.
   - derived values belong in `school_browser_rows` or a documented derived layer.
5. Add backend tests for normalization, null semantics, and browser-search
   answerability.
6. Fix existing school-page key-stat references that point at the wrong ACT
   composite fields.

## Non-goals

- Do not add arbitrary filtering over every CDS field in the public UI.
- Do not claim SAT/ACT/GPA values are admissions requirements; they are reported
  admitted/enrolled profile data from the CDS.
- Do not derive SAT composite from EBRW + Math unless a separate, documented
  derived metric is approved.
- Do not impute missing test data from nearby rows, school reputation, Scorecard,
  or other external sources.
- Do not run LLM repair as part of this PRD. LLM/VLM repair remains PRD 011 work.

## Candidate Fields

### Recommended first promotion

These are direct CDS fields and are useful enough to justify first-class browser
columns if answerability is acceptable.

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
| `avg_hs_gpa` | `C.1201` | Average high school GPA of students submitting GPA | decimal |
| `hs_gpa_submit_rate` | `C.1202` | Percent submitting high school GPA | fractional `0..1` |

### Optional second promotion

Class-rank fields are valuable, but less universal because many high schools no
longer rank students. They should ship if answerability is strong enough and the
UI labels make missingness obvious.

| Metric | Field | Meaning | Storage |
|---|---|---|---|
| `top_tenth_pct` | `C.1001` | Percent in top tenth of high-school class | fractional `0..1` |
| `top_quarter_pct` | `C.1002` | Percent in top quarter | fractional `0..1` |
| `top_half_pct` | `C.1003` | Percent in top half | fractional `0..1` |
| `class_rank_submit_rate` | `C.1006` | Percent submitting class rank | fractional `0..1` |

### Keep in `cds_fields` only for now

The following fields should remain queryable through `cds_fields` but should not be
first-class browser columns yet:

- SAT distribution buckets (`C.932`-`C.952`)
- ACT distribution buckets (`C.953`-`C.987`)
- GPA distribution buckets (`C.1101`-`C.1130`)
- per-section ACT Math/English/Writing/Science/Reading percentiles unless a user
  workflow specifically needs them

They add a lot of width and interpretation burden to the browser. The direct
field substrate can support analysts who need them without turning the public
browser into a 100-column spreadsheet.

## Answerability Gate

Before adding the UI controls, run a measurement pass over refreshed `cds_fields`
and `school_browser_rows`:

Scope:

- `year_start >= 2024`
- `sub_institutional IS NULL`
- selected extraction result only
- exclude `data_quality_flag = 'wrong_file'`

For each candidate metric, report:

- rows with `value_status = reported`
- rows with parse errors
- rows with source producer breakdown
- latest-per-school answerability
- answerability among primary rows only
- count of values outside plausible range

Promotion thresholds:

| Promotion level | Minimum bar |
|---|---|
| Add to `cds_metric_aliases` / `cds_fields` alias | direct field exists in current schema and parses deterministically |
| Add to `school_browser_rows` | meaningful reported count in `2024-25+` primary rows and no systemic range failures |
| Add as visible table column / CSV export | answerability is high enough that users will see values in normal searches |
| Add as default filter control | answerability is high enough that filtering does not mostly measure missingness |

Initial numeric thresholds:

- Display/export candidate: at least 25% reported among `2024-25+` primary rows.
- Filter candidate: at least 40% reported among `2024-25+` primary rows.
- Parse-error rate: below 2% of reported-looking values.
- Manual spot check: at least 20 schools across producer/source-format mix before
  calling a metric launch-certified.

These thresholds are intentionally pragmatic, not permanent. A field with lower
coverage may still be useful if the UI clearly labels it as "reported by school"
and answerability metadata is visible.

## Data Semantics

### Percent and rate values

All percent/rate columns must store fractional values in `0..1`, matching PRD 010.

Examples:

- source `58%` -> `0.58`
- source `58` in a CDS percent field -> `0.58`
- source `0.58` -> `0.58`

### Missingness

SAT/ACT/GPA missingness is not one thing. The browser should distinguish where the
source allows it:

- `reported`: value appears in the selected extraction result
- `not_applicable`: school explicitly marks the field not applicable
- `not_used`: school says the metric is not used or not considered
- `test_optional`: policy context says tests are optional, but percentile data may
  still be reported for submitters
- `missing_extraction`: value may exist in the PDF, but the selected extractor did
  not recover it
- `missing_source`: the school did not publish the value in the CDS

MVP implementation can keep the existing `value_status` column, but the UI copy must
avoid implying that blank SAT/ACT/GPA fields always mean "school does not use this."

### SAT/ACT profile caveat

CDS SAT/ACT percentile fields describe students who submitted scores. They do not
describe every admitted or enrolled student when test submission is optional or
partial. The browser should label these as "reported submitter profile" or similar
where space allows.

### Composite caveat

Some schools report SAT EBRW/Math but not SAT Composite. PRD 012 should not derive
composite scores from components. If this becomes useful later, add explicit
derived metrics such as `sat_component_sum_p25_v1`.

## Implementation Plan

### Phase 0: Refresh and measure

1. Run the projection rebuild unchanged:

   ```bash
   python tools/browser_backend/project_browser_data.py --full-rebuild --apply
   ```

2. Run an answerability report for the candidate field IDs.
3. Save the report under `.context/` and summarize the results in
   `docs/queryable-browser-backend.md`.

### Phase 1: Schema migration

Add nullable columns to `school_browser_rows` for the first-promotion fields:

- `sat_submit_rate numeric(7,6)`
- `act_submit_rate numeric(7,6)`
- `sat_composite_p25 integer`
- `sat_composite_p50 integer`
- `sat_composite_p75 integer`
- `sat_ebrw_p25 integer`
- `sat_ebrw_p50 integer`
- `sat_ebrw_p75 integer`
- `sat_math_p25 integer`
- `sat_math_p50 integer`
- `sat_math_p75 integer`
- `act_composite_p25 integer`
- `act_composite_p50 integer`
- `act_composite_p75 integer`
- `avg_hs_gpa numeric(4,2)`
- `hs_gpa_submit_rate numeric(7,6)`

Add fractional checks for submit rates and plausible-range checks for scores/GPA:

- SAT fields: `200..1600` for composite, `200..800` for sections
- ACT fields: `1..36`
- GPA: `0..4.5` for MVP tolerance, even though most values should be `0..4.0`

Indexes:

- `sat_composite_p50`
- `act_composite_p50`
- `avg_hs_gpa`
- optional composite indexes only if browser-search filtering gets slow

### Phase 2: Projection worker

1. Extend `DIRECT_METRIC_ALIASES` with the direct field aliases above.
2. Keep derived metrics out of `cds_metric_aliases`.
3. Extend `build_browser_row()` to populate the new columns.
4. Preserve fractional percent normalization for submit rates.
5. Add tests for:
   - direct aliases include SAT/ACT/GPA fields
   - derived metrics are still excluded from aliases
   - submit rates are fractional
   - invalid SAT/ACT/GPA values do not write misleading browser values
   - `sub_institutional` is preserved

### Phase 3: API/search contract

Extend `browser-search` to:

- allow filters on promoted academic-profile columns
- include the columns in result rows
- include answerability metadata for any active academic-profile filters
- keep the latest-per-school required-field semantics from PRD 010

Important operator/null rule from PRD 010 still applies:

- `=`, `!=`, `>`, `>=`, `<`, `<=`, `is not blank` require the field for
  answerability
- `is blank` does not require the field
- `!= NULL` must not count as satisfying a predicate

### Phase 4: Frontend

Add an "Academic profile" section to `/browse` only after Phase 0 confirms enough
answerability.

Recommended first UI controls:

- SAT Composite 50th percentile min/max
- ACT Composite 50th percentile min/max
- Average high-school GPA min/max
- optional toggles for "has SAT profile", "has ACT profile", and "has GPA profile"

Do not expose every percentile and section score as a first-screen filter. Include
the supporting p25/p75 columns in result details or CSV export first.

Also fix the existing school-page key-stat mapping:

- ACT Composite should use `C.914` and `C.916` for 25th/75th percentile.
- It currently appears to reference `C.921` and `C.923`, which are ACT English
  50th percentile and ACT Writing 25th percentile in the 2025-26 schema.

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
- latest-per-school query with SAT/GPA filters
- CSV export includes promoted columns with fractional labels for rates
- spot-check at least 20 source PDFs across Tier 1, Tier 2, Tier 4, and Tier 6
  where available

## Open Questions

1. Should SAT/ACT/GPA columns display in the main results table by default, or only
   after the user enables academic-profile filters?
2. Should class-rank fields ship with SAT/ACT/GPA, or wait for a second browser
   expansion?
3. Should `school_browser_rows` include p25/p50/p75 for each metric, or should the
   public table expose only p50 with p25/p75 available in detail/CSV?
4. Should stale `tier4_llm_fallback` artifacts be invalidated before the projection
   refresh, so academic-profile values cannot accidentally combine a v0.3 base with
   an older fallback overlay?

## Recommendation

Proceed, but gate the public UI on measurement.

The v0.3 extraction drain gives enough coverage to justify expanding the projection
model now. The safest path is:

1. refresh projection unchanged
2. measure academic-profile answerability
3. add direct aliases and serving columns for SAT/ACT/GPA
4. add browser-search support
5. expose UI filters only for the fields that clear the answerability gate

This keeps the API useful immediately while preserving the browser's credibility.
