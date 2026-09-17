-- FSA institutional nonpayment (PRD companion pipeline).
-- Surgical directory OPEID columns plus vintage-preserving FSA facts.
-- Do not populate opeid here; tools/fsa/load.py fills from the Scorecard CSV
-- after this migration is applied from main. Do not run load_directory.py
-- --apply as the backfill.

ALTER TABLE public.institution_directory
  ADD COLUMN IF NOT EXISTS opeid text;

ALTER TABLE public.institution_directory
  ADD COLUMN IF NOT EXISTS opeid6 text GENERATED ALWAYS AS (left(opeid, 6)) STORED;

ALTER TABLE public.institution_directory
  DROP CONSTRAINT IF EXISTS institution_directory_opeid_shape;

ALTER TABLE public.institution_directory
  ADD CONSTRAINT institution_directory_opeid_shape
  CHECK (opeid IS NULL OR opeid ~ '^[0-9]{8}$');

COMMENT ON COLUMN public.institution_directory.opeid IS
  '8-digit Title IV OPEID from College Scorecard, zero-padded. Not the FSA 6-digit main-campus key.';

COMMENT ON COLUMN public.institution_directory.opeid6 IS
  'First 6 characters of opeid. Used to join FSA school-level nonpayment rows to the main campus.';

CREATE INDEX IF NOT EXISTS institution_directory_opeid_idx
  ON public.institution_directory (opeid);

CREATE INDEX IF NOT EXISTS institution_directory_opeid6_main_idx
  ON public.institution_directory (opeid6)
  WHERE in_scope = true AND main_campus = true;

CREATE OR REPLACE FUNCTION public.apply_directory_opeid_fill(updates jsonb)
RETURNS integer
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  updated integer;
BEGIN
  UPDATE public.institution_directory d
  SET opeid = u.opeid
  FROM jsonb_to_recordset(updates) AS u(ipeds_id text, opeid text)
  WHERE d.ipeds_id = u.ipeds_id
    AND d.opeid IS NULL
    AND u.opeid ~ '^[0-9]{8}$';
  GET DIAGNOSTICS updated = ROW_COUNT;
  RETURN updated;
END;
$$;

