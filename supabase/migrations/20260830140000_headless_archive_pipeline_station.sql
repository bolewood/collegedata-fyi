-- Daily Playwright archive worker (ops-headless-archive.yml).
-- Ingests WAF/JS-gated CDS files that Deno fetch cannot download (HTTP 405,
-- Cloudflare 403, cookie-gated landings). Heartbeats use station_id
-- headless_archive. Apply from main after merge; do not push from a branch.

insert into public.pipeline_stations (
  station_id, display_name, cadence_label, class, source_kind, on_board, sort_order,
  required_keys, allowed_keys
) values (
  'headless_archive',
  'Headless archive',
  'daily · WAF/JS ingest',
  'daily_sla',
  'gha',
  true,
  55,
  array['schools_attempted', 'inserted', 'unchanged', 'failed'],
  array[
    'schools_attempted', 'inserted', 'unchanged', 'failed',
    'crawled', 'discovered', 'skipped_known', 'dry_run',
    'pr_url', 'run_url'
  ]
);

insert into public.pipeline_heartbeats (station_id)
values ('headless_archive');
