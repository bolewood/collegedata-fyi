-- PRD 021 — IPEDS federal baseline coverage layer.
--
-- Adds official NCES/IPEDS release metadata, raw row preservation, curated
-- long-form facts, and a public serving view that keeps provenance visible.
-- Loaders live in tools/ipeds/. This migration is schema-only; production
-- applies still happen from main per CLAUDE.md.

begin;

create table public.ipeds_releases (
  id                 uuid primary key default gen_random_uuid(),
  collection_year    text not null,
  data_year          integer not null,
  release_type       text not null,
  release_date       date,
  source_page_url    text not null,
  source_page_sha256 text,
  metadata_url       text not null,
  metadata_sha256    text not null,
  access_url         text,
  access_sha256      text,
  downloaded_at      timestamptz not null default now(),
  notes              jsonb not null default '{}'::jsonb,
  created_at         timestamptz not null default now(),

  constraint ipeds_releases_release_type_valid
    check (release_type in ('preliminary', 'provisional', 'final')),
  constraint ipeds_releases_unique_source
    unique (collection_year, release_type, metadata_sha256)
);

comment on table public.ipeds_releases is
  'One row per official NCES/IPEDS release load. Preserves source URLs, checksums, release type, and collection/data-year metadata for PRD 021 provenance.';

create table public.ipeds_tables (
  release_id       uuid not null references public.ipeds_releases(id) on delete cascade,
  table_name       text not null,
  survey_component text,
  year_coverage    text,
  table_number     integer,
  table_title      text,
  description      text,
  table_release    text,
  table_release_date text,
  data_url         text,
  dictionary_url   text,
  row_count        integer,
  source_sha256    text,
  loaded_at        timestamptz,
  created_at       timestamptz not null default now(),

  primary key (release_id, table_name)
);

comment on table public.ipeds_tables is
  'IPEDS table metadata from the official Tablesdoc workbook plus loader-observed row counts and table-file checksums.';

create table public.ipeds_columns (
  release_id       uuid not null references public.ipeds_releases(id) on delete cascade,
  table_name       text not null,
  var_name         text not null,
  survey_component text,
  table_number     integer,
  table_title      text,
  var_number       integer,
  var_order        integer,
  imputation_var   text,
  var_title        text,
  data_type        text,
  field_width      integer,
  format           text,
  multi_record     boolean,
  has_rv           text,
  file_number      integer,
  section_number   integer,
  long_description text,
  var_source       text,
  file_title       text,
  section_title    text,
  created_at       timestamptz not null default now(),

  primary key (release_id, table_name, var_name),
  foreign key (release_id, table_name)
    references public.ipeds_tables (release_id, table_name)
    on delete cascade
);

comment on table public.ipeds_columns is
  'Variable metadata from the official IPEDS table documentation workbook. imputation_var points at the matching X* reporting-status column when NCES provides one.';

create table public.ipeds_value_labels (
  release_id    uuid not null references public.ipeds_releases(id) on delete cascade,
  table_name    text not null,
  var_name      text not null,
  code_value    text not null,
  value_label   text,
  frequency     integer,
  percent       numeric,
  value_order   integer,
  var_title     text,
  created_at    timestamptz not null default now(),

  primary key (release_id, table_name, var_name, code_value),
  foreign key (release_id, table_name, var_name)
    references public.ipeds_columns (release_id, table_name, var_name)
    on delete cascade
);

comment on table public.ipeds_value_labels is
  'Categorical code labels from the official IPEDS metadata workbook, including reporting-status and imputation-code labels.';

create table public.ipeds_raw_rows (
  release_id uuid not null references public.ipeds_releases(id) on delete cascade,
  table_name text not null,
  unitid     integer not null,
  row_data   jsonb not null,
  loaded_at  timestamptz not null default now(),

  primary key (release_id, table_name, unitid),
  foreign key (release_id, table_name)
    references public.ipeds_tables (release_id, table_name)
    on delete cascade
);

