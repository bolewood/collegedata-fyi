-- PRD 038 Decision 1 / A3: before/after diff of the selected base artifact per document. READ-ONLY (one SELECT).
--
-- "Before" is what cds_selected_extraction_result picks today. "After" applies the A3 rule: keep only
-- artifacts built from the document's CURRENT source (an artifact is excluded only when it records a source
-- sha AND that sha differs from the current source; no recorded sha counts as current), then the same
-- producer rank and recency. Current source = the newest canonical artifact's
-- notes.source_selection.chosen_sha256 when PR #258 chose one, else the newest kind='source' sha.
--
-- Run (read-only):  psql "$DATABASE_URL" -X -f supabase/pending/038_decision1_selection_diff.sql
-- It lists only documents whose selected base artifact changes, then a one-row summary.

WITH docs AS (
  SELECT DISTINCT a.document_id FROM public.cds_artifacts a WHERE a.kind = 'canonical'
),
newest_canonical AS (
  SELECT DISTINCT ON (a.document_id) a.document_id, a.notes -> 'source_selection' ->> 'chosen_sha256' AS chosen_sha
  FROM public.cds_artifacts a
  WHERE a.kind = 'canonical'
    AND a.producer IN ('tier1_xlsx', 'tier2_acroform', 'tier6_html', 'tier4_docling')
  ORDER BY a.document_id, a.created_at DESC, a.id DESC
),
newest_source AS (
  SELECT DISTINCT ON (a.document_id) a.document_id, a.sha256 AS source_sha
  FROM public.cds_artifacts a
  WHERE a.kind = 'source'
  ORDER BY a.document_id, a.created_at DESC, a.id DESC
),
current_source AS (
  SELECT d.document_id, COALESCE(nc.chosen_sha, ns.source_sha) AS current_sha
  FROM docs d
  LEFT JOIN newest_canonical nc USING (document_id)
  LEFT JOIN newest_source ns USING (document_id)
),
cands AS (
  SELECT
    a.document_id, a.id, a.producer, a.producer_version, a.created_at,
    COALESCE(a.notes ->> 'source_sha256', a.notes -> 'source_artifact' ->> 'sha256') AS recorded_sha,
    cs.current_sha,
    CASE a.producer WHEN 'tier1_xlsx' THEN 1 WHEN 'tier2_acroform' THEN 2 WHEN 'tier6_html' THEN 3 WHEN 'tier4_docling' THEN 4 END AS producer_rank
  FROM public.cds_artifacts a
  JOIN current_source cs USING (document_id)
  WHERE a.kind = 'canonical'
    AND a.producer IN ('tier1_xlsx', 'tier2_acroform', 'tier6_html', 'tier4_docling')
),
before_pick AS (
  SELECT DISTINCT ON (document_id) document_id, id AS before_id, producer AS before_producer, producer_version AS before_version
  FROM cands
  ORDER BY document_id, producer_rank, created_at DESC, id DESC
),
after_pick AS (
  SELECT DISTINCT ON (document_id) document_id, id AS after_id, producer AS after_producer, producer_version AS after_version
  FROM cands
  WHERE recorded_sha IS NULL OR current_sha IS NULL OR recorded_sha = current_sha
  ORDER BY document_id, producer_rank, created_at DESC, id DESC
),
diff AS (
  SELECT b.document_id, b.before_producer, b.before_version, a.after_producer, a.after_version,
         (a.after_id IS NULL) AS no_artifact_after
  FROM before_pick b
  LEFT JOIN after_pick a USING (document_id)
  WHERE a.after_id IS DISTINCT FROM b.before_id
)
SELECT d.document_id, m.school_id, m.canonical_year, d.before_producer, d.before_version,
       d.after_producer, d.after_version, d.no_artifact_after
FROM diff d
LEFT JOIN public.cds_manifest m ON m.document_id = d.document_id
ORDER BY m.school_id, m.canonical_year;
