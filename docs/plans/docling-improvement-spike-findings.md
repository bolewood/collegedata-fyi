# Docling improvement spike findings

**Status:** Initial code audit plus native-table spike harness
**Created:** 2026-04-26
**Related:** [PRD 0111A](../prd/0111A-docling-improvement-spike.md), [PRD 011](../prd/011-academic-profile-llm-repair.md), [Extraction Quality](../extraction-quality.md)

## Summary

The current extraction code uses Docling in the right broad role: flattened PDFs go
through Docling, fillable PDFs/XLSX take deterministic paths, and scanned PDFs are
routed to OCR. The trust boundary around LLM fallback is also directionally good:
deterministic extraction wins, LLM output fills gaps, and values must pass validation.

The main gap is representation. Production Tier 4 treats Docling primarily as a
markdown producer. It asks Docling for a `DoclingDocument`, but immediately exports to
markdown and stores only markdown plus cleaned values. The richer document/table/page
model is not persisted in production artifacts, not parsed by the cleaner, and not
available to the browser projection or repair layers.

There is one important exception: the extraction validator bakeoff already writes
`doc.export_to_dict()` to `output.json`. So the project has already experimented with
Docling JSON locally, but that capability has not been promoted into the production
artifact contract. Important caveat: the harness still scores markdown. It does not
prove a JSON/table parser would beat the current production cleaner unless the spike
adds a narrow parser comparison arm.

## What approaches best practice

| Area | Current behavior | Assessment |
|---|---|---|
| Tier routing | `pdf_fillable` uses deterministic AcroForm extraction; `pdf_flat` and `pdf_scanned` route to Docling; `xlsx` uses deterministic cell mapping. | Good. This matches the "cheapest reliable extractor first" principle. |
| OCR routing | `pdf_scanned` routes through Tier 4 with `force_ocr=True`, and `tier4_extractor` sets `EasyOcrOptions(force_full_page_ocr=True)`. | Good for scanned PDFs, though docs/comments are slightly stale in places. |
| Table structure | Tier 4 enables `pipeline.do_table_structure = True`, `TableFormerMode.FAST`, and cell matching. | Good baseline, but only the markdown serialization is consumed. |
| Config bakeoff | `tools/extraction-validator/run_matrix.py` can test multiple Docling configs and writes markdown plus JSON outputs. | Strong foundation for the spike. Needs updated configs for current Docling features. |
| LLM fallback trust boundary | Fallback consumes markdown, fills gaps only, requires evidence substrings, caches by markdown hash, and writes a separate artifact. | Good policy shape. Evidence should eventually point to Docling page/table/items, not only markdown. |
| Source classification | `tools/tier_probe` classifies fillable, flat, scanned, xlsx, docx, and other. | Good coarse routing. Could add richer weak-text/scanned diagnostics. |

## Main gaps

