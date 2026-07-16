-- Enforce the atomic completion invariant introduced by
-- 20260716010500_archive_queue_attempt_telemetry.sql.
--
-- A queue transition must never commit unless the matching attempt ledger row
-- is closed in the same transaction. The original RPC lease-guarded the queue
-- update but did not verify that its ledger UPDATE affected exactly one row.

begin;

lock table public.archive_queue in access exclusive mode;

create or replace function public.complete_archive_queue_attempt(
  p_queue_id uuid,
  p_attempt_number int,
  p_claimed_at timestamptz,
  p_status text,
  p_last_outcome text,
  p_last_error text,
  p_finished_at timestamptz
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  updated_rows int;
  attempt_updated_rows int;
  attempt_state text;
begin
  if p_status not in ('ready', 'done', 'failed_permanent') then
    raise exception 'invalid archive queue completion status: %', p_status;
  end if;

  attempt_state := case p_status
    when 'ready' then 'retryable_failure'
    when 'done' then 'completed'
    else 'failed_permanent'
  end;

  update public.archive_queue q
     set status = p_status,
         last_error = p_last_error,
         claimed_at = case when p_status = 'ready' then null else q.claimed_at end,
         enqueued_at = case when p_status = 'ready' then p_finished_at else q.enqueued_at end,
         processed_at = case
           when p_status in ('done', 'failed_permanent') then p_finished_at
           else q.processed_at
         end,
         last_outcome = case
           when p_status = 'ready' or p_last_outcome is null then q.last_outcome
           else p_last_outcome
         end
   where q.id = p_queue_id
     and q.attempts = p_attempt_number
     and q.claimed_at = p_claimed_at;

  get diagnostics updated_rows = row_count;
  if updated_rows = 0 then
    return false;
  end if;

  update public.archive_queue_attempts a
     set finished_at = p_finished_at,
         duration_ms = greatest(
           0,
           floor(extract(epoch from (p_finished_at - a.claimed_at)) * 1000)::bigint
         ),
         terminal_state = attempt_state,
         last_outcome = p_last_outcome,
         last_error = p_last_error
   where a.queue_id = p_queue_id
     and a.attempt_number = p_attempt_number
     and a.claimed_at = p_claimed_at
     and a.finished_at is null;

  get diagnostics attempt_updated_rows = row_count;
  if attempt_updated_rows <> 1 then
    raise exception
      'archive attempt completion expected one open ledger row, updated %',
      attempt_updated_rows;
  end if;

  return true;
end;
$$;

comment on function public.complete_archive_queue_attempt(
  uuid, int, timestamptz, text, text, text, timestamptz
) is
  'Atomically applies a lease-guarded archive_queue terminal/retry update and '
  'closes exactly one corresponding archive_queue_attempts telemetry row. '
  'Returns false when the lease is stale and a newer worker owns the queue row.';

revoke all on function public.complete_archive_queue_attempt(
  uuid, int, timestamptz, text, text, text, timestamptz
) from public;
revoke all on function public.complete_archive_queue_attempt(
  uuid, int, timestamptz, text, text, text, timestamptz
) from anon, authenticated;
grant execute on function public.complete_archive_queue_attempt(
  uuid, int, timestamptz, text, text, text, timestamptz
) to service_role;

-- Transactional contract checks for the branches not exercised by the
-- original migration: retry release, stale-lease rejection, permanent failure,
-- and invalid status rejection. The canary and its attempts are deleted before
-- commit.
do $$
declare
  canary_id uuid := gen_random_uuid();
  first_claim public.archive_queue;
  second_claim public.archive_queue;
  retry_finished_at timestamptz := clock_timestamp();
  permanent_finished_at timestamptz;
  completed boolean;
  invalid_status_rejected boolean := false;
  queue_snapshot public.archive_queue;
  attempt_state text;
begin
  if exists (
    select 1 from public.archive_queue where status in ('ready', 'processing')
  ) then
    raise exception
      'archive attempt completion guard migration requires an idle archive queue';
  end if;

  insert into public.archive_queue (
    id,
    enqueued_run_id,
    school_id,
    school_name,
    cds_url_hint,
    last_outcome
  ) values (
    canary_id,
    gen_random_uuid(),
    '__archive_attempt_completion_guard_canary__',
    'Archive Attempt Completion Guard Canary',
    'https://example.invalid/cds',
    'unchanged_verified'
  );

  first_claim := public.claim_archive_queue_row();
  completed := public.complete_archive_queue_attempt(
    canary_id,
    first_claim.attempts,
    first_claim.claimed_at,
    'ready',
    null,
    'retry canary',
    retry_finished_at
  );
  if not completed then
    raise exception 'archive completion guard retry canary rejected its lease';
  end if;

  select * into queue_snapshot
    from public.archive_queue
   where id = canary_id;
  if queue_snapshot.status is distinct from 'ready'
     or queue_snapshot.claimed_at is not null
     or queue_snapshot.enqueued_at is distinct from retry_finished_at
     or queue_snapshot.last_outcome is distinct from 'unchanged_verified' then
    raise exception 'archive completion guard retry transition was incomplete';
  end if;

  select terminal_state into attempt_state
    from public.archive_queue_attempts
   where queue_id = canary_id and attempt_number = first_claim.attempts;
  if attempt_state is distinct from 'retryable_failure' then
    raise exception 'archive completion guard retry ledger state was not recorded';
  end if;

  second_claim := public.claim_archive_queue_row();
  completed := public.complete_archive_queue_attempt(
    canary_id,
    first_claim.attempts,
    first_claim.claimed_at,
    'done',
    'unchanged_verified',
    null,
    clock_timestamp()
  );
  if completed then
    raise exception 'archive completion guard accepted a stale lease';
  end if;

  select * into queue_snapshot
    from public.archive_queue
   where id = canary_id;
  if queue_snapshot.status is distinct from 'processing'
     or queue_snapshot.attempts is distinct from second_claim.attempts
     or queue_snapshot.claimed_at is distinct from second_claim.claimed_at then
    raise exception 'stale completion mutated the current archive queue lease';
  end if;

  permanent_finished_at := clock_timestamp();
  completed := public.complete_archive_queue_attempt(
    canary_id,
    second_claim.attempts,
    second_claim.claimed_at,
    'failed_permanent',
    'transient',
    'permanent canary',
    permanent_finished_at
  );
  if not completed then
    raise exception 'archive completion guard permanent canary rejected its lease';
  end if;

  select * into queue_snapshot
    from public.archive_queue
   where id = canary_id;
  if queue_snapshot.status is distinct from 'failed_permanent'
     or queue_snapshot.processed_at is distinct from permanent_finished_at
     or queue_snapshot.last_outcome is distinct from 'transient' then
    raise exception 'archive completion guard permanent transition was incomplete';
  end if;

  select terminal_state into attempt_state
    from public.archive_queue_attempts
   where queue_id = canary_id and attempt_number = second_claim.attempts;
  if attempt_state is distinct from 'failed_permanent' then
    raise exception 'archive completion guard permanent ledger state was not recorded';
  end if;

  begin
    perform public.complete_archive_queue_attempt(
      canary_id,
      second_claim.attempts,
      second_claim.claimed_at,
      'invalid_status',
      null,
      null,
      clock_timestamp()
    );
  exception when others then
    invalid_status_rejected := true;
  end;
  if not invalid_status_rejected then
    raise exception 'archive completion guard accepted an invalid status';
  end if;

  delete from public.archive_queue where id = canary_id;
end;
$$;

commit;
