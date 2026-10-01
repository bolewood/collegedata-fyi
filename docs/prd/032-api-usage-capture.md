# PRD 032: Capture all public API usage, not just the friendly routes

**Status:** Rev 3 (2026-10-01). M0–M4 implemented; see "Implementation notes" for where the build differs from rev 2.
**Author:** Anthony Showalter (with Claude)
**Related:** [PRD 013](013-analytics-and-abuse-signal.md) (analytics and abuse signal), [`docs/api-usage-attribution.md`](../api-usage-attribution.md), migration `supabase/migrations/20260625120000_api_usage_events.sql`, `web/src/lib/api-usage.ts`

---

## What changed from rev 1

- **Aggregates, not per-request rows.** Third-party traffic is stored as
  client-hour aggregates. That stays under any Management API row cap,
  shrinks storage, and avoids keeping a per-request trail of which colleges
  a (probably young) visitor looked at.
- **Our own browser traffic is classified correctly.** Rev 1's rules counted
  the site's browser-side school search, and PDF clicks from school pages, as
  third-party. Rev 2 tags those paths and adds a `browser_unattributed` bucket
  for traffic from before the tags existed.
- **Tagging mechanics fixed.** supabase-js sends `X-Client-Info` with that
  exact casing, so overriding it with a lowercase key would merge two values.
  The friendly API needs its own client, and internal scripts that use the
  anon key need a rule of their own.
- **Salt scheme fixed.** Rev 1 derived daily salts from one long-lived
  secret, which made old hashes testable forever. Rev 2 generates a random
  salt each day and deletes it after two days.
- **Whole-hour recompute.** Rollups are rebuilt for whole hours only, under a
  workflow concurrency group, so a delayed or overlapping run can't overwrite
  an hour with partial counts.
- **A sibling table, not `api_usage_events`.** Folding PDF downloads into the
  existing table would silently change the meaning of every query in
  `docs/api-usage-attribution.md`. Rev 2 adds sibling tables and a union view.
- **Edge Functions come from `function_edge_logs`.** Function calls do not
  appear in `edge_logs` at all.
- **Endpoint spike first.** Retention and row limits were observed through
  Supabase's MCP log tool, not the token-based endpoint the job will call. M0
  verifies them before anything is built.
- **Public-CI hygiene and token scope.** The repo is public, so Actions logs
  and artifacts are public. Raw log rows must never reach them.

Follow-up the same day, from the Supabase docs:

- **`logs.all` is gone.** It returns `410 Gone`. The job uses
  `GET /v1/projects/{ref}/analytics/endpoints/logs`, which takes the same
  ClickHouse SQL as the MCP probe, so the dialect question is settled.
- **Scoped token instead of a bot account.** The org's Read-Only role is
  Team-plan only, so a bot account on Pro would need the broader Developer
  role. A scoped personal access token (public alpha) limited to this project
  with only **Logs: Read** is narrower.
- **The 06:00 UTC Azure client is not ours.** Anthony confirmed he runs
  nothing on Microsoft's cloud.

## Problem

`public.api_usage_events` records calls to the friendly API routes on
`www.collegedata.fyi/api/...`. It works: 306,598 events since June 25, and
about 72,000 since September 1 from named integrations, MCP clients, scripts,
and AI agents.

It does not see anything that hits `api.collegedata.fyi` directly. That domain
is a Supabase custom domain in front of PostgREST (`/rest/v1`), public Storage
(`/storage/v1/object/public/sources/...`, the archived PDFs), and Edge
Functions. Those are the surfaces the docs, the API page, and the bulk-data
recipes point people at. Today we cannot answer:

- How many third-party calls go to PostgREST and Storage each day?
- Who is bulk-walking the corpus, and are they identifying themselves?
- Which tables, views, and schools do outside users actually read?
- How much Storage egress is the public, as opposed to our own visitors?

Vercel Web Analytics cannot fill the gap. It counts only browsers that run its
script, so API clients, scripts, and PDF downloads are invisible to it.

