-- Relax refresh-coverage cron while the project is under Supabase Disk IO
-- Budget pressure.
--
-- The original PRD 015 cron ran every 15 minutes. That was useful while
-- launching the coverage surface, but it repeatedly runs a TRUNCATE+INSERT
-- rebuild of institution_cds_coverage. Hourly is enough for the public UI and
-- lowers unattended refresh pressure by 75%.
--
-- Unschedules the old 15-minute job and replaces it with a clearly named
-- hourly job. The function still supports operator-triggered refreshes after
-- a manual drain.
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
    raise notice 'relax_refresh_coverage_cron: Vault secrets not configured, skipping cron update. This is normal in local dev.';
  else
    if exists (select 1 from cron.job where jobname = 'refresh-coverage-every-15min') then
      perform cron.unschedule('refresh-coverage-every-15min');
    end if;

    perform cron.schedule(
      'refresh-coverage-hourly',
      '17 * * * *',
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
        body := '{"include_histogram": false}'::jsonb,
        timeout_milliseconds := 300000
      );
      $cron$
    );

    select count(*) into job_count
      from cron.job
     where jobname = 'refresh-coverage-hourly'
       and schedule = '17 * * * *';

    if job_count <> 1 then
      raise exception
        'relax_refresh_coverage_cron migration aborted: expected 1 hourly refresh job, found %. Check pg_cron extension is enabled.',
        job_count;
    end if;
  end if;
end$$;

commit;
