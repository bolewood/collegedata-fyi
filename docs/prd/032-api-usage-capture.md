# PRD 032: Capture all public API usage, not just the friendly routes

**Status:** Draft (2026-10-01). Feasibility probe done; see "What the gateway logs already have."
**Author:** Anthony Showalter (with Claude)
**Related:** [PRD 013](013-analytics-and-abuse-signal.md) (analytics and abuse signal), [`docs/api-usage-attribution.md`](../api-usage-attribution.md), migration `supabase/migrations/20260625120000_api_usage_events.sql`, `web/src/lib/api-usage.ts`

---

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
- How much Storage egress is the public, as opposed to our own site?

Vercel Web Analytics cannot fill the gap. It counts only browsers that run its
script, so API clients, scripts, and PDF downloads are invisible to it.

## Goals

1. Count every request to `api.collegedata.fyi` and classify it as our own
   site, our own pipelines, a friendly-API upstream call, or a third party.
2. For third-party traffic, record enough to recognize a client across days
   (client name, network owner, user-agent family, country, a salted client
   hash) without storing anything that identifies a person.
3. Land it in the same `api_usage_events` table, so the queries in
   `docs/api-usage-attribution.md` work across all surfaces.
4. Run unattended: hourly, idempotent, recoverable after an outage.

## Non-goals

- Rate limiting, blocking, or API keys. The API stays anonymous and public.
  Enforcement belongs to PRD 013 and needs this measurement first.
- Moving the domain to a proxy we operate (Cloudflare Worker or similar).
- Identifying individuals. Raw IP addresses, full user-agent strings, query
  strings, and request bodies are never stored.

## What the gateway logs already have

The probe ran read-only on 2026-10-01 through the Supabase logs query tool
(ClickHouse SQL over the unified `logs` table) against project
`isduwmygvmdozhpvzaix`. The org is on the **Pro** plan.

### Fields

Every request through the Supabase gateway is an `edge_logs` row. These keys
are present on effectively all rows, so the capture does not depend on
anything we have to switch on:

| Need | Log key |
|---|---|
| Surface and resource | `request.host`, `request.path`, `request.method` |
| Outcome | `response.status_code`, `response.headers.cf_cache_status`, `response.origin_time` |
| Client identity | `request.headers.user_agent`, `request.headers.x_client_info` |
| Key role | `request.sb.jwt.apikey.payload.role` for legacy JWT keys (`anon`, `service_role`); `request.sb.apikey.apikey.prefix` for new-style keys (`sb_secret_`, `sb_publishable_`); both absent for public Storage |
| Network and place | `request.cf.asOrganization`, `request.cf.country`, `request.cf.region`, `request.cf.city` |
| Client hash input | `request.headers.cf_connecting_ip`, `request.cf.botManagement.ja4` |
| Dedupe key | `request_id` |
| Size | `response.headers.content_length`, `response.headers.content_range` |
| Query shape | `request.search` (the query string, used only to extract `school_id`) |

Two caveats from the probe. `content_length` is present on only about a third
of rows: it is reliable for Storage PDFs, but PostgREST responses are mostly
chunked, so PostgREST byte counts would be partial. `referer` appears on fewer
than 0.2% of rows, so it is not a useful signal on this domain.

Custom request headers are not logged, only a fixed set (`user_agent`,
`x_client_info`, `accept`, `prefer`, `range`, `referer`, `content_type`). Any
tagging we add has to ride on `User-Agent` or `x-client-info`.

### Retention and limits

- **Retention reaches about 90 days.** On October 1, logs from July 4 were
  queryable and July 2 returned nothing. Supabase documents a shorter Pro
  window, so the design must not depend on 90 days. But it means a one-time
  backfill can recover roughly the last three months, and that window shrinks
  by one day every day until the backfill runs.
- **One query covers at most 24 hours.** An hourly job is well inside that.
- **Row caps on the Management API are unverified.** The design aggregates in
  SQL and slices time windows small enough to stay under any cap.

### One day of traffic (Sep 30 12:00 to Oct 1 12:00 UTC)

