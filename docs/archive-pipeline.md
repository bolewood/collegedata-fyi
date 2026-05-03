# Archive pipeline

The archive pipeline is the bridge between discovery (the finder corpus and
the M1a `discover` edge function) and extraction (the Python worker). It
takes every active school in `tools/finder/schools.yaml`, resolves its
`discovery_seed_url` (renamed from `cds_url_hint` in PR 5 of the URL hint
refactor — see [docs/plans/url-hint-refactor-and-hosting-jsonb.md](plans/url-hint-refactor-and-hosting-jsonb.md))
to a direct document URL, downloads the bytes, hashes them, writes
provenance rows to `cds_documents` + `cds_artifacts`, and uploads the
source file to the `sources` Storage bucket. The extraction worker then polls
`cds_documents WHERE extraction_status = 'extraction_pending'` and does
the structured extraction.

As of May 3, 2026, this document covers the full operating chain:

1. **Discovery / archive** in Supabase Edge Functions.
2. **Structured extraction** in the Python worker across shipped Tiers 1, 2, 4, 5, and 6.
3. **Tier 4 LLM fallback overlay** for selected low-coverage flattened PDFs.
4. **Queryable browser projection** into `cds_fields` and `school_browser_rows`.
5. **Institution coverage / fit-data projections** into `institution_cds_coverage`,
   `school_browser_rows`, and `school_merit_profile`.
6. **GitHub Actions wrappers** for boring PR CI and bounded ops drains.

The archive layer stores immutable source bytes and provenance. It does not
decide which extracted values are canonical for consumers; that decision happens
later in the extraction artifacts and browser projection layers.

The resolver also writes a row to `school_hosting_observations` on every
probe (gated by `HOSTING_OBSERVATIONS_ENABLED=true`), capturing inferred
CMS, file_storage, auth_required, rendering, and WAF. The
`latest_school_hosting` view exposes the most-recent observation per
school for consumers that don't want history.

The monthly enqueuer applies a per-outcome cooldown so schools whose
most recent probe was `unchanged_verified` (30d), `auth_walled_*` (90d),
`dead_url` (14d), etc. are skipped for the relevant window — typically
~67% of active schools per cron.

Archive discovery runs on Supabase Edge Functions + pg_cron + pg_net. One
school per edge function invocation so the 400 s wall clock, 256 MB memory, and
2 s CPU caps never bind. The active-school count changes with the finder corpus;
the original ~840-school monthly batch drained in roughly seven hours of wall
clock.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  OUTER CRON  (daily, 02:00 UTC)                              │
│  pg_cron → net.http_post → archive-enqueue                   │
│                                                              │
│  archive-enqueue:                                            │
│    1. GET schools.yaml from GitHub raw                       │
│    2. Filter: scrape_policy=active AND discovery_seed_url   │
│                != null AND sub_institutions is null          │
│    2b. Cooldown filter: drop schools whose most-recent       │
│                         last_outcome's window hasn't expired │
│    3. Derive run_id = sha256('archive-enqueue:YYYY-MM')      │
│    4. Bulk upsert one archive_queue row per school,          │
│       ignoreDuplicates=true → same month is a no-op          │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  INNER CRON  (every 30 seconds)                              │
│  pg_cron → net.http_post → archive-process                   │
│                                                              │
│  archive-process (one school per invocation):                │
│    1. claim_archive_queue_row() RPC                          │
│       → UPDATE status='processing', claimed_at=now(),        │
│              attempts = attempts + 1                         │
│       → FOR UPDATE SKIP LOCKED + visibility timeout (10 min) │
│    2. try: archiveOneSchool()                                │
│       catch PermanentError  → status=failed_permanent        │
│       catch TransientError  → status=ready, enqueued_at=now()│
│                                 (bump to tail of queue)      │
│                              → failed_permanent after        │
│                                MAX_ATTEMPTS=3                │
│    3. finally: UPDATE archive_queue with terminal state,     │
│                guarded by .eq('claimed_at', claimLease)      │
│                so a stale worker cannot overwrite a newer    │
│                owner's state                                 │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  archiveOneSchool  (shared, supabase/functions/_shared/)     │
│                                                              │
│  Resolve: fetch hint, parse HTML, extract every CDS-ish      │
│           document anchor, follow one hop of subpages        │
│           (CMU pattern), fan out via pickCandidates (ADR     │
│           0007 Stage B — multi-candidate, prefer full-CDS    │
│           over section, deprioritize test artifacts).        │
│           Year is a URL-side guess only; content year is     │
│           written later by the extraction worker.            │
│                                                              │
│  Returns a discriminated ResolveResult:                      │
│    resolved             → happy path                         │
│    upstream_gone        → 404/410, mark removed_at on the    │
│                           most recent row for the school     │
│    transient            → DNS/5xx/timeout, throw TransientErr│
│    no_cds_found         → landing parsed, no usable anchor   │
│                           → throw PermanentError             │
│    unsupported_content  → wrong content-type → PermanentErr  │
│    blocked_url          → SSRF guard tripped → PermanentErr  │
│                                                              │
│  Download: fetch with AbortSignal.timeout(30s), stream read  │
│            into chunks, enforce 50 MB cap, compute SHA-256,  │
│            block private IPs / cloud metadata at every fetch │
│                                                              │
│  Decide upsert action:                                       │
│    no row      → INSERT cds_documents + cds_artifacts,       │
│                  upload bytes,                               │
│                  extraction_status='extraction_pending'      │
│    row + same SHA + object present                           │
│                → bumpVerified() (last_verified_at=now(),     │
│                  source_url updated if it moved)             │
│    row + same SHA + object MISSING                           │
│                → re-upload (idempotent on SHA path),         │
│                  record repair artifact row                  │
│    row + new SHA                                             │
│                → upload new bytes to new SHA path,           │
│                  UPDATE cds_documents first (document first, │
│                  then artifact — crash-safe),                │
│                  flip extraction_status='extraction_pending' │
└──────────────────────────────────────────────────────────────┘
```

Downstream of the archive queue, the operator-run Python workers complete the
data path:

```
cds_documents(extraction_pending)
  └─ tools/extraction_worker/worker.py
       ├─ xlsx         → tier1_xlsx canonical artifact
       ├─ pdf_fillable → tier2_acroform canonical artifact
       ├─ pdf_flat     → tier4_docling canonical artifact
       ├─ pdf_scanned  → tier4_docling with forced OCR
       └─ html         → tier6_html canonical artifact

