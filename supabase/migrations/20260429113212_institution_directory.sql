-- PRD 015 M1 — Institution directory and slug crosswalk.
--
-- The directory is one row per Title-IV institution from the College
-- Scorecard institution file, including those without a CDS in our
-- archive. The crosswalk records every (ipeds_id, school_id) mapping
-- so search can resolve aliases and prior slugs to the canonical
-- school_id.
--
-- This migration only creates the tables. The loader at
-- tools/scorecard/load_directory.py populates them and is the only
-- supported writer; web/edge-function clients read via RLS.

CREATE TABLE IF NOT EXISTS public.institution_directory (
  ipeds_id                  text PRIMARY KEY,
  school_id                 text NOT NULL UNIQUE,
  school_name               text NOT NULL,
  aliases                   text[] NOT NULL DEFAULT '{}',
  city                      text,
  state                     text,
  zip                       text,
  website_url               text,
  scorecard_data_year       text NOT NULL,
  undergraduate_enrollment  integer,
  control                   integer,
  institution_level         integer,
  predominant_degree        integer,
  highest_degree            integer,
  currently_operating       boolean,
  main_campus               boolean,
  branch_count              integer,
  latitude                  numeric,
  longitude                 numeric,
  in_scope                  boolean NOT NULL,
  exclusion_reason          text,
  directory_source          text NOT NULL DEFAULT 'scorecard',
  refreshed_at              timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT institution_directory_scope_reason_consistent
    CHECK (
      (in_scope = true  AND exclusion_reason IS NULL)
      OR
      (in_scope = false AND exclusion_reason IS NOT NULL)
    )
);

COMMENT ON TABLE public.institution_directory IS
  'Per-institution directory keyed by IPEDS UNITID. One row per Title-IV institution loaded from the College Scorecard institution file. in_scope=true means the row meets MVP public defaults (active, undergraduate-serving, four-year or two-year, degree-granting). exclusion_reason explains why an out-of-scope row is filtered from the public directory.';

-- Common filter for search and coverage queries: in-scope rows ordered
-- by school_name. Composite covers both the WHERE and the ORDER BY.
CREATE INDEX IF NOT EXISTS institution_directory_in_scope_name_idx
  ON public.institution_directory (in_scope, school_name);

-- State filter on the coverage page.
CREATE INDEX IF NOT EXISTS institution_directory_state_idx
  ON public.institution_directory (state)
  WHERE in_scope = true;

-- Lookup by school_id is already covered by the UNIQUE constraint.

CREATE TABLE IF NOT EXISTS public.institution_slug_crosswalk (
  ipeds_id      text NOT NULL,
  school_id     text NOT NULL,
  alias         text NOT NULL,
  source        text NOT NULL,
  is_primary    boolean NOT NULL DEFAULT false,
  reviewed_at   timestamptz,

  PRIMARY KEY (ipeds_id, alias),

  CONSTRAINT institution_slug_crosswalk_source_valid
    CHECK (source IN ('schools_yaml', 'scorecard', 'manual', 'redirect'))
);

COMMENT ON TABLE public.institution_slug_crosswalk IS
  'Maps every known alias for an institution to its canonical school_id. Sources: schools_yaml (preserved from existing site slugs), scorecard (auto-generated from INSTNM), manual (operator-curated), redirect (prior public slug that has been retired).';

-- Reverse lookups: "what alias points at this school_id" used by
-- redirect-resolution and admin tooling.
CREATE INDEX IF NOT EXISTS institution_slug_crosswalk_school_id_idx
  ON public.institution_slug_crosswalk (school_id);

-- Primary-only lookups for fast canonical resolution.
CREATE INDEX IF NOT EXISTS institution_slug_crosswalk_primary_idx
  ON public.institution_slug_crosswalk (alias)
  WHERE is_primary = true;

-- RLS: the directory and crosswalk are public-safe. Anonymous and
-- authenticated readers see everything. Writes go through the service
-- role only (no public write policy).
ALTER TABLE public.institution_directory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.institution_slug_crosswalk ENABLE ROW LEVEL SECURITY;

CREATE POLICY institution_directory_public_read
  ON public.institution_directory
  FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY institution_slug_crosswalk_public_read
  ON public.institution_slug_crosswalk
  FOR SELECT
  TO anon, authenticated
  USING (true);

GRANT SELECT ON public.institution_directory      TO anon, authenticated;
GRANT SELECT ON public.institution_slug_crosswalk TO anon, authenticated;
