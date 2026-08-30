# PRD 030: Public pipeline observation

**Status:** Implementing M0 — board, heartbeats, writers, JSON. Locked-door wall is M1.
**Created:** 2026-08-21
**Updated:** 2026-08-21 (eng review T1: match the codebase; split M0/M1)
**Author:** Anthony Showalter (with Cursor Grok, via CEO-design)
**URL:** `https://www.collegedata.fyi/pipeline-observation`
**Related:** [ARCHITECTURE](../ARCHITECTURE.md), [PRD 015 coverage](015-institution-directory-and-cds-coverage.md), [PRD 029 freshness](029-discovery-freshness-and-publish-alerts.md), [probe outcomes](../../supabase/functions/_shared/probe_outcome.ts), [design system](../../web/DESIGN_SYSTEM.md), [eng review](../../.context/prd-030-eng-review.md)

---

## One-line job

A public page that makes it impossible to miss a pipeline breakdown, and
that names every school whose CDS sits behind a lock we cannot open.

If this page had existed in April 2026, the monthly Brave finder sitting
unscheduled until August would have been a red lamp on day 40, not a
surprise four months later.

---

## Why this is not `/coverage`

| Page | Question it answers |
|---|---|
| `/coverage` | Do we have a public CDS for this school? |
| `/pipeline-observation` | Is our machine running, and what is blocking it? |

Coverage is a school ledger. This page is a **dispatch board**. Mixing
them would hide a dead cron behind 2,900 school rows. Keep both.

---

## Premise (CEO inversion)

The failure mode that actually happened: a job that "succeeds" when it
runs, while the job that finds new listings **never ran**. Archive-enqueue
re-verified existing PDF seeds on schedule. Coverage looked fine. The
finder was silent. Silence looked like health.

**Proxy to kill:** "last job succeeded" — including a manual
`workflow_dispatch` that resets a clock while the monthly schedule is
still missing.

**Metric that matters:** every SLA station has a **scheduled** heartbeat
inside its predicate, or the lamp is red. Missing data is red, not gray.

---

## Sequencing (D1)

Two PRs. Do not land M0+M1 together: the migration must come from
`main`, and the locked-door wall must not block the clocks.

| Slice | Ships | Does not ship |
|---|---|---|
| **M0** | Registry + heartbeats + RPC + facts function + writers + board + JSON + nav/footer/sitemap | Locked-door wall |
| **M1** | `pipeline_locked_doors`, override YAML, wall UI, JSON `locked_doors` populated | RSS |
| **M3** | Incident feed, reusing `cds_publish_events` as the event-log precedent | New event tables unless that pattern does not fit |

Writers ship with the M0 UI. A board without writers is a pretty lie.

---

## Calls already made

1. **Canonical route** `/pipeline-observation` (Next default: no
   trailing slash). Add `/pipeline` → `/pipeline-observation` **308** in
   `web/next.config.ts` next to `APEX_TO_WWW_REDIRECTS` (those are 301).
   `/pipeline-observation/` already 308s for free. Tests for both.
2. **No login.**
3. **Name schools** on the M1 wall. Civic, not dunking.
4. **Do not leak** stacks, service-role errors, Vault, GitHub secrets,
   `archive_queue.last_error`, `hosting.notes`,
   `tools/finder/school_overrides.yaml` (never parsed by this feature),
   signed SharePoint URLs, seed URLs with tokens.
5. **Heartbeat table is the source of truth.** Jobs write; the page
   reads a facts function. Do not scrape GitHub Actions from Vercel.
   `tools/ops/automation_health.py` stays operator-only (D9).
6. **Color is a scoped exception.** Site chrome stays paper/ink. Lamps
   are page-local CSS. **No teal, no blue.** `run` is ok-green with a
   hatched treatment plus the word `RUN` (D7).
7. **Nav:** `{ href: "/pipeline-observation", label: "Pipeline" }`
   immediately after Coverage in the module-local `SECONDARY_NAV_LINKS`
   (`web/src/components/Nav.tsx`). Footer: Pipeline **and** Coverage.
   Sitemap `web/src/lib/sitemap-static.ts` `daily` / `0.7` (update the
   guard test). `web/src/app/llms.txt/route.ts` bullet.
