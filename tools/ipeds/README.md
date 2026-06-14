# IPEDS coverage layer

PRD 021 adds a federal NCES/IPEDS baseline for schools that do not publish a
Common Data Set and for CDS schools where a source-labeled federal context row
is useful. The public UI reads curated facts, not raw IPEDS JSON.

As of the June 2026 backfill, the pipeline supports historical releases from
2004-05 through 2024-25. Current public facts are served through
`ipeds_current_facts`, a stable view backed by the materialized
`ipeds_current_facts_cache`; historical analysis should query `ipeds_facts`
with `ipeds_id`, `field_key`, and a bounded `data_year` range.

## Workflow

Run IPEDS loads from a fresh `main` checkout after the corresponding migrations
have landed and been applied. Feature-branch loads can put production ahead of
the committed schema.

1. Download the official NCES metadata workbook and mapped CSV table ZIPs. The
   downloader writes into `scratch/ipeds/<collection-year>-<release-type>/` and
   creates a `release.json` manifest with normalized release-date metadata and
   source URLs.

```bash
python tools/ipeds/download_release.py
```

For historical releases where the NCES data-generator CSV ZIP endpoint no
longer serves mapped tables, install `mdbtools` and export the missing tables
from the official Access ZIP:

```bash
brew install mdbtools
python tools/ipeds/download_release.py --collection-year 2019-20 --data-year 2019 --access-fallback
```

The downloader still prefers data-generator CSV ZIPs. `--access-fallback` only
exports mapped tables that are present in the release metadata but return 404
from the CSV endpoint.

2. Dry-run the loader. This parses metadata, reads the ZIPs, projects public
   facts, and writes `scratch/ipeds/ipeds-<year>-<release>-report.json`. Review
   row counts, missing tables, projected fact counts, and any schema-drift notes
   before applying.

```bash
python tools/ipeds/load_release.py \
  --metadata-xlsx scratch/ipeds/2024-25-provisional/IPEDS202425Tablesdoc.xlsx \
  --data-dir scratch/ipeds/2024-25-provisional \
  --collection-year 2024-25 \
  --data-year 2024 \
  --release-type provisional \
  --release-date 2026-03-01 \
  --release-date-text "March 2026" \
  --metadata-url https://nces.ed.gov/ipeds/tablefiles/tableDocs/IPEDS202425Tablesdoc.xlsx
```

3. After reviewing the report and after the migration has landed/applied from
   `main`, re-run with `--apply`. This requires `SUPABASE_URL` and
   `SUPABASE_SERVICE_ROLE_KEY` in `.env`.

```bash
python tools/ipeds/load_release.py ... --apply
```

The loader refreshes `ipeds_current_facts_cache` after fact upserts, then
refreshes browser source-mode flags that depend on current facts. If an
operator applies rows manually, run these RPCs with service-role credentials in
the same order:

```sql
select public.refresh_ipeds_current_facts_cache();
select public.refresh_ipeds_browser_source_modes();
```

For a targeted backfill after adding table aliases, restrict projection to one
or more display groups:

```bash
python tools/ipeds/load_release.py ... --display-groups Costs --apply
```

## Source discipline

- Metadata comes from the official IPEDS Tablesdoc workbook.
- Table data comes from the official IPEDS data-generator CSV ZIP endpoints.
- The Access database ZIP is recorded as release provenance but not parsed.
- Raw rows are preserved in `ipeds_raw_rows`; public products query
  `ipeds_facts`, `ipeds_current_facts`, or `school_facts_unified`.
  `ipeds_current_facts` is a stable view backed by the materialized
  `ipeds_current_facts_cache` serving surface.
- `release_date` is normalized to ISO form. Month-level NCES dates such as
  `March 2026` are stored as the first day of the month with
  `release_date_precision = "month"` in notes.
- Provisional/final status, source table, source variable, imputation status,
  and CDS-definition alignment must stay attached to every public fact.

## Release probe

The monthly GitHub Actions workflow `.github/workflows/ipeds-release-probe.yml`
checks the official NCES Access Database page for the next bundle. It no-ops
until 10 months after the latest loaded provisional Access release date, then
looks for both:

- the final release for the current collection year, and
- the provisional release for the next collection year.

For the `2024-25 provisional` Access release dated `March 2026`, the first
automatic due date is `2027-01-01`. When NCES publishes a matching release, the
workflow opens a GitHub issue with the exact download and dry-run commands.

Manual dry run:

```bash
python tools/ipeds/probe_releases.py --as-of 2027-01-01
```

Manual forced probe before the due date:

```bash
python tools/ipeds/probe_releases.py --force --out-json scratch/ipeds/probe-summary.json
```

Required GitHub Actions secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

The workflow uses `GITHUB_TOKEN` to create issues and does not mutate IPEDS
tables. Issue creation is idempotent by title:
`ipeds_release_available: <collection_year> <release_type>`.

## Applying a release issue

When the probe opens a release-available issue:

1. Run the suggested `download_release.py` command.
2. Run the suggested `load_release.py` command without `--apply`.
3. Review the generated report under `scratch/ipeds/`.
4. If migrations are needed for schema drift, ship/apply those first from
   `main`.
5. Re-run the same loader command with `--apply`.
6. Confirm the probe now sees the release as loaded:

```bash
python tools/ipeds/probe_releases.py --as-of "$(date +%F)"
```

7. Spot-check the public serving view with the public anon key:

```bash
curl "$SUPABASE_URL/rest/v1/school_facts_unified?school_id=eq.goshen-college&select=school_name,field_label,display_value,release_type,collection_year,source_table,source_variable&limit=5" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

The probe should mark the target release as `loaded`, and school pages should
read the new current facts through `school_facts_unified`.

## Public query performance

`ipeds_facts` is a long-form historical table. Public queries should use the
same keys as the serving indexes:

- Prefer `ipeds_id` over raw `unitid`. `ipeds_id` is the public, zero-padded
  UNITID text key used by `institution_directory`, `school_facts_unified`, and
  the index-backed historical query path.
- Include `field_key` for analytical reads.
- Include `data_year` or a narrow `data_year` range when reading history.
- Use `school_facts_unified` for current school-page display and
  `ipeds_current_facts` for latest-per-school fact reads. Both avoid
  recomputing the latest-release window over the full historical table.

Fast historical example:

```bash
curl "$SUPABASE_URL/rest/v1/ipeds_facts?ipeds_id=eq.110635&field_key=in.(retention_rate_full_time,graduation_rate_6yr)&data_year=gte.2019&data_year=lte.2024&select=ipeds_id,data_year,field_key,value_numeric,source_table,source_variable&order=data_year.asc" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

## Public defaults

- Public school pages show facts from `school_facts_unified`, which only joins
  `institution_directory.in_scope = true`.
- Imputed values remain visible but labeled.
- Imputed values should not feed rankings, editorial claims, or change
  intelligence unless a future PRD explicitly opts in.
- Baseline-only pages are marked `noindex` until the methodology and QA surface
  mature.

## Verification

Before shipping loader or probe changes:

```bash
python3 -m unittest discover -s tools/ipeds -p 'test_*.py'
git diff --check
```

For frontend changes that render IPEDS facts, also run the web typecheck/build
from `web/` and smoke the affected school page.
