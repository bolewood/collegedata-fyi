-- Durable, privacy-bounded extraction history for pipeline observation.
-- Running/crashed state remains in pipeline_heartbeats. This ledger records
-- only completed runs and normalized item outcomes.

begin;

create table public.pipeline_extraction_runs (
  run_id                  uuid primary key,
  trigger                 text not null
                          check (trigger in ('schedule', 'dispatch', 'operator')),
  dry_run                 boolean not null,
  started_at              timestamptz not null,
  finished_at             timestamptz not null,
  stopped_reason          text not null
                          check (stopped_reason in ('complete', 'cap', 'deadline', 'error')),
  run_error_code          text not null
                          check (run_error_code in ('none', 'projection_error')),
  status                  text not null
                          check (status in ('no_work', 'succeeded', 'partial', 'failed')),
  run_url                 text,
  pending_remaining       integer not null check (pending_remaining >= 0),
  item_count              integer not null check (item_count >= 0),
  extracted_count         integer not null check (extracted_count >= 0),
  re_extracted_count      integer not null check (re_extracted_count >= 0),
  already_current_count   integer not null check (already_current_count >= 0),
  reconciled_count        integer not null check (reconciled_count >= 0),
  failed_count            integer not null check (failed_count >= 0),
  payload_sha256          bytea not null check (octet_length(payload_sha256) = 32),
  recorded_at             timestamptz not null default now(),

  constraint pipeline_extraction_runs_time_valid
    check (finished_at >= started_at),
  constraint pipeline_extraction_runs_counts_balance
    check (
      item_count = extracted_count + re_extracted_count
        + already_current_count + reconciled_count + failed_count
    ),
  constraint pipeline_extraction_runs_error_consistent
    check ((stopped_reason = 'error') = (run_error_code <> 'none')),
  constraint pipeline_extraction_runs_status_consistent
    check (
      (status = 'no_work' and item_count = 0 and stopped_reason <> 'error')
      or (
        status = 'failed'
        and (
          (item_count = 0 and stopped_reason = 'error')
          or (item_count > 0 and failed_count = item_count)
        )
      )
      or (
        status = 'partial'
        and item_count > 0
        and failed_count < item_count
        and (failed_count > 0 or stopped_reason = 'error')
      )
      or (
        status = 'succeeded'
        and item_count > 0
        and failed_count = 0
        and stopped_reason <> 'error'
      )
    )
);

create table public.pipeline_extraction_run_items (
  id                 bigint generated always as identity primary key,
  run_id             uuid not null
                     references public.pipeline_extraction_runs(run_id)
                     on delete restrict,
  item_ordinal       integer not null check (item_ordinal > 0),
  -- Deliberately not a foreign key: existing dedup/identity maintenance
  -- deletes superseded cds_documents rows. Immutable school/year snapshots
  -- in the closed service-role payload preserve exact, replayable history.
  document_id        uuid not null,
  school_id          text not null,
  school_name        text not null,
  canonical_year     text not null,
  occurred_at        timestamptz not null,
  outcome            text not null
                     check (
                       outcome in (
                         'extracted',
                         're_extracted',
                         'already_current',
                         'reconciled',
                         'failed'
                       )
                     ),
  source_format      text not null
                     check (
                       source_format in (
                         'pdf_fillable',
                         'pdf_flat',
                         'pdf_scanned',
                         'xlsx',
                         'docx',
                         'html',
                         'other',
                         'unknown'
                       )
                     ),
  extraction_tier    text not null
                     check (
                       extraction_tier in (
                         'tier1',
                         'tier2',
                         'tier3',
                         'tier4',
                         'tier4_ocr',
                         'tier4_fallback',
                         'tier6',
                         'reconciliation',
                         'unsupported',
                         'unknown'
                       )
                     ),
  field_count        integer check (field_count is null or field_count >= 0),
  failure_code       text not null
                     check (
                       failure_code in (
                         'none',
                         'source_missing',
                         'source_download_failed',
                         'unsupported_format',
                         'schema_failed',
                         'extraction_failed',
                         'low_coverage',
                         'artifact_write_failed',
                         'worker_failed',
                         'unknown_failure'
                       )
                     ),
  recorded_at        timestamptz not null default now(),

  constraint pipeline_extraction_run_items_failure_consistent
    check (
      (outcome = 'failed' and failure_code <> 'none')
      or (outcome <> 'failed' and failure_code = 'none')
    ),
  constraint pipeline_extraction_run_items_run_ordinal_unique
    unique (run_id, item_ordinal),
  constraint pipeline_extraction_run_items_run_document_unique
    unique (run_id, document_id)
);

