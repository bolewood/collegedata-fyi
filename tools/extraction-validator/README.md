# extraction-validator

Three families of quality tooling for the extraction pipeline:

1. **Docling config bake-off** — `run_matrix.py` + `validate.py`. Historical: used to pick the Docling config that ships as Tier 4 baseline. See "Bake-off" section below. Preserved for future config tuning.
2. **Per-tier regression scorers** — `score_tier2.py` + `score_tier4.py`. Join cleaner/extractor output against hand-verified ground truth via an id_map and report per-field match. Exits non-zero on critical failures. Use as the gate before landing any change to an extractor.
3. **Corpus quality surveys** — `corpus_survey_tier4.py` + `inspect_tier4_doc.py`. Read-only tools that pull extraction artifacts from Supabase and report coverage distribution. Safe to run while the extraction worker is writing.

4. **Corpus scoreboard** — `scoreboard.py`. The current corpus-level measure of what the site serves: federal match on admissions, coverage, internal consistency and fix reach, by CDS year and source format. See "Corpus scoreboard" below.

Ground-truth YAMLs live in [`ground_truth/`](./ground_truth/), id_maps in [`id_maps/`](./id_maps/). Both are hand-built per school-year.

## Corpus scoreboard

```bash
tools/extraction_worker/.venv/bin/python tools/extraction-validator/scoreboard.py
tools/extraction_worker/.venv/bin/python tools/extraction-validator/scoreboard.py \
  --compare scratch/extraction-scoreboard/scoreboard-<earlier>.json   # deltas
```

Read-only. For each live, extracted document of 2023-24, 2024-25 and 2025-26 it measures the extraction the browser projection serves, not the newest artifact:

- Years the projection covers (2024-25 on) are read from `cds_fields` and `school_browser_rows`.
- Earlier years are read from `cds_artifacts`, picking the artifact with the projection's own ordering (`sort_base_candidates`). These reads fetch only the keys needed, run one at a time a few seconds apart, wait when the database host is short of memory, and are cached by artifact id in `scratch/extraction-scoreboard/cache/`, so a later run reads only what changed. Run one copy at a time.

