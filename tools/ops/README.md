# ops

Operator and CI automation scripts for the pipelines: health checks, heartbeats, alerts, controlled directory drains, and workflow linting. None of these own data; they read live Supabase state or call the Edge Functions. Most accept `--env <path>` (default `.env`) and use the shared `tools/extraction_worker/.venv` environment. Write run artifacts to `scratch/ops/`.

## Used by GitHub Actions

| Script | Purpose |
|---|---|
| `record_heartbeat.py` | Writes a pipeline-observation heartbeat via `record_pipeline_heartbeat` (feeds `/pipeline-observation`). Never fails the calling job: a POST error prints a `::warning::` and exits 0. Flags: `--station`, `--status`, `--trigger`, `--summary`, `--summary-json`, `--error-code`, `--run-url`, `--pr-url`. |
| `upsert_pipeline_alert_issue.py` | Opens (or comments on) a single GitHub "Pipeline alert" issue when a scheduled station fails, instead of spamming. Flags: `--repo`, `--component`, `--title`, `--body`, `--run-url`. |
| `notify_discord.py` | Posts ops events to the Discord webhooks (`ops-discord-notify.yml`, hourly). Posts only on first miss and on recovery; never fails the job; never prints webhook URLs. See [`docs/ops-discord.md`](../../docs/ops-discord.md). |
| `enqueue_changed_seeds.py` | After `tools/finder/schools.yaml` changes on `main`, enqueues archive work for the schools whose seed changed so they do not wait out the 7-day cooldown (`ops-archive-seed-catchup.yml`). `--before`, `--after`, `--apply`. |
| `top100_coverage.py` | Scores the priority-100 cohort (`data/watchlists/priority_coverage.yaml`) against the two-year byte bar and routes residential-allowlisted schools (`data/watchlists/residential_allowlist.yaml`) to the headless archive workflow. Coverage means finder and archive, not extraction. |
| `lint_gha_heredocs.py` | CI check: fails on indented bash heredoc terminators inside `run: |` blocks, which GitHub Actions leaves indented so bash never closes the heredoc. Run `python tools/ops/lint_gha_heredocs.py` before pushing workflow edits. |

## Operator tools

| Script | Purpose |
|---|---|
| `automation_health.py` | One-command health check of the automated archive and extraction workers (database state plus recent GitHub Actions runs). `--hours`, `--json-out`, `--markdown-out`, `--fail-on-unhealthy`. |
| `extraction_backlog_audit.py` | Reports the `extraction_pending` backlog after archive or directory drains and optionally checks the extraction worker's last successful run. `--max-pending-age-hours`, `--max-pending-count`, `--fail-on-pending-growth`, `--json`. |
| `directory_enqueue_batches.py` | Controlled batches of `directory-enqueue`. Dry-run by default; `--apply` enqueues and drains staged batches, with transient-failure and stall gates. |
| `directory_enqueue_autopilot.py` | Unattended sequence of small directory batches that waits for each to drain, audits high-value `no_pdfs_found` rows, and force-archives official CDS documents when discovery is unambiguous. Operator workflow, not CI or cron. |
| `duplicate_slug_audit.py` | Read-only audit of active `cds_documents` filed under non-canonical alias slugs, using `institution_slug_crosswalk` and `institution_directory`. |
| `bootstrap_collegedata_ops.sh` | Creates the private `collegedata-ops` repo and pushes the bundle in `ops/collegedata-ops/` (requires a token that can create private repositories). |

## Tests

`test_*.py` files sit beside the scripts. Run them with `pytest tools/ops`.
