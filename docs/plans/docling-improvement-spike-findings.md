# Docling improvement spike findings

**Status:** Rough initial code audit
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
artifact contract.

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
  spike because it avoids DB writes and already supports config comparisons.
- `tools/extraction_worker/tier4_llm_fallback.py` has a good "cleaner wins, fallback
  fills gaps" design, but its strategy is named `markdown_section_fill_gaps`, which is
  accurate: it is currently a markdown repair layer, not a document-model repair layer.

## Suggested next experiment

Start with the validator harness, not production extraction:

1. Pick 5-10 PDFs with known Tier 4 C9/C11/C12 gaps.
2. Extend `run_matrix.py` or add a sibling inspector that writes:
   - markdown
   - Docling dict/JSON
   - table count
   - per-table DataFrame/CSV/HTML/markdown exports
   - page numbers and item refs if available
3. Score whether native Docling tables expose the missing GPA/SAT/ACT fields.
4. Only then decide whether PRD 011 should prioritize:
   - native table parsing
   - better Docling options
   - page-image crop repair
   - Docling beta extraction
   - DeepSeek-OCR sidecar repair

## Initial conclusion

We are close on routing and extraction policy, but far off on the Docling data model
best practices. The current pipeline uses Docling's conversion engine but mostly
discards the structured representation that makes Docling valuable for table-heavy
repair. The first implementation move should be an artifact/inspector spike around
Docling JSON and native tables, not a VLM repair script.