8. **Tableau / SharePoint IRM / Box / Drive / Dropbox / intranet are
   override-only (M1).** Auto-list is a **positive allowlist** of latest
   `archive_queue.last_outcome` in
   `{auth_walled_microsoft, auth_walled_okta, auth_walled_google, bot_challenge}`
   **and** `processed_at` within **120 days** (D5). Overrides are exempt
   from the 120-day rule. `wrong_content_type` is not auto-listed.
   `marked_removed` is not a lock.
9. **Machine faults vs school gates are visually split.**
10. **Lamps computed at read time** from `last_scheduled_status`. Dispatch
    cannot green a failed/missing schedule.
11. **Ad-hoc stations are not on the dispatch board.** Directory and
    mirror are a "Manual sources" footnote.
12. **JSON is M0.** `locked_doors` is `[]` until M1.

---

## Audiences, in order

1. Anthony at 11pm, scanning for quiet jobs.
2. A journalist / HN reader inspecting infrastructure.
3. An IR office that finds their school on the wall.
4. A contributor who must add a heartbeat or the board goes red.

Not an operator console. No enqueue / force_school buttons.

---

## Information architecture

```
1. § kicker + STATUS STRIP (sticky, above the 64px headline)
   Brick if any board station is `down`.
   Amber if any is `late` and none are `down`.
   Ok sentence only when every SLA station is `ok` or `run`.
   Every tile shows text (`DOWN` / `LATE` / `OK` / `RUN` / `SLATE`)
   plus `aria-label`. Color is not the only channel.

2. Headline + lede

3. DISPATCH BOARD

4. LOCKED DOORS (M1 only; M0 omits the section)

5. METHODOLOGY
```

Mobile: sticky strip; vertical tiles; M1 door groups accordion with
Tableau / SharePoint IRM / SSO open by default.

Headline: **The clocks, and the locked doors.**

---

## Stations

Eleven stations on the **dispatch board**, plus **Headless archive** as a
twelfth daily SLA. Finder's three **work** steps
get three tiles because they get three writes.

| `station_id` | Plain name | Actual job | Class | Overdue predicate |
|---|---|---|---|---|
| `finder_brave` | Finder (Brave search) | `ops-finder-probe.yml` step **Probe unknown schools** (`probe_urls.py` without `--ids-file`) | monthly SLA | `last_scheduled_status` not `ok` inside **40 days** |
| `finder_stuck_pdf` | Stuck PDF re-probe | same Action, step **Re-probe stuck PDF seeds** (`probe_urls.py --ids-file`). Not the unguarded `stuck_pdf_seeds.py` classifier, which runs twice and has no mode guard. | monthly SLA | same 40-day scheduled clock |
| `finder_landing_hints` | Landing-hint promotion | same Action, **Promote high-confidence landing hints**. Guarded by `INPUT_APPLY_LANDING_HINTS` only (not by mode). On `schedule`, that env is forced `true` (`ops-finder-probe.yml:63`). Do not spec a scheduled skip path. | monthly SLA | same 40-day scheduled clock |
| `archive_enqueue` | Archive enqueue | pg_cron `archive-enqueue-daily` (`0 2 * * *`) → `archive-enqueue` | daily SLA | `last_scheduled_status` not `ok` inside **36 hours** |
| `archive_process` | Archive process | pg_cron `archive-process-every-30s` → `archive-process` | continuous SLA | see below |
| `headless_archive` | Headless archive | `ops-headless-archive.yml` (Playwright crawl + ingest of WAF/JS landings) | daily SLA | `last_scheduled_status` not `ok` inside **36 hours** |
| `extraction_worker` | Extraction | `ops-extraction-worker.yml` (schedule `--limit 5`, `--deadline-minutes 25`) | daily SLA | see below |
| `coverage_refresh` | Coverage refresh | pg_cron `refresh-coverage-hourly` (`17 * * * *`) → `refresh-coverage` | hourly SLA | `last_scheduled_status` not `ok` inside **3 hours** |
| `serving_cache_refresh` | Public serving caches | pg_cron `refresh-public-serving-caches-hourly` (`23 * * * *`, plain SQL `refresh_public_serving_caches()`) (D4) | hourly SLA | `last_scheduled_status` not `ok` inside **3 hours** |
| `ipeds_release_probe` | IPEDS release probe | `ipeds-release-probe.yml` | monthly SLA | `last_scheduled_status` not `ok` inside **40 days**. A monthly no-op still writes `ok` with `new_release=false`. |
| `schema_build` | Schema (CDS year) | operator | yearly | `never` → slate. Down only if `last_finished_at` is non-null and older than **18 months**. Do not infer vintage from git. |
| `scorecard_load` | Scorecard load | operator | yearly | same 18-month rule |

