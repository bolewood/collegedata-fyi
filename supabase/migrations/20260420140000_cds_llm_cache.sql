-- cds_llm_cache: response cache for the Tier 4 LLM fallback (PRD 006 Phase 1).
--
-- Internal table. Service-role access only; no anon/authenticated grants.
-- Every LLM call writes a row here keyed by the exact prompt-shaping
-- inputs so a second call with the same inputs can reuse the response
-- and re-run deterministic validation locally.
--
-- Key columns grounded in what actually persists today:
--   - source_sha256 mirrors cds_documents.source_sha256 (the PDF bytes hash).
--   - markdown_sha256 is hashed at runtime from notes.markdown on the
--     tier4_docling artifact. cds_artifacts.sha256 is NOT populated by the
--     current Tier 4 writer (worker.py:420), so we don't depend on it.
--
-- See docs/prd/006-llm-fallback.md §Data-model changes for the full design.

CREATE TABLE public.cds_llm_cache (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id            uuid NOT NULL REFERENCES public.cds_documents(id) ON DELETE CASCADE,
  source_sha256          text NOT NULL,
  markdown_sha256        text NOT NULL,
  section_name           text NOT NULL,
  schema_version         text NOT NULL,
  model_name             text NOT NULL,
  prompt_version         text NOT NULL,
  strategy_version       text NOT NULL,
  cleaner_version        text NOT NULL DEFAULT '',
  missing_fields_sha256  text NOT NULL,
  status                 text NOT NULL CHECK (
    status IN ('ok', 'validation_failed', 'budget_skipped', 'in_flight')
  ),
  input_tokens           integer,
  cache_write_tokens     integer,
  cache_read_tokens      integer,
  output_tokens          integer,
  estimated_cost_usd     numeric(10, 6),
  response_json          jsonb,
  created_at             timestamptz NOT NULL DEFAULT now()
);

-- Uniqueness enforced by a dedicated unique index rather than a table
-- UNIQUE constraint. cleaner_version is NOT NULL DEFAULT '' so no
-- coalesce() expression is required.
CREATE UNIQUE INDEX cds_llm_cache_key_idx
  ON public.cds_llm_cache (
    source_sha256,
    section_name,
    schema_version,
    model_name,
    prompt_version,
    strategy_version,
    cleaner_version,
    missing_fields_sha256
  );

-- Supporting index for document-scoped lookups (worker "what has this
-- doc already cached" queries).
CREATE INDEX cds_llm_cache_document_id_idx
  ON public.cds_llm_cache (document_id, section_name);

COMMENT ON TABLE public.cds_llm_cache IS
  'Response cache for the Tier 4 LLM fallback (PRD 006). Keyed by the exact '
  'prompt-shaping inputs so a re-run with the same inputs reuses the '
  'response without re-billing. markdown_sha256 captures Docling re-runs '
  '(new markdown invalidates stale cached responses).';

COMMENT ON COLUMN public.cds_llm_cache.source_sha256 IS
  'Mirrors cds_documents.source_sha256. Re-hashed PDF bytes would invalidate.';

COMMENT ON COLUMN public.cds_llm_cache.markdown_sha256 IS
  'sha256(notes.markdown) at time of call. Docling version bumps or re-runs '
  'produce new markdown and must invalidate the cache.';

COMMENT ON COLUMN public.cds_llm_cache.status IS
  'ok = response accepted; validation_failed = model returned unusable output; '
  'budget_skipped = cap hit before the call was made; in_flight = reserved for '
  'future concurrent-run protection (unused in Phase 1).';
