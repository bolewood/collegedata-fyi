-- PRD 015 M3 — pg_cron schedule for refresh-coverage.
--
-- Reuses the same vault secrets as archive_pipeline_cron
-- (archive_pipeline_function_base_url + archive_pipeline_service_role_key)
-- so no additional operator setup is required. The cron-driven refresh
-- removes one item from the manual operator runbook — coverage stays
-- fresh without anyone remembering to re-run after each archive drain.
--
-- 15-minute cadence rationale: archive-process drains one row per 30s,
-- a typical directory-enqueue batch is 10-100 schools (5-50 minutes
-- wall clock), and the rebuild itself is sub-second on ~6K rows. 15
-- minutes gives an operator a meaningful refresh signal shortly after
-- a batch finishes without dominating DB load. Adjustable via UPDATE
-- on cron.job once we have real data.
--
-- Idempotency: cron.schedule() upserts by jobname in pg_cron 1.5+.
-- Re-applying this migration updates the job in place.
begin;

create extension if not exists pg_cron with schema extensions;
create extension if not exists pg_net  with schema extensions;

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
    raise notice 'refresh_coverage_cron: Vault secrets not configured, skipping cron scheduling. This is normal in local dev. In production, the archive_pipeline_cron migration documents how to create them; this migration reuses the same secrets.';
  else
    perform cron.schedule(
      'refresh-coverage-every-15min',
      '*/15 * * * *',
      $cron$
      select net.http_post(
        url := (
          select decrypted_secret from vault.decrypted_secrets
           where name = 'archive_pipeline_function_base_url'
        ) || '/refresh-coverage',
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

    select count(*) into job_count
      from cron.job
     where jobname = 'refresh-coverage-every-15min';

    if job_count <> 1 then
      raise exception
        'refresh_coverage_cron migration aborted: expected 1 cron job, found %. Check pg_cron extension is enabled.',
        job_count;
    end if;
  end if;
end$$;

commit;
