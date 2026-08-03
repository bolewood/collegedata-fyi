# IPEDS coverage layer

PRD 021 adds a federal NCES/IPEDS baseline for schools that do not publish a
Common Data Set and for CDS schools where a source-labeled federal context row
is useful. The public UI reads curated facts, not raw IPEDS JSON.

As of the June 2026 backfill, the pipeline supports historical releases from
2004-05 through 2024-25. Current public facts are served through
`ipeds_current_facts`, a stable view backed by the materialized
`ipeds_current_facts_cache`; historical analysis should query `ipeds_facts`
with `ipeds_id`, `field_key`, and a bounded `data_year` range.

Install the IPEDS tool dependencies before downloading or applying a release:

```bash
python3 -m pip install -r tools/ipeds/requirements.txt
```

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

Install `mdbtools` for final releases and provisional releases whose mapped
table is available only in the official Access ZIP:

```bash
brew install mdbtools
python tools/ipeds/download_release.py \
  --collection-year 2024-25 \
  --release-type provisional \
  --tables F2324_F2 \
  --access-fallback
```

For preliminary and provisional releases, the downloader prefers data-generator
CSV ZIPs. `--access-fallback` exports mapped tables that return 404 from the CSV
endpoint. Final releases route directly to the official Access database because
the data-generator URL pins `HasRV=0` and can return stale provisional values.
Release-year and optional release-type selection are strict: a request that is
not on the official page exits instead of silently substituting another release.
The generated `release.json` records the actual release, source mode, downloaded
or Access-exported tables, and unresolved tables; unresolved Finance F2 tables
exit nonzero.

Finance Part H final releases may be Access-only. For example:

```bash
python tools/ipeds/download_release.py \
  --collection-year 2023-24 \
  --release-type final \
  --tables F2223_F2
```

The loader reads `release.json` so an Access-exported table keeps the official
Access bundle URL as table provenance rather than the data-generator URL that
returned 404.

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
   `main`, re-run with `--apply`. This requires `SUPABASE_URL`,
   `SUPABASE_SERVICE_ROLE_KEY`, and `IPEDS_ADMIN_DATABASE_URL` in `.env`.
   `IPEDS_ADMIN_DATABASE_URL` must be a direct PostgreSQL or Supavisor
   **session-mode** URI copied from the target project's database connection
   settings. Do not substitute a transaction-mode pooler URI.

```bash
python tools/ipeds/load_release.py ... --apply
```

The loader preflights the administrative session before writing. Normal release
metadata, raw-row, fact, pruning, and supersession writes continue through
PostgREST with the service role. Publication then uses the dedicated database
session, sets a 10-minute statement timeout, refreshes
`ipeds_current_facts_cache`, and finally refreshes browser source-mode flags.
The current-facts cache is required; browser source modes remain best-effort.
The loader prints `applied release ...` only after the required cache refresh
succeeds.

The split is intentional. The cache refresh scans millions of historical facts
and takes about 65–71 seconds in production. PostgREST's service-role requests
inherit the `authenticator` role's 8-second statement timeout, so the ordinary
API path cannot complete this administrative operation. There is no PostgREST
fallback for either post-load refresh: retrying the same known-short path would
only repeat the timeout. If an operator applies rows manually, run these
functions through a direct or session-mode database connection in this order:

```sql
select public.refresh_ipeds_current_facts_cache();
select public.refresh_ipeds_browser_source_modes();
```

### Apply failure and recovery semantics

- Missing, malformed, or unreachable `IPEDS_ADMIN_DATABASE_URL` fails the
  preflight before release writes begin. Connection errors identify the config
  name and safe error class/SQLSTATE only; the URI and password are never
  printed.
- A PostgREST write failure is a data-load failure. The loader does not print
  `release data writes completed` or `applied release`; correct the write error
  and rerun the exact command.
- If the required cache refresh fails after writes, the loader exits 4 and says
  `release data writes completed, but required publication failed`. It does not
  claim success. Correct the administrative session or timeout issue and rerun
  the exact `--apply` command. Upserts, stale-row pruning, release-priority
  checks, and supersession are idempotent at the same release/mapping scope.
- If only `refresh_ipeds_browser_source_modes()` fails, the loader warns after
  confirming that the current-facts cache was published, then completes. Rerun
  the function later through the same administrative session if browser badges
  need recovery.