eligible tier4_docling artifacts
  └─ tools/extraction_worker/llm_fallback_worker.py
       └─ tier4_llm_fallback cleaned artifact

selected extraction results
  └─ tools/browser_backend/project_browser_data.py
       ├─ cds_fields
       └─ school_browser_rows
```

The selected-result contract is deterministic: choose the strongest base
producer by rank (`tier1_xlsx`, `tier2_acroform`, `tier6_html`, then
`tier4_docling`), and for Tier 4 rows overlay `tier4_llm_fallback` only as a
gap-fill when the fallback matches the selected base artifact. New fallback
artifacts match by `notes.base_artifact_id`; legacy rows match by
`notes.markdown_sha256 == sha256(base.notes.markdown)` and
`notes.cleaner_version == base.producer_version`. Base deterministic values
win conflicts.

Projection freshness has two paths:

- Incremental extraction drains refresh `cds_fields` and
  `school_browser_rows` for each document that writes a new canonical artifact.
  This keeps newly written artifacts visible in the browser without a separate
  full rebuild. Idempotent `already_extracted` rows skip projection to avoid
  thousands of unnecessary API calls during status-check re-runs. The write
  replacement uses `replace_browser_projection_for_document(...)`, so the
  per-document `cds_fields` and `school_browser_rows` delete/insert sequence is
  one Postgres transaction. Use `--skip-projection-refresh` only when
  intentionally isolating extraction from serving-table side effects.
- Worker drains do not reseed `cds_field_definitions` or `cds_metric_aliases`
  by default. Add `--seed-projection-metadata` after schema or alias changes.
- Full rebuilds remain the operator tool after migrations, projection logic
  changes, metadata changes, or corpus-wide fallback backfills:
  `python tools/browser_backend/project_browser_data.py --full-rebuild --apply`.

### GitHub Actions workers

There are two Actions surfaces, and they are intentionally separate:

- `.github/workflows/ci.yml` is boring PR/push CI. It runs Python unit tests
  for the browser projection and extraction worker, Deno tests for Supabase
  functions, and the Next.js typecheck/build. It deliberately does not run
  Docling corpus drains, live extraction work, projection rebuilds, or any
  service-role database writes.
- `.github/workflows/ops-extraction-worker.yml` is the bounded ops path for
  production-ish extraction work. It runs on a small daily schedule and can be
  started manually with `limit`, `school`, `include_failed`,
  `seed_projection_metadata`, and `low_field_threshold` inputs. It requires
  `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` GitHub Secrets, installs the
  extraction worker dependencies, then calls `tools/extraction_worker/worker.py`
  with `--limit`, `--summary-json`, and the requested filters. Projection
  refresh is enabled by default; metadata seeding is controlled by the workflow
  input.

The ops workflow caps GitHub-hosted runs at 100 rows. Full corpus drains,
large Docling/OCR backfills, and expensive repair experiments still belong on a
laptop or self-hosted runner. Every ops run uploads an
`extraction-worker-summary` artifact containing `summary.json` and
`worker.log`; the summary includes processed count, failures, mean fields,
low-field docs, extraction counts, and projection counts.

### Files

| Purpose | Path |
|---|---|
| `cds_documents` NULL-uniqueness fix + `archive_queue` + claim RPC | `supabase/migrations/20260414170000_archive_pipeline.sql` |
| pg_cron schedules with vault-backed secrets | `supabase/migrations/20260414180000_archive_pipeline_cron.sql` |
| URL-hint year guesser (not authoritative; see ADR 0007) | `supabase/functions/_shared/year.ts` |
| HTML anchor extraction, two-hop, SSRF guard, `pickCandidates` multi-candidate selection, discriminated resolver | `supabase/functions/_shared/resolve.ts` |
| `schools.yaml` fetch + filter + validation | `supabase/functions/_shared/schools.ts` |
| SHA-addressed Storage helpers (upload, head, path build) | `supabase/functions/_shared/storage.ts` |
| `cds_documents` + `cds_artifacts` data access | `supabase/functions/_shared/db.ts` |
| One-school pipeline orchestrator | `supabase/functions/_shared/archive.ts` |
| Resolver dev entry (dry-run, no writes) | `supabase/functions/discover/index.ts` |
| Queue consumer (30 s cron target + `force_school` backfill) | `supabase/functions/archive-process/index.ts` |
| Monthly seeder (daily cron target, deterministic per-month run_id) | `supabase/functions/archive-enqueue/index.ts` |
| Operator-triggered seeder for Scorecard-only directory rows (PRD 015 M2) | `supabase/functions/directory-enqueue/index.ts` |
| Public-safe coverage table refresh, on 15-min pg_cron (PRD 015 M3) | `supabase/functions/refresh-coverage/index.ts` |
| Coverage table + status precedence + atomic refresh RPC (PRD 015 M3) | `supabase/migrations/<ts>_institution_cds_coverage.sql` |
| Format badge / source-format presentation | `supabase/functions/_shared/format.ts`, `web/src/lib/format.ts` |
| Extraction worker | `tools/extraction_worker/worker.py` |
| Tier 4 LLM fallback worker | `tools/extraction_worker/llm_fallback_worker.py` |
| Browser projection worker | `tools/browser_backend/project_browser_data.py` |
| Atomic document projection replacement RPC | `supabase/migrations/20260428170000_atomic_browser_projection_refresh.sql` |
| Minimal CI | `.github/workflows/ci.yml` |
| Bounded ops extraction worker workflow | `.github/workflows/ops-extraction-worker.yml` |
| Unit tests (resolver, year normalizer, hosting inference, probe outcome cooldowns, schools.yaml validation, browser search) | `supabase/functions/**/*.test.ts` |

## Storage path convention

Source files are stored at `sources/{school_id}/{cds_year}/{sha256}.{ext}`.
Every version of a school's CDS gets a unique path, so the archive is
truly immutable and crash-safe. Consumers never construct these paths
themselves — they read `cds_manifest.source_storage_path`, the view
column that picks the most recent `cds_artifacts` row with `kind='source'`
for each document.

Supported source extensions are `pdf`, `xlsx`, `docx`, and `html`. Archived
HTML is uploaded with `content-type: text/plain` even though the object suffix
is `.html`; this prevents public Storage URLs from executing school-hosted
scripts in the `sources` bucket. The extraction worker reads the bytes directly,
so this XSS mitigation does not affect Tier 6 extraction.

SHA-addressed paths replace the earlier `source.pdf` stable path because
the stable-path + history-copy approach had crash windows without real
cross-Storage/Postgres transactions. Details in the code comments on
`archive.ts`.

## Auth model

Both edge functions (`archive-process`, `archive-enqueue`) are configured
with `verify_jwt = true` in `supabase/config.toml`. The Supabase gateway
validates that every incoming request carries a valid project JWT before
the function handler runs.

Inside the handler, `isServiceRoleAuth()` additionally checks that the
caller has the service role, not just any authenticated user. It accepts
two credential formats to survive Supabase's key rotation transition:

1. **Exact match** against `Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")` —
   on projects rotated to the new `sb_secret_` format, this is what the
   runtime injects.