| Area | Current behavior | Best-practice gap | Impact | Recommendation |
|---|---|---|---|---|
| Artifact representation | `tier4_extractor.extract()` calls `doc.export_to_markdown()` and returns `markdown` + `values`. | Does not persist lossless Docling JSON / native document model. | Later parsers and repair layers cannot inspect table grid, item refs, boxes, or reading order without rerunning conversion. | Add a Tier 4 artifact payload field or sidecar artifact for compact `doc.export_to_dict()` / lossless JSON. |
| Native tables | Cleaner parses pipe-delimited markdown only. | Does not inspect `doc.tables`, `TableItem`, or DataFrame/native grid exports. | C9/C11/C12 may be recoverable before any VLM work, but current code cannot tell. | Build a narrow table-object inspector before DeepSeek-OCR repair. |
| Provenance | Values are keyed by question number with `source: tier4_cleaner`; page/table/item evidence is absent. | No page number, table id, item ref, cell box, or crop coordinate. | Browser values and repair candidates cannot be visually grounded. | Extend extraction output for new values with source page/table/item metadata where available. |
| Page images/crops | Production Tier 4 sets `images_scale = 1.0` but does not request/persist page images. | Cannot deterministically target VLM/OCR repair crops. | DeepSeek-OCR would likely start from full pages or rerendered pages instead of Docling-localized crops. | Add a spike config that enables page image generation and records artifact paths/hashes. |
| Current Docling feature verification | Requirements say `docling>=2.0`; local global Python does not have Docling installed. | Installed worker version/features are not visible in this workspace; no pin to Heron/lossless JSON/schema extraction. | Current behavior may drift as Docling changes; spike cannot assume docs features exist in deployed worker. | Record runtime versions during spike and consider pinning once a config is chosen. |
| Schema extraction beta | No `DocumentExtractor` usage. | Could be useful as candidate generation, but no evidence that it returns boxes/items. | Not a blocker; should not replace deterministic parser. | Test only as an optional comparison arm. Reject default-filled values. |
| LLM fallback substrate | Fallback hashes and cites `notes.markdown`. | It inherits markdown lossiness. | A value can be valid relative to markdown but still not traceable to page/table/cell. | Keep fallback policy, but feed it better slices/evidence after Docling JSON is persisted. |
| Fixture risk | Early PRD drafts named Harvard/Yale/Dartmouth as fixtures. | These are likely high-quality/easy publishers and can bias the conclusion. | Spike may prove JSON works on easy cases while missing the real Tier 4 failure population. | Sample from low-coverage `tier4_docling` `pdf_flat` artifacts first; keep elite docs as sanity checks only. |
| Outcome thresholds | Outcome labels were qualitative. | No pre-committed line between "JSON helps" and "JSON should become primary." | Decision could become post-hoc and preference-driven. | Use explicit thresholds before running: 70% target-field recovery for Outcome A, 80% localization for Outcome C. |
| Storage strategy | Initial recommendation allowed inline field or sidecar artifact. | Storage shape changes API/query performance and migration cost. | `select notes` patterns may balloon if large Docling JSON is stored inline. | Measure sample sizes and choose inline JSONB vs sidecar row vs object storage in the decision memo. |
| Producer precedence | New Tier 4 producer/version would create newer artifacts. | Existing manifests often pick by recency. | Reprocessing can silently switch consumers to a worse artifact. | Require producer-precedence semantics before shipping a JSON-first producer broadly. |
| Cache invalidation | `tier4_llm_fallback` cache is keyed by `markdown_sha256`. | JSON-first or serializer changes may invalidate existing cache entries. | Re-running fallback across thousands of docs has real cost. | Estimate cache impact and add serializer/config versioning before changing production markdown. |

## Code observations

- `tools/extraction_worker/tier4_extractor.py` imports Docling, builds
  `PdfPipelineOptions`, converts to `result.document`, then immediately exports
  markdown. It records `page_count`, `markdown_length`, and `schema_fields_populated`,
  but not the Docling document dict or table metadata.
- `tools/extraction_worker/tier4_cleaner.py` is explicitly a markdown cleaner. Its
  first parsing primitive is `_parse_markdown_tables(markdown)`.
- `tools/extraction_worker/worker.py` writes canonical artifacts inline to
  `cds_artifacts.notes`. For Tier 4, that means the markdown and cleaned values become
  the durable contract.
- `tools/extraction-validator/run_matrix.py` already writes both `output.md` and
  `output.json` using `doc.export_to_dict()`. This is the easiest place to start the
  spike because it avoids DB writes and already supports config comparisons. It still
  validates markdown output, so it needs a new table/JSON parser arm before it can
  support claims about production parser quality.
- `tools/extraction_worker/tier4_llm_fallback.py` has a good "cleaner wins, fallback
  fills gaps" design, but its strategy is named `markdown_section_fill_gaps`, which is
  accurate: it is currently a markdown repair layer, not a document-model repair layer.

## Suggested next experiment

Start with the validator harness, not production extraction, but tighten the experiment:

1. Record the exact Docling/docling-core/OCR versions from the worker environment.
2. Pick 8-12 PDFs from real low-coverage `tier4_docling` `pdf_flat` artifacts, plus
   1-2 elite sanity fixtures.
