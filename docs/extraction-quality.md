# Extraction Quality

*Last updated: April 2026 (post-drain: 2026-04-20)*

This document records current extraction accuracy across our pipeline. It's meant as an honest, calibrated self-assessment, not a marketing page. The numbers here are produced by reproducible scorers you can run yourself against our ground-truth fixtures in [`tools/extraction-validator/`](../tools/extraction-validator/).

We report two different kinds of number, because they measure different things:

1. **Ground-truth scores** on hand-audited schools. Tells us how well our extractors perform when we can verify every field against a trusted reference.
2. **Corpus-wide coverage** across all extracted documents. Tells us what percentage of the 1,105-field canonical schema is populated on average across the whole library, without per-school hand tuning.

The gap between the two is where the real work is.

## Summary

| Measure | Value |
|---|---|
| Schools indexed | 723 |
| Archived CDS documents | 4,131 |
| Documents with structured extraction | 4,042 (98%) |
| Extraction artifacts by tier | 3,545 Tier 4+5 · 362 Tier 1 · 136 Tier 2 |
| Ground-truth score, hand-audited schools (average) | 94% |
| Corpus-wide coverage, C1 admissions section (Tier 4) | 50-60% |
| Corpus-wide coverage, 1,105-field schema (Tier 4 average) | ~35-40% |
| Tier 1 XLSX field coverage (median per doc) | 307 fields (~28% of schema) |
| Tier 1 XLSX field coverage (max per doc) | 782 fields (~71% of schema) |

## Pipeline tiers

The extraction pipeline routes each document to a tier based on its source format.

