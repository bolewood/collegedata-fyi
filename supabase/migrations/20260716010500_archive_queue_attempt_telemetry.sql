-- Durable per-claim telemetry for archive-process.
--
-- archive_queue keeps only the latest claimed_at value. Before this migration,
-- an edge invocation that hit its wall-clock limit left no direct record: the
-- next claim merely incremented attempts and overwrote claimed_at. This ledger
-- records every claim and lets the database mark abandoned leases timed_out
-- when they are reclaimed, even though the dead edge invocation cannot report
-- its own failure.

begin;

-- Keep the cron consumer from racing the RPC replacement and the transactional
-- self-test at the end of this migration.
lock table public.archive_queue in access exclusive mode;

create table public.archive_queue_attempts (
  queue_id          uuid not null references public.archive_queue(id) on delete cascade,
  attempt_number    int not null check (attempt_number > 0),
  claimed_at        timestamptz not null,
  finished_at       timestamptz,
  duration_ms       bigint check (duration_ms is null or duration_ms >= 0),
  terminal_state    text check (terminal_state is null or terminal_state in (
    'completed',
    'retryable_failure',
    'failed_permanent',
    'timed_out'
  )),
  last_outcome      text,
  last_error        text,
  primary key (queue_id, attempt_number)
);

comment on table public.archive_queue_attempts is
  'One durable row per archive-process claim. Open rows are active invocations; '
  'claim_archive_queue_row marks an abandoned prior lease timed_out before '
  'creating the next attempt. This preserves timeout and duration history that '
  'archive_queue itself necessarily overwrites on reclaim.';

comment on column public.archive_queue_attempts.duration_ms is
  'Elapsed milliseconds from claim to terminal update or lease reclaim.';

create index archive_queue_attempts_timeout_idx
  on public.archive_queue_attempts (claimed_at desc)
  where terminal_state = 'timed_out';

create index archive_queue_attempts_open_idx
  on public.archive_queue_attempts (claimed_at)
  where finished_at is null;

alter table public.archive_queue_attempts enable row level security;

-- Operational error text can contain upstream URLs. Keep this service-role
-- only rather than exposing it through the public read policies used by the
-- user-facing CDS tables.
revoke all on table public.archive_queue_attempts from anon, authenticated;
grant select, insert, update, delete on table public.archive_queue_attempts to service_role;

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

  -- A processing row can only be selected after its lease expired. Close the
  -- prior attempt before overwriting archive_queue.claimed_at so the timeout is
  -- explicit and queryable even though the prior edge invocation disappeared.
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
       and a.finished_at is null;
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
  'archive_queue_attempts row for every claim and marks an expired prior lease '
  'timed_out before reclaim. Returns NULL when no row is eligible.';

revoke all on function public.claim_archive_queue_row() from public;
revoke all on function public.claim_archive_queue_row() from anon, authenticated;
grant execute on function public.claim_archive_queue_row() to service_role;

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

  return true;
end;
$$;

comment on function public.complete_archive_queue_attempt(
  uuid, int, timestamptz, text, text, text, timestamptz
) is
  'Atomically applies a lease-guarded archive_queue terminal/retry update and '
  'closes the corresponding archive_queue_attempts telemetry row. Returns false '
  'when the lease is stale and a newer worker owns the queue row.';

revoke all on function public.complete_archive_queue_attempt(
  uuid, int, timestamptz, text, text, text, timestamptz
) from public;
revoke all on function public.complete_archive_queue_attempt(
  uuid, int, timestamptz, text, text, text, timestamptz
) from anon, authenticated;
grant execute on function public.complete_archive_queue_attempt(
  uuid, int, timestamptz, text, text, text, timestamptz
) to service_role;

-- Exercise both paths that matter while the queue lock prevents cron claims:
-- an expired lease becomes timed_out on reclaim, and the replacement attempt
-- is closed atomically with its archive_queue terminal state. The canary row
-- and its cascading attempt rows are deleted before commit.
do $$
declare
  canary_id uuid := gen_random_uuid();
  first_claim public.archive_queue;
  second_claim public.archive_queue;
  completed boolean;
  first_state text;
  second_state text;
begin
  if exists (
    select 1 from public.archive_queue where status in ('ready', 'processing')
  ) then
    raise exception
      'archive attempt telemetry migration requires an idle archive queue';
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
    '__archive_attempt_telemetry_canary__',
    'Archive Attempt Telemetry Canary',
    'https://example.invalid/cds'
  );

  first_claim := public.claim_archive_queue_row();
  if first_claim.id is distinct from canary_id or first_claim.attempts <> 1 then
    raise exception 'archive telemetry canary first claim failed';
  end if;

  update public.archive_queue
     set claimed_at = claimed_at - interval '11 minutes'
   where id = canary_id;
  update public.archive_queue_attempts
     set claimed_at = claimed_at - interval '11 minutes'
   where queue_id = canary_id and attempt_number = 1;

  second_claim := public.claim_archive_queue_row();
  if second_claim.id is distinct from canary_id or second_claim.attempts <> 2 then
    raise exception 'archive telemetry canary reclaim failed';
  end if;

  select terminal_state
    into first_state
    from public.archive_queue_attempts
   where queue_id = canary_id and attempt_number = 1;
  if first_state is distinct from 'timed_out' then
    raise exception 'archive telemetry canary did not record timeout';
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
    raise exception 'archive telemetry canary completion rejected its lease';
  end if;

  select terminal_state
    into second_state
    from public.archive_queue_attempts
   where queue_id = canary_id and attempt_number = 2;
  if second_state is distinct from 'completed' then
    raise exception 'archive telemetry canary did not record completion';
  end if;

  delete from public.archive_queue where id = canary_id;
end;
$$;

commit;
