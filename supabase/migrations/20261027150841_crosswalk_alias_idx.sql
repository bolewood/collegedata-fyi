-- App lookups are WHERE alias = $1 (no is_primary predicate).
-- PK is (ipeds_id, alias); PG17 skip-scan works but is ~60x costlier
-- than a dedicated alias index. The partial primary_idx is unused
-- because callers never send is_primary = true.
CREATE INDEX IF NOT EXISTS institution_slug_crosswalk_alias_idx
  ON public.institution_slug_crosswalk (alias);
