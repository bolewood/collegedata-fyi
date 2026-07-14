-- Return the newest terminal archive result for each school without sending
-- the full queue history through PostgREST. archive-enqueue calls this once per
-- day before applying outcome-specific cooldowns.

create index if not exists archive_queue_terminal_latest_idx
  on public.archive_queue (school_id, processed_at desc, id desc)
  where status in ('done', 'failed_permanent')
    and last_outcome is not null
    and processed_at is not null;

create or replace function public.latest_archive_terminal_rows(
  p_since timestamptz,
  p_school_ids text[]
)
returns table (
  school_id text,
  processed_at timestamptz,
  last_outcome text
)
language sql
stable
security invoker
set search_path = public
as $$
  select distinct on (q.school_id)
    q.school_id,
    q.processed_at,
    q.last_outcome
  from public.archive_queue q
  where q.status in ('done', 'failed_permanent')
    and q.last_outcome is not null
    and q.processed_at is not null
    and q.processed_at >= p_since
    and q.school_id = any(p_school_ids)
  order by q.school_id, q.processed_at desc, q.id desc;
$$;

comment on function public.latest_archive_terminal_rows(timestamptz, text[]) is
  'Returns one latest terminal archive_queue outcome per requested school at or after p_since for archive-enqueue cooldown decisions.';

revoke all on function public.latest_archive_terminal_rows(timestamptz, text[])
  from public, anon, authenticated;
grant execute on function public.latest_archive_terminal_rows(timestamptz, text[])
  to service_role;

-- A new UTC run ID every day must not create one live job per school per day
-- when archive-process is paused. Remove redundant unclaimed rows, then make
-- the invariant database-enforced so concurrent enqueuers cannot race it.
delete from public.archive_queue q
using (
  select
    id,
    row_number() over (
      partition by school_id
      order by
        case when status = 'processing' then 0 else 1 end,
        enqueued_at,
        id
    ) as active_rank
  from public.archive_queue
  where status in ('ready', 'processing')
) ranked
where q.id = ranked.id
  and ranked.active_rank > 1
  and q.status = 'ready';

create unique index if not exists archive_queue_one_active_school_idx
  on public.archive_queue (school_id)
  where status in ('ready', 'processing');

-- All queue seeders use this function instead of a client-side upsert. The
-- untargeted ON CONFLICT handles both same-run duplication and the partial
-- one-active-school index atomically, returning a scalar count so PostgREST's
-- row cap cannot distort enqueue accounting.
create or replace function public.enqueue_archive_queue_rows(p_rows jsonb)
returns bigint
language sql
volatile
security invoker
set search_path = public
as $$
  with inserted as (
    insert into public.archive_queue (
      enqueued_run_id,
      school_id,
      school_name,
      cds_url_hint,
      status,
      source
    )
    select
      r.enqueued_run_id,
      r.school_id,
      r.school_name,
      r.cds_url_hint,
      'ready',
      coalesce(r.source, 'schools_yaml')
    from jsonb_to_recordset(p_rows) as r(
      enqueued_run_id uuid,
      school_id text,
      school_name text,
      cds_url_hint text,
      source text
    )
    on conflict do nothing
    returning id
  )
  select count(*) from inserted;
$$;

comment on function public.enqueue_archive_queue_rows(jsonb) is
  'Atomically inserts archive queue rows while ignoring same-run or already-active school conflicts.';

revoke all on function public.enqueue_archive_queue_rows(jsonb)
  from public, anon, authenticated;
grant execute on function public.enqueue_archive_queue_rows(jsonb)
  to service_role;