`pg_cron` ticks use `last_trigger=cron` (**counts as scheduled**).
GHA `schedule` counts as scheduled. `dispatch` / `operator` never
update `last_scheduled_*`.

The three edge-function crons are **secret-gated and do not exist in
local/fresh DBs**. Seed migration and tests must **not** assert cron
rows. Heartbeat silence is the public signal.

**Manual sources** (below the board, not on the strip):
`directory_enqueue`, `mirror_ingest`.

**Not on the page:** IPEDS CSV load, `build_school_list.py`, PRD 019,
gated `/changes`, PRD 026 `/discover`. No
`publish_alerts` station. Playwright ingest is on the board as
`headless_archive`.

### Archive-process predicate

Finish-only heartbeat on **every tick**, including empty dequeues and
the existing `queue_drained` early return
(`supabase/functions/archive-process/index.ts`). Never writes `running`.
Keep the 30s upsert (~2,880/day); empty-queue liveness has no other
public signal. **Never key a cache on `updated_at`.**

Live unfinished count from the facts function:
`archive_queue.status IN ('ready','processing')`.
(`processing` exists only on `archive_queue.status`, not on
`cds_documents`.)

- Live unfinished > 0 AND no successful cron process in **15 minutes** → `down`
- Live unfinished = 0 AND no cron heartbeat in **2 hours** → `down`
- Else `last_scheduled_status=ok` → `ok`; `error` → `down`

This route uses **`revalidate = 60`**. `/coverage` stays **900**
(`web/src/app/coverage/page.tsx`). Do not copy `fetchCoverageRows`:
it **throws** on error and has an `isStaticBuild()` branch
(`web/src/lib/queries.ts`). The pipeline loader needs its **own**
try/catch and static-build path. Seed rows render `down`/`slate` on
failure; the page still paints.

`--lamp-run` is finder + extraction only.

### Extraction predicate (D2)

Today the worker summary (`tools/extraction_worker/worker.py` ~2174)
emits `processed_count`, `failure_count`, `stopped_early`,
`extraction_counts` — **not** `stopped_reason` / `extracted` /
`pending`. Cap is enforced in `ops-extraction-worker.yml` (hosted
`--limit` 100 max; schedule `--limit 5`). The worker slices
`docs[:args.limit]`. `--deadline-minutes` on schedule is **25**.

**M0 worker change (required, not a wrapper):** emit in `summary.json`:

- `stopped_reason`: `cap | deadline | complete | error`
- `extracted` (int)
- `failed` (int)
- `pending_remaining` (int; live count of
  `cds_documents.extraction_status = 'extraction_pending'` at finish)

Heartbeat step reads that file. `llm_fallback` is **not** required
(optional, from `extraction_counts` if cheap).

Collapsed lamp (scheduled clock only):

- No scheduled finish inside **36 hours** (including `never`) → `down`
- Live `extraction_pending` > 0 AND (`stopped_reason` in `{cap, deadline}`
  OR `extracted = 0`) → `late`
- Else → `ok`

Missing required keys on a finish write → `down` with
`error_code=heartbeat_summary_malformed`.

Empty drain still writes a scheduled heartbeat. Dispatch is a footnote.

Confirm an index on `cds_documents(extraction_status)` or add one in
the M0 migration so the pending count is not a seq scan every minute.

### Schedule vs dispatch

SLA lamps use **only** `last_scheduled_*`. Dispatch writes
`last_status` / `last_finished_at` / `last_summary` as a footnote.

Test: scheduled `error` yesterday + dispatch `ok` today = `down`.

**`on.schedule` CI is a lint**, not a detector. It would have caught
the April failure (schedule removed from the workflow file). It will
not catch disabled schedules, GitHub suppression, broken secrets, or
default-branch drift. Keep it labeled as lint: finder, extraction, and
IPEDS workflows contain `on.schedule`; station IDs in the registry
equal writer calls.

### Bootstrap

Migration seeds registry + heartbeat rows with
`last_scheduled_status = 'never'`. SLA `never` → `down` on first paint.
Yearly `never` → `slate`. Manual sources omitted from the strip. Board
stations are never dropped from the grid.