2. **Legacy JWT path** — if the bearer token starts with `eyJ`, decode
   the base64url payload and accept only `role === "service_role"`. Safe
   because Supabase has already verified the JWT signature at the gateway.

This double-gate prevents codex finding #2 from the PR 1-2 review: without
the in-handler check, `verify_jwt=true` alone would let any authenticated
project user trigger service-role writes.

`discover` has no write path and is gated by `verify_jwt=true` only. It
returns a dry-run `ResolveResult` for each requested school without
touching the database or Storage.

## Operator runbook

### One-time setup

1. Deploy the migrations:

   ```bash
   supabase link --project-ref <ref>
   supabase db push
   ```

2. Deploy all five edge functions:

   ```bash
   supabase functions deploy discover archive-process archive-enqueue directory-enqueue refresh-coverage
   ```

   `directory-enqueue` is operator-triggered only — no pg_cron entry.
   `refresh-coverage` runs on a 15-minute pg_cron tick (operators can also
   curl it for ad-hoc refresh after a manual archive drain).

3. Create the two Vault secrets in the dashboard SQL editor. These are
   required for pg_cron to authenticate its `net.http_post` calls:

   ```sql
   select vault.create_secret(
     'https://<your-project-ref>.supabase.co/functions/v1',
     'archive_pipeline_function_base_url',
     'Base URL for archive edge functions, used by pg_cron.'
   );

   select vault.create_secret(
     '<service role JWT or sb_secret_ from Project Settings → API>',
     'archive_pipeline_service_role_key',
     'Service role key used by pg_cron to authenticate edge function calls.'
   );
   ```

4. Re-run `supabase db push` (or apply `20260414180000_archive_pipeline_cron.sql`
   manually). With the vault secrets present, the cron scheduling block
   will run and both jobs will be registered. Verify:

   ```sql
   select jobname, schedule from cron.job where jobname like 'archive%';
   ```

   Expected:

   ```
   archive-enqueue-daily       0 2 * * *
   archive-process-every-30s   30 seconds
   ```

5. Manually seed the first batch so you don't wait until the next 02:00 UTC
   tick:

   ```bash
   curl -X POST "https://<ref>.supabase.co/functions/v1/archive-enqueue" \
        -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
   ```

   Expected response shape. Counts vary with the active corpus and cooldowns:

   ```json
   {
     "mode": "enqueue",
     "run_id": "<deterministic per-month uuid>",
     "enqueued": 837,
     "skipped": 2,
     "skipped_invalid_yaml": 0,
     "total_archivable": 839
   }
   ```