## Goals

1. Count every request to the Supabase gateway (custom domain and raw
   `supabase.co` host), classified as internal pipeline, friendly-API
   upstream, our own site, unattributed browser, or third party.
2. For non-browser third parties, recognize a client within a day (client
   name, network owner, user-agent family, country, a salted client hash),
   without storing anything that identifies a person or links them across days.
3. Expose it next to the friendly-API data through one union view, so a single
   query answers "who uses collegedata, on which surface."
4. Run unattended: hourly, idempotent, recoverable after an outage, with a
   heartbeat in the existing pipeline-observation station table.

## Non-goals

- Rate limiting, blocking, or API keys. The API stays anonymous and public.
  Enforcement belongs to PRD 013 and needs this measurement first.
- Moving the domain to a proxy we operate (Cloudflare Worker or similar).
- Identifying individuals. Raw IP addresses, full user-agent strings, query
  strings, and request bodies are never stored. Browser traffic is never
  hashed.

## What the gateway logs already have

The probe ran read-only on 2026-10-01 through Supabase's MCP log tool
(ClickHouse SQL over the unified `logs` table) against project
`isduwmygvmdozhpvzaix`. The org is on the **Pro** plan. M0 must confirm that
the token-based Management API endpoint sees the same thing.

### Fields

PostgREST and Storage requests are `edge_logs` rows. These keys are present on
effectively all of them:

| Need | Log key |
|---|---|
| Surface and resource | `request.host`, `request.path`, `request.method` |
| Outcome | `response.status_code`, `response.headers.cf_cache_status`, `response.origin_time` |
| Client identity | `request.headers.user_agent`, `request.headers.x_client_info`, `request.headers.referer` (when sent) |
| Key | `request.sb.jwt.apikey.payload.role` for legacy JWT keys (`anon`, `service_role`); `request.sb.apikey.apikey.prefix` for new-style keys (`sb_secret_`, `sb_publishable_`); both absent for public Storage |
| Network and place | `request.cf.asOrganization`, `request.cf.country` |
| Client hash input | `request.headers.cf_connecting_ip`, `request.cf.botManagement.ja4` |
| Size | `response.headers.content_length`, `response.headers.content_range` |
| Query shape | `request.search` (used only to extract `school_id`) |

Caveats:

- `content_length` is present on only about a third of rows. It is reliable
  for Storage PDFs; PostgREST byte counts would be partial.
- `referer` appears on under 0.2% of rows, largely because our own PDF links
  use `rel="noopener noreferrer"` (`web/src/components/DocumentCard.tsx`).
- Custom request headers are not logged. Only a fixed set is (`user_agent`,
  `x_client_info`, `accept`, `prefer`, `range`, `referer`, `content_type`), so
  tagging has to use `User-Agent`, `X-Client-Info`, or `Referer`.
- No Cloudflare verified-bot field is logged. Bot detection is limited to what
  the client declares about itself.
- Storage cache hits are logged (1,607 `HIT`, 1,811 `MISS` in the probe day),
  so CDN-served PDFs are counted.

Edge Function calls are **not** in `edge_logs`. They are `function_edge_logs`
rows, which carry `request.pathname`, method, status, user agent, network
owner, country and IP, but not `X-Client-Info` or `Referer`. In the probe day,
2,733 of 2,758 function calls were our own `archive-process` cron. The public
`browser-search` function saw one `OPTIONS` request.

### Retention and limits (verified in M0 on the token endpoint)

These were measured on 2026-10-01 through
`GET /v1/projects/{ref}/analytics/endpoints/logs` with the scoped token.

- **Retention is a rolling 90 days.** At 17:38 UTC on October 1, the oldest
  row was July 3 at 17:31 UTC, and July 2 was empty. That is more than
  Supabase documents for Pro, so the job still alerts if retention shrinks.
- **Results are silently truncated at 1,000 rows.** Asking for `limit 5000`,
  or for no limit, returned exactly 1,000 rows with no error or flag. The job
  treats any result of exactly 1,000 rows as truncated, then splits the
  window and retries.
