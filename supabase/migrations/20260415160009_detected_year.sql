-- ADR 0007 Stage B: detected_year column
--
-- Adds cds_documents.detected_year as the authoritative content-derived
-- academic year, populated by the extraction worker via
-- detect_year_from_pdf_bytes. The existing cds_year column stays on the
-- row as the archive-time guess — its semantics shift from "the year"
-- to "the resolver's best guess at archive time, may be corrected by
-- extraction." cds_year remains part of the NULLS NOT DISTINCT unique
-- constraint so the archive path is unaffected.
--
-- The cds_manifest view gains a canonical_year column that returns
-- detected_year when set, otherwise falls back to cds_year. New consumer
-- code should read canonical_year; existing consumers reading cds_year
-- continue to work (the column is still populated).
--
-- This migration does NOT backfill detected_year. The extraction worker
-- populates it on its next run — see ADR 0007 Stage B rollout and
-- tools/extraction_worker/worker.py for the flip from observe to write.
--
-- This migration does NOT touch storage paths. Source bucket objects
-- remain at their archive-time paths {school_id}/{cds_year}/{sha}.ext.
-- A future year-correction operation rekeys the blob on the fly (ADR
-- 0007 Stage B trade-offs, option A).

begin;

-- ─── New column ────────────────────────────────────────────────────────────

alter table public.cds_documents
  add column detected_year text null;

-- Partial index: only populated rows. Queries like "all extracted rows
-- where the content-derived year is 2024-25" hit this index directly.
create index cds_documents_detected_year_idx
  on public.cds_documents (school_id, detected_year)
  where detected_year is not null;

-- Validity check: detected_year must match the same YYYY-YY shape as
-- cds_year when it's set. Prevents the extraction worker from writing
-- garbage like "2024" or "pending" into the authoritative column.
alter table public.cds_documents
  add constraint cds_documents_detected_year_shape
  check (
    detected_year is null
    or detected_year ~ '^(19|20)\d{2}-\d{2}$'
  );

comment on column public.cds_documents.cds_year is
  'Archive-time academic year guessed by the resolver from URL filename '
  'or anchor text. Kept as the primary-key component for historical '
  'stability. Authoritative content-derived year lives in detected_year '
  'once extraction runs. Consumers should prefer cds_manifest.canonical_year '
  'which coalesces detected_year over cds_year.';

comment on column public.cds_documents.detected_year is
  'Content-derived academic year extracted from the archived source document '
  'via detect_year_from_pdf_bytes (see tools/extraction_worker/worker.py and '
  'ADR 0007). Null until extraction runs. When set, supersedes cds_year for '
  'consumer queries via the canonical_year expression in the cds_manifest view.';

-- ─── Updated cds_manifest view ─────────────────────────────────────────────
-- CREATE OR REPLACE VIEW preserves grants and can add new columns as long
-- as the existing columns keep the same name, type, and order. The new
-- canonical_year column is appended last.

create or replace view public.cds_manifest as
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
    ) as source_storage_path,
    -- New: detected_year takes precedence when set.
    d.detected_year,
    coalesce(d.detected_year, d.cds_year) as canonical_year
  from public.cds_documents d;

comment on view public.cds_manifest is
  'Convenience view joining cds_documents to their most recent canonical '
  'artifact and archived source file. Query this view when you want '
  '"latest structured data per school" as a single join-free GET. '
  'Prefer canonical_year over cds_year — it coalesces the content-derived '
  'detected_year over the archive-time resolver guess.';

-- ─── Self-test ─────────────────────────────────────────────────────────────
-- Verify the new column, index, check constraint, and view column are
-- all live before committing. Running the migration and seeing it commit
-- IS the passing test for this migration.

do $$
declare
  have_column int;
  have_index int;
  have_check int;
  have_view_col int;
  sample_canonical text;
begin
  select count(*) into have_column
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'cds_documents'
      and column_name = 'detected_year';
  if have_column <> 1 then
    raise exception 'detected_year column was not created';
  end if;

  select count(*) into have_index
    from pg_indexes
    where schemaname = 'public'
      and indexname = 'cds_documents_detected_year_idx';
  if have_index <> 1 then
    raise exception 'cds_documents_detected_year_idx was not created';
  end if;

  select count(*) into have_check
    from pg_constraint
    where conname = 'cds_documents_detected_year_shape';
  if have_check <> 1 then
    raise exception 'cds_documents_detected_year_shape check was not created';
  end if;

  select count(*) into have_view_col
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'cds_manifest'
      and column_name = 'canonical_year';
  if have_view_col <> 1 then
    raise exception 'cds_manifest.canonical_year view column was not created';
  end if;

  -- Verify COALESCE semantics: when detected_year is null, canonical_year
  -- must equal cds_year. When detected_year is set, canonical_year must
  -- equal detected_year.
  select canonical_year into sample_canonical
    from public.cds_manifest
    limit 1;
  if sample_canonical is null then
    raise exception 'canonical_year returned null for a row with non-null cds_year';
  end if;

  -- Sanity check: attempting to write a malformed detected_year fails.
  begin
    insert into public.cds_documents (school_id, school_name, cds_year, detected_year)
      values ('__check_test__', 'Check Test', '2099-00', 'not-a-year');
    raise exception 'detected_year check constraint did not reject malformed value';
  exception when check_violation then
    -- expected
    null;
  end;
end $$;

commit;
