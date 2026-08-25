-- Add Goshen College's official purple after a direct alumni request.
-- Audit record: data/brand-colors/batch-38-2026-08-25.jsonl

begin;

do $$
begin
  if not exists (
    select 1
    from public.institution_directory
    where ipeds_id = '150668'
      and school_id = 'goshen-college'
      and school_name = 'Goshen College'
  ) then
    raise exception 'Expected Goshen College directory identity is missing';
  end if;
end$$;

update public.institution_directory
set brand_colors = array['#49176D']::text[],
    brand_colors_source = 'https://goleafs.net/sports/2025/8/6/info-for-opponent-athletic-communications-staff-members.aspx',
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = 'medium',
    brand_colors_notes = 'Current official Goshen College athletics communications page labels Purple as Pantone 2627 and explicitly prints HEX #49176D. Black, light gray, and light purple are supporting colors and omitted; confidence is medium because the source is athletics-owned rather than the institution-wide brand portal.'
where ipeds_id = '150668'
  and school_id = 'goshen-college'
  and brand_colors is null;

do $$
begin
  if not exists (
    select 1
    from public.institution_directory
    where ipeds_id = '150668'
      and school_id = 'goshen-college'
      and brand_colors = array['#49176D']::text[]
      and brand_colors_source = 'https://goleafs.net/sports/2025/8/6/info-for-opponent-athletic-communications-staff-members.aspx'
  ) then
    raise exception 'Goshen College brand-color verification failed';
  end if;
end$$;

commit;
