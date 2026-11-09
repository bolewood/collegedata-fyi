# PRD 038: Template overlay extraction for flattened official CDS PDFs

**Status:** Approved for M0–M3 (revised after adversarial review; decisions recorded 2026-11-09)
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

It writes a new canonical producer.

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
| 2024-25 | 134 (all 38–70 p docs with a resolvable source; 68 of the 84 in 48–55 p) | **60** (54 in 48–55 p, 6 at 40–47 p) | 313.5 | 24 | 36 |

The split between the last two columns uses the `source_producer` family as a proxy: Print To PDF counts as needing OCR, plus Arkansas State, whose text layer is garbled. The yield table below covers the 92 docs that matched at the stricter first threshold.

**The addressable set is 97 documents (2024-25 + 2025-26), not 126.** They are listed in [`assets/038/template-cohort-2026-11-09.csv`](assets/038/template-cohort-2026-11-09.csv).

- Distiller files are part of it: 44 of the 97 were produced by Acrobat Distiller 25/26, and 36 by Print To PDF.
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
| 2025-26 | Blank template (`scratch/CDS-PDF-2025-2026_PDF_Template.pdf`, **not in repo**) | 50 | 1,089 | 1,263 (789 / 76 / 398) | 114 |
| 2024-25 | No blank PDF; Vaughn and UW Tier 2 sources agree on 1,116 / 1,116 fields within 0.5 pt | 50 | 1,116 | 1,257 (817 / 76 / 364) | 0 |
| 2023-24 | `schemas/templates/cds_2023-24_template.pdf` | 50 | 1,086 | 1,228 (784 / 76 / 368) | 0 |

**Maps are year-specific.** 2024-25 and 2025-26 share 1,082 tags, but only 738 of them keep the same page and rectangle (within 0.5 pt) across years. Inverted rects are a 2025-26 quirk. The build normalizes every rect regardless.

### Alignment

- Every matched doc in the sample is 612×792 pt with no rotation. One doc has a single 816×1056 page.
- Page-index offsets seen are 0, ±1, ±2, −3 and −4. 8 of the 97 docs mix two offsets (dropped or inserted pages mid-packet).
- Within a matched page, widget positions do not drift: Valparaiso, Miami and Caltech read at offset (0, 0).

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

1. On the 97 matched documents, emit template-overlay values that meet the Decision 3 bar: ≥ 99% exact on a hand-audited sample and zero numeric values that differ from the printed page.
2. Raise the median field count of the text-layer docs to ≥ 550, and of the vector-path docs to ≥ 450.
   - Today the text-layer docs sit at a median 291 (2025-26) and 406.5 (2024-25), measured on the 92-doc subset.
   - The vector-path docs sit at Tier 4's level, a median of 136–139 for Print To PDF.
   - Both targets are set from the yield and Miami measurements; M3 confirms them.
3. No regression on any document. A non-template PDF never yields overlay values.

## Non-goals

- Excel-, Word- or custom-layout PDFs. They fail the raster gate and stay on Tier 4.
- 2023-24 and older years until the cohort is measured for them.
- Text that overflowed a fixed widget box. The flattened file does not contain it.
- Skewed or low-resolution scans of printed paper. No such case was seen among the 97.
- OCR of free-text fields (`Text`, `URL`, `Email Address`). On Miami these were the main source of wrong values.

## Design

### 1. Field maps (`schemas/field_maps/cds_pdf_field_map_YYYY_YY.json`)

A build CLI, `tools/tier2_extractor/build_field_map.py`, harvests each map once. The output is committed.

**Sources:**
- 2025-26: commit the blank PDF to `schemas/templates/cds_2025-26_template.pdf`, next to the 2023-24 one.
- 2024-25: build by consensus of at least 2 Tier 2 donor PDFs. Every widget must agree within 0.5 pt.

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
3. **Year selection.**
   - The wrong year's template also clears the 30-page gate. At the < 160 ink threshold, 35 / 35 of the 2025-26 docs matched the 2024-25 template, and 56 / 57 the other way round.
   - Per document, the correct year always matched more pages, but sometimes only just:
     - the minimum lead was 3 pages in 2025-26 and 1 page in 2024-25;
     - 23 of 55 2024-25 docs led by fewer than 3 pages.
   - Rule:
     - choose the year with the most matched pages;
     - when the lead is under 3 pages, require that year to agree with `detected_year`, else return `template_year_ambiguous`;
     - a tie is always ambiguous.
   - Most pages are identical across years, but only 738 of 1,082 shared tags keep their rectangle, so a wrong year is not harmless.
   - M1 re-measures these margins with the final matcher.
4. **Gate.** At least 30 template pages matched; otherwise `not_official_pdf_template`.
5. **Page alignment.**
   - The page mapping is the monotonic assignment of target pages to template pages, which handles mid-packet drops.
   - Within a page, the transform is `(sx, sy)` from the mediabox ratio plus a `(dx, dy)` shift. Estimate the shift from the raster mask; it is (0, 0) in every sample.
   - Reject the page if the residual exceeds 1 pt.