---

## Data model

### `pipeline_stations` (static registry, D8)

One row per `station_id`. Name, cadence_label, class, required/allowed
summary keys, `source_kind`. RPC validates writes against this table.
CI asserts every writer `--station` is a subset of the registry.
Seeded in the migration; not updated by jobs.

### `pipeline_heartbeats` (state)

One row per station, FK to the registry. Cron ticks write **finish
only**. GHA finder / extract / IPEDS write start (`running`) then
finish. Any `(class, last_status)` combo not in the lamp table → `down`.

`running` older than **8 hours** → `down`.

Anon **cannot** `SELECT` this table.

```
station_id                     text PK  FK pipeline_stations
last_started_at                timestamptz
last_finished_at               timestamptz   -- any trigger; footnote
last_status                    text          -- never | running | ok | error
last_trigger                   text          -- schedule | dispatch | operator | cron
last_summary                   jsonb         -- top-level keys only
last_scheduled_finished_at     timestamptz
last_scheduled_status          text
last_scheduled_summary         jsonb
last_scheduled_error_code      text
last_error_code                text
source_url                     text          -- sanitized GitHub URL or null
updated_at                     timestamptz   -- do not key caches on this
```

`error_code` closed set: `search_provider_rejected`,
`missing_required_secret`, `heartbeat_summary_malformed`,
`worker_timeout`, `job_failed`, `none`. Page maps code → copy. Raw
exception text is never stored.

### RPC `record_pipeline_heartbeat(station_id, status, trigger, summary, error_code)`

- Validates `station_id` against `pipeline_stations`.
- Unknown JSON keys dropped. Nested `counts.{…}` stripped.
  Keys are **top-level**.
- Missing required keys on **finish** → persist `error` +
  `heartbeat_summary_malformed`, not `ok`.
- `trigger` in `{schedule, cron}` copies into `last_scheduled_*`.
  `dispatch` / `operator` leave scheduled columns alone.
- `source_url` / `run_url`: only
  `https://github.com/bolewood/collegedata-fyi/actions/runs/<digits>`
  or `.../pull/<digits>`. Everything else dropped. Test the sanitizer.

**Grants (load-bearing — Supabase grants EXECUTE on new public
functions to anon by default):**

```
revoke all on function public.record_pipeline_heartbeat(text, text, text, jsonb, text) from public;
revoke all on function public.record_pipeline_heartbeat(text, text, text, jsonb, text) from anon, authenticated;
grant execute on function public.record_pipeline_heartbeat(text, text, text, jsonb, text) to service_role;
```

Precedent: `claim_archive_queue_row`, `refresh_institution_cds_coverage`.
Test: anon EXECUTE denied.

Reuse `SUPABASE_SERVICE_ROLE_KEY`. No new secret.

### `pipeline_station_facts()` (D3)

**SECURITY DEFINER function**, not a view. Owner-rights views reintroduce
the advisor warning cleared in `20260614141000`.

```
revoke all on function public.pipeline_station_facts() from public;
grant execute on function public.pipeline_station_facts() to anon, authenticated;
```

Returns, per registry station:

- heartbeat scheduled columns (no raw errors)
- `queue_unfinished` (archive_process only)
- `extraction_pending` (count of
  `cds_documents.extraction_status = 'extraction_pending'`)

The Next loader and JSON **only** call this function (and, in M1, select
`pipeline_locked_doors`). They never read `archive_queue` from the browser.

Lamps: `web/src/lib/pipeline-lamps.ts` + `pipeline-lamps.test.ts` with
an exhaustive fixture next to it (D6). **No Python lamp tests.**
`tools/ops/record_heartbeat.py` tests cover RPC payload validation only.

### `last_summary` required keys on finish

| station | required keys |
|---|---|
| `finder_brave` | `probed`, `found`, `replaced`, `budget_remaining` |
| `finder_stuck_pdf` | `stuck`, `reprobed`, `still_stuck` |
| `finder_landing_hints` | `proposals`, `promoted` |
| `archive_enqueue` | `queued`, `skipped`, `errors` |
| `archive_process` | `dequeued`, `queue_depth`, `inserted`, `refreshed`, `walled`, `events_written` |
| `headless_archive` | `schools_attempted`, `inserted`, `unchanged`, `failed` |
| `extraction_worker` | `extracted`, `failed`, `pending_remaining`, `stopped_reason` |
| `coverage_refresh` | `current`, `stale`, `inaccessible`, `never_found` |
| `serving_cache_refresh` | `ok` (bool) |
| `ipeds_release_probe` | `new_release`, `issue_opened` |
| `schema_build` | `years` |
| `scorecard_load` | `vintage`, `rows` |
| `directory_enqueue` | `seeded` |
| `mirror_ingest` | `source`, `rows_added` |