### Day-two operations

**Enqueue Scorecard-only directory schools for discovery** (PRD 015 M2 —
the path that turns `not_checked` rows into real archive attempts so
coverage status precedence has actual data to read). Operator-triggered;
no cron. `limit` is required so every batch is sized intentionally.

For the production launch backlog, use the controlled batch wrapper
instead of one-off curls. The launch state still had ~2.1K
`not_checked` rows; the first reduction pass targets the top 500
highest-enrollment remaining institutions in staged batches:
`25 -> 75 -> 150 -> 250`. This keeps PRD 015's scope intact: no CI
drain, no pg_cron drain, and no automatic full-universe discovery.

```bash
cd /Users/santhonys/Projects/Owen/colleges/collegedata-fyi

# Inspect baseline counts, current in-flight rows, and the next 25 picks.
# This is dry-run-only; it never enqueues archive_queue rows.
python3 tools/ops/directory_enqueue_batches.py --limit 25

# First canary: dry-run, enqueue 25, wait for the run_id to drain,
# refresh coverage, print deltas, and write JSONL under scratch/.
python3 tools/ops/directory_enqueue_batches.py --apply --limit 25

# Continue only after the canary looks sane.
python3 tools/ops/directory_enqueue_batches.py --apply --batches 75,150,250

# If local polling is interrupted after enqueue, resume the same run_id
# without enqueueing another batch.
python3 tools/ops/directory_enqueue_batches.py --resume-run-id <run_id>

# Overnight mode from an operator Mac: keep the machine awake, stream logs,
# drain repeated 25-row batches, stop on permanent_other spikes, and warn
# on transient-heavy batches without stopping.
caffeinate -dimsu python3 -u tools/ops/directory_enqueue_batches.py \
  --apply \
  --batches 25,25,25,25,25,25,25,25,25,25 \
  --poll-interval-seconds 30 \
  --stall-timeout-minutes 20 \
  --max-transient-rate 0.25 \
  --max-permanent-other-rate 0.05

# Unattended mode with high-signal repair after each drained batch.
# This remains operator-controlled: no cron, no CI drain, and explicit
# batch limits. Repairs are conservative: only high-enrollment failed
# rows are probed, only official-domain documents are force-archived,
# and third-party/cached search hits are skipped.
caffeinate -dimsu python3 -u tools/ops/directory_enqueue_autopilot.py \
  --apply \
  --batch-size 25 \
  --max-batches 8 \
  --uniform-cooldown-days 1 \
  --poll-interval-seconds 30 \
  --stall-timeout-minutes 20 \
  --max-transient-rate 0.25 \
  --max-permanent-other-rate 0.05 \
  --repair-min-enrollment 10000 \
  --repair-max-per-batch 5 \
  --repair-bing-fallback
```

The wrapper reads `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from
`.env`, calls `directory-enqueue?dry_run=true` before every real enqueue,
polls `archive_queue` for that run's `ready`/`processing` rows, calls
`refresh-coverage` after the run drains, then prints before/after
coverage histograms and watched status deltas for:

- `not_checked`
- `no_public_cds_found`
- `source_not_automatically_accessible`
- `cds_available_current`
- `extract_failed`

It also records every baseline, dry-run, enqueue, poll, drain, and
refresh event as JSONL in `scratch/directory-enqueue-runs/`. That
directory is intentionally uncommitted operator evidence.

After each applied batch, both `directory_enqueue_batches.py` and
`directory_enqueue_autopilot.py` run an extraction backlog audit unless
`--skip-extraction-backlog-audit` is passed. The audit reads
`cds_documents WHERE extraction_status='extraction_pending'`, prints the
pending count, oldest pending age, source-format buckets, oldest rows, and
high-enrollment pending rows, then writes the result into the JSONL run log.
By default it stops the wrapper if any pending row is older than 24 hours.
Use `--extraction-max-pending-age-hours N` to change that gate and
`--extraction-max-pending-count N` to add a hard backlog-size gate. During
launch drains, pass `--extraction-audit-github` to also require a recent
successful `.github/workflows/ops-extraction-worker.yml` run; the default
GitHub success freshness gate is 30 hours.

For unattended launch drains, `directory_enqueue_autopilot.py` wraps the
same batch workflow and then audits only the just-drained
`last_outcome='no_pdfs_found'` rows above the configured enrollment
threshold. Its repair ladder is intentionally narrow:

1. Try the free official-domain pattern ladder from `tools/finder/probe_urls.py`.
2. Optionally try Bing HTML search with `site:<school-domain> "Common Data Set"`.
3. Accept only URLs on the school's own root domain/subdomains.
4. If the hit is a landing page, archive only direct PDF/XLSX/DOCX links
   whose text or URL says CDS/Common Data Set.
5. Refresh coverage after any successful repair. Extraction can be run
   inline with `--extract-repaired` when the local worker environment has
   the dependencies installed.

Batch gate:

1. Capture the baseline that the wrapper prints: coverage histogram,
   top `not_checked` schools by enrollment, and current in-flight
   `archive_queue` rows with `source='institution_directory'`.
2. Dry-run every batch. Continue to the real enqueue only if the sample
   schools and skipped buckets look sane.
3. Wait for each `run_id` to drain before starting the next batch.
4. Run `refresh-coverage` immediately after each drained batch; the
   wrapper does this automatically in `--apply` mode.
5. Review the extraction backlog audit after each drained batch. Stop and
   run the extraction worker if the oldest pending row is older than 24
   hours, if high-enrollment rows are piling up, or if the GitHub ops
   worker has not succeeded recently.
6. Do not use `--force-recheck` for the first top-500 pass. The first
   pass should respect cooldowns, existing-CDS rows, in-flight rows, and
   curated schools.yaml exclusions.

`schools_yaml_covered` means "protected from the directory fallback,"
not "present anywhere in schools.yaml." Active schools with explicit
seed URLs remain owned by `archive-enqueue`, and `verified_absent` rows
remain manual/override-owned. YAML rows with `scrape_policy: unknown`
or `active` without a seed URL can be probed by `directory-enqueue`
using the Scorecard website URL, which closes the old dead zone where
those rows were neither archivable by `archive-enqueue` nor eligible for
directory batches.

Stop the rollout if any of these happen:

- More than 5% of a batch ends with unexpected `permanent_other`
  outcomes.
- `transient` outcomes exceed the configured warning gate and the run
  was started with `--stop-on-transient-gate`. For overnight drains,
  transient-heavy batches are logged and reviewed in the morning because
  they usually mean flaky school infrastructure rather than product
  corruption.
- The queue stalls for more than 20 minutes with no additional terminal
  rows.
- `directory-enqueue` or `refresh-coverage` returns an auth, load, or
  enqueue error.
- The coverage histogram is wildly implausible, for example the total
  row count shifts unexpectedly or a known-good bucket disappears.

Raw curl remains useful for debugging the Edge Function directly:

```bash
cd /Users/santhonys/Projects/Owen/colleges/collegedata-fyi
set -a && source .env && set +a

