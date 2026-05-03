# Queryable Browser Backend Notes

Implemented for PRD 010. Backend and frontend MVP were deployed on
2026-04-26. PRD 012 expanded the backend serving contract on 2026-04-28 with
SAT/ACT academic-profile fields after the Tier 4 v0.3 projection refresh.
PRD 016, 016B, 017, and 018 now use the same serving substrate for academic
positioning, admission strategy, match-list building, and merit profile data.

## Surfaces

- `cds_field_definitions`: schema-local field labels and type hints.
- `cds_metric_aliases`: direct-field aliases only. Browser aliases currently
  include PRD 012 SAT/ACT submission-rate and percentile fields. Admissions
  funnel metrics moved to PRD 014 derived formulas because 2024-25 and 2025-26
  use different C.10x layouts.
- `cds_canonical_field_equivalence`: source-schema field ids mapped into the
  2025-26 reference frame with `direct`, `derived`, `preserved-only`, or
  `unmapped` classifications.
- `cds_selected_extraction_result`: helper view that selects the strongest
  deterministic extraction result and merges `tier4_llm_fallback`
  `kind='cleaned'` values as a gap-filling overlay for Tier 4 rows only when
  the fallback matches the selected base artifact id or legacy markdown hash +
  cleaner version.
- `cds_fields`: materialized long-form field projection for `2024-25+`.
- `school_browser_rows`: curated one-row-per-school-year serving table.
- `school_merit_profile`: PRD 018 view exposing latest primary 2024-25+ CDS
  Section H merit/need-aid facts per school, left-joined to selected Scorecard
  affordability and outcome fields.
- `browser-search` Supabase Edge Function: ranked latest-per-school search with
  answerability metadata.
- `/browse`: public MVP browser page backed by the Edge Function. The first UI
  exposes launch-certified filters, answerability counts, pagination, source
  links, and CSV export for the current curated result set.

## Refresh

Run the projection worker with the service-role key:

```bash
python tools/browser_backend/project_browser_data.py --full-rebuild --apply
python tools/browser_backend/project_browser_data.py --document-id <uuid> --apply
```

The worker also seeds `cds_field_definitions`, `cds_metric_aliases`, and
`cds_canonical_field_equivalence` from the committed schema/diff artifacts
unless `--skip-metadata` is passed.

Production projection history:

| Date | Change | `cds_fields` rows | `school_browser_rows` rows | Documents processed | Notes |
|---|---|---:|---:|---:|---|
| 2026-04-26 | PRD 010 launch | 113,836 | 472 | 507 | First browser substrate after launch projection. |
| 2026-04-28 | PRD 012 + Tier 4 v0.3 refresh | 217,910 | 469 | 503 | Stale rows cleared before rebuild; SAT/ACT backend columns populated. |
| 2026-05-03 | PRD 016B/018 + fresh-row drains | 200,957 | 475 | n/a | Admission strategy columns, merit profile view, and targeted redrains. Lower `cds_fields` count is expected after source-routing cleanup and current selected-result filtering. |

The PRD 012 refresh added `104,074` projected field rows, a `91.4%` increase
over launch. Average field rows per processed document moved from about `224.5`
to `433.2`. The browser row count dropped by three because `--full-rebuild` now
clears stale `2024+` projection rows before repopulating.

Current `2024+` field rows by selected source format:

| Source format | Field rows |
|---|---:|
| `pdf_flat` | 138,145 |
| `pdf_fillable` | 45,014 |
| `xlsx` | 17,524 |
| `html` | 173 |
| `pdf_scanned` | 101 |

The full rebuild worker remains operator-run. Incremental projection refresh is
wired into `tools/extraction_worker/worker.py` after successful canonical writes
unless `--skip-projection-refresh` is passed.

## Frontend Contract

The public `/browse` page uses the Edge Function rather than querying
`school_browser_rows` directly. Its default request is:

```json
{
  "mode": "latest_per_school",
  "variant_scope": "primary_only",
  "min_year_start": 2024
}
```

Numeric percentages in the UI are displayed as `0..100%`, but request filters
and table storage use fractional `0..1` values. CSV exports keep rate columns
as fractional values and label them with `_fraction`.

PRD 012 added SAT/ACT backend fields to `school_browser_rows`:

- `sat_submit_rate`, `act_submit_rate`
- `sat_composite_p25`, `sat_composite_p50`, `sat_composite_p75`
- `sat_ebrw_p25`, `sat_ebrw_p50`, `sat_ebrw_p75`
- `sat_math_p25`, `sat_math_p50`, `sat_math_p75`
- `act_composite_p25`, `act_composite_p50`, `act_composite_p75`

Score columns are nullable and range-checked before projection. Submit rates are
stored fractionally in `0..1`. The Edge Function accepts these fields for
filters/sorts and returns academic-profile companion metadata for score filters,
including how many matching rows have a missing submit-rate companion. The public
`/browse` UI does not yet expose score filters by default.

PRD 016B added admission-strategy fields to `school_browser_rows`:

- `ed_offered`, `ed_applicants`, `ed_admitted`,
  `ed_has_second_deadline`