### 3. Lanes

**Lane 1: text layer (`/Tx`, `/Ch`).**
- Read characters whose box center lies inside the widget rect. Do not pad the rect by 1 pt; that padding pulled neighbouring `(` / `)` into 3 Valparaiso values. Subtract the template's static text for that rect.
- Map `/Ch` display strings to export codes through `/Opt`.
- Normalize by schema `value_type`:
  - number types (`Number`, `Numbers`, `Nearest $1`, `Nearest 1%`, `Whole Number or Round to Nearest Tenth`, `…Hundredths`): strip `$`, `,`, `%`;
  - `MM` / `DD`, `Text` and `URL`: keep the string.
- **A read that contains control or private-use characters is never cleaned. Treat it as unreadable and send that page to Lane 2.** Arkansas State 2025-26 matches the template, but 502 of its 521 non-empty reads are Caesar-shifted glyphs. Stripping `\x00–\x1f` would silently drop digits.

**Lane 2: crop OCR (`/Tx` and `/Ch` on pages where Lane 1 finds no values or unreadable glyphs).**
- Render the page once at 300 DPI.
- Crop each widget with a 1.2 pt inset and 16 px white padding.
- Skip the cell when it has fewer than *N* dark pixels. *N* is an absolute count, calibrated so a single digit passes; the ink-ratio gate dropped 8 Miami single digits.
- Run `tesseract stdin stdout --psm 7` with a numeric whitelist, in memory.
- Number types only. Text, URL and email fields are not OCR'd.
- Tesseract is already installed in `.github/workflows/ops-extraction-worker.yml`.

**Lane 3: checkboxes and radios (`/Btn`).**
- Ink density over the widget interior at a 35% inset.
- Subtract the blank template's ink at the same crop, which handles static boxes printed under widgets such as `C.207`.
- A single checkbox is checked when its baseline-subtracted score clears the threshold.
- In a radio group, the top widget wins when it clears the threshold and beats the second by a margin.
- The emitted value is the raw export (`/Y`, `/Public`, `/2024`), decoded with `decode_button_value` from `tools/tier2_extractor/extract.py`, exactly as Tier 2 does.

**Post-processing:** `apply_b1_derived_all_totals` from `tools/extraction_worker/b1_derive_totals.py`, as Tier 2 does.

### 4. Validation: what stops a wrong value

Each value is checked before it is written. Values that fail are left out of `values` and listed in `notes.rejected_fields`, with the reason.

1. **Type.** It must parse for its `value_type`, and percentages must fall in 0–100.
2. **Identities present in the template.**
   - B1 total degree-seeking equals the sum of its rows.
   - C1 applied ≥ admitted ≥ enrolled.
   - C9 25th ≤ 50th ≤ 75th, with scores inside the test's range.
   - When an identity fails on OCR'd values, every value in that identity is rejected. On text-layer values, the failure is recorded but nothing is rejected, because the school may have published inconsistent numbers.
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
  - `web/src/lib/queries.ts:600` and `web/src/lib/c1-headline-totals.ts:220`, which special-case `tier4_docling`.
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
- The 2024-25 map agrees between the two donors.

**M1 — Stage 1 and Lanes 1 and 3.**
- On the 300 PDFs scanned in the review, Stage 1 matches the 97 listed in [`assets/038/template-cohort-2026-11-09.csv`](assets/038/template-cohort-2026-11-09.csv) and rejects the other 203. Any difference is explained in the PR.
- It chooses the correct year for all 97, or returns `template_year_ambiguous` only where `detected_year` is missing.
- Valparaiso flattened recovers ≥ 614 / 624 of its Tier 2 values with the blank-template map and the §3 read method.
- Lanes 1+3 emit no value where Tier 2 is blank, other than values actually printed on the page.
- Miami recovers 152 / 152 `/Btn` values, with 0 emissions on its 72 blank checkbox fields.

**M2 — Lane 2.**
- Miami flattened recovers ≥ 541 / 562 populated `/Tx` values. Every remaining mismatch is either a field excluded from OCR or a documented edition difference.
- Zero numeric values are emitted that differ from the printed page.
- The full document runs in ≤ 30 s on the worker runner.
- The 44 `/Ch` fields are measured and reported.

**M3 — Shadow drain and audit.**
- Code: projection, web and change-intelligence consumers learn the producer, but nothing serves it yet.
- Run the overlay on the 97 docs.
- Hand-audit a random sample of at least 200 emitted values across at least 20 docs, at least 10 of them vector-path, against the rendered page.
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

## Risks

| Risk | Mitigation |
|---|---|
| Wrong-year map gives plausible but wrong values (most pages look identical across years) | Score every year; when the margin is under 3 pages require `detected_year` agreement (§2.3); type and identity validation |
| Garbled CMaps put shifted glyphs in the text layer | Reject reads with control characters; OCR that page (§3) |
| Non-template PDF passes the gate | Raster gate at ≥ 30 pages separated 97 matches from 203 non-matches (best non-match 19 pages, worst match 33); M1 re-checks this |
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
