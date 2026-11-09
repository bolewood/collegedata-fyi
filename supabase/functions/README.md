# Edge Functions

Seven Supabase Edge Functions (Deno/TypeScript) plus shared modules in `_shared/`. Each function's header comment is the authoritative description; this page is the index.

**Deploying:** never run `supabase functions deploy` from a feature branch or worktree. The `Deploy Edge Functions` workflow (`.github/workflows/deploy-edge-functions.yml`) deploys every function here when function code or `supabase/config.toml` changes on `main`. To redeploy without a code change, dispatch that workflow. See "Edge Functions" in the root `CLAUDE.md`.

**Auth:** all functions except `browser-search` use `verify_jwt = true` in `supabase/config.toml` and additionally require the bearer token to equal `SUPABASE_SERVICE_ROLE_KEY` in the handler. They are called by `pg_cron` or by an operator with `curl`; they are not public APIs. `browser-search` is the exception: it is called by the web app with the anon key.

| Function | Trigger | What it does | Related |
|---|---|---|---|
| `archive-enqueue` | `pg_cron`, daily | Seeds `archive_queue` from `tools/finder/schools.yaml` with a deterministic per-UTC-day `run_id`. Per-outcome cooldowns (successful schools every 7 days; stable failures back off longer). Query params `school_ids` and `force_recheck=true` support targeted runs. | `tools/ops/enqueue_changed_seeds.py`, `ops-archive-seed-catchup.yml` |
| `archive-process` | `pg_cron`, every 30 seconds | Claims one ready `archive_queue` row, runs the shared `archiveOneSchool` pipeline (resolve, fetch, hash, upload to Storage, write `cds_documents`/`cds_artifacts`). Also the operator entry points `?force_school=<id>` and `force_urls` (archive explicit URLs; see `tools/mirrors/`). | `tools/finder/`, `docs/archive-pipeline.md` |
| `archive-upload` | Operator | Accepts a multipart upload (`school_id`, `cds_year`, `file`, optional `source_url`, `source_provenance`, `school_name`) for files the resolver cannot fetch. PDF/XLSX/DOCX only, magic-byte validated, deduplicated by SHA-256. | `tools/upload/` |
| `directory-enqueue` | Operator, no cron | Seeds `archive_queue` from `institution_directory` (Scorecard-only institutions that have not been probed). `limit` is required; the default does nothing. | `tools/ops/directory_enqueue_batches.py`, `directory_enqueue_autopilot.py`, PRD 015 |
| `refresh-coverage` | `pg_cron`, hourly; also operator | Rebuilds `institution_cds_coverage` via `refresh_institution_cds_coverage()` and returns the row count and duration. Send `{"include_histogram": true}` for a `coverage_status` histogram. | `tools/scorecard/`, PRD 015 M3 |
| `discover` | Operator, dev only | Dry-run of the landing-page resolver: `GET .../discover?schools=yale,mit` returns the resolved URL and `cds_year` (or the classified failure) per school. Never writes to the database or Storage. | `tools/finder/` |
| `browser-search` | Web app (`POST`) | Powers the school browser search: reads `school_browser_rows` with the anon key and returns ranked matches for a `BrowserSearchRequest`. CORS-enabled. | `web/src/lib/browser-search.ts`, `docs/queryable-browser-backend.md` |

## Shared modules (`_shared/`)

`archive.ts` (per-school archive pipeline), `resolve.ts` (landing-page resolver), `schools.ts` (reads `schools.yaml` and `school_overrides.yaml`), `hosting.ts` and `probe_outcome.ts` (hosting fingerprints, outcome classes), `html_source_guard.ts` (rejects non-CDS HTML), `storage.ts`, `year.ts` (`normalizeYear`), `db.ts`, `pipeline_heartbeat.ts` (writes pipeline-observation heartbeats). Each has a sibling `*.test.ts`.

## Tests

CI runs Deno tests for `_shared/`, `archive-enqueue`, `archive-process`, `browser-search` and `directory-enqueue` (see `.github/workflows/ci.yml` for the exact command and flags).