REVOKE ALL ON FUNCTION public.apply_directory_opeid_fill(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_directory_opeid_fill(jsonb) TO service_role;

CREATE TABLE IF NOT EXISTS public.fsa_releases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  as_of_date date NOT NULL,
  as_of_label text,
  cohort_window_start date,
  cohort_window_end date,
  source_url text NOT NULL,
  source_sha256 text NOT NULL UNIQUE,
  announcement_url text,
  title text,
  downloaded_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.fsa_releases IS
  'One row per FSA institutional nonpayment workbook. Unique on source_sha256. Same as-of with a new sha is a replacement vintage.';

CREATE TABLE IF NOT EXISTS public.fsa_nonpayment_facts (
  release_id uuid NOT NULL REFERENCES public.fsa_releases(id) ON DELETE CASCADE,
  opeid text NOT NULL,
  school_id text,
  school_name_raw text,
  school_type text,
  state text,
  borrowers_in_denom integer,
  borrowers_raw text,
  nonpayment_rate numeric,
  rate_raw text,
  suppressed boolean NOT NULL DEFAULT false,
  public_visible boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (release_id, opeid),
  CONSTRAINT fsa_nonpayment_facts_rate_fraction
    CHECK (nonpayment_rate IS NULL OR (nonpayment_rate >= 0 AND nonpayment_rate <= 1)),
  CONSTRAINT fsa_nonpayment_facts_public_visible_ok
    CHECK (
      NOT public_visible
      OR (
        school_id IS NOT NULL
        AND suppressed IS NOT TRUE
        AND nonpayment_rate IS NOT NULL
      )
    )
);

COMMENT ON TABLE public.fsa_nonpayment_facts IS
  'Institution-level FSA nonpayment rates. school_id is stamped at load. public_visible is false for suppression tokens and unmatched rows.';

CREATE UNIQUE INDEX IF NOT EXISTS fsa_nonpayment_facts_release_school_idx
  ON public.fsa_nonpayment_facts (release_id, school_id)
  WHERE school_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fsa_nonpayment_facts_school_idx
  ON public.fsa_nonpayment_facts (school_id)
  WHERE public_visible = true AND school_id IS NOT NULL;

ALTER TABLE public.fsa_releases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fsa_nonpayment_facts ENABLE ROW LEVEL SECURITY;

CREATE POLICY fsa_releases_public_read
  ON public.fsa_releases
  FOR SELECT TO anon, authenticated
  USING (true);

CREATE POLICY fsa_nonpayment_facts_public_read
  ON public.fsa_nonpayment_facts
  FOR SELECT TO anon, authenticated
  USING (public_visible);

GRANT SELECT ON public.fsa_releases TO anon, authenticated;
GRANT SELECT ON public.fsa_nonpayment_facts TO anon, authenticated;

CREATE OR REPLACE FUNCTION public.apply_fsa_nonpayment_release(
  release jsonb,
  facts jsonb
) RETURNS uuid
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  rid uuid;
BEGIN
  SELECT id INTO rid
  FROM public.fsa_releases
  WHERE source_sha256 = release->>'source_sha256';

  IF rid IS NULL THEN
    INSERT INTO public.fsa_releases (
      as_of_date, as_of_label, cohort_window_start, cohort_window_end,
      source_url, source_sha256, announcement_url, title, downloaded_at
    )
    VALUES (
      (release->>'as_of_date')::date,
      release->>'as_of_label',
      (release->>'cohort_window_start')::date,
      (release->>'cohort_window_end')::date,
      release->>'source_url',
      release->>'source_sha256',
      release->>'announcement_url',
      release->>'title',
      COALESCE((release->>'downloaded_at')::timestamptz, now())
    )
    RETURNING id INTO rid;
  ELSE
    UPDATE public.fsa_releases
    SET
      as_of_date = (release->>'as_of_date')::date,
      as_of_label = release->>'as_of_label',
      cohort_window_start = (release->>'cohort_window_start')::date,
      cohort_window_end = (release->>'cohort_window_end')::date,
      source_url = release->>'source_url',
      announcement_url = release->>'announcement_url',
      title = release->>'title',
      downloaded_at = COALESCE((release->>'downloaded_at')::timestamptz, now())
    WHERE id = rid;
    DELETE FROM public.fsa_nonpayment_facts WHERE release_id = rid;
  END IF;

  INSERT INTO public.fsa_nonpayment_facts (
    release_id, opeid, school_id, school_name_raw, school_type, state,
    borrowers_in_denom, borrowers_raw, nonpayment_rate, rate_raw,
    suppressed, public_visible
  )
  SELECT
    rid,
    f.opeid,
    f.school_id,
    f.school_name_raw,
    f.school_type,
    f.state,
    f.borrowers_in_denom,
    f.borrowers_raw,
    f.nonpayment_rate,
    f.rate_raw,
    COALESCE(f.suppressed, false),
    COALESCE(f.public_visible, false)
  FROM jsonb_to_recordset(facts) AS f(
    opeid text,
    school_id text,
    school_name_raw text,
    school_type text,
    state text,
    borrowers_in_denom integer,
    borrowers_raw text,
    nonpayment_rate numeric,
    rate_raw text,
    suppressed boolean,
    public_visible boolean
  );

  RETURN rid;
END;
$$;

REVOKE ALL ON FUNCTION public.apply_fsa_nonpayment_release(jsonb, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_fsa_nonpayment_release(jsonb, jsonb) TO service_role;

CREATE OR REPLACE VIEW public.fsa_nonpayment_current
WITH (security_invoker = true) AS
SELECT
  f.school_id,
  f.opeid,
  f.school_name_raw,
  f.school_type,
  f.state,
  f.borrowers_in_denom,
  f.nonpayment_rate,
  f.rate_raw,
  r.as_of_date,
  r.as_of_label,
  r.cohort_window_start,
  r.cohort_window_end,
  r.source_url,
  r.source_sha256,
  r.announcement_url,
  r.title
FROM public.fsa_nonpayment_facts f
JOIN public.fsa_releases r ON r.id = f.release_id
WHERE f.public_visible = true
  AND f.school_id IS NOT NULL
  AND r.id = (
    SELECT id
    FROM public.fsa_releases
    ORDER BY as_of_date DESC, downloaded_at DESC
    LIMIT 1
  );

COMMENT ON VIEW public.fsa_nonpayment_current IS
  'Latest FSA nonpayment vintage, one public row per matched school_id. Not the official cohort default rate.';

GRANT SELECT ON public.fsa_nonpayment_current TO anon, authenticated;
