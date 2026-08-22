-- PRD 030 M0: public pipeline observation.
-- Registry + heartbeat state + writer RPC (service_role) + anon facts function.
-- pg_cron jobs are secret-gated and absent locally; this migration does not
-- assert cron.job rows. Heartbeat silence is the public signal.

create table public.pipeline_stations (
  station_id text primary key,
  display_name text not null,
  cadence_label text not null,
  class text not null,
  source_kind text not null,
  on_board boolean not null,
  sort_order integer not null,
  required_keys text[] not null default '{}',
  allowed_keys text[] not null default '{}',
  constraint pipeline_stations_class_valid
    check (class in (
      'monthly_sla',
      'daily_sla',
      'hourly_sla',
      'continuous_sla',
      'yearly',
      'adhoc'
    )),
  constraint pipeline_stations_source_kind_valid
    check (source_kind in ('gha', 'pg_cron', 'sql', 'operator'))
);

comment on table public.pipeline_stations is
  'Static registry for PRD 030 pipeline observation. Jobs do not update this table. record_pipeline_heartbeat validates writes against required/allowed keys here.';

create table public.pipeline_heartbeats (
  station_id text primary key references public.pipeline_stations (station_id),
  last_started_at timestamptz,
  last_finished_at timestamptz,
  last_status text not null default 'never',
  last_trigger text,
  last_summary jsonb not null default '{}'::jsonb,
  last_scheduled_finished_at timestamptz,
  last_scheduled_status text not null default 'never',
  last_scheduled_summary jsonb not null default '{}'::jsonb,
  last_scheduled_error_code text not null default 'none',
  last_error_code text not null default 'none',
  source_url text,
  updated_at timestamptz not null default now(),
  constraint pipeline_heartbeats_status_valid
    check (last_status in ('never', 'running', 'ok', 'error')),
  constraint pipeline_heartbeats_scheduled_status_valid
    check (last_scheduled_status in ('never', 'running', 'ok', 'error')),
  constraint pipeline_heartbeats_trigger_valid
    check (last_trigger is null or last_trigger in ('schedule', 'dispatch', 'operator', 'cron')),
  constraint pipeline_heartbeats_error_code_valid
    check (last_error_code in (
      'search_provider_rejected',
      'missing_required_secret',
      'heartbeat_summary_malformed',
      'worker_timeout',
      'job_failed',
      'none'
    )),
  constraint pipeline_heartbeats_scheduled_error_code_valid
    check (last_scheduled_error_code in (
      'search_provider_rejected',
      'missing_required_secret',
      'heartbeat_summary_malformed',
      'worker_timeout',
      'job_failed',
      'none'
    ))
);

comment on table public.pipeline_heartbeats is
  'Per-station pipeline clocks. Anon cannot SELECT. Public page reads pipeline_station_facts(). Do not key caches on updated_at.';

comment on column public.pipeline_heartbeats.last_scheduled_finished_at is
  'Last finish whose trigger was schedule or cron. Dispatch and operator never copy here.';

comment on column public.pipeline_heartbeats.updated_at is
  'Row maintenance timestamp. Never use as an SLA clock.';

create index if not exists cds_documents_extraction_pending_idx
  on public.cds_documents (id)
  where extraction_status = 'extraction_pending';

