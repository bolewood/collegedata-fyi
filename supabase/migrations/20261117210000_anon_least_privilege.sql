-- Least privilege for the public API roles (anon, authenticated).
--
-- The public key is meant to read. Until now it also held:
--   * INSERT/UPDATE/DELETE/TRUNCATE on nearly every public table and view
--     (Supabase's default grants). Row-level security refused the writes, since
--     every policy is SELECT-only and every view is security_invoker, but one
--     table created without RLS would have been writable by anyone.
--   * EXECUTE on maintenance functions, including the SECURITY DEFINER cache
--     refreshes. Anyone could call the expensive refreshes in a loop.
--
-- Reads are unchanged: the public API (api.collegedata.fyi) is a product.
-- service_role and postgres are unchanged.

-- 1. No writes for the public roles, on what exists now.
revoke insert, update, delete, truncate, references, trigger
  on all tables in schema public
  from anon, authenticated;

revoke all on all sequences in schema public from anon, authenticated;

-- 2. Nor on tables and sequences created later by postgres (migrations).
--    SELECT keeps its default grant, so a new public table is still readable
--    once it has a SELECT policy.
alter default privileges for role postgres in schema public
  revoke insert, update, delete, truncate, references, trigger on tables
  from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke all on sequences
  from anon, authenticated;

-- 3. Maintenance functions are for service_role, cron and operators only.
--    Functions the public site calls stay as they are: search_institutions,
--    pipeline_station_facts, pipeline_recent_extraction_activity, and the pure
--    helpers the public views use.
--    rls_auto_enable() is left alone: it is an event-trigger function and
--    cannot be called through the API.
--    New maintenance functions still need their own revoke, as before: Postgres
--    grants EXECUTE on every new function to PUBLIC.
do $$
declare
  fn text;
begin
  foreach fn in array array[
    'public.refresh_ipeds_current_facts_cache()',
    'public.refresh_public_serving_caches()',
    'public.refresh_school_merit_profile_cache()',
    'public.refresh_site_stats_cache()',
    'public.refresh_ipeds_browser_source_modes()',
    'public.replace_browser_projection_for_document(uuid, jsonb, jsonb)',
    'public.publish_alert_tier_schools(integer)',
    'public.publish_alert_freshness_anchors(text[])'
  ]
  loop
    if to_regprocedure(fn) is null then
      raise exception 'anon_least_privilege: function % not found', fn;
    end if;
    execute format('revoke all on function %s from public, anon, authenticated', fn);
    execute format('grant execute on function %s to service_role', fn);
  end loop;
end
$$;

-- 4. Verify. Fails the migration (and rolls it back) if anything is off.
do $$
declare
  leaked text;
  unreadable text;
begin
  select string_agg(format('%s:%s', c.relname, p.priv), ', ')
    into leaked
    from pg_class c
    cross join (values ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE')) as p(priv)
    cross join (values ('anon'), ('authenticated')) as r(role)
   where c.relnamespace = 'public'::regnamespace
     and c.relkind in ('r', 'p', 'v', 'm', 'f')
     and has_table_privilege(r.role, c.oid, p.priv);
  if leaked is not null then
    raise exception 'anon_least_privilege: write grants remain: %', leaked;
  end if;

  select string_agg(p.proname, ', ')
    into leaked
    from pg_proc p
   where p.pronamespace = 'public'::regnamespace
     and p.proname in (
       'refresh_ipeds_current_facts_cache', 'refresh_public_serving_caches',
       'refresh_school_merit_profile_cache', 'refresh_site_stats_cache',
       'refresh_ipeds_browser_source_modes', 'replace_browser_projection_for_document',
       'publish_alert_tier_schools', 'publish_alert_freshness_anchors')
     and (has_function_privilege('anon', p.oid, 'EXECUTE')
          or has_function_privilege('authenticated', p.oid, 'EXECUTE')
          or not has_function_privilege('service_role', p.oid, 'EXECUTE'));
  if leaked is not null then
    raise exception 'anon_least_privilege: function grants are wrong for: %', leaked;
  end if;

  -- The public site's own calls must still work.
  select string_agg(p.proname, ', ')
    into unreadable
    from pg_proc p
   where p.pronamespace = 'public'::regnamespace
     and p.proname in ('search_institutions', 'pipeline_station_facts', 'pipeline_recent_extraction_activity')
     and not has_function_privilege('anon', p.oid, 'EXECUTE');
  if unreadable is not null then
    raise exception 'anon_least_privilege: public function lost its grant: %', unreadable;
  end if;
end
$$;