- **The rate limit is 10 queries a minute per token.** It is reported in
  `x-ratelimit-*` headers. After the budget ran out, requests kept getting
  `429` for one to four minutes, longer than the advertised 60-second reset.
  The job paces queries at least 7 seconds apart, and on a `429` waits five
  minutes before retrying.
- **Logs arrive within about a minute.** The newest row was about 40 seconds
  behind query time. Re-reading the same completed minutes four minutes later
  returned identical counts. Only the minute still in progress changed.
- **The 24-hour window cap is documented but wasn't enforced.** A 25-hour
  window returned data with no error, possibly clamped. The job never asks
  for more than 24 hours.
- **The query shape the job needs fits easily.** Grouping non-browser third
  parties by hour, IP, User-Agent, JA4 fingerprint and route gave 23 groups
  for the busiest hour (06:00 UTC on October 1, 4,331 requests) and 370
  groups for a full day.
- **`function_edge_logs` is reachable** with the same token.
- **No usage charge was seen.** About 20 queries returned no `402`, and nothing
  in the responses suggests metering.

### One day of traffic (Sep 30 12:00 to Oct 1 12:00 UTC)

| Bucket | Requests | Notes |
|---|---:|---|
| Our site, server side (`supabase-js-node`, anon key, AWS) | 247,699 | about 91% of gateway traffic |
| Our pipelines and Edge Functions | about 15,500 | 5,722 `service_role`; about 9,800 from our Edge Functions on the raw host with `sb_secret_` keys |
| Non-site PostgREST on the custom domain | about 4,700 | 4,308 from one unidentified Azure client; includes some of our own visitors' browser-side school searches |
| Public PDF downloads | 3,719 | 3.3 GB, about 1,400 IPs, about 410 schools; our visitors and third parties combined, which can't be told apart today |

The single biggest non-site PostgREST caller made 2,156 `school_merit_profile`
and 2,152 `school_facts_unified` requests in one burst at 06:00 UTC, one call per
school per view. It sends User-Agent `node`, no client marker, and comes from
one Microsoft network IP. It is confirmed not ours. This is the kind of client
the friendly-API table can never see.

Of PDF downloads, 1,862 came from browser-like user agents, 1,582 from
self-declared bots (Meta's indexer, `CollegeConnect-DataBot`, `RosterRoomBot`,
and others), and 205 from scripts.

## Design

### Overview

```text
api.collegedata.fyi / raw host ─▶ Supabase gateway ─▶ edge_logs, function_edge_logs
                                                          │ hourly, read-only SQL
                                                          │ (aggregated in SQL)
                                                          ▼
                                  tools/api_usage/ingest_gateway_logs.py
                                    classify · hash (non-browser only) · extract
                        ┌─────────────────────┬─────────────────────┴──────┐
                        ▼                     ▼                            ▼
          api_gateway_rollups_hourly  api_gateway_clients_hourly  api_gateway_schools_hourly
                (all traffic)        (non-browser third parties)   (per-school counts)
                        └───────────── view: api_usage_daily ◀── api_usage_events
```

### Step 1: tag our own traffic

Attribution only, never trust: anyone can send these headers. That is fine for
counting and would not be fine for rate limiting.