create index pipeline_extraction_runs_finished_idx
  on public.pipeline_extraction_runs (finished_at desc, run_id);

create index pipeline_extraction_run_items_activity_idx
  on public.pipeline_extraction_run_items (occurred_at desc, id desc);

create function public.reject_pipeline_extraction_ledger_mutation()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog
as $$
begin
  raise exception
    'pipeline extraction ledger is append-only: %.% % rejected',
    tg_table_schema,
    tg_table_name,
    tg_op
    using errcode = '55000';
  return null;
end;
$$;

create trigger pipeline_extraction_runs_immutable
before update or delete on public.pipeline_extraction_runs
for each row
execute function public.reject_pipeline_extraction_ledger_mutation();

create trigger pipeline_extraction_run_items_immutable
before update or delete on public.pipeline_extraction_run_items
for each row
execute function public.reject_pipeline_extraction_ledger_mutation();

alter table public.pipeline_extraction_runs enable row level security;
alter table public.pipeline_extraction_run_items enable row level security;

revoke all on table public.pipeline_extraction_runs
  from public, anon, authenticated, service_role;
revoke all on table public.pipeline_extraction_run_items
  from public, anon, authenticated, service_role;
revoke all on sequence public.pipeline_extraction_run_items_id_seq
  from public, anon, authenticated, service_role;

grant select on table public.pipeline_extraction_runs to service_role;
grant select on table public.pipeline_extraction_run_items to service_role;

revoke all on function public.reject_pipeline_extraction_ledger_mutation()
  from public, anon, authenticated, service_role;

