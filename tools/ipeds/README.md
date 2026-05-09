# IPEDS coverage layer

PRD 021 adds a federal NCES/IPEDS baseline for schools that do not publish a
Common Data Set and for CDS schools where a source-labeled federal context row
is useful. The public UI reads curated facts, not raw IPEDS JSON.

## Workflow

1. Download the official NCES metadata workbook and mapped CSV table ZIPs:

```bash
python tools/ipeds/download_release.py
```

2. Dry-run the loader. This parses metadata, reads the ZIPs, projects public
facts, and writes `scratch/ipeds/ipeds-<year>-<release>-report.json`.

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

## Source discipline

- Metadata comes from the official IPEDS Tablesdoc workbook.
- Table data comes from the official IPEDS data-generator CSV ZIP endpoints.
- The Access database ZIP is recorded as release provenance but not parsed.
- Raw rows are preserved in `ipeds_raw_rows`; public products query
  `ipeds_facts`, `ipeds_current_facts`, or `school_facts_unified`.

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

## Public defaults

- Public school pages show facts from `school_facts_unified`, which only joins
  `institution_directory.in_scope = true`.
- Imputed values remain visible but labeled.
- Imputed values should not feed rankings, editorial claims, or change
  intelligence unless a future PRD explicitly opts in.
- Baseline-only pages are marked `noindex` until the methodology and QA surface
  mature.