| Path | Change |
|---|---|
| `web/src/lib/supabase.ts` (site client, server and browser) | `global.headers: { "X-Client-Info": "collegedata-web/<sha>" }` from `web/src/lib/client-info.ts`. The exact `X-Client-Info` key replaces supabase-js's default instead of merging with it. |
| `web/src/lib/queries.ts` raw `fetch` | Same `X-Client-Info`. No User-Agent change: `X-Client-Info` alone classifies these. |
| `web/src/lib/browser-search.ts` raw `fetch` | Same `X-Client-Info`. The function's CORS already allows it. Function logs don't record it, so this is for consistency only. |
| Friendly API route handlers | A second client, from a small factory in `supabase.ts`, tagged `collegedata-friendly-api/<version>`. These requests are already counted at the route in `api_usage_events`, and the tag keeps them out of the third-party numbers. `public-data.ts` currently imports the shared site client, so this needs a small refactor. |
| PDF links (`DocumentCard.tsx` and siblings) | `rel={externalLinkRel(href)}`: `noopener` for archive files, so the browser default policy (`strict-origin-when-cross-origin`) sends `Referer: https://www.collegedata.fyi/`; other external links keep `noreferrer`. The Referer header does not affect the Storage or CDN cache key. |
| Python tools that call `api.collegedata.fyi` with the anon key (`tools/scorecard/build_alignment_gap_recipe.py`, `tools/ipeds/build_pricing_power_recipe.py`, `tools/ipeds/build_endowment_draw_rate_recipe.py`, `tools/ipeds/probe_releases.py`, `tools/discovery/cds_card_coverage.py`, and any others `rg api.collegedata.fyi tools` finds) | `User-Agent: collegedata-pipeline/<tool>` |

Rules match on **token contains**, not prefix. The cutover time T0 is a fixed
timestamp recorded in the ingest config when M2 is deployed, so re-ingesting
old windows gives the same answer.

### Step 2: classification

Evaluated in order:

1. **`internal_pipeline`:** a `service_role` JWT; a `sb_secret_` key; a
   User-Agent containing `collegedata-pipeline` or `collegedata-fyi`; or an
   internal-only Edge Function (`archive-*`, `directory-enqueue`, `discover`,
   `refresh-coverage`).
2. **`friendly_api_upstream`:** `X-Client-Info` contains `collegedata-friendly-api`.
3. **`first_party_site`:** `X-Client-Info` contains `collegedata-web`, or the
   `Referer` host is `collegedata.fyi` or `www.collegedata.fyi`.
4. **Before T0 only (flagged `inferred`):**
   - `supabase-js-node` with the anon key from an AWS network → `first_party_site`.
   - `supabase-js-web` with the anon key → `first_party_site`.
   - A browser-like User-Agent on Storage → `browser_unattributed`.
5. **After T0,** a browser-like User-Agent with no first-party marker →
   `browser_unattributed`. That covers PDF links shared elsewhere, browsers
   that strip Referer, and the like. It is never hashed.
6. **Everything else** → `third_party`.

Third-party rows reuse the `api-usage.ts` family rules (`mcp`, `cli`,
`integration`, `ai_agent`, `script`, `unknown`), plus:

- **`declared_bot`:** the User-Agent's product token matches a maintained list
  (`meta-webindexer`, `CollegeConnect-DataBot`, `RosterRoomBot`, …), or
  contains `bot`, `crawler` or `spider` as a whole word. `client_name` is the
  product token; the full string is not stored. The label means *self-declared*,
  not verified.
- **Self-identification:** a User-Agent like `acme-research/1.2` makes
  `acme-research` the `client_name`. The API page will ask bulk users to send
  one. It is the only marker that works on PostgREST: unknown query parameters
  break PostgREST filters, and custom headers are not logged.

### Step 3: tables

All three are new, RLS-enabled, and service-role-only, matching
`api_usage_events`. Each ingest run replaces whole periods, so re-running a
window is idempotent with no per-request dedupe key.

**`api_gateway_rollups_hourly`** holds all traffic. Key: `(hour, host, surface,
route_kind, classification, client_family, status_class, inferred)`. Values:
`requests`, `downloads` (Storage `200`s), `range_requests` (`206`s),
`cache_hits`, `response_bytes`. `OPTIONS` preflights are counted in their own
`route_kind` and left out of request totals. Size is low thousands of rows a
day. Kept indefinitely.

**`api_gateway_clients_hourly`** holds non-browser third parties only. Key:
`(hour, client_hash, surface, route_kind)`. Values: `client_family`,
`client_name`, `client_version`, `user_agent_family`, `network_owner`,
`country`, `requests`, `distinct_schools`, `status_4xx`, `status_5xx`,
`response_bytes`. Size is a few hundred rows an hour. Kept 400 days; a nightly
delete enforces this.