# Dry-run: see what the next batch of 50 high-enrollment schools would be.
curl -X POST "$SUPABASE_URL/functions/v1/directory-enqueue?limit=50&dry_run=true" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"

# Real run: enqueue 50 in-scope schools with at least 2,000 undergrads.
curl -X POST "$SUPABASE_URL/functions/v1/directory-enqueue?limit=50&min_enrollment=2000" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"

# State-scoped run.
curl -X POST "$SUPABASE_URL/functions/v1/directory-enqueue?limit=25&state=NY" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

Response shape:

```json
{
  "mode": "enqueue",
  "run_id": "<uuid>",
  "enqueued": 50,
  "considered": 5421,
  "skipped_existing": 0,
  "skipped": {
    "schools_yaml_covered": 837,
    "already_has_cds": 0,
    "in_flight": 0,
    "cooldown": 0,
    "no_website_url": 12,
    "below_min_enrollment": 4522
  }
}
```

Rows are inserted with `source = 'institution_directory'` and flow
through the same `archive-process` worker as schools.yaml-sourced rows.
The worker runs every 30 seconds, so a 50-school batch drains in ~25
minutes with the existing single-row claim cadence.

**Refresh the public coverage table on demand** (PRD 015 M3 — pg_cron
hits this every 15 minutes; manual invocation is for after-batch
debugging or when 15 minutes feels too long):

```bash
cd /Users/santhonys/Projects/Owen/colleges/collegedata-fyi
set -a && source .env && set +a

curl -X POST "$SUPABASE_URL/functions/v1/refresh-coverage" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

Response includes the rebuild row count, duration, and a histogram by
`coverage_status` so operators can spot precedence regressions at a
glance:

```json
{
  "rows_written": 6322,
  "refresh_duration_ms": 412,
  "total_duration_ms": 1106,
  "coverage_status_histogram": {
    "out_of_scope": 3398,
    "not_checked": 2853,
    "no_public_cds_found": 9,
    "cds_available_current": 60,
    "cds_available_stale": 2
  }
}
```

A wildly different histogram (e.g., zero `cds_available_current` when
schools.yaml has dozens of extracted documents) means the precedence
logic in `derive_coverage_status()` has regressed — read it from
`/supabase/migrations/<ts>_institution_cds_coverage.sql` to debug.

**Force-archive one school** (e.g. to re-try a `failed_permanent` row or
debug a resolver regression):

```bash
curl -X POST "https://<ref>.supabase.co/functions/v1/archive-process?force_school=yale" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

This bypasses the queue entirely and runs `archiveOneSchool()` directly.
Returns the action (`inserted` / `refreshed` / `unchanged_verified` /
`unchanged_repaired` / `marked_removed`) in the response body.

**Dry-run the resolver on one or more schools** (no writes, useful for
iterating on resolver logic):

