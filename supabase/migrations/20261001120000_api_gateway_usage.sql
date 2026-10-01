-- PRD 032: gateway-level API usage capture.
--
-- An hourly GitHub Actions job (ops-api-usage-ingest.yml) reads Supabase
-- gateway logs through the Management API and writes aggregates here.
-- Nothing in these tables holds an IP address, a full user agent, a query
-- string, or a request body. Client hashes are keyed by a per-day random
-- salt that is deleted two days later, so hashes cannot be linked across
-- days or reversed once the salt is gone.
--
-- Apply from main after merge; do not push from a branch.

create table if not exists public.api_gateway_rollups_hourly (
  hour timestamptz not null,
  log_source text not null,
  host text not null,
  surface text not null,
  route_kind text not null,
  classification text not null,
  client_family text not null,
  status_class text not null,
  inferred boolean not null default false,
  requests bigint not null,
  downloads bigint not null default 0,
  range_requests bigint not null default 0,
  cache_hits bigint not null default 0,
  response_bytes bigint not null default 0,
  ingested_at timestamptz not null default now(),
  primary key (
    hour, log_source, host, surface, route_kind,
    classification, client_family, status_class, inferred
  ),
  constraint api_gateway_rollups_hour_whole check (date_trunc('hour', hour) = hour),
  constraint api_gateway_rollups_log_source_valid check (
    log_source in ('edge_logs', 'function_edge_logs')
  ),
  constraint api_gateway_rollups_classification_valid check (
    classification in (
      'internal_pipeline', 'friendly_api_upstream', 'first_party_site',
      'browser_unattributed', 'third_party'
    )
  ),
  constraint api_gateway_rollups_status_class_valid check (
    status_class in ('2xx', '3xx', '4xx', '5xx', 'other')
  ),
  constraint api_gateway_rollups_counts_valid check (
    requests >= 0 and downloads >= 0 and range_requests >= 0
    and cache_hits >= 0 and response_bytes >= 0
  )
);

comment on table public.api_gateway_rollups_hourly is
  'PRD 032. Every gateway request, aggregated per UTC hour. classification says who sent it (internal pipeline, friendly API upstream, first-party site, unattributed browser, third party); inferred marks rows classified by pre-tagging heuristics.';

create table if not exists public.api_gateway_clients_hourly (
  hour timestamptz not null,
  client_hash text not null,
  surface text not null,
  route_kind text not null,
  client_family text not null,
  client_name text,
  client_version text,
  user_agent_family text not null,
  network_owner text,
  country text,
  requests bigint not null,
  distinct_schools integer not null default 0,
  status_4xx bigint not null default 0,
  status_5xx bigint not null default 0,
  response_bytes bigint not null default 0,
  ingested_at timestamptz not null default now(),
  primary key (hour, client_hash, surface, route_kind),
  constraint api_gateway_clients_hour_whole check (date_trunc('hour', hour) = hour),
  constraint api_gateway_clients_hash_shape check (client_hash ~ '^[0-9a-f]{16}$'),
  constraint api_gateway_clients_counts_valid check (
    requests >= 0 and distinct_schools >= 0 and status_4xx >= 0
    and status_5xx >= 0 and response_bytes >= 0
  )
);

comment on table public.api_gateway_clients_hourly is
  'PRD 032. Non-browser third-party clients per UTC hour. client_hash is HMAC-SHA256(daily salt, ip|ua|ja4) truncated; it changes every UTC day. distinct_schools is a lower bound when several log groups merge into one row. Retained 400 days.';

create table if not exists public.api_gateway_schools_hourly (
  hour timestamptz not null,
  school_id text not null,
  surface text not null,
  classification text not null,
  requests bigint not null,
  downloads bigint not null default 0,
  ingested_at timestamptz not null default now(),
  primary key (hour, school_id, surface, classification),
  constraint api_gateway_schools_hour_whole check (date_trunc('hour', hour) = hour),
  constraint api_gateway_schools_id_shape check (school_id ~ '^[a-z0-9][a-z0-9-]{0,99}$'),
  constraint api_gateway_schools_counts_valid check (requests >= 0 and downloads >= 0)
);

