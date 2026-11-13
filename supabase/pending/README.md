# supabase/pending

SQL that is written and tested but is **not** a migration. Nothing here is applied by `supabase db push` or by CI.

- `038_decision1_selection_diff.sql`: read-only before/after diff of the selected producer per document under the A3 rule
  (PRD 038 Decision 1). The Decision 1 view rewrite itself is not written yet.

The template-overlay serving SQL that used to live here is now two migrations
(`20261113042000_overlay_serving_view.sql`, `20261113042100_school_browser_rows_overlay_producer_version.sql`; PRD 038 A15).
`tools/browser_backend/run_overlay_sql_fixture.py` (read-only, against any Postgres you point a read-only psql wrapper at) and
`tools/browser_backend/run_overlay_migration_local.py` (a throwaway local Postgres) run them over the shared parity fixture, by hand.