| Bucket | Requests | Notes |
|---|---:|---|
| Our site (`supabase-js-node`, anon key, AWS) | 247,699 | about 91% of all gateway traffic |
| Our pipelines and Edge Functions | about 15,500 | 5,722 `service_role`; about 9,800 from our Edge Functions on the raw `supabase.co` host with `sb_secret_` keys |
| Third-party PostgREST (custom domain) | about 4,700 | 4,308 of these from one unidentified Azure client |
| Third-party Storage PDF downloads | 3,719 | 3.3 GB, about 1,400 IPs, about 410 schools |

The single biggest third-party PostgREST caller made 2,156 `school_merit_profile`
and 2,152 `school_facts_unified` requests in one burst at 06:00 UTC, one call per
school per view. It sends User-Agent `node`, no client marker, and comes from
one Microsoft network IP. No collegedata workflow runs at that hour. This is
exactly the kind of client the friendly-API table can never see.

Of PDF downloads, 1,862 came from browser-like user agents, 1,582 from
self-declared bots (Meta's indexer, `CollegeConnect-DataBot`, `RosterRoomBot`,
and others), and 205 from scripts.

The friendly API logged roughly 2,000 to 3,000 calls a day over the same week.
Direct third-party use of `api.collegedata.fyi` is several times larger, and
none of it is in `api_usage_events` today.

## Design

### Overview

An hourly job pulls the last window of `edge_logs` from the Supabase
Management API, classifies each request, and writes:

- one `api_usage_events` row per **third-party** request, and
- hourly **rollup counts** for first-party, pipeline, and friendly-API
  upstream traffic. These are about 260,000 requests a day, too many to keep
  per row and of little use one by one.

```text
api.collegedata.fyi ─▶ Supabase gateway ─▶ edge_logs (≈90 days)
                                              │  hourly, read-only SQL
                                              ▼
                            tools/api_usage/ingest_gateway_logs.py
                              classify · hash · extract resource
                                   │                      │
                   third-party rows ▼                      ▼ hourly rollups
                       public.api_usage_events   public.api_gateway_rollups_hourly
```

### Step 1: tag our own traffic (prerequisite)

Today "our site" means `supabase-js-node` plus the anon key from AWS, which is
inferred, not declared. A third party using supabase-js from AWS would be
counted as us. Some site code also calls PostgREST with raw `fetch`
(`web/src/lib/queries.ts`), which shows up as User-Agent `node` with no client
marker, the same shape as the Azure walker.

Tag every first-party call explicitly:

- `web/src/lib/supabase.ts`: pass `global.headers` with
  `x-client-info: collegedata-web/<version>`.
- `web/src/lib/queries.ts` raw `fetch` calls: send
  `User-Agent: collegedata-web/<version> (+https://collegedata.fyi)` on the
  server and the same `x-client-info` everywhere.
- Friendly API route handlers that call PostgREST: tag them
  `collegedata-friendly-api/<version>`. Those requests are already counted in
  `api_usage_events` at the route, and this tag keeps them from being counted
  twice.
- Python pipelines already use `service_role`; add
  `User-Agent: collegedata-pipeline/<tool>` where cheap, for readability.

This is a client-set header, so it is used only for **attribution, never for
trust**. Anyone can spoof it. That is fine for counting and would not be fine
for rate limiting.

### Step 2: classification

Evaluated in order:

1. `service_role` JWT, or a new-style key with prefix `sb_secret_` → `internal_pipeline` (rollup)
2. `x-client-info` or User-Agent starts with `collegedata-friendly-api` → `friendly_api_upstream` (rollup)
3. starts with `collegedata-web` → `first_party_site` (rollup)
4. everything else → `third_party` (per-row event)

Until step 1 has been live for a full day, rule 3 falls back to
`supabase-js-node` + anon + an AWS network, and those rows are flagged
`classification_inferred = true`.

Third-party rows reuse the `api-usage.ts` normalization so families match the
friendly API: `mcp`, `cli`, `integration`, `browser`, `ai_agent`, `script`,
`unknown`. Two additions:

