-- Initial schema for collegedata.fyi
--
-- Creates the three core tables described in docs/v1-plan.md and PRD 001:
--   cds_documents  — one row per school / sub-institutional variant / CDS year
--   cds_artifacts  — derived files associated with each document (extracts, archives)
--   cleaners       — registry of community cleanup tools
--
-- Also:
--   - Enables row-level security and exposes public read policies
--     (writes use the service_role key, which bypasses RLS)
--   - Creates the cds_manifest view for the common "latest per school" query
--   - Creates the `sources` Storage bucket for archived source files
--   - Adds an updated_at trigger on cds_documents
--
-- Inline table and column comments are deliberate: PostgREST surfaces them
-- in the generated OpenAPI output and the Supabase dashboard uses them as
-- tooltips, so they serve as both documentation and live schema reference.

-- ─── Extensions ─────────────────────────────────────────────────────────────
-- gen_random_uuid() lives in pgcrypto, which Supabase enables by default.
-- Asserted here for portability if this migration is ever replayed on a
-- bare Postgres instance.
create extension if not exists pgcrypto;

-- ─── cds_documents ──────────────────────────────────────────────────────────
create table public.cds_documents (
  id                    uuid primary key default gen_random_uuid(),

  -- Identity
  school_id             text not null,
  school_name           text not null,
  sub_institutional     text,
  cds_year              text not null,

  -- Source provenance
  source_url            text,
  source_format         text,
  source_sha256         text,
  source_page_count     int,

  -- Lifecycle
  participation_status  text not null default 'not_yet_found',
  discovered_at         timestamptz,
  last_verified_at      timestamptz,
  removed_at            timestamptz,
  extraction_status     text not null default 'discovered',

  -- Bookkeeping
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),

  constraint cds_documents_unique_school_year
    unique (school_id, sub_institutional, cds_year),

  constraint cds_documents_source_format_valid
    check (source_format is null or source_format in (
      'pdf_fillable',
      'pdf_flat',
      'pdf_scanned',
      'xlsx',
      'docx',
      'other'
    )),

  constraint cds_documents_participation_status_valid
    check (participation_status in (
      'published',
      'verified_absent',
      'verified_partial',
      'not_yet_found',
      'withdrawn'
    )),

  constraint cds_documents_extraction_status_valid
    check (extraction_status in (
      'discovered',
      'extraction_pending',
      'extracted',
      'failed',
      'not_applicable'
    ))
);

comment on table public.cds_documents is
  'One row per (school, sub-institutional variant, CDS year). Tracks discovery, source provenance, participation status, and extraction lifecycle. Source files are archived to Storage on first discovery; the archived copy survives even if the live source is later removed.';

comment on column public.cds_documents.school_id is
  'Stable slug identifying the school, e.g. "yale", "harvey-mudd". Not guaranteed to match any external ID scheme. Cross-reference with IPEDS via a lookup table if needed.';

comment on column public.cds_documents.sub_institutional is
  'Distinguishes multiple CDS variants published by the same school in the same year (Columbia publishes separate files for the traditional college and the School of General Studies). Null for the common case of one CDS per school per year.';

comment on column public.cds_documents.cds_year is
  'CDS year as published on the source document, e.g. "2024-25".';

comment on column public.cds_documents.source_format is
  'Source file format detected on discovery. pdf_fillable = unflattened PDF with AcroForm fields (Tier 2). pdf_flat = flattened PDF requiring layout extraction (Tier 4). pdf_scanned = image-only PDF requiring OCR. xlsx = filled Excel template. docx = filled Word template.';

comment on column public.cds_documents.participation_status is
  'published = we have a live document; verified_absent = school is publicly known to refuse CDS publication; verified_partial = school publishes but intentionally omits sections; not_yet_found = we have not yet located a URL; withdrawn = school previously published but has since removed.';

comment on column public.cds_documents.last_verified_at is
  'Most recent time a re-check job confirmed source_url still returns 200. Null if never verified after discovery.';

comment on column public.cds_documents.removed_at is
  'First time a re-check job observed source_url return 404/5xx or a different document. Null while the source is still live.';

comment on column public.cds_documents.extraction_status is
  'discovered = source archived, extraction not yet attempted; extraction_pending = queued for the extraction worker; extracted = at least one canonical artifact exists; failed = extractor ran and gave up; not_applicable = source is verified_absent or similar.';

-- Indexes on the columns consumers and workers filter by most often.
create index cds_documents_school_year_idx
  on public.cds_documents (school_id, cds_year desc);

-- Partial index: only the rows the worker actively polls.
create index cds_documents_extraction_pending_idx
  on public.cds_documents (discovered_at)
  where extraction_status = 'extraction_pending';

create index cds_documents_participation_status_idx
  on public.cds_documents (participation_status);

