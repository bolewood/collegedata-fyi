# PRD 038: Template overlay extraction for flattened official CDS PDFs

**Status:** Approved for M0–M3 (revised after adversarial review; decisions recorded 2026-11-09; amended the same day after a second review — see [Amendments](#amendments-2026-11-09-second-review), which override §5, §6 and Decisions 1–4 where they conflict; M1 was reviewed independently and fixed — see [A8](#a8-m1-findings-2026-11-10), which overrides §2, §3 and §4 where they conflict; the verification round is in [A9](#a9-m1-verification-round-2026-11-10), which overrides A8 and §2-§4 where they conflict; the third round, which adds emission classes and the stop rule, is in [A10](#a10-m1-round-3-emission-classes-and-the-stop-rule-2026-11-10) and overrides A9 where they conflict; Lane 2 and sub-point registration are in [A11](#a11-m2-lane-2-numeric-ocr-and-sub-point-registration-2026-11-12), which overrides the Lane 2 sketch in §3; the M2 fix round is in [A12](#a12-m2-fix-round-ocr-class-second-model-gate-and-a-withdrawn-claim-2026-11-12), which overrides A11 where they conflict; the M3 build, which adds the worker entry point, the shadow artifact and the switched-off merge, is in [A13](#a13-m3-build-worker-entry-point-shadow-artifact-and-a-merge-that-is-switched-off-2026-11-12), which refines A1-A7 where it says so; the M3 fix round, with the write-time hold facts, `--rehold`, the single-writer contract and the page-kind metadata, is in [A14](#a14-m3-fix-round-write-time-hold-facts-rehold-the-single-writer-contract-and-page-kind-2026-11-12), which overrides A13 where they conflict; the serving change, with the default served set, vector-page OCR and the `overlay_producer_version` column, is in [A15](#a15-serving-change-2026-11-13), which overrides A13 and A14 where they conflict)
**Created:** 2026-11-09
**Author:** Antigravity; revised by Claude
**Related:** [ADR 0006 — Tiered extraction strategy](../decisions/0006-tiered-extraction-strategy.md), [ADR 0007 — Year authority moves to extraction](../decisions/0007-year-authority-moves-to-extraction.md), [PRD 005 — Full schema extraction](005-full-schema-extraction.md), [PRD 006 — LLM fallback](006-llm-fallback.md), [PRD 0111A — Docling improvement spike](0111A-docling-improvement-spike.md), PR #258 (flattened reprint source guard, merged as v0.6.19.13)

---

## Summary

The CDS Initiative ships a 50-page fillable PDF template each year. When a school fills it in and keeps the form fields, Tier 2 (`tier2_acroform`) reads exact values. When the school flattens or prints it to PDF, the form fields are gone. The worker then routes it to Tier 4 (`tier4_docling`), which recovers about half as many fields on these files.

The page layout of a flattened official template is still the template's layout. Every value sits at a known widget rectangle. Template overlay extraction finds which template pages a document contains, then reads each widget rectangle in one of three ways:

- from the PDF text layer;
- by OCR of the rendered crop, when the values were drawn as vector paths;
- by ink density, for checkboxes.

It writes a new producer, `tier2_template_overlay`, as a `kind='cleaned'` supplement artifact (Amendment A1).

All numbers below were measured on 2026-11-09 against production (read-only) and source PDFs from the `sources` bucket. See [How measured](#how-measured).

## Problem

### Selected extraction results by producer

Metric: `notes.stats.schema_fields_populated` of the artifact selected by `cds_selected_extraction_result`. Year: `coalesce(detected_year, cds_year)`.

| Year | Producer | Docs | Median fields | Mean |
|---|---|---:|---:|---:|
| 2025-26 | `tier1_xlsx` | 40 | 674 | 635.8 |
| 2025-26 | `tier2_acroform` | 60 | 674.5 | 667.8 |
| 2025-26 | `tier4_docling` | 179 | 503 | 457.2 |
| 2024-25 | `tier2_acroform` | 83 | 534 | 512.7 |
| 2024-25 | `tier4_docling` | 369 | 499 | 450.1 |
| 2023-24 | `tier2_acroform` | 20 | 610 | 586.0 |
| 2023-24 | `tier4_docling` | 400 | 212.5 | 294.8 |

Tier 4's median is not the problem by itself. Excel- and Word-exported PDFs extract well. The loss is concentrated in flattened copies of the Adobe template.

### Sizing the cohort: geometry, not page count

The first draft sized the cohort as Tier 4 PDFs with 48–55 pages. That gives 42 docs for 2025-26 and 84 for 2024-25. It assumed all of them were template prints because of the page-1 banner "Welcome to the YYYY-YYYY Common Data Set collection!". Neither signal holds:

- The banner appears in only 18 of the 42 2025-26 docs and 51 of the 84 2024-25 docs (searched in the Tier 4 markdown).
- The banner also appears in 24 2025-26 Tier 4 docs outside 48–55 pages. Those are Word or Excel template exports that reuse the intro text.
- Some 48–55 page docs are Word-template or custom layouts (Duke, Chico, UTEP, Kutztown, UMass Amherst, Columbia, Northwestern, Williams, …).

The review re-measured the cohort with a raster page match.

- Each page of the Tier 4 PDF is rendered at 36 DPI, and pixels with gray level < 225 count as ink.
- A page matches template page *p* when at least 85% of *p*'s static ink is present within 3 px.
- A document matches when 30 or more of the 50 template pages are found.

The ink threshold matters. A stricter threshold (< 160) missed Georgia Gwinnett, FAU, UW–Green Bay, American and Valdosta: their template prints render gray. A spot render confirmed they are unscaled template prints. The gate has clear separation in this sample:

- the worst true match found 33 pages;
- the best non-match found 19.

| Year | Tier 4 PDFs scanned | Template match (≥30 pages) | Median Tier 4 fields of matched docs | Matched, < 50 readable text-layer values (needs OCR) | Matched, text-layer values |
|---|---:|---:|---:|---:|---:|
| 2025-26 | 166 of 179 (all with a resolvable source) | **37** (36 in 48–55 p, 1 at 40 p) | 270 | 13 | 24 |
| 2024-25 | 134 (all 38–70 p docs with a resolvable source; 68 of the 84 in 48–55 p) | **58** (52 in 48–55 p, 6 at 40–47 p) | 313.5 | 24 | 34 |

The split between the last two columns uses the `source_producer` family as a proxy: Print To PDF counts as needing OCR, plus Arkansas State, whose text layer is garbled. The yield table below covers the 92 docs that matched at the stricter first threshold.

**The addressable set is 95 documents (2024-25 + 2025-26), not 126.** The first version of the cohort list had 97 rows because Caltech 2024-25 and Texas A&M 2024-25 were each listed twice; the review's "300 PDFs scanned" likewise counts those two twice (298 distinct). They are listed in [`assets/038/template-cohort-2026-11-09.csv`](assets/038/template-cohort-2026-11-09.csv).

- Distiller files are part of it: 42 of the 95 were produced by Acrobat Distiller 25/26, and 36 by Print To PDF.
- The five 2025-26 cohort docs that still do not match are Word or custom layouts: Duke, Chico, UTEP, Kutztown and UMass Amherst. Tier 4 already extracts more fields from them than from the template prints, and they stay on Tier 4.
- 2023-24 was not measured (59 docs in 48–55 p) and is out of scope until it is.
- None of the first 92 has a `tier2_acroform` artifact. 12 have more than one source sha, so PR #258 can only affect a handful.

The three benchmark schools in the first draft (Valparaiso, Barnard and Miami 2025-26) are **not** in this cohort. Each still has an older `tier2_acroform` artifact. `cds_selected_extraction_result` ranks by producer before recency, so those Tier 2 artifacts are what we serve today. They remain useful as ground truth, because each has a fillable and a flattened copy, but they are not production losses.

### What the overlay recovers (yield, not yet accuracy)

**Text-layer docs.** On the matched docs, the review counted widget rectangles whose bounded text was non-empty and free of control characters. These are `/Tx` and `/Ch` fields only. `/Btn` fields are not counted, and the values were not validated.

| Year | Text-layer matched docs | Median Tier 4 fields | Median non-empty `/Tx`+`/Ch` reads |
|---|---:|---:|---:|
| 2025-26 | 24 | 291 | 564 |
| 2024-25 | 34 | 406.5 | 577 |

**Vector-path docs.** These have almost no values in the text layer (Miami: 0 of 562 populated `/Tx` rects). Their yield depends on OCR; see the Miami benchmark below.

## Evidence

### Field maps

| Year | Source | Pages | Fields | Widgets (`/Tx` / `/Ch` / `/Btn`) | Inverted `/Rect` |
|---|---|---:|---:|---|---:|
| 2025-26 | Blank template (`schemas/templates/cds_2025-26_template.pdf`) | 50 | 1,089 | 1,263 (789 / 76 / 398) | 114 |
| 2024-25 | Official blank (`schemas/templates/cds_2024-25_template.pdf`); Vaughn and UW Tier 2 donors agree with it within 0.002 pt | 50 | 1,116 | 1,257 (817 / 76 / 364) | 0 |
| 2023-24 | `schemas/templates/cds_2023-24_template.pdf` | 50 | 1,086 | 1,228 (784 / 76 / 368) | 0 |

**Join cap.** The 2024-25 and 2023-24 schemas give a `pdf_tag` to only 814 and 810 of the maps' 1,116 and 1,086 fields (2025-26: 1,087 of 1,089). Fields without a tag have `question_number: null` and are skipped, so the overlay's yield for 2024-25 is capped at Tier 2 parity until the tags are recovered. That is a separate schema project; see `scratch/prd038/tag-research/REPORT.md` (best join found: 952 and 921 tags).

**Maps are year-specific.** 2024-25 and 2025-26 share 1,082 tags, but only 738 of them keep the same page and rectangle (within 0.5 pt) across years. Inverted rects are a 2025-26 quirk. The build normalizes every rect regardless.

### Alignment

- Every matched doc in the sample is 612×792 pt with no rotation. One doc has a single 816×1056 page.
- Page-index offsets seen are 0, ±1, ±2, −3 and −4. 8 of the cohort docs mix two offsets (dropped or inserted pages mid-packet).
- Whole pages are mostly rigid: Valparaiso, Miami and Caltech read at offset (0, 0). Partial-page shifts exist, though (CSU Northridge 2024-25 has a lower half 14–16 pt low; South Dakota has bands that move by 1–8 pt; Eastern Michigan's typed "X" reflowed a Yes/No line by 8–9 pt), and page-level alignment cannot see them. Alignment is therefore checked per band and per widget ([A8](#a8-m1-findings-2026-11-10)).

**Text anchors do not work as the page matcher.** Acrobat Distiller 26.0 garbles text beyond bold headings: regular-weight prompts and some digits come through as Caesar-shifted bytes. A word-position matcher found 30 or more pages on only 2 of 17 Distiller docs. The raster matcher found 16 of them.

### Benchmarks against each school's own Tier 2

**Valparaiso 2025-26** (PDFium flattened `5969b8e6` vs fillable `80475b8f`):

- With the blank-template map, Lanes 1+3 match 611 of 621 directly extracted values, plus 3 of 3 derived B1 totals. That is **614 / 624**.
- This needs a 35% checkbox inset and stripping adjacent `(` / `)`. At the first draft's 25% inset it is 608 / 624: three radio dots score 0.109–0.110 against a 0.12 threshold.
- That 614 was measured with ±1 pt padding plus paren stripping, not the center-in-rect read specified in §3. M1 re-measures it with the specified method.
- The 10 misses:
  - 5 multi-line text fields clipped at the widget edge;
  - 2 display-rounded decimals (`77.2` printed as `77`);
  - 2 hidden C9 checker zeros;
  - 1 real correction between editions (`STATE_CODE` IL→IN).
- **False positives:** across the 468 fields Tier 2 left blank, there were 4 emissions.
  - 2 are URLs printed on the page with no `/V`.
  - 1 is a stray label character (`g`), which type validation rejects.
  - 1 is `C.207`, a static box printed under the widget: raw ink 0.138, 0 after subtracting the blank template's ink.

**Miami 2025-26** (Print-To-PDF `eaed9690`, values drawn as vector paths, +2 page offset):

- **Checkboxes:** 152 / 152 at a 35% inset; 149 / 152 at 25%.
  - Of the 72 checkbox fields Tier 2 left blank, 1 emits without baseline subtraction: `C.207` again, at 0.152 raw and 0.015 after subtraction.
- **300-DPI per-widget Tesseract OCR, full document:** 541 / 562 populated `/Tx` values match. 3 of 227 blank cells produced a value. The 5 pages in the first draft were 169 / 169.
- **The 21 misses:**
  - 8 single-digit values dropped by the ink-ratio gate;
  - 2 hidden checker values;
  - 2 display-rounded values;
  - 5 URLs and multi-line text fields mangled by OCR;
  - 1 phone number;
  - 1 missing long text;
  - 2 percentages (`FRAT_P`, `SORO_P`) where the flattened page really does print 24.00 / 25.00 and the fillable has 11 / 14. These are edition differences, not OCR errors.
- **Not measured:** the 44 populated `/Ch` dropdowns.
- **Runtime:** 25.7 s wall time for the full document on an Apple-silicon laptop, including Tier 2 ground-truth extraction.

**Barnard** was not re-run in the review. The first draft reported 586 / 609.

## Goals

1. On the 95 matched documents, emit template-overlay values that meet the Decision 3 bar: ≥ 99% exact on a hand-audited sample and zero numeric values that differ from the printed page.
2. Raise the median field count of the text-layer docs to ≥ 550, and of the vector-path docs to ≥ 450.
   - Today the text-layer docs sit at a median 291 (2025-26) and 406.5 (2024-25), measured on the 92-doc subset.
   - The vector-path docs sit at Tier 4's level, a median of 136–139 for Print To PDF.
   - Both targets are set from the yield and Miami measurements; M3 confirms them.
3. No regression on any document. A non-template PDF never yields overlay values.

## Non-goals

- Excel-, Word- or custom-layout PDFs. They fail the raster gate and stay on Tier 4.
- 2023-24 and older years until the cohort is measured for them. A 2023-24 print is recognised by its printed header and rejected (`template_year_unsupported`), never read through another year's map.
- Text that overflowed a fixed widget box. The flattened file does not contain it.
- Scans of printed paper. One cohort document is one (Akron 2024-25, Adobe Paper Capture, an invisible OCR text layer over the page image), so scans *are* present. Invisible text is never read as Lane 1 (it is not what the page prints); such pages go to Lane 2, which reads rendered pixels.
- OCR of free-text fields (`Text`, `URL`, `Email Address`). On Miami these were the main source of wrong values.

## Design

### 1. Field maps (`schemas/field_maps/cds_pdf_field_map_YYYY_YY.json`)

A build CLI, `tools/tier2_extractor/build_field_map.py`, harvests each map once. The output is committed.

**Sources:**
- 2025-26: commit the blank PDF to `schemas/templates/cds_2025-26_template.pdf`, next to the 2023-24 one.
- 2024-25: build from the official blank (`schemas/templates/cds_2024-25_template.pdf`, archived from the Wayback capture listed in `SOURCES.md`), like the other years. A consensus of Tier 2 donor PDFs (every widget within 0.5 pt) reproduces it and is kept as an optional cross-check.

**Per field:**
- `question_number`, joined via `pdf_tag` to `schemas/cds_schema_YYYY_YY.json`;
- the schema `value_type`;
- `ft`;
- widgets as `{template_page, rect}`, normalized so x0 < x1 and y0 < y1;
- the `/Opt` `[export, display]` pairs;
- the `/AP /N` on-state of each button widget;
- the blank template's static text inside the rect, used to subtract labels in Lane 1.

**Per page:** a 36-DPI static-ink mask of the blank template, for Stage 1.

### 2. Stage 1: template match, year, page alignment

1. **Pre-filter.** Run only on a single `kind='source'` PDF whose selected `source_format` is `pdf_flat` or `pdf_scanned`, with 30–70 pages.
2. **Raster match.** Match each target page against every template page of every year with a map. This took 0.3–0.5 s per document (max 1.2 s) in the review.
3. **Year selection: the printed header decides.**
   - Every template page prints "Common Data Set YYYY-YYYY" at a fixed position. Each matched page votes for the year whose blank page its header pixels match at 144 DPI (2023-24 is one of the choices), so it works on vector-drawn prints without OCR.
   - The document year is the header plurality (≥ 5 votes) and must agree with the best raster year; **any confident other-year page holds the whole packet** (A9: no majority rule). Anything else holds the document and emits nothing: a tie in the raster counts, no verifiable header, a mixed-year packet, a header that contradicts the raster year (a wrong year can lead on raster counts: 4 swapped pages flip a 2024-25 packet to 2025-26), or a known `detected_year` that contradicts the header. `detected_year` and `cds_year` never choose the map (CSU Northridge's `cds_year` is wrong).
   - A matched page whose own raster score in another year exceeds the chosen year's by more than 0.02 is not read (`page_raster_prefers_other_year`); neither is a page whose own header casts a *weak* vote for another year (`weak_other_year_vote`; it cannot hold the packet, but its rects are not trusted). Only 2024-25 and 2025-26 may emit; 2023-24 is recognised and rejected.
   - Measured on the 95 cohort documents: every vote is unanimous for the true year (31–45 voting pages per document), and the raster lead is as low as 2 pages, so the lead is not a usable rule.
4. **Gate.** At least 30 template pages matched; otherwise `not_official_pdf_template`.
5. **Page assignment.**
   - The page mapping is the monotonic assignment of target pages to template pages, which handles mid-packet drops. A pair is kept only when the template page is within 0.02 of the target page's best-scoring template page (blank pages 8, 38 and 41 cross-match at 0.85–0.87 and must not be read through each other's map).
   - When several target pages strongly claim one template page, they must agree on every answer or that template page's fields are rejected (`duplicate_page_conflict`): candidates with a native text layer are compared by the text read at each `/Tx` and `/Ch` rect, buttons and raster-only candidates by ink at 216 DPI (A10).
6. **Geometry and alignment.**
   - Text boxes, widget rects, static-template characters and rendered crops share one coordinate space built from PDFium's page transform (CropBox ∩ MediaBox origin, `/Rotate`, page scale; shifts are in template points and scaled with the page). A page that cannot be mapped exactly is rejected, not read.
   - The page shift is estimated at 72 DPI; a page whose optimum lies on the ±8 pt search boundary, or whose inked bands mostly agree on another shift, is rejected (`residual_page_shift`). The shift is applied only when no inked horizontal band (six bands) has a better shift of its own: a band disagrees when its best shift differs from the applied one by more than 1 pt and gains at least 0.10 recall. With no page shift, a disagreeing band's widgets are withheld (`band_misaligned`); with a nonzero page shift, a disagreeing band rejects the page (`partial_page_shift`).
   - Before any lane reads a widget, the template's static ink around it (rect + 14 pt) must fit the target at the applied transform: if shifting x or y alone (±10 pt, ignoring alternatives the blank template itself cannot tell apart, such as one table-row period) explains it ≥ 0.10 better, the widget is withheld (`local_misalignment`).

### 3. Lanes

**Lane 1: text layer (`/Tx`, `/Ch`).**
- Read characters whose box center lies inside the widget rect (and the spaces pdfium generated between them). Do not pad the rect by 1 pt; that padding pulled neighbouring `(` / `)` into 3 Valparaiso values. Subtract the template's static text for that rect.
- Map `/Ch` display strings to export codes through `/Opt`.
- Normalize by schema `value_type`:
  - number types (`Number`, `Numbers`, `Nearest $1`, `Nearest 1%`, `Whole Number or Round to Nearest Tenth`, `…Hundredths`): strip `$`, `,`, `%`;
  - `MM` / `DD`, `Text` and `URL`: keep the string.
- **The edge guard** (Number, Text and `/Ch` alike): a non-form glyph on the read's line whose box crosses the rect's left or right edge, or lies within 1 pt outside it, abstains (`glyph_crosses_*_edge`, `glyph_past_*_edge`); a multi-line Text read with paragraph lines just above or below the rect abstains (`multiline_overflow`). The same test is applied to Lane 2 crops.
- **Numeric token gate** (A10; numeric class; written on boxes, so Lane 2's OCR word boxes reuse it): a read is withheld when the printed token it belongs to is not wholly in the rect (`token_crosses_rect`: signs, points and commas attach to their digits by vertical extent, not by centre height) or mixes digit sizes or baselines (`mixed_glyph_size`: a superscript footnote marker; a uniformly small font still reads). **Free text** has one more rule: a line cut by the rect's top or bottom abstains (`line_straddles_rect`).
- **Invisible text is never read.** Each glyph's text render mode is read; a widget read containing any invisible (mode 3 or 7) glyph is not Lane 1 and the widget is scheduled for Lane 2. Every Lane 1 read also needs rendered ink in the rect that the blank template does not have there.
- Numbers use one token grammar (commas only as `\d{1,3}(,\d{3})+`, no joining of disjoint runs, no signs, ASCII digits); every percentage-typed field (`_P` tags, `Nearest 1%`) is checked against 0–100, and the per-field effective type is recorded in each value. A `/Ch` read that equals an option which is a proper prefix of another ("per semester" vs "per semester hour") abstains when the glyphs reach the rect edge; multi-widget fields must agree.
- **A read that contains control or private-use characters is never cleaned (a noncharacter or format character is ignored only when PDFium marks it generated). Treat it as unreadable and send that page to Lane 2.** Arkansas State 2025-26 matches the template, but 502 of its 521 non-empty reads are Caesar-shifted glyphs. Stripping `\x00–\x1f` would silently drop digits.

**Lane 2: crop OCR (`/Tx` and `/Ch` on pages where Lane 1 finds no values or unreadable glyphs).**
- Render the page once at 300 DPI.
- Crop each widget with a 1.2 pt inset and 16 px white padding.
- Skip the cell when it has fewer than *N* dark pixels. *N* is an absolute count, calibrated so a single digit passes; the ink-ratio gate dropped 8 Miami single digits.
- Run `tesseract stdin stdout --psm 7` with a numeric whitelist, in memory.
- Number types only. Text, URL and email fields are not OCR'd.
- Tesseract is already installed in `.github/workflows/ops-extraction-worker.yml`.

**Lane 3: checkboxes and radios (`/Btn`).**
- The box is measured where the print draws it (A9): the white interior its own frame encloses is found by flood fill from the rect's centre, and the mark is the ink density of that interior's central 60%, minus the ink the blank template has in its own interior. Frame, bevel and template glyph are never in the measured area.
- A box checks at ≥ 0.04; in a radio group the top box wins when it beats the second by 0.03. Interior scores are bimodal (empty ≈ 0, mark ≥ 0.06), so there is no gray band.
- A group abstains when the template draws a box and the print's is not found, closed and box-shaped within 2.5 pt of the rect (`box_not_closed`, `box_geometry`), and two checked boxes in a "fill in one only" group (C16, C17) abstain on both. Options the template draws no box for (an N/A) are read from the rect core.
- A10: only ink darker than the interior-white level counts (a uniform tint or veil is not a mark); two or more options at or above the threshold abstain before any winner margin (`multiple_options_marked`); ink in the winner's box that continues as a stroke or text run beyond it into the row abstains (`stroke_continues_beyond_box`).
- The emitted value is the raw export (`/Y`, `/Public`, `/2024`), decoded with `decode_button_value` from `tools/tier2_extractor/extract.py`, exactly as Tier 2 does.

**Post-processing:** `apply_b1_derived_all_totals` from `tools/extraction_worker/b1_derive_totals.py`, as Tier 2 does.

### 4. Validation: what stops a wrong value

Each value is checked before it is written. Values that fail are left out of `values` and listed in `notes.rejected_fields`, with the reason.

1. **Type.** It must parse for its `value_type`, and percentages must fall in 0–100.
2. **Identities present in the template.**
   - B1 total degree-seeking equals the sum of its rows.
   - C1 applied ≥ admitted ≥ enrolled.
   - C9 25th ≤ 50th ≤ 75th, with scores inside the test's range.
   - When an identity fails, every value in that identity is rejected in every lane and listed in `notes.rejected_fields` (Decision 3: values failing cross-field checks are not emitted), even where the school may have published inconsistent numbers.
3. **Document-level agreement with Tier 4.**
   - Compute exact agreement on fields both producers populate. Tier 4 is not ground truth, so this is a review signal, not a correctness check.
   - Disagreement above a set bar sets `quality_warnings` and holds the doc for review.

The first draft also proposed per-field confidence buckets. Nothing downstream reads per-field confidence, so the design emits only values that pass validation.

### 5. Producer, selection and merge

- **Artifact.** The producer is `tier2_template_overlay` (Decision 4). It writes `cds_artifacts.notes`, not `metadata` (no such column exists):
  - `producer_version`, `field_map_version` and `template_year`;
  - `matched_template_pages` and the page map;
  - `lane_counts` and `rejected_fields`;
  - `source_sha256`;
  - `source_selection` when PR #258 applies.
- **The worker runs Tier 4 as it does today, and also runs the overlay on docs that pass Stage 1.** The overlay never replaces the Tier 4 run:
  - Tier 4 values are still needed for fields the overlay does not emit;
  - any overlay failure leaves the document exactly where it is now.
- **Merge ("supplement" model; Decision 2).**
  - The overlay artifact holds only its own values. It is never a base candidate, so it never enters the view's `producer IN (…)` list or rank `CASE`.
  - `cds_selected_extraction_result` adds a second lateral join, next to the `tier4_llm_fallback` join. It picks the newest overlay artifact for the same document whose `source_sha256` equals the Tier 4 base's.
  - Merge order is `fallback || tier4 base || overlay`: overlay wins, then deterministic Tier 4, then the LLM fallback.
  - `project_browser_data.py` and `web/src/lib/queries.ts` need the same three-way merge.
  - This keeps per-field provenance and needs no merge code in the worker.
  - The alternative "base" model: the worker writes one combined overlay+Tier 4 artifact, and the overlay enters the `IN` list ranked above `tier4_docling`.
- **Existing producer-name consumers that must change** (the first draft listed only a migration):
  - `cds_selected_extraction_result`: the new overlay join and merge, and the view comment (base model: the `IN` filter and rank `CASE` instead);
  - `BASE_PRODUCER_RANK` and the Tier-4-only fallback logic in `tools/browser_backend/project_browser_data.py`;
  - `PRODUCER_FAMILY` in `tools/change_intelligence/project_change_events.py`, where an unknown producer currently falls back to the `tier2` family by prefix;
  - `extraction_ledger_tier` in `worker.py`, which is Python, not SQL;
  - `fallbackMatchesCanonical` and `fetchExtract` in `web/src/lib/queries.ts` and `web/src/lib/c1-headline-totals.ts:220`, which special-case `tier4_docling`.
- **Regression guard.**
  - `previous_canonical_field_count` reads the newest canonical artifact of *any* producer for the source sha.
  - Once an overlay artifact (~550 fields) exists, a later Tier 4 re-extraction (~290) would be blocked as a regression.
  - Scope that lookup, and the overlay's own guard, to the same producer.
  - The first draft's 250-field floor is dropped.
- **PR #258 order.** Source selection runs first. The overlay sees only the source PR #258 selects.
  - In the `print_to_pdf_values_missing_from_text` path, the fillable source is selected, so the overlay never sees the flattened file and cannot clear `needs_review`. That is out of scope.
  - In `edition_values_changed`, the overlay runs on the new flattened file. But an older `tier2_acroform` artifact for the same document would still outrank it in the current view. See Decisions.

### 6. Shadow mode and rollback

Overlay artifacts are written but not served until the precision audit passes.

- **Supplement model:** the switch is the overlay join in the view (plus the matching projection and web merge).
- **Base model:** the switch is the `IN` list.

Either way it is a separate, later migration, and rollback is the reverse migration. Per the migration rules, both are applied from `main` after merge. Bumping `producer_version` and re-running the drain replaces bad artifacts without touching Tier 4.

## Milestones

**M0 — Field maps.**
- Commit the 2025-26 blank template and three maps.
- Tests assert the counts in the table: 1,089 / 1,263; 1,116 / 1,257; 1,086 / 1,228.
- No inverted rects remain after normalization.
- The 2024-25 map rebuilds byte-exact from the official blank, and the donor consensus agrees with it.

**M1 — Stage 1 and Lanes 1 and 3.**
- On the 298 distinct PDFs scanned in the review, Stage 1 matches the 95 listed in [`assets/038/template-cohort-2026-11-09.csv`](assets/038/template-cohort-2026-11-09.csv) and rejects the other 203. Any difference is explained in the PR.
- It chooses the correct year for all 95 from the printed header, with the real `detected_year` metadata and no ambiguity (A8; the original lead/`detected_year` rule left 29 ambiguous).
- Valparaiso flattened recovers its Tier 2 values with the blank-template map and the §3 read method; every lost value is named by a rule (A9: 614 / 624, `/Btn` 139 / 139 at 10 sub-point phases).
- Lanes 1+3 emit no value where Tier 2 is blank, other than values actually printed on the page.
- Miami `/Btn`: 0 emissions on its 72 blank checkbox fields; recovery is reported with each loss named (A9: 152 / 152 at 10 sub-point phases, `ACAD_YR` included).

**M2 — Lane 2.**
- Miami flattened recovers ≥ 541 / 562 populated `/Tx` values. Every remaining mismatch is either a field excluded from OCR or a documented edition difference.
- Zero numeric values are emitted that differ from the printed page.
- The full document runs in ≤ 30 s on the worker runner.
- The 44 `/Ch` fields are measured and reported.

**M3 — Shadow drain and audit.**
- Code: projection, web and change-intelligence consumers learn the producer, but nothing serves it yet.
- Run the overlay on the 95 docs.
- Hand-audit a random sample of at least 300 emitted values across at least 20 docs, at least 10 of them vector-path, against the rendered page (Amendment A6).
- Report precision and the per-doc field-count change, with 0 regressions.
- If precision meets the Decision 3 bar, the serving migration lands (§6), together with the Decision 1 selection-precedence change.

## Decisions

Recorded 2026-11-09 by Anthony:

1. **Selection precedence: the current source wins over producer rank.** Selection first keeps only artifacts built from the document's current source, then applies producer rank among them. The current source is the source the newest extraction selected: `notes.source_selection.chosen_sha256` when PR #258 chose a source, else the newest `kind='source'` sha. A `tier2_acroform` artifact from an earlier edition no longer outranks a newer edition's results.
   - This changes behaviour for existing documents. The migration ships with a before/after diff of the selected producer per document, reviewed before merge.
   - Documents where PR #258 deliberately selected an older fillable source keep that source's Tier 2 artifact.
2. **Merge location: in the view** (the supplement model in §5). Projection and web mirror the same three-way merge.
3. **Precision bar for M3.**
   - At least 99% exact on the hand-audited sample.
   - Zero emitted numeric values that differ from the printed page.
   - A document is held for review when Tier 4 and the overlay disagree on more than 5% of the fields both populate.
   - Values that fail the §4 cross-field checks are not emitted.
4. **Producer: `tier2_template_overlay`, Tier 2 family** for change intelligence, listed explicitly in `PRODUCER_FAMILY` rather than relying on the prefix fallback. Under the supplement model it is never a base candidate, so it gets no base rank.
5. **2023-24: deferred.** Ship 2024-25 and 2025-26 first. Measure the 59-document 2023-24 cohort's geometry before including it.

## Amendments (2026-11-09, second review)

A second review checked the design against the serving code and production (read-only). These amendments override §5, §6 and Decisions 1–4 where they conflict. Each lists what was measured.

### A1. The overlay artifact is `kind='cleaned'`, not `kind='canonical'`

Several readers take the newest `kind='canonical'` artifact for a document with no producer filter. A canonical overlay artifact written after Tier 4 would be served immediately, with only overlay values and no markdown, so shadow mode would not hold:

- `fetchExtract` and `fetchCanonicalArtifact` in `web/src/lib/queries.ts` (the school page);
- `latest_canonical_artifact_id` in the `cds_manifest` view, and the documented public API call `cds_artifacts?kind=eq.canonical`;
- `has_canonical_for_current_bytes` in `worker.py` (the reconcile pass), which could mark a document `extracted` on the strength of an overlay artifact alone;
- `previous_canonical_field_count` in `worker.py` (the regression guard §5 patches);
- newest-canonical audits in `tools/data_quality/` (`audit_manifest.py`, `completeness_report.py`, `audit_reclean_candidates.py`, `audit_visual_ocr_candidates.py`).

The overlay is written as `kind='cleaned'`, `producer='tier2_template_overlay'`, like `tier4_llm_fallback`. None of the readers above then see it, and the §5 regression-guard change is no longer needed. The `kind` CHECK constraint already allows `cleaned`.

### A2. Three selectors, one parity test

"The selected result" is computed in three places, and they already disagree:

| Selector | Order | Feeds |
|---|---|---|
| `cds_selected_extraction_result` (SQL view) | producer rank, then recency | public API (granted to `anon`), `run_data_integrity_audit.py`, `audit_schema_alignment.py` |
| `select_extraction_result` in `project_browser_data.py` | schema version, schema fallback, unusable AcroForm, producer rank, recency | `school_browser_rows`, `cds_fields`, and so the browser, match, merit and change intelligence |
| `fetchExtract` in `web/src/lib/queries.ts` | newest canonical | the school page field viewer |

Measured: 8 documents have a newest-canonical producer different from the view's pick. Barnard 2025-26 is one: the school page serves a Tier 4 artifact written 2026-11-09 while the view picks June's Tier 2. So the statement in "Sizing the cohort" that the benchmark schools are served from Tier 2 is true of the view and the projection, not of every surface.

Decision 2 stands (the view merges), but the view is not what most users see. The overlay merge is therefore implemented in all three selectors, and M3 adds a shared fixture (a document with Tier 4, a matching overlay, a stale overlay from another source sha, and a Tier 2 artifact) that each selector must resolve identically. Consolidating the three selectors is out of scope.

### A3. Decision 1 needs a rule for artifacts with no source sha

Measured: 3,417 of 5,342 view-selected base artifacts (64%) record no source sha in `notes`. Only 4 selected artifacts record a sha that differs from the document's current source.

Rule: an artifact is excluded from selection only when it records a source sha **and** that sha differs from the current source. An artifact with no recorded sha counts as built from the current source. This is deliberately the opposite of `artifact_already_extracted`, which treats a missing sha as stale for idempotency; that function is not changed. The Decision 1 before/after diff should therefore show a handful of documents.

The overlay join is stricter: an overlay artifact merges only when its `source_sha256` is present and equals the base's recorded sha. If the Tier 4 base has no recorded sha, the overlay does not merge until Tier 4 is re-extracted.

### A4. Change intelligence must see that an overlay was applied

The projection writes `producer = selected.base_producer` into `school_browser_rows`, and `project_change_events.py` gates comparability on producer family and `producer_version`. Under the supplement model an overlay-merged row still reads `tier4_docling` at the same version, so Decision 4's family assignment has no effect, and values the overlay recovers would be reported as `newly_reported` or as school-side deltas.

When an overlay is merged, the projection writes `producer_version` as `<tier4 version>+overlay.<overlay version>`. The existing version gate then treats a Tier-4-only year and a Tier-4-plus-overlay year as not comparable. The implementer confirms that nothing parses `producer_version` structurally; if something does, add an explicit `overlay_producer_version` column and extend the gate instead. `tier2_template_overlay` is still listed in `PRODUCER_FAMILY` so a lookup never falls through to the prefix rule.

### A5. Worker flow

- The overlay has its own entry point and its own idempotency check keyed on (document, producer, producer version, field-map version, source sha). It is not a hook after the Tier 4 insert: `_run_tier4` returns early on `already_extracted` and on `tier4_field_regression`, which is the state of every existing cohort document.
- A scoped CLI mode runs the overlay alone over given document ids, for the M3 shadow drain.
- The Stage 1 pre-filter keys on the PDF having no usable AcroForm values and 30–70 pages, not on `source_format` alone, so documents that reach Tier 4 through the Tier 2 label-AcroForm fallback (`source_format='pdf_fillable'`) are considered too.
- An overlay failure of any kind is logged and never changes the document's status or the Tier 4 outcome.

### A6. Goals and audit, restated

- **Goal 2** is measured on the merged result (Tier 4 values plus overlay values), which is what is served: median ≥ 550 for text-layer docs and ≥ 450 for vector-path docs.
- **Conflicts.** "Overlay wins" is not yet measured. The M3 shadow report gives, per document, the count of fields both producers populate and the share that disagree, and the audit sample draws at least 100 of its values from those disagreements. The 5% hold threshold in Decision 3 is confirmed or reset from that distribution before serving.
- **Sample size.** 200 clean values only bound the error rate at about 1.5% (95% confidence). The audit uses at least 300 values, and the bar is zero wrong numeric values *in the sample* and ≥ 99% exact.
- **LLM fallback.** Measured: 231 Tier-4-selected documents have a `tier4_llm_fallback` artifact and the view merges none of them (no `base_artifact_id`; hashes and cleaner versions no longer match). The fallback leg of the three-way merge is inert today. Repairing it is outside this PRD; the merge order is unchanged so it works if the fallback is re-run.

### A7. Execution gates

Code for M0–M3 lands by PR. Three steps need the owner's explicit go-ahead and are run from `main` after merge, never from the feature branch: the production shadow drain, the Decision 1 selection migration, and the serving migration. The hand audit is done by a person.

### A8. M1 findings (2026-11-10)

Two independent reviews of the M1 code (Claude Opus, Codex) agreed that Stage 1 matched the right 95 documents but found emitted values that differ from the printed page, clustered in specific failure paths: CSU Northridge 2024-25 (10 false checkboxes on a page whose lower half is printed 14–16 pt low), Eastern Michigan 2025-26 (3 Yes/No radios read as No after typed text reflowed the line), Lone Star 2025-26 (`WAITLIST_INFO_STUD` read as No on empty boxes), and three more false lone checkboxes (John Carroll, McPherson, Arkansas); plus latent paths reproduced on synthetic variants (nonzero box origin, `/Rotate`, invisible OCR text, duplicated or swapped pages, mixed-year packets, a wrong year leading on raster counts, a late unreadable glyph, clipped dropdowns, malformed numbers). A random 100-value audit was 100/100 correct, which shows how clustered the errors are: audits must be stratified by risk signal, not only random. The fixes follow the rule that **a missing value is acceptable, a wrong emitted value is not**, and are written into §2–§4 and Non-goals above:

- **Year:** the printed header decides (§2.3); `detected_year` can only veto; 2023-24 is recognised and rejected; mixed or contradictory packets are held.
- **Geometry and alignment:** one display space from PDFium's page transform; per-band and per-widget local alignment; a page shift is applied only when the bands agree (§2.6).
- **Pages:** argmax guard and duplicate-page conflict (§2.5).
- **Lane 1:** invisible text and ink-free reads are never read; strict number grammar and 0–100 for every percentage-typed field; clipped dropdowns abstain (§3). **Scans are present in the cohort** (Akron 2024-25: an invisible OCR layer; 482 of 482 of its Lane 1 values came from invisible glyphs and no other cohort document has any).
- **Lane 3:** abstention band, outline and interior checks, "fill in one only" groups (§3).
- **Validation:** identity failures reject in every lane (§4, Decision 3); OCR-seam output lists unreadable and invisible pages and unresolved numeric widgets.
- **Cap:** the 2024-25 and 2023-24 maps join only 814 and 810 of their 1,116 and 1,086 tags to a question, so overlay yield for those years is capped at Tier 2 parity until tag recovery (a separate schema project, `scratch/prd038/tag-research/REPORT.md`).

Measured with the real metadata path (no expected year injected): Stage 1 still matches exactly the 95 cohort documents of 298 (worst match 33 pages, best non-match 19) and all 95 resolve to the correct year with none held; none of the 17 distinct reviewed wrong values is emitted (each abstains by a named rule); v0.2.0 emits a strict subset of v0.1 (0 new, 0 changed values); the cohort emits 37,184 values and abstains on 933 more, and 212 of the 38,089 values emitted before the fixes are now withheld by the alignment checks (a by-eye sample of 20 found 19 correct, so almost all of that cost is recall, not removed errors). Valparaiso falls from 614 to 611 / 624 and Miami `/Btn` from 152 to 147 / 152, every loss named by a rule or a below-threshold score. The wrong-year control (a forced wrong map, reachable only from the evaluation script) still passes validation for hundreds of values with 0–6 silently different per document, which is why the year is decided by the header and not by validation.

### A9. M1 verification round (2026-11-10)

An independent verification (Claude Opus) reproduced every v0.2.0 number and found what remained. All of it is fixed in v0.3.0; the numbers are in `scratch/prd038/m1/REPORT_v3.md`.

- **Page shift:** a page printed 8.5-12 pt aside was applied as a shifted-but-exact page (empty boxes read as checked). Pages whose optimum lies on the search boundary, or whose bands mostly disagree with the applied shift, are rejected (`residual_page_shift`; cohort cost: 1 page, 6 values).
- **Year, strict:** one confident other-year page holds the packet; the majority rule is gone. The header is cropped at the page's applied shift, a vote must fit the crop (diff below 0.85 of its ink), and only a confident vote (margin ≥ 0.02, fit ≤ 0.6) can hold, so sub-point shifted prints cannot hold a correct packet (cost on the cohort: 0). A page that fails alignment casts no vote, and a matched page whose own raster prefers another year by > 0.02 is not read (`page_raster_prefers_other_year`; cost 0). (A10 corrects an earlier statement here that a per-page header disagreement is unreachable: a page whose own header casts a *weak* vote for another year does reach it, and is now excluded from extraction as `weak_other_year_vote`.)
- **Edge guard on every Lane 1 read** (Number, Text, `/Ch`; also for Lane 2 crops) plus the multi-line overflow rule, spaces kept between glyphs, and `1.234` rejected on whole-number fields. All 8 wrong free-text values of the review are withheld (left-edge glyph ×5, right-edge glyph ×1, glyph adjacent outside the left edge ×1, adjacent outside the right edge ×1). Cost: 25 crossing + 4 adjacent + 11 multi-line + 1 thousands, none numeric except the one thousands value.
- **Lane 3 is measured per print, not per template.** The v0.2.0 core and baseline came from the blank template's glyph, which sits elsewhere in the rect than the box the print draws; 28 widgets have template border ink in the core, so the baseline cancelled real checks (Miami `ACAD_YR` scored 0.014 on a visibly checked box: a systematic miss, not crop rounding as A8's report said) and a sub-point shift moved box borders into the core. The interior of the print's own box is now found per box (§3); the legacy fitted rules (lone and radio gray bands, blank-outline gate at 200, border-in-interior) are removed, because with the print's own interior they stopped nothing: with them off, none of the 17 reviewed wrong values is emitted at any of 9 phases, there are 0 radio flips, and Valparaiso and Miami read every `/Btn` right (139/139, 152/152) at 10 phases. One residual risk was found and fixed on the way (one fitted constant: flag-only runs show the wrong count is unchanged for `INTERIOR_NEST_RATIO` between 1.2 and 2.0, which trades 1-25 correct values for the one wrong): a one-pixel pinhole in a nested inner frame (FORM_DOM_*) merged the fill with the ring around it (one wrong value at one phase); pinholes are closed when the fill is much bigger than the blank's own interior.
- **Tests and seams:** text-faithful shift fixtures (no duplicated text layer), tests for the five untested behaviours, a mutation set that fails loudly on a missing target; Lane 2 gets widget index, rect and applied shift in `ocr_widgets`, the public `widget_gates` and `edge_continuation`, and `reject_identity_failures` over the union of lanes.

### A10. M1 round 3: emission classes and the stop rule (2026-11-10)

A second independent verification (Claude Opus) and an outside review (Codex) of v0.3.0 found wrong values outside the tuned phases and classes of wrong value the guards did not cover. v0.4.0 fixes what is cheap and principled, labels what is not, and stops adding rules. Numbers: `scratch/prd038/m1/REPORT_v4.md`.

- **Emission classes.** Every value carries `emission_class`: `numeric` (typed numerics and derived totals), `choice` (`/Ch`), `checkbox_box` (Lane 3 through a located box interior), `checkbox_boxless` (Lane 3 where the blank draws no box: 22 + 57 widgets, 646 baseline emissions in v0.3.0) and `free_text`. The shadow artifact keeps every class. `SERVE_CLASSES_DEFAULT = {numeric, choice, checkbox_box}` and `serve_values()` filters by class; `checkbox_boxless` and `free_text` are shadow-only by default.
- **Fixed (each costs a few values or none on the cohort; see the report):** ink-only density (a uniform tint or veil is not a mark; v0.2.0 regression); two or more marked options abstain (`multiple_options_marked`); ink that continues as a stroke or text run beyond the box abstains (`stroke_continues_beyond_box`; this one costs 27 correct ticks at baseline and hundreds at some sub-point phases); numeric token membership on boxes (`token_crosses_rect`, `mixed_glyph_size`; written so Lane 2's OCR word boxes reuse it); duplicate pages compared by text, buttons and raster-only pages by ink at 216 DPI; a weak other-year page is excluded (`weak_other_year_vote`) without holding the packet; one free-text rule (`line_straddles_rect`); `1.234` rejected on every numeric type.
- **Not fixed, measured.** (1) The box locator can still read a leaked or doubled frame as a mark at untuned sub-point phases (Marine Option ×2, NCCU `HOUS_SINGLE`): flooding from one seed costs 234 correct values at baseline, rejecting frame-connected core ink 1,015, an open-versus-closed agreement check 18 / 523 / 56 / 391 at baseline / x067 / d067 / s0995, and any area or centre test about 2,800 (29% of prints draw boxes bigger than the blank's), so none ships and `checkbox_box` is not at 0 wrong. (2) The boxless path reads typed text and specks as marks. (3) Free text beyond the one rule. (4) Specks (a 0.8 pt dot reads as a check; v0.2.0's gray band withheld it; recorded as an audit stratum, no minimum mark size).
- **The stop rule.** No further fix that is justified only by a synthetic fixture. Per-class serving is decided at M3 from (1) shadow data, (2) a held-out perturbation set the builders do not see and (3) a hand audit. The audit needs about 300 values per served class, aimed at disagreements with other extractions (Tier 4, the fillable twin where one exists) and at the risk strata: boxless, weak-tail scores (0.04-0.10), shifted pages (applied or residual page shift), scans, specks.

### A11. M2: Lane 2 numeric OCR and sub-point registration (2026-11-12)

Numbers: `scratch/prd038/m2/REPORT.md`. `PRODUCER_VERSION` 0.5.0.

- **Sub-point registration.** After the whole-point page shift each page is registered to the blank at 1/3 pt (±1 pt) on the 216-DPI render; every lane reads through `PageCtx.dx/dy`. Baseline: 0 changed values. It removes the Marine Option ×2 wrong values and cuts the stroke-guard losses at 0.33-0.67 pt offsets by about 90% (d067 467 → 31); NCCU `HOUS_SINGLE` and `HOUS_MARRIED` remain wrong at a 0.5% scale, which is out of scope.
- **Lane 2 (`lane2_ocr.py`) replaces the §3 sketch.** `numeric` class only, on pages Lane 1 cannot read, off unless asked for. A value is emitted only when the rect holds ink the blank lacks, the per-widget gates pass on the OCR word boxes (the blank's own label words dropped), three reads agree (tight rect at 300 and 400 DPI, and the token at the rect in a wider context crop with the blank's ink erased), every word has Tesseract confidence ≥ 85, and the strict number grammar passes. Identities run over the union of lanes before the derived totals. Records carry `lane: 2`, confidence and the agreeing reads. The engine is the `tesseract` command line (5.5.3 measured); CI does not need it.
- **Measured.** Real vector image-only documents (39): 15,831 values, median 436 per document against Tier 4's 134 fields; 0 wrong in the 557 values viewed (397 Tier-4 disagreements, where Tier 4 was wrong every time, and a 160-value sample). Clean 300 DPI rasterised twins of the 56 text-layer documents: 89.8% of 25,793 ground-truth values, 0 wrong at baseline, 1 value wrong at four of the eight sub-point phases. Poor-scan twins (150 DPI, JPEG q55): 82.6%, 4 wrong at baseline and 5 distinct wrong values across the phases (a `1` read as `4`; a lost decimal point). Valparaiso and Miami were not measured.
- **Residual, not fitted.** The wrong values are single-glyph or decimal-point confusions at confidence 86-95 on which all three reads agree. No confidence floor reaches 0 on the poor scans without withholding about a third of the values (floor 88: 0.8% of clean values; 95: 18%). The floor, a source-resolution floor and a decimal-point test are levers for M3's held-out set; Lane 2 stays shadow-only until M3 decides per class.
- **Costs.** Per rule, on 12 documents: the second rendering withholds 150 (clean) and 51 (poor) values and stops 7 and 1 wrong ones; the confidence floor stops 1; the context agreement and the gates stop none on rasterised fills; erasing the blank's ink from the context crop is worth 30% of the values. Runtime: about 78 s per image-only document, 115 ms per widget read.

## Risks

| Risk | Mitigation |
|---|---|
| Wrong-year map gives plausible but wrong values (most pages look identical across years) | The printed header year must agree with the best raster year; mixed or contradictory packets are held (§2.3). Type and identity validation do not catch a wrong year (6–34 silently different values per document in the control) |
| Garbled CMaps put shifted glyphs in the text layer | Reject reads with control characters; OCR that page (§3) |
| Non-template PDF passes the gate | Raster gate at ≥ 30 pages separated 95 matches from 203 non-matches (best non-match 19 pages, worst match 33); M1 re-checks this |
| Light-gray or faded print misses the gate | Ink threshold < 225; a < 160 threshold missed 5 real template prints. The doc stays on Tier 4, so the failure costs nothing extra |
| OCR misreads a digit and the value passes type checks | Numbers only, identity checks reject the whole identity, shadow-mode audit before serving |
| Display rounding (`77.2` printed as `77`) | The overlay records what the school printed; not treated as an error |
| Clipped free text | Lane 1 emits the visible prefix only for text-layer docs; Tier 4 text is kept by the merge where the overlay has none |

## How measured

Scripts and outputs are in `scratch/prd038/review/` (gitignored). Each one was run against read-only production data and PDFs downloaded read-only from the `sources` bucket:

| Script or output | What it produced |
|---|---|
| `q1.sql`–`q5.sql` | Sizing via the pooler with `default_transaction_read_only=on` |
| `fmap.py` | Map harvest |
| `overlay.py`, `overlay2.py` | Valparaiso and Miami Lanes 1+3 |
| `miami.py`, output in `miami_full.txt` | Miami Lane 2 |
| `rastermatch.py`, outputs in `ras*.jsonl` and `cross_*.jsonl` | Stage 1 gate and cross-year test at ink < 160 |
| `rastermatch2.py` with `INK=225`, outputs in `ras*_ink225.jsonl` | Final gate and the cohort CSV |
| `fp.py` | False-positive counts |
| `geomatch.py`, output in `geo*.jsonl` | Text-anchor comparison |
| `yield.py`, `lane1scan.py` | Lane 1 yield and control-character scan |
| `../miami_crop_ocr.py` | The original author's 5-page Miami spike |

### A12. M2 fix round: OCR class, second-model gate and a withdrawn claim (2026-11-12)

Two independent reviews of M2 (producer 0.5.0) found Lane 2 could emit wrong values with high confidence and could serve them by default. Producer 0.6.0 changes:

1. **Lane 2 has its own class, `ocr_numeric`.** It is never in `SERVE_CLASSES_DEFAULT`. A derived total carries the lanes of its inputs; one that depends on a Lane 2 value is `ocr_numeric`. `serve_values` enforces this by construction (a record with `lane == 2` or `2 in derived_lanes` is not served by default whatever its label). Lane 2 may veto (identity failures) but never vouch. Lane 1+3 output is unchanged on the cohort (0 new / 0 changed / 0 lost).
2. **Second-model agreement gate.** A value is emitted only if tessdata_best (eng, LSTM), reading the Otsu-binarised tight crop without a digit whitelist, parses under the same number grammar to the same value. Parameters are those of the verifier's `a_best_bin`; `MIN_CONF` stays 85. The verifier's 30/30 was measured on the values it was chosen from and is in-sample; Codex B1–B4 are quasi-held-out. **Both models are LSTMs, so correlated errors (7→1, l→1, O→0) pass the gate** (`l123`→1123 and `O123`→0123 still emit; a leading point beside a rule, `border-decimal`, still emits). Model files are fetched by `fetch_tessdata.py` with sha256 verification, never committed; a missing or wrong second model disables Lane 2 and records `notes.lane2_disabled`. Engine version and both shas are recorded in notes.
3. **Token completeness.** Edge and token gates also run on the unmodified raster; ink at the crop edge, in a strip beyond the cell, or an internal gap above 0.5 digit advance abstains. These rules cost recall (clean 300 DPI twin 89.8% → 71.7%) and are a trade to be judged on M3's held-out set.
4. **Hidden native text.** Text covered by a later image XObject (paint order) is invisible to Lane 1.
5. **Registration.** `refine_subpoint_shift` uses the connected plateau containing the maximum.
6. **Withdrawn claim.** M2's "0 wrong on real documents" is withdrawn: South Carolina State 2025-26 `EN_GRAD_PT_WMN_N` prints 75, Lane 2 emitted 15 (conf 93.8) and Tier 4 was right. **M2 has no real-scan evidence**: the 39 real documents are vector image-only, none is a raster scan, and the twins are synthetic. Measurements are in `scratch/prd038/m2/REPORT_v2.md`.

### A13. M3 build: worker entry point, shadow artifact and a merge that is switched off (2026-11-12)

M3's code lands with no change to production behaviour: no overlay artifact exists until the owner runs the shadow drain, and nothing serves one if it did. Where this refines A1-A7:

1. **Entry point (A5).** `tools/extraction_worker/overlay_entry.py`, imported lazily and only from inside `try/except` (never at the top of `worker.py`). Its own idempotency key is (document, producer, producer version, field-map version, source sha256). The routine worker loop calls it only when `OVERLAY_WORKER_ENABLED` is truthy (default off). The CLI defaults to `--dry-run`; `--write` inserts only the artifact; neither writes a heartbeat or ledger row, refreshes the projection or notifies the web. `--pdf-dir` is a local mode with no database at all. The A5 pre-filter reads "usable AcroForm values" as schema-mapped populated fields, so a label-AcroForm PDF that reached Tier 4 through the Tier 2 fallback is still considered. The workflow image and a Lane 2 time budget are not in M3 (the shadow drain runs from a local checkout); the later workflow change needs the sha-verified second model (`fetch_tessdata.py`), a Tesseract install, and a per-document Lane 2 budget.
2. **Artifact (A1).** `kind='cleaned'`, `producer='tier2_template_overlay'`. `notes` holds every class with `emission_class`, `lane` and `derived_lanes`, plus the audit fields and the Decision 3 hold: `base_artifact_id`, `tier4_disagreement_share` (over fields both populate) and `held`. An overlay is **held unless `held` is exactly `false`**; a missing Tier 4 base (`no_tier4_base`) or a base whose schema version differs (`tier4_schema_mismatch`) is held because no share can be computed. The threshold is 5% (`OVERLAY_HOLD_THRESHOLD`).
3. **One definition of "served overlay values" (A2, A3).** `tools/browser_backend/overlay_serving.py`, mirrored in `web/src/lib/overlay-serving.ts` and `supabase/pending/038_overlay_serving.sql`, pinned by `tools/browser_backend/fixtures/overlay_parity.json`. An overlay merges only onto a **`tier4_docling` base**, when its `source_sha256` is present and equal to the base's recorded sha (`notes.source_sha256`, else `notes.source_artifact.sha256`), **its `schema_version` and the base's are both non-null and equal** (new: the overlay's question ids follow its template year, and Tier 4 artifacts without a schema version carry 2025-26 ids whatever the template), and it is not held; the newest such overlay is used. A value is served only if its class is in the served set and it has no Lane 2 evidence (`lane == 2` or `2` in `derived_lanes`), whatever the set says. Merge order `fallback || tier4 base || overlay`.
4. **Served-class configuration.** Python and TS: server-only env `OVERLAY_SERVE_CLASSES` (comma-separated; default empty; an unknown name means nothing is served; the web needs a redeploy to change it, and the set is part of the `fetchExtract` cache key when on). SQL: the function `cds_overlay_serve_classes()` returning `'{}'::text[]`. With the set empty, no overlay code runs and the output is byte-identical with or without overlay artifacts. Selectors always pass the configured set explicitly; the producer's own `SERVE_CLASSES_DEFAULT` is never used for serving.
5. **SQL is not a migration.** `supabase/pending/` (see its README), applied only by a later PR after owner approval. Decision 1's selection-precedence rewrite is not written in M3; only its read-only before/after diff query is (`038_decision1_selection_diff.sql`; on production it lists 5 documents).
6. **A4.** Under the supplement model an overlay-merged row keeps the base producer and its `producer_version` is `<tier4 version>+overlay.<overlay version>` (only when at least one overlay value is served). Three places parse or compare `producer_version` structurally: the two `version_tuple` functions (`audit_watchlist_freshness.py`, `audit_visual_ocr_candidates.py`) and the projection-identity comparison in `run_data_integrity_audit.py`. All three now ignore the suffix. The alternative A4 names, an explicit `overlay_producer_version` column, needs a migration and was not added; choosing between the suffix and a column is the owner's call before the serving PR. `tier2_template_overlay` is listed in `PRODUCER_FAMILY` (Tier 2 family).
7. **Other producer-name consumers.** `fallbackMatchesCanonical` and the Python fallback match accept only `tier4_llm_fallback`; `c1TemplateForArtifact` has an explicit overlay branch; `extraction_ledger_tier` maps an overlay action to `unknown` (a new tier value needs a CHECK-constraint migration; the overlay writes no ledger row).
8. **Disagreement comparison.** Values are compared by number, and `Yes`/`/Y`/`X`/`/X` (and the no forms) are one value: Tier 4 writes a ticked box as `X`, the overlay writes the export value. This is a representation rule written after reading the cohort's disagreeing pairs, not a tuned threshold.

### A14. M3 fix round: write-time hold facts, `--rehold`, the single-writer contract and page kind (2026-11-12)

Two independent reviews of M3 (head 6380886) found that the 5% hold as built measured Tier 4's grid errors (in 120 sampled disagreements the overlay was right 115 times, 5 were spelling only, Tier 4 right 0 times), was computed over classes that are never served, and was frozen at write time with no way to change it short of a forced re-extraction. This amendment overrides A13 where they conflict.

1. **The hold stays a write-time fact; the facts are stored.** The selectors still skip any overlay whose `notes.held` is not exactly `false`; no selector reads a threshold, and there is no `OVERLAY_HOLD_THRESHOLD` or `cds_overlay_hold_threshold()` in them (a read-time rule was considered and rejected). At write time the artifact stores `notes.comparison`: per emission class the fields both producers populate and the ones that disagree, the disagreeing question ids with their class, per class the fields Tier 4 populates that the overlay leaves empty (the blind spot the share cannot see), the comparison base's id, version, schema version and recorded sha; and `notes.hold_basis` (classes, threshold, compared, disagree, share). `held` is computed at write time over the default served-candidate classes (`numeric`, `choice`, `checkbox_box`) only, with the tool's threshold (default 0.05, `off` disables the disagreement part). Structural conditions that are facts about the artifact are kept apart in `structural_hold_reason` (`no_tier4_base`, `tier4_schema_mismatch`, `chosen_base_not_tier4`, `document_hold`) and always hold. The comparison base is the one the projection would choose (`sort_base_candidates` order) among bases whose recorded sha equals the overlay's source sha.
2. **`--rehold`** (`overlay_entry.py`, dry run by default, `--write` explicit) recomputes `held` and `hold_basis` from the stored facts under a given threshold and class set (or `off`) and appends a new artifact with the values copied; no extraction. The newest eligible overlay wins in every selector, so the appended artifact takes over; an unchanged outcome and basis appends nothing.
3. **Comparator.** By the overlay value's class: numeric classes by value only; choice and checkbox classes with the yes/no/X spellings as one boolean; free text as trimmed text; nothing else. "Required" against "Required of All" (83 cohort pairs) is a known spelling difference and is not normalised.
4. **Selector rules (all three).** Lane 2 evidence is `lane` or a `derived_lanes` member that is the number 2 as `2`, `2.0` or `"2"`. A blank overlay value is never merged, so it cannot overwrite a populated base value. A `notes.values` that is not an object serves nothing. An unknown class name anywhere in the served set serves nothing (SQL included). Empty strings count as a missing sha or schema version in SQL as they do in Python and TS. The web query filters kind, producer, schema version and the base's recorded sha and pages newest-first until a page holds an eligible overlay (a fixed `limit` before eligibility hid older eligible ones). With the served set empty: exactly the same two web queries and the original cache key, and the projection does not fetch overlay artifacts at all. "Lane 2 is never served" is unchanged in every selector; the vector-page serving rule belongs to the serving PR after the hand audit.
5. **Change intelligence.** Overlay identity (overlay version and served class set) is read through one helper (`overlay_identity`; today it parses the `producer_version` suffix `<base>+overlay.<overlay version>/<classes>`; the owner has since chosen the explicit `overlay_producer_version` column, which ships with the serving change; until then the suffix stands and this helper is the one place that changes). When two compared rows differ in overlay identity, any change in what is reported, in any direction, is classified `producer_changed` with the existing extraction caveat, never as a school-side change; an unchanged value emits nothing.
6. **Producer 0.7.0 records page kind.** Every Lane 2 value carries `page_kind` (`vector` unless one image XObject covers at least half the page, else `raster`) and `image_coverage`; a derived total that depends on Lane 2 carries `input_page_kinds`. Metadata only: what is emitted is unchanged. Tesseract's version and the model shas stay in the notes, not in the skip key.
7. **Single-writer contract.** There is no database uniqueness on overlay artifacts and none is added. The drain tool is for ONE SERIAL WRITER. Before extracting it skips a document when an overlay with the same (document, producer version, field-map version, source sha, whether Lane 2 was requested) exists (the lookup pages through every matching row); two concurrent writers can both insert, which is harmless because the newest eligible overlay wins. This is a best-effort skip, not general idempotency. `--env` values reach every setting the tool reads; the CLI continues after any `BaseException` except `KeyboardInterrupt`.
8. **Wording and owner decisions.** No selected-result consumer serves overlay values unless `OVERLAY_SERVE_CLASSES` names classes; the raw artifact rows are publicly readable through the `cds_artifacts` API, which the owner has accepted. The owner chose the explicit `overlay_producer_version` column over the suffix (it ships with the serving change, with a migration). The owner waived the hand audit. Whether to mention the raw rows in the `/api` documentation remains open.
9. **A Lane 2 failure does not lose Lane 1+3.** Any engine failure (Tesseract exits nonzero, a call times out after 30 s, the binary is missing or its probe fails) is caught around the Lane 2 hook: everything Lane 2 emitted or withheld is dropped, `notes.lane2_failed` (or `notes.lane2_disabled`, from the probe) records the reason, and the result is exactly the `--no-lane2` result. The probe (`check()`) runs before `version()` and `model_info()`, so a missing binary is reported as `tesseract_not_installed`.
10. **Open, not done here.** `tools/schema_builder/decode_checkboxes.py:76-77` swaps the `/TFER_RFS` and `/TFER_ROS` labels; it is live in production through Tier 2 and is a separate change, and the overlay's `value_decoded` for D5 columns 3 and 4 inherits it. Tier 4's grid errors, the workflow image and Decision 1's view rewrite are out of scope.

### A15. Serving change (2026-11-13)

Owner decisions, final: serve the overlay; the M3 hand-audit requirement (§M3, Decision 3's 99% bar, A6's 300-value sample) is **waived by the owner**; the explicit `overlay_producer_version` column replaces the `+overlay.` suffix; raw shadow rows being publicly readable through the `cds_artifacts` API is accepted; the Tier 4 disagreement hold is off for serving because the M3 review showed it measures Tier 4's error, not the overlay's (in 120 sampled disagreements the overlay was right 115 times, 5 were spelling only, Tier 4 right 0 times); the `decode_checkboxes.py` RFS/ROS label swap is a separate change. This amendment overrides A13 and A14 where they conflict.

1. **What is served.** `numeric`, `choice` and `checkbox_box` values; `ocr_numeric` only when the value's `page_kind` is `vector` (a derived total with Lane 2 inputs only when its `input_page_kinds` is a non-empty list of only `vector`); never raster-page OCR and never a value without a `page_kind`; never `checkbox_boxless` or `free_text`. One predicate, written identically in Python (`overlay_serving.py`), TypeScript (`overlay-serving.ts`) and the SQL view, pinned by `overlay_parity.json` (58 cases). Structural holds still apply (no Tier 4 base, schema mismatch, producer document hold); the shadow drain runs with the disagreement hold off, so `held` is false unless a structural reason applies. The tool's default is now off (`--hold-threshold` or `OVERLAY_HOLD_THRESHOLD` turns it on).
2. **Default served set, in code.** `numeric,choice,checkbox_box,ocr_numeric` is one named constant in each selector (`DEFAULT_SERVE_CLASSES`, `DEFAULT_OVERLAY_SERVE_CLASSES`, and the body of `cds_overlay_serve_classes()`). `OVERLAY_SERVE_CLASSES` still overrides it in Python and TS; unset, empty or whitespace means the default (an unset repository variable expands to an empty string and must not silently turn serving off); **`none` is the only off token**; an unknown class name anywhere serves nothing. No Vercel or workflow environment change is needed to turn serving on, and the default set is part of the web cache key (a one-time cold cache on deploy).
3. **Migrations.** `20261113042000_overlay_serving_view.sql` creates `cds_overlay_serve_classes()` (STABLE, executable by `anon`, `authenticated` and `service_role`) and then `cds_selected_extraction_result` with the overlay join (column list and order unchanged); `20261113042100_school_browser_rows_overlay_producer_version.sql` adds `school_browser_rows.overlay_producer_version text null` and extends `replace_browser_projection_for_document()`. Their DO blocks assert schema shape only. The serving SQL left `supabase/pending/` (the Decision 1 diff query and README stay).
4. **Identity.** `overlay_producer_version` stores `<overlay version>/<sorted served classes>` (null when no overlay value was served); `producer_version` is the plain Tier 4 version. The `+overlay.` suffix is no longer written; the three audit readers stay tolerant of it. `overlay_identity` in change intelligence reads the column. The projection sends the key only when it has a value, and the RPC reads `p_browser_row` through an explicit column list, so the window between this code merging and the migration being applied does not fail the daily drain.
5. **Rollout order.** No overlay artifact exists in production (0 rows). Merge PR 1, merge PR 2, `supabase db push`, then `overlay_entry.py --write --hold-threshold off` for the 95 cohort documents, then re-project them, refresh the serving caches once, revalidate the schools. **Rollback:** set `OVERLAY_SERVE_CLASSES=none` for the web and the projection, replace `cds_overlay_serve_classes()` with a function returning `'{}'`, re-project rows where `overlay_producer_version IS NOT NULL`, refresh the caches.
6. **Still out of scope.** The routine worker calling the overlay, Decision 1 selection precedence, relaxing the Lane 2 completeness rules, and the label swap in `decode_checkboxes.py`.
7. **Zero never replaces a positive base value.** In all three selectors an overlay value that is numerically zero (any spelling: `0`, `0.0`, `"0"`, `"0.00"`, `"0%"`, `"$0"`) does not overwrite a Tier 4 or fallback value that is numerically non-zero (negative included); the base value is kept. Zero still fills a field the base leaves empty or holds as text and still overwrites a base zero. A printed 0 in a total or unknown cell is often a form default (California State University Northridge 2024-25 prints 0 in the residency-table totals; the C1 gender rows on its image-rendered page add up to Tier 4's applied 33,350, while Tier 4's admitted 17,021 is not the sum of the printed admitted rows, 30,842: the rule keeps today's served values, right or wrong). The rule can only keep what is served today. If it suppresses every served value of an overlay, no overlay identity is recorded for the row.