- **Declared bots.** If the User-Agent contains `bot`, `crawler`, or `spider`,
  `client_family = 'bot'` and `client_name` is the product token
  (`CollegeConnect-DataBot`, `meta-webindexer`). The token is stored; the full
  string is not.
- **PostgREST self-identification.** If a third party sends a User-Agent like
  `acme-research/1.2`, the product token becomes `client_name`. The API page
  and docs will ask bulk users to do this. It is the one marker that works on
  PostgREST, because unknown query parameters break PostgREST filters and
  custom headers are not logged.

### Step 3: what a third-party row stores

Reuses `api_usage_events` (it already has `request_source`, defaulted to
`'friendly_api'`) with additive, nullable columns:

| Column | Source | Notes |
|---|---|---|
| `request_source` | path prefix | `postgrest`, `storage`, `edge_function` |
| `route_kind` | path | table/view/rpc name, `pdf`, or function name |
| `school_id` | `school_id=eq.X` in the query, or the Storage folder | nothing else from the query string is kept |
| `http_method`, `status_code` | log | |
| `response_bytes` | `content_length` | Storage reliable; PostgREST partial |
| `cache_status` | `cf_cache_status` | |
| `client_family`, `client_name`, `client_version` | User-Agent and `x-client-info` | same rules as `api-usage.ts` |
| `user_agent_family` | User-Agent | existing column |
| `network_owner` | `cf.asOrganization` | e.g. `Microsoft Corporation`; an organization, not a person |
| `country` | `cf.country` | existing column |
| `client_hash` | HMAC of IP + User-Agent + JA4 | daily-rotated secret salt, see below |
| `gateway_request_id` | `request_id` | unique; makes re-ingest idempotent |
| `occurred_at` | log timestamp | existing column |

**Client hash.** `HMAC-SHA256(daily_salt, ip ‖ user_agent ‖ ja4)`, truncated
to 16 hex characters. The salt is generated by the job, kept only in the job's
secret store, and rotated every UTC day. That supports "distinct clients per
day" and "the same client within a day" (like Vercel's visitor count) without
making it possible to link clients across days or recover an IP. The IPv4
space is small enough that an unsalted hash could be brute-forced, which is why
it is salted. Raw IPs exist only in job memory and are never logged, printed,
or written to `scratch/`.

### Step 4: rollups for non-third-party traffic

New table `api_gateway_rollups_hourly`, keyed by
`(hour, classification, request_source, route_kind, status_class)`, with
`requests`, `response_bytes`, and `classification_inferred`. That is enough to
chart total load, our own share, and pipeline volume, at about 200 rows a day.

### Step 5: the job

- **Script:** `tools/api_usage/ingest_gateway_logs.py`. Standard library plus
  `requests` and `psycopg`, like the other `tools/` jobs. `--dry-run` writes a
  summary JSON to `scratch/api-usage/` with no IPs.
- **Query:** one parameterized SQL query per window. The SQL stays in one
  module, so a dialect change (see open questions) is a one-file edit.
- **Schedule:** a GitHub Actions workflow `ops-api-usage-ingest.yml`, hourly at
  minute 20. It ingests `[watermark − 15 min, now − 5 min]`. The overlap absorbs
  late-arriving logs; `gateway_request_id` uniqueness absorbs the duplicates.
  Rollups are recomputed for every hour the window touches.
- **State:** `api_usage_ingest_runs` (window start/end, rows read, rows
  written, status). The watermark is the last successful window end. After an
  outage the job walks forward in 24-hour slices until it catches up, as long
  as the gap is inside retention.
- **Backfill:** a manual `--backfill-from` run in 24-hour slices back to the
  retention edge. This should run soon after M2 merges, because about one day
  of history is lost per day of delay.
- **Secrets:** `SUPABASE_ACCESS_TOKEN` (a Management API personal access
  token, `sbp_...`), `SUPABASE_DB_URL` or service role for the insert, and
  `API_USAGE_HASH_SECRET` (the seed the daily salts are derived from).

### Step 6: reporting

- Views `api_usage_daily` and `api_usage_top_clients_7d` combine friendly-API
  and gateway rows, grouped by surface, client family, client name, and
  network owner.
