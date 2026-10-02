-- PRD 033 M1: public usage tables and the publish step.
--
-- The API usage ingest job writes private aggregates (PRD 032 hourly
-- rollups, PRD 033 daily unique downloads). api_usage_publish_pending()
-- copies what may be published into two public tables, applying every
-- privacy rule here rather than in the page:
--
--   usage_public_daily          whole-archive totals per closed UTC day
--   usage_public_school_months  one combined number per school per complete
--                               calendar month, rounded to 10; schools under
--                               10 are not listed
--   usage_public_months         per complete month, how many schools had
--                               downloads and how many were under 10
--
-- The public tables hold only publishable columns, so a query bug cannot
-- leak a private one. Nothing here names a client, holds a hash, a network,
-- a country, or a user agent.
--
-- Daily totals sum every school's downloads, so unlisted schools' combined
-- count is the month total minus the listed ones. Listing only rounded
-- values, and never which schools are under 10, keeps that difference from
-- pinning any school.
--
-- Apply from main after merge; do not push from a branch.

create table if not exists public.usage_public_daily (
  day date not null,
  metric text not null,
  access_method text not null default '',
  client_kind text not null default '',
  value bigint not null,
  method_version smallint not null,
  published_at timestamptz not null default now(),
  primary key (day, metric, access_method, client_kind),
  constraint usage_public_daily_metric_valid check (
    metric in (
      'unique_downloads', 'site_downloads', 'api_requests',
      'friendly_api_requests', 'serving_requests'
    )
  ),
  constraint usage_public_daily_method_valid check (
    access_method in ('', 'browser', 'machine', 'bots_crawlers')
  ),
  constraint usage_public_daily_kind_valid check (
    client_kind in (
      '', 'browser', 'heavy_browser', 'script', 'integration', 'unknown',
      'ai_user', 'ai_agent', 'ai_crawler', 'declared_bot', 'mcp', 'cli'
    )
  ),
  constraint usage_public_daily_value_valid check (value >= 0),
  constraint usage_public_daily_version_valid check (method_version >= 1)
);

comment on table public.usage_public_daily is
  'PRD 033. Public whole-archive usage per closed UTC day. unique_downloads: one client x one archive file x one day, by access method and client kind (heavy_browser = browser-like clients over 30 files a day, counted as machine). site_downloads: browser downloads that followed a link on collegedata.fyi. api_requests: third-party PostgREST and Edge Function requests. friendly_api_requests: calls to the collegedata.fyi /api routes and MCP server. serving_requests: requests the site and friendly API made to serve pages. CC0.';

create table if not exists public.usage_public_school_months (
  month date not null,
  school_id text not null,
  school_name text not null,
  unique_downloads bigint not null,
  method_version smallint not null,
  published_at timestamptz not null default now(),
  primary key (month, school_id),
  constraint usage_public_school_months_month_whole check (date_trunc('month', month)::date = month),
  constraint usage_public_school_months_school_shape check (school_id ~ '^[a-z0-9][a-z0-9-]{0,99}$'),
  constraint usage_public_school_months_floor check (unique_downloads >= 10 and unique_downloads % 10 = 0),
  constraint usage_public_school_months_version_valid check (method_version >= 1)
);

comment on table public.usage_public_school_months is
  'PRD 033. Browser plus machine unique downloads of each school''s archive files per complete calendar month, rounded to the nearest 10. Schools with fewer than 10 are not listed. Storage folders are mapped to the school that owns them, then through institution_slug_crosswalk. CC0.';

create table if not exists public.usage_public_months (
  month date primary key,
  schools_with_downloads integer not null,
  schools_under_floor integer not null,
  method_version smallint not null,
  published_at timestamptz not null default now(),
  constraint usage_public_months_month_whole check (date_trunc('month', month)::date = month),
  constraint usage_public_months_counts_valid check (
    schools_under_floor >= 0 and schools_with_downloads >= schools_under_floor
  ),
  constraint usage_public_months_version_valid check (method_version >= 1)
);