- Dry runs do not connect to either Supabase path and do not require
  `IPEDS_ADMIN_DATABASE_URL`.

For a targeted backfill after adding table aliases, restrict projection to one
or more display groups:

```bash
python tools/ipeds/load_release.py ... --display-groups Costs --apply
```

Targeted reruns upsert table, column, and valueset metadata only for tables
loaded in that run, and existing release notes are merged. Re-pass
`--release-date-text` from that release's `release.json` on every dry run and
apply; the loader validates manifest provenance rather than accepting a release
type, metadata URL, or date text that contradicts the downloaded data.

## Endowment spike audit

The `Endowment` mapping group covers Finance Part H for all F2 filers: beginning
and ending endowment value, new gifts, investment return, spending distribution,
and other/residual change. `F2H03` is deliberately not mapped because it is the
calculated change `(F2H02 - F2H01)`. Component detail begins in fiscal year 2020.

Create the mappings and `analyze_endowment` script before running this spike;
otherwise `--display-groups Endowment` can vacuously produce zero facts. Download
the current FY2023 final release, then derive every loader provenance value from
the emitted manifest:

```bash
python -m tools.ipeds.download_release \
  --collection-year 2023-24 \
  --release-type final \
  --tables F2223_F2

RELEASE_MANIFEST="$(python3 - <<'PY'
import json
from pathlib import Path
matches = []
for path in Path("scratch/ipeds").glob("2023-24-*/release.json"):
    manifest = json.loads(path.read_text())
    if manifest.get("collection_year") == "2023-24" and manifest.get("release_type") == "final":
        matches.append(path)
if len(matches) != 1:
    raise SystemExit(f"expected one FY2023 final manifest, found {matches}")
print(matches[0])
PY
)"
RELEASE_DIR="$(dirname "$RELEASE_MANIFEST")"
METADATA_URL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["metadata_url"])' "$RELEASE_MANIFEST")"
METADATA_XLSX="$RELEASE_DIR/$(basename "$METADATA_URL")"
RELEASE_TYPE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["release_type"])' "$RELEASE_MANIFEST")"
RELEASE_DATE_TEXT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["release_date_text"])' "$RELEASE_MANIFEST")"

python -m tools.ipeds.load_release \
  --metadata-xlsx "$METADATA_XLSX" \
  --metadata-url "$METADATA_URL" \
  --data-dir "$RELEASE_DIR" \
  --collection-year 2023-24 \
  --data-year 2023 \
  --release-type "$RELEASE_TYPE" \
  --release-date-text "$RELEASE_DATE_TEXT" \
  --display-groups Endowment

python -m tools.ipeds.analyze_endowment \
  --data-dir "$RELEASE_DIR" \
  --unitids 201195,148131,231420,203580,152080 \
  --out scratch/ipeds/endowment-spike-analysis.json
```

The dry-run gate is `F2223_F2` under `source_tables_loaded` and a positive
`facts_by_group.Endowment` count. The analysis report records the corrected five
fixtures, source manifest metadata and SHA-256, FY2023 spending-sign tolerance,
the single accounting identity
`(F2H02 - F2H01) = F2H03A + F2H03B + F2H03C + F2H03D`, draw-rate distribution,
and blank Part H rows. The analyzer fails if `release.json` does not identify
exactly one Finance source, its recorded artifact is missing, or a requested
fixture UNITID is absent. Blank screener-A rows project to no facts; no synthetic
`not_applicable` facts are expected. Draw rate is `abs(F2H03C) / F2H01` with no
small-endowment floor; the volatility note belongs with any consumer of the
metric. The $5 million denominator floor applies only to the future
`other_change_share` metric.

### Phase 1 endowment release cycles

After the loader changes have merged and any required production setup is
applied from `main`, run one complete download, dry-run, review, analysis, and
apply cycle for each release. Phase 1 has no schema migration. The future Phase
2 `school_endowment_health` view is a migration and must be applied from `main`
after merge. Never apply from a feature branch.

| Fiscal year | Collection | F2 table | Selected release | Download option |
|---|---|---|---|---|
| 2020 | 2020-21 | `F1920_F2` | final | — |
| 2021 | 2021-22 | `F2021_F2` | final | — |
| 2022 | 2022-23 | `F2122_F2` | final | — |
| 2023 | 2023-24 | `F2223_F2` | final | direct Access route |
| 2024 | 2024-25 | `F2324_F2` | provisional | `--access-fallback` |