`events_written` is on **`archive_process`**, not enqueue.
`recordPublishEvent` is reached from `_shared/archive.ts` via
archive-process and archive-upload only.

Optional shared: `pr_url`, `run_url` (sanitized). No free-form `notes`.
`coverage_refresh` may set `overrides_stale: true` in M1 if the override
YAML fetch failed (last-good rows kept).

### Writers (M0)

Helper: `tools/ops/record_heartbeat.py` with
`tools/ops/test_record_heartbeat.py` (co-located, like other Python
packages). There is no `tools/pipeline/` or `tests/fixtures/` tree today;
do not create them.

Finder writes are **separate steps** with `id:`. `if: always()` on the
same step as a mode guard is wrong. Pattern:

```yaml
- id: re_probe_stuck
  name: Re-probe stuck PDF seeds
  if: env.INPUT_MODE == 'both' || env.INPUT_MODE == 'stuck-pdf'
  run: python tools/finder/probe_urls.py --ids-file …   # not stuck_pdf_seeds.py
- name: Heartbeat finder_stuck_pdf
  if: always() && (env.INPUT_MODE == 'both' || env.INPUT_MODE == 'stuck-pdf')
  run: python tools/ops/record_heartbeat.py --station finder_stuck_pdf …
```

Same pair for `probe_unknown` → `finder_brave` and
`promote_landing_hints` → `finder_landing_hints`.
A `stuck-pdf`-only run does not write `finder_brave`.

Heartbeat POST failure: **exit 0** and print
`::warning::pipeline heartbeat failed for <station>` so it shows in the
Actions summary, not only logs. Same for Deno `finally` writers: catch,
log, do not throw.

`serving_cache_refresh`: write from `refresh_public_serving_caches()`
(SQL) or a one-line wrapper in that function. Finish only, `trigger=cron`.

`archive_enqueue` / `archive_process` / `coverage_refresh`: Deno
`finally`, finish only, `trigger=cron`.

### `pipeline_locked_doors` (M1 only)

Table refreshed by `refresh_pipeline_locked_doors()`, called from
`refresh-coverage`. Service role. **Own** `DISTINCT ON (school_id)
ORDER BY processed_at DESC, id DESC` using
`archive_queue_terminal_latest_idx`. **Do not** call
`latest_archive_terminal_rows(p_since, …)` — it is time-bounded and
will silently miss old locks.

Overrides file: `tools/finder/locked_door_overrides.yaml` (same
directory as `school_overrides.yaml` and `schools.yaml`). Fetched from
GitHub `main` raw, same pattern as
`supabase/functions/_shared/schools.ts`. Fetch fail → keep last good
rows + `overrides_stale: true` on the coverage heartbeat. **Never
parse or import `tools/finder/school_overrides.yaml`.** Test that.

Join names from `institution_cds_coverage` (**table**, not a view):
`school_name`, `undergraduate_enrollment`, `state`, `coverage_status`,
`school_id`, `ipeds_id`. Alias to `name` / `enrollment` only in the
TypeScript loader, not in SQL.

**Drop `final_host`.** `archive_queue` has no host column;
`latest_school_hosting.final_url_host` is forbidden (anon revoked;
unsafe). Do not add a hostname column in M1.

#### Override YAML

Keyed by `school_id`. Closed `reason_key` only. CI rejects URLs, query
strings, emails, token-shaped strings, unknown keys.

Sample IDs from `tools/finder/schools.yaml` (do not invent UNITIDs):

```yaml
- school_id: ohio-university-main-campus
  ipeds_id: "204857"
  kind: sharepoint_irm
  reason_key: excel_online_download_blocked
- school_id: pomona-college
  ipeds_id: "121345"
  kind: tableau
  reason_key: tableau_view_not_file
- school_id: colorado
  ipeds_id: "126614"
  kind: sharepoint
  reason_key: sharepoint_folder
```

