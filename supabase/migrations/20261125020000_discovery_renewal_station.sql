-- Discovery renewal station + heartbeat history (#463, postmortem
-- 2026-11-24-stale-discovery-seeds). Apply from main after merge; do not push
-- from a branch.
--
-- 1. New board station `discovery_renewal`: the current-year renewal outcome.
-- 2. finder_stuck_pdf, headless_archive and finder_brave accept the new counters
--    their jobs now report.
-- 3. pipeline_heartbeat_history keeps one row per finished run, so the page can
--    show month-on-month change, not only the latest summary.

-- 1. Station ---------------------------------------------------------------

insert into public.pipeline_stations (
  station_id, display_name, cadence_label, class, source_kind, on_board, sort_order,
  required_keys, allowed_keys
) values (
  'discovery_renewal',
  'Renewal',
  'daily · SLA 36h',
  'daily_sla',
  'gha',
  true,
  5,
  array['current_year', 'renewed', 'prev_schools', 'renewal_pct', 'floor_pct', 'below_floor'],
  array[
    'current_year', 'renewed', 'prev_schools', 'renewal_pct', 'floor_pct', 'below_floor',
    'months_since_fall', 'next_year', 'next_renewed', 'next_prev_schools',
    'next_renewal_pct', 'next_floor_pct', 'next_below_floor', 'lapsed_schools',
    'two_year_renewed', 'two_year_prev_schools', 'two_year_renewal_pct',
    'two_year_floor_pct', 'two_year_below_floor',
    'floor_overridden', 'alarm_issue', 'same_year_duplicates', 'seeds_without_new_year',
    'seeds_with_seed', 'seeds_without_new_year_one_file',
    'seeds_without_new_year_listing_page',
    'flagged_current_docs', 'sub_institutional_excluded',
    'outstanding_below_floor', 'outstanding_years',
    'arrivals_30d', 'arrivals_expected_30d', 'arrivals_below_floor',
    'arrivals_window_days', 'unextracted_current_docs',
    'arrivals_checked', 'arrivals_60d', 'arrivals_expected_60d',
    'arrivals_current_30d', 'arrivals_current_60d',
    'arrivals_expected_current_30d', 'arrivals_expected_current_60d',
    'arrivals_current_window_days', 'arrivals_current_checked',
    'arrivals_current_below_floor', 'arrivals_next_30d',
    'arrivals_next_60d', 'arrivals_expected_next_30d',
    'arrivals_expected_next_60d', 'arrivals_next_window_days',
    'arrivals_next_checked', 'arrivals_next_below_floor',
    'unextracted_next_docs',
    'fetch_failures', 'fetch_failures_blocked', 'fetch_failures_viewer',
    'fetch_failures_section_files', 'fetch_failures_dead_link', 'fetch_failures_other',
    'run_url'
  ]
)
on conflict (station_id) do nothing;

insert into public.pipeline_heartbeats (station_id)
values ('discovery_renewal')
on conflict (station_id) do nothing;

-- 2. finder_stuck_pdf: append new keys, no duplicates ----------------------

update public.pipeline_stations s
set allowed_keys = (
  select array_agg(k order by first_pos)
  from (
    select k, min(pos) as first_pos
    from unnest(
      s.allowed_keys || array[
        'total', 'fresh', 'skipped', 'fixed', 'listing_unverified',
        'skipped_listing_seed', 'skipped_no_seed'
      ]
    ) with ordinality as t(k, pos)
    group by k
  ) d
)
where s.station_id = 'finder_stuck_pdf';

update public.pipeline_stations s
set allowed_keys = (
  select array_agg(k order by first_pos)
  from (
    select k, min(pos) as first_pos
    from unnest(
      s.allowed_keys || array[
        'schools_targeted', 'schools_capped', 'years_capped', 'years_below_min',
        'years_unparseable', 'years_unparseable_known', 'summary_missing'
      ]
    ) with ordinality as t(k, pos)
    group by k
  ) d
)
where s.station_id = 'headless_archive';

update public.pipeline_stations s
set allowed_keys = (
  select array_agg(k order by first_pos)
  from (
    select k, min(pos) as first_pos
    from unnest(
      s.allowed_keys || array[
        'attempted', 'not_searched', 'not_searched_causes', 'capped_out', 'capped_out_detail'
      ]
    ) with ordinality as t(k, pos)
    group by k
  ) d
)
where s.station_id = 'finder_brave';

-- 3. Heartbeat history -----------------------------------------------------