comment on table public.usage_public_months is
  'PRD 033. Per complete calendar month: schools whose archive files had any browser or machine download, and how many of them had fewer than 10 (not listed in usage_public_school_months). CC0.';

create table if not exists public.api_usage_publish_days (
  day date primary key,
  method_version smallint not null,
  source_finished_at timestamptz not null,
  published_at timestamptz not null default now()
);

comment on table public.api_usage_publish_days is
  'PRD 033. Days copied into usage_public_daily. source_finished_at is the latest ingest run touching the day at publish time; a newer run means the day is republished.';

alter table public.usage_public_daily enable row level security;
alter table public.usage_public_school_months enable row level security;
alter table public.usage_public_months enable row level security;
alter table public.api_usage_publish_days enable row level security;

drop policy if exists usage_public_daily_read on public.usage_public_daily;
create policy usage_public_daily_read on public.usage_public_daily
  for select to anon, authenticated using (true);
drop policy if exists usage_public_school_months_read on public.usage_public_school_months;
create policy usage_public_school_months_read on public.usage_public_school_months
  for select to anon, authenticated using (true);
drop policy if exists usage_public_months_read on public.usage_public_months;
create policy usage_public_months_read on public.usage_public_months
  for select to anon, authenticated using (true);

revoke all on table
  public.usage_public_daily,
  public.usage_public_school_months,
  public.usage_public_months,
  public.api_usage_publish_days
from anon, authenticated;
grant select on table
  public.usage_public_daily,
  public.usage_public_school_months,
  public.usage_public_months
to anon, authenticated;
grant all on table
  public.usage_public_daily,
  public.usage_public_school_months,
  public.usage_public_months,
  public.api_usage_publish_days
to service_role;

-- Written with the service role only; RLS already hides its rows, and this
-- drops the default table grant as well.
revoke all on table public.api_usage_events from anon, authenticated;

create index if not exists api_usage_ingest_runs_ok_window_idx
  on public.api_usage_ingest_runs (window_start, window_end)
  where status = 'ok';

-- Latest finish time of the ingest runs behind a day, or null until the day
-- is ready: a successful daily count and every hour covered by a successful
-- hourly or backfill window.
create or replace function public.api_usage_day_source(p_day date)
returns timestamptz
language sql
stable
set search_path = public
as $$
  with bounds as (
    select (p_day::timestamp at time zone 'utc') as lo,
           ((p_day + 1)::timestamp at time zone 'utc') as hi
  ),
  daily as (
    select max(r.finished_at) as at
    from public.api_usage_ingest_runs r, bounds b
    where r.mode = 'daily' and r.status = 'ok' and r.window_start = b.lo
  ),
  hourly as (
    select max(r.finished_at) as at
    from public.api_usage_ingest_runs r, bounds b
    where r.mode in ('hourly', 'backfill') and r.status = 'ok'
      and r.window_start < b.hi and r.window_end > b.lo
  ),
  gaps as (
    select count(*) as n
    from bounds b, generate_series(b.lo, b.hi - interval '1 hour', interval '1 hour') as h
    where not exists (
      select 1 from public.api_usage_ingest_runs r
      where r.mode in ('hourly', 'backfill') and r.status = 'ok'
        and r.window_start <= h and r.window_end >= h + interval '1 hour'
    )
  )
  select case when daily.at is not null and hourly.at is not null and gaps.n = 0
              then greatest(daily.at, hourly.at) end
  from daily, hourly, gaps;
$$;

-- Client families outside the public list publish as 'unknown', so a new
-- family can never put a name on the page.
create or replace function public.api_usage_public_kind(p_family text)
returns text
language sql
immutable
set search_path = public
as $$
  select case when p_family in (
    'browser', 'script', 'integration', 'unknown', 'ai_user', 'ai_agent',
    'ai_crawler', 'declared_bot', 'mcp', 'cli'
  ) then p_family else 'unknown' end;
$$;