| Tier | Input shape | Extractor | Status | Notes |
|---|---|---|---|---|
| 1 | Filled XLSX | Template cell-position map + openpyxl | ✅ Shipped 2026-04-20 | Parses the CDS Excel template's hidden lookup columns once; applies the map to any filled workbook. Deterministic on the standard template layout. 289 artifacts, median 307 fields/doc. |
| 2 | Fillable PDF with AcroForm fields | `pypdf.get_fields()` | ✅ Shipped | Deterministic. Fields read directly from the PDF's form metadata. |
| 3 | Filled DOCX | `python-docx` SDT reader | 📄 [PRD 007](prd/007-tier3-docx-extraction.md) | Word template has 1,204 Structured Document Tags whose `w:tag` values match schema `word_tag` exactly. ~30-50 addressable docs today (Kent State's 14 SDT-preserving files are the largest family). Not yet built. |
| 4 | Flattened PDF (most common) | Docling layout extraction + schema-targeting cleaner | ✅ Shipped | The hardest tier. Most of this document is about Tier 4. Full-schema expansion planned in [PRD 005](prd/005-full-schema-extraction.md). |
| 5 | Image-only scan | Tier 4 with `force_ocr=True` | ✅ Shipped 2026-04-20 | Same Docling pipeline, swaps in `EasyOcrOptions(force_full_page_ocr=True)`. Kennesaw State 2023-24 went from 0 fields (default lazy OCR) to 172 fields (force OCR) on 31 scanned pages. |

## Tier 1: filled XLSX (deterministic)

When a school publishes their CDS as a filled Excel workbook, extraction is deterministic via the template's own lookup structure. The CDS Initiative's Excel template has hidden columns on each section tab (`AA` = question number, `AC` = formula pointing at the answer cell) that assemble every canonical field into one flat list. Most filled files strip the Answer Sheet tab but preserve the data cells at their original positions, so we parse the template once to build a `{question_number: (sheet, cell)}` map and apply it to any filled workbook.

| Metric | Value |
|---|---|
| Artifacts produced | 362 |
| Median fields populated per doc | 307 (~28% of schema) |
| Max fields populated (well-filled school) | 782 (~71% of schema) |
| Accuracy on standard template | Deterministic (cell-position read, no heuristics) |

The median is pulled down by schools that use older templates (the cell map is minted from the 2025-26 template) or partial fills. Shipping per-year templates would close the older-year gap.

## Tier 2: fillable PDFs (deterministic)

When a school publishes their CDS as an unflattened fillable PDF, extraction is trivial and perfect. The PDF stores field values keyed by AcroForm names, and we read them directly.

| School | CDS Year | Score |
|---|---|---|
| Harvey Mudd | 2025-26 | 31/31 (100%) |

A meaningful minority of schools publish fillable PDFs (136 artifacts in the current corpus). For those, Tier 2 is the preferred path because it produces ground-truth-quality output with zero heuristics.

## Tier 4: flattened PDFs (the hard case)

Most schools publish their CDS as a flattened PDF. We run Docling over the PDF to produce structured markdown, then apply a schema-targeting cleaner ([`tools/extraction_worker/tier4_cleaner.py`](../tools/extraction_worker/tier4_cleaner.py)) that maps cleaned markdown back to the canonical CDS field IDs.

### Ground-truth scores (post-Phase 6, April 2026)

Hand-audited against full ground-truth fixtures for three schools:

| School | CDS Year | Overall | Critical Fields |
|---|---|---|---|
| Harvard | 2024-25 | 32/32 (100%) | 10/10 |
| Dartmouth | 2024-25 | 25/27 (92.6%) | 11/11 |
| Yale | 2024-25 | 26/29 (89.7%) | n/a |

Average across the three schools: ~94%. These are schools with clean, well-structured CDS documents. Remaining misses are structural: Dartmouth's C10 is a Docling flat-text emission, Yale's H4/H6 are deferred to a later phase of the cleaner.

### Corpus-wide coverage by section

The single-digit averages mask wide section-to-section variance. These numbers are from the three-document benchmark (Harvard, Yale, Dartmouth 2024-25), post-Phase 6 expansion of the cleaner from 72 to ~380 fields:

| Section | Fill Rate | Shape |
|---|---:|---|
| B4 (Grad rate current) | 100% | Letter-row grid |
| B5 (Grad rate previous) | 100% | Letter-row grid |
| B2 (Race/ethnicity) | 87.8% | Clean 3-column matrix |
| I (Faculty + class size) | 86.4% | I1 letter-row grid + I3 size buckets |
| C7 (Basis for selection) | 84.2% | Checkmark-in-column |
| B3 (Degrees conferred) | 70.4% | Small table |
| C10 (Class rank) | 66.7% | Simple 2-col table |
| F (Student life) | 62.6% | Checkbox scan + F1 percentages |
| B1 (Enrollment) | 60.7% | Matrix with context tracking |
| C1 (Applications) | 56.7% | Gender rows + residency split |
| E (Academic offerings) | 52.9% | Checkbox scan |
| B22 (Retention) | 33.3% | Inline regex; only the percent field covered |
| C2 (Wait list) | 28.6% | YesNo fields deferred |
| H (Financial aid) | 24.8% | H1/H2/H2A/H4 only |
| G (Annual expenses) | 18.8% | G1 only; G5 fragmented |
| C9 (Test scores) | 15.7% | Percentiles covered; policies not |
| J (Disciplines by CIP code) | 13.9% | Most schools only fill one column |
| C13-C22 (Admissions policies) | ≤13% | Dates, YesNo, checkboxes interleaved |
| C11 (GPA profile) | 11.1% | Format highly school-dependent |
| A (General info) | 9.0% | Only degree checkboxes |
| D (Transfer) | 1.5% | Docling flattens D2 to paragraphs |
| C5 (Carnegie units) | 0% | Most test schools don't fill it |
| C3, C4, C6, C8 | 0% | Single YesNo or checkbox fields |

The pattern is consistent: sections rendered as rectangular tables with stable headers extract well. Sections that Docling flattens into paragraphs, rows that get merged, and sections dominated by single YesNo or checkbox fields all degrade sharply.

### Known failure modes

See [`docs/research/tier4-cleaner-learnings-for-llm-fallback.md`](research/tier4-cleaner-learnings-for-llm-fallback.md) for the detailed failure-mode catalog. In summary:

- **Table to paragraphs.** Docling sometimes flattens a table into an ordered list of labels and values with no structural markers. The deterministic parser cannot recover positional context.
- **Row merge.** Two consecutive rows collapse into one table row, leaving a single value array ambiguously associated with either source row.
- **Header promoted to data.** Header cells containing digits get treated as data, leaving the nominal header empty.
- **Header and column concatenation.** Multi-row headers collapse, losing the column meanings.
- **School-specific layout variants.** Community college templates, pre-2020 terminology, wrapped cells, and custom cover pages fall outside our in-tree cleaner's coverage.

## Tier 5: scanned PDFs (force-OCR Docling)

When a school publishes their CDS as an image-only scan (no extractable text layer), Tier 5 routes it through the same Docling pipeline as Tier 4 but with `force_full_page_ocr=True` — every page goes through EasyOCR before layout analysis and cleaning. Docling's default "auto" OCR heuristic doesn't reliably trigger on scanned CDS PDFs in the corpus, hence the force-mode requirement.

| School | CDS Year | Default lazy OCR | Force OCR |
|---|---|---|---|
| Kennesaw State | 2023-24 | 0 fields, 14 chars | 172 fields, 104,890 chars |

OCR quality is variable and generally below the native-text Tier 4 baseline — OCR-derived text introduces character noise that the cleaner's substring matching tolerates unevenly. For documents that have any populated text layer, Tier 4's default config is always preferred.

## Tier 3: filled DOCX (not yet built)

Some schools (notably Kent State's 8 campuses) publish their CDS as a filled Word document. The CDS Word template ships with 1,204 Structured Document Tags whose `w:tag` values match schema `word_tag` values exactly — the same deterministic-lookup pattern as Tier 2. A school that fills the template without stripping structure preserves all 1,204 tags; Kent State's 2025-26 CDS has 769 populated out of 804 in the filled file. [PRD 007](prd/007-tier3-docx-extraction.md) covers the build plan.

## How to run the scorers yourself

Every number in this document is reproducible. Ground-truth fixtures and id-map files live in [`tools/extraction-validator/`](../tools/extraction-validator/). Example:

```bash
# Score Tier 2 (fillable PDF) — Harvey Mudd
python tools/extraction-validator/score_tier2.py \
  --ground-truth tools/extraction-validator/ground_truth/harvey-mudd-2025-26.yaml \
  --tier2-extract /tmp/hmc_tier2.json \
  --id-map tools/extraction-validator/id_maps/harvey-mudd-2025-26.yaml

# Score Tier 4 (flattened PDF) — Harvard
python tools/extraction-validator/score_tier4.py \
  --ground-truth tools/extraction-validator/ground_truth/harvard-2024-25.yaml \
  --markdown tools/extraction-validator/runs/harvard-2024-25/baseline/output.md \
  --id-map tools/extraction-validator/id_maps/harvard-2024-25.yaml
```

Corpus-wide surveys are available via [`corpus_survey_tier4.py`](../tools/extraction-validator/corpus_survey_tier4.py).

## Where future work goes

The cleaner has pushed deterministic extraction about as far as the Docling output will permit on the hard sections. Three active workstreams move the quality needle:

- **[PRD 005: Full-schema extraction](prd/005-full-schema-extraction.md)** — expand the Tier 4 cleaner from 72 to full 1,105-field coverage via a section-family resolver framework backed by a shared `SchemaIndex`. Rev 2 incorporates measured schema ambiguity and phases the work by section cleanliness, starting with the cleanest sections (J disciplines, B2 race/ethnicity).
- **[PRD 006: LLM fallback](prd/006-llm-fallback.md)** — schema-aware LLM pass for the failure modes the deterministic cleaner cannot recover. Evaluates alternative extraction backends for the initial PDF-to-structured step.
- **[PRD 007: Tier 3 DOCX extraction](prd/007-tier3-docx-extraction.md)** — ship the SDT-based DOCX reader. Unlocks Kent State's campus family and other SDT-preserving publications.

Quality improvements fall into three categories, roughly in priority order:

1. **Better upstream extraction** on flattened PDFs. Evaluating commercial document-extraction APIs against our ground-truth fixtures. A meaningful quality jump here would unlock most of the sections currently below 30% fill rate.
2. **LLM fallback** for the structural failure modes the deterministic cleaner cannot recover. Prompts designed against the failure-mode catalog.
3. **Community cleaners** for school-specific and template-specific variants. The [`cleaners.yaml`](../cleaners.yaml) registry is built for this; see [`CONTRIBUTING.md`](../CONTRIBUTING.md).

Contributions that directly advance any of these categories are especially welcome.
