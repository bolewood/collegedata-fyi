# extraction-validator

Three families of quality tooling for the extraction pipeline:

1. **Docling config bake-off** — `run_matrix.py` + `validate.py`. Historical: used to pick the Docling config that ships as Tier 4 baseline. See "Bake-off" section below. Preserved for future config tuning.
2. **Per-tier regression scorers** — `score_tier2.py` + `score_tier4.py`. Join cleaner/extractor output against hand-verified ground truth via an id_map and report per-field match. Exits non-zero on critical failures. Use as the gate before landing any change to an extractor.
3. **Corpus quality surveys** — `corpus_survey_tier4.py` + `inspect_tier4_doc.py`. Read-only tools that pull extraction artifacts from Supabase and report coverage distribution. Safe to run while the extraction worker is writing.

Ground-truth YAMLs live in [`ground_truth/`](./ground_truth/), id_maps in [`id_maps/`](./id_maps/). Both are hand-built per school-year.

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
/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/select_docling_spike_fixtures.py \
  --env .env.local \
  --limit 12 \
  --candidate-limit 300 \
  --min-year 2024-25 \
  --download

# Inspect native Docling JSON/tables and run the narrow C9 heuristic.
/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/inspect_docling_native.py \
  --manifest .context/docling-spike/fixtures/manifest.json \
  --config production-fast

# Compare full current Tier 4 cleaner output between two Docling runs.
/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/compare_docling_full_cleaner.py \
  --manifest .context/docling-spike/fixtures/manifest.json \
  --left-label production \
  --right-label docling-default \
  --left-dir .context/docling-spike/native-runs-production \
  --right-dir .context/docling-spike/native-runs-docling-default
```

Outputs are written under `.context/docling-spike/` by default. They include
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