create table if not exists public.pipeline_heartbeat_history (
  id bigserial primary key,
  station_id text not null references public.pipeline_stations (station_id),
  status text not null,
  trigger text,
  summary jsonb not null default '{}'::jsonb,
  error_code text,
  recorded_at timestamptz not null default now()
);

comment on table public.pipeline_heartbeat_history is
  'One row per finished pipeline run (status ok or error), written by a trigger on pipeline_heartbeats. summary is the writer-filtered last_summary. Public page reads pipeline_station_history(); anon cannot SELECT.';

create index if not exists pipeline_heartbeat_history_station_recorded_idx
  on public.pipeline_heartbeat_history (station_id, recorded_at desc);

alter table public.pipeline_heartbeat_history enable row level security;

revoke all on table public.pipeline_heartbeat_history from public;
revoke all on table public.pipeline_heartbeat_history from anon, authenticated;
grant all on table public.pipeline_heartbeat_history to service_role;

revoke all on sequence public.pipeline_heartbeat_history_id_seq from public;
revoke all on sequence public.pipeline_heartbeat_history_id_seq from anon, authenticated;
grant all on sequence public.pipeline_heartbeat_history_id_seq to service_role;

create or replace function public.pipeline_heartbeat_history_capture()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  station_class text;
begin
  -- Finishes only. 'running' updates and no-op maintenance updates are skipped.
  -- High-frequency stations (hourly_sla, continuous_sla) are not kept: archive_process
  -- finishes every 30 s and would add about a million rows a year for no trend value.
  select class into station_class
  from public.pipeline_stations where station_id = new.station_id;

  if station_class in ('monthly_sla', 'daily_sla', 'yearly', 'adhoc')
     and new.last_finished_at is not null
     and new.last_status in ('ok', 'error')
     and (tg_op = 'INSERT' or new.last_finished_at is distinct from old.last_finished_at)
  then
    insert into public.pipeline_heartbeat_history (
      station_id, status, trigger, summary, error_code, recorded_at
    ) values (
      new.station_id,
      new.last_status,
      new.last_trigger,
      new.last_summary,
      new.last_error_code,
      new.last_finished_at
    );
    -- Retention: 400 days per station (indexed on station_id, recorded_at).
    delete from public.pipeline_heartbeat_history
    where station_id = new.station_id
      and recorded_at < now() - interval '400 days';
  end if;
  return null;
end;
$$;

revoke all on function public.pipeline_heartbeat_history_capture() from public;
revoke all on function public.pipeline_heartbeat_history_capture() from anon, authenticated;

drop trigger if exists pipeline_heartbeat_history_capture on public.pipeline_heartbeats;
create trigger pipeline_heartbeat_history_capture
  after insert or update on public.pipeline_heartbeats
  for each row
  execute function public.pipeline_heartbeat_history_capture();

create or replace function public.pipeline_station_history(
  p_station_id text,
  p_limit int default 24
)
returns table (
  recorded_at timestamptz,
  status text,
  trigger text,
  summary jsonb
)
language sql
stable
security definer
set search_path = public
as $$
  select h.recorded_at, h.status, h.trigger, h.summary
  from public.pipeline_heartbeat_history h
  join public.pipeline_stations s using (station_id)
  where h.station_id = p_station_id
    and s.on_board
  order by h.recorded_at desc, h.id desc
  limit greatest(1, least(coalesce(p_limit, 24), 100));
$$;

comment on function public.pipeline_station_history(text, int) is
  'Anon-readable history of finished runs for one on-board station, newest first, capped at 100 rows. summary is already filtered to the station allowed keys by record_pipeline_heartbeat. Only monthly, daily, yearly and adhoc stations are recorded. Callers wanting the scheduled trend should filter trigger in (''schedule'', ''cron'').';

revoke all on function public.pipeline_station_history(text, int) from public;
grant execute on function public.pipeline_station_history(text, int) to anon, authenticated, service_role;

-- Backfill: one row per station from its current finish, once.
insert into public.pipeline_heartbeat_history (
  station_id, status, trigger, summary, error_code, recorded_at
)
select h.station_id, h.last_status, h.last_trigger, h.last_summary,
       h.last_error_code, h.last_finished_at
from public.pipeline_heartbeats h
join public.pipeline_stations st using (station_id)
where st.class in ('monthly_sla', 'daily_sla', 'yearly', 'adhoc')
  and h.last_finished_at is not null
  and h.last_status in ('ok', 'error')
  and not exists (
    select 1 from public.pipeline_heartbeat_history x
    where x.station_id = h.station_id and x.recorded_at = h.last_finished_at
  );

-- 4. Verification (no production-data assumptions) --------------------------

do $$
declare
  keys text[];
