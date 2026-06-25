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

It does not cover raw PostgREST requests to `https://api.collegedata.fyi/rest/v1`
or Supabase Storage requests. Those bypass the Vercel app and are visible only
through Supabase/API-gateway observability unless a proxy or log-drain layer is
added later.

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

Raw Supabase REST and Storage traffic are outside this layer. To attribute those
surfaces, add a proxy/log-drain plan rather than expanding this table into a
general analytics product.
