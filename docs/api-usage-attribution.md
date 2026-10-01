# API usage attribution

This document describes the lightweight usage signal shipped for the public
friendly API at `https://www.collegedata.fyi/api/...`. It answers operational
questions like:

- Are first-party MCP clients calling the API?
- Are first-party CLI users calling the API?
- Are external apps or scripts self-identifying?
- Which friendly API routes are active, and which tools are they using?

It does not replace Supabase or Vercel observability. It is a small attribution
layer for the no-auth API surface.

## Scope

The attribution layer covers the friendly Next.js API routes:

- `/api/schools/search`
- `/api/schools/:school_id/facts`
- `/api/schools/:school_id/sources`
- `/api/facts/:school_id`
- `/api/compare`
- `/api/fields`
- `/api/snapshots`

Raw PostgREST requests to `https://api.collegedata.fyi/rest/v1` and Supabase
Storage requests bypass the Vercel app. PRD 032 covers them separately from
Supabase gateway logs; see [Gateway usage (PRD 032)](#gateway-usage-prd-032).

## What gets logged

Requests are recorded in `public.api_usage_events`.

The table stores only coarse metadata:

- `occurred_at`
- `route_path`
- `route_kind`
- `http_method`
- `client_family`
- `client_name`
- `client_version`
- `client_tool`
- `user_agent_family`
- `referer_host`
- `country`
- `school_id`
- `school_count`

The table is private: RLS is enabled and only `service_role` has table access.

## What is intentionally not logged

Do not add these without an explicit privacy review:

- IP addresses
- full raw `User-Agent` strings
- full URLs or query strings
- search query text
- request bodies
- profile, match-list, or student-input payloads
- cookies or account identifiers

The logger also fails closed: if `SUPABASE_SERVICE_ROLE_KEY` is missing or the
insert fails, the public API response still completes.

## Client markers

First-party wrappers identify themselves on every friendly API call.

The MCP server sends:

```http
X-CollegeData-Client: mcp
X-CollegeData-Client-Version: 0.1.0
X-CollegeData-MCP-Tool: search_schools
```

It also appends query markers:

```text
cd_client=mcp&cd_client_version=0.1.0&cd_tool=search_schools
```

The CLI sends:

```http
X-CollegeData-Client: cli
X-CollegeData-Client-Version: 0.1.0
X-CollegeData-CLI-Command: search
```

It also appends query markers:

```text
cd_client=cli&cd_client_version=0.1.0&cd_command=search
```

External builders are encouraged to send a short client marker:

```bash
curl 'https://www.collegedata.fyi/api/schools/search?q=mit' \
  -H 'X-CollegeData-Client: my-app-name'
```

These labels are self-declared and untrusted. They are useful for product and
operational visibility, not authorization.

## How classification works

`web/src/lib/api-usage.ts` normalizes each request into an event.

Client family precedence:

1. `client_name` containing `mcp` -> `mcp`
2. `client_name` containing `cli` -> `cli`
3. any other `client_name` -> `integration`
4. browser-like user agent -> `browser`
5. known AI-agent user agent -> `ai_agent`
6. curl, Python, Node fetch, or other script-like user agent -> `script`
7. otherwise -> `unknown`

The user-agent classification stores only the family bucket, not the raw header.

## Required production configuration

Vercel Production must have:

- `NEXT_PUBLIC_SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

`SUPABASE_SERVICE_ROLE_KEY` should be configured as a sensitive Production
environment variable. Without it, production API calls still work but no usage
events are inserted.

After changing Vercel environment variables, redeploy production so the runtime
loads the new values.

## Common queries

Recent events:

```sql
select
  occurred_at,
  route_kind,
  client_family,
  client_name,
  client_version,
  client_tool,
  user_agent_family,
  referer_host,
  country,
  school_id,
  school_count
from public.api_usage_events
order by occurred_at desc
limit 50;
```

MCP usage by tool:

```sql
select
  date_trunc('day', occurred_at) as day,
  client_tool,
  count(*) as calls
from public.api_usage_events
where client_family = 'mcp'
group by 1, 2
order by 1 desc, calls desc;
```

CLI usage by command:

```sql
select
  date_trunc('day', occurred_at) as day,
  client_tool as command,
  count(*) as calls
from public.api_usage_events
where client_family = 'cli'
group by 1, 2
order by 1 desc, calls desc;
```

External integrations that self-identify:

```sql
select
  client_name,
  client_version,
  count(*) as calls,
  min(occurred_at) as first_seen,
  max(occurred_at) as last_seen
from public.api_usage_events
where client_family = 'integration'
group by 1, 2
order by calls desc;
```

Route mix over the last 7 days:

```sql
select
  route_kind,
  client_family,
  count(*) as calls
from public.api_usage_events
where occurred_at >= now() - interval '7 days'
group by 1, 2
order by calls desc;
```

Top school fact/source lookups:

```sql
select
  school_id,
  route_kind,
  count(*) as calls
from public.api_usage_events
where school_id is not null
  and occurred_at >= now() - interval '30 days'
group by 1, 2
order by calls desc
limit 50;
```

## Post-deploy canary

Send a marked request:

```bash
curl 'https://www.collegedata.fyi/api/schools/search?q=mit&cd_client=deploy-canary&cd_client_version=YYYY-MM-DD&cd_tool=post_deploy_canary' \
  -H 'X-CollegeData-Client: deploy-canary' \
  -H 'X-CollegeData-Client-Version: YYYY-MM-DD'
```

Then verify the event:

```sql
select
  occurred_at,
  route_kind,
  client_family,
  client_name,
  client_version,
  client_tool,
  user_agent_family
from public.api_usage_events
where client_name = 'deploy-canary'
order by occurred_at desc
limit 5;
```

Expected result:

- `route_kind = 'schools_search'`
- `client_family = 'integration'`
- `client_name = 'deploy-canary'`
- `client_tool` matches the canary marker

## Limitations

This system can confidently identify first-party MCP and CLI usage after the
marker change. It cannot prove that an unmarked script is or is not an AI agent.
For unmarked traffic, `client_family` is only a coarse inference from the
user-agent family.

Raw Supabase REST and Storage traffic are outside this table; the gateway
aggregates below cover them.

## Gateway usage (PRD 032)

`.github/workflows/ops-api-usage-ingest.yml` runs hourly at minute 20. It reads
Supabase gateway logs (`edge_logs` and `function_edge_logs`) through the
Management API logs endpoint with the scoped `SUPABASE_LOGS_TOKEN` (Logs: Read,
this project only, expires 2027-10-01) and replaces whole UTC hours in:

- `api_gateway_rollups_hourly`: every request, by host, surface, route,
  classification, client family, and status class.
- `api_gateway_clients_hourly`: non-browser third-party clients, keyed by a
  salted daily hash. Kept 400 days.
- `api_gateway_schools_hourly`: archive-file requests per school (all callers)
  and third-party `school_id=eq.` lookups.
- `api_usage_ingest_runs`: one row per processed window.
- Views: `api_usage_daily` (gateway plus `api_usage_events`) and
  `api_usage_top_clients_7d`.

All of these are service-role only. Nothing stores an IP, a full user agent, a
query string, or a request body. `client_hash` is
`HMAC-SHA256(daily salt, ip|ua|ja4)` truncated to 16 hex characters; the salt in
`api_usage_hash_salts` is deleted two days after its UTC day, so hashes do not
link across days.

### Classification

`tools/api_usage/classify.py`, first match wins:

1. `internal_pipeline`: service-role JWT, `sb_secret_` key, a
   `collegedata-pipeline` user agent, or an internal Edge Function
   (archive, discover, directory, coverage).
2. `friendly_api_upstream`: `X-Client-Info: collegedata-friendly-api/<sha>`.
3. `first_party_site`: `X-Client-Info: collegedata-web/<sha>`, or a
   `collegedata.fyi` referer (archive PDF links keep the origin-only referer).
4. Hours up to the tagged-build deploy (`SITE_TAGGING_T0`) use inference,
   flagged `inferred = true`: anon `supabase-js-node` from AWS and anon
   `supabase-js-web` count as the site; browser downloads from Storage count as
   `browser_unattributed`.
5. `browser_unattributed`: a browser-shaped user agent with no marker.
6. `third_party`: everything else.

The gateway logs `X-Client-Info` but not custom headers, which is why first-party
code sets that header (`web/src/lib/client-info.ts`) and Python tools send
`User-Agent: collegedata-pipeline/<tool>`.

### Operations

```bash
# Counts-only dry run of the last three hours (needs SUPABASE_LOGS_TOKEN).
python tools/api_usage/ingest_gateway_logs.py --dry-run --out-json scratch/api-usage/dry.json

# Backfill: dispatch the workflow with mode=backfill, days=1..89.
gh workflow run ops-api-usage-ingest.yml -f mode=backfill -f days=89
```

The logs endpoint allows 10 queries per minute, so the client paces calls 7
seconds apart and waits 5 minutes on a 429. Results truncate at 1,000 rows, so
every query pages with `LIMIT`/`OFFSET`. Each window checks that rollup totals
match the raw `count()`. A window that misses by more than 0.1% writes nothing
and fails the run, so the next hourly run retries it.

Alerts: six straight failed scheduled runs, or no logs from seven days ago
(retention shrank), open a pipeline alert issue. `tools/ops/automation_health.py`
also flags the workflow when its latest run is more than 3 hours old. The
heartbeat station is `api_usage_ingest` (off the public board, and its summary
carries no traffic counts).

`SITE_TAGGING_T0` in `tools/api_usage/classify.py` is the production deploy of
the tagged web build (2026-10-01 19:16 UTC). Hours through 19:00 that day use
the pre-tagging inference rules and are flagged `inferred`; strict attribution
starts at 20:00 UTC. Preview builds sent tagged traffic from 18:51 UTC; the
tag makes it first-party regardless of T0.

Debugging a broken query locally: `API_USAGE_DEBUG=1` adds the (IP-redacted)
logs-API error message. Never set it in CI.

The repository is public. Workflow logs and summaries carry counts only; keep
it that way.

### Common gateway queries

Daily traffic by who sent it:

```sql
select day, classification, sum(requests) as requests
from public.api_usage_daily
where source = 'gateway' and day >= current_date - 14
group by 1, 2
order by 1 desc, requests desc;
```

Top third-party clients this week:

```sql
select * from public.api_usage_top_clients_7d limit 25;
```

Most-downloaded archive files by school, last 30 days:

```sql
select school_id, sum(downloads) as downloads, sum(requests) as requests
from public.api_gateway_schools_hourly
where surface = 'storage' and hour >= now() - interval '30 days'
group by 1
order by downloads desc
limit 50;
```