begin
  if not exists (
    select 1 from public.pipeline_stations
    where station_id = 'discovery_renewal' and on_board and sort_order = 5
      and class = 'daily_sla' and source_kind = 'gha'
  ) then
    raise exception 'discovery_renewal station missing or wrong';
  end if;
  if not exists (
    select 1 from public.pipeline_heartbeats where station_id = 'discovery_renewal'
  ) then
    raise exception 'discovery_renewal heartbeat row missing';
  end if;
  select allowed_keys into keys from public.pipeline_stations
  where station_id = 'discovery_renewal';
  if not (keys @> array[
    'current_year', 'below_floor', 'run_url', 'seeds_without_new_year',
    'seeds_with_seed', 'seeds_without_new_year_one_file',
    'seeds_without_new_year_listing_page', 'flagged_current_docs',
    'sub_institutional_excluded', 'outstanding_below_floor', 'outstanding_years',
    'arrivals_30d', 'arrivals_expected_30d', 'arrivals_below_floor',
    'arrivals_window_days', 'unextracted_current_docs',
    'arrivals_checked', 'arrivals_60d', 'arrivals_expected_60d',
    'arrivals_current_30d', 'arrivals_current_60d',
    'arrivals_expected_current_30d', 'arrivals_expected_current_60d',
    'arrivals_current_window_days', 'arrivals_current_checked',
    'arrivals_current_below_floor', 'arrivals_next_30d',
    'arrivals_next_60d', 'arrivals_expected_next_30d',
    'arrivals_expected_next_60d', 'arrivals_next_window_days',
    'arrivals_next_checked', 'arrivals_next_below_floor',
    'unextracted_next_docs'
  ]) then
    raise exception 'discovery_renewal allowed_keys missing seed keys: %', keys;
  end if;
  if cardinality(keys) <> (select count(distinct k) from unnest(keys) k) then
    raise exception 'discovery_renewal allowed_keys has duplicates: %', keys;
  end if;

  select allowed_keys into keys from public.pipeline_stations
  where station_id = 'finder_stuck_pdf';
  if keys is null then
    raise exception 'finder_stuck_pdf station missing or has null allowed_keys';
  end if;
  if not (keys @> array['stuck', 'still_stuck', 'run_url', 'total', 'skipped_no_seed']) then
    raise exception 'finder_stuck_pdf allowed_keys not extended: %', keys;
  end if;
  if cardinality(keys) <> (select count(distinct k) from unnest(keys) k) then
    raise exception 'finder_stuck_pdf allowed_keys has duplicates: %', keys;
  end if;

  select allowed_keys into keys from public.pipeline_stations
  where station_id = 'headless_archive';
  if keys is null then
    raise exception 'headless_archive station missing or has null allowed_keys';
  end if;
  if not (keys @> array['schools_attempted', 'run_url', 'schools_targeted', 'years_capped', 'summary_missing']) then
    raise exception 'headless_archive allowed_keys not extended: %', keys;
  end if;
  if cardinality(keys) <> (select count(distinct k) from unnest(keys) k) then
    raise exception 'headless_archive allowed_keys has duplicates: %', keys;
  end if;

  select allowed_keys into keys from public.pipeline_stations
  where station_id = 'finder_brave';
  if keys is null then
    raise exception 'finder_brave station missing or has null allowed_keys';
  end if;
  if not (keys @> array['probed', 'run_url', 'attempted', 'not_searched', 'not_searched_causes', 'capped_out', 'capped_out_detail']) then
    raise exception 'finder_brave allowed_keys not extended: %', keys;
  end if;
  if cardinality(keys) <> (select count(distinct k) from unnest(keys) k) then
    raise exception 'finder_brave allowed_keys has duplicates: %', keys;
  end if;

  if not exists (
    select 1 from pg_trigger
    where tgrelid = 'public.pipeline_heartbeats'::regclass
      and tgname = 'pipeline_heartbeat_history_capture'
      and not tgisinternal
  ) then
    raise exception 'pipeline_heartbeat_history_capture trigger not installed';
  end if;

  if has_table_privilege('anon', 'public.pipeline_heartbeat_history', 'select') then
    raise exception 'anon must not select pipeline_heartbeat_history';
  end if;
  if not has_function_privilege('anon', 'public.pipeline_station_history(text, int)', 'execute') then
    raise exception 'anon must execute pipeline_station_history';
  end if;
  if has_function_privilege('anon', 'public.pipeline_heartbeat_history_capture()', 'execute') then
    raise exception 'anon must not execute the history trigger function';
  end if;
end;
$$;
