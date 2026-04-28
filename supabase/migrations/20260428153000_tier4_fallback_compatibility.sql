-- Tighten Tier 4 fallback overlay semantics after the v0.3 Docling drain.
--
-- A tier4_llm_fallback artifact is only safe to merge when it was generated
-- against the selected tier4_docling base artifact. New fallback artifacts
-- carry notes.base_artifact_id. Legacy artifacts can still match by the
-- markdown hash + cleaner version recorded in notes.

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;

CREATE OR REPLACE VIEW public.cds_selected_extraction_result
WITH (security_invoker = true) AS
WITH ranked_base AS (
  SELECT
    a.*,
    CASE a.producer
      WHEN 'tier1_xlsx' THEN 1
      WHEN 'tier2_acroform' THEN 2
      WHEN 'tier6_html' THEN 3
      WHEN 'tier4_docling' THEN 4
      ELSE 99
    END AS producer_rank,
    row_number() OVER (
      PARTITION BY a.document_id
      ORDER BY
        CASE a.producer
          WHEN 'tier1_xlsx' THEN 1
          WHEN 'tier2_acroform' THEN 2
          WHEN 'tier6_html' THEN 3
          WHEN 'tier4_docling' THEN 4
          ELSE 99
        END,
        a.created_at DESC,
        a.id DESC
    ) AS rn
  FROM public.cds_artifacts a
  WHERE a.kind = 'canonical'
    AND a.producer IN ('tier1_xlsx', 'tier2_acroform', 'tier6_html', 'tier4_docling')
)
SELECT
  b.document_id,
  b.id AS base_artifact_id,
  b.producer AS base_producer,
  b.producer_version AS base_producer_version,
  b.schema_version AS base_schema_version,
  b.created_at AS base_created_at,
  CASE WHEN b.producer = 'tier4_docling' THEN f.id ELSE NULL END AS fallback_artifact_id,
  CASE WHEN b.producer = 'tier4_docling' THEN f.producer ELSE NULL END AS fallback_producer,
  CASE WHEN b.producer = 'tier4_docling' THEN f.producer_version ELSE NULL END AS fallback_producer_version,
  CASE WHEN b.producer = 'tier4_docling' THEN f.created_at ELSE NULL END AS fallback_created_at,
  CASE
    WHEN b.producer = 'tier4_docling' AND f.id IS NOT NULL
      THEN COALESCE(f.notes -> 'values', '{}'::jsonb) || COALESCE(b.notes -> 'values', '{}'::jsonb)
    ELSE COALESCE(b.notes -> 'values', '{}'::jsonb)
  END AS selected_values
FROM ranked_base b
LEFT JOIN LATERAL (
  SELECT a.*
  FROM public.cds_artifacts a
  WHERE a.document_id = b.document_id
    AND a.kind = 'cleaned'
    AND a.producer = 'tier4_llm_fallback'
    AND b.producer = 'tier4_docling'
    AND (
      (
        a.notes ? 'base_artifact_id'
        AND a.notes ->> 'base_artifact_id' = b.id::text
        AND COALESCE(a.notes ->> 'base_producer_version', b.producer_version, '') =
            COALESCE(b.producer_version, '')
      )
      OR (
        NOT (a.notes ? 'base_artifact_id')
        AND a.notes ? 'markdown_sha256'
        AND b.notes ? 'markdown'
        AND a.notes ->> 'markdown_sha256' =
            encode(extensions.digest(convert_to(b.notes ->> 'markdown', 'UTF8'), 'sha256'), 'hex')
        AND COALESCE(a.notes ->> 'cleaner_version', '') =
            COALESCE(b.producer_version, '')
      )
    )
  ORDER BY a.created_at DESC, a.id DESC
  LIMIT 1
) f ON true
WHERE b.rn = 1;

COMMENT ON VIEW public.cds_selected_extraction_result IS
  'One selected extraction result per document. Chooses canonical producer precedence tier1_xlsx > tier2_acroform > tier6_html > tier4_docling, then overlays tier4_llm_fallback cleaned values only for Tier 4 base results when the fallback matches the selected base artifact id or legacy markdown hash + cleaner version. JSONB merge order makes deterministic base values win conflicts.';
