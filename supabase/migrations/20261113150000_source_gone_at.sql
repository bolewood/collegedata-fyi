-- A school deleting its CDS file must not delete our copy from the site.
--
-- Until now the archive re-check wrote cds_documents.removed_at when a
-- school's source went away, and every public listing filters
-- removed_at IS NULL. So the archived, extracted document vanished from
-- the school page, the year page and the sitemap exactly when the archive
-- mattered most (RPI 2024-25, University of Utah 2025-26, Oberlin 2023-24
-- and 2024-25, and others).
--
-- removed_at is also the operator's hide flag (takedowns, retired duplicate
-- slugs, wrong files), and the public API docs tell consumers to filter on
-- it. That meaning stays. The upstream observation moves to its own column.

begin;

alter table public.cds_documents
  add column if not exists source_gone_at timestamptz;

comment on column public.cds_documents.source_gone_at is
  'First time a re-check found the school''s CDS page gone (404/410); recorded on the school''s most recent document. The archived copy stays public. Cleared when the source is verified live again.';

comment on column public.cds_documents.removed_at is
  'Operator hide flag: the row is excluded from every public listing (takedown, retired duplicate slug, wrong file). Not set by the archive re-check; see source_gone_at for "the school removed it".';

-- Backfill: rows the re-check hid automatically. Wrong-file hides carry a
-- data_quality_flag, and the duplicate-slug cleanup wrote its rows in two
-- batches on 2026-11-09 between 17:00 and 19:00 UTC; both are excluded and
-- stay hidden. On a clean database this matches no rows.
update public.cds_documents
   set source_gone_at = removed_at,
       removed_at = null
 where removed_at is not null
   and not (removed_at >= timestamptz '2026-11-09 17:00:00+00'
            and removed_at < timestamptz '2026-11-09 19:00:00+00')
   and data_quality_flag is null
   and participation_status = 'published';

-- Append the new column to the manifest view. CREATE OR REPLACE keeps the
-- existing column order, dependents, grants and security_invoker setting.
create or replace view public.cds_manifest
with (security_invoker = true) as
  select
    d.id as document_id,
    d.school_id,
    d.school_name,
    d.ipeds_id,
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
    ) as source_storage_path,
    d.detected_year,
    coalesce(d.detected_year, d.cds_year) as canonical_year,
    d.data_quality_flag,
    d.extracted_at,
    d.source_http_last_modified,
    d.source_creation_date,
    d.source_modification_date,
    d.source_gone_at
  from public.cds_documents d;

grant select on public.cds_manifest to anon, authenticated;

comment on view public.cds_manifest is
  'Convenience view joining cds_documents to their most recent canonical '
  'artifact and archived source file. SECURITY INVOKER so public reads '
  'honor underlying RLS. extracted_at and source_* date columns are the '
  'PRD 029 freshness signals. removed_at = hidden from public listings; '
  'source_gone_at = the school no longer publishes the file, our copy stays.';

commit;
