-- Allow the archive pipeline to preserve sectionized CDS source PDFs
-- alongside the derived merged source artifact that extraction consumes.
--
-- source_part: original A/B/C/... section PDF bytes.
-- source_bundle: reserved for future explicit bundle manifests. The current
-- archive path stores the merged PDF as kind='source' so existing extraction
-- workers keep consuming the latest source artifact unchanged.

alter table public.cds_artifacts
  drop constraint if exists cds_artifacts_kind_valid,
  add constraint cds_artifacts_kind_valid
    check (kind in (
      'source',
      'source_part',
      'source_bundle',
      'canonical',
      'raw_docling',
      'raw_reducto',
      'cleaned',
      'schema_v1_normalized'
    ));