**`api_gateway_schools_hourly`** holds per-school counts: archive-file requests
from every caller, plus `school_id=eq.` lookups from third parties and
unattributed browsers. Key: `(hour, school_id, surface, classification)`.
Values: `requests`, `downloads`. It has no client hash, so school interest can't be joined back to
a client. `school_id` comes from `school_id=eq.<id>` in the query string or the
Storage folder. Nothing else from the query string is kept.

**`api_usage_daily` (view)** unions friendly-API daily counts from
`api_usage_events` with the gateway rollups, with a `source` column. The
existing queries in `docs/api-usage-attribution.md` keep their current meaning.

### Step 4: client hash and salts

- `client_hash = HMAC-SHA256(salt[day], ip ‖ user_agent ‖ ja4)`, truncated to
  16 hex characters. It is computed only for non-browser third parties.
- `salt[day]` is 32 random bytes created by the job on first use and stored in
  `api_usage_hash_salts (day, salt)`, a service-role-only table. It is deleted
  once that day's late-arrival window closes (day plus 2). There is no
  long-lived seed.
- Within a day the hash is **pseudonymous**: anyone holding the salt and a
  suspected IP, User-Agent and JA4 fingerprint could test for a match. After
  deletion, hashes from different days cannot be linked or tested. The IPv4
  space is small enough to brute-force an unsalted hash, which is why it is
  salted.
- Backfill creates salts for past days and deletes each one when that day
  finishes.

### Step 5: the job

- **Script:** `tools/api_usage/ingest_gateway_logs.py`. It writes through
  `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` over REST upserts, like the
  other ops jobs, and records a heartbeat through `tools/ops/record_heartbeat.py`
  in a new `pipeline_stations` row.
- **Queries:** one per log source per window, aggregated in SQL by hour, IP,
  User-Agent, JA4, surface, route, status and `school_id`. Hashing happens in
  Python, so raw IPs exist only in job memory. The SQL lives in one module, so
  a dialect change is a one-file edit. Any result of exactly 1,000 rows is
  treated as truncated, and the job halves the window and retries.
- **Pacing:** queries run at least 7 seconds apart, under the 10-a-minute
  limit. On a `429` the job waits five minutes, then retries.
- **Windows:** each hourly run re-processes the last three **whole** hours,
  `[floor(now) − 3h, floor(now))`, and replaces them. M0 measured log arrival
  at about a minute, so three hours is a wide margin. An hour is final once
  it falls out of that range. The watermark is the last final hour.
- **Budget:** an hourly run uses about six queries. A 90-day backfill in
  6-hour slices, two sources and two grains, is about 1,400 queries, or about
  three hours at the paced rate. That fits in one workflow run.
- **Schedule:** `ops-api-usage-ingest.yml`, hourly at minute 20, plus a
  `workflow_dispatch` backfill input (`--backfill-from`). Both share one
  `concurrency:` group, so a backfill and an hourly run never race. Backfill
  progress is tracked apart from the forward watermark in
  `api_usage_ingest_runs (mode, window_start, window_end, rows_read,
  rows_written, status)`.
- **Catch-up:** after an outage, the hourly run walks forward in 24-hour
  slices until it reaches the present, as long as the gap is inside retention.
- **Alerting:** the station heartbeat feeds the existing automation-health
  check. The job also alerts if the oldest queryable hour moves inside 7 days.

### Step 6: public-CI hygiene

The repo is public, so workflow logs and artifacts are public.

- The fetch layer returns parsed aggregates only. On an HTTP error it raises
  with the status code and Supabase's error message, never the response body.
- Exceptions are caught at the top level and re-raised without their local
  variables. Tracebacks do not print row data.
- The run summary and any artifact contain counts by classification, surface
  and family, with no IPs, hashes, User-Agents or school IDs.