-- Same rule as the web's resolveCanonicalSchoolId: one primary target wins,
-- several primaries are ambiguous, otherwise one distinct target wins.
create or replace function public.api_usage_canonical_school(p_school_id text)
returns text
language sql
stable
set search_path = public
as $$
  with m as (
    select c.school_id, c.is_primary
    from public.institution_slug_crosswalk c
    where c.alias = p_school_id and c.school_id is not null
  ),
  prim as (select count(distinct school_id) as n, min(school_id) as id from m where is_primary),
  any_target as (select count(distinct school_id) as n, min(school_id) as id from m)
  select case
    when prim.n = 1 then prim.id
    when prim.n > 1 then null
    when any_target.n = 1 then any_target.id
  end
  from prim, any_target;
$$;

create or replace function public.api_usage_publish_day(p_day date, p_method_version integer)
returns boolean
language plpgsql
set search_path = public
as $$
declare
  v_source timestamptz;
  v_lo timestamptz := p_day::timestamp at time zone 'utc';
  v_hi timestamptz := (p_day + 1)::timestamp at time zone 'utc';
begin
  if p_day is null or p_method_version is null then
    raise exception 'api_usage_publish_day: day and method version are required';
  end if;
  v_source := public.api_usage_day_source(p_day);
  if v_source is null or not exists (
    select 1 from public.api_usage_downloads_daily
    where day = p_day and method_version = p_method_version
  ) then
    return false;
  end if;

  delete from public.usage_public_daily where day = p_day;

  insert into public.usage_public_daily (day, metric, access_method, client_kind, value, method_version)
  select p_day, 'unique_downloads', d.access_method,
         case when d.access_method = 'machine' and d.client_family = 'browser' then 'heavy_browser'
              else public.api_usage_public_kind(d.client_family) end,
         sum(d.unique_downloads), p_method_version
  from public.api_usage_downloads_daily d
  where d.day = p_day and d.method_version = p_method_version
    and d.access_method in ('browser', 'machine', 'bots_crawlers')
  group by 3, 4;

  insert into public.usage_public_daily (day, metric, access_method, client_kind, value, method_version)
  select p_day, 'site_downloads', 'browser', 'browser', sum(d.unique_downloads), p_method_version
  from public.api_usage_downloads_daily d
  where d.day = p_day and d.method_version = p_method_version
    and d.access_method = 'browser' and d.from_site
  having sum(d.unique_downloads) > 0;

  insert into public.usage_public_daily (day, metric, access_method, client_kind, value, method_version)
  select p_day, 'api_requests', '', public.api_usage_public_kind(r.client_family), sum(r.requests), p_method_version
  from public.api_gateway_rollups_hourly r
  where r.hour >= v_lo and r.hour < v_hi
    and r.classification = 'third_party'
    and r.surface in ('postgrest', 'edge_function')
    and r.route_kind <> 'options_preflight'
  group by 3, 4;

  insert into public.usage_public_daily (day, metric, access_method, client_kind, value, method_version)
  select p_day, 'friendly_api_requests', '', public.api_usage_public_kind(e.client_family), count(*), p_method_version
  from public.api_usage_events e
  where e.occurred_at >= v_lo and e.occurred_at < v_hi
    and e.http_method <> 'OPTIONS'
  group by 3, 4;

  -- Storage is left out: archive GETs with a collegedata.fyi referer are
  -- people's downloads, already counted as browser downloads.
  insert into public.usage_public_daily (day, metric, access_method, client_kind, value, method_version)
  select p_day, 'serving_requests', '', '', sum(r.requests), p_method_version
  from public.api_gateway_rollups_hourly r
  where r.hour >= v_lo and r.hour < v_hi
    and r.classification in ('first_party_site', 'friendly_api_upstream')
    and r.surface in ('postgrest', 'edge_function')
    and r.route_kind <> 'options_preflight'
  having sum(r.requests) > 0;

  insert into public.api_usage_publish_days (day, method_version, source_finished_at, published_at)
  values (p_day, p_method_version, v_source, now())
  on conflict (day) do update
    set method_version = excluded.method_version,
        source_finished_at = excluded.source_finished_at,
        published_at = excluded.published_at;
  return true;