M1 does not merge without Ohio + Pomona. Colorado is the third
SharePoint fixture. Negative tests: HTML must **not** contain
`sharepoint.com/:x:`, the Ohio sharing token, `H1 review`, or
Pomona `force_urls` — those strings live in `school_overrides.yaml`
and must never leak.

#### Auto-list (positive allowlist + D5 recency)

Include if **latest** terminal `last_outcome` is in
`{auth_walled_microsoft, auth_walled_okta, auth_walled_google, bot_challenge}`
**and** `processed_at >= now() - interval '120 days'`.
Else drop, unless an override applies (overrides skip the 120-day rule).

`inserted` / `refreshed` / `unchanged_verified` / `unchanged_repaired`
/ `marked_removed` / `wrong_content_type` / anything else → not auto-listed.

#### Closed copy

| reason_key / kind | Copy |
|---|---|
| `microsoft_sso` | Redirects to login.microsoftonline.com. |
| `okta_sso` | Redirects to an Okta login. |
| `google_sso` | Redirects to accounts.google.com. |
| `bot_challenge` | School CDN served a bot challenge instead of the file. |
| `excel_online_download_blocked` | Listed in Excel Online with download blocked. |
| `tableau_view_not_file` | CDS is a Tableau view, not a downloadable file. |
| `sharepoint_folder` | CDS files sit in a SharePoint folder we cannot archive as a file. |
| `box` / `google_drive` / `dropbox` / `intranet` | Closed one-liners; override-only. |

Public columns: `school_id`, `ipeds_id`, `name` (from `school_name`),
`state`, `enrollment` (from `undergraduate_enrollment`), `kind`,
`vendor_label`, `reason_key`, `public_reason` (generated),
`last_observed_at`, `coverage_status`. No host, no path, no query string.

Anon `SELECT` on those columns only.

---

## Lamps

Computed in `web/src/lib/pipeline-lamps.ts` from facts + the fixture.
Jobs never write a lamp. SLA stations use `last_scheduled_status`.

| Lamp | CSS | Ink | Predicate |
|---|---|---|---|
| `down` | `--lamp-down` `#d7263d` | white | scheduled predicate failed, OR scheduled `error`, OR `running` > 8h |
| `late` | `--lamp-late` `#e0a106` | `#1c1400` | extraction backlog only |
| `ok` | `--lamp-ok` `#1f7a4d` | white | scheduled `ok` AND not `late` |
| `run` | same `--lamp-ok` + CSS hatch (no new hue) | white | GHA `running` within 8h; finder + extraction only |
| `slate` | `--lamp-slate` `#5c5a54` | white | yearly `never` or yearly inside 18 months |
| `lock` | `--lamp-lock` `#6b3fa0` | white | M1 chips |
| `sso` | `--lamp-sso` `#7a2f6a` | white | M1 SSO chips |
| `waf` | `--lamp-waf` `#c45c14` | white | M1 bot_challenge chips |

Error is never `late`. Test 13 = page-CSS **hex allowlist** (these
hexes plus paper/ink tokens). No `#2a9d8f`, no blue.

Door cards: `--paper` / `.cd-card` (`tokens.css`). Page-local CSS:
`web/src/app/pipeline-observation/pipeline-observation.css`.
`web/DESIGN_SYSTEM.md` gets a "Pipeline observation exception"
subsection.

---

## Public JSON (M0)

`GET /pipeline-observation.json` (`revalidate = 60`):

```
{
  "as_of": "ISO-8601",
  "strip": { "lamp": "down|late|ok", "text": "…" },
  "stations": [{ "station_id", "lamp", "label",
                 "last_scheduled_finished_at", "last_scheduled_status",
                 "last_finished_at", "last_trigger", "summary",
                 "error_code" }],
  "locked_doors": [],
  "manual_sources": [{ "station_id", "last_finished_at" }],
  "methodology_url": "https://www.collegedata.fyi/pipeline-observation#methodology"
}
```

M1 fills `locked_doors`. Snapshot test: shape, precomputed lamps, no
secret-shaped strings.

---

## Public-safe / threat model

**Allowed:** station names, cadences, timestamps, allowlisted counts,
sanitized Actions/PR URLs, school names, UNITIDs, lock kinds,
coverage_status, enrollment.