- `--dry-run` writes the same aggregate summary to `scratch/api-usage/`.
- A test feeds a fixture full of IPs through the job with log capture on, and
  asserts that no IP string appears in stdout, stderr, the summary or any
  written row.

### Step 7: credentials

- **`SUPABASE_LOGS_TOKEN`:** a **scoped** personal access token, limited to
  project `isduwmygvmdozhpvzaix` with only the **Logs: Read** permission. A
  classic token carries every permission on every org and project its owner
  can reach, so a classic token must never be used here. If scoped tokens
  aren't enabled for the account (they're in public alpha), request access
  through Supabase support rather than falling back to a classic token. The
  token is rotated yearly.
- **`SUPABASE_URL`** and **`SUPABASE_SERVICE_ROLE_KEY`:** the existing ops
  secrets.
- No hash secret: salts live in the database and are deleted on schedule.

### Step 8: reporting

- Views `api_usage_daily` and `api_usage_top_clients_7d`. The second groups
  `api_gateway_clients_hourly` by `client_name`, falling back to `network_owner`
  plus `user_agent_family`.
- Update `docs/api-usage-attribution.md` with the new tables, the
  classification rules, sample queries, and a post-deploy canary.
- The API page and README ask bulk users to send a descriptive User-Agent,
  for example `your-project/1.0 (+https://your-site)`.
- Once a month, audit the top 20 third-party clients by hand for
  misclassified first-party traffic.

Weekly digests and alerts (a big new client, a jump in Storage egress) are
PRD 013's job. This PRD supplies the data.

## Implementation notes (rev 3)

Where the build differs from rev 2, and why:

- **Paging instead of window halving.** The endpoint accepts `LIMIT`/`OFFSET`.
  Every query orders by all of its group keys, so pages are deterministic; a
  live check paged 4,675 groups and the page totals matched the raw `count()`
  exactly.