insert into public.pipeline_stations (
  station_id, display_name, cadence_label, class, source_kind, on_board, sort_order,
  required_keys, allowed_keys
) values
  (
    'finder_brave', 'Finder', 'monthly · scheduled SLA 40d', 'monthly_sla', 'gha', true, 10,
    array['probed', 'found', 'replaced', 'budget_remaining'],
    array['probed', 'found', 'replaced', 'budget_remaining', 'pr_url', 'run_url']
  ),
  (
    'finder_stuck_pdf', 'Stuck PDFs', 'monthly · scheduled SLA 40d', 'monthly_sla', 'gha', true, 20,
    array['stuck', 'reprobed', 'still_stuck'],
    array['stuck', 'reprobed', 'still_stuck', 'pr_url', 'run_url']
  ),
  (
    'finder_landing_hints', 'Landing hints', 'monthly · scheduled SLA 40d', 'monthly_sla', 'gha', true, 30,
    array['proposals', 'promoted'],
    array['proposals', 'promoted', 'pr_url', 'run_url']
  ),
  (
    'archive_enqueue', 'Enqueue', 'daily · SLA 36h', 'daily_sla', 'pg_cron', true, 40,
    array['queued', 'skipped', 'errors'],
    array['queued', 'skipped', 'errors', 'pr_url', 'run_url']
  ),
  (
    'archive_process', 'Process', 'every 30s', 'continuous_sla', 'pg_cron', true, 50,
    array['dequeued', 'queue_depth', 'inserted', 'refreshed', 'walled', 'events_written'],
    array['dequeued', 'queue_depth', 'inserted', 'refreshed', 'walled', 'events_written', 'pr_url', 'run_url']
  ),
  (
    'extraction_worker', 'Extract', 'daily · pending drain', 'daily_sla', 'gha', true, 60,
    array['extracted', 'failed', 'pending_remaining', 'stopped_reason'],
    array['extracted', 'failed', 'pending_remaining', 'stopped_reason', 'llm_fallback', 'pr_url', 'run_url']
  ),
  (
    'coverage_refresh', 'Coverage', 'hourly · SLA 3h', 'hourly_sla', 'pg_cron', true, 70,
    array['current', 'stale', 'inaccessible', 'never_found'],
    array['current', 'stale', 'inaccessible', 'never_found', 'overrides_stale', 'pr_url', 'run_url']
  ),
  (
    'serving_cache_refresh', 'Serving caches', 'hourly · SLA 3h', 'hourly_sla', 'sql', true, 80,
    array['ok'],
    array['ok', 'pr_url', 'run_url']
  ),
  (
    'ipeds_release_probe', 'IPEDS probe', 'monthly · scheduled SLA 40d', 'monthly_sla', 'gha', true, 90,
    array['new_release', 'issue_opened'],
    array['new_release', 'issue_opened', 'pr_url', 'run_url']
  ),
  (
    'schema_build', 'Schema', 'yearly · slate until a heartbeat', 'yearly', 'operator', true, 100,
    array['years'],
    array['years', 'pr_url', 'run_url']
  ),
  (
    'scorecard_load', 'Scorecard', 'yearly · slate until a heartbeat', 'yearly', 'operator', true, 110,
    array['vintage', 'rows'],
    array['vintage', 'rows', 'pr_url', 'run_url']
  ),
  (
    'directory_enqueue', 'Directory enqueue', 'manual', 'adhoc', 'operator', false, 200,
    array['seeded'],
    array['seeded', 'pr_url', 'run_url']
  ),
  (
    'mirror_ingest', 'Mirror ingest', 'manual', 'adhoc', 'operator', false, 210,
    array['source', 'rows_added'],
    array['source', 'rows_added', 'pr_url', 'run_url']
  );

insert into public.pipeline_heartbeats (station_id)
select station_id from public.pipeline_stations;

alter table public.pipeline_stations enable row level security;
alter table public.pipeline_heartbeats enable row level security;

revoke all on table public.pipeline_stations from public;
revoke all on table public.pipeline_stations from anon, authenticated;
grant all on table public.pipeline_stations to service_role;

revoke all on table public.pipeline_heartbeats from public;
revoke all on table public.pipeline_heartbeats from anon, authenticated;
grant all on table public.pipeline_heartbeats to service_role;

create or replace function public.pipeline_sanitize_source_url(p_url text)
returns text
language sql
immutable
parallel safe
as $$
  select case
    when p_url is null then null
    when p_url ~ '^https://github\.com/bolewood/collegedata-fyi/(actions/runs|pull)/[0-9]+/?$'
      then regexp_replace(p_url, '/$', '')
    else null
  end;
$$;

comment on function public.pipeline_sanitize_source_url(text) is
  'Allowlist for public heartbeat URLs: Actions run pages and repo pull requests only.';

revoke all on function public.pipeline_sanitize_source_url(text) from public;
revoke all on function public.pipeline_sanitize_source_url(text) from anon, authenticated;
grant execute on function public.pipeline_sanitize_source_url(text) to service_role;

