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

## Public defaults

- Public school pages show facts from `school_facts_unified`, which only joins
  `institution_directory.in_scope = true`.
- Imputed values remain visible but labeled.
- Imputed values should not feed rankings, editorial claims, or change
  intelligence unless a future PRD explicitly opts in.
- Baseline-only pages are marked `noindex` until the methodology and QA surface
  mature.

