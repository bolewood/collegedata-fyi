# Queryable Browser Backend Notes

Implemented for PRD 010. Backend and frontend MVP were deployed on
2026-04-26. PRD 012 expanded the backend serving contract on 2026-04-28 with
SAT/ACT academic-profile fields after the Tier 4 v0.3 projection refresh.

## Surfaces

- `cds_field_definitions`: schema-local field labels and type hints.
- `cds_metric_aliases`: direct-field aliases only. Browser aliases currently
  include the PRD 010 admissions funnel fields plus PRD 012 SAT/ACT
  submission-rate and percentile fields. Derived metrics such as
  `acceptance_rate` and `yield_rate` stay out of the alias table.
- `cds_selected_extraction_result`: helper view that selects the strongest
  deterministic extraction result and merges `tier4_llm_fallback`
  `kind='cleaned'` values as a gap-filling overlay for Tier 4 rows.
- `cds_fields`: materialized long-form field projection for `2024-25+`.
- `school_browser_rows`: curated one-row-per-school-year serving table.
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

The worker also seeds `cds_field_definitions` and `cds_metric_aliases` from the
committed schema artifacts unless `--skip-metadata` is passed.

Production projection history:

| Date | Change | `cds_fields` rows | `school_browser_rows` rows | Documents processed | Notes |
|---|---|---:|---:|---:|---|
| 2026-04-26 | PRD 010 launch | 113,836 | 472 | 507 | First browser substrate after launch projection. |
| 2026-04-28 | PRD 012 + Tier 4 v0.3 refresh | 217,910 | 469 | 503 | Stale rows cleared before rebuild; SAT/ACT backend columns populated. |

The PRD 012 refresh added `104,074` projected field rows, a `91.4%` increase
over launch. Average field rows per processed document moved from about `224.5`
to `433.2`. The browser row count dropped by three because `--full-rebuild` now
clears stale `2024+` projection rows before repopulating.

Current `2024+` field rows by selected source format:

| Source format | Field rows |
|---|---:|
| `pdf_flat` | 141,554 |
| `pdf_fillable` | 53,016 |
| `xlsx` | 23,082 |
| `html` | 152 |
| `pdf_scanned` | 106 |

The worker is currently operator-run. It is not yet wired into the extraction
worker after every artifact write.

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

- `canonical_metric` is only used for direct field aliases. `acceptance_rate` and
  `yield_rate` are derived in `school_browser_rows`.
- `sub_institutional` is preserved in both public tables. Browser search defaults
  to `variant_scope = primary_only`, which filters to `sub_institutional IS NULL`.
- Percent/rate storage is fractional `0..1`.
- Some current Tier 4/Tier 6 artifacts do not carry `schema_version`; the
  projector falls back to `2025-26` for the `2024-25+` MVP because that is the
  only committed full schema JSON artifact today.
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

- wire the projection worker into the extraction pipeline or a scheduled refresh
- move browser ranking into a SQL RPC/window-function path if traffic or corpus
  size makes the Edge Function table-read approach hot
- add repo-native Playwright smoke tests
- paginate CSV export beyond the current Edge Function page-size cap
