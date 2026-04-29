-- PRD 015 M2 — archive_queue.source column.
--
-- Distinguishes which universe a queue row was enqueued from. The two
-- enqueue paths are:
--
--   schools_yaml          archive-enqueue reads tools/finder/schools.yaml
--                         and seeds rows for every active entry. This
--                         is the existing daily cron path.
--
--   institution_directory directory-enqueue (M2) reads
--                         institution_directory WHERE in_scope = true
--                         and seeds rows for Scorecard-only schools that
--                         have no schools.yaml entry and no prior
--                         cds_documents row. Operator-triggered, no cron.
--
-- Why this column exists: M3's coverage status depends on knowing whether
-- a school has had a real resolver attempt yet. Without source, we cannot
-- cleanly answer "how many directory-sourced schools have been probed?"
-- without joining through institution_directory. The audit trail also lets
-- operator reports break out cooldown / outcome stats by universe — useful
-- when triaging "is the directory expansion producing too many
-- no_pdfs_found rows?".
--
-- Default 'schools_yaml' so the existing archive-enqueue function does not
-- need to be modified to set the column. New writers (directory-enqueue)
-- pass 'institution_directory' explicitly.
--
-- school_hosting_observations intentionally does NOT get this column.
-- Its observation_source already differentiates probe origin
-- (resolver/playwright/manual) and the enqueue universe is recoverable
-- via school_id ↔ institution_directory join when needed. Adding a
-- second source column there would require plumbing through
-- archive-process and the shared resolver, which is invasive for
-- negligible analytical benefit.

alter table public.archive_queue
  add column source text not null default 'schools_yaml';

alter table public.archive_queue
  add constraint archive_queue_source_valid
  check (source in ('schools_yaml', 'institution_directory'));

comment on column public.archive_queue.source is
  'Which enqueue path created this row. schools_yaml = archive-enqueue reading tools/finder/schools.yaml (the daily cron path). institution_directory = directory-enqueue (PRD 015 M2) reading institution_directory in-scope rows that have no schools.yaml entry. Existing rows backfilled to schools_yaml since archive-enqueue is the only writer prior to this migration.';

-- Partial index supporting "show me directory-sourced rows by status"
-- operator queries. schools_yaml rows dominate cardinality; partial index
-- on the smaller universe keeps directory-discovery analytics cheap.
create index archive_queue_directory_source_idx
  on public.archive_queue (status, processed_at desc)
  where source = 'institution_directory';
