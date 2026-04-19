-- Add source_provenance to cds_documents so consumers can distinguish
-- documents we archived directly from the school's own website from
-- documents we pulled from a third-party mirror (college-transitions,
-- wayback machine, etc.). Existing rows are all school_direct by
-- definition — we didn't have any mirror intake before this migration.
--
-- Policy:
--   school_direct             resolver / probe / well-known-paths fallback
--                             on the school's own domain, OR operator-supplied
--                             URLs that point at the school's own domain.
--   mirror_college_transitions re-hosted on Google Drive by collegetransitions.com
--                             at https://www.collegetransitions.com/dataverse/
--                             common-data-set-repository/ Ingested by
--                             tools/mirrors/college_transitions/ingest.py as a
--                             gap-filler — NEVER overwrites an existing
--                             school_direct row.
--   operator_manual           hand-curated via manual_urls.yaml or
--                             school_overrides.yaml.direct_archive_urls.
--
-- When a school publishes their own file after we mirrored it, the next
-- resolver run's refreshDocumentWithNewSha path upgrades the row's
-- provenance to school_direct. The original school's publication always
-- wins.

alter table public.cds_documents
  add column source_provenance text not null default 'school_direct';

alter table public.cds_documents
  add constraint cds_documents_source_provenance_valid
  check (source_provenance in (
    'school_direct',
    'mirror_college_transitions',
    'operator_manual'
  ));

comment on column public.cds_documents.source_provenance is
  'Where we got this document. school_direct = archived from the school''s own domain via the resolver or operator override on a school-hosted URL. mirror_* = re-hosted by a third-party aggregator (see individual mirror values for the source). operator_manual = hand-curated URL list. Consumers preferring authoritative data should filter on source_provenance = ''school_direct''; consumers prioritizing coverage can include all.';

-- Index to support "show me all schools whose current doc is mirrored" queries
-- and the cds_completeness audit pattern.
create index cds_documents_provenance_idx
  on public.cds_documents (source_provenance, cds_year);
