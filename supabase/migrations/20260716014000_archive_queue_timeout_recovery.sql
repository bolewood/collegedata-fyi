-- A corrupt or missing attempt ledger row must not turn the oldest expired
-- archive lease into a poison row that blocks every later queue item. Preserve
-- the timeout by reconstructing a clearly labeled ledger entry, then reclaim.

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
    if timed_out_rows = 0 then
      insert into public.archive_queue_attempts (
        queue_id,
        attempt_number,
        claimed_at,
        finished_at,
        duration_ms,
        terminal_state,
        last_outcome,
        last_error
      ) values (
        candidate.id,
        candidate.attempts,
        candidate.claimed_at,
        claim_time,
        greatest(
          0,
          floor(extract(epoch from (claim_time - candidate.claimed_at)) * 1000)::bigint
        ),
        'timed_out',
        'transient',
        'reconstructed timeout: expired claim had no matching open ledger row'
      )
      on conflict (queue_id, attempt_number) do update
        set claimed_at = excluded.claimed_at,
            finished_at = excluded.finished_at,
            duration_ms = excluded.duration_ms,
            terminal_state = excluded.terminal_state,
            last_outcome = excluded.last_outcome,
            last_error = excluded.last_error;
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
  'Atomic queue claim for archive-process. Creates one attempt row per claim, '
  'closes expired attempts as timed_out, and reconstructs a labeled timeout '
  'entry when ledger corruption would otherwise poison the queue. Returns NULL '
  'when no row is eligible.';

revoke all on function public.claim_archive_queue_row() from public;
revoke all on function public.claim_archive_queue_row() from anon, authenticated;
grant execute on function public.claim_archive_queue_row() to service_role;

-- Prove a deliberately missing ledger row is reconstructed and does not stop
-- the queue from reclaiming and completing the expired item.
do $$
declare
  canary_id uuid := gen_random_uuid();
  first_claim public.archive_queue;
  second_claim public.archive_queue;
  timeout_state text;
  timeout_error text;
  completed boolean;
begin
  if exists (
    select 1 from public.archive_queue where status in ('ready', 'processing')
  ) then
    raise exception 'archive timeout recovery migration requires an idle archive queue';
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
    '__archive_timeout_recovery_canary__',
    'Archive Timeout Recovery Canary',
    'https://example.invalid/cds'
  );

  first_claim := public.claim_archive_queue_row();
  update public.archive_queue
     set claimed_at = claimed_at - interval '11 minutes'
   where id = canary_id;
  delete from public.archive_queue_attempts
   where queue_id = canary_id and attempt_number = first_claim.attempts;

  second_claim := public.claim_archive_queue_row();
  if second_claim.id is distinct from canary_id
     or second_claim.attempts <> first_claim.attempts + 1 then
    raise exception 'archive timeout recovery did not reclaim the corrupt lease';
  end if;

  select terminal_state, last_error
    into timeout_state, timeout_error
    from public.archive_queue_attempts
   where queue_id = canary_id and attempt_number = first_claim.attempts;
  if timeout_state is distinct from 'timed_out'
     or timeout_error not like 'reconstructed timeout:%' then
    raise exception 'archive timeout recovery did not label the repaired ledger row';
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
    raise exception 'archive timeout recovery canary completion rejected its lease';
  end if;

  delete from public.archive_queue where id = canary_id;
end;
$$;

commit;