3. Pre-commit thresholds:
   - Outcome A: at least 70% C9/C11/C12 target-field recovery with a narrow parser.
   - Outcome C: below 70% recovery but at least 80% page/table localization.
   - Otherwise keep DeepSeek-OCR as the primary repair path.
4. Add a narrow throwaway C9 parser if making claims about JSON/native-table recovery.
   Without that parser, the spike can only conclude that native structure is present or
   absent.
5. Extend `run_matrix.py` or add a sibling inspector that writes:
   - markdown
   - Docling dict/JSON
   - table count
   - per-table DataFrame/CSV/HTML/markdown exports
   - page numbers and item refs if available
6. Measure:
   - target-field recovery
   - localization success
   - conversion failure rate
   - sample JSON artifact size
   - expected fallback cache invalidation
7. Only then decide whether PRD 011 should prioritize:
   - native table parsing
   - better Docling options
   - page-image crop repair
   - DeepSeek-OCR sidecar repair

Out of scope unless time remains:

- Docling beta schema extraction
- GraniteDocling / Small Docling
- production artifact migration

## Operationalization started

Two spike tools now exist under `tools/extraction-validator/`:

- `select_docling_spike_fixtures.py` selects low-coverage `tier4_docling`
  `pdf_flat` artifacts from Supabase and optionally downloads the source PDFs into
  `.context/docling-spike/fixtures/`.
- `inspect_docling_native.py` runs Docling conversion over those PDFs and writes:
  markdown, Docling JSON, per-table CSV/HTML/markdown exports, table provenance, a
  rollup summary, package versions, and a narrow C9 SAT/ACT heuristic.
- `compare_docling_full_cleaner.py` runs the existing full Tier 4 markdown cleaner
  against two Docling run directories and compares all recovered canonical fields.
- `compare_docling_native_tables.py` bypasses markdown table parsing and feeds rows
  reconstructed from native Docling table cells into the existing resolver logic.

Local Docling evaluation environment:

```text
/Users/santhonys/docling-eval/bin/python
docling==2.85.0
docling-core==2.72.0
docling-ibm-models==3.13.0
docling-parse==5.8.0
easyocr==1.7.2
rapidocr==3.8.0
torch==2.11.0
pandas==2.3.3
```

Smoke commands:

```bash
/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/select_docling_spike_fixtures.py \
  --env .env.local \
  --limit 1 \
  --candidate-limit 300 \
  --download

/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/inspect_docling_native.py \
  --manifest .context/docling-spike/fixtures/manifest.json \
  --config production \
  --out-dir .context/docling-spike/native-runs-smoke
```

Smoke result on `farmingdale-state-college` 2024-25:

- source artifact was `pdf_flat`, current Tier 4 artifact had 22 schema fields
  populated
- Docling production-like config converted 29 pages in about 16 seconds
- native output contained 39 tables
- table provenance included page number, bbox, and Docling item ref
- the narrow C9 heuristic recovered:
  - `sat_ebrw_p25/p50/p75 = 520/570/620`
  - `sat_math_p25/p50/p75 = 520/570/620`
  - `act_composite_p25/p50/p75 = 20/25/28`

This is not enough to declare Outcome A. It is enough to prove the operational path:
we can select real failure fixtures, download archived sources with the local anon
Supabase env, run Docling native inspection, and produce parser-facing table evidence
without touching production extraction.

## Ivy sanity run

Command:

```bash
/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/inspect_docling_native.py \
  --manifest .context/docling-spike/ivy-fixtures/manifest.json \
  --config production \
  --out-dir .context/docling-spike/ivy-native-runs
```

Fixture set:

- `harvard` 2024-25
- `yale` 2024-25
- `dartmouth` 2025-26
- `princeton` 2024-25
- `brown` 2024-25
- `columbia` 2024-25

Cornell was intentionally skipped for this Docling sanity run because recent Cornell
artifacts are fillable PDF or XLSX, not Tier 4 flat PDFs.

Results:

| School | Pages | Native tables | Runtime | Narrow C9 fields recovered |
|---|---:|---:|---:|---:|
| Harvard 2024-25 | 32 | 41 | 12.7s | 9 |
| Yale 2024-25 | 43 | 69 | 15.3s | 14 |
| Dartmouth 2025-26 | 34 | 45 | 22.4s | 12 |
| Princeton 2024-25 | 43 | 40 | 12.2s | 12 |
| Brown 2024-25 | 37 | 95 | 22.0s | 14 |
| Columbia 2024-25 | 50 | 41 | 16.4s | 14 |

The narrow heuristic recovered SAT/ACT percentile rows for every Ivy fixture. It also
found SAT/ACT submission rates for Yale, Brown, and Columbia. Harvard lacks a direct
SAT composite row in this heuristic output because the table exposes EBRW and Math
component rows; a production parser would need explicit rules for whether and how to
derive composite values from component rows.

This is a sanity set, not the failure-stratified decision set required by PRD 0111A.
The takeaway is that native Docling tables are very usable on high-quality flat PDFs,
with page/bbox/item provenance available for the relevant tables.

## Recent failure-stratified run

After the Ivy sanity check, the spike selected a corrected 2024-25+ fixture set from
low-coverage `tier4_docling` `pdf_flat` canonical artifacts. Selection now filters by
`cds_year` first and falls back to `detected_year` only when `cds_year` is missing,
which avoids admitting stale-year documents because of detected-year noise.

Command:

```bash
/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/select_docling_spike_fixtures.py \
  --env .env.local \
  --limit 10 \
  --candidate-limit 600 \
  --min-fields 20 \
  --min-year 2024-25 \
  --max-per-school 1 \
  --download \
  --out-dir .context/docling-spike/failure-fixtures-2024-plus-v2

/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/inspect_docling_native.py \
  --manifest .context/docling-spike/failure-fixtures-2024-plus-v2/manifest.json \
  --config production \
  --out-dir .context/docling-spike/failure-native-runs-2024-plus-v2-production
```

Results:

| School | Year | Pages | Native tables | Runtime | Narrow C9 fields recovered |
|---|---:|---:|---:|---:|---:|
| Farmingdale State College | 2024-25 | 29 | 39 | 14.8s | 9 |
| Franklin and Marshall College | 2024-25 | 28 | 37 | 10.3s | 9 |
| DeSales University | 2024-25 | 30 | 39 | 11.4s | 9 |
| Emory | 2024-25 | 26 | 43 | 11.6s | 12 |
| Michigan State University | 2024-25 | 50 | 39 | 12.2s | 12 |
| Dominican University | 2025-26 | 40 | 48 | 19.3s | 12 |
| Gettysburg College | 2024-25 | 26 | 33 | 10.2s | 9 |
| Lafayette College | 2025-26 | 43 | 39 | 12.4s | 12 |
| Lehigh | 2025-26 | 24 | 37 | 10.7s | 12 |
| Kennesaw State University | 2024-25 | 26 | 38 | 11.6s | 12 |

Totals:

- 10/10 documents produced C9 SAT/ACT candidates.
- 108 C9 field candidates were recovered.
- Production-like Docling config runtime was 124.6s total.
- Docling's current defaults recovered the same 108 candidates but took 203.9s.

The same two run directories were then compared with the full existing Tier 4
cleaner, not just the C9 heuristic:

```bash
/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/compare_docling_full_cleaner.py \
  --manifest .context/docling-spike/failure-fixtures-2024-plus-v2/manifest.json \
  --left-label production \
  --right-label docling-default \
  --left-dir .context/docling-spike/failure-native-runs-2024-plus-v2-production \
  --right-dir .context/docling-spike/failure-native-runs-2024-plus-v2-docling-default \
  --out .context/docling-spike/failure-native-runs-2024-plus-v2-full-cleaner-comparison.json
```

Full-cleaner comparison:

| School | Year | Production fields | Docling default fields | Overlap | Production only | Default only | Conflicts |
|---|---:|---:|---:|---:|---:|---:|---:|
| Farmingdale State College | 2024-25 | 354 | 365 | 348 | 6 | 17 | 0 |
| Franklin and Marshall College | 2024-25 | 367 | 336 | 334 | 33 | 2 | 0 |
| DeSales University | 2024-25 | 344 | 359 | 344 | 0 | 15 | 1 |
| Emory | 2024-25 | 378 | 379 | 376 | 2 | 3 | 0 |
| Michigan State University | 2024-25 | 290 | 296 | 290 | 0 | 6 | 0 |
| Dominican University | 2025-26 | 401 | 380 | 373 | 28 | 7 | 0 |
| Gettysburg College | 2024-25 | 389 | 389 | 387 | 2 | 2 | 0 |
| Lafayette College | 2025-26 | 416 | 409 | 397 | 19 | 12 | 1 |
| Lehigh | 2025-26 | 338 | 343 | 337 | 1 | 6 | 1 |
| Kennesaw State University | 2024-25 | 468 | 467 | 462 | 6 | 5 | 0 |

Full-cleaner totals:

- Production-like config: 3,745 canonical fields.
- Docling default config: 3,723 canonical fields.
- Overlap: 3,648 fields.
- Production-only: 97 fields.
- Default-only: 75 fields.
- Conflicting shared values: 3 fields.

This still is not ground-truth scoring. It tells us the current full markdown cleaner
is broadly stable across both Docling serializations, production-like config is
slightly ahead on total recovered fields in this sample, and Docling defaults do not
show a clear recovery advantage despite being slower. The three conflicts are exactly
why the next step should be ground-truth spot scoring or deterministic value
validation before changing extraction precedence.

## Systematic tuning pass

The next tuning pass used the same corrected 2024-25+ ten-document fixture set and
changed one Docling variable at a time from the production-fast baseline. Runtime was
recorded in the run summaries but was not used as a decision criterion; the screening
metric here is full Tier 4 cleaner field recovery, plus config-only fields,
baseline-only fields, and conflicts.

| Config | Total fields | Delta vs production-fast | Config-only | Baseline-only | Conflicts |
|---|---:|---:|---:|---:|---:|
| `production-fast` | 3,745 | baseline | 0 | 0 | 0 |
| `table-accurate` | 3,723 | -22 | 75 | 97 | 3 |
| `ocr-off` | 3,745 | +0 | 0 | 0 | 0 |
| `force-backend-text` | 3,745 | +0 | 0 | 0 | 0 |
| `no-cell-matching` | 3,728 | -17 | 98 | 115 | 7 |
| `force-full-page-ocr` | 1,988 | -1,757 | 89 | 1,846 | 301 |
| `layout-keep-empty-clusters` | 3,651 | -94 | 0 | 94 | 23 |
| `layout-no-orphan-clusters` | 3,797 | +52 | 53 | 1 | 0 |
| `layout-skip-cell-assignment` | 2,560 | -1,185 | 53 | 1,238 | 1 |
| `layout-no-orphan-table-accurate` | 3,775 | +30 | 128 | 98 | 3 |

The first genuinely promising tuning variable is:

```python
pipeline.layout_options.create_orphan_clusters = False
```

With production-fast table settings, that produced 52 net additional fields and no
value conflicts against the baseline. The 53 config-only fields were concentrated in
Section C admissions requirements:

- Farmingdale State College: 5 new C5 high-school-unit fields.
- Franklin and Marshall College: 13 new C5 high-school-unit fields.
- Lehigh: 18 new C5 high-school-unit fields.
- Kennesaw State University: 16 new C5 high-school-unit fields.
- Gettysburg College: 1 new B field, while losing 1 I field.

This result is promising but not yet safe to ship. Field count is only a screening
metric; the new C5 values need ground-truth spot checks against source PDFs, and the
single lost baseline field should be inspected. Still, this is materially better than
the OCR/table-mode knobs: ACCURATE tables did not help overall, full-page OCR badly
degraded these text PDFs, and the layout no-orphan setting improved recoverability
without introducing conflicts in this sample.

Production follow-through:

- `tier4_extractor.py` now uses `producer_version = "0.2.0"` for new
  `tier4_docling` canonical artifacts.
