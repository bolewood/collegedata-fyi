# supabase/pending

SQL that is written and tested but is **not** a migration. Nothing here is applied by `supabase db push`
or by CI. A file here becomes a real migration only in a later PR, after the owner approves it, and is then
applied from a fresh `main` checkout (see `CLAUDE.md`, "Migrations").

- `038_overlay_serving.sql`: PRD 038 template-overlay serving in `cds_selected_extraction_result`. It defines
  `cds_overlay_serve_classes()` returning `'{}'`, so applying it changes no output until a later change to
  that function names a class. Applied only by a later PR after owner approval of the shadow audit.
- `038_decision1_selection_diff.sql`: read-only before/after diff of the selected producer per document under
  the A3 rule (PRD 038 Decision 1). The Decision 1 view rewrite itself is not written yet and is not part of M3.

The disagreement hold is not in the SQL: `held` is computed when the overlay artifact is written (PRD 038 A14) and the view only skips artifacts whose `notes.held` is not exactly `false`. `tools/browser_backend/run_overlay_sql_fixture.py` runs the pending view over the shared parity fixture (SELECT only, by hand, not CI).