create function public.record_pipeline_extraction_run(
  p_run_id uuid,
  p_trigger text,
  p_run_url text,
  p_started_at timestamptz,
  p_finished_at timestamptz,
  p_dry_run boolean,
  p_stopped_reason text,
  p_pending_remaining integer,
  p_run_error_code text,
  p_items jsonb
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, extensions
as $$
declare
  v_now                     timestamptz := clock_timestamp();
  v_items                   jsonb;
  v_fingerprint             jsonb;
  v_payload_sha256          bytea;
  v_run_url                 text;
  v_item_count              integer;
  v_extracted_count         integer;
  v_re_extracted_count      integer;
  v_already_current_count   integer;
  v_reconciled_count        integer;
  v_failed_count            integer;
  v_status                  text;
  v_inserted_rows           integer;
  v_existing_sha            bytea;
  v_existing_item_count     integer;
  v_existing_rows           integer;
begin
  if p_run_id is null then
    raise exception 'run_id is required' using errcode = '22023';
  end if;
  if p_trigger is null
     or p_trigger not in ('schedule', 'dispatch', 'operator') then
    raise exception 'invalid extraction run trigger' using errcode = '22023';
  end if;
  if p_started_at is null
     or p_finished_at is null
     or p_finished_at < p_started_at
     or p_finished_at > v_now + interval '5 minutes' then
    raise exception 'invalid extraction run timestamps' using errcode = '22023';
  end if;
  if p_dry_run is null then
    raise exception 'dry_run is required' using errcode = '22023';
  end if;
  if p_stopped_reason is null
     or p_stopped_reason not in ('complete', 'cap', 'deadline', 'error') then
    raise exception 'invalid extraction stopped_reason' using errcode = '22023';
  end if;
  if p_pending_remaining is null or p_pending_remaining < 0 then
    raise exception 'invalid pending_remaining' using errcode = '22023';
  end if;
  if p_run_error_code is null
     or p_run_error_code not in ('none', 'projection_error') then
    raise exception 'invalid extraction run error code' using errcode = '22023';
  end if;
  if (p_stopped_reason = 'error') <> (p_run_error_code <> 'none') then
    raise exception 'stopped_reason and run_error_code disagree'
      using errcode = '22023';
  end if;
  if p_items is null or jsonb_typeof(p_items) <> 'array' then
    raise exception 'items must be a JSON array' using errcode = '22023';
  end if;
  if jsonb_array_length(p_items) > 5000 then
    raise exception 'items exceeds the 5000-row limit' using errcode = '22023';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(p_items) as e(value)
    where jsonb_typeof(e.value) <> 'object'
  ) then
    raise exception 'every item must be a JSON object' using errcode = '22023';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(p_items) as e(value)
    where not (
      e.value ?& array[
        'ordinal',
        'document_id',
        'school_id',
        'school_name',
        'canonical_year',
        'occurred_at',
        'outcome',
        'source_format',
        'extraction_tier',
        'field_count',
        'failure_code'
      ]::text[]
    )
  ) then
    raise exception 'an extraction item is missing required keys'
      using errcode = '22023';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(p_items) as e(value)
    cross join lateral jsonb_object_keys(e.value) as k(key)
    where k.key <> all (array[
      'ordinal',
      'document_id',
      'school_id',
      'school_name',
      'canonical_year',
      'occurred_at',
      'outcome',
      'source_format',
      'extraction_tier',
      'field_count',
      'failure_code'
    ]::text[])
  ) then
    raise exception 'an extraction item contains unknown keys'
      using errcode = '22023';
  end if;

  begin
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'ordinal', x.ordinal,
          'document_id', x.document_id,
          'school_id', x.school_id,
          'school_name', x.school_name,
          'canonical_year', x.canonical_year,
          'occurred_at', x.occurred_at,
          'outcome', x.outcome,
          'source_format', x.source_format,
          'extraction_tier', x.extraction_tier,
          'field_count', x.field_count,
          'failure_code', x.failure_code
        )
        order by x.ordinal
      ),
      '[]'::jsonb
    )
    into v_items
    from jsonb_to_recordset(p_items) as x(
      ordinal integer,
      document_id uuid,
      school_id text,
      school_name text,
      canonical_year text,
      occurred_at timestamptz,
      outcome text,
      source_format text,
      extraction_tier text,
      field_count integer,
      failure_code text
    );
  exception
    when data_exception then
      raise exception 'an extraction item contains malformed typed values'
        using errcode = '22023';
  end;

  if exists (
    select 1
    from jsonb_to_recordset(v_items) as x(
      ordinal integer,
      document_id uuid,
      school_id text,
      school_name text,
      canonical_year text,
      occurred_at timestamptz,
      outcome text,
      source_format text,
      extraction_tier text,
      field_count integer,
      failure_code text
    )
    where x.ordinal is null
       or x.ordinal <= 0
       or x.document_id is null
       or x.school_id is null
       or x.school_id !~ '^[a-z0-9][a-z0-9-]{0,199}$'
       or x.school_name is null
       or btrim(x.school_name) = ''
       or char_length(x.school_name) > 300
       or x.canonical_year is null
       or x.canonical_year !~ '^(19|20)[0-9]{2}-[0-9]{2}$|^unknown$'
       or x.occurred_at is null
       or x.occurred_at < p_started_at
       or x.occurred_at > p_finished_at
       or x.outcome is null
       or x.outcome not in (
         'extracted',
         're_extracted',
         'already_current',
         'reconciled',
         'failed'
       )
       or x.source_format is null
       or x.source_format not in (
         'pdf_fillable',
         'pdf_flat',
         'pdf_scanned',
         'xlsx',
         'docx',
         'html',
         'other',
         'unknown'
       )
       or x.extraction_tier is null
       or x.extraction_tier not in (
         'tier1',
         'tier2',
         'tier3',
         'tier4',
         'tier4_ocr',
         'tier4_fallback',
         'tier6',
         'reconciliation',
         'unsupported',
         'unknown'
       )
       or x.field_count < 0
       or x.failure_code is null
       or x.failure_code not in (
         'none',
         'source_missing',
         'source_download_failed',
         'unsupported_format',
         'schema_failed',
         'extraction_failed',
         'low_coverage',
         'artifact_write_failed',
         'worker_failed',
         'unknown_failure'
       )
       or (
         (x.outcome = 'failed' and x.failure_code = 'none')
         or (x.outcome <> 'failed' and x.failure_code <> 'none')
       )
  ) then
    raise exception 'an extraction item violates the typed contract'
      using errcode = '22023';
  end if;

  if exists (
    select 1
    from jsonb_to_recordset(v_items) as x(
      ordinal integer,
      document_id uuid,
      school_id text,
      school_name text,
      canonical_year text,
      occurred_at timestamptz,
      outcome text,
      source_format text,
      extraction_tier text,
      field_count integer,
      failure_code text
    )
    group by x.ordinal
    having count(*) > 1
  ) then
    raise exception 'duplicate item ordinal' using errcode = '22023';
  end if;
  if exists (
    select 1
    from jsonb_to_recordset(v_items) as x(
      ordinal integer,
      document_id uuid,
      school_id text,
      school_name text,
      canonical_year text,
      occurred_at timestamptz,
      outcome text,
      source_format text,
      extraction_tier text,
      field_count integer,
      failure_code text
    )
    group by x.document_id
    having count(*) > 1
  ) then
    raise exception 'duplicate document in extraction run' using errcode = '22023';
  end if;
  select
    count(*)::integer,
    (count(*) filter (where x.outcome = 'extracted'))::integer,
    (count(*) filter (where x.outcome = 're_extracted'))::integer,
    (count(*) filter (where x.outcome = 'already_current'))::integer,
    (count(*) filter (where x.outcome = 'reconciled'))::integer,
    (count(*) filter (where x.outcome = 'failed'))::integer
  into
    v_item_count,
    v_extracted_count,
    v_re_extracted_count,
    v_already_current_count,
    v_reconciled_count,
    v_failed_count
  from jsonb_to_recordset(v_items) as x(
    ordinal integer,
    document_id uuid,
    school_id text,
    school_name text,
    canonical_year text,
    occurred_at timestamptz,
    outcome text,
    source_format text,
    extraction_tier text,
    field_count integer,
    failure_code text
  );

  v_status := case
    when v_item_count = 0 and p_stopped_reason <> 'error' then 'no_work'
    when v_item_count = 0 and p_stopped_reason = 'error' then 'failed'
    when v_failed_count = v_item_count then 'failed'
    when v_failed_count > 0 or p_stopped_reason = 'error' then 'partial'
    else 'succeeded'
  end;
  v_run_url := public.pipeline_sanitize_source_url(p_run_url);
  v_fingerprint := jsonb_build_object(
    'run_id', p_run_id,
    'trigger', p_trigger,
    'run_url', v_run_url,
    'started_at', p_started_at,
    'finished_at', p_finished_at,
    'dry_run', p_dry_run,
    'stopped_reason', p_stopped_reason,
    'pending_remaining', p_pending_remaining,
    'run_error_code', p_run_error_code,
    'items', v_items
  );
  v_payload_sha256 := extensions.digest(
    convert_to(v_fingerprint::text, 'UTF8'),
    'sha256'
  );

  insert into public.pipeline_extraction_runs (
    run_id,
    trigger,
    dry_run,
    started_at,
    finished_at,
    stopped_reason,
    run_error_code,
    status,
    run_url,
    pending_remaining,
    item_count,
    extracted_count,
    re_extracted_count,
    already_current_count,
    reconciled_count,
    failed_count,
    payload_sha256
  ) values (
    p_run_id,
    p_trigger,
    p_dry_run,
    p_started_at,
    p_finished_at,
    p_stopped_reason,
    p_run_error_code,
    v_status,
    v_run_url,
    p_pending_remaining,
    v_item_count,
    v_extracted_count,
    v_re_extracted_count,
    v_already_current_count,
    v_reconciled_count,
    v_failed_count,
    v_payload_sha256
  )
  on conflict (run_id) do nothing;

  get diagnostics v_inserted_rows = row_count;
  if v_inserted_rows = 0 then
    select r.payload_sha256, r.item_count
    into v_existing_sha, v_existing_item_count
    from public.pipeline_extraction_runs r
    where r.run_id = p_run_id;

    if not found then
      raise exception 'extraction run conflict could not be resolved'
        using errcode = '40001';
    end if;

    select count(*)::integer
    into v_existing_rows
    from public.pipeline_extraction_run_items i
    where i.run_id = p_run_id;

    if v_existing_sha is distinct from v_payload_sha256
       or v_existing_item_count is distinct from v_item_count
       or v_existing_rows is distinct from v_item_count then
      raise exception 'run_id already exists with a different payload'
        using errcode = '23505';
    end if;
    return false;
  end if;

  insert into public.pipeline_extraction_run_items (
    run_id,
    item_ordinal,
    document_id,
    school_id,
    school_name,
    canonical_year,
    occurred_at,
    outcome,
    source_format,
    extraction_tier,
    field_count,
    failure_code
  )
  select
    p_run_id,
    x.ordinal,
    x.document_id,
    x.school_id,
    x.school_name,
    x.canonical_year,
    x.occurred_at,
    x.outcome,
    x.source_format,
    x.extraction_tier,
    x.field_count,
    x.failure_code
  from jsonb_to_recordset(v_items) as x(
    ordinal integer,
    document_id uuid,
    school_id text,
    school_name text,
    canonical_year text,
    occurred_at timestamptz,
    outcome text,
    source_format text,
    extraction_tier text,
    field_count integer,
    failure_code text
  )
  order by x.ordinal;

  get diagnostics v_inserted_rows = row_count;
  if v_inserted_rows <> v_item_count then
    raise exception 'extraction item insert count mismatch'
      using errcode = '23503';
  end if;
  return true;