- **Classification in Python over grouped dimensions.** SQL groups by the raw
  classification inputs (role, key prefix, `X-Client-Info`, referer host, user
  agent or browser flags, AWS flag, path segments). The busiest hour measured
  had 81 groups. Four grouped queries plus two `count()` checks per window:
  rollups (no IP), schools (no IP), clients (IP, User-Agent and JA4 only for
  rows a SQL prefilter can't rule out as first-party or browser), and
  `function_edge_logs`.
- **Atomic writes.** `api_usage_replace_window()` deletes and inserts a whole
  window in one transaction and rejects rows outside it. The function-log pass
  never touches client or school rows.
- **Schools table is hourly** and drops `client_family`, so whole-hour
  replacement works and per-school rows can't carry a client signature.
- **AI agents are never browsers.** User agents like `ChatGPT-User` and the
  Claude desktop app start with `Mozilla/`; anything that names a bot or AI
  agent is `ai_agent` or `declared_bot` and is hashed like other third parties.
  First-party rows use `client_family = 'first_party'`.
- **Salts are pruned by `api_usage_prune()`** at the end of every run
  (`day < today − 2`), which also enforces the 400-day client retention.
- **Workflow inputs** are `mode` (`hourly` or `backfill`), `days` and
  `dry_run`. Backfill uses 24-hour slices: about 10 queries a day, so 89 days
  takes about two hours. Hourly runs catch up from the last good window end.
- **Alerts:** six straight failed scheduled runs, or no logs from seven days
  ago (checked once a day at 03:00 UTC), open a pipeline alert issue.
- **T0** is `SITE_TAGGING_T0` in `tools/api_usage/classify.py`. The hour that
  contains T0 still uses inference.

## Relationship to PRD 013

PRD 032 **supersedes PRD 013's API measurement source.** PRD 013 rejected
"observe through Supabase logs only" because it can't enforce limits. That
still stands for enforcement, which stays with PRD 013, but logs are enough
for measurement. PRD 013's proposed `X-Internal-Traffic` header would never
appear in `edge_logs`, because custom headers aren't logged. Internal traffic
is marked through `X-Client-Info` and `User-Agent` as described above. PRD 013
should be updated to point here when this merges.

## Alternatives considered

| Option | Why not now |
|---|---|
| Per-request rows (rev 1) | Hits likely row caps; keeps a per-visitor trail of which schools were viewed; aggregates answer every question in Problem. |
| Reuse `api_usage_events` (rev 1) | Changes the meaning of existing attribution queries; that table's `request_source` is typed for the friendly API only. |
| Supabase log drain | Paid add-on and plan-gated. It pushes everything, including about 260,000 first-party rows a day we only want counted. Revisit if the hourly pull becomes unreliable. |
| Cloudflare Worker in front of `api.collegedata.fyi` | Real-time capture and rate limiting, but it moves the domain, adds a hop, and sends egress through a second provider. That's PRD 013's enforcement decision. |
| Logging inside PostgREST (`pre-request` hook) | Adds a database write to every read and misses Storage entirely. |

## Milestones

- **M0, endpoint spike. Done 2026-10-01.** The scoped token
  (`SUPABASE_LOGS_TOKEN`, Logs: Read on this project only, expiring
  2027-10-01) is stored as a GitHub Actions secret. Results are under
  "Retention and limits."
- **M1, schema, ingest and aggregate backfill.**
  - One additive migration: the three tables, the salts table, the runs table
    and the station row.
  - The ingest script, with tests covering classification, `school_id`
    extraction, bot-token parsing, whole-hour replacement, and "no IP in
    output."
  - Run the backfill as soon as M1 merges. Pre-T0 data uses the inference
    rules and is flagged, and about a day of history is lost for every day
    the backfill waits.
- **M2, tag first-party traffic (T0).** This can be built alongside M1. Ship
  the Step 1 changes and record T0. Then confirm in `edge_logs` that untagged
  `supabase-js-node` traffic from AWS falls to near zero and that our PDF
  clicks carry the site's `Referer`.
- **M3, hourly schedule.** Add the workflow, heartbeat, and alerts.
- **M4, views and docs.** Add the reporting views, update the attribution
  doc, add the User-Agent ask, and update PRD 013's pointer.

## Success criteria

- Within one day of T0, untagged `supabase-js-node` anon traffic from AWS is
  under 1% of first-party site requests.
- After T0, `browser_unattributed` PDF downloads fall clearly below the
  pre-T0 browser share. The remainder is links shared outside the site.
- For any final hour, rollup totals match a direct count of `edge_logs` and
  `function_edge_logs` for the same hour to within 1%.
- The ingest heartbeat is never more than 3 hours stale outside a declared
  outage, and a missed run self-heals on the next run.
- No raw IP, full User-Agent, non-`school_id` query parameter, or salt older
  than day plus 2 exists anywhere. This is enforced by the no-IP test and a
  canary query.
- The monthly top-20 audit finds no first-party traffic labeled `third_party`.

## Open questions

1. **Is log querying metered?** M0 saw no `402` and no usage signal across
   about 20 queries, but the endpoint documents a `402 Usage exceeded`
   response. Check the org usage page a week after M3 ships.
2. **Should the 06:00 UTC Azure walker be contacted?** It is confirmed not
   ours. It sends no User-Agent identity, so there is no way to reach it.
   Once the API page asks for a descriptive User-Agent, watch whether it
   starts sending one.
3. **Scoped-token availability.** Scoped tokens are in public alpha. If the
   permission picker doesn't appear when creating a token, request access
   through Supabase support.
4. **`browser-search` attribution.** Function logs carry no `X-Client-Info` or
   `Referer`, so first-party and third-party `browser-search` calls can't be
   separated. With about one call a day, it is classified by User-Agent only.
   Revisit if `/browse` traffic grows.
5. **Secret-key hygiene.** A `sb_secret_` key in a request from outside AWS or
   Azure is classified as internal, but would also mean the key leaked. The
   ingest counts those requests separately and alerts on any.
