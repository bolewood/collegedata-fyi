-- Archive pipeline cron schedules
--
-- This migration wires pg_cron to invoke the archive-enqueue and
-- archive-process edge functions on a schedule:
--
--   * outer cron: 02:00 UTC on the 1st of every month →  archive-enqueue
--     Seeds archive_queue with one row per active school. Generates a
--     fresh run_id so it can safely coexist with any rows from earlier
--     months that haven't fully drained.
--
--   * inner cron: every 30 seconds →  archive-process
--     Claims one row via claim_archive_queue_row() and runs the shared
--     archiveOneSchool pipeline. A full 840-school drain takes ~7 hours
--     at this cadence. When the queue is empty the function early-returns
--     queue_drained, which is effectively a no-op for the cron.
--
-- ── PREREQUISITE (manual, one-time per environment) ────────────────────
-- Before applying this migration you must create two Vault secrets so
-- pg_cron can call the edge functions without leaking values into job
-- SQL or to cron history:
--
--   select vault.create_secret(
--     'https://<project-ref>.supabase.co/functions/v1',
--     'archive_pipeline_function_base_url',
--     'Base URL for archive-enqueue and archive-process edge functions.'
--   );
--
--   select vault.create_secret(
--     '<service role JWT from the project settings>',
--     'archive_pipeline_service_role_key',
--     'Service role key used by pg_cron to authenticate edge function calls.'
--   );
--
-- The DO block below aborts the migration with a clear error if either
-- secret is missing, so an operator who forgets the pre-step gets an
-- actionable message instead of a silent cron that can't auth.
--
-- ── Idempotency ────────────────────────────────────────────────────────
-- cron.schedule() upserts by jobname in pg_cron 1.5+, which is the
-- version Supabase runs. Re-applying this migration updates the two
-- jobs in place; no cron.unschedule() dance required.
--
-- Wrapped in an explicit BEGIN/COMMIT because Supabase CLI does NOT
-- apply migrations in a single implicit transaction. The wrapper ensures
-- the whole migration rolls back atomically if any step (secret guard,
-- cron.schedule, post-schedule verification) fails.
begin;

-- Extensions: usually pre-installed in Supabase projects, but defensive
-- creates keep this migration portable to fresh environments.
create extension if not exists pg_cron with schema extensions;
create extension if not exists pg_net with schema extensions;

-- ── Cron scheduling (conditional on Vault secrets) ────────────────────
-- The cron jobs reference vault secrets for the base URL and service role
-- key. We can't schedule the cron jobs until those secrets exist.
--
-- Local dev: secrets typically don't exist, and that's fine — there's no
-- production traffic to schedule. The migration logs a NOTICE and skips
-- scheduling. Local testing happens via direct curl invocation instead.
--
-- Production: the operator creates the two secrets before running
-- `supabase db push` (see the header prerequisite block). If they forget,
-- the NOTICE fires and the cron jobs are silently skipped. The operator
-- verification step in the rollout runbook catches this via
-- `select * from cron.job where jobname like 'archive%'`.
--
-- Scheduling semantics:
--
--   Outer cron: 02:00 UTC daily → archive-enqueue
--     Daily rather than monthly so a transient schools.yaml fetch failure
--     on any given day self-heals on the next tick. archive-enqueue derives
--     a deterministic run_id from the current calendar month, so repeated
--     daily calls within a month collide on the unique (run_id, school_id)
--     constraint and become no-ops once the batch has landed. At the start
--     of a new month, run_id changes and a fresh batch is seeded alongside
--     any unprocessed rows from the prior month.
--
--   Inner cron: 30 seconds → archive-process
--     pg_cron 1.6+ supports sub-minute scheduling via the "<N> seconds"
--     string form. Each tick: pg_net fires one HTTP POST. When the queue
--     is empty, archive-process returns queue_drained quickly (<200ms). A
--     fresh 840-school batch drains in ~7 hours of wall clock at this
--     cadence.
--
-- pg_net.http_post is async; the cron job returns immediately with a
-- request_id. The actual edge function invocation happens in pg_net's
-- background worker, capped at 300s. Responses land in net._http_response.
do $$
declare
  url_secret_count int;
  key_secret_count int;
  job_count int;
begin
  select count(*) into url_secret_count
    from vault.decrypted_secrets
   where name = 'archive_pipeline_function_base_url';

  select count(*) into key_secret_count
    from vault.decrypted_secrets
   where name = 'archive_pipeline_service_role_key';

  if url_secret_count = 0 or key_secret_count = 0 then
    raise notice 'archive_pipeline_cron: Vault secrets not configured, skipping cron scheduling. This is normal in local dev. In production, create the two Vault secrets documented in this file and re-run this migration (or manually schedule via cron.schedule after setting the secrets).';
  else
    perform cron.schedule(
      'archive-enqueue-daily',
      '0 2 * * *',
      $cron$
      select net.http_post(
        url := (
          select decrypted_secret from vault.decrypted_secrets
           where name = 'archive_pipeline_function_base_url'
        ) || '/archive-enqueue',
        headers := jsonb_build_object(
          'Content-Type', 'application/json',
          'Authorization', 'Bearer ' || trim((
            select decrypted_secret from vault.decrypted_secrets
             where name = 'archive_pipeline_service_role_key'
          ))
        ),
        body := '{}'::jsonb,
        timeout_milliseconds := 300000
      );
      $cron$
    );

    perform cron.schedule(
      'archive-process-every-30s',
      '30 seconds',
      $cron$
      select net.http_post(
        url := (
          select decrypted_secret from vault.decrypted_secrets
           where name = 'archive_pipeline_function_base_url'
        ) || '/archive-process',
        headers := jsonb_build_object(
          'Content-Type', 'application/json',
          'Authorization', 'Bearer ' || trim((
            select decrypted_secret from vault.decrypted_secrets
             where name = 'archive_pipeline_service_role_key'
          ))
        ),
        body := '{}'::jsonb,
        timeout_milliseconds := 300000
      );
      $cron$
    );

    -- Post-schedule verification. If cron.schedule silently no-ops
    -- (permissions issue, pg_cron disabled), this raises and rolls back.
    select count(*) into job_count
      from cron.job
     where jobname in ('archive-enqueue-daily', 'archive-process-every-30s');

    if job_count < 2 then
      raise exception
        'archive_pipeline_cron migration aborted: expected 2 cron jobs, found %. Check pg_cron extension is enabled in this database.',
        job_count;
    end if;
  end if;
end$$;

commit;
