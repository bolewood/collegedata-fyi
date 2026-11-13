# tier2_extractor

Deterministic CDS extraction from fillable PDFs via AcroForm fields.

## Why this exists

The Common Data Set Initiative publishes a fillable PDF template each year. Schools that distribute the filled template **without flattening** preserve the 1,089 named AcroForm form fields in their published PDF. Those field names are canonical (`AP_RECD_1ST_MEN_N`, `EN_FRSH_FT_WMN_N`, …) and map one-to-one with entries in the [`schemas/cds_schema_{year}.json`](../../schemas/) artifact produced by [`tools/schema_builder/`](../schema_builder/).

When a PDF has a populated AcroForm, extraction is a 20-line job: read the fields with `pypdf.get_fields()`, join against the schema, emit canonical JSON keyed by question number (`A.001`, `B.101`, `C.101`, …). No OCR. No layout parsing. No LLM. No ambiguity. The published values are exactly what the school entered.

This is the **Tier 2** extraction path in the project's tiered strategy:

| Tier | Input | Extractor | Accuracy |
|---|---|---|---|
| Tier 1 | Filled XLSX | `openpyxl` → Answer Sheet | ~100% when available, but no schools are known to publish this format |
| **Tier 2** | Unflattened fillable PDF | **this tool** | **~100% when AcroForm is populated** |
| Tier 3 | Filled DOCX | `python-docx` → Word tags | ~100% when available (not yet observed in the wild) |
| Tier 4 | Flattened PDF | Docling/Reducto + cleaner | variable, hard path |
| Tier 5 | Image-only scan | OCR + cleaner | worst case |

Tier 2 works if and only if `pypdf.get_fields()` returns a non-empty dict for the source PDF. Flattened PDFs (Yale 2024-25, Harvard 2024-25) return `None` and need Tier 4. The scraper should probe every incoming PDF with this check first before routing to a heavier pipeline.

## Origin story

This tool exists because of a realization we should have had earlier: Harvey Mudd's 2025-26 CDS, the exact school our initial Docling audit documented as "degraded with real data corruption" (see [`docs/known-issues/harvey-mudd-2025-26.md`](../../docs/known-issues/harvey-mudd-2025-26.md)), is an unflattened fillable PDF with **1,026 AcroForm fields and 558 populated**. Every ground-truth value Docling misaligned is sitting in a named form field that `pypdf.get_fields()` reads correctly. The C1 row-shift "Docling bug" was never a bug at the source. We were using the wrong tool on a source that had structured data ready to read.

## Usage

```bash
# Extract canonical JSON to stdout
python tools/tier2_extractor/extract.py \
    scratch/CDS-HMC-2025.2026_shared.pdf \
    schemas/cds_schema_2025_26.json

# Write to file, print a summary to stderr
python tools/tier2_extractor/extract.py \
    scratch/CDS-HMC-2025.2026_shared.pdf \
    schemas/cds_schema_2025_26.json \
    --output /tmp/hmc_tier2.json \
    --summary
```

Example summary output:

```
[CDS-HMC-2025.2026_shared.pdf]
  acroform fields (populated): 558
  schema fields total:         1089
  schema fields populated:     558 (51%)
  unmapped acroform tags:      0
```

`unmapped acroform tags: 0` is what you want to see. It means every field name the PDF uses is known to the schema for that year. A non-zero count indicates either a drifted schema year or a school that added custom fields; both are worth investigating.

## Output JSON shape

```json
{
  "producer": "tier2_acroform",
  "producer_version": "0.1.0",
  "schema_version": "2025-26",
  "source_pdf": "CDS-HMC-2025.2026_shared.pdf",
  "extracted_at": "2026-04-13T06:30:00Z",
  "stats": {
    "acroform_fields_total": 558,
    "schema_fields_total": 1089,
    "schema_fields_populated": 558,
    "unmapped_acroform_fields": 0
  },
  "values": {
    "C.101": {
      "value": "3452",
      "pdf_tag": "AP_RECD_1ST_MEN_N",
      "word_tag": "c1_total_first_time_first_year_males_who_applied_total",
      "question": "Total first-time, first-year males who applied",
      "section": "First-Time, First-Year Admission",
      "subsection": null,
      "value_type": "Number"
    }
  },
  "unmapped_fields": []
}
```

