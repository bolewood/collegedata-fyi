# Scorecard pipeline

The eighth and most-recent of the project's pipelines. Loads a curated
43-column subset of the federal [College Scorecard](https://collegescorecard.ed.gov/data/)
into `scorecard_summary`, joined to the CDS archive on IPEDS UNITID and
exposed via the public PostgREST API at `/rest/v1/cds_scorecard`.

The design rationale, the field-by-field selection, and the list of
deliberately-excluded Scorecard fields live in
[`docs/research/scorecard-summary-table-v2-plan.md`](../../docs/research/scorecard-summary-table-v2-plan.md).
The operational story (what's loaded, what's not, what to do about it)
is below.

## What's live right now

- **`scorecard_summary` — 6,322 rows** of Scorecard 2022-23 data, one per IPEDS UNITID. Every Title-IV institution.
- **`cds_documents.ipeds_id` — 3,794 of 4,131 rows** populated. The 130-row gap (~10 distinct school_ids) is from slug variants written by the discovery pipeline that don't match `schools.yaml` entries (e.g. `university-of-minnesota-twin-cities` not in YAML; `caltech` is, but the discovery slug is something else). See "Slug rationalization" below.
- **`cds_scorecard` view — joins live**. One row per CDS document with the Scorecard outcome slice attached. NULLs on the Scorecard side mean either the school has no IPEDS match (the 130 above) or the school dropped out of the federal Title-IV list.

## Files

- [`backfill_ipeds_ids.py`](./backfill_ipeds_ids.py) — one-shot fill of `cds_documents.ipeds_id` for rows inserted before the migration shipped. New rows pick up `ipeds_id` automatically via the archive edge functions (`_shared/archive.ts` reads it off `SchoolInput`).
- [`refresh_summary.py`](./refresh_summary.py) — annual upsert of `scorecard_summary` from the Scorecard Most-Recent Institution CSV. Schema-drift guard catches renamed columns; per-row dedup prevents `ON CONFLICT` failures; `--only-cds` scopes to schools we actually have CDS docs for.
- [`load_directory.py`](./load_directory.py) — PRD 015 M1. Refreshes `institution_directory` and `institution_slug_crosswalk` from the same Scorecard CSV. Applies the MVP in-scope filter (active, undergraduate-serving, two-or-four-year, degree-granting) and records `exclusion_reason` on out-of-scope rows. Preserves `schools.yaml` slugs where IPEDS IDs match; generates deterministic slugs for Scorecard-only rows with collision resolution `state → city → ipeds_id`. Writes a refresh summary to `scratch/scorecard/directory-refresh-<year>.json`.
- [`test_load_directory.py`](./test_load_directory.py) — unit tests for the loader's pure functions (slug determinism, collision tiers, schools.yaml preservation, in-scope filter, UNITID normalization, crosswalk construction).

## Migrations

Apply in order — the third depends on the first via `cds_manifest.ipeds_id`, and the fourth was added during initial load to adapt to the March 2026 Scorecard data dictionary.

| Migration | What it does |
|---|---|
| `20260420170000_ipeds_id.sql` | Adds `ipeds_id text` to `cds_documents`, indexes it, recreates the `cds_manifest` view to expose it. Header comment warns future authors that `cds_scorecard` now depends on `cds_manifest`. |
| `20260420170100_scorecard_summary.sql` | Creates `scorecard_summary` (43 columns, PK on `ipeds_id`, RLS-gated public read). |
| `20260420170200_cds_scorecard_view.sql` | Creates the joined `cds_scorecard` view with `WITH (security_invoker = true)`. |
| `20260420180000_scorecard_pell_remap.sql` | Drops `median_debt_non_pell` and `grad_rate_non_pell` (Scorecard removed the underlying CSV columns between the V2 plan and the March 2026 release). Recreates `cds_scorecard` without those fields. |
| `20260429113212_institution_directory.sql` | PRD 015 M1. Adds `institution_directory` (one row per Title-IV institution, with `in_scope` flag) and `institution_slug_crosswalk` (every alias for an institution → its canonical `school_id`). RLS-gated public read. Populated by `load_directory.py`. |

## First-time setup

Already done as of 2026-04-20. For posterity / re-setup elsewhere:

```bash
# 1. Apply migrations
supabase db push
# (or paste each SQL file into the Supabase SQL editor)

# 2. Backfill ipeds_id on existing cds_documents rows
#    Recommended: review the SQL first
python tools/scorecard/backfill_ipeds_ids.py > /tmp/backfill.sql
head -20 /tmp/backfill.sql       # sanity check
# Then either paste into Supabase SQL editor, OR:
python tools/scorecard/backfill_ipeds_ids.py --apply

# 3. Load the Scorecard CSV
unzip ~/Downloads/Most-Recent-Cohorts.zip -d /tmp/scorecard
python tools/scorecard/refresh_summary.py \
  --csv /tmp/scorecard/Most-Recent-Cohorts-Institution.csv \
  --data-year 2022-23
# Dry run prints the first row + total count. Re-run with --apply when satisfied.
python tools/scorecard/refresh_summary.py \
  --csv /tmp/scorecard/Most-Recent-Cohorts-Institution.csv \
  --data-year 2022-23 --apply
```

## Annual refresh

Scorecard releases a new Most-Recent-Cohorts bundle each fall (typically October). Run step 3 above with the new CSV and an updated `--data-year`.

The schema-drift guard fires loudly on any renamed/removed column, so the first symptom of a Scorecard schema change is a clean error from `refresh_summary.py` listing exactly which CSV columns are missing. When that happens:

1. Look the missing column up in the latest [data dictionary](https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx) — Scorecard publishes a deprecation note for renames.
2. Update `COLUMN_MAP` in `refresh_summary.py`.
3. If a column has no replacement (as happened with `GRAD_DEBT_MDN_NOPELL` in 2026), write a migration that drops the dead column from `scorecard_summary` AND recreates `cds_scorecard` without it. Use `20260420180000_scorecard_pell_remap.sql` as the template.

The same `--only-cds` flag scopes the upsert to just the IPEDS IDs referenced by `cds_documents`, which is faster but means new schools archived between refreshes won't get Scorecard data until the next full refresh.

## Querying the data

```bash
ANON=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...   # public anon key

# Top earners among CDS-archived schools
curl "https://api.collegedata.fyi/rest/v1/cds_scorecard?select=school_name,cds_year,earnings_10yr_median,graduation_rate_6yr,avg_net_price&earnings_10yr_median=not.is.null&extraction_status=eq.extracted&order=earnings_10yr_median.desc&limit=25" \
  -H "apikey: $ANON" -H "Authorization: Bearer $ANON"

# Net price by income bracket for one school
curl "https://api.collegedata.fyi/rest/v1/cds_scorecard?school_id=eq.harvard&select=school_name,net_price_0_30k,net_price_30k_48k,net_price_48k_75k,net_price_75k_110k,net_price_110k_plus&limit=1" \
  -H "apikey: $ANON" -H "Authorization: Bearer $ANON"

# Full Scorecard subset (all 6,322 institutions, not just CDS-archived ones)
curl "https://api.collegedata.fyi/rest/v1/scorecard_summary?ipeds_id=eq.166027&select=*" \
  -H "apikey: $ANON" -H "Authorization: Bearer $ANON"
```

`cds_year` in `cds_scorecard` is the canonical CDS year for the document; `scorecard_data_year` is the Scorecard vintage. They are not the same thing — Scorecard outcomes lag, currently 2022-23 data attached to every CDS year.

## Slug rationalization (130-row gap)

Ten `cds_documents.school_id` slugs don't match any `schools.yaml.id` and therefore got NULL `ipeds_id` from the backfill. They're slug variants from the discovery pipeline using IPEDS-official long names where `schools.yaml` uses canonical short forms:

| In `cds_documents.school_id` | In `schools.yaml.id` (canonical) | IPEDS |
|---|---|---|
| `georgia-institute-of-technology-main-campus` | `georgia-tech` | 139755 |
| `university-of-chicago` | `uchicago` | 144050 |
| `university-of-washington-seattle-campus` | `uw` | 236948 |
| `tulane-university` | `tulane-university-of-louisiana` | 160755 |
| `university-of-minnesota-twin-cities` | (not present, only branch campuses) | — |
| `caltech` | (not present under that exact slug) | 110404 |
| `virginia-tech` | (verify) | — |
| `rutgers-university-new-brunswick` | (verify) | — |
| `texas-a-and-m-university-college-station` | (only system office and branches) | — |
| `university-of-virginia-main-campus` | (verify) | — |

Two clean ways to fix:

1. **Add the variants to `schools.yaml`** as alternate ids pointing at the same IPEDS, then re-run `backfill_ipeds_ids.py --apply`. Idempotent — picks up only the still-NULL rows.
2. **Run a one-off `UPDATE cds_documents SET school_id = '<canonical>' WHERE school_id = '<variant>'`** to consolidate. More invasive (frontend URLs change for the affected schools).

Either way the Scorecard data already exists in `scorecard_summary` for these IPEDS — the join just doesn't fire until the slug crosswalk is reconciled.

## Schema-drift events (the running log)

Capture each Scorecard schema-rename event here so future-us doesn't relitigate:

- **2026-04-20 (March 2026 dictionary)**: Initial load. Three columns from the V2 plan turned out to be renamed or removed in the current dictionary:
  - `GRAD_DEBT_MDN_PELL` → renamed to `PELL_DEBT_MDN`. Remap-only; column kept in our table.
  - `GRAD_DEBT_MDN_NOPELL` → removed. Column dropped from `scorecard_summary` and `cds_scorecard` in `20260420180000_scorecard_pell_remap.sql`.
  - `C150_4_NONPELL` → removed (split into `C150_4_LOANNOPELL` + `C150_4_NOLOANNOPELL`, no clean weighted-average synthesis without per-cohort weights). Column dropped same migration.

## Requirements

```bash
pip install pandas supabase python-dotenv pyyaml
```

`.env` at repo root:

```
SUPABASE_URL=https://api.collegedata.fyi
SUPABASE_SERVICE_ROLE_KEY=...   # for --apply paths only; never check in
```
