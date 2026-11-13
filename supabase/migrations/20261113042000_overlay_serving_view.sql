-- PRD 038 A15: serve the template overlay through cds_selected_extraction_result.
--
-- The projection (project_browser_data.py) and the school page (web fetchExtract) apply the same rules in Python and TS; the three
-- are pinned by tools/browser_backend/fixtures/overlay_parity.json (tools/browser_backend/run_overlay_sql_fixture.py runs this view
-- body over that fixture, read-only).
--
-- What this migration does:
--   * cds_overlay_serve_classes(): the served-class set, STABLE (it is a configuration point, replaced by a later migration, not by an
--     environment variable). It returns numeric, choice, checkbox_box and ocr_numeric. ROLLBACK is
--         CREATE OR REPLACE FUNCTION public.cds_overlay_serve_classes() RETURNS text[] LANGUAGE sql STABLE AS $$ SELECT '{}'::text[] $$;
--     (with the web and the projection set to OVERLAY_SERVE_CLASSES=none, then re-project the rows whose
--     school_browser_rows.overlay_producer_version IS NOT NULL, then refresh the serving caches).
--   * adds an overlay lateral join next to the tier4_llm_fallback join. It picks the newest kind='cleaned',
--     producer='tier2_template_overlay' artifact for the document whose notes.source_sha256 is present and EQUAL to the Tier 4
--     base's recorded sha (notes.source_sha256, else notes.source_artifact.sha256; a base with no recorded sha never merges, A3),
--     whose schema_version equals the base's (both non-null), whose notes.held is exactly false, only for a tier4_docling base.
--   * validates the WHOLE served set: any name outside the known classes makes the set empty.
--   * serves a value only when its class is in the validated set, it is not blank (a blank overlay value never overwrites a
--     populated base value), and: its class is not ocr_numeric and it has no Lane 2 evidence; or its class is ocr_numeric, it has
--     Lane 2 evidence and either it is a direct Lane 2 value whose page_kind is 'vector' or it is a derived total whose
--     input_page_kinds is a non-empty list of only 'vector'. Raster-page OCR and a missing page_kind are never served. A
--     notes.values that is not a JSON object serves nothing.
--   * merge order fallback || tier4 base || overlay (the jsonb || operator: the right side wins).
--
-- The view's column list and order are unchanged from 20260428153000_tier4_fallback_compatibility.sql; CREATE OR REPLACE VIEW
-- keeps its grants. The view is security_invoker, so anon and authenticated also need EXECUTE on the function (granted below).
-- The Tier 4 disagreement hold is not evaluated here: `held` is a write-time fact in the artifact and this view only skips
-- artifacts whose notes.held is not exactly false.

CREATE OR REPLACE FUNCTION public.cds_overlay_serve_classes()
RETURNS text[]
LANGUAGE sql
STABLE
AS $$ SELECT ARRAY['numeric', 'choice', 'checkbox_box', 'ocr_numeric']::text[] $$;

COMMENT ON FUNCTION public.cds_overlay_serve_classes() IS
  'PRD 038 A15: the template-overlay emission classes cds_selected_extraction_result serves. ocr_numeric is further restricted to vector pages. Replace this function (a migration) to change what is served; empty = serve nothing.';

GRANT EXECUTE ON FUNCTION public.cds_overlay_serve_classes() TO anon, authenticated, service_role;

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
        CROSS JOIN LATERAL (
          SELECT
            -- Lane 2 evidence, in any spelling of the number two: lane 2, 2.0 or "2", or such a 2 inside derived_lanes
            CASE
              WHEN jsonb_typeof(e.value -> 'lane') = 'number' THEN (e.value ->> 'lane')::numeric = 2
              WHEN jsonb_typeof(e.value -> 'lane') = 'string' AND (e.value ->> 'lane') ~ '^\s*[0-9]+(\.[0-9]+)?\s*$'
                THEN btrim(e.value ->> 'lane')::numeric = 2
              ELSE false
            END AS lane_two,
            EXISTS (
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
            ) AS derived_two,
            -- a derived total's Lane 2 inputs: a non-empty list of only "vector"
            (
              jsonb_typeof(e.value -> 'input_page_kinds') = 'array'
              AND jsonb_array_length(e.value -> 'input_page_kinds') > 0
              AND NOT EXISTS (
                SELECT 1 FROM jsonb_array_elements(e.value -> 'input_page_kinds') AS k(kind)
                WHERE k.kind IS DISTINCT FROM '"vector"'::jsonb
              )
            ) AS inputs_all_vector
        ) AS f
        WHERE e.value ->> 'emission_class' = ANY (sv.classes)
          AND COALESCE(NULLIF(btrim(e.value ->> 'value_decoded'), ''), NULLIF(btrim(e.value ->> 'value'), '')) IS NOT NULL
          AND CASE
            -- OCR is served only with Lane 2 evidence and every Lane 2 input on a vector page; a missing page kind is not served
            WHEN e.value ->> 'emission_class' = 'ocr_numeric' THEN
              (f.lane_two OR f.derived_two)
              AND CASE WHEN f.lane_two THEN e.value ->> 'page_kind' = 'vector' ELSE f.inputs_all_vector END
            ELSE NOT (f.lane_two OR f.derived_two)
          END
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
  'One selected extraction result per document. Chooses canonical producer precedence tier1_xlsx > tier2_acroform > tier6_html > tier4_docling, then overlays tier4_llm_fallback cleaned values only for Tier 4 base results when the fallback matches the selected base artifact id or legacy markdown hash + cleaner version, then the served tier2_template_overlay values (only a Tier 4 base with a recorded source sha and schema version equal to the overlay''s, an overlay that is not held, classes in cds_overlay_serve_classes(), OCR only from vector pages). JSONB merge order: overlay over deterministic base over fallback.';

DO $$
BEGIN
  -- shape only (no row counts): the function and the view exist, and the view keeps its eleven columns in order
  IF to_regprocedure('public.cds_overlay_serve_classes()') IS NULL THEN
    RAISE EXCEPTION 'cds_overlay_serve_classes() was not created';
  END IF;
  IF (SELECT array_agg(column_name::text ORDER BY ordinal_position)
      FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'cds_selected_extraction_result')
     IS DISTINCT FROM ARRAY['document_id', 'base_artifact_id', 'base_producer', 'base_producer_version', 'base_schema_version',
                            'base_created_at', 'fallback_artifact_id', 'fallback_producer', 'fallback_producer_version',
                            'fallback_created_at', 'selected_values']::text[] THEN
    RAISE EXCEPTION 'cds_selected_extraction_result columns changed';
  END IF;
END
$$;
