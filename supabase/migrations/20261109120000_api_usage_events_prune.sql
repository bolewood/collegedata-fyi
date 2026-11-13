-- Prune public.api_usage_events after 400 days.
--
-- api_usage_prune() already retires hash salts and api_gateway_clients_hourly
-- rows, but api_usage_events (friendly API usage events) had no retention
-- limit. It now shares the same p_client_keep_days window (default 400) and
-- reports the count as events_deleted. The hourly ingest job calls this
-- function with no arguments, so the signature stays unchanged and no new
-- overload is introduced.
--
-- The delete is served by api_usage_events_occurred_at_idx
-- (20260625120000_api_usage_events.sql), so no new index is needed.
-- The table's earliest rows date from June 2026, so the first run after this
-- migration is expected to delete 0 rows; the first real deletions begin
-- once rows pass 400 days of age (mid-2027).

create or replace function public.api_usage_prune(p_client_keep_days integer default 400)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  n_salts integer;
  n_clients integer;
  n_events integer;
begin
  delete from public.api_usage_hash_salts
  where day < (now() at time zone 'utc')::date - 2;
  get diagnostics n_salts = row_count;

  delete from public.api_gateway_clients_hourly
  where hour < now() - make_interval(days => p_client_keep_days);
  get diagnostics n_clients = row_count;

  delete from public.api_usage_events
  where occurred_at < now() - make_interval(days => p_client_keep_days);
  get diagnostics n_events = row_count;

  return jsonb_build_object(
    'salts_deleted', n_salts,
    'client_rows_deleted', n_clients,
    'events_deleted', n_events
  );
end;
$$;

revoke all on function public.api_usage_prune(integer) from public, anon, authenticated;
grant execute on function public.api_usage_prune(integer) to service_role;

comment on table public.api_usage_events is
  'Low-PII server-side usage events for the public friendly API. Used to distinguish first-party MCP/CLI calls, cooperative app integrations, and unknown script/browser traffic. Retained 400 days (pruned by api_usage_prune()).';
