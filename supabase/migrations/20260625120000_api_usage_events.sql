-- Lightweight public API usage attribution.
--
-- This table intentionally stores coarse request metadata only: endpoint
-- family, self-declared client labels, referrer host, country, and public
-- school identifiers. It does not store IP addresses, full user agents,
-- search queries, full query strings, request bodies, or profile inputs.

create table if not exists public.api_usage_events (
  id bigserial primary key,
  occurred_at timestamptz not null default now(),
  request_source text not null default 'friendly_api',
  route_path text not null,
  route_kind text not null,
  http_method text not null,
  client_family text not null default 'unknown',
  client_name text,
  client_version text,
  client_tool text,
  user_agent_family text not null default 'unknown',
  referer_host text,
  country text,
  school_id text,
  school_count integer,
  created_at timestamptz not null default now(),
  constraint api_usage_events_method_valid check (
    http_method in ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS')
  ),
  constraint api_usage_events_school_count_valid check (
    school_count is null or school_count >= 0
  )
);

comment on table public.api_usage_events is
  'Low-PII server-side usage events for the public friendly API. Used to distinguish first-party MCP/CLI calls, cooperative app integrations, and unknown script/browser traffic.';

comment on column public.api_usage_events.client_name is
  'Self-declared client marker from X-CollegeData-Client or cd_client. Sanitized before insert; untrusted and advisory only.';

comment on column public.api_usage_events.client_tool is
  'MCP tool or CLI command marker when supplied by first-party clients. Sanitized before insert; untrusted and advisory only.';

comment on column public.api_usage_events.user_agent_family is
  'Coarse user-agent bucket only, not the raw User-Agent header.';

alter table public.api_usage_events enable row level security;

create index if not exists api_usage_events_occurred_at_idx
  on public.api_usage_events (occurred_at desc);

create index if not exists api_usage_events_route_kind_occurred_at_idx
  on public.api_usage_events (route_kind, occurred_at desc);

create index if not exists api_usage_events_client_family_occurred_at_idx
  on public.api_usage_events (client_family, occurred_at desc);

grant all on public.api_usage_events to service_role;
grant usage, select on sequence public.api_usage_events_id_seq to service_role;