Only populated fields are emitted. Downstream consumers who want a full-coverage view can join this output against the schema to see which canonical fields are absent.

The `values` dict is keyed by canonical `question_number`, which is the stable cross-school join key. A consumer asking "what did every school report for C.101?" iterates `values["C.101"]` across every school's Tier 2 output.

## Field maps (PRD 038)

`build_field_map.py` harvests a per-year *field map* of the official fillable
template: for every AcroForm field, its `question_number` (joined by `pdf_tag`
to that year's `schemas/cds_schema_YYYY_YY.json`), schema `value_type`, `ft`,
widgets (`template_page`, normalized `rect`, `on_state` for buttons,
`static_text` printed inside the rect), and `/Opt` `[export, display]` pairs.
Each page also carries a 36-DPI static-ink mask (gray < 225). Maps live in
`schemas/field_maps/cds_pdf_field_map_YYYY_YY.json`; output is deterministic
(sorted keys, one line per field/page, masks as a hand-written RLE so it does
not depend on the zlib build). `decode_mask()` and `load_field_map()` are the
read seams for template matching.

**Coordinates** (also written to every map under `coordinates`): rects are PDF
user space in points (1/72 in), origin bottom-left, y increasing upward,
`[x0, y0, x1, y1]` with x0 < x1 and y0 < y1; page indexes are 0-based. Mask row 0
is the top of the page and each pixel covers 2x2 pt: `row = (page_height_pt - y) / 2`,
`column = x / 2`. Static text is the characters whose box center lies inside the rect.

```bash
python tools/tier2_extractor/build_field_map.py --year 2025-26 [--check]   # also 2024-25, 2023-24
python -m pytest tools/tier2_extractor -q
# optional 2024-25 donor cross-check (filled Tier 2 PDFs, never committed):
CDS_2024_25_DONORS=a.pdf:b.pdf python -m pytest tools/tier2_extractor -q
python tools/tier2_extractor/build_field_map.py --year 2024-25 --donor a.pdf --donor b.pdf \
    --out scratch/prd038/donor_check.json
```

All three years build from the official blank PDFs in `schemas/templates/`
(`*.pdf` is gitignored; new templates need `git add -f`), and the tests demand a
byte-exact rebuild when the recorded pypdfium2 version matches (the repo pins
5.15.1). With a different pdfium build the masks may differ by ~0.3% of ink, so
the test allows 1% there; everything else is still compared exactly.

**Donor consensus (cross-check only).** For 2024-25 the builder can also merge two
or more filled donors; every widget must agree within 0.5 pt or the build fails.
Donors draw their static layer from page content with annotations and form
widgets not drawn, because filled values normally live in widget annotations.
That assumption is not guaranteed: UW-Madison's 2024-25 PDF has typed text and
edits in its page content stream (about 460 px over pages 14, 21 and 24). So
the ink mask is a strict-majority vote across donors (a pixelwise AND for two),
and static text takes the most common string across donors. A tie (even donor
count only) is broken by the lexicographically smallest string; disagreements
are counted in `stats.text_disagreements` and the cross-check test requires 0.
With four donors the consensus matches the official blank: same fields, `/Opt`,
on-states and static text, 0 differing mask pixels, rects within 0.002 pt.

**Schema join.** Duplicate `pdf_tag`s in a year's schema make the build raise
(Tier 2's `extract.py` keeps the last duplicate silently; the schema fix below
removes the only known case). `tags_not_in_schema` in each map's `stats` counts
AcroForm tags the year's schema has no `pdf_tag` for (2025-26: 2, 2024-25: 302,
2023-24: 276); their `question_number` is null, matching what Tier 2 drops
today. Deciding how to join them is separate work. Needs `numpy` and `pypdfium2`.

## Template overlay extraction (PRD 038 M1)

