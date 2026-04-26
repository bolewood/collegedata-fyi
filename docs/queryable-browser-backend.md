# Queryable Browser Backend Notes

Implemented for PRD 010. Backend and frontend MVP were deployed on
2026-04-26.

## Surfaces

- `cds_field_definitions`: schema-local field labels and type hints.
- `cds_metric_aliases`: direct-field aliases only. MVP aliases are `applied`,
  `admitted`, and `first_year_enrolled`.
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

Production launch projection populated:

- `113,836` rows in `cds_fields`
- `472` rows in `school_browser_rows`
- from `507` documents in the `2024-25+` scope

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

## Verification

Primary checks:

```bash
python3 -m unittest tools/browser_backend/project_browser_data_test.py
python3 -m py_compile tools/browser_backend/project_browser_data.py tools/browser_backend/project_browser_data_test.py
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

## Follow-ups

Tracked in [`docs/backlog.md`](backlog.md):

- wire the projection worker into the extraction pipeline or a scheduled refresh
- move browser ranking into a SQL RPC/window-function path if traffic or corpus
  size makes the Edge Function table-read approach hot
- add repo-native Playwright smoke tests
- paginate CSV export beyond the current Edge Function page-size cap