- Update `docs/api-usage-attribution.md` with the new sources, columns, and
  queries, plus the post-deploy canary (below).
- The API page and README ask bulk users to send a descriptive User-Agent,
  for example `your-project/1.0 (+https://your-site)`.

A weekly digest or alert (big new client, sudden Storage egress) is PRD 013's
job. This PRD supplies the data it needs.

## Alternatives considered

| Option | Why not now |
|---|---|
| Supabase log drain to our own store | Paid add-on and plan-gated. It pushes everything, including the roughly 260,000 first-party rows a day we only want counted. Worth revisiting if the hourly pull becomes unreliable. |
| Cloudflare Worker in front of `api.collegedata.fyi` | Gives real-time capture and makes rate limiting possible. But it moves the domain, adds a hop, and egress passes through a second provider. That is the PRD 013 enforcement decision, not a measurement need. |
| Log in PostgREST (`pre-request` hook writing a row) | Adds a database write to every read, misses Storage entirely, and puts analytics on the hot path. |
| Keep only the friendly API | It misses most third-party use, per the probe. |

## Milestones

- **M0, tag first-party traffic.** Update `supabase.ts`, `queries.ts`, and the
  friendly API handlers. Ship it, then confirm in `edge_logs` that
  `collegedata-web` and `collegedata-friendly-api` appear and that untagged
  `supabase-js-node` traffic from AWS drops to near zero.
- **M1, schema and dry run.** One additive migration: the new
  `api_usage_events` columns, a unique index on `gateway_request_id`,
  `api_gateway_rollups_hourly`, and `api_usage_ingest_runs`, all RLS with
  service-role-only grants, matching the existing table. Add the ingest script
  with `--dry-run` and tests for classification, `school_id` extraction,
  bot-token parsing, and "no IP in output."
- **M2, schedule and backfill.** Add the hourly workflow. Then run the backfill
  to the retention edge.
- **M3, views and docs.** Add the reporting views, update the attribution doc,
  and add the User-Agent ask on the API page.

## Success criteria

- At least 99% of gateway requests in a day land in a named classification.
  Inferred classifications fall to zero within a day of M0.
- Daily third-party counts in `api_usage_events` match a direct `edge_logs`
  count for the same window to within 1%.
- Ingest lag is under 2 hours at p95, and a missed run self-heals on the next
  run.
- No raw IP, full user-agent string, or non-`school_id` query parameter is
  stored anywhere, enforced by a test on the normalizer and a canary query on
  the table.

## Open questions

1. **SQL dialect over the REST endpoint.** The probe used the ClickHouse
   unified-logs interface through Supabase's MCP. The Management API endpoint
   `GET /v1/projects/{ref}/analytics/endpoints/logs.all` has historically
   accepted BigQuery-style SQL over `edge_logs` with `unnest(metadata)`. M1
   confirms which one a personal access token gets and pins it.
2. **Access token.** The `SUPABASE_ACCESS_TOKEN` in the local `.env` returned
   `401` from the Management API during the probe. A fresh PAT is needed for
   CI regardless.
3. **Retention guarantee.** About 90 days was observed, which is more than
   documented for Pro. Treat it as luck: alert if the oldest queryable hour
   moves inside 7 days.
4. **Edge Functions.** Direct function calls should appear in `edge_logs`
   under `/functions/v1`. The probe saw almost none in 24 hours.
   `function_edge_logs` also exists. Confirm which source to use the first time
   a public function sees real traffic.
5. **Raw-host third parties.** Nearly all traffic on
   `isduwmygvmdozhpvzaix.supabase.co` in the probe was our own Edge Functions
   (`sb_secret_` keys, Deno runtime user agent). Capture both hosts anyway and
   record which one was used, since any third party on the raw host found it
   outside our docs.
6. **Secret-key hygiene.** A `sb_secret_` key in a third-party request would
   be classified as internal and would also mean the key leaked. The ingest
   should count `sb_secret_` requests from networks outside AWS and Azure
   separately so a leak would show up.