```bash
curl "https://<ref>.supabase.co/functions/v1/discover?schools=yale,mit,fairfield" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

Response contains a `ResolveResult` per school with `kind` set to
`resolved` / `upstream_gone` / `transient` / `no_cds_found` /
`unsupported_content` / `blocked_url`.

Capped at 10 schools per request to keep memory bounded.

**Run extraction over archived pending rows:**

```bash
python tools/ops/extraction_backlog_audit.py
python tools/ops/extraction_backlog_audit.py --skip-github
python tools/extraction_worker/worker.py
python tools/extraction_worker/worker.py --limit 25
python tools/extraction_worker/worker.py --school yale
python tools/extraction_worker/worker.py --dry-run
```

`tools/ops/extraction_backlog_audit.py` is the pre-flight/status check for
the worker. It writes JSON reports to `scratch/extraction-backlog-audits/`
and exits non-zero when the configured gates fail. The default gate is:
oldest pending extraction row must be no older than 24 hours. The optional
GitHub gate checks the bounded ops workflow's last success so missing
secrets or a broken scheduled drain do not stay hidden behind healthy
archive/coverage numbers.

The worker detects or backfills `source_format`, writes one canonical
`cds_artifacts` row per successful extraction, and flips
`cds_documents.extraction_status` to `extracted`. Shipped routes:

| Source format | Producer | Notes |
|---|---|---|
| `xlsx` | `tier1_xlsx` | Deterministic template cell-position extraction. |
| `pdf_fillable` | `tier2_acroform` | Deterministic AcroForm extraction. |
| `pdf_flat` | `tier4_docling` | Docling + schema-targeting cleaner; v0.3 includes deterministic layout overlay. |
| `pdf_scanned` | `tier4_docling` | Same Tier 4 route with forced OCR. |
| `html` | `tier6_html` | HTML normalized to markdown, then passed through the Tier 4 cleaner. |
| `docx` | none yet | Tier 3 is designed but not implemented. |

**Run Tier 4 LLM fallback overlay:**

```bash
python tools/extraction_worker/llm_fallback_worker.py --limit 25
python tools/extraction_worker/llm_fallback_worker.py --school yale
```

The fallback is not a replacement producer. It writes
`producer='tier4_llm_fallback'`, `kind='cleaned'` artifacts for selected
subsections. Consumers and the browser projection merge it as a gap-fill only;
the deterministic cleaner wins conflicts.

**Refresh browser/public query projections:**

```bash
python tools/browser_backend/project_browser_data.py --full-rebuild --apply
python tools/browser_backend/project_browser_data.py --document-id <uuid> --apply
```

The projection is currently operator-run. New canonical artifacts do not
automatically update `cds_fields` or `school_browser_rows` until this worker
runs. This is tracked in [`docs/backlog.md`](backlog.md).

**Queue health snapshot:**

```sql
select status, count(*) from public.archive_queue group by status;
```

Historical note: the first full monthly drain (2026-04-14/15) produced `done: 535`,
`failed_permanent: 302`, `ready/processing: 0`. The 302 failure
bucket decomposes into: ~204 resolver "no year-bearing anchors"
(~68% of all failures — addressed by [ADR 0007](decisions/0007-year-authority-moves-to-extraction.md)
which moves year authority from discovery to extraction), ~51 HTTP
404 on stale hints, ~20 transient 403/timeout exhausted, ~11
content-type / magic-byte misses.

**2026-04-15/16 Stage B re-drain** (commit `6ea67a8`): archive queue
truncated and re-seeded against the new multi-candidate resolver.
Drained overnight in ~8 hours via the existing 30 s cron.

| Metric | Pre-drain (April 14/15) | Post-drain (April 16) | Delta |
|---|---|---|---|
| `cds_documents` rows | 518 | **1,675** | **+1,157** (3.2x) |
| Distinct schools with rows | 518 | **617** | **+99 new schools** |
| `archive_queue` done | 535 | **615** | +80 |
| `archive_queue` failed_permanent | 302 | **221** | **-81** (27% fewer) |
| `detected_year` populated | 380 | 380 | — (new rows need backfill) |

The "no year-bearing anchors" failure class is gone structurally —
direct-doc hints bypass year parsing and landing pages with
multi-year archives fan out into one `cds_documents` row per year.
Top fan-out schools: Bates and Cal Poly SLO (27 rows each),
Louisiana Tech / Michigan State / Montclair State (25 each),
Dartmouth (22), Harvard (18), Lafayette (19 — was `failed_permanent`
before Stage B). No schools lost rows; upsert semantics held.

At the time, the 1,295 newly archived rows had `detected_year = NULL` because
the extraction worker had not processed them yet. Later extraction drains
populated `detected_year` and `cds_manifest.canonical_year` for public
consumers.

Earlier versions of this runbook projected a "healthy steady state"
of `failed_permanent: <20` based on a 10-school hand-picked sample;
that target did not survive contact with the real corpus and has
been retired.

Current high-level corpus counters are maintained in
[`docs/extraction-quality.md`](extraction-quality.md). After the May 3 PRD
016B/018 drains and source-routing cleanup, production has `3,950` archived CDS
documents, `3,792` extracted rows, `200,957` `cds_fields` rows, `475`
`school_browser_rows`, and `383` `school_merit_profile` rows. Projection counts
can move down after cleanup because full rebuilds remove stale or
non-qualifying selected-result rows before repopulating.

**Recent cron executions:**

```sql
select j.jobname, jrd.runid, jrd.status, jrd.return_message,
       jrd.start_time, jrd.end_time
  from cron.job_run_details jrd
  join cron.job j on j.jobid = jrd.jobid
 where jrd.start_time > now() - interval '10 minutes'
 order by jrd.start_time desc
 limit 20;
```

**Recent pg_net HTTP calls** (what the cron is sending to the edge
functions):

```sql
select id, status_code, content_type,
       left(error_msg, 200) as error_msg,
       created
  from net._http_response
 where created > now() - interval '10 minutes'
 order by created desc
 limit 20;
```

**What failed this month and why:**

```sql
select school_id, last_error, processed_at
  from public.archive_queue
 where status = 'failed_permanent'
 order by processed_at desc;
