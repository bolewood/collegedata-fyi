-- PRD 019: change-intelligence observation view and generated event tables.
--
-- v1 keeps observations as a view over the existing browser projection
-- substrate. Event generation remains an operator-run deterministic projector
-- in tools/change_intelligence/project_change_events.py.

create or replace view public.cds_field_observations as
with selected_documents as (
  select distinct document_id
  from public.school_browser_rows
  where sub_institutional is null
),
observed_fields as (
  select
    f.school_id,
    f.school_name,
    f.sub_institutional,
    f.ipeds_id,
    f.document_id,
    f.canonical_year,
    f.year_start,
    coalesce(f.canonical_field_id, f.canonical_metric, f.field_id) as field_key,
    f.schema_version,
    f.field_id,
    f.canonical_field_id,
    f.equivalence_kind,
    f.canonical_metric,
    f.value_num as value_numeric,
    f.value_text,
    case
      when f.value_num is not null then f.value_num::text
      when f.value_bool is not null then f.value_bool::text
      else f.value_text
    end as normalized_value,
    f.value_kind as unit,
    f.value_status,
    f.source_format,
    f.producer as source_producer,
    f.producer_version as source_producer_version,
    null::integer as source_page,
    concat(f.schema_version, ':', f.field_id) as source_locator,
    f.archive_url,
    f.updated_at as observed_at,
    f.data_quality_flag as quality_flag,
    d.source_provenance,
    d.source_url,
    d.source_sha256,
    d.source_http_last_modified,
    d.source_creation_date,
    d.source_modification_date,
    d.source_producer as embedded_source_producer,
    def.section,
    def.subsection
  from public.cds_fields f
  join selected_documents sd
    on sd.document_id = f.document_id
  join public.cds_documents d
    on d.id = f.document_id
  left join public.cds_field_definitions def
    on def.schema_version = f.schema_version
   and def.field_id = f.field_id
)
select *
from observed_fields;

comment on view public.cds_field_observations is
  'PRD 019 source view: one normalized observed field per selected primary document and canonical field key. Derived from cds_fields plus school_browser_rows selected-primary logic.';

grant select on public.cds_field_observations to anon, authenticated;

create table if not exists public.cds_field_change_events (
  id                         text primary key,
  school_id                  text not null,
  school_name                text,
  ipeds_id                   text,
  field_key                  text not null,
  field_label                text,
  field_family               text not null,
  from_document_id           uuid references public.cds_documents(id) on delete cascade,
  to_document_id             uuid references public.cds_documents(id) on delete cascade,
  from_year                  text not null,
  to_year                    text not null,
  from_year_start            integer not null,
  to_year_start              integer not null,
  event_type                 text not null,
  severity                   text not null,
  from_value                 text,
  to_value                   text,
  from_value_numeric         numeric,
  to_value_numeric           numeric,
  absolute_delta             numeric,
  relative_delta             numeric,
  threshold_rule             text not null,
  summary                    text not null,
  from_producer              text,
  to_producer                text,
  from_producer_version      text,
  to_producer_version        text,
  from_source_provenance     text,
  to_source_provenance       text,
  from_archive_url           text,
  to_archive_url             text,
  from_source_url            text,
  to_source_url              text,
  evidence_json              jsonb not null,
  verification_status        text not null default 'not_required',
  public_visible             boolean not null default false,
  created_at                 timestamptz not null default now(),
  updated_at                 timestamptz not null default now(),

  constraint cds_field_change_events_event_type_valid
    check (event_type in (
      'material_delta',
      'newly_missing',
      'newly_reported',
      'reappeared',
      'format_changed',
      'producer_changed',
      'quality_regression',
      'quality_recovered',
      'card_quality_changed'
    )),
  constraint cds_field_change_events_severity_valid
    check (severity in ('watch', 'notable', 'major')),
  constraint cds_field_change_events_verification_status_valid
    check (verification_status in (
      'not_required',
      'candidate',
      'confirmed',
      'extractor_noise',
      'ambiguous',
      'not_reportable'
    ))
);

create index if not exists idx_cds_field_change_events_school_year
  on public.cds_field_change_events (school_id, to_year_start desc, severity);

create index if not exists idx_cds_field_change_events_type_severity
  on public.cds_field_change_events (event_type, severity, to_year_start desc);

create index if not exists idx_cds_field_change_events_field
  on public.cds_field_change_events (field_key, to_year_start desc);

comment on table public.cds_field_change_events is
  'PRD 019 generated year-over-year CDS change events. Written by tools/change_intelligence/project_change_events.py; not public by default.';

alter table public.cds_field_change_events enable row level security;
grant all on public.cds_field_change_events to service_role;

create table if not exists public.cds_field_change_event_reviews (
  event_id             text primary key references public.cds_field_change_events(id) on delete cascade,
  reviewer             text not null,
  reviewed_at          timestamptz not null default now(),
  verdict              text not null,
  notes                text,
  source_pages_checked jsonb not null default '[]'::jsonb,

  constraint cds_field_change_event_reviews_verdict_valid
    check (verdict in ('confirmed', 'extractor_noise', 'ambiguous', 'not_reportable'))
);

comment on table public.cds_field_change_event_reviews is
  'Human verification gate for PRD 019 major and report-bound newly_missing events.';

alter table public.cds_field_change_event_reviews enable row level security;
grant all on public.cds_field_change_event_reviews to service_role;