**Forbidden:** stacks; Deno logs; `last_error`; Storage paths; cron SQL;
Vault; `BRAVE_API_KEY` presence (`search_provider_rejected` only);
redirect chains; cookies; signed query strings; operator notes;
`school_overrides.yaml`; hostnames we cannot legally source.

**Anon surface (final-grants test):**

- CAN: `EXECUTE pipeline_station_facts()`; `SELECT` on
  `pipeline_locked_doors` public columns (M1).
- CANNOT: `EXECUTE record_pipeline_heartbeat`; `SELECT`
  `pipeline_heartbeats`, `archive_queue`, `latest_school_hosting`,
  `bot_challenged_documents`. (`bot_challenged_documents` was granted
  to anon in `20260505160000` and revoked in `20260614141000` — pin
  that with this test.)

---

## Error & empty states

| State | User sees |
|---|---|
| Facts fetch fails | Brick: "Could not load station clocks." Seed rows `down`/`slate`. Page paints. |
| Locked-doors fetch fails (M1) | Board still shows. "Could not load the lock list." |
| Zero locked doors | "No vendor locks in the current snapshot. Tableau and SharePoint IRM only appear when listed in the public override file." |
| `isStaticBuild()` | Fixture/seed lamps, no live RPC. |

---

## Implementation slices

**M0 PR:** `pipeline_stations` + `pipeline_heartbeats` + RPC grants +
`pipeline_station_facts()` + `record_heartbeat.py` + worker summary
fields + workflow `id:` / heartbeats + edge-function writers +
`serving_cache_refresh` + page/JSON/lamps/CSS/nav/footer/sitemap/llms.txt
+ `/pipeline` 308 + loader try/catch + `isStaticBuild` +
`on.schedule` lint + hex allowlist test + stale cron name fix in
`automation_health.py` + TODO to read heartbeats.

**M1 PR:** locked-doors table + refresh + YAML + wall + JSON fill +
never-parse-`school_overrides` test + Ohio/Pomona/Colorado fixtures +
120-day recency.

**M3:** RSS of overdue transitions; reuse `cds_publish_events` as the
append-only precedent (`web/src/lib/school-rss.ts`), do not invent a
second event-log style unless that table cannot represent station
transitions.

Lane A (migration/RPC/facts) and Lane B (Python/workflows) and Lane C
(web against fixtures) can parallelize after M0 migration exists.
M1 waits on M0 because both touch `supabase/migrations/`.

---

## What already exists (reuse)

- `/coverage` public RLS + ISR **pattern** (900s, not 60s)
- `probe_outcome.ts` (all 16 values)
- `archive_queue.last_outcome` + `archive_queue_terminal_latest_idx`
- `institution_cds_coverage` table (`school_name`,
  `undergraduate_enrollment`)
- Actions `SUPABASE_SERVICE_ROLE_KEY`
- Edge functions on service role
- `schools.yaml` GitHub-raw fetch
  (`supabase/functions/_shared/schools.ts`)
- `.cd-card`, `SECONDARY_NAV_LINKS`, sitemap guard test
- `tools/ops/automation_health.py` (operator; stale job name
  `refresh-coverage-every-15min` at line 21 — fix to
  `refresh-coverage-hourly` and add `refresh-public-serving-caches-hourly`;
  TODO to read `pipeline_heartbeats` and drop GHA scraping)
- `cds_publish_events` + school RSS renderer (M3 precedent)
- `archive_queue_attempts` is per-item, service-role only — not a
  heartbeat log

`HOSTING_OBSERVATIONS_ENABLED` defaults **off**.
`latest_school_hosting` / `bot_challenged_documents` already revoked
from anon.

---

## NOT in scope

- Operator controls; crawl tail; replacing `/coverage`; global recolor
- Email / PagerDuty
- Automatic Tableau / IRM detection
- Seed URLs / SAS tokens
- IPEDS CSV load, `build_school_list`, PRD 019, Playwright, `/changes`
- Recent-results history UI
- Incident RSS (M3)
- `publish_alerts` station
- Rewriting `automation_health.py` beyond the stale name + TODO (D9)
- Owner-rights views for facts
- Reusing `latest_archive_terminal_rows` for the wall
- Python lamp tests / `tests/fixtures/` / `tools/pipeline/`
- Teal `--lamp-run #2a9d8f`

---

## Tests (Friday-night + eng-review gaps)

