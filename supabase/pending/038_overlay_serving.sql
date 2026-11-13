-- PRD 038 (A2, A3, A13): serve template-overlay values through cds_selected_extraction_result.
--
-- PENDING. This file is NOT a migration and is NOT applied by `supabase db push`. It is applied only by a
-- later PR (as a real file under supabase/migrations/), from `main`, after the owner approves the shadow
-- audit. See supabase/pending/README.md.
--
-- What it does:
--   * cds_overlay_serve_classes(): the served-class set. Returns '{}' here, so applying this file changes no
--     output. Serving a class is a later one-line CREATE OR REPLACE of this function.
--   * adds an overlay lateral join next to the tier4_llm_fallback join. It picks the newest
--     kind='cleaned', producer='tier2_template_overlay' artifact for the document whose notes.source_sha256 is
--     present and EQUAL to the Tier 4 base's recorded sha (notes.source_sha256, else
--     notes.source_artifact.sha256; a base with no recorded sha never merges, A3), whose schema_version equals the
--     base's (both non-null: the overlay's ids follow its template year; Tier 4 artifacts without a schema version
--     carry 2025-26 ids whatever the template, A13), whose notes.held is
--     exactly false (Decision 3), only for a tier4_docling base.
--   * validates the WHOLE served set: any name outside the known classes makes the set empty (as in Python and TS).
--   * serves only values whose emission_class is in the (validated) set, that are not blank (a blank overlay value
--     never overwrites a populated base value) and that carry no Lane 2 evidence: lane 2 as 2, 2.0 or "2", or any
--     such 2 in derived_lanes, whatever the set says. A notes.values that is not a JSON object serves nothing.
--   * treats an empty string as a missing sha or schema version (NULLIF), as Python and TS do.
--   * merge order fallback || tier4 base || overlay (the jsonb || operator: the right side wins).
--
-- The disagreement hold is NOT evaluated here: `held` is a write-time fact in the artifact (PRD 038 A14), and this view
-- only skips artifacts whose notes.held is not exactly false.
--
-- The output columns are exactly those of the view in 20260428153000_tier4_fallback_compatibility.sql.
-- The Decision 1 selection-precedence change is NOT in this file (see 038_decision1_selection_diff.sql).

CREATE OR REPLACE FUNCTION public.cds_overlay_serve_classes()
RETURNS text[]
LANGUAGE sql
IMMUTABLE
AS $$ SELECT '{}'::text[] $$;

COMMENT ON FUNCTION public.cds_overlay_serve_classes() IS
  'PRD 038: the template-overlay emission classes the selected-extraction view serves. Empty = serve nothing. Lane 2 values are never served whatever this returns.';

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;

CREATE OR REPLACE VIEW public.cds_selected_extraction_result
WITH (security_invoker = true) AS
WITH serve AS (
  -- the served set, validated as a whole: any unknown class name serves nothing
  SELECT CASE
           WHEN c <@ ARRAY['numeric', 'choice', 'checkbox_box', 'checkbox_boxless', 'free_text', 'ocr_numeric']::text[]
             THEN c
           ELSE '{}'::text[]
         END AS classes
  FROM (SELECT COALESCE(public.cds_overlay_serve_classes(), '{}'::text[]) AS c) x
),
ranked_base AS (
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
  END
  || COALESCE(ov.served_values, '{}'::jsonb) AS selected_values
FROM ranked_base b
CROSS JOIN serve sv
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
LEFT JOIN LATERAL (
  -- served overlay values: newest overlay with a strictly equal source sha and schema version, not held, Tier 4 base only
  SELECT
    CASE WHEN jsonb_typeof(o.notes -> 'values') = 'object' THEN COALESCE(
      (
        SELECT jsonb_object_agg(e.key, e.value)
        FROM jsonb_each(o.notes -> 'values') AS e
        WHERE e.value ->> 'emission_class' = ANY (sv.classes)
          AND COALESCE(NULLIF(btrim(e.value ->> 'value_decoded'), ''), NULLIF(btrim(e.value ->> 'value'), '')) IS NOT NULL
          AND NOT (
            CASE
              WHEN jsonb_typeof(e.value -> 'lane') = 'number' THEN (e.value ->> 'lane')::numeric = 2
              WHEN jsonb_typeof(e.value -> 'lane') = 'string' AND (e.value ->> 'lane') ~ '^\s*[0-9]+(\.[0-9]+)?\s*$'
                THEN btrim(e.value ->> 'lane')::numeric = 2
              ELSE false
            END
          )
          AND NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements(
              CASE WHEN jsonb_typeof(e.value -> 'derived_lanes') = 'array' THEN e.value -> 'derived_lanes' ELSE '[]'::jsonb END
            ) AS d(lane)
            WHERE CASE
              WHEN jsonb_typeof(d.lane) = 'number' THEN (d.lane #>> '{}')::numeric = 2
              WHEN jsonb_typeof(d.lane) = 'string' AND (d.lane #>> '{}') ~ '^\s*[0-9]+(\.[0-9]+)?\s*$'
                THEN btrim(d.lane #>> '{}')::numeric = 2
              ELSE false
            END
          )
      ),
      '{}'::jsonb
    ) ELSE '{}'::jsonb END AS served_values
  FROM (
    SELECT a.*
    FROM public.cds_artifacts a
    WHERE a.document_id = b.document_id
      AND a.kind = 'cleaned'
      AND a.producer = 'tier2_template_overlay'
      AND b.producer = 'tier4_docling'
      AND cardinality(sv.classes) > 0
      AND NULLIF(b.schema_version, '') IS NOT NULL
      AND NULLIF(a.schema_version, '') IS NOT NULL
      AND a.schema_version = b.schema_version
      AND COALESCE(NULLIF(b.notes ->> 'source_sha256', ''), NULLIF(b.notes -> 'source_artifact' ->> 'sha256', '')) IS NOT NULL
      AND NULLIF(a.notes ->> 'source_sha256', '') =
          COALESCE(NULLIF(b.notes ->> 'source_sha256', ''), NULLIF(b.notes -> 'source_artifact' ->> 'sha256', ''))
      AND (a.notes -> 'held') = 'false'::jsonb
    ORDER BY a.created_at DESC, a.id DESC
    LIMIT 1
  ) o
) ov ON true
WHERE b.rn = 1;

COMMENT ON VIEW public.cds_selected_extraction_result IS
  'One selected extraction result per document. Chooses canonical producer precedence tier1_xlsx > tier2_acroform > tier6_html > tier4_docling, then overlays tier4_llm_fallback cleaned values only for Tier 4 base results when the fallback matches the selected base artifact id or legacy markdown hash + cleaner version, then the served tier2_template_overlay values (only a Tier 4 base with a recorded source sha equal to the overlay''s, an overlay that is not held, classes in cds_overlay_serve_classes(), never Lane 2). JSONB merge order: overlay over deterministic base over fallback.';