For each row, pass `--collection-year`, `--release-type`, `--tables`, and the
listed download option. Locate that row's `release.json` as above; take its
directory, `release_type`, `release_date_text`, and `metadata_url`; run
`load_release` without `--apply`; review both reports; then rerun the exact same
loader command with `--apply`. Include `--release-date-text` on the apply and on
every later rerun because the date text is required provenance and the loader
validates it against the manifest. Run the sign and identity analysis separately
for every release. FY2020 and FY2021 may have roughly 194 and 184 positive
`F2H03C` rows respectively; those are tolerance bands, so material divergence
triggers investigation rather than an automatic count-based failure.

An apply first upserts the replacement data, then prunes stale raw rows for each
loaded table and stale facts only for the selected mappings. This keeps a
targeted display-group rerun from deleting other mappings that share a source
table, while preventing corrected sources from leaving stale same-release
values behind. A higher-priority or revised same-priority release then marks
matching same-year fields from older releases non-public; selected field keys
come from the mappings, so an all-blank final field cannot fall back to an older
public value. The loader refuses to apply a lower-priority release after a
higher-priority one is present. It also rejects a competing same-priority
revision unless the incoming official release date is strictly newer than every
loaded peer. These read-only guards run before any write. The current-facts
cache publishes last and its refresh is required; the browser source-mode
refresh remains best-effort.

Post-load endowment reconciliation uses the raw College Scorecard institution
file (`Most-Recent-Cohorts-Institution_*.zip`), which carries both `ENDOWBEGIN`
and `ENDOWEND`; `scorecard_summary` persists only `endowment_end` and cannot run
this gate. Join the raw Scorecard rows to a bounded `ipeds_facts` export by
UNITID, scan candidate fiscal years over the full in-scope private-nonprofit
population, document the best alignment, and require at least 99% exact matches.
PostgREST requests must use the Supabase REST endpoint and both auth headers:

```bash
curl "$SUPABASE_URL/rest/v1/ipeds_facts?field_key=in.(endowment_value_begin,endowment_value_end)&data_year=gte.2020&data_year=lte.2024&select=unitid,data_year,field_key,value_numeric" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

Run the checked-in reconciliation command against the untouched Scorecard CSV
or ZIP. It loads `.env`, uses the anon key in both required headers, paginates
both PostgREST tables, and writes no database data:

```bash
python -m tools.ipeds.reconcile_endowment_scorecard \
  /path/to/Most-Recent-Cohorts-Institution_06102026.zip \
  --min-year 2020 \
  --max-year 2024 \
  --threshold 0.99 \
  --min-reporting-coverage 0.95 \
  --out scratch/ipeds/endowment-scorecard-reconciliation-06102026.json
```

The June 10, 2026 Scorecard file empirically aligns to FY2024. Of 1,110
in-scope private-nonprofit Scorecard rows with both values, 1,079 have a
complete F2 fact pair. Direct UNITID comparison matches 1,060. The remaining 19
are reporting-entity consolidations: 16 exact OPEID6 allocation rollups and two
unique exact beginning-and-ending residual matches reconcile; the Chicago
School remains visible and unreconciled because its Dallas branch has `NA`
Scorecard values. The reporting-entity gate is therefore 1,078/1,079 = 99.907%
(pass). The 31 in-scope rows without a complete F2 pair are reported separately,
not counted as independent F2 reporters, and leave 97.207% population coverage,
above the command's default 95% anti-sparsity floor. All five corrected fixtures
(201195, 148131, 231420, 203580, and 152080) match both values exactly.

The consolidation detail in the JSON report is deliberately auditable. Every
member UNITID, OPEID6, value pair, inclusion flag, and matching method is
listed. The tool never uses fuzzy names, never discards ambiguous residual
matches, and never promotes a Scorecard branch without direct F2 facts into the
reporting-entity denominator.

## Source discipline

- Metadata comes from the official IPEDS Tablesdoc workbook.
- Table data comes from official IPEDS data-generator CSV ZIPs or, for final and
  Access-only releases, tables exported from the official Access database ZIP.
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