- The Tier 4 Docling config sets
  `pipeline.layout_options.create_orphan_clusters = False`.
- New artifacts record the config under `notes.docling_config`.
- New artifacts persist compact native table cells under `notes.native_tables`.
  This is intentionally not merged into `notes.values` yet; it is substrate for
  deterministic native-table parsers and repair passes before any LLM fallback.
- A vision cross-check on Farmingdale page 9 confirmed the new C5 required-unit
  fields and caught one additional deterministic cleaner bug: Docling truncated
  the `Recommended` header to `Recommende` and wrapped a blank lab row into
  `Foreign language`. The C5 resolver now treats `recommend*` as recommended
  and prioritizes `Foreign language` / `Computer Science` before broader
  substring matches.

## Native JSON table parser arm

The spike then tested the larger "markdown is lossy" hypothesis directly. Instead of
parsing Docling's full-document markdown, `compare_docling_native_tables.py` reads
`docling.json`, reconstructs table rows from native `table_cells`, and feeds those
rows into the existing resolver logic. This is still not a purpose-built native
parser; it is an adapter test that answers whether the current resolver stack can
benefit from the native table model without going through `_parse_markdown_tables()`.

Command:

```bash
/Users/santhonys/docling-eval/bin/python \
  tools/extraction-validator/compare_docling_native_tables.py \
  --manifest .context/docling-spike/failure-fixtures-2024-plus-v2/manifest.json \
  --run-dir .context/docling-spike/tuning-2024-plus/layout-no-orphan-clusters \
  --table-source json \
  --out .context/docling-spike/tuning-2024-plus/compare-markdown-vs-native-json-layout-no-orphan.json
```

Result on the tuned `layout-no-orphan-clusters` run:

| Path | Total fields |
|---|---:|
| Markdown cleaner | 3,797 |
| Native JSON table adapter | 2,793 |
| Markdown plus JSON-only candidates | 3,900 |

Diff shape:

- Native JSON table adapter overlapped 2,690 markdown fields.
- Markdown-only fields: 1,107, concentrated in B, C, D, and I.
- Native-JSON-only fields: 103, concentrated in J disciplines (64), I faculty (30),
  C admissions (6), F student life (2), and B enrollment (1).
- Remaining conflicts after numeric normalization: 119, concentrated in B and C.

Interpretation:

- Native JSON is not yet a drop-in replacement for the markdown cleaner. The existing
  resolver stack has been tuned around Docling's markdown serialization, and native
  table cells require their own row/header/section adapter.
- Native JSON is still promising as an overlay/repair source: it surfaced 103
  candidates the markdown path did not claim, especially in J and I.
- The current adapter lacks enough section context and table-shape-specific logic to
  recover all fields that the markdown serializer currently flattens conveniently.
- The next native-parser step should not be a generic "feed all tables to old
  resolvers" pass. It should be section-specific native parsers that use Docling cell
  flags, row/column spans, page/table provenance, and explicit validation rules.

The narrower conclusion is stronger than the original audit but still bounded:
native Docling tables appear sufficient to recover common SAT/ACT percentile rows
from recent low-coverage flat PDFs. This is not yet ground-truth scoring. The
candidate parser still needs CDS-specific validation, conflict handling against
existing deterministic values, and explicit support for older/non-standard C9 layouts
before it can write production browser fields.

## Initial conclusion

We are close on routing and extraction policy, but far off on the Docling data model
best practices. The current pipeline uses Docling's conversion engine but mostly
discards the structured representation that makes Docling valuable for table-heavy
repair. The first implementation move should be to ground-truth the
`layout-no-orphan-clusters` tuning win and then promote a narrow native-table
parser/provenance path for academic profile fields. A VLM repair script should remain
behind deterministic Docling/parser improvements.

Red-team adjustment: the spike must not conclude "JSON parser works" from structure
inspection alone. It needs either a narrow parser arm or a deliberately narrower
conclusion: "Docling JSON contains enough structure to justify a follow-on parser PRD."