1. Scheduled `error` yesterday + dispatch `ok` today → `down`.
2. Seed `never` → SLA `down`; yearly `slate`; manual sources off strip.
3. `archive_process`: unfinished=0, cron 30s ago → `ok`; 3h ago → `down`; unfinished>0, 20 min → `down`.
4. RPC `{queue_depth:3, stack:"…"}` keeps `queue_depth`, drops `stack`; nested `counts.*` dropped.
5. Anon EXECUTE denied on `record_pipeline_heartbeat`.
6. Final-grants: anon cannot select heartbeats / archive_queue / latest_school_hosting / bot_challenged_documents; can execute facts.
7. Malformed finish → `error` + `heartbeat_summary_malformed`.
8. `running` > 8h → `down`.
9. Exhaustive (class, status, age) lamp matrix in `pipeline-lamps.test.ts`.
10. Heartbeat POST failure exits 0 and prints `::warning::`.
11. Worker summary contains `stopped_reason` / `extracted` / `failed` / `pending_remaining`; cap → `late`.
12. `isStaticBuild()` path renders seed lamps.
13. `/pipeline` 308 and `/pipeline-observation/` 308 tests; sitemap-static guard updated.
14. JSON snapshot: `as_of`, precomputed lamps, no secret-shaped strings; hex allowlist (no teal, no blue).
15. Finder: `stuck-pdf` mode does not bump `finder_brave`; heartbeats keyed off re-probe / unknown / promote steps (`id:` present).
16. IPEDS scheduled no-op writes `ok` / `new_release=false`.
17. Seed migration does **not** require pg_cron rows.
18. **M1:** Ohio `204857` + Pomona `121345` + Colorado; HTML lacks `sharepoint.com/:x:`, tokens, `H1 review`, `force_urls`.
19. **M1:** YAML fetch fail → last-good + `overrides_stale`.
20. **M1:** refresh never parses `school_overrides.yaml`.
21. **M1:** latest lock older than 120 days dropped unless override; `marked_removed` not listed; `wrong_content_type` not listed.
22. [E2E, later] scheduled finder run → three tiles `ok` within 60s ISR.

---

## Dream state (12 months)

```
  NOW                         M0 THEN M1                 12 MONTHS
  Jobs are folklore.    →   Public overdue lamps.  →  New job without
  Brave silent 4 months.    Named vendor locks.       a registry row
  Tableau in operator       Scheduled ≠ dispatch.     cannot merge.
  notes.                    World can inspect.        Incident RSS.
```

---

## Decisions locked (eng review D1–D9)

| # | Decision | Letter |
|---|---|---|
| D1 | Two PRs: M0 board, then M1 wall | A |
| D2 | Worker emits `stopped_reason` / `extracted` / `failed` / `pending_remaining`; collapsed lamp | A |
| D3 | `pipeline_station_facts()` SECURITY DEFINER function; grant EXECUTE to anon | A |
| D4 | Add `serving_cache_refresh` | A |
| D5 | Auto-list latest lock outcome within 120 days; overrides exempt | A |
| D6 | Lamps: `web/src/lib/pipeline-lamps.ts` + `.test.ts` only | A |
| D7 | Drop teal; `run` = ok-green hatch + RUN text; hex allowlist | A |
| D8 | Split `pipeline_stations` registry from `pipeline_heartbeats` | A |
| D9 | Fix stale cron name in `automation_health.py`; TODO to read heartbeats | A |

---

## Review changelog

**Round 1 (6/10) / Round 2 (8/10 inherit + 7/10 Codex):** silence is
red; three finder writes; scheduled ≠ dispatch; public-safe copy;
JSON in M0.

**Eng review 2026-08-21** (`/plan-eng-review`, Codex outside voice):
architecture kept; implementation blocked until this T1 pass. Corrected
`extraction_pending`, worker summary, `events_written` station, coverage
column names, Ohio UNITID `204857`, finder step mapping, pg_cron names,
fourth cron, ISR/loader, paths, grants, recency allowlist, two-PR split.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO / design | CEO-design + adversarial | Scope | 2 | patched | 6/10 then 8/10 |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | T1 applied; D1–D9 locked | 8 arch, 6 quality, 12 test gaps originally |
| Codex | outside voice | Independent | 1 | 13 points folded | 3 tensions resolved as D9/lint/keep-30s |

**VERDICT:** Spec is the build contract. Implement M0, then M1. Do not
start until this file is what the PR is measured against.