comment on table public.ipeds_raw_rows is
  'Forensic landing table for official IPEDS rows. Public products should query ipeds_facts or serving views, not this JSONB table.';

create index ipeds_raw_rows_table_idx
  on public.ipeds_raw_rows (table_name, unitid);

create table public.ipeds_facts (
  release_id           uuid not null references public.ipeds_releases(id) on delete cascade,
  unitid               integer not null,
  ipeds_id             text generated always as (lpad(unitid::text, 6, '0')) stored,
  school_id            text,
  collection_year      text not null,
  data_year            integer not null,
  field_key            text not null,
  field_label          text not null,
  value_numeric        numeric,
  value_text           text,
  value_label          text,
  unit                 text,
  cohort               text,
  population           text,
  source_table         text not null,
  source_variable      text not null,
  source_title         text,
  release_type         text not null,
  imputation_flag      text,
  imputation_label     text,
  quality_flag         text not null default 'reported',
  definition_alignment text not null,
  definition_note      text,
  display_group        text not null,
  public_visible       boolean not null default true,
  created_at           timestamptz not null default now(),

  primary key (release_id, unitid, field_key, source_table, source_variable),

  constraint ipeds_facts_value_present
    check (value_numeric is not null or value_text is not null or value_label is not null),
  constraint ipeds_facts_release_type_valid
    check (release_type in ('preliminary', 'provisional', 'final')),
  constraint ipeds_facts_quality_flag_valid
    check (quality_flag in (
      'reported',
      'imputed',
      'not_applicable',
      'suppressed',
      'missing',
      'unusable'
    )),
  constraint ipeds_facts_definition_alignment_valid
    check (definition_alignment in (
      'direct',
      'near',
      'context_only',
      'not_cds_equivalent'
    ))
);

comment on table public.ipeds_facts is
  'Curated long-form IPEDS facts used by public products. Carries source table/variable, release type, imputation status, definition alignment, and public visibility per fact.';

create index ipeds_facts_school_field_idx
  on public.ipeds_facts (school_id, field_key, data_year desc);

create index ipeds_facts_ipeds_field_idx
  on public.ipeds_facts (ipeds_id, field_key, data_year desc);

create index ipeds_facts_field_numeric_idx
  on public.ipeds_facts (field_key, value_numeric)
  where public_visible = true and value_numeric is not null;

create index ipeds_facts_group_idx
  on public.ipeds_facts (display_group, field_key)
  where public_visible = true;

alter table public.ipeds_releases enable row level security;
alter table public.ipeds_tables enable row level security;
alter table public.ipeds_columns enable row level security;
alter table public.ipeds_value_labels enable row level security;
alter table public.ipeds_raw_rows enable row level security;
alter table public.ipeds_facts enable row level security;

create policy ipeds_releases_public_read
  on public.ipeds_releases
  for select to anon, authenticated using (true);

create policy ipeds_tables_public_read
  on public.ipeds_tables
  for select to anon, authenticated using (true);

create policy ipeds_columns_public_read
  on public.ipeds_columns
  for select to anon, authenticated using (true);

create policy ipeds_value_labels_public_read
  on public.ipeds_value_labels
  for select to anon, authenticated using (true);

create policy ipeds_raw_rows_public_read
  on public.ipeds_raw_rows
  for select to anon, authenticated using (false);

create policy ipeds_facts_public_read
  on public.ipeds_facts
  for select to anon, authenticated using (public_visible);

grant select on public.ipeds_releases to anon, authenticated;
grant select on public.ipeds_tables to anon, authenticated;
grant select on public.ipeds_columns to anon, authenticated;
grant select on public.ipeds_value_labels to anon, authenticated;
grant select on public.ipeds_facts to anon, authenticated;