end;
$$;

comment on function public.record_pipeline_extraction_run(
  uuid, text, text, timestamptz, timestamptz, boolean, text, integer, text, jsonb
) is
  'Atomically records one completed extraction run and normalized item set. '
  'Unknown JSON keys are rejected; raw actions, errors, document URLs, paths, '
  'artifact hashes, secrets, and arbitrary summaries are never stored.';

revoke all on function public.record_pipeline_extraction_run(
  uuid, text, text, timestamptz, timestamptz, boolean, text, integer, text, jsonb
) from public, anon, authenticated;
grant execute on function public.record_pipeline_extraction_run(
  uuid, text, text, timestamptz, timestamptz, boolean, text, integer, text, jsonb
) to service_role;

create function public.pipeline_recent_extraction_activity()
returns table (
  activity_at timestamptz,
  school_id text,
  school_name text,
  canonical_year text,
  source_format text,
  extraction_tier text,
  field_count integer,
  outcome text,
  trigger text,
  run_url text
)
language sql
stable
security definer
set search_path = pg_catalog
as $$
  select
    i.occurred_at as activity_at,
    i.school_id,
    i.school_name,
    i.canonical_year,
    i.source_format,
    i.extraction_tier,
    i.field_count,
    i.outcome,
    r.trigger,
    r.run_url
  from public.pipeline_extraction_run_items i
  join public.pipeline_extraction_runs r using (run_id)
  where r.dry_run = false
    and i.occurred_at >= statement_timestamp() - interval '14 days'
  order by i.occurred_at desc, i.id desc
  limit 50;
