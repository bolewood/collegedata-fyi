-- Source brand hexes for school-page two-plate inks.
-- Store what the school publishes, not the derived A/B plates.
-- The Scorecard directory upsert does not send these columns, so
-- scouted values survive a directory refresh.

alter table public.institution_directory
  add column if not exists brand_colors text[],
  add column if not exists brand_colors_source text,
  add column if not exists brand_colors_checked_at date,
  add column if not exists brand_colors_confidence text,
  add column if not exists brand_colors_notes text;

alter table public.institution_directory
  drop constraint if exists institution_directory_brand_colors_len,
  drop constraint if exists institution_directory_brand_colors_confidence;

alter table public.institution_directory
  add constraint institution_directory_brand_colors_len
    check (
      brand_colors is null
      or (
        cardinality(brand_colors) between 1 and 3
        and brand_colors_source is not null
      )
    ),
  add constraint institution_directory_brand_colors_confidence
    check (
      brand_colors_confidence is null
      or brand_colors_confidence in ('high', 'medium', 'low')
    );

comment on column public.institution_directory.brand_colors is
  '1–3 official brand hexes, primary first. Null means house inks. Never store derived plates.';
comment on column public.institution_directory.brand_colors_source is
  'URL of the brand guide or page the hexes were read from.';
comment on column public.institution_directory.brand_colors_checked_at is
  'Date the source was last read.';
comment on column public.institution_directory.brand_colors_confidence is
  'high = official hexes; medium = official names plus on-domain hex; low = secondary index.';
comment on column public.institution_directory.brand_colors_notes is
  'Scout notes: athletics vs academic conflict, system-shared brand, search that found nothing.';