end;
$$;

-- Rebuild one calendar month of school numbers once every day of it (from
-- the first published day on) is published. Returns the rows written, or
-- null while the month is incomplete.
create or replace function public.api_usage_publish_month(p_month date, p_method_version integer)
returns integer
language plpgsql
set search_path = public
as $$
declare
  v_first date;
  v_start date;
  v_end date;
  n_rows integer;
begin
  if p_month is null or date_trunc('month', p_month)::date <> p_month then
    raise exception 'api_usage_publish_month: month must be the first day of a month';
  end if;
  select min(day) into v_first from public.api_usage_publish_days;
  v_end := (p_month + interval '1 month')::date - 1;
  if v_first is null or v_end < v_first then
    return null;
  end if;
  v_start := greatest(p_month, v_first);
  if exists (
    select 1 from generate_series(v_start, v_end, interval '1 day') as g(d)
    where not exists (select 1 from public.api_usage_publish_days p where p.day = g.d::date)
  ) then
    return null;
  end if;

  delete from public.usage_public_school_months where month = p_month;

  with downloads as (
    select d.school_id as folder, sum(d.unique_downloads) as n
    from public.api_usage_downloads_daily d
    join public.api_usage_publish_days p on p.day = d.day and p.method_version = d.method_version
    where d.day between v_start and v_end
      and d.access_method in ('browser', 'machine')
    group by 1
  ),
  owners as (
    select split_part(a.storage_path, '/', 1) as folder,
           min(doc.school_id) as school_id,
           count(distinct doc.school_id) as owners
    from public.cds_artifacts a
    join public.cds_documents doc on doc.id = a.document_id
    where split_part(a.storage_path, '/', 1) in (select folder from downloads)
      and doc.school_id is not null
    group by 1
  ),
  owned as (
    select dl.n,
           case when o.owners = 1 then o.school_id else dl.folder end as owner
    from downloads dl
    left join owners o on o.folder = dl.folder
  ),
  totals as (
    select coalesce(public.api_usage_canonical_school(owner), owner) as school_id, sum(n) as n
    from owned
    group by 1
  ),
  schools as (
    select school_id, n from totals
    where n > 0 and school_id ~ '^[a-z0-9][a-z0-9-]{0,99}$'
  ),
  listed as (
    insert into public.usage_public_school_months (month, school_id, school_name, unique_downloads, method_version)
    select p_month, s.school_id,
           coalesce(
             (select dir.school_name from public.institution_directory dir
              where dir.school_id = s.school_id and dir.school_name is not null limit 1),
             (select doc.school_name from public.cds_documents doc
              where doc.school_id = s.school_id and doc.school_name is not null
              order by doc.cds_year desc nulls last, doc.updated_at desc nulls last limit 1),
             s.school_id
           ),
           (round(s.n / 10.0) * 10)::bigint,
           p_method_version
    from schools s
    where s.n >= 10
    returning 1
  )
  insert into public.usage_public_months (month, schools_with_downloads, schools_under_floor, method_version, published_at)
  select p_month, count(*), count(*) filter (where n < 10), p_method_version, now()
  from schools
  on conflict (month) do update
    set schools_with_downloads = excluded.schools_with_downloads,
        schools_under_floor = excluded.schools_under_floor,
        method_version = excluded.method_version,
        published_at = excluded.published_at;

  select count(*) into n_rows from public.usage_public_school_months where month = p_month;
  return n_rows;
end;
$$;

