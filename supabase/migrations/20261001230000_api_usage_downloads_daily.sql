-- PRD 033 M0: daily unique archive downloads.
--
-- The API usage ingest job (ops-api-usage-ingest.yml) counts unique
-- downloads for each closed UTC day: one client key (IP address + user
-- agent) x one archive file x one day, GETs returning 200 or 206. The client
-- key exists only inside the logs query; rows here hold counts by school,
-- access method, and client family, nothing that identifies a client.
--
-- Private and service-role only. PRD 033 M1 publishes a filtered copy.
--
-- Apply from main after merge; do not push from a branch.

create table if not exists public.api_usage_downloads_daily (
  day date not null,
  school_id text not null,
  access_method text not null,
  client_family text not null,
  from_site boolean not null default false,
  unique_downloads bigint not null,
  raw_downloads bigint not null,
  method_version smallint not null,
  ingested_at timestamptz not null default now(),
  primary key (day, method_version, school_id, access_method, client_family, from_site),
  constraint api_usage_downloads_school_shape check (school_id ~ '^[a-z0-9][a-z0-9-]{0,99}$'),
  constraint api_usage_downloads_method_valid check (
    access_method in ('browser', 'machine', 'bots_crawlers', 'excluded')
  ),
  constraint api_usage_downloads_counts_valid check (
    unique_downloads > 0 and raw_downloads >= unique_downloads
  ),
  constraint api_usage_downloads_version_valid check (method_version >= 1)
);

comment on table public.api_usage_downloads_daily is
  'PRD 033. Unique archive downloads per UTC day: one client key (IP + user agent, never stored) x one file x one day. access_method: browser, machine (scripts, AI agents acting for a person, unknown clients, and browser keys over the heavy-client threshold), bots_crawlers (declared bots and AI crawlers), excluded (our pipeline). from_site marks fetches with a collegedata.fyi referer. raw_downloads counts every 200/206 GET. Rows are replaced per (day, method_version).';

create index if not exists api_usage_downloads_school_day_idx
  on public.api_usage_downloads_daily (school_id, day desc);

alter table public.api_usage_downloads_daily enable row level security;
revoke all on table public.api_usage_downloads_daily from anon, authenticated;
grant all on table public.api_usage_downloads_daily to service_role;

alter table public.api_usage_ingest_runs
  drop constraint if exists api_usage_ingest_runs_mode_valid;
alter table public.api_usage_ingest_runs
  add constraint api_usage_ingest_runs_mode_valid check (mode in ('hourly', 'backfill', 'daily'));

create or replace function public.api_usage_replace_downloads_day(
  p_day date,
  p_method_version integer,
  p_rows jsonb
)
returns integer
language plpgsql
set search_path = public
as $$
declare
  n_rows integer;
  n_payload integer := jsonb_array_length(coalesce(p_rows, '[]'::jsonb));
begin
  if p_day is null or p_method_version is null then
    raise exception 'api_usage_replace_downloads_day: day and method version are required';
  end if;

  delete from public.api_usage_downloads_daily
  where day = p_day and method_version = p_method_version;

  insert into public.api_usage_downloads_daily (
    day, school_id, access_method, client_family, from_site,
    unique_downloads, raw_downloads, method_version
  )
  select
    r.day, r.school_id, r.access_method, r.client_family, r.from_site,
    r.unique_downloads, r.raw_downloads, r.method_version
  from jsonb_to_recordset(coalesce(p_rows, '[]'::jsonb)) as r(
    day date, school_id text, access_method text, client_family text, from_site boolean,
    unique_downloads bigint, raw_downloads bigint, method_version smallint
  )
  where r.day = p_day and r.method_version = p_method_version;
  get diagnostics n_rows = row_count;
  if n_rows <> n_payload then
    raise exception 'api_usage_replace_downloads_day: % rows have another day or method version',
      n_payload - n_rows;
  end if;
  return n_rows;
end;
$$;

revoke all on function public.api_usage_replace_downloads_day(date, integer, jsonb)
  from public, anon, authenticated;
grant execute on function public.api_usage_replace_downloads_day(date, integer, jsonb)
  to service_role;

do $$
begin
  if has_table_privilege('anon', 'public.api_usage_downloads_daily', 'select')
     or has_table_privilege('authenticated', 'public.api_usage_downloads_daily', 'select') then
    raise exception 'PRD 033: api_usage_downloads_daily is readable by anon or authenticated';
  end if;
  if has_function_privilege('anon', 'public.api_usage_replace_downloads_day(date, integer, jsonb)', 'execute') then
    raise exception 'PRD 033: api_usage_replace_downloads_day is executable by anon';
  end if;
end;
$$;
