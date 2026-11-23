# Extraction Quality

*Current measure: the [extraction scoreboard](#corpus-scoreboard-the-current-measure), from November 23, 2026. Benchmark tables: historical, May 5, 2026 snapshot. Repair log: updated November 9, 2026.*

> **How to read the dates.** The summary table, tier tables, and ground-truth scores below were measured in April and May 2026 and have not been re-run since. They are a dated snapshot, not current counts. For current coverage use [`/coverage`](https://collegedata.fyi/coverage); for pipeline health use [`/pipeline-observation`](https://collegedata.fyi/pipeline-observation). The August 6, 2026 data-integrity audit ([`docs/plans/audit-2026-08-06-final/`](plans/audit-2026-08-06-final/README.md)) counted 6,322 directory institutions, 4,071 archived CDS documents, 262,537 `cds_fields` rows, and 558 `school_browser_rows`; that audit is the later, broader measurement and its counts supersede the May figures. What changed in extraction between June and November 2026 is in [June to November 2026 repairs](#june-to-november-2026-repairs).

## Corpus scoreboard (the current measure)

One script measures what the site serves, across the corpus, and is re-run after every re-extraction batch or cleaner change:

```bash
tools/extraction_worker/.venv/bin/python tools/extraction-validator/scoreboard.py

# with the changes since an earlier run
tools/extraction_worker/.venv/bin/python tools/extraction-validator/scoreboard.py \
  --compare scratch/extraction-scoreboard/scoreboard-<earlier>.json
```

For every live, extracted document of CDS years 2023-24, 2024-25 and 2025-26 it takes the extraction the browser projection serves (not the newest artifact) and reports, by year and source format:

1. **Federal match on admissions.** C1 applied, admitted and enrolled against IPEDS for the same fall: within 2%, blank, or present but different.
2. **Coverage.** Median and 10th-percentile field count per served extraction.
3. **Internal consistency.** The sums the form defines (B1 totals, C1 by sex against the total, H1 grant and self-help totals): pass, fail, not checkable.
4. **Fix reach.** Served extractions on the current cleaner version and on each older one, documents a worker guard is holding, and documents hidden behind a quality flag.

The baseline (November 23, 2026) and every later run are posted as comments on [issue #431, "Extraction scoreboard"](https://github.com/bolewood/collegedata-fyi/issues/431). A cleaner change states which of these numbers it expects to move. The script is read-only, paces its reads, and writes its output to `scratch/extraction-scoreboard/`. Guard holds come from the worker run summaries on the machine that ran the re-extraction, so that column is complete only there.

**Everything below this section is historical**: the summary, tier tables and ground-truth scores were measured in April and May 2026 and are kept as a record, not as current numbers.

This document records extraction accuracy across our pipeline as of that snapshot. It's meant as an honest, calibrated self-assessment, not a marketing page. The numbers here are produced by reproducible scorers you can run yourself against our ground-truth fixtures in [`tools/extraction-validator/`](../tools/extraction-validator/).

We report two different kinds of number, because they measure different things:

1. **Ground-truth scores** on hand-audited schools. Tells us how well our extractors perform when we can verify every field against a trusted reference.
2. **Corpus-wide coverage** across all extracted documents. Tells us what percentage of the 1,105-field canonical schema is populated on average across the whole library, without per-school hand tuning.

The gap between the two is where the real work is.

## Summary (historical: May 5, 2026 snapshot)

| Measure | Value (May 5, 2026) |
|---|---|
| Institutions indexed | 6,322 Scorecard directory rows; 2,924 public in-scope coverage rows |
| Archived CDS documents | 3,950 |
| Documents with structured extraction | 3,792 (96.0%); 35 pending, 110 failed, 13 not applicable |
| Documents by source format | 3,390 `pdf_flat` · 362 `xlsx` · 127 `pdf_fillable` · 20 `pdf_scanned` · 9 `html` · 11 `docx` |
| Ground-truth score, hand-audited schools (average) | 94% |
| Benchmark-school coverage, C1 admissions section (Tier 4) | Launch benchmark 50-60%; C21/C22 early-plan coverage materially improved in PRD 016B |
| Benchmark-school coverage, 1,105-field schema (3-doc Tier 4 avg, post-Phase 6) | ~35-40% baseline; subsequent targeted resolvers improve product-critical sections rather than claiming full-schema parity |
| Tier 4 v0.3 layout-overlay spike, 10-doc failure sample | 5,066 -> 5,602 fields (+536) |
| Public long-form field substrate | 200,957 `cds_fields` rows |
| Public browser serving rows | 475 `school_browser_rows` rows |
| Public merit-profile rows | 383 `school_merit_profile` rows |
| PRD 019 admissions/reporting spike | 85 schools with pairable 2024-25/2025-26 primary rows; 392 candidate events, 282 clean comparable events, 31 reporting-status candidates requiring review |
| PRD 019 calibration dry-run | 30-school subset, 4 latest/prior pairable schools, 36 generated events, 2 major, 11 notable, 4 human-review candidates |
| PRD 010 launch -> PRD 012 refresh, `cds_fields` | 113,836 -> 217,910 field rows (+104,074, +91.4%) |
| PRD 012 SAT/ACT browser answerability | SAT median 67.2% primary clean · ACT 75th 66.1% primary clean |
| Tier 1 XLSX field coverage (median per doc) | 521 fields in the current `2024+` projection (~47% of schema) |
| Tier 1 XLSX field coverage (max per doc) | 782 fields (~71% of schema) |
| 2025-26 extraction freshness | 118 archived 2025-26 rows: 101 extracted, 16 failed, 1 not applicable, 0 pending after the May 3 manual fresh-year drain |

## Pipeline tiers

The extraction pipeline routes each document to a tier based on its source format.

| Tier | Input shape | Extractor | Status | Notes |
|---|---|---|---|---|
| 1 | Filled XLSX | Template/embedded answer-column cell map + openpyxl | ✅ Shipped 2026-04-20; hardened 2026-05-03 | Parses the CDS Excel template's hidden lookup columns once; applies the map to any filled workbook. Falls back to workbook-native Question Number / Answer columns when the standard template map produces near-zero fields. Deterministic on standard or embedded-answer layouts. |
| 2 | Fillable PDF with AcroForm fields | `pypdf.get_fields()` | ✅ Shipped | Deterministic. Fields read directly from the PDF's form metadata. |
| 3 | Filled DOCX | OOXML SDT reader + measured Docling fallback | 📄 [PRD 007](prd/007-tier3-docx-extraction.md) | Word template has 1,204 Structured Document Tags whose `w:tag` values match schema `word_tag` exactly. SDT-preserving DOCX should be deterministic; Docling fallback is planned for SDT-stripped Word tables. The probe/worker now correctly route DOCX bytes to `source_format='docx'` instead of false-positive XLSX. Extractor not yet built. |
| 4 | Flattened PDF (most common) | Docling layout extraction + schema-targeting cleaner | ✅ Shipped | The hardest tier. Most of this document is about Tier 4. [PRD 005](prd/005-full-schema-extraction.md) Phase 6 shipped 2026-04-20: section-family resolvers took the cleaner from 72 -> ~380 fields (Harvard 382, Yale 390, Dartmouth 343). Tier 4 v0.3 adds a deterministic embedded-text layout overlay. PRD 016B added C21/C22 early decision/action extraction and quality checks; PRD 018 added H1/H2/H2A merit/aid improvements for the school-page merit profile. |
| 5 | Image-only scan | Tier 4 with `force_ocr=True` | ✅ Shipped 2026-04-20 | Same Docling pipeline, swaps in `EasyOcrOptions(force_full_page_ocr=True)`. Kennesaw State 2023-24 went from 0 fields (default lazy OCR) to 172 fields (force OCR) on 31 scanned pages. |
| 6 | Structured HTML | `html_to_markdown` (BeautifulSoup + lxml) → `tier4_cleaner.clean` | ✅ Shipped 2026-04-20 | HTML normalizer + reuse of the Tier 4 cleaner. Archived HTML bytes are served as `text/plain` from the public Storage bucket to prevent XSS. MIT 2024-25 reference: 152 of 1,105 schema fields populated on first-drain without an alias table. See [PRD 008](prd/008-html-extraction.md). |

## Tier 1: filled XLSX (deterministic)

When a school publishes their CDS as a filled Excel workbook, extraction is deterministic via the template's own lookup structure. The CDS Initiative's Excel template has hidden columns on each section tab (`AA` = question number, `AC` = formula pointing at the answer cell) that assemble every canonical field into one flat list. Most filled files strip the Answer Sheet tab but preserve the data cells at their original positions, so we parse the template once to build a `{question_number: (sheet, cell)}` map and apply it to any filled workbook.

| Metric | Value |
|---|---|
| Artifacts produced | 362 |
| Median fields populated per doc | 521 in the current `2024+` projection (~47% of schema); older full-corpus median was 307 |
| Max fields populated (well-filled school) | 782 (~71% of schema) |
| Accuracy on standard template | Deterministic (cell-position read, no heuristics) |

The median is pulled down by schools that use older templates or partial fills.
PRD 014 M3 added year-aware schema/template dispatch for 2024-25 and 2025-26,
and 2026-27 was added in November 2026:
2025-26 and 2026-27 use the hidden AA/AC lookup columns, while 2024-25 uses the
reduced section-tab layout with question numbers in column A and answer cells in
column C. XLSX files from before 2023-24 still fall back to the 2025-26 schema
until older canonical mappings exist. A 2026-27 file built on the 2025-26
workbook or fillable PDF is detected and read with the 2025-26 schema.

PR #44 added an embedded answer-column fallback. Some school-published
workbooks preserve their own `Question Number` / `Answer` columns even when
they do not match the official template's cell positions. If the template map
yields fewer than 25 populated fields, Tier 1 scans each worksheet for
workbook-native question/answer columns and uses that map only when it recovers
more fields. This is still deterministic; it is a second cell-map source, not
fuzzy layout parsing.

## Tier 2: fillable PDFs (deterministic)

When a school publishes their CDS as an unflattened fillable PDF, extraction is trivial and perfect. The PDF stores field values keyed by AcroForm names, and we read them directly.

| School | CDS Year | Score |
|---|---|---|
| Harvey Mudd | 2025-26 | 31/31 (100%) |

A meaningful minority of schools publish fillable PDFs (136 artifacts at the May 2026 snapshot; the summary table's 127 `pdf_fillable` documents is a separate count that was not reconciled with it). For those, Tier 2 is the preferred path because it produces ground-truth-quality output with zero heuristics.

## Tier 4: flattened PDFs (the hard case)

Most schools publish their CDS as a flattened PDF. We run Docling over the PDF to produce structured markdown, then apply a schema-targeting cleaner ([`tools/extraction_worker/tier4_cleaner.py`](../tools/extraction_worker/tier4_cleaner.py)) that maps cleaned markdown back to the canonical CDS field IDs.

### Ground-truth scores (historical: post-Phase 6, April 2026)

Hand-audited against full ground-truth fixtures for three schools:

| School | CDS Year | Overall | Critical Fields |
|---|---|---|---|
| Harvard | 2024-25 | 32/32 (100%) | 10/10 |
| Dartmouth | 2024-25 | 25/27 (92.6%) | 11/11 |
| Yale | 2024-25 | 26/29 (89.7%) | n/a |

Average across the three schools: ~94%. These are schools with clean, well-structured CDS documents. Remaining misses are structural: Dartmouth's C10 is a Docling flat-text emission, Yale's H4/H6 are deferred to a later phase of the cleaner.

### Layout-overlay cleaner spike and production refresh (April 27-28, 2026)

PRD 0111A's Docling spike found that the biggest immediate gain was not an LLM repair pass. It was retaining Docling's tuned markdown/native-table path and adding a deterministic supplemental text overlay from `pypdf` layout extraction for the places where Docling loses row/column context.

The v0.3 cleaner still treats Docling/native table output as the primary substrate. The supplemental layout text is gap-fill only: it targets known CDS section shapes, writes canonical fields only when the source text pattern is deterministic, and leaves ambiguous or blank cells empty. There is no confidence scoring and no invented data.

The spike was audited page-by-page on Farmingdale State College, then run autonomously on Kenyon and Michigan State. Against the same ten low-coverage Tier 4 fixture PDFs, the deterministic cleaner improved from 5,066 recovered fields after the Farmingdale pass to 5,602 after the Kenyon/Michigan State generalization pass.

| PDF fixture | Before | After v0.3 | Delta |
|---|---:|---:|---:|
| DeSales University 2024-25 | 428 | 504 | +76 |
| Dominican University 2025-26 | 532 | 587 | +55 |
| Dominican University of California 2024-25 | 610 | 624 | +14 |
| Emory 2024-25 | 506 | 564 | +58 |
| Farmingdale State College 2024-25 | 631 | 635 | +4 |
| Franklin and Marshall College 2024-25 | 527 | 568 | +41 |
| Gettysburg College 2024-25 | 540 | 574 | +34 |
| Kenyon 2024-25 | 402 | 479 | +77 |
| Lafayette College 2025-26 | 554 | 581 | +27 |
| Michigan State University 2024-25 | 336 | 486 | +150 |
| **Total** | **5,066** | **5,602** | **+536** |

The largest generalized wins were A-section contact/header fields, B5 graduation-rate grids, D transfer fields, E/F checkbox grids, G expense rows, H financial-aid tables, and J discipline rows. The Michigan State pass is the clearest evidence that the fixes generalized beyond the school being actively inspected: it moved from 336 to 486 fields while preserving the existing fixture counts elsewhere.

Important limits:

- Field count is a coverage screen, not semantic ground truth.
- The overlay is optimized for 2024-25+ CDS layouts; older templates remain best-effort.
- Some cells are intentionally left blank when the visible source cell is blank or when alignment is ambiguous.
- PRD 014 M3 makes Tier 4's `SchemaIndex` year-aware, but the hand-coded
  phrase matcher remains 2025-26-keyed until the follow-on M6 schema-derived
  phrase matcher.

The production browser projection was refreshed on April 28 after the v0.3 drain.
For the `2024+` selected-result scope, the public substrate now contains:

| Measure | PRD 010 launch | PRD 012 refresh | Delta |
|---|---:|---:|---:|
| `cds_fields` rows | 113,836 | 217,910 | +104,074 (+91.4%) |
| `school_browser_rows` rows | 472 | 469 | -3 stale rows |
| Processed documents | 507 | 503 | -4 stale/non-qualifying rows |
| Mean field rows per processed document | 224.5 | 433.2 | +208.7 (+93.0%) |

Within the refreshed `2024+` field substrate:

| Source format | Field rows |
|---|---:|
| `pdf_flat` | 141,554 |
| `pdf_fillable` | 53,016 |
| `xlsx` | 23,082 |
| `html` | 152 |
| `pdf_scanned` | 106 |

Documents with at least one projected field now average `477.9` fields, median
`544`, max `802`. That is still coverage, not accuracy: field count does not prove
each value is correct. But it is a strong signal that the deterministic v0.3
overlay moved the flattened-PDF corpus from sparse extraction to useful browser
substrate.

PRD 012 also turned the improved C9 coverage into a measured backend expansion:

| Browser metric | Field | Primary clean coverage | pdf_flat coverage |
|---|---|---:|---:|
| SAT submit rate | `C.901` | 65.4% | 67.2% |
| ACT submit rate | `C.902` | 58.1% | 57.3% |
| SAT Composite 50th | `C.906` | 67.2% | 71.9% |
| ACT Composite 75th | `C.916` | 66.1% | 71.2% |

Those fields are now queryable through the browser backend, with companion
submit-rate metadata. GPA and class-rank remain long-form only because scale and
denominator semantics need a better UI before becoming first-class browser filters.

### Product-surface targeted cleanup (May 2-3, 2026)

PRD 016B and PRD 018 deliberately improved product-critical sections instead
of claiming full-schema completion:

- **Admission strategy:** Tier 4 now reads C21 early decision and C22 early
  action fields, including ED applicants/admitted, second-deadline hints,
  EA/restrictive-EA flags, wait-list counts, selected C7 factor rows, and
  application-fee fields. `school_browser_rows` stores effective flags and
  `admission_strategy_card_quality` so the frontend can suppress or caveat
  inconsistent rows instead of making the card look more certain than the
  source permits.
- **Merit profile:** Tier 4 now handles more H1/H2/H2A layouts, including
  non-need institutional scholarship/grant rows used by
  `school_merit_profile`. The public view is explicitly school-reported CDS
  Section H data plus Scorecard affordability/outcome context; it is not a
  personalized merit-aid estimator.
- **Fresh-year drain:** The worker now prioritizes rows by
  `detected_year/cds_year` recency and `discovered_at` before older backlog
  rows. Manual drains can also use `--min-year-start` and the GitHub Actions
  ops workflow exposes `min_year_start`, so newly published 2025-26 files clear
  before stale historical PDFs.
- **Source routing:** ZIP bytes are now inspected internally before routing:
  XLSX requires workbook content and DOCX requires `word/document.xml`.
  Headless/archiver downloads also preserve document-like response bytes even
  when hosting headers are misleading. This fixed DOCX-as-XLSX failures and
  reduced false failures from WAF/interstitial handling.

### PRD 019 change-intelligence spike and QA (May 5, 2026)

PRD 019 is not an extractor by itself. It is a downstream quality consumer that
tests whether extracted data is stable enough to support year-over-year change
events. The spike and first calibration pass are therefore useful extraction QA:
they show both real signal and where false deltas can be fabricated by producer
or quality drift.

The pre-PRD admissions/reporting spike compared five high-leverage field groups
over schools with both 2024-25 and 2025-26 primary rows. It found:

- 85 schools with pairable primary rows.
- 392 candidate events.
- 282 clean comparable events after gating out provenance/quality noise.
- 31 reporting-status candidates requiring human review.

The first deterministic projector calibration run used the 30-school PRD 019
subset and produced:

- 4 pairable latest/prior schools in the current calibration subset.
- 36 generated events: 2 major, 11 notable, 23 watch.
- 4 human-review candidates.

The important QA outcome is the gate design, not the raw event count. `major`
events and `newly_missing` events are candidates until a human checks the source
PDFs. Producer changes, source-provenance crossings, and document-quality
regressions are explicit event types or severity caps, not silent inputs to a
"school stopped reporting" claim.

### Corpus-wide coverage by section (historical: April 2026, three documents)

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

Some schools (notably Kent State's 8 campuses) publish their CDS as a filled Word document. The CDS Word template ships with 1,204 Structured Document Tags whose `w:tag` values match schema `word_tag` values exactly — the same deterministic-lookup pattern as Tier 2. A school that fills the template without stripping structure preserves all 1,204 tags; Kent State's 2025-26 CDS has 769 populated out of 804 in the filled file. [PRD 007](prd/007-tier3-docx-extraction.md) covers the revised build plan: direct OOXML SDT extraction first, then a measured Docling DOCX fallback for SDT-stripped Word tables.

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

The corpus-level measure is [`scoreboard.py`](../tools/extraction-validator/scoreboard.py) (see [Corpus scoreboard](#corpus-scoreboard-the-current-measure)). A Tier 4 re-clean survey is available via [`corpus_survey_tier4.py`](../tools/extraction-validator/corpus_survey_tier4.py).

## June to November 2026 repairs

These are the extraction-quality changes that shipped after the May snapshot, taken from merged PRs. They are grouped by what they fix; none of them comes with a new accuracy figure here. Re-run the scorers (below) before quoting a number.

**Field-level fixes (cleaner and parsers)**

- **C1 totals.** 2025-26 residency rows were zipped All-first, so the in-state cell overwrote the total (Wabash showed 911 applicants instead of 2,496). Rows are now mapped by header, totals smaller than a gender component are restored, and the same guard runs in KeyStats and `school_browser_rows` (#160). A second pass fixed 2025-26 C1 enrolled-by-sex totals that took the full-time row (#248).
- **B1 sex ratios.** The 2024-25 B1 gender mapping showed wrong sex ratios (#168); the table parser also missed total undergraduate men/women stored under a differently named cohort, and missing "All" totals are now derived from full-time plus part-time (#169, `b1_derive_totals.py`).
- **Doubled text-layer cells.** Flattened-form PDFs that print every value twice made Docling read "113 113" and dropped whole tables. Doubled cells are collapsed when they dominate a document (#248).
- **D2 transfer table.** The 2024-25 year-page layout read four cells per row from a five-cell layout; the numbering is now detected from the values (#233). The official 2021-22 and 2022-23 templates were archived from Wayback in the same change.
- **Older-form numbering for policy and date tables.** Since a document is cleaned under its own year's schema, values that the Tier 4 resolvers number by the 2025-26 form landed on other questions in 2023-24 and 2024-25 documents. Of 290 published 2024-25 PDF extractions, 141 had "X" in H.901 (the priority filing date), 153 a bare month in C.1402 (the application closing date), 172 a bare month in D.909, 201 the retention rate under B.2203 (no such field there) and 95 a per-credit charge on the G6 "PUBLIC INSTITUTIONS" heading. One table in `tier4_cleaner.py` now moves each of these claims to the older forms' field: B22, C13, C14, C16, C17, C22, D9, D22, E1/E3 "Other", F3, G6, H7, H9, H10 and H11. D2 is numbered by form year where it is read, and its table reader no longer takes the Women column for a second Men column. A month and a day become one date ("3/15"); a 2025-26 field with no counterpart (the "a date is given" boxes) is dropped. The table hold-back counts a date field as holding its month and day within its own table, so the change is not read as a lost table (#421). Not fixed here: the D9 reader takes a row's first date as the closing date and its second as the notification date, whichever columns they sit in.
- **H15 spill.** A free-text financial-aid answer ran into Sections I and J and got full 500-600 field documents hidden as low coverage. The cutoff is whitespace-tolerant and the hide threshold is now under 300 fields (#243).
- **H14 merit versus need.** `school_merit_profile` combined non-need (H.1401) and need-based (H.1411) academic criteria; they are now separate columns and the card uses the non-need flag (#249).

**Year detection, flags, and source selection**

- **KU-style year detection and blank templates.** Years are detected on section-title Factbook layouts, still under ADR 0007's rule that zero or multiple distinct years returns no year. Blank-template documents are hidden from public listings, and a school-page note appears when extraction used a schema fallback (#235).
- **Low-field flag on every tier.** Documents below the low-field threshold are flagged whatever tier produced them (#242, with archive fixes for section-split and wiki-hosted schools).
- **Flattened-reprint guard.** When a school republishes a fillable PDF as a flattened copy and the form values still appear in the new file's text, the worker keeps Tier 2 extraction from the fillable source. Decisions are recorded in `notes.source_selection` (#258). [PRD 038](prd/038-template-overlay-extraction.md) plans a template-overlay approach for flattened fillable PDFs (#259, docs only).
- **Section-file protection.** Archive refreshes that would replace a full CDS with a section file are held (#257).

**Environment and run safety**

- **Pinned Docling and regression hold-back.** The requirements said `docling>=2.0`, so CI and a local venv ran different builds (Sacramento State 2023-24: 274 versus 108 fields). Docling and its companions are pinned exactly, Docling versions are recorded in each artifact, and a Tier 4 re-extraction that keeps under 60% of the previous artifact's fields is held back as `tier4_field_regression` (#244).
- **Ten-field hold-back.** The 60% rule let smaller losses through. Of 135 documents re-extracted on a Mac on 2026-11-21 (same Docling; 112 of them were last extracted on the GitHub runner), seven ended 13 to 41 fields lower and were written (Concordia Texas 2014-15: 222 to 181). A Tier 4 re-extraction that ends 10 or more fields below the previous artifact of the same file under the same schema is now held as `tier4_field_regression`, whatever the document's size. The count is the net one: 31 of the 135 no longer had 10 or more of their old fields, and 15 of those 31 ended level or higher. `--accept-field-loss` (workflow input `accept_field_loss`) writes the new result anyway, for documents named one by one; a cleaner fix that removes ten or more wrong values from one document needs it.
- **Headline hold-back.** A re-extraction of the same file can gain fields overall and still lose the admissions rows: Docling 2.148.0 dropped the C1 tables by sex from SMU and Wentworth 2025-26. A Tier 4 re-extraction is held back as `tier4_headline_field_regression` when two or more headline C1 fields (applied, admitted and enrolled totals and their rows for men and women) that the previous extraction of the same file read are missing and their numbers are nowhere in the newly converted text. A number that is still in the text and merely no longer assigned is the cleaner declining a value, and is not held. The previous extraction keeps being served and the document shows as a failure in the run summary. `--accept-headline-loss` (workflow input `accept_headline_loss`) writes the new one anyway, and only for documents named with `--document-ids` or `--requeue-document-ids`. Only the Docling markdown is searched, not the PDF layout or OCR text, so a fix that stops accepting a value read only from those is held too; and the enrolled rows rarely trip the guard because section B repeats those numbers.
- **Table hold-back.** The net count hides a lost table. On 2026-11-22 a re-extraction of 2023-24 flat PDFs took 199 documents from 56,938 to 66,301 values in all, yet 28 of the 191 that were rewritten lost most of one table: all 30 values of H2 at Colorado (505 to 512 fields overall), all of I1 at Clemson and Florida A&M, H1 at eight schools. Their previous extractions dated from April 2026, were converted by a Docling older than the pinned one, were cleaned under the 2025-26 schema whatever their year, and recorded no source file, so neither existing hold-back compared them. A Tier 4 re-extraction is now held as `tier4_table_field_regression` when a table loses 5 or more numbers and over half of what it had. A number counts as lost only when no field in the same section of the new extraction still holds it (each new field accounts for one old one), which makes the check indifferent to renumbering between form years; zeros and ticks are ignored and section A is not compared. On that day's documents the rule holds all 28, none of the eight losses checked by hand and found to be corrections, and 52 of the 206 not yet re-extracted. It cannot tell a real loss from the removal of wrong numbers, so a held document still needs a look. `--accept-table-loss` (workflow input `accept_table_loss`) writes the new result anyway, for documents named one by one.
- **Collapse hold-back, every tier.** The Tier 4 hold-backs compare re-extractions of one PDF. Northern Michigan's CDS is archived both as a PDF and as an .xlsx, and its current source is the workbook; on 2026-11-22 a re-extraction routed to Tier 1 replaced 229 fields with 8 for 2023-24 and 568 with 124 for 2024-25, with nothing comparing the two. Any extraction, from any tier and any source file, that would become the served one and ends under half the field count of the extraction being served (when that one has 50 or more) is now held as `<tier>_field_regression`. "Served" is the browser projection's own choice, which ranks Tier 1 over Tier 2 over Tier 6 over Tier 4 before it looks at recency, so the check uses that ordering and not the newest artifact; a result that would be stored but not served is written. The ranking uses the document's own year, as the projection does, so a workbook read under another year's form does not count as served over an extraction under the document's year. Two limits: values the projection merges in from an LLM-fallback artifact are not counted, and Tier 2 counts unticked boxes as fields, so its counts run higher than the other tiers'. A held result leaves the document's recorded source format as it was. `--accept-field-loss` writes it anyway.
- **Lock file.** `requirements.lock` pins all packages for Python 3.12 and `dependency_check.py` makes the worker exit on drift (#245).
- **In-place requeue.** `--requeue-document-ids` re-extracts without flipping documents to `extraction_pending`, so pages do not go blank during a redrain (#246).
- **pdfium text fallback.** pypdf raised on some font descriptors, the format sniff counted zero text, and text PDFs were force-OCR'd (Grinnell 2023-24: 411 to 122 fields). `pdf_text.py` falls back to pdfium for the pages pypdf cannot read (#256).
- **Wayback bytes.** Archive.org toolbar URLs return HTML; the fetch now injects the `id_` flag and rejects truncated 1 MB captures (#164).

**Visibility**

- **Extraction activity ledger.** A private append-only ledger records each run and item, and `/pipeline-observation` shows the last 14 days of extraction finishes without exposing document IDs or hashes (#177).

The cumulative list with dates is in [`CHANGELOG.md`](../CHANGELOG.md) from 0.1.0.0 (2026-08-03). Earlier history is in git.

## Where future work goes

Most of the structural work is shipped. What's left is either opportunistic coverage expansion or the one remaining tier.

- **[PRD 005: Full-schema extraction](prd/005-full-schema-extraction.md)** — ✅ Phase 6 shipped 2026-04-20. Section-family resolvers took the Tier 4 cleaner from 72 -> ~380 fields. PRD 016B and PRD 018 continued that pattern for high-value C21/C22 and H1/H2/H2A surfaces. Continuing to add resolvers for thinner sections is opportunistic work, triggered by specific school gaps.
- **[PRD 006: LLM fallback](prd/006-llm-fallback.md)** — ✅ Shipped 2026-04-20. Schema-aware Claude Haiku pass for structural-failure modes the deterministic cleaner can't recover. 244 2024-25 docs backfilled with mean 28.2 fields added per doc beyond the pre-Phase-6 cleaner baseline. Cache keyed on source+markdown+prompt sha so re-runs cost $0. See [`docs/tier4-llm-fallback.md`](tier4-llm-fallback.md) for the operator runbook.
- **[PRD 007: Tier 3 DOCX extraction](prd/007-tier3-docx-extraction.md)** — the only remaining tier. Ships the SDT-based DOCX reader first, then evaluates Docling as a fallback for SDT-stripped Word tables. Unlocks Kent State's campus family (14 docs, SDT-preserving) and other structured-DOCX publications. Addressable corpus today is ~30-50 documents.

Quality improvements fall into three categories, roughly in priority order:

1. **DOCX Tier 3.** The extractor is now the only missing tier. The probe/worker route DOCX correctly; the SDT reader still needs to ship.
2. **Failed-row triage by root cause.** Remaining failures are mostly DOCX not implemented, publisher pages that return auth/WAF/interstitial HTML instead of source bytes, malformed/empty publisher files, and a small set of low/zero-field extracts that need school-specific inspection.
3. **Better upstream extraction** on flattened PDFs. Evaluating commercial document-extraction APIs against our ground-truth fixtures. A meaningful quality jump here would unlock most of the sections currently below 30% fill rate.
4. **Template overlay for flattened fillable PDFs** ([PRD 038](prd/038-template-overlay-extraction.md)). Approved for M0-M3; docs only so far.
5. **Community cleaners** for school-specific and template-specific variants. The [`cleaners.yaml`](../cleaners.yaml) registry is built for this; see [`CONTRIBUTING.md`](../CONTRIBUTING.md).

Contributions that directly advance any of these categories are especially welcome.