-- Publish up to p_limit ready days that are new, rewritten since they were
-- published, or published under another method version, then rebuild the
-- months they fall in. Call again while days_published = p_limit.
--
-- Every closed day since the first successful daily count is checked, so a
-- later day that never got one is still reported. Days that cannot be
-- published yet are counted by age: days_waiting are yesterday and the day
-- before (normal), days_stuck are 3 to 80 days ago and block their month
-- until a backfill or daily run fixes them, and days_expired are older than
-- the 90-day log retention allows fixing.
create or replace function public.api_usage_publish_pending(
  p_method_version integer,
  p_limit integer default 31
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  d date;
  m date;
  v_latest timestamptz;
  v_source timestamptz;
  v_ready boolean;
  months date[] := '{}';
  n_days integer := 0;
  n_waiting integer := 0;
  n_stuck integer := 0;
  n_expired integer := 0;
  n_months integer := 0;
  n_month_rows integer;
  v_today date := (now() at time zone 'utc')::date;
begin
  if p_method_version is null or p_limit is null or p_limit < 1 then
    raise exception 'api_usage_publish_pending: method version and a positive limit are required';
  end if;
  for d in
    select g::date
    from generate_series(
      (select min((r.window_start at time zone 'utc')::date)
       from public.api_usage_ingest_runs r where r.mode = 'daily' and r.status = 'ok'),
      v_today - 1,
      interval '1 day') as g
  loop
    select max(r.finished_at) into v_latest
    from public.api_usage_ingest_runs r
    where r.status = 'ok'
      and r.window_start < ((d + 1)::timestamp at time zone 'utc')
      and r.window_end > (d::timestamp at time zone 'utc');
    continue when exists (
      select 1 from public.api_usage_publish_days p
      where p.day = d and p.method_version = p_method_version and p.source_finished_at >= v_latest
    );
    v_source := public.api_usage_day_source(d);
    v_ready := v_source is not null and exists (
      select 1 from public.api_usage_downloads_daily
      where day = d and method_version = p_method_version
    );
    if not v_ready then
      if d >= v_today - 2 then
        n_waiting := n_waiting + 1;
      elsif d >= v_today - 80 then
        n_stuck := n_stuck + 1;
      else
        n_expired := n_expired + 1;
      end if;
      continue;
    end if;
    exit when n_days >= p_limit;
    if public.api_usage_publish_day(d, p_method_version) then
      n_days := n_days + 1;
      if not date_trunc('month', d)::date = any(months) then
        months := months || date_trunc('month', d)::date;
      end if;
    end if;
  end loop;

  foreach m in array months loop
    n_month_rows := public.api_usage_publish_month(m, p_method_version);
    if n_month_rows is not null then
      n_months := n_months + 1;
    end if;
  end loop;

  return jsonb_build_object(
    'days_published', n_days,
    'days_waiting', n_waiting,
    'days_stuck', n_stuck,
    'days_expired', n_expired,
    'months_published', n_months
  );
end;
$$;

-- Full scan of everything published. Every value must be zero.
create or replace function public.usage_public_violations()
returns jsonb
language sql
stable
set search_path = public
as $$
  select jsonb_build_object(
    'school_cells_off_rule',
      (select count(*) from public.usage_public_school_months
       where unique_downloads is null or unique_downloads < 10 or unique_downloads % 10 <> 0),
    'school_months_incomplete',
      (select count(*) from (
         select month from public.usage_public_school_months
         union select month from public.usage_public_months
       ) s
       where exists (
         select 1 from generate_series(
           greatest(s.month, (select min(day) from public.api_usage_publish_days)),
           (s.month + interval '1 month')::date - 1,
           interval '1 day') as g(d)
         where not exists (select 1 from public.api_usage_publish_days p where p.day = g.d::date)
       )),
    'school_months_without_summary',
      (select count(distinct s.month) from public.usage_public_school_months s
       where not exists (select 1 from public.usage_public_months m where m.month = s.month)),
    'summary_count_mismatch',
      (select count(*) from public.usage_public_months m
       where m.schools_with_downloads - m.schools_under_floor
             <> (select count(*) from public.usage_public_school_months s where s.month = m.month)),
    'days_without_publish_record',
      (select count(distinct u.day) from public.usage_public_daily u
       where not exists (select 1 from public.api_usage_publish_days p where p.day = u.day)),
    'unexpected_columns',
      (select count(*) from information_schema.columns c
       where c.table_schema = 'public'
         and (c.table_name, c.column_name) not in (
           ('usage_public_daily', 'day'), ('usage_public_daily', 'metric'),
           ('usage_public_daily', 'access_method'), ('usage_public_daily', 'client_kind'),
           ('usage_public_daily', 'value'), ('usage_public_daily', 'method_version'),
           ('usage_public_daily', 'published_at'),
           ('usage_public_school_months', 'month'), ('usage_public_school_months', 'school_id'),
           ('usage_public_school_months', 'school_name'),
           ('usage_public_school_months', 'unique_downloads'),
           ('usage_public_school_months', 'method_version'),
           ('usage_public_school_months', 'published_at'),
           ('usage_public_months', 'month'),
           ('usage_public_months', 'schools_with_downloads'),
           ('usage_public_months', 'schools_under_floor'),
           ('usage_public_months', 'method_version'),
           ('usage_public_months', 'published_at')
         )
         and c.table_name in ('usage_public_daily', 'usage_public_school_months', 'usage_public_months')),
    'private_tables_readable_by_anon',
      (select count(*) from (values
         ('public.api_usage_publish_days'),
         ('public.api_usage_events'),
         ('public.api_usage_downloads_daily'),
         ('public.api_gateway_rollups_hourly'),
         ('public.api_gateway_clients_hourly'),
         ('public.api_gateway_schools_hourly'),
         ('public.api_usage_hash_salts'),
         ('public.api_usage_ingest_runs')
       ) as t(rel)
       where has_table_privilege('anon', t.rel, 'select')
          or has_table_privilege('authenticated', t.rel, 'select'))
  );
$$;

revoke all on function public.api_usage_day_source(date) from public, anon, authenticated;
revoke all on function public.api_usage_canonical_school(text) from public, anon, authenticated;
revoke all on function public.api_usage_public_kind(text) from public, anon, authenticated;
revoke all on function public.api_usage_publish_day(date, integer) from public, anon, authenticated;
revoke all on function public.api_usage_publish_month(date, integer) from public, anon, authenticated;
revoke all on function public.api_usage_publish_pending(integer, integer) from public, anon, authenticated;
revoke all on function public.usage_public_violations() from public, anon, authenticated;
grant execute on function public.api_usage_day_source(date) to service_role;
grant execute on function public.api_usage_canonical_school(text) to service_role;
grant execute on function public.api_usage_public_kind(text) to service_role;
grant execute on function public.api_usage_publish_day(date, integer) to service_role;
grant execute on function public.api_usage_publish_month(date, integer) to service_role;
grant execute on function public.api_usage_publish_pending(integer, integer) to service_role;
grant execute on function public.usage_public_violations() to service_role;

do $$
begin
  if not has_table_privilege('anon', 'public.usage_public_daily', 'select')
     or not has_table_privilege('anon', 'public.usage_public_school_months', 'select')
     or not has_table_privilege('anon', 'public.usage_public_months', 'select') then
    raise exception 'PRD 033: public usage tables are not readable by anon';
  end if;
  if has_table_privilege('anon', 'public.usage_public_daily', 'insert')
     or has_table_privilege('anon', 'public.usage_public_school_months', 'insert')
     or has_table_privilege('anon', 'public.usage_public_months', 'insert')
     or has_table_privilege('anon', 'public.api_usage_publish_days', 'select')
     or has_table_privilege('anon', 'public.api_usage_events', 'select') then
    raise exception 'PRD 033: anon can write public usage tables or read the publish log';
  end if;
  if has_function_privilege('anon', 'public.api_usage_publish_pending(integer, integer)', 'execute')
     or has_function_privilege('anon', 'public.usage_public_violations()', 'execute') then
    raise exception 'PRD 033: publish functions are executable by anon';
  end if;
end;
$$;