- `ea_offered`, `ea_restrictive`
- `wait_list_policy`, `wait_list_offered`, `wait_list_accepted`,
  `wait_list_admitted`
- selected C7 factors: first-generation, alumni/ae relation, geographical
  residence, state residency, demonstrated interest
- `app_fee_amount`, `app_fee_waiver_offered`
- `admission_strategy_card_quality`

The projector stores effective booleans for ED and wait-list policy when valid
counts prove the policy exists even if the source checkbox was blank or missed.
Math-inconsistent rows are flagged so cards can suppress rate calculations.

PRD 017's `/match` page reads `school_browser_rows` plus directory and
Scorecard enrichment to rank schools against the same student-profile model used
by PRD 016 positioning. The save/share code is stateless and client-side; no
profile data is written to the backend.

PRD 018's `school_merit_profile` is a read-only view, not part of
`school_browser_rows`. It keeps Section H aid semantics separate from the
browser table because merit-aid rows need more copy, caveats, and Scorecard
context than a flat browser column should carry.

Production PRD 012 answerability, primary clean rows (`sub_institutional IS NULL`
and no `data_quality_flag`), 2024+:

| Metric | Field | Primary clean coverage | pdf_flat coverage | Latest-row coverage |
|---|---|---:|---:|---:|
| `sat_submit_rate` | `C.901` | 65.4% | 67.2% | 65.2% |
| `act_submit_rate` | `C.902` | 58.1% | 57.3% | 57.8% |
| `sat_composite_p50` | `C.906` | 67.2% | 71.9% | 68.0% |
| `act_composite_p75` | `C.916` | 66.1% | 71.2% | 66.6% |

Full Phase 0 output is in
[`docs/plans/prd-012-phase-0-findings.md`](plans/prd-012-phase-0-findings.md).

## Verification

Primary checks:

```bash
python3 -m unittest tools/browser_backend/project_browser_data_test.py
python3 -m py_compile tools/browser_backend/project_browser_data.py tools/browser_backend/project_browser_data_test.py tools/browser_backend/prd012_answerability.py
deno test supabase/functions/_shared/*.test.ts supabase/functions/browser-search/*.test.ts
cd web && npm exec tsc -- --noEmit
cd web && npm run build
```

Production smoke checks used:

- `GET https://www.collegedata.fyi/browse`
- `POST https://isduwmygvmdozhpvzaix.supabase.co/functions/v1/browser-search`
- Playwright screenshot wait for a live browser result row on `/browse`

## Implementation Notes

- `cds_fields.field_id` is the source schema field id. `canonical_field_id` is
  the equivalent 2025-26 reference id when one exists; `equivalence_kind`
  records whether the row is `direct`, `derived`, `preserved-only`, or
  `unmapped`.
- The Python projector now prefers a selected canonical artifact whose
  `schema_version` matches `cds_documents.canonical_year`; fallback artifacts
  marked with `notes.schema_fallback_used` lose to a year-matched non-fallback
  artifact even when the fallback is newer.
- Admissions browser metrics (`applied`, `admitted`, `enrolled_first_year`) are
  evaluated through per-year formulas. For 2024-25, `applied` is
  `C.101 + C.102 + C.103 + C.104`; for 2025-26 it is `C.116`.
- Admission strategy columns are sourced from C21/C22, C2 wait-list rows, C7
  factor rows, and app-fee/waiver fields. The card-quality enum is intentionally
  part of the data contract so consumers can tell unknown from known-but-
  internally-inconsistent.
- `canonical_metric` is set on direct alias rows and on single-field derived
  formula rows. Multi-field formula components remain source rows in
  `cds_fields`; their aggregate lands in `school_browser_rows`.
- `sub_institutional` is preserved in both public tables. Browser search defaults
  to `variant_scope = primary_only`, which filters to `sub_institutional IS NULL`.
- Percent/rate storage is fractional `0..1`.
- Some current Tier 4/Tier 6 artifacts do not carry `schema_version`; the
  projector still has a legacy fallback to `2025-26`. PRD 014 M3 will make
  extractor writes year-aware so new artifacts carry the actual schema version.
- The `browser-search` Edge Function ranks over the materialized table after one
  paginated table read. That keeps the MVP small and testable. If corpus size or
  traffic makes this hot, move the same pure ranking contract into a Postgres RPC
  with window functions.
- The first frontend intentionally does not expose arbitrary `cds_fields`
  filtering. It stays on the curated `school_browser_rows` contract until more
  fields are launch-certified.
- GPA and class-rank remain in the long-form field substrate only. GPA scale
  comparability and class-rank denominator semantics are not solved enough for
  first-class browser columns.
- The PRD 012 Phase 0 measurement found strong SAT/ACT coverage in `pdf_flat`
  Tier 4 rows, but also found XLSX academic-profile parse errors that look like
  schema/mapping drift. The projection validator nulls invalid score values
  rather than letting them into browser columns; the XLSX mapping audit remains
  a follow-up.

## Follow-ups

Tracked in [`docs/backlog.md`](backlog.md):

- move browser ranking into a SQL RPC/window-function path if traffic or corpus
  size makes the Edge Function table-read approach hot
- paginate CSV export beyond the current Edge Function page-size cap
