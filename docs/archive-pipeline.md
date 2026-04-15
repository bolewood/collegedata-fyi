# Archive pipeline

The archive pipeline is the bridge between discovery (the finder corpus and
the M1a `discover` edge function) and extraction (the M2 Python worker). It
takes every active school in `tools/finder/schools.yaml`, resolves its
`cds_url_hint` to a direct document URL, downloads the bytes, hashes them,
writes provenance rows to `cds_documents` + `cds_artifacts`, and uploads
the source file to the `sources` Storage bucket. The M2 extractor then
polls `cds_documents WHERE extraction_status = 'extraction_pending'` and
does the structured extraction.

Runs on Supabase Edge Functions + pg_cron + pg_net. One school per edge
function invocation so the 400 s wall clock, 256 MB memory, and 2 s CPU
caps never bind. Each monthly batch of ~840 schools drains in ~7 hours of
wall clock.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  OUTER CRON  (daily, 02:00 UTC)                              │
│  pg_cron → net.http_post → archive-enqueue                   │
│                                                              │
│  archive-enqueue:                                            │
│    1. GET schools.yaml from GitHub raw                       │
│    2. Filter: scrape_policy=active AND cds_url_hint != null  │
│                AND sub_institutions is null                  │
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
│  Resolve: fetch hint, parse HTML, extract CDS anchors,       │
│           follow one hop of subpages (CMU pattern),          │
│           normalize year span (YYYY-YY canonical),           │
│           pick best anchor (prefer full-CDS over section,    │
│           prefer year-bearing, prefer recent).               │
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

### Files

| Purpose | Path |
|---|---|
| `cds_documents` NULL-uniqueness fix + `archive_queue` + claim RPC | `supabase/migrations/20260414170000_archive_pipeline.sql` |
| pg_cron schedules with vault-backed secrets | `supabase/migrations/20260414180000_archive_pipeline_cron.sql` |
| Year normalizer (`YYYY-YY` canonical) | `supabase/functions/_shared/year.ts` |
| HTML anchor extraction, two-hop, SSRF guard, discriminated resolver | `supabase/functions/_shared/resolve.ts` |
| `schools.yaml` fetch + filter + validation | `supabase/functions/_shared/schools.ts` |
| SHA-addressed Storage helpers (upload, head, path build) | `supabase/functions/_shared/storage.ts` |
| `cds_documents` + `cds_artifacts` data access | `supabase/functions/_shared/db.ts` |
| One-school pipeline orchestrator | `supabase/functions/_shared/archive.ts` |
| Resolver dev entry (dry-run, no writes) | `supabase/functions/discover/index.ts` |
| Queue consumer (30 s cron target + `force_school` backfill) | `supabase/functions/archive-process/index.ts` |
| Monthly seeder (daily cron target, deterministic per-month run_id) | `supabase/functions/archive-enqueue/index.ts` |
| Unit tests (28 tests: year normalizer, HTML extraction, Brown regression) | `supabase/functions/_shared/{year,resolve}.test.ts` |

## Storage path convention

Source files are stored at `sources/{school_id}/{cds_year}/{sha256}.{ext}`.
Every version of a school's CDS gets a unique path, so the archive is
truly immutable and crash-safe. Consumers never construct these paths
themselves — they read `cds_manifest.source_storage_path`, the view
column that picks the most recent `cds_artifacts` row with `kind='source'`
for each document.

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

2. Deploy all three edge functions:

   ```bash
   supabase functions deploy discover archive-process archive-enqueue
   ```

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

   Expected response shape:

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

**Queue health snapshot:**

```sql
select status, count(*) from public.archive_queue group by status;
```

A healthy steady state after a full monthly drain is `done: ~820`,
`failed_permanent: <20`, `ready/processing: 0` between runs.

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
deno test --allow-net supabase/functions/_shared/
```

28 tests:

- **`year.test.ts`** (16 tests) — `YYYY-YY` canonicalization for the 7
  forms the corpus uses (long-long hyphen, long-long en-dash, underscore,
  space, long-short, short-short, no-separator 4-digit), millennium
  boundary, false positives (2021 is not a span), plausibility bounds,
  and the Brown `/sites/default/files/2020-04/CDS2009_2010.pdf` path-trap
  regression codex flagged in the PR 1-2 review.

- **`resolve.test.ts`** (12 tests) — HTML anchor extraction, relative
  href resolution, CDS keyword filtering (hostname doesn't false-match
  commondataset.org), section-file detection via filename, document
  vs subpage categorization, malformed HTML, and `findBestSourceAnchor`
  ranking (full-CDS beats section, more recent year beats older,
  fallback to section if no full CDS).

Integration tests against a local Supabase stack (claim RPC concurrency,
NULL uniqueness, decision-table branches) are out of scope for this PR
and listed as a follow-up. The migration's inline self-test provides
basic regression coverage for the `NULLS NOT DISTINCT` constraint.

## Production verification summary (as of 2026-04-14)

**Proven working in production:**

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

**Sub-institution schools.** Columbia (and any other school with a
`sub_institutions` array) is intentionally excluded in V1 per
`filterArchivable`. Follow-up: add a resolver path that matches landing
page anchors against each `sub_institutions[i].label` to handle
multi-CDS schools.

**Two duplicate school ids in schools.yaml.** `archive-enqueue` returned
`enqueued: 837, skipped: 2` from 839 archivable inputs. The two skipped
rows come from duplicate `(enqueued_run_id, school_id)` tuples —
meaning schools.yaml has two entries sharing an id. Separate corpus
cleanup task.

**Documentation divergence for stable path.** Earlier docs referenced
`sources/{school}/{year}/source.pdf` as the canonical path. The pipeline
now uses SHA-addressed paths instead; `docs/ARCHITECTURE.md` and
`docs/v1-plan.md` have been updated to reflect this. Any external
documentation or client code that assumes the old convention will need
updating — prefer `cds_manifest.source_storage_path` as the canonical
accessor.

## Resolved issues

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
