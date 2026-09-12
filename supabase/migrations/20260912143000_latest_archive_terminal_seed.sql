-- Bind finder seed demotion to the exact URL and terminal row that failed.
-- The finder audit must not delete a newer schools.yaml seed because an older
-- archive attempt for the same school ended in no_pdfs_found.

begin;

drop function public.latest_archive_terminal_rows(timestamptz, text[]);

create function public.latest_archive_terminal_rows(
  p_since timestamptz,
  p_school_ids text[]
)
returns table (
  school_id text,
  processed_at timestamptz,
  last_outcome text,
  cds_url_hint text,
  status text,
  active_work boolean
)
language sql
stable
security invoker
set search_path = public
as $$
  select distinct on (q.school_id)
    q.school_id,
    q.processed_at,
    q.last_outcome,
    q.cds_url_hint,
    q.status,
    exists (
      select 1
      from public.archive_queue active
      where active.school_id = q.school_id
        and active.status in ('ready', 'processing')
    ) as active_work
  from public.archive_queue q
  where q.status in ('done', 'failed_permanent')
    and q.last_outcome is not null
    and q.processed_at is not null
    and q.processed_at >= p_since
    and q.school_id = any(p_school_ids)
  order by q.school_id, q.processed_at desc, q.id desc;
$$;

comment on function public.latest_archive_terminal_rows(timestamptz, text[]) is
  'Returns each requested school latest terminal archive outcome, attempted seed URL, and status at or after p_since.';

revoke all on function public.latest_archive_terminal_rows(timestamptz, text[])
  from public, anon, authenticated;
grant execute on function public.latest_archive_terminal_rows(timestamptz, text[])
  to service_role;

commit;