create or replace function public.record_pipeline_heartbeat(
  p_station_id text,
  p_status text,
  p_trigger text,
  p_summary jsonb,
  p_error_code text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  registry public.pipeline_stations%rowtype;
  filtered jsonb := '{}'::jsonb;
  key text;
  value jsonb;
  status_out text;
  error_out text;
  source_out text;
  is_finish boolean;
  missing boolean := false;
  required_key text;
begin
  if p_station_id is null then
    raise exception 'record_pipeline_heartbeat: station_id is required';
  end if;

  select * into registry
  from public.pipeline_stations
  where station_id = p_station_id;

  if not found then
    raise exception 'record_pipeline_heartbeat: unknown station_id %', p_station_id;
  end if;

  if p_status not in ('running', 'ok', 'error') then
    raise exception 'record_pipeline_heartbeat: invalid status %', p_status;
  end if;

  if p_trigger not in ('schedule', 'dispatch', 'operator', 'cron') then
    raise exception 'record_pipeline_heartbeat: invalid trigger %', p_trigger;
  end if;

  if p_error_code is null or p_error_code not in (
    'search_provider_rejected',
    'missing_required_secret',
    'heartbeat_summary_malformed',
    'worker_timeout',
    'job_failed',
    'none'
  ) then
    raise exception 'record_pipeline_heartbeat: invalid error_code %', p_error_code;
  end if;

  for key, value in
    select * from jsonb_each(coalesce(p_summary, '{}'::jsonb))
  loop
    if key = any (registry.allowed_keys) then
      if key in ('run_url', 'pr_url') then
        if jsonb_typeof(value) = 'string' then
          source_out := public.pipeline_sanitize_source_url(value #>> '{}');
          if source_out is not null then
            filtered := filtered || jsonb_build_object(key, to_jsonb(source_out));
          end if;
        end if;
      else
        filtered := filtered || jsonb_build_object(key, value);
      end if;
    end if;
  end loop;

  is_finish := p_status in ('ok', 'error');
  status_out := p_status;
  error_out := p_error_code;

  if is_finish then
    foreach required_key in array registry.required_keys
    loop
      if not (filtered ? required_key) then
        missing := true;
        exit;
      end if;
    end loop;
    if missing then
      status_out := 'error';
      error_out := 'heartbeat_summary_malformed';
    end if;
  end if;

  if source_out is null and filtered ? 'run_url' then
    source_out := public.pipeline_sanitize_source_url(filtered ->> 'run_url');
  end if;
  if source_out is null and filtered ? 'pr_url' then
    source_out := public.pipeline_sanitize_source_url(filtered ->> 'pr_url');
  end if;

  insert into public.pipeline_heartbeats as h (
    station_id,
    last_started_at,
    last_finished_at,
    last_status,
    last_trigger,
    last_summary,
    last_scheduled_finished_at,
    last_scheduled_status,
    last_scheduled_summary,
    last_scheduled_error_code,
    last_error_code,
    source_url,
    updated_at
  ) values (
    p_station_id,
    case when p_status = 'running' then now() else null end,
    case when is_finish then now() else null end,
    status_out,
    p_trigger,
    filtered,
    case
      when is_finish and p_trigger in ('schedule', 'cron') then now()
      else null
    end,
    case
      when is_finish and p_trigger in ('schedule', 'cron') then status_out
      else 'never'
    end,
    case
      when is_finish and p_trigger in ('schedule', 'cron') then filtered
      else '{}'::jsonb
    end,
    case
      when is_finish and p_trigger in ('schedule', 'cron') then error_out
      else 'none'
    end,
    error_out,
    source_out,
    now()
  )
  on conflict (station_id) do update set
    last_started_at = case
      when p_status = 'running' then now()
      else coalesce(h.last_started_at, excluded.last_started_at)
    end,
    last_finished_at = case
      when is_finish then now()
      else h.last_finished_at
    end,
    last_status = excluded.last_status,
    last_trigger = excluded.last_trigger,
    last_summary = excluded.last_summary,
    last_scheduled_finished_at = case
      when is_finish and p_trigger in ('schedule', 'cron') then now()
      else h.last_scheduled_finished_at
    end,
    last_scheduled_status = case
      when is_finish and p_trigger in ('schedule', 'cron') then excluded.last_status
      else h.last_scheduled_status
    end,
    last_scheduled_summary = case
      when is_finish and p_trigger in ('schedule', 'cron') then excluded.last_summary
      else h.last_scheduled_summary
    end,
    last_scheduled_error_code = case
      when is_finish and p_trigger in ('schedule', 'cron') then excluded.last_error_code
      else h.last_scheduled_error_code
    end,
    last_error_code = excluded.last_error_code,
    source_url = coalesce(excluded.source_url, h.source_url),
    updated_at = now();
end;
$$;

comment on function public.record_pipeline_heartbeat(text, text, text, jsonb, text) is
  'Service-role writer for pipeline_heartbeats. Drops unknown JSON keys, strips nested counts by allowlist, and refuses to persist ok when required finish keys are missing.';

revoke all on function public.record_pipeline_heartbeat(text, text, text, jsonb, text) from public;
revoke all on function public.record_pipeline_heartbeat(text, text, text, jsonb, text) from anon, authenticated;
grant execute on function public.record_pipeline_heartbeat(text, text, text, jsonb, text) to service_role;

create or replace function public.pipeline_station_facts()
returns table (
  station_id text,
  display_name text,
  cadence_label text,
  class text,
  on_board boolean,
  sort_order integer,
  last_started_at timestamptz,
  last_finished_at timestamptz,
  last_status text,
  last_trigger text,
  last_summary jsonb,
  last_scheduled_finished_at timestamptz,
  last_scheduled_status text,
  last_scheduled_summary jsonb,
  last_scheduled_error_code text,
  last_error_code text,
  source_url text,
  queue_unfinished bigint,
  extraction_pending bigint
)
language sql
stable
security definer
set search_path = public
as $$
  with live as (
    select
      (select count(*) from public.archive_queue q where q.status in ('ready', 'processing')) as queue_unfinished,
      (select count(*) from public.cds_documents d where d.extraction_status = 'extraction_pending') as extraction_pending
  )
  select
    s.station_id,
    s.display_name,
    s.cadence_label,
    s.class,
    s.on_board,
    s.sort_order,
    h.last_started_at,
    h.last_finished_at,
    h.last_status,
    h.last_trigger,
    h.last_summary,
    h.last_scheduled_finished_at,
    h.last_scheduled_status,
    h.last_scheduled_summary,
    h.last_scheduled_error_code,
    h.last_error_code,
    h.source_url,
    case when s.station_id = 'archive_process' then live.queue_unfinished else null end,
    case when s.station_id = 'extraction_worker' then live.extraction_pending else null end
  from public.pipeline_stations s
  join public.pipeline_heartbeats h using (station_id)
  cross join live
  order by s.sort_order;
$$;

comment on function public.pipeline_station_facts() is
  'Anon-readable SECURITY DEFINER snapshot of pipeline clocks plus live unfinished/pending counts. Not a view: owner-rights views reintroduce the advisor warning cleared in 20260614141000.';

revoke all on function public.pipeline_station_facts() from public;
grant execute on function public.pipeline_station_facts() to anon, authenticated, service_role;

create or replace function public.refresh_public_serving_caches()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  merit_count integer;
  stats_count integer;
  result jsonb;
begin
  begin
    merit_count := public.refresh_school_merit_profile_cache();
    stats_count := public.refresh_site_stats_cache();
    result := jsonb_build_object(
      'school_merit_profile_cache', merit_count,
      'site_stats_cache', stats_count
    );
    perform public.record_pipeline_heartbeat(
      'serving_cache_refresh',
      'ok',
      'cron',
      jsonb_build_object('ok', true),
      'none'
    );
    return result;
  exception
    when others then
      begin
        perform public.record_pipeline_heartbeat(
          'serving_cache_refresh',
          'error',
          'cron',
          jsonb_build_object('ok', false),
          'job_failed'
        );
      exception
        when others then
          raise warning 'pipeline heartbeat failed for serving_cache_refresh: %', sqlerrm;
      end;
      raise;
  end;
end;
$$;

comment on function public.refresh_public_serving_caches() is
  'Refreshes materialized public serving caches and writes the serving_cache_refresh heartbeat.';

revoke all on table public.archive_queue from public;
revoke all on table public.archive_queue from anon, authenticated;
grant all on table public.archive_queue to service_role;

revoke all on public.bot_challenged_documents from public;
revoke select on public.bot_challenged_documents from anon, authenticated;
grant select on public.bot_challenged_documents to service_role;

revoke all on public.latest_school_hosting from public;
revoke select on public.latest_school_hosting from anon, authenticated;
grant select on public.latest_school_hosting to service_role;

-- Self-tests. Reset seed rows afterward so first public paint is still never.

do $$
declare
  summary jsonb;
  status_out text;
  error_out text;
  source_out text;
begin
  if has_function_privilege('anon', 'public.record_pipeline_heartbeat(text, text, text, jsonb, text)', 'execute') then
    raise exception 'anon must not execute record_pipeline_heartbeat';
  end if;
  if has_function_privilege('authenticated', 'public.record_pipeline_heartbeat(text, text, text, jsonb, text)', 'execute') then
    raise exception 'authenticated must not execute record_pipeline_heartbeat';
  end if;
  if not has_function_privilege('anon', 'public.pipeline_station_facts()', 'execute') then
    raise exception 'anon must execute pipeline_station_facts';
  end if;
  if has_table_privilege('anon', 'public.pipeline_heartbeats', 'select') then
    raise exception 'anon must not select pipeline_heartbeats';
  end if;
  if has_table_privilege('anon', 'public.pipeline_stations', 'select') then
    raise exception 'anon must not select pipeline_stations';
  end if;
  if has_table_privilege('anon', 'public.archive_queue', 'select') then
    raise exception 'anon must not select archive_queue';
  end if;
  if has_table_privilege('anon', 'public.bot_challenged_documents', 'select') then
    raise exception 'anon must not select bot_challenged_documents';
  end if;
  if to_regclass('public.latest_school_hosting') is not null
     and has_table_privilege('anon', 'public.latest_school_hosting', 'select') then
    raise exception 'anon must not select latest_school_hosting';
  end if;

  if public.pipeline_sanitize_source_url('https://github.com/bolewood/collegedata-fyi/actions/runs/123')
     is distinct from 'https://github.com/bolewood/collegedata-fyi/actions/runs/123' then
    raise exception 'run URL sanitizer rejected a valid Actions URL';
  end if;
  if public.pipeline_sanitize_source_url('https://github.com/bolewood/collegedata-fyi/pull/99')
     is distinct from 'https://github.com/bolewood/collegedata-fyi/pull/99' then
    raise exception 'PR URL sanitizer rejected a valid pull URL';
  end if;
  if public.pipeline_sanitize_source_url('https://github.com/bolewood/collegedata-fyi/actions/runs/123?token=abc') is not null then
    raise exception 'sanitizer allowed a query string';
  end if;
  if public.pipeline_sanitize_source_url('https://evil.example/steal') is not null then
    raise exception 'sanitizer allowed a non-allowlisted URL';
  end if;

  perform public.record_pipeline_heartbeat(
    'archive_process',
    'ok',
    'cron',
    jsonb_build_object(
      'dequeued', 1,
      'queue_depth', 3,
      'inserted', 0,
      'refreshed', 0,
      'walled', 0,
      'events_written', 0,
      'stack', 'SecretError: boom',
      'counts', jsonb_build_object('x', 1)
    ),
    'none'
  );
  select last_summary, last_scheduled_status, last_error_code
    into summary, status_out, error_out
  from public.pipeline_heartbeats
  where station_id = 'archive_process';
  if summary ? 'stack' or summary ? 'counts' then
    raise exception 'record_pipeline_heartbeat kept forbidden keys: %', summary;
  end if;
  if (summary ->> 'queue_depth') is distinct from '3' then
    raise exception 'record_pipeline_heartbeat dropped queue_depth';
  end if;
  if status_out is distinct from 'ok' then
    raise exception 'allowlisted finish should stay ok';
  end if;

  perform public.record_pipeline_heartbeat(
    'finder_brave',
    'ok',
    'schedule',
    jsonb_build_object('probed', 1, 'run_url', 'https://evil.example/x'),
    'none'
  );
  select last_scheduled_status, last_scheduled_error_code, source_url, last_summary
    into status_out, error_out, source_out, summary
  from public.pipeline_heartbeats
  where station_id = 'finder_brave';
  if status_out is distinct from 'error' or error_out is distinct from 'heartbeat_summary_malformed' then
    raise exception 'malformed finish must persist error + heartbeat_summary_malformed';
  end if;
  if source_out is not null then
    raise exception 'unsanitized run_url leaked into source_url';
  end if;
  if summary ? 'run_url' then
    raise exception 'unsanitized run_url leaked into summary';
  end if;

  update public.pipeline_heartbeats
  set
    last_started_at = null,
    last_finished_at = null,
    last_status = 'never',
    last_trigger = null,
    last_summary = '{}'::jsonb,
    last_scheduled_finished_at = null,
    last_scheduled_status = 'never',
    last_scheduled_summary = '{}'::jsonb,
    last_scheduled_error_code = 'none',
    last_error_code = 'none',
    source_url = null,
    updated_at = now()
  where station_id in ('archive_process', 'finder_brave');
end;
$$;