`template_overlay.py` reads a *flattened* print of an official CDS template at the
field map's widget coordinates (Stage 1 template match, Lane 1 text layer, Lane 3
checkboxes and radios, validation). It is a pure library (bytes in, dict out; no
database, network or worker access). Lane 2 (OCR of vector-drawn pages) and the
worker/DB wiring are later milestones; pages and widgets that need OCR are listed in
`notes.pages_needing_ocr` and `notes.ocr_widgets`. The governing rule: **a missing
value is acceptable, a wrong emitted value is not**, so every doubtful read abstains and
is recorded in `notes.withheld` (abstentions) or `notes.rejected_fields` (parse and
identity failures), each with a named rule.

```bash
python tools/tier2_extractor/template_overlay.py school.pdf [--detected-year 2025-26] > overlay.json
python tools/tier2_extractor/template_overlay.py school.pdf --match-only      # Stage 1 only
python -m pytest tools/tier2_extractor -q                                      # synthetic fixtures, no school PDFs
CDS_M1_PDF_DIR=/path/to/review/pdfs python -m pytest tools/tier2_extractor -q -k real
```

- **Year.** The printed page header ("Common Data Set YYYY-YYYY") is compared with each
  year's blank (2023-24 included) at 144 DPI, cropped at the page's applied shift (±4 px
  residual search). A page votes when the best year beats the next by 0.01 and its diff is
  under 0.85 of the crop's own ink (a blank or misplaced crop votes for nothing). The year is
  the plurality of votes (≥ 5) and must agree with the best raster year. The rule is strict:
  one *confident* other-year vote (margin ≥ 0.02 and diff ≤ 0.6 of the ink) holds the whole
  packet (`mixed_year_packet`); weak other-year votes (poorly fitting headers of sub-point
  shifted prints scored 0.68-0.74) cannot hold it, but that page is not read
  (`weak_other_year_vote`). A page that will be rejected for alignment casts no
  vote. Ties, contradictions and unverifiable headers hold the document
  (`template_year_ambiguous`, nothing emitted); a 2023-24 print is
  `template_year_unsupported`. A matched page whose own raster score in another year beats
  the chosen year's by > 0.02 is not read (`page_raster_prefers_other_year`). `detected_year`
  can only veto; `cds_year` is never used. A forced-year run exists only as
  `_diagnostic_extract_forced_year` for the evaluation script.
- **Pages.** Each target page is rendered like the committed masks (36 DPI, ink gray
  < 225) and scored against every template page: recall of the template's static ink
  (two 4-neighbour dilations), clamped by precision (`min(recall, precision + 0.25)`).
  Pages are assigned monotonically (dropped and inserted pages are fine), a pair is kept
  only when the template page is within 0.02 of the page's best match (blank pages 8, 38,
  41 cross-match), and a template page claimed by several target pages is rejected
  (`duplicate_page_conflict`) unless they agree on every answer: candidates with a native text
  layer are compared by the text read at each `/Tx` and `/Ch` rect, buttons and raster-only
  candidates by ink at 216 DPI (any 3 differing pixels, or a rect that cannot be compared,
  mean equality is not established).
- **Geometry.** Text boxes, widget rects, static-template characters and rendered crops
  all use one space derived from PDFium's page transform (CropBox ∩ MediaBox origin,
  `/Rotate`, uniform page scale; shifts are in template points and scale with the page).
  Pages that cannot be mapped exactly are rejected.
- **Alignment.** The page shift is applied only when every inked horizontal band agrees
  with it within 1 pt; otherwise the page is rejected (`partial_page_shift`) or, with no
  shift, the disagreeing band's widgets abstain (`band_misaligned`). A page is also rejected
  (`residual_page_shift`) when its optimum sits on the ±8 pt search boundary, or when most
  inked bands agree on a shift more than 1 pt from the applied one, whatever the gain (a
  10-12 pt page shift otherwise leaves a 2-4 pt residual that reads empty boxes as checked). Each widget is also
  checked on its own: its template static ink within 14 pt must not fit a shifted target
  ≥ 0.10 better in x or y (ignoring shifts the blank itself cannot tell from 0, like one
  table-row period): `local_misalignment`.
