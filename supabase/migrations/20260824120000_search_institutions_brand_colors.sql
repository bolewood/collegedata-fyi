-- Include scouted brand_colors on search so Jump-to-school can render
-- the two-dot glyph without a second round-trip. Null means the unknown
-- (grey + hollow) glyph, not house forest/ochre.

begin;

drop function if exists public.search_institutions(text, int);

create function public.search_institutions(
  p_query text,
  p_limit int default 10
)
returns table (
  school_id                  text,
  school_name                text,
  city                       text,
  state                      text,
  coverage_status            public.coverage_status_t,
  coverage_label             text,
  latest_available_cds_year  text,
  brand_colors               text[]
)
language sql
stable
security invoker
set search_path = public
as $$
  with q as (
    select
      lower(trim(coalesce(p_query, ''))) as qstr,
      regexp_replace(
        lower(trim(coalesce(p_query, ''))),
        '[^a-z0-9]',
        '',
        'g'
      ) as qcompact,
      regexp_replace(
        lower(trim(coalesce(p_query, ''))),
        '([\\.^$|?*+(){}\[\]-])',
        '\\\1',
        'g'
      ) as qescaped
  )
  select
    c.school_id,
    c.school_name,
    c.city,
    c.state,
    c.coverage_status,
    c.coverage_label,
    c.latest_available_cds_year,
    d.brand_colors
  from public.institution_cds_coverage c
  left join public.institution_directory d on d.school_id = c.school_id
  cross join q
  where c.coverage_status <> 'out_of_scope'
    and length(q.qstr) > 0
    and length(q.qcompact) > 0
    and (
      regexp_replace(c.school_id, '[^a-z0-9]', '', 'g') like q.qcompact || '%'
      or exists (
        select 1
        from unnest(coalesce(c.aliases, '{}'::text[])) as alias
        where regexp_replace(lower(alias), '[^a-z0-9]', '', 'g')
          like q.qcompact || '%'
      )
      or (
        length(q.qescaped) > 0
        and lower(c.school_name) ~ ('\y' || q.qescaped)
      )
      or (
        length(q.qstr) > 4
        and c.search_text like '%' || q.qstr || '%'
      )
    )
  order by
    case
      when regexp_replace(c.school_id, '[^a-z0-9]', '', 'g') = q.qcompact
        then 0
      when exists (
        select 1
        from unnest(coalesce(c.aliases, '{}'::text[])) as alias
        where regexp_replace(lower(alias), '[^a-z0-9]', '', 'g') = q.qcompact
      ) then 0
      when regexp_replace(c.school_id, '[^a-z0-9]', '', 'g') like q.qcompact || '%'
        then 1
      when exists (
        select 1
        from unnest(coalesce(c.aliases, '{}'::text[])) as alias
        where regexp_replace(lower(alias), '[^a-z0-9]', '', 'g') like q.qcompact || '%'
      ) then 1
      when length(q.qescaped) > 0
        and lower(c.school_name) ~ ('\y' || q.qescaped)
        then 2
      when lower(c.school_name) like '%' || q.qstr || '%'
        then 3
      else 4
    end,
    case when c.latest_available_cds_year is not null then 0 else 1 end,
    c.undergraduate_enrollment desc nulls last,
    c.school_name
  limit greatest(p_limit, 1);
$$;

comment on function public.search_institutions(text, int) is
  'Public autocomplete over institution_cds_coverage. Rank: exact school_id/alias, id/alias prefix, name token-prefix, name substring, other search_text. CDS year then enrollment as tie-breaks. Includes scouted brand_colors for the school glyph. SECURITY INVOKER so RLS hides out_of_scope rows.';

grant execute on function public.search_institutions(text, int) to anon, authenticated;

commit;
