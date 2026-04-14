# extraction-validator

A small harness for deciding which Docling configuration we should run in production.

## Why this exists

Docling has several knobs (TableFormer FAST vs ACCURATE, `do_ocr`, `force_full_page_ocr`, OCR backend, image DPI, etc.) and the right combination is not obvious. We do not want to pick one based on vibes. This harness runs multiple Docling configs against the same source PDFs and scores each run against a hand-verified ground-truth file.

## How it works

1. A **ground-truth YAML** captures ~30 values we read from the source PDF with our own eyes — things like "Yale B1 full-time first-year men = 782".
2. A **config YAML** describes Docling `PdfPipelineOptions`.
3. `run_matrix.py` runs Docling with each config on each PDF, writing markdown + json into `runs/<pdf_stem>/<config_name>/`.
4. `validate.py` loads a markdown output and a ground-truth file, tries to extract each value using the field's `extract` hint (regex or literal), and scores the run.
5. `run_matrix.py` prints a comparison table and writes `runs/summary.csv`.

Fields marked `critical: true` count double and are surfaced separately. Harvey Mudd's C1 applicants/admits cells are the critical set — those are the Docling regression we are specifically trying to fix.

## Ground truth

Ground-truth values for Yale 2024-25 and Harvey Mudd 2025-26 were transcribed directly from the source PDFs during the initial extraction-quality audit (see `docs/known-issues/`). If you add a new school, hand-verify every field against the PDF — do not copy from a previous Docling run.

## Usage

```bash
# Install
pip install -r requirements.txt --break-system-packages

# Put source PDFs under ./pdfs/
cp ~/Downloads/CDS-HMC-2025.2026_shared.pdf pdfs/harvey-mudd-2025-26.pdf
cp ~/Downloads/cds_yale_2024_2025.pdf pdfs/yale-2024-25.pdf

# Run the full matrix
python run_matrix.py

# Or validate an already-extracted markdown file
python validate.py \
  --ground-truth ground_truth/harvey-mudd-2025-26.yaml \
  --markdown runs/harvey-mudd-2025-26/baseline/output.md
```

## Output

```
                    baseline  tf-accurate  ocr-tesseract  combined
yale-2024-25         28/30       29/30         27/30         29/30
harvey-mudd-2025-26  18/30 *     24/30 *       26/30         28/30 *

(* = at least one critical field still wrong)
```

The config with the best HMC score that also holds Yale at >= baseline wins. That choice gets written up as ADR 0006.