- **Lane 1.** Characters whose box centre lies inside the widget rect, no padding;
  characters that coincide with a blank-template character there are the label and are
  dropped. Never read: control/private-use/unassigned glyphs (the page is unreadable),
  noncharacters and format characters PDFium did not mark generated, and any widget with
  an **invisible** (render mode 3/7) glyph (`invisible_text`, an OCR layer; scheduled for
  Lane 2). A read also needs rendered ink the blank template lacks (`no_rendered_ink`).
  Numbers use one token grammar (commas only as `\d{1,3}(,\d{3})+`, no disjoint runs, no
  signs, ASCII digits), every percentage-typed field is 0-100, and the effective type used
  is recorded in each value. `/Ch` reads map to exports through `/Opt` (whitespace-
  insensitive; a clipped read must be the prefix of exactly one option; an exact match
  that is a proper prefix of another option abstains when it reaches the rect edge).
  **Edge guard** (Number, Text and /Ch alike; `edge_continuation`, also meant for Lane 2 crops):
  a non-form glyph on the read's line whose box crosses the rect's left or right edge, or lies
  within 1 pt outside it, means the rect cuts a longer string (`glyph_crosses_*_edge`,
  `glyph_past_*_edge`); a multi-line Text read with paragraph lines just above or below the rect
  abstains (`multiline_overflow`). Spaces pdfium generated between the read glyphs are kept even
  when they sit below the rect's centre line. `1.234` on any numeric field is a thousands
  separator or a misread, not a decimal: no numeric type takes three decimals
  (`ambiguous_thousands_separator`).
  **Numeric token gate** (`numeric_token_gate`; numeric class only; defined on boxes with a vertical
  extent and a text, so Lane 2's OCR word boxes use it unchanged): the token that holds the read
  grows over every box that overlaps its vertical extent and sits within 0.35 of a median character
  width (a sign, point, comma, percent or currency mark: 1.25), so a decimal point whose centre is
  far below the digits' still belongs to them. A token with a box whose centre is outside the rect
  (the rect holds part of a printed number, or a number crosses the rect's edge) abstains
  (`token_crosses_rect`), as does a token whose digits differ in height by more than 20% or stand on
  different baselines (`mixed_glyph_size`: a superscript or footnote marker); a uniformly small
  font reads. **Free text** has one more rule: a printed line with glyph centres on both sides of the
  rect's top or bottom edge is cut by the rect (`line_straddles_rect`).
- **Lane 3.** Each box is measured where the print draws it: the white interior enclosed by
  the box's own frame is found by flood fill from the rect's centre (confined to the rect + 3 pt;
  seeded by every white pixel near the centre so a check mark that splits the box still gives
  the whole box; one-pixel pinholes are closed when the fill is much bigger than the blank
  template's own interior, which is how a nested inner frame is told apart), and the mark is the
  ink density of its central 60%. The frame, bevel and template glyph are never inside the
  measured area, so an empty box scores ~0 at any sub-point phase and a mark ≥ 0.06 (cohort: 18,372
  scores within ±0.005, 27 between 0.001 and 0.03, none in [0.03, 0.04)). Checked at ≥ 0.04 after
  subtracting the ink the blank template itself has in that interior; a radio winner needs a 0.03
  margin. Abstentions: the template draws a box and the print's is not found (`box_not_closed`,
  `box_geometry`: not closed, not box-shaped, or not centred within 2.5 pt of the rect), the alignment
  gates, two checked boxes in a "fill in one only" group, two or more options of a group at or above
  the threshold (`multiple_options_marked`, before any winner margin), and ink in the winner's box
  that continues as a stroke or a text run beyond it into the row (`stroke_continues_beyond_box`:
  a strike-through, underline or overflowing word; two strips one box long beside the interior, past
  the frame, with the blank's own ink removed). Only ink darker than the interior-white level
  counts, so a uniformly gray paper, scan tone or box background is not a mark. Options with no box
  in the template (an N/A) are read from the rect core. The v0.2.0 rules this replaces (gray bands, blank-outline
  gate, border-in-interior) are removed, not disabled; PRD A9 lists what each cost.
- **Page registration (M2).** After the whole-point page shift, each page's static ink is registered to the
  blank at one INK_DPI pixel (1/3 pt, ±3 px) on the 216-DPI render (`refine_subpoint_shift`; the best recall is a
  plateau because the page ink is dilated one pixel, so its centre is taken; a residual must beat (0, 0) by 0.01).
  `PageCtx.dx/dy` are the whole-point shift plus this refinement and every lane reads through them, so a
  0.67 pt offset no longer reads Lane 3's frame as a mark (PRD A11).
- **Lane 2 (M2, `lane2_ocr.py`; gate and class changed in A12).** Numeric OCR at the widget rects of pages Lane 1
  cannot read (image-only pages, invisible-text pages, pages whose text is hidden under an image, unreadable pages),
  only for Number, Dollars, Percent, Identifier, Month and Day `/Tx` fields. Off unless asked for:
  `extract_overlay(pdf, lane2=make_hook(TesseractEngine()))`. Every value is `emission_class: ocr_numeric`, `lane: 2`,
  never served by default, and a total derived from a Lane 2 value is `ocr_numeric` too (`derived_lanes`); Lane 2 may
  veto (an identity failure withholds every member) but never vouches for a Lane 1 value. A value is emitted only when:
  the rect holds ink the blank lacks; the gates pass on the OCR word boxes of the erased context crop and of the
  UNMODIFIED context crop (so erasing the blank's rule never hides a token's overlap with the cell edge); no ink sits at
  the tight crop's left or right edge or in a 1.5 pt strip beyond the cell; the ink is one contiguous token (no internal
  gap over 0.5 of the digit advance); the tight rect at 300 and 400 DPI and the context token agree; confidence ≥ 85;
  the number grammar passes; and a SECOND model (tessdata_best, Otsu-binarised tight crop, no digit whitelist) reads a
  string that parses to the same value (a letter, a space or a different digit abstains). Each failure is a named
  abstention (`notes.withheld`, lane `ocr`). The engine is the `tesseract` command line: it raises on a failed run, and at
  construction probes a known string with both models; a failed probe, a missing second model or a model whose sha256 is not
  the pinned one disables Lane 2 and records why (`notes.lane2_disabled`; fail closed). Fetch the second model with
  `python tools/tier2_extractor/fetch_tessdata.py` (sha256-verified; never committed; `CDS_TESSDATA_BEST` or
  `~/.cache/cds-tessdata/best`). `notes.ocr_engine` and `notes.ocr_models` record the versions and shas. CI does not need
  Tesseract: its tests skip when it is absent.
- **Emission classes.** Every value carries `emission_class`: `numeric` (typed numerics read from the text layer, derived totals of text-layer values), `ocr_numeric` (Lane 2 and totals derived from it),
  `choice` (`/Ch`), `checkbox_box` (Lane 3 through a located box interior), `checkbox_boxless` (Lane 3 where
  the blank draws no box), `free_text`. The shadow artifact keeps every class; `serve_values(values,
  classes=SERVE_CLASSES_DEFAULT)` filters, and the default serves `numeric`, `choice` and
  `checkbox_box` only. `checkbox_boxless` and `free_text` are shadow-only until M3 decides per class
  (PRD A10).
- **Validation.** Identity failures (B1, C1, C9) reject every value in the identity, in
  every lane. Then `apply_b1_derived_all_totals`. Fields whose map entry has no
  `question_number` are skipped and counted.

`eval_template_overlay.py` reproduces the acceptance numbers from local PDFs (`stage1`,
`cohort` with the real metadata path or a labelled `--oracle` run, `compare`,
`wrong-year`, `old-vs-new`); see its docstring for the inputs.

## Tested against

| PDF | AcroForm populated | Result |
|---|---:|---|
| `CDS-HMC-2025.2026_shared.pdf` | 558 / 1089 (51%) | 13/13 ground-truth spot checks match, 0 unmapped tags |
| `yale_cds_2024-25_rmd_20250612.pdf` | 0 | flattened — Tier 2 not available |
| `HarvardUniversity_CDS_2024-2025.pdf` | 0 | flattened — Tier 2 not available |
| `CDS-PDF-2025-2026_PDF_Template.pdf` | 75 | blank template with SUM-formula zeros |

Ground truth checked on HMC:

```
B1 full-time first-year men    109    EN_FRSH_FT_MEN_N        B.101
B1 full-time first-year women  125    EN_FRSH_FT_WMN_N        B.126
C1 applied men                 3452   AP_RECD_1ST_MEN_N       C.101
C1 applied women               1761   AP_RECD_1ST_WMN_N       C.102
C1 applied unknown             4      AP_RECD_1ST_UNK_N       C.103
C1 applied total               5217   AP_RECD_1ST_N           C.116
C1 admitted men                276    AP_ADMT_1ST_MEN_N       C.104
C1 admitted women              365    AP_ADMT_1ST_WMN_N       C.105
C1 admitted unknown            2      AP_ADMT_1ST_UNK_N       C.106
C1 admitted total              643    AP_ADMT_1ST_N           C.117
C2 waitlist offered            685    AP_RECD_WAIT_N          C.202
C2 waitlist accepted           439    AP_ACPT_WAIT_N          C.203
C2 waitlist admitted           0      AP_ADMT_WAIT_N          C.204
```

Every value matches the hand-verified numbers in [`tools/extraction-validator/ground_truth/harvey-mudd-2025-26.yaml`](../extraction-validator/ground_truth/harvey-mudd-2025-26.yaml).

## Known gaps

1. ~~**Checkbox values are cryptic.**~~ **Fixed in producer v0.2.0.** AcroForm button widgets still return PDF export values like `/VI`, `/X`, `/NON`, `/SAME`, `/P` in the raw `value` field, but the extractor now also emits a `value_decoded` field with the human-readable label sourced from `value_options` on the schema entry. See `tools/schema_builder/decode_checkboxes.py` for how the decoder map is built and maintained. Consumers can use `value` for provenance and `value_decoded` for display. Example from HMC: `C.701` (rigor of secondary school record) returns `{"value": "/VI", "value_decoded": "Very Important", ...}`.

2. **Header/metadata fields are sometimes blank.** HMC's AcroForm has no value for `NAME` (`A.101` — name of institution) or the respondent address fields, even though the visible PDF clearly shows them. The institution filled the data tables but left the header fields for the Adobe template to render from elsewhere. For those canonical fields, the extractor emits nothing and the downstream consumer should prefer external metadata (the `schools.yaml` entry the scraper used to find the PDF, or the `cds_documents.school_name` column in the manifest). The schema builder could eventually flag "prefer external" fields.

3. **No school-identity detection.** This tool extracts values. It does not know which school the PDF is for. That mapping is the scraper's job — it knew which school it was downloading when it fetched the file. The Tier 2 output deliberately omits `school_id` / `school_name` so that callers cannot accidentally rely on extractor-provided identity.

4. **Pypdf xref warnings.** Some PDFs (Yale specifically) emit "Ignoring wrong pointing object" warnings during `PdfReader` construction. These are harmless — pypdf is repairing a mildly broken cross-reference table — but they clutter stderr. Suppressed with a `warnings.catch_warnings()` block in the extractor, but if a user runs `pypdf` directly they will see them.

5. **Value strings are not type-coerced.** Every value is emitted as a string, even when the schema's `value_type` says `Number`. The schema carries enough metadata for downstream code to coerce per field; this tool intentionally does not lose fidelity by parsing at extraction time. (Original string preserved for provenance.)

## Tier 2 vs Tier 4 routing

The scraper should probe every incoming PDF:

```python
import pypdf
reader = pypdf.PdfReader(pdf_path)
fields = reader.get_fields()
if fields and any(f.get("/V") is not None for f in fields.values()):
    tier = "tier2"      # route to tools/tier2_extractor
else:
    tier = "tier4"      # route to Docling/Reducto + cleaner
```

Store the detected tier alongside the manifest row so consumers can filter by producer quality.

## See also

- [`tools/schema_builder/`](../schema_builder/) — builds the canonical schema JSON this tool consumes
- [`schemas/cds_schema_2025_26.json`](../../schemas/cds_schema_2025_26.json) — the 2025-26 canonical schema
- [`tools/extraction-validator/`](../extraction-validator/) — neutral scorer for comparing producers against hand-verified ground truth
- [`docs/known-issues/harvey-mudd-2025-26.md`](../../docs/known-issues/harvey-mudd-2025-26.md) — the correction record explaining why this tool exists
