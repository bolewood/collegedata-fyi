-- The GitHub repo bolewood/collegedata-fyi is being renamed to
-- bolewood/quadfile. Public heartbeat URLs must keep passing the allowlist
-- under both names, so run and pull-request links survive the rename.
-- Only the owner/repo part of the pattern changes; the "/" after the group
-- keeps look-alikes such as bolewood/quadfile-ops from matching.

create or replace function public.pipeline_sanitize_source_url(p_url text)
returns text
language sql
immutable
parallel safe
as $$
  select case
    when p_url is null then null
    when p_url ~ '^https://github\.com/bolewood/(collegedata-fyi|quadfile)/(actions/runs|pull)/[0-9]+/?$'
      then regexp_replace(p_url, '/$', '')
    else null
  end;
$$;

comment on function public.pipeline_sanitize_source_url(text) is
  'Allowlist for public heartbeat URLs: Actions run pages and repo pull requests only.';

revoke all on function public.pipeline_sanitize_source_url(text) from public;
revoke all on function public.pipeline_sanitize_source_url(text) from anon, authenticated;
grant execute on function public.pipeline_sanitize_source_url(text) to service_role;

do $$
declare
  repo text;
  tail text;
  u text;
begin
  foreach repo in array array['collegedata-fyi', 'quadfile'] loop
    foreach tail in array array['actions/runs/123', 'pull/99'] loop
      u := 'https://github.com/bolewood/' || repo || '/' || tail;
      if public.pipeline_sanitize_source_url(u) is distinct from u then
        raise exception 'pipeline_sanitize_source_url must accept %', u;
      end if;
      if public.pipeline_sanitize_source_url(u || '/') is distinct from u then
        raise exception 'pipeline_sanitize_source_url must accept % with a trailing slash', u;
      end if;
    end loop;
  end loop;

  foreach u in array array[
    'https://github.com/bolewood/quadfile-ops/actions/runs/1',
    'https://github.com/bolewood/quadfilex/actions/runs/1',
    'https://github.com/bolewood/quadfile/actions/runs/123?token=abc',
    'https://github.com/otherowner/quadfile/actions/runs/1',
    'https://github.com/bolewood/quadfile/issues/1'
  ] loop
    if public.pipeline_sanitize_source_url(u) is not null then
      raise exception 'pipeline_sanitize_source_url must reject %', u;
    end if;
  end loop;
end
$$;