-- ─── cds_artifacts ──────────────────────────────────────────────────────────
create table public.cds_artifacts (
  id                uuid primary key default gen_random_uuid(),
  document_id       uuid not null references public.cds_documents(id) on delete cascade,
  kind              text not null,
  producer          text not null,
  producer_version  text not null,
  schema_version    text,
  storage_path      text not null,
  sha256            text,
  created_at        timestamptz not null default now(),
  notes             jsonb not null default '{}'::jsonb,

  constraint cds_artifacts_kind_valid
    check (kind in (
      'source',
      'canonical',
      'raw_docling',
      'raw_reducto',
      'cleaned',
      'schema_v1_normalized'
    ))
);

comment on table public.cds_artifacts is
  'One row per derived file associated with a cds_documents row. Multiple producers can emit different kinds of artifacts for the same document; consumers filter by kind + producer to pick the quality tier they want. The raw source file itself is stored as kind=source.';

comment on column public.cds_artifacts.kind is
  'Artifact category. source = archived original file; canonical = structured extract keyed to the canonical CDS schema; raw_docling / raw_reducto = producer-specific extracts without schema normalization; cleaned = community cleaner output; schema_v1_normalized = output validating against a published target schema.';

comment on column public.cds_artifacts.producer is
  'Name of the tool that produced this artifact, e.g. tier2_acroform, docling, reducto, community-cleaner, scraper.';

comment on column public.cds_artifacts.schema_version is
  'Which year of the canonical CDS schema this artifact targets, e.g. "2025-26". Null for raw producer output that does not target a specific schema year.';

create index cds_artifacts_document_idx
  on public.cds_artifacts (document_id);

create index cds_artifacts_kind_producer_idx
  on public.cds_artifacts (kind, producer);

-- ─── cleaners ───────────────────────────────────────────────────────────────
create table public.cleaners (
  name              text primary key,
  repo_url          text not null,
  latest_version    text not null,
  output_kind       text not null,
  description       text,
  registered_at     timestamptz not null default now()
);

comment on table public.cleaners is
  'Registry of community cleanup tools that produce normalized CDS artifacts. Cleaners register here via a PR to cleaners.yaml; CI runs each registered cleaner against new raw artifacts and writes results back as cds_artifacts rows.';

-- ─── Row-level security ─────────────────────────────────────────────────────
-- Every table has RLS enabled (Automatic RLS is on for this project) and a
-- single explicit "public read" policy. Writes happen through the service_role
-- key, which bypasses RLS entirely, so no write policies are needed for V1.

alter table public.cds_documents enable row level security;
alter table public.cds_artifacts enable row level security;
alter table public.cleaners      enable row level security;

create policy "public read cds_documents"
  on public.cds_documents
  for select
  to anon, authenticated
  using (true);

create policy "public read cds_artifacts"
  on public.cds_artifacts
  for select
  to anon, authenticated
  using (true);

create policy "public read cleaners"
  on public.cleaners
  for select
  to anon, authenticated
  using (true);

-- ─── updated_at trigger on cds_documents ───────────────────────────────────
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

comment on function public.set_updated_at() is
  'Trigger function that sets NEW.updated_at = now() on every row update. Attached to cds_documents; add to other tables via CREATE TRIGGER as needed.';

create trigger cds_documents_updated_at
  before update on public.cds_documents
  for each row execute function public.set_updated_at();

-- ─── cds_manifest view ─────────────────────────────────────────────────────
-- Convenience view that joins each document to its most recent canonical
-- artifact and its archived source. Consumers who just want "latest
-- structured data per school" query this view instead of assembling the
-- join themselves. The view inherits RLS from the base tables, so the
-- public-read policies on cds_documents and cds_artifacts apply here too.

create view public.cds_manifest as
  select
    d.id                   as document_id,
    d.school_id,
    d.school_name,
    d.sub_institutional,
    d.cds_year,
    d.source_url,
    d.source_format,
    d.participation_status,
    d.discovered_at,
    d.last_verified_at,
    d.removed_at,
    d.extraction_status,
    (
      select a.id
      from public.cds_artifacts a
      where a.document_id = d.id and a.kind = 'canonical'
      order by a.created_at desc
      limit 1
    ) as latest_canonical_artifact_id,
    (
      select a.storage_path
      from public.cds_artifacts a
      where a.document_id = d.id and a.kind = 'source'
      order by a.created_at desc
      limit 1
    ) as source_storage_path
  from public.cds_documents d;

comment on view public.cds_manifest is
  'Convenience view joining cds_documents to their most recent canonical artifact and archived source file. Query this view when you want "latest structured data per school" as a single join-free GET.';

grant select on public.cds_manifest to anon, authenticated;

-- ─── Storage bucket: sources ────────────────────────────────────────────────
-- Public bucket for archived source files. Writes (uploads) require the
-- service_role key, which is how the scraper and extraction workers will
-- populate it. Public reads let consumers download the original PDF / XLSX
-- / DOCX alongside the structured data in cds_artifacts.

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'sources',
  'sources',
  true,
  52428800,  -- 50 MB per file; most CDS PDFs are 0.5-2 MB
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
)
on conflict (id) do nothing;

-- Public read policy for objects in the sources bucket. Writes bypass this
-- policy when they use the service_role key.
create policy "public read sources bucket"
  on storage.objects
  for select
  to anon, authenticated
  using (bucket_id = 'sources');