```

**Manual retry of a specific failed row** (bypasses the queue cooldown):
use the `force_school` curl above.

### Reset / clean state

If you need to reset the pipeline (e.g. during a redesign):

```sql
-- Stop the cron jobs
select cron.unschedule('archive-process-every-30s');
select cron.unschedule('archive-enqueue-daily');

-- Truncate the work queue
truncate table public.archive_queue;

-- Optional: clear archived documents (destructive, use with care)
-- delete from public.cds_artifacts where kind = 'source';
-- delete from public.cds_documents;
```

Then re-run step 4 of the setup to re-schedule the cron jobs.

## Test suite

```bash
deno test supabase/functions/_shared/*.test.ts supabase/functions/browser-search/*.test.ts
python3 -m unittest tools/browser_backend/project_browser_data_test.py
python3 -m py_compile tools/extraction_worker/worker.py tools/browser_backend/project_browser_data.py
```

The Deno suite now covers more than the original resolver-only archive tests:

- **`year.test.ts`** — `YYYY-YY` canonicalization for the 7
  forms the corpus uses (long-long hyphen, long-long en-dash, underscore,
  space, long-short, short-short, no-separator 4-digit), millennium
  boundary, false positives (2021 is not a span), plausibility bounds,
  and the Brown `/sites/default/files/2020-04/CDS2009_2010.pdf` path-trap
  regression codex flagged in the PR 1-2 review. Note: per ADR 0007 these
  tests cover `normalizeYear`'s URL-hint semantics; the authoritative
  document year lives in `detected_year` and is tested by the Python
  extraction worker's harness, not here.

- **`resolve.test.ts`** — HTML anchor extraction, relative
  href resolution, CDS keyword filtering (hostname doesn't false-match
  commondataset.org), section-file detection via filename, document
  vs subpage categorization, malformed HTML, `findBestSourceAnchor`
  ranking (full-CDS beats section, more recent year beats older,
  test-artifact deprioritization, Lafayette CDS-digit filename
  regression), `findDownloadLinks` Digital Commons fallback, Google
  Drive URL rewriting (Stanford pattern), and the 8 `pickCandidates`
  cases for ADR 0007 Stage B multi-candidate fan-out (Lafayette-style
  multi-year landing page, single year-less candidate sentinel, mixed
  year-labeled + year-less drops, multi-candidate all-year-less null
  return, clean-vs-demoted partitioning, CSULB-style demoted fallback,
  cross-subpage URL dedup, empty-list pass-through), parent-landing walks,
  well-known CDS paths, Box URL rewrites, and Google Drive rewrites.

- **`hosting.test.ts` / `probe_outcome.test.ts` / `schools.test.ts`** —
  hosting-observation inference, auth-wall classification, cooldown windows,
  school-token normalization, and schools.yaml validation helpers.

- **`browser-search.test.ts`** — latest-per-school ranking, required-field
  operator semantics, `is blank` answerability, null handling for `!=`, variant
  scope, and SAT/ACT companion submit-rate metadata.

- **`project_browser_data_test.py`** — selected-result projection semantics,
  direct-vs-derived metric split, `sub_institutional` preservation, percent
  normalization, Tier 4 fallback overlay behavior, and PRD 012 academic-profile
  parsing/range checks.

Integration tests against a local Supabase stack (claim RPC concurrency,
NULL uniqueness, decision-table branches) are out of scope for this PR
and listed as a follow-up. The migration's inline self-test provides
basic regression coverage for the `NULLS NOT DISTINCT` constraint.

## Production verification summary

### Current status (as of 2026-05-03)

- Archive and extraction have produced `3,950` archived CDS documents and
  `3,792` extracted documents across the public corpus.
- Shipped extraction tiers are active for XLSX, fillable PDF, flattened PDF,
  scanned PDF, and HTML. DOCX remains a designed-but-unbuilt Tier 3.
- Tier 4 v0.3 layout-overlay extraction, PRD 016B admission-strategy cleanup,
  and PRD 018 H1/H2/H2A merit-profile cleanup have been drained into
  production and projected into public serving tables.
- The worker now prioritizes fresh CDS rows first; manual 2025-26 drain status:
  101 extracted, 16 failed, 1 not applicable, 0 pending.
- Public serving tables:
  - `200,957` `cds_fields` rows.
  - `475` `school_browser_rows` rows.
  - `383` `school_merit_profile` rows.

### Historical archive launch check (2026-04-14)

The original archive-only production check remains useful as provenance for the
queue and Storage path design:

- Both migrations applied cleanly via `supabase db push`.
- All three edge functions deployed successfully.
- Resolver dry-run returned correct results for yale (resolved 2024-25),
  mit (correctly classified `no_cds_found` — not falsely marked removed),
  and harvey-mudd (resolved 2025-26).
- `archive-process?force_school=yale` end-to-end: new `cds_documents`
  row, new `cds_artifacts(kind='source')` row, Storage object reachable
  at the public SHA-addressed URL.
- Idempotent re-run: second `force_school=yale` call returned
  `unchanged_verified`, no new artifact row, `last_verified_at` advanced
  by 14 seconds.
- `archive-enqueue` seeded 837 of 839 archivable schools (2 skipped as
  duplicate school ids in schools.yaml — worth investigating as a
  separate corpus cleanup task).
- 11 schools processed end-to-end via manual queue-mode ticks:
  - 9 `done` (davidson, harvard, harvey-mudd, stanford, yale,
    barnard, bates, carnegie-mellon, claremont-mckenna).
  - 2 `failed_permanent` (fairfield and mit, both from `no_cds_found`
    after two-hop walk — both are documented resolver gaps from the
    approved plan).
  - 1 transient (umich) correctly sent back to `ready` and bumped to
    the tail of the queue.

## Known issues

**Sub-institution schools.** The archive resolver still treats
`sub_institutions` conservatively. Downstream public surfaces preserve
`sub_institutional`, and `browser-search` defaults to primary rows where
`sub_institutional IS NULL`, but discovery still needs a richer resolver path
that can match landing-page anchors against each `sub_institutions[i].label` for
multi-CDS schools.

**Projection freshness.** Extraction writes canonical artifacts, but
`project_browser_data.py` is still operator-run. After a new extraction drain,
`cds_fields` and `school_browser_rows` are stale until the projection worker is
run. The backlog tracks wiring the projection into the extraction pipeline or a
scheduled incremental refresh.

**Tier 4 fallback artifact freshness.** Some `tier4_llm_fallback` artifacts were
generated against older Tier 4 markdown hashes. The selected-result projection
now excludes stale fallbacks unless they match the selected base artifact by
base artifact id or legacy markdown hash + cleaner version. The follow-up is
to re-run the fallback worker for the v0.3 corpus, then refresh browser
projections so compatible fallback values are visible again.

**XLSX academic-profile mapping audit.** PRD 012 found invalid SAT/ACT values in
some XLSX-derived rows that look like template alignment drift. Browser
projection range-checks and nulls those invalid score values, but the underlying
Tier 1 mapping needs a focused audit before XLSX SAT/ACT fields are treated as
fully launch-certified.

**Documentation divergence for stable path.** Earlier docs referenced
`sources/{school}/{year}/source.pdf` as the canonical path. The pipeline
now uses SHA-addressed paths instead; `docs/ARCHITECTURE.md` and
`docs/v1-plan.md` have been updated to reflect this. Any external
documentation or client code that assumes the old convention will need
updating — prefer `cds_manifest.source_storage_path` as the canonical
accessor.

## Resolved issues

**Resolver year requirement causing 68% of permanent failures (resolved
2026-04-15, commit `6ea67a8`).** The first full drain (2026-04-14/15)
classified 204 of 302 `failed_permanent` rows as "no year-bearing
anchors / no parseable year." ADR 0007 Stage B fixed this structurally:
direct-doc hints bypass year parsing entirely, landing pages return
every CDS-ish anchor via `pickCandidates`, and content-derived year
lives in `cds_documents.detected_year` (authoritative) exposed via
`cds_manifest.canonical_year`. The `no_cds_found` bucket still exists
for pathological cases (multi-candidate all-year-less landing pages
with no distinguishing signal) but the 204-row class is gone.

**Resolver losing multi-year historical depth on successful schools
(resolved 2026-04-15, commit `6ea67a8`).** 25% of successful schools
have HTML landing pages with an average of 14.2 distinct years
(Northern Michigan has 25, Allegheny 24, Lafayette 20). ADR 0007
Stage B `pickCandidates` now returns every qualifying anchor, so
the archiver fans out into one `cds_documents` row per year rather
than picking-then-discarding. Measured gain lands in this doc's
failure taxonomy once the post-Stage-B re-drain completes.

**pg_cron authorization 401 (resolved 2026-04-15).** Inner cron fired
on schedule, pg_net made the HTTP call, but every response was 401 at
Supabase's gateway layer. Root cause: during the one-time operator
setup, the SQL block to create the vault secret was copy-pasted with
its placeholder text `<paste SUPABASE_SERVICE_ROLE_KEY from your .env
here>` still in place, so the vault-stored "credential" was that
53-character English sentence. Direct curl with the real key worked
because the handler's own auth check used `Deno.env.get(...)` which
is injected by Supabase with the actual key. Fixed via
`vault.update_secret()` called against the live database. HTTP status
flipped from 401 → 200 on the next cron tick, confirmed in
`net._http_response`.

Mitigation baked into the operator runbook: the SQL block in this doc
makes the placeholder obvious, and the `trim()` wrapper added to both
cron bodies in the migration defends against whitespace in real-world
paste scenarios. A future improvement would be a dashboard link in the
operator setup that generates a ready-to-run SQL block with the actual
service role key already substituted in.

## ADRs touched

- ADR 0001 (Supabase-only architecture) — still holds. The archive
  pipeline is entirely on Supabase infrastructure, as specified.
- ADR 0006 (Tiered extraction strategy) — the "archive bytes are
  immutable" guarantee is now backed by SHA-addressed Storage paths,
  which is a stronger implementation of the same promise.
- [ADR 0007](decisions/0007-year-authority-moves-to-extraction.md)
  (Year authority moves to extraction) — Stages A + B + C shipped
  2026-04-15. Stage A (7c86e37) added content detection as an
  observation-only side channel. Stage B (6ea67a8) made detection
  write-authoritative via the new `cds_documents.detected_year`
  column, removed the resolver's URL year requirement, and landed
  `pickCandidates` multi-candidate fan-out. Stage C (9af6a5f) was
  de-scoped to docs-only; the full retirement of `cds_year` is
  tracked in [`docs/backlog.md`](./backlog.md).