$$;

comment on function public.pipeline_recent_extraction_activity() is
  'Returns at most 50 sanitized file outcomes from completed non-dry extraction '
  'runs in the last 14 days. Exposes no document IDs, failure codes, raw text, '
  'source URLs, storage paths, hashes, secrets, or arbitrary metadata.';

revoke all on function public.pipeline_recent_extraction_activity() from public;
grant execute on function public.pipeline_recent_extraction_activity()
  to anon, authenticated, service_role;

do $verify$
declare
  test_run_id uuid := '00000000-0000-0000-0000-000000000030';
  test_document_id uuid := '00000000-0000-0000-0000-000000000031';
  test_items jsonb;
  wrote boolean := false;
begin
  if has_table_privilege('anon', 'public.pipeline_extraction_runs', 'select')
     or has_table_privilege(
       'anon',
       'public.pipeline_extraction_run_items',
       'select'
     ) then
    raise exception 'anon must not read private extraction ledger tables';
  end if;
  if has_table_privilege(
    'service_role',
    'public.pipeline_extraction_runs',
    'insert'
  ) then
    raise exception 'service_role must write extraction runs only through RPC';
  end if;
  if has_function_privilege(
    'anon',
    'public.record_pipeline_extraction_run(uuid,text,text,timestamptz,timestamptz,boolean,text,integer,text,jsonb)',
    'execute'
  ) then
    raise exception 'anon must not execute extraction ledger writer';
  end if;
  if not has_function_privilege(
    'service_role',
    'public.record_pipeline_extraction_run(uuid,text,text,timestamptz,timestamptz,boolean,text,integer,text,jsonb)',
    'execute'
  ) then
    raise exception 'service_role cannot execute extraction ledger writer';
  end if;
  if not has_function_privilege(
    'anon',
    'public.pipeline_recent_extraction_activity()',
    'execute'
  ) then
    raise exception 'anon cannot execute extraction activity reader';
  end if;
  if public.pipeline_sanitize_source_url(
    'https://github.com/bolewood/collegedata-fyi/actions/runs/123?token=secret'
  ) is not null then
    raise exception 'run URL sanitizer allowed a query string';
  end if;

  begin
    perform public.record_pipeline_extraction_run(
      test_run_id,
      'operator',
      null,
      statement_timestamp(),
      statement_timestamp(),
      false,
      'complete',
      0,
      'none',
      jsonb_build_array(jsonb_build_object(
        'ordinal', 1,
        'document_id', test_run_id,
        'school_id', 'pipeline-activity-canary',
        'school_name', 'Pipeline activity canary',
        'canonical_year', '2025-26',
        'occurred_at', statement_timestamp(),
        'outcome', 'failed',
        'source_format', 'unknown',
        'extraction_tier', 'unknown',
        'field_count', null,
        'failure_code', 'worker_failed',
        'action', 'raw worker error must not be accepted'
      ))
    );
    raise exception 'writer accepted an unknown raw action key';
  exception
    when sqlstate '22023' then null;
  end;

  begin
    perform public.record_pipeline_extraction_run(
      test_run_id,
      'operator',
      null,
      statement_timestamp(),
      statement_timestamp() - interval '1 minute',
      false,
      'complete',
      0,
      'none',
      '[]'::jsonb
    );
    raise exception 'writer accepted reversed run timestamps';
  exception
    when sqlstate '22023' then null;
  end;

  begin
    test_items := jsonb_build_array(jsonb_build_object(
      'ordinal', 1,
      'document_id', test_document_id,
      'school_id', 'pipeline-activity-canary',
      'school_name', 'Pipeline activity canary',
      'canonical_year', '2025-26',
      'occurred_at', statement_timestamp(),
      'outcome', 'extracted',
      'source_format', 'pdf_flat',
      'extraction_tier', 'tier4',
      'field_count', 123,
      'failure_code', 'none'
    ));

    wrote := public.record_pipeline_extraction_run(
      test_run_id,
      'operator',
      'https://evil.example/private',
      statement_timestamp(),
      statement_timestamp(),
      false,
      'complete',
      0,
      'none',
      test_items
    );
    if not wrote then
      raise exception 'writer did not insert first item run';
    end if;
    if (
      select run_url
      from public.pipeline_extraction_runs
      where run_id = test_run_id
    ) is not null then
      raise exception 'writer retained a non-allowlisted run URL';
    end if;
    if not exists (
      select 1
      from public.pipeline_extraction_runs
      where run_id = test_run_id
        and status = 'succeeded'
        and item_count = 1
        and extracted_count = 1
    ) then
      raise exception 'writer stored incorrect run counts or status';
    end if;
    if not exists (
      select 1
      from public.pipeline_extraction_run_items
      where run_id = test_run_id
        and document_id = test_document_id
        and school_id = 'pipeline-activity-canary'
        and school_name = 'Pipeline activity canary'
        and canonical_year = '2025-26'
        and field_count = 123
    ) then
      raise exception 'writer stored incorrect immutable item snapshot';
    end if;
    if not exists (
      select 1
      from public.pipeline_recent_extraction_activity()
      where school_id = 'pipeline-activity-canary'
        and outcome = 'extracted'
        and trigger = 'operator'
    ) then
      raise exception 'public activity reader omitted the canary item';
    end if;

    wrote := public.record_pipeline_extraction_run(
      test_run_id,
      'operator',
      'https://evil.example/private',
      statement_timestamp(),
      statement_timestamp(),
      false,
      'complete',
      0,
      'none',
      test_items
    );
    if wrote then
      raise exception 'identical replay inserted duplicate rows';
    end if;

    begin
      perform public.record_pipeline_extraction_run(
        test_run_id,
        'operator',
        'https://evil.example/private',
        statement_timestamp(),
        statement_timestamp(),
        false,
        'complete',
        1,
        'none',
        test_items
      );
      raise exception 'writer accepted a divergent run replay';
    exception
      when unique_violation then null;
    end;

    begin
      update public.pipeline_extraction_runs
      set pending_remaining = 1
      where run_id = test_run_id;
      raise exception 'append-only trigger allowed run mutation';
    exception
      when sqlstate '55000' then null;
    end;

    begin
      update public.pipeline_extraction_run_items
      set field_count = 124
      where run_id = test_run_id;
      raise exception 'append-only trigger allowed item mutation';
    exception
      when sqlstate '55000' then null;
    end;

    raise exception 'rollback ledger writer canary' using errcode = 'P0001';
  exception
    when raise_exception then
      if sqlerrm <> 'rollback ledger writer canary' then
        raise;
      end if;
  end;
  if exists (
    select 1
    from public.pipeline_extraction_runs
    where run_id = test_run_id
  ) then
    raise exception 'ledger writer canary escaped its rollback block';
  end if;
end;
$verify$;

commit;