Output: `scratch/extraction-scoreboard/scoreboard-<UTC>.json` (one record per document, for drill-down and deltas) and `.md`. Post the Markdown as a comment on [issue #431](https://github.com/bolewood/quadfile/issues/431) after every re-extraction batch or cleaner merge. `--from-json` re-renders a saved run; `--limit N` is a smoke test.

Federal figures come from `ipeds_facts` (the unified view keeps only each school's latest year). 2023-24 is not projected, so its figures are computed here the way the projection computes 2024-25; a school's year page shows the newest extraction, which section 4 compares with the projection's pick.

### Earlier years (staged; not run yet)

`--years` takes any canonical CDS year, in any order (the run lists them oldest first); a repeated or non-CDS year such as `unknown` is refused before any read. Years before 2023-24 are read from `cds_artifacts` the way 2023-24 is. Their forms have no full field schema, only a structural schema and a core-table overlay, so:

- Status counts, formats and **fields stored** are recorded and published as for any year.
- **No sum checks and no federal comparison.** `forms[year].sum_tables` is empty and `--public` lists `["B1","C1","H1"]` in `sum_checks_unavailable` (omitted for a year with checks), so the page can show a dash and a notice rather than a "can't check" count read as a result. The worker reads an older document into the 2025-26 ids by row label, and the overlays are not a mapping to trust for sums: 2019-20 and 2020-21 map only the men and women C1 rows (those forms have no C1 total row), 2021-22 maps one total and maps "total men who applied/admitted" onto the men rows, and 2022-23 leaves the another-gender rows unmapped (a school reporting that row would read "off by more" falsely). A verified per-year C1 mapping, with totals and another-gender rows, is what would turn the checks on.
- Admissions are "not compared" (`federal_compared` false, null outcomes). Public: `federal_left_out.not_compared` (omitted when 0), separate from `no_federal_figures`, which keeps meaning "IPEDS has no positive figure". For a year whose federal fall is loaded, `federal.reports + single_campus + no_federal_figures + not_compared` equals the published reports.
- `federal_fall_loaded` is decided at run time from `federal_schools[year]`: true when `ipeds_facts` holds any C1 figure for that fall (`tools/ipeds/README.md` lists releases 2004-05 to 2024-25; the oldest falls' keys are not assumed).
- `forms[year].field_count` is 0 and `schema_exists` false (public: `full_field_schema: false`, `questions: 0`): "no question list", not "no questions". The structural row and answer-cell counts do not reliably equal the full schemas' field counts (2023-24: 1,081 vs 1,053; 2025-26: 1,061 vs 1,105), so no number is shown.
- In the run JSON, `admissions` and `federal_values.ours` on a document with `federal_compared` false come from unverified ids: do not use them without checking `federal_compared`.
- B1 enrollment and G1 tuition candidates (`federal_extra`) have no field there (`cds_field` null).
- A year with a full field schema, including one with no `SUM_CHECKS` of its own such as 2026-27, behaves as before: sums follow the numbering each document carries.
- `renewal` is computed from the live manifest and does not depend on `--years`.

Run from the main checkout (`cd <main checkout>`). Precondition: it is on an up-to-date `main` that contains this change, and no extraction job is running there (this README does not switch branches for you). One copy at a time. First slice: 2022-23 alone, about 445 to 980 artifact reads, **30 to 70 minutes** (a sizing run; it is not publishable because `--public` needs 2023-24 to 2025-26 too):

```bash
cd <main checkout>
caffeinate -i tools/extraction_worker/.venv/bin/python tools/extraction-validator/scoreboard.py \
  --years 2022-23 \
  --artifact-interval 4.0 --field-interval 0.25 --min-free-mb 300 \
  --out-dir scratch/extraction-scoreboard 2>&1 | tee scratch/extraction-scoreboard/run-2022-23.log
```

Several earlier years together with the three current years (this run can go to `--public`). Live documents: 2019-20 453, 2020-21 456, 2021-22 472, 2022-23 495, 1,876 in all; about 1,690 are extracted, **an assumption** (90% of live, carried from #492; 2023-24 is 438 of 484). At 1.0 to 2.2 reads each and about 4.3 s a read that is about **2 to 4.5 hours**. All earlier years (4,407 live, about 3,970 extracted on the same assumption): 4,000 to 8,700 reads, **5 to 10 hours**. The cache is about 27 KB per read, 110 to 235 MB for everything. The projected current years add about 900 per-document `cds_fields` reads at 0.25 s (487 + 417 in the newest run); 2023-24 comes from artifacts, cached after the first run. About 10 minutes in all.

```bash
caffeinate -i tools/extraction_worker/.venv/bin/python tools/extraction-validator/scoreboard.py \
  --years 2019-20 2020-21 2021-22 2022-23 2023-24 2024-25 2025-26 \
  --artifact-interval 4.0 --field-interval 0.25 --min-free-mb 300 \
  --out-dir scratch/extraction-scoreboard 2>&1 | tee scratch/extraction-scoreboard/run-earlier-years.log
```

Add earlier years the same way. Never pass `--limit` for a run you mean to publish: `--public` refuses it.

If a run is interrupted (Ctrl-C, a stop for low memory, a dropped connection), run the same command again. Each artifact read is cached by id in `scratch/extraction-scoreboard/cache/`, so the second run re-reads only what was missing, plus the cheap index and `cds_fields` reads (a few minutes). No JSON is written until a run finishes. The run waits whenever the host has under `--min-free-mb` free; do not lower it.

`--public` on a run with earlier years writes `sum_checks_unavailable`, `federal_left_out.not_compared` and `questions: 0` for them. The page must show a dash and a notice for those tables, say admissions were not compared, and hide "The form has 0 questions", before such a snapshot is committed (follow-up in `web/`, not done here).

Guard holds are read from local worker `--summary-json` files (`scratch/extraction-drain/local/` by default), so that column is complete only on the machine that ran the re-extractions.

Tests: `python -m unittest discover -s tools/extraction-validator -p "test_*.py"`.

## Regression scoring (the gate)

Pipeline:

```
                                  ┌──────────────────────┐
                                  │ ground_truth/*.yaml  │
                                  │ id_maps/*.yaml       │
                                  └──────────┬───────────┘
                                             │
                                             ▼
  ┌────────────────┐   ┌───────────────────────────┐
  │ Tier 2 extract │──▶│ score_tier2.py            │──▶ per-field match, overall %
  │ (JSON)         │   │ joins on canonical q#     │
  └────────────────┘   └───────────────────────────┘

  ┌────────────────┐   ┌───────────────────────────┐
  │ Docling .md    │──▶│ score_tier4.py            │──▶ per-field match, overall %
  │                │   │ runs tier4_cleaner.clean()│
  │                │   │ then joins on canonical q#│
  └────────────────┘   └───────────────────────────┘
```

### Usage

```bash
# Tier 2 — Harvey Mudd (only school with Tier 2 AcroForm coverage in the GT set)
python tools/extraction-validator/score_tier2.py \
  --ground-truth tools/extraction-validator/ground_truth/harvey-mudd-2025-26.yaml \
  --tier2-extract /tmp/hmc_tier2.json \
  --id-map tools/extraction-validator/id_maps/harvey-mudd-2025-26.yaml

# Tier 4 — any of Harvard / Yale / Dartmouth 2024-25
python tools/extraction-validator/score_tier4.py \
  --ground-truth tools/extraction-validator/ground_truth/harvard-2024-25.yaml \
  --markdown tools/extraction-validator/runs/harvard-2024-25/baseline/output.md \
  --id-map tools/extraction-validator/id_maps/harvard-2024-25.yaml
```

### Current scores

| School | Tier | Overall | Critical |
|---|---|---|---|
| Harvey Mudd 2025-26 | 2 | 31/31 (100%) | — |
| Harvard 2024-25 | 4 | 32/32 (100%) | 10/10 |
| Dartmouth 2024-25 | 4 | 25/27 (92.6%) | 11/11 |
| Yale 2024-25 | 4 | 26/29 (89.7%) | n/a |

Remaining misses are all structural: Dartmouth C10 is a Docling flat-text emission, Yale H4/H6 are deferred Phase 2b scope. See [`docs/backlog.md`](../../docs/backlog.md) for follow-ups.

### Ground truth

Ground-truth values were transcribed directly from the source PDFs during the initial extraction-quality audit (see `docs/known-issues/`). Adding a new school:

1. Hand-verify ~25–30 fields against the PDF. Do **not** copy from a previous Docling run.
2. Pick a spread across B1 enrollment, B2 race/ethnicity, B3 degrees, C1 admissions (mark critical), C9 test scores, and any H section fields the PDF provides.
3. Save as `ground_truth/<school>-<year>.yaml`.
4. Build the `id_maps/<school>-<year>.yaml` by running the extractor against the PDF, matching expected values to the canonical question numbers in the output, and hand-disambiguating any that collide.
5. Run the appropriate scorer — it should pass every field that's in scope for the current cleaner. Fields that fail are either genuine cleaner gaps (opportunities) or mis-matched id_maps (fix the mapping).

## Corpus surveys

Once the extraction worker has drained a meaningful number of documents, the corpus survey shows how well the cleaner generalizes beyond the four hand-audited schools.

```bash
# Survey every tier4 artifact (read-only, safe during a worker run)
tools/extraction_worker/.venv/bin/python \
  tools/extraction-validator/corpus_survey_tier4.py

# Limit for a quick run
tools/extraction_worker/.venv/bin/python \
  tools/extraction-validator/corpus_survey_tier4.py --limit 100

# Inspect a specific low-coverage doc
tools/extraction_worker/.venv/bin/python \
  tools/extraction-validator/inspect_tier4_doc.py \
  --school california-polytechnic-state-university-san-luis-obispo \
  --year 2024-25 \
  --slice B2,C1
```

The survey output is a histogram of `fields_populated`, percentile summary, per-question-number coverage, and the 15 lowest-coverage docs. Use that last list as input to `inspect_tier4_doc.py` to see what's actually in the markdown.

The cleaner and the scorer are locked by the GT regression gate — the scorer must stay green before any cleaner change lands. The corpus survey is the improvement signal: it surfaces which fields + which schools still have coverage gaps, which are cleaner bugs vs Docling-rendering limits vs corpus data-quality issues.

## Bake-off (historical, preserved for config tuning)

Docling has several knobs (TableFormer FAST vs ACCURATE, `do_ocr`, `force_full_page_ocr`, OCR backend, image DPI, etc.) and the right combination is not obvious. The bake-off runs multiple configs against the same source PDFs and scores each run against ground truth.

1. A config YAML in [`configs/`](./configs/) describes Docling `PdfPipelineOptions`.
2. `run_matrix.py` runs Docling with each config on each PDF in [`pdfs/`](./pdfs/), writing markdown + json into `runs/<pdf_stem>/<config_name>/`.
3. `validate.py` loads a markdown output and a ground-truth file, tries to extract each value using the field's `capture` regex hint, and scores the run.
4. `run_matrix.py` prints a comparison table and writes `runs/summary.csv`.

Fields marked `critical: true` count double and are surfaced separately. The baseline config won the original bake-off (see [ADR 0006](../../docs/decisions/0006-tiered-extraction-strategy.md)) and is what `tier4_extractor.py` runs today.

```bash
pip install -r requirements.txt --break-system-packages
cp ~/Downloads/CDS-HMC-2025.2026_shared.pdf pdfs/harvey-mudd-2025-26.pdf
cp ~/Downloads/cds_yale_2024_2025.pdf pdfs/yale-2024-25.pdf
python run_matrix.py
```

Re-run when considering a config change (new Docling version, new knob, new OCR backend). Not part of the routine validation loop.

## Docling native-table spike

PRD 0111A uses two helper scripts to test whether Docling's native document/table
model contains recoverable C9/C11/C12 structure before adding a VLM repair path.

```bash
# Select low-coverage Tier 4 PDF fixtures and download the source PDFs.
tools/extraction_worker/.venv/bin/python \
  tools/extraction-validator/select_docling_spike_fixtures.py \
  --env .env.local \
  --limit 12 \
  --candidate-limit 300 \
  --min-year 2024-25 \
  --download

# Inspect native Docling JSON/tables and run the narrow C9 heuristic.
tools/extraction_worker/.venv/bin/python \
  tools/extraction-validator/inspect_docling_native.py \
  --manifest .context/docling-spike/fixtures/manifest.json \
  --config production-fast

# Compare full current Tier 4 cleaner output between two Docling runs.
tools/extraction_worker/.venv/bin/python \
  tools/extraction-validator/compare_docling_full_cleaner.py \
  --manifest .context/docling-spike/fixtures/manifest.json \
  --left-label production \
  --right-label docling-default \
  --left-dir .context/docling-spike/native-runs-production \
  --right-dir .context/docling-spike/native-runs-docling-default

# Compare markdown table parsing with native Docling JSON table-cell parsing.
tools/extraction_worker/.venv/bin/python \
  tools/extraction-validator/compare_docling_native_tables.py \
  --manifest .context/docling-spike/fixtures/manifest.json \
  --run-dir .context/docling-spike/native-runs-production \
  --table-source json
```

Run these with the extraction worker's lock-built venv (`tools/extraction_worker/.venv`, Python 3.12; see that README) so Docling matches production. Outputs are written under `.context/docling-spike/` by default (the scripts take `--out-dir` if you prefer `scratch/extraction-validator/`). They include
markdown, Docling JSON, per-table CSV/HTML/markdown exports, package versions,
table provenance, and `summary.json`.

When `--min-year` is used, fixture selection filters by `cds_year` first and
falls back to `detected_year` only when `cds_year` is missing. This keeps the
spike aligned with the 2024-25+ MVP scope without hiding metadata mismatches in
the source corpus.

This is a spike harness, not production extraction code. A successful native-table
candidate still needs CDS-specific validation before it can influence browser data.
The full-cleaner comparison is also not ground-truth scoring; it only compares
how the existing markdown cleaner behaves on two Docling markdown serializations.
The native-table comparison reuses the existing resolver logic but bypasses
`_parse_markdown_tables()`, feeding rows reconstructed from Docling JSON table
cells. Treat it as an adapter spike, not a production parser.

Available Docling spike configs:

| Config | Purpose |
|---|---|
| `production` / `production-fast` | Current Tier 4-like baseline: OCR on, table structure on, FAST tables, cell matching on. |
| `docling-default` | Unmodified installed Docling defaults. |
| `table-accurate` | One-variable change from production-fast: FAST tables to ACCURATE tables. |
| `ocr-off` | One-variable change: disable OCR for text PDFs. |
| `force-backend-text` | One-variable change: force embedded PDF text usage. |
| `no-cell-matching` | One-variable change: disable table cell matching. |
| `force-full-page-ocr` | One-variable change: OCR every page. |
| `layout-keep-empty-clusters` | One-variable change: retain empty layout clusters. |
| `layout-no-orphan-clusters` | One-variable change: disable orphan layout clusters. Current best screening result on the 2024-25+ fixture set. |
| `layout-skip-cell-assignment` | One-variable change: skip layout cell assignment. |
| `layout-no-orphan-table-accurate` | Combination arm: no orphan clusters plus ACCURATE tables. |
