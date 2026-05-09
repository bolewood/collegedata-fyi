-- Backfill official month-level release provenance for the first PRD 021 load.
--
-- NCES lists the 2024-25 Access Database as Provisional, released March 2026.
-- Store that as 2026-03-01 with month precision in notes; the release probe
-- starts checking for the next bundle 10 months later.

begin;

update public.ipeds_releases
set
  release_date = '2026-03-01'::date,
  notes = coalesce(notes, '{}'::jsonb) || jsonb_build_object(
    'release_date_text', 'March 2026',
    'release_date_precision', 'month',
    'release_probe_due_on', '2027-01-01'
  )
where collection_year = '2024-25'
  and release_type = 'provisional'
  and metadata_url like '%IPEDS202425Tablesdoc.xlsx';

commit;