comment on table public.api_gateway_schools_hourly is
  'PRD 032. Per-school demand per UTC hour: archive-file requests from every caller, plus PostgREST school_id=eq. lookups from third parties and unattributed browsers.';

create table if not exists public.api_usage_hash_salts (
  day date primary key,
  salt text not null,
  created_at timestamptz not null default now(),
  constraint api_usage_hash_salts_shape check (salt ~ '^[0-9a-f]{64}$')
);

comment on table public.api_usage_hash_salts is
  'PRD 032. Random per-UTC-day HMAC salt for api_gateway_clients_hourly.client_hash. Deleted by api_usage_prune() two days after the day ends.';

create table if not exists public.api_usage_ingest_runs (
  id bigserial primary key,
  mode text not null,
  window_start timestamptz not null,
  window_end timestamptz not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',
  rows_read bigint not null default 0,
  rows_written bigint not null default 0,
  raw_requests bigint,
  rollup_requests bigint,
  error_code text,
  run_url text,
  constraint api_usage_ingest_runs_mode_valid check (mode in ('hourly', 'backfill')),
  constraint api_usage_ingest_runs_status_valid check (status in ('running', 'ok', 'error')),
  constraint api_usage_ingest_runs_window_valid check (window_start < window_end)
);

create index if not exists api_usage_ingest_runs_ok_end_idx
  on public.api_usage_ingest_runs (mode, window_end desc)
  where status = 'ok';

create index if not exists api_gateway_rollups_hour_idx
  on public.api_gateway_rollups_hourly (hour desc);
create index if not exists api_gateway_clients_hour_idx
  on public.api_gateway_clients_hourly (hour desc);
create index if not exists api_gateway_schools_school_hour_idx
  on public.api_gateway_schools_hourly (school_id, hour desc);

alter table public.api_gateway_rollups_hourly enable row level security;
alter table public.api_gateway_clients_hourly enable row level security;
alter table public.api_gateway_schools_hourly enable row level security;
alter table public.api_usage_hash_salts enable row level security;
alter table public.api_usage_ingest_runs enable row level security;

revoke all on table
  public.api_gateway_rollups_hourly,
  public.api_gateway_clients_hourly,
  public.api_gateway_schools_hourly,
  public.api_usage_hash_salts,
  public.api_usage_ingest_runs
from anon, authenticated;

grant all on table
  public.api_gateway_rollups_hourly,
  public.api_gateway_clients_hourly,
  public.api_gateway_schools_hourly,
  public.api_usage_hash_salts,
  public.api_usage_ingest_runs
to service_role;
revoke all on sequence public.api_usage_ingest_runs_id_seq from anon, authenticated;
grant usage, select on sequence public.api_usage_ingest_runs_id_seq to service_role;