create view public.ipeds_current_facts
with (security_invoker = true) as
with ranked as (
  select
    f.*,
    row_number() over (
      partition by f.unitid, f.field_key
      order by
        f.data_year desc,
        case f.release_type
          when 'final' then 3
          when 'provisional' then 2
          when 'preliminary' then 1
          else 0
        end desc,
        f.created_at desc
    ) as rn
  from public.ipeds_facts f
  where f.public_visible = true
)
select *
from ranked
where rn = 1;

comment on view public.ipeds_current_facts is
  'Latest public IPEDS fact per UNITID + field_key. Prefers newer data_year, then final over provisional over preliminary within the same data year.';

grant select on public.ipeds_current_facts to anon, authenticated;

create view public.school_facts_unified
with (security_invoker = true) as
select
  d.ipeds_id,
  d.school_id,
  d.school_name,
  d.city,
  d.state,
  d.in_scope,
  f.collection_year,
  f.data_year,
  f.field_key,
  f.field_label,
  coalesce(
    f.value_label,
    f.value_text,
    case
      when f.unit = 'percent' and f.value_numeric is not null
        then trim(to_char(f.value_numeric, 'FM999999990.099')) || '%'
      when f.value_numeric is not null
        then trim(to_char(f.value_numeric, 'FM999999999999990.999999'))
      else null
    end
  ) as display_value,
  f.value_numeric,
  f.value_text,
  f.value_label,
  f.unit,
  f.cohort,
  f.population,
  'ipeds'::text as source_layer,
  f.source_table,
  f.source_variable,
  f.source_title,
  f.release_type,
  f.imputation_flag,
  f.imputation_label,
  f.quality_flag,
  f.definition_alignment,
  f.definition_note,
  f.display_group,
  f.created_at
from public.ipeds_current_facts f
join public.institution_directory d
  on d.ipeds_id = f.ipeds_id
where d.in_scope = true;

comment on view public.school_facts_unified is
  'Public PRD 021 serving view. Exposes source-labeled federal baseline facts for in-scope institutions without hiding provenance or definition alignment.';

grant select on public.school_facts_unified to anon, authenticated;

alter table public.school_browser_rows
  add column if not exists federal_baseline_available boolean not null default false,
  add column if not exists federal_source_mode text not null default 'cds_only';

alter table public.school_browser_rows
  drop constraint if exists school_browser_rows_federal_source_mode_valid,
  add constraint school_browser_rows_federal_source_mode_valid
    check (federal_source_mode in (
      'cds_only',
      'cds_plus_ipeds_baseline',
      'ipeds_baseline_only'
    ));

comment on column public.school_browser_rows.federal_baseline_available is
  'True when the row has a UNITID that can join to source-labeled IPEDS baseline facts. Browser defaults remain CDS-first until PRD 021 QA gates pass.';

comment on column public.school_browser_rows.federal_source_mode is
  'Source mode for browse/export UI. Existing CDS rows default to cds_only; future projections may mark CDS+IPEDS or IPEDS-only rows.';

create or replace function public.refresh_ipeds_browser_source_modes()
returns integer
language plpgsql
security invoker
set search_path = public
as $$
declare
  updated_count integer;
begin
  update public.school_browser_rows as sbr
  set
    federal_baseline_available = exists (
      select 1
      from public.ipeds_current_facts f
      where f.ipeds_id = sbr.ipeds_id
      limit 1
    ),
    federal_source_mode = case
      when exists (
        select 1
        from public.ipeds_current_facts f
        where f.ipeds_id = sbr.ipeds_id
        limit 1
      )
        then 'cds_plus_ipeds_baseline'
      else 'cds_only'
    end;

  get diagnostics updated_count = row_count;
  return updated_count;
end;
$$;

comment on function public.refresh_ipeds_browser_source_modes() is
  'Marks existing CDS browser rows that have a matching IPEDS baseline after an IPEDS fact load. Service-role loader calls this after upserting facts.';

revoke all on function public.refresh_ipeds_browser_source_modes() from public;
grant execute on function public.refresh_ipeds_browser_source_modes() to service_role;

commit;
