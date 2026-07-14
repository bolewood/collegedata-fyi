-- Return the newest terminal archive result for each school without sending
-- the full queue history through PostgREST. archive-enqueue calls this once per
-- day before applying outcome-specific cooldowns.

create index if not exists archive_queue_terminal_latest_idx
  on public.archive_queue (school_id, processed_at desc, id desc)
  where status in ('done', 'failed_permanent')
    and last_outcome is not null
    and processed_at is not null;

create or replace function public.latest_archive_terminal_rows(
  p_since timestamptz
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
  order by q.school_id, q.processed_at desc, q.id desc;
$$;

comment on function public.latest_archive_terminal_rows(timestamptz) is
  'Returns one latest terminal archive_queue outcome per school at or after p_since for archive-enqueue cooldown decisions.';

revoke all on function public.latest_archive_terminal_rows(timestamptz)
  from public, anon, authenticated;
grant execute on function public.latest_archive_terminal_rows(timestamptz)
  to service_role;