-- Replace whole hours atomically. A null payload leaves that table alone,
-- so the function_edge_logs pass never touches client or school rows.
create or replace function public.api_usage_replace_window(
  p_log_source text,
  p_start timestamptz,
  p_end timestamptz,
  p_rollups jsonb,
  p_clients jsonb default null,
  p_schools jsonb default null
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  n_rollups integer := 0;
  n_clients integer := 0;
  n_schools integer := 0;
  n_payload integer;
begin
  if p_start >= p_end
     or date_trunc('hour', p_start) <> p_start
     or date_trunc('hour', p_end) <> p_end then
    raise exception 'api_usage_replace_window: window must be whole hours with start < end';
  end if;
  if p_log_source not in ('edge_logs', 'function_edge_logs') then
    raise exception 'api_usage_replace_window: unknown log source %', p_log_source;
  end if;

  delete from public.api_gateway_rollups_hourly
  where log_source = p_log_source and hour >= p_start and hour < p_end;

  n_payload := jsonb_array_length(coalesce(p_rollups, '[]'::jsonb));
  insert into public.api_gateway_rollups_hourly (
    hour, log_source, host, surface, route_kind, classification, client_family,
    status_class, inferred, requests, downloads, range_requests, cache_hits, response_bytes
  )
  select
    r.hour, p_log_source, r.host, r.surface, r.route_kind, r.classification, r.client_family,
    r.status_class, r.inferred, r.requests, r.downloads, r.range_requests, r.cache_hits, r.response_bytes
  from jsonb_to_recordset(coalesce(p_rollups, '[]'::jsonb)) as r(
    hour timestamptz, host text, surface text, route_kind text, classification text,
    client_family text, status_class text, inferred boolean, requests bigint,
    downloads bigint, range_requests bigint, cache_hits bigint, response_bytes bigint
  )
  where r.hour >= p_start and r.hour < p_end;
  get diagnostics n_rollups = row_count;
  if n_rollups <> n_payload then
    raise exception 'api_usage_replace_window: % rollup rows fall outside the window', n_payload - n_rollups;
  end if;

  if p_clients is not null then
    delete from public.api_gateway_clients_hourly where hour >= p_start and hour < p_end;
    n_payload := jsonb_array_length(p_clients);
    insert into public.api_gateway_clients_hourly (
      hour, client_hash, surface, route_kind, client_family, client_name, client_version,
      user_agent_family, network_owner, country, requests, distinct_schools,
      status_4xx, status_5xx, response_bytes
    )
    select
      c.hour, c.client_hash, c.surface, c.route_kind, c.client_family, c.client_name, c.client_version,
      c.user_agent_family, c.network_owner, c.country, c.requests, c.distinct_schools,
      c.status_4xx, c.status_5xx, c.response_bytes
    from jsonb_to_recordset(p_clients) as c(
      hour timestamptz, client_hash text, surface text, route_kind text, client_family text,
      client_name text, client_version text, user_agent_family text, network_owner text,
      country text, requests bigint, distinct_schools integer, status_4xx bigint,
      status_5xx bigint, response_bytes bigint
    )
    where c.hour >= p_start and c.hour < p_end;
    get diagnostics n_clients = row_count;
    if n_clients <> n_payload then
      raise exception 'api_usage_replace_window: % client rows fall outside the window', n_payload - n_clients;
    end if;
  end if;

  if p_schools is not null then
    delete from public.api_gateway_schools_hourly where hour >= p_start and hour < p_end;
    n_payload := jsonb_array_length(p_schools);
    insert into public.api_gateway_schools_hourly (
      hour, school_id, surface, classification, requests, downloads
    )
    select s.hour, s.school_id, s.surface, s.classification, s.requests, s.downloads
    from jsonb_to_recordset(p_schools) as s(
      hour timestamptz, school_id text, surface text, classification text,
      requests bigint, downloads bigint
    )
    where s.hour >= p_start and s.hour < p_end;
    get diagnostics n_schools = row_count;
    if n_schools <> n_payload then
      raise exception 'api_usage_replace_window: % school rows fall outside the window', n_payload - n_schools;
    end if;
  end if;

  return jsonb_build_object(
    'rollups', n_rollups,
    'clients', n_clients,
    'schools', n_schools
  );
end;
$$;

create or replace function public.api_usage_prune(p_client_keep_days integer default 400)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  n_salts integer;
  n_clients integer;
begin
  delete from public.api_usage_hash_salts
  where day < (now() at time zone 'utc')::date - 2;
  get diagnostics n_salts = row_count;

  delete from public.api_gateway_clients_hourly
  where hour < now() - make_interval(days => p_client_keep_days);
  get diagnostics n_clients = row_count;

  return jsonb_build_object('salts_deleted', n_salts, 'client_rows_deleted', n_clients);
end;
$$;

revoke all on function public.api_usage_replace_window(text, timestamptz, timestamptz, jsonb, jsonb, jsonb)
  from public, anon, authenticated;
revoke all on function public.api_usage_prune(integer) from public, anon, authenticated;
grant execute on function public.api_usage_replace_window(text, timestamptz, timestamptz, jsonb, jsonb, jsonb)
  to service_role;
grant execute on function public.api_usage_prune(integer) to service_role;

-- One place to answer "how much API traffic, from whom". Gateway rows
-- with classification friendly_api_upstream are the friendly API's own
-- upstream calls; the friendly_api source rows count the same traffic at
-- the edge, so sum one or the other, not both.
create or replace view public.api_usage_daily
with (security_invoker = true) as
select
  (r.hour at time zone 'utc')::date as day,
  'gateway'::text as source,
  r.surface,
  r.route_kind,
  r.classification,
  r.client_family,
  r.inferred,
  sum(r.requests)::bigint as requests,
  sum(r.downloads)::bigint as downloads,
  sum(r.response_bytes)::bigint as response_bytes
from public.api_gateway_rollups_hourly r
where r.route_kind <> 'options_preflight'
group by 1, 2, 3, 4, 5, 6, 7
union all
select
  (e.occurred_at at time zone 'utc')::date as day,
  'friendly_api'::text as source,
  'friendly_api'::text as surface,
  e.route_kind,
  'friendly_api'::text as classification,
  e.client_family,
  false as inferred,
  count(*)::bigint as requests,
  0::bigint as downloads,
  0::bigint as response_bytes
from public.api_usage_events e
group by 1, 2, 3, 4, 5, 6, 7;

create or replace view public.api_usage_top_clients_7d
with (security_invoker = true) as
select
  coalesce(c.client_name, c.user_agent_family) as client_label,
  c.client_family,
  c.network_owner,
  sum(c.requests)::bigint as requests,
  count(distinct c.client_hash)::integer as client_day_hashes,
  max(c.distinct_schools)::integer as max_schools_in_hour,
  sum(c.status_4xx)::bigint as status_4xx,
  sum(c.status_5xx)::bigint as status_5xx,
  array_agg(distinct c.surface order by c.surface) as surfaces,
  min(c.hour) as first_seen,
  max(c.hour) as last_seen
from public.api_gateway_clients_hourly c
where c.hour >= now() - interval '7 days'
group by 1, 2, 3
order by requests desc;

revoke all on public.api_usage_daily, public.api_usage_top_clients_7d from anon, authenticated;
grant select on public.api_usage_daily, public.api_usage_top_clients_7d to service_role;

insert into public.pipeline_stations (
  station_id, display_name, cadence_label, class, source_kind, on_board, sort_order,
  required_keys, allowed_keys
) values (
  'api_usage_ingest',
  'API usage ingest',
  'hourly · SLA 3h',
  'hourly_sla',
  'gha',
  false,
  220,
  -- pipeline_station_facts() is public, so no traffic counts here.
  array['windows', 'reconciled'],
  array['windows', 'reconciled', 'mode', 'rows_written', 'lag_hours', 'dry_run', 'run_url']
);

insert into public.pipeline_heartbeats (station_id)
values ('api_usage_ingest');

do $$
declare
  rel text;
begin
  foreach rel in array array[
    'public.api_gateway_rollups_hourly',
    'public.api_gateway_clients_hourly',
    'public.api_gateway_schools_hourly',
    'public.api_usage_hash_salts',
    'public.api_usage_ingest_runs',
    'public.api_usage_daily',
    'public.api_usage_top_clients_7d'
  ]
  loop
    if has_table_privilege('anon', rel, 'select')
       or has_table_privilege('authenticated', rel, 'select') then
      raise exception 'PRD 032: % is readable by anon or authenticated', rel;
    end if;
  end loop;
  if has_function_privilege('anon', 'public.api_usage_replace_window(text, timestamptz, timestamptz, jsonb, jsonb, jsonb)', 'execute')
     or has_function_privilege('anon', 'public.api_usage_prune(integer)', 'execute') then
    raise exception 'PRD 032: usage functions are executable by anon';
  end if;
end;
$$;
