-- Reclaiming an expired lease must close exactly one prior attempt. Refuse to
-- overwrite archive_queue.claimed_at when the ledger invariant is broken;
-- otherwise the missing timeout would become impossible to reconstruct.

begin;

lock table public.archive_queue in access exclusive mode;

create or replace function public.claim_archive_queue_row()
returns public.archive_queue
language plpgsql
security definer
set search_path = public
as $$
declare
  candidate public.archive_queue;
  claimed public.archive_queue;
  claim_time timestamptz := clock_timestamp();
  timed_out_rows int;
begin
  select q.*
    into candidate
    from public.archive_queue q
   where q.status = 'ready'
      or (q.status = 'processing' and q.claimed_at < now() - interval '10 minutes')
   order by q.enqueued_at asc
     for update skip locked
   limit 1;

  if candidate.id is null then
    return null;
  end if;

  if candidate.status = 'processing' and candidate.claimed_at is not null then
    update public.archive_queue_attempts a
       set finished_at = claim_time,
           duration_ms = greatest(
             0,
             floor(extract(epoch from (claim_time - a.claimed_at)) * 1000)::bigint
           ),
           terminal_state = 'timed_out',
           last_outcome = 'transient',
           last_error = 'claim lease expired before terminal update'
     where a.queue_id = candidate.id
       and a.attempt_number = candidate.attempts
       and a.claimed_at = candidate.claimed_at
       and a.finished_at is null;

    get diagnostics timed_out_rows = row_count;
    if timed_out_rows <> 1 then
      raise exception
        'archive lease reclaim expected one open ledger row, updated %',
        timed_out_rows;
    end if;
  end if;

  update public.archive_queue q
     set status = 'processing',
         claimed_at = claim_time,
         attempts = q.attempts + 1
   where q.id = candidate.id
  returning q.* into claimed;

  insert into public.archive_queue_attempts (
    queue_id,
    attempt_number,
    claimed_at
  ) values (
    claimed.id,
    claimed.attempts,
    claimed.claimed_at
  );

  return claimed;
end;
$$;

comment on function public.claim_archive_queue_row() is
  'Atomic queue claim for archive-process. Returns one row with status flipped '
  'to processing, claimed_at set, and attempts incremented. Creates a durable '
  'archive_queue_attempts row for every claim and requires exactly one expired '
  'prior attempt to be closed before reclaim. Returns NULL when no row is eligible.';

revoke all on function public.claim_archive_queue_row() from public;
revoke all on function public.claim_archive_queue_row() from anon, authenticated;
grant execute on function public.claim_archive_queue_row() to service_role;

-- Prove a missing ledger row aborts reclaim without overwriting the lease, then
-- restore the invariant and prove the same row reclaims and completes normally.
do $$
declare
  canary_id uuid := gen_random_uuid();
  first_claim public.archive_queue;
  second_claim public.archive_queue;
  queue_snapshot public.archive_queue;
  timed_out_state text;
  reclaim_rejected boolean := false;
  completed boolean;
begin
  if exists (
    select 1 from public.archive_queue where status in ('ready', 'processing')
  ) then
    raise exception 'archive timeout guard migration requires an idle archive queue';
  end if;

  insert into public.archive_queue (
    id,
    enqueued_run_id,
    school_id,
    school_name,
    cds_url_hint
  ) values (
    canary_id,
    gen_random_uuid(),
    '__archive_timeout_guard_canary__',
    'Archive Timeout Guard Canary',
    'https://example.invalid/cds'
  );

  first_claim := public.claim_archive_queue_row();
  update public.archive_queue
     set claimed_at = claimed_at - interval '11 minutes'
   where id = canary_id;
  delete from public.archive_queue_attempts
   where queue_id = canary_id and attempt_number = first_claim.attempts;

  begin
    perform public.claim_archive_queue_row();
  exception when others then
    reclaim_rejected := true;
  end;
  if not reclaim_rejected then
    raise exception 'archive timeout guard accepted a missing ledger row';
  end if;

  select * into queue_snapshot
    from public.archive_queue
   where id = canary_id;
  if queue_snapshot.status is distinct from 'processing'
     or queue_snapshot.attempts is distinct from first_claim.attempts
     or queue_snapshot.claimed_at >= now() - interval '10 minutes' then
    raise exception 'rejected reclaim mutated the archive queue lease';
  end if;

  insert into public.archive_queue_attempts (
    queue_id,
    attempt_number,
    claimed_at
  ) values (
    canary_id,
    queue_snapshot.attempts,
    queue_snapshot.claimed_at
  );

  second_claim := public.claim_archive_queue_row();
  if second_claim.id is distinct from canary_id
     or second_claim.attempts <> first_claim.attempts + 1 then
    raise exception 'archive timeout guard did not reclaim a valid expired lease';
  end if;

  select terminal_state into timed_out_state
    from public.archive_queue_attempts
   where queue_id = canary_id and attempt_number = first_claim.attempts;
  if timed_out_state is distinct from 'timed_out' then
    raise exception 'archive timeout guard did not preserve the timeout';
  end if;

  completed := public.complete_archive_queue_attempt(
    canary_id,
    second_claim.attempts,
    second_claim.claimed_at,
    'done',
    'unchanged_verified',
    null,
    clock_timestamp()
  );
  if not completed then
    raise exception 'archive timeout guard canary completion rejected its lease';
  end if;

  delete from public.archive_queue where id = canary_id;
end;
$$;

commit;
