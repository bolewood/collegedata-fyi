# PRD 008: Tier 6 HTML Extraction

**Status:** Draft
**Created:** 2026-04-20

---

## Context

A growing number of schools publish their Common Data Set as structured HTML
directly on their institutional research (IR) landing pages, not as a PDF, XLSX,
or DOCX download. The tiered extraction pipeline does not handle this. Today
these schools are unreachable: the discovery resolver looks for anchors that
point at downloadable documents and rejects pages that render CDS content
inline.

**MIT is the archetype.** https://ir.mit.edu/projects/2024-25-common-data-set/
serves the full CDS as a single HTML page with:

- All 10 sections as `<h3>` headings (`A. GENERAL INFORMATION` through
  `J. Disciplinary areas…`)
- Question numbers verbatim in `<strong>` tags (`A2.`, `B1.`, `C1.`, `I-1.`
  — note MIT uses `I-1` with a hyphen)
- Real `<table>` / `<thead>` / `<tbody>` markup with verbatim CDS row labels
- Server-rendered static DOM (no JS execution needed at extraction time)
- URL pattern `/projects/{YYYY}-{YY}-common-data-set/`

There is no `data-*` / `aria-` anchor set. Binding is purely
(question-number text × row-label text × column-header text), which is the
same join strategy Tier 4's cleaner uses on Docling-produced markdown — only
the source is cleaner structured HTML instead of recovered markdown.

**Why MIT drives this PRD now.** MIT is a top-20 school with zero CDS coverage
today. Their IR office has explicitly chosen HTML-first publication (likely
for WCAG accessibility reasons — screen readers parse HTML tables far better
than PDF tables). Other schools following the same accessibility pattern will
surface in discovery as HTML publishers, and the only thing blocking those
from landing in the corpus is an extractor that reads HTML. This PRD ships
that extractor.

## Premises

1. **Structured HTML is closer to canonical JSON than any flattened PDF.** MIT's
   HTML carries the section, question, row, and column structure verbatim in
   the DOM. The extractor's job is shape-transformation, not layout recovery.
   The pattern is closer to Tier 1 (XLSX cell map) and Tier 2 (AcroForm
   deterministic read) than to Tier 4 (Docling + layout cleaner).

2. **Question-number text is the stable anchor.** MIT uses verbatim CDS
   question numbers (`A2.`, `B1.`, `C1.`) in `<strong>` tags. These are the
   same canonical question numbers the schema already indexes. No
   `data-question="C1"` attribute is needed — the text content is the
   contract. MIT's `I-1.` (with a hyphen) is a minor variant the parser
   normalizes to `I.1`.

3. **Row-label text will paraphrase, and the alias table handles it.** CDS
   publishers paraphrase row labels slightly while keeping the semantic
   binding. MIT writes "Total first-time, first-year men who applied" for
   C.101 where the template row label is "Men." A small per-question alias
   table (JSON, committed, maintained per publisher pattern) resolves the
   residual cases. PRD 006's LLM fallback is the second line if the alias
   table misses.

4. **Server-rendered first. JS-rendered is a separate problem.** MIT's HTML
   is fully rendered in the initial response — no client-side React or
   Vue-driven fetches. If a later school turns out to be JS-rendered, we
   already have the Playwright URL collector from PRD 004 and can snapshot
   the rendered HTML at discovery time. The extractor in this PRD does not
   run a browser; it takes bytes and returns canonical JSON.

5. **Discovery archival must be extended.** Today the archive pipeline only
   accepts `application/pdf`, `application/xlsx`, `application/docx` MIME
   types (per the `sources` bucket `allowed_mime_types` constraint in the
   initial migration). HTML needs to land in the same bucket at the same
   SHA-addressed path convention with `text/html` MIME. Without this, the
   extractor has no input.

## What to build

### 1. Tier 6 extractor: `tools/tier6_html/extract.py`

Pattern after `tools/tier2_extractor/extract.py`:

```python
PRODUCER_NAME = "tier6_html"
PRODUCER_VERSION = "0.1.0"

def extract(html_path: Path, schema: dict) -> dict: ...
def extract_from_bytes(html_bytes: bytes, schema: dict) -> dict: ...
```

Both functions return the canonical shape every tier emits:

```json
{
  "producer": "tier6_html",
  "producer_version": "0.1.0",
  "schema_version": "2025-26",
  "source_html": "2024-25-common-data-set.html",
  "extracted_at": "2026-04-20T12:00:00Z",
  "stats": {
    "schema_fields_total": 1105,
    "schema_fields_populated": 137,
    "unmapped_cells": 4,
    "tables_seen": 64,
    "narrative_paragraphs": 12
  },
  "values": {
    "C.101": {
      "value": "17,448",
      "row_label": "Men",
      "col_label": "Total",
      "question": "Total first-time, first-year men who applied",
      "section": "First-Time, First-Year Admission",
      "subsection": "C1",
      "binding_strategy": "alias_table"
    }
  },
  "unmapped_fields": [...]
}
```

**Algorithm:**

1. **Parse.** BeautifulSoup (`lxml` backend) on the HTML bytes. No
   JavaScript execution.
2. **Section segmentation.** Walk top-level `<h3>` elements; keep those whose
   text matches `^[A-J]\.\s` (or `^[A-J]\s*\.\s*`). Each match opens a new
   section bucket; all subsequent siblings up to the next matching `<h3>`
   belong to that section.
3. **Question segmentation.** Within each section, find `<p>` elements whose
   first `<strong>` child matches `^([A-Z])-?(\d+)([A-Z]?)\.\s`. The
   capture groups yield `(letter, number, suffix)` → canonical
   `question_id` (e.g., `I-1.` → `I.1`, `C1.` → `C.1`). The question's
   content block is the run of sibling nodes up to the next question
   anchor.
4. **Table parsing.** For each `<table>` inside a content block:
   - Column labels from `<thead>` cells (or first `<tr>` if no `<thead>`)
   - Row label from the leftmost cell of each `<tbody>` row
   - Value cells keyed by `(row_label, col_label)` pair
5. **Schema binding.** For each `(question_id, row_label, col_label)` triple:
   - Direct match against schema fields indexed by question number + row label
     + column header
   - If no direct match, consult `tools/tier6_html/aliases.json`: `{question_id:
     {row_label_alias: canonical_row_label}}`
   - If still no match, record in `unmapped_fields` for operator review
6. **Narrative capture.** For non-tabular questions (short-answer narrative),
   collect `<p>` text between the question anchor and the next question
   anchor. Emit as `value: string` with `binding_strategy: "narrative"`.
7. **Emit.** Canonical JSON keyed by `question_number` per the shape above.

**CLI matching Tier 2 / Tier 1:**

```bash
python tools/tier6_html/extract.py \
    scratch/mit-2024-25.html \
    schemas/cds_schema_2025_26.json \
    --output /tmp/mit_tier6.json \
    --summary
```

`--summary` prints populated-field count, unmapped cells, tables seen, and
narrative paragraphs to stderr.

**Dependencies.** `beautifulsoup4` (transitively installed via Docling today,
pin explicitly) and `lxml` (parser backend). Both go in
`tools/tier6_html/requirements.txt` and get referenced from
`tools/extraction_worker/requirements.txt` so the worker picks them up in
its venv.

### 2. Worker wiring: `tools/extraction_worker/worker.py`

Mirror the Tier 1 / Tier 2 pattern:

- Add `from tier6_html.extract import extract_from_bytes as tier6_extract`.
- Add `_run_tier6(client, document_id, school_id, html_bytes, source_format,
  schema, dry_run) -> str` modeled on `_run_tier1`. Inserts a `cds_artifacts`
  row with `kind='canonical'`, `producer='tier6_html'`,
  `producer_version='0.1.0'`. Marks `cds_documents.extraction_status='extracted'`
  on success, `'failed'` on error.
- Extend `sniff_format_from_bytes(data: bytes) -> str`. The current sniffer
  recognizes `%PDF`, `PK\x03\x04`. Add a case: if the first ~200 bytes
  (case-folded) contain `<html`, `<!doctype html`, or `<head`, return
  `"html"`. Place this case **after** the PDF / ZIP checks so binary
  signatures still win; HTML sniff is the text fallback.
- Extend the main router. `if source_format == "html": return _run_tier6(...)`.
- Update the module docstring's routing table to include `html → Tier 6`.

### 3. Schema: allow `source_format='html'`

`cds_documents.source_format` is gated by a CHECK constraint in
`supabase/migrations/20260413201910_initial_schema.sql` that enumerates
`('pdf_fillable', 'pdf_flat', 'pdf_scanned', 'xlsx', 'docx', 'other')`.
Extend the constraint to include `'html'`.

New migration:
`supabase/migrations/{YYYYMMDDHHMMSS}_html_source_format.sql`:

```sql
alter table public.cds_documents
  drop constraint if exists cds_documents_source_format_valid;

alter table public.cds_documents
  add constraint cds_documents_source_format_valid
  check (source_format is null or source_format in (
    'pdf_fillable',
    'pdf_flat',
    'pdf_scanned',
    'xlsx',
    'docx',
    'html',
    'other'
  ));

comment on column public.cds_documents.source_format is
  'Source file format detected on discovery. pdf_fillable = unflattened PDF '
  'with AcroForm fields (Tier 2). pdf_flat = flattened PDF requiring layout '
  'extraction (Tier 4). pdf_scanned = image-only PDF requiring OCR. '
  'xlsx = filled Excel template (Tier 1). docx = filled Word template (Tier 3). '
  'html = structured HTML page (Tier 6).';
```

### 4. Storage: allow `text/html` uploads to the `sources` bucket

The `sources` bucket's `allowed_mime_types` (same initial migration) does
not include `text/html`. Without this, `archive.ts` will fail to upload HTML
bytes. Extend the allowlist in the new migration:

```sql
update storage.buckets
set allowed_mime_types = array[
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/html'
]
where id = 'sources';
```

### 5. Discovery archival: archive HTML bytes

`supabase/functions/_shared/storage.ts` and `_shared/archive.ts` currently
reject non-PDF/XLSX/DOCX content:

- `extForContentType()` returns `null` for `text/html`
- `sniffBytesForExt()` returns `null` for non-PDF non-ZIP bytes
- `extForResponse()` returns `null` when both miss
- `archive.ts` throws `unknown content type` when ext is `null`

Extend each to recognize HTML:

- `extForContentType`: add `if (ct.includes("text/html")) return "html";`
  and URL-suffix fallback for `.html` / `.htm`.
- `sniffBytesForExt`: add a text sniff for `<html`, `<!DOCTYPE html`,
  `<head` in the first 200 bytes (case-folded).
- `normalizedContentType`: map `"html" → "text/html; charset=utf-8"`.
- SHA-addressed path stays the same: `{school_id}/{cds_year}/{sha256}.html`.

The rest of `archive.ts` (download, SHA compute, upload) works unchanged —
it is extension-agnostic.

**MIT caveat.** The resolver today looks for downloadable document anchors.
For MIT's 2024-25 page, the HTML **is** the document. Two paths:

- **Short term (shipped with this PRD):** hand-curate MIT's HTML URL into
  `tools/finder/manual_urls.yaml` and archive via the `force_urls` endpoint.
  MIT is already on the manual list (per backlog note). Updating its entry to
  point at the HTML URL is the operator action to bring MIT online after this
  PRD ships.
- **Long term (separate corpus-survey task):** teach the resolver to recognize
  HTML-native CDS pages. Out of scope for this PRD. Tracked as a follow-up
  in `docs/backlog.md`.

### 6. Alias table: `tools/tier6_html/aliases.json`

MIT paraphrases row labels. Seed the alias table from MIT's observed
paraphrases (collected during build + verification). Shape:

```json
{
  "C.1": {
    "Total first-time, first-year men who applied": "Men",
    "Total first-time, first-year women who applied": "Women"
  },
  "C.2": { ... }
}
```

The alias table is maintained incrementally: every new HTML publisher
contributes paraphrases observed during first-run QA. Missing paraphrases
surface in `unmapped_fields`, which is the operator signal to update the
table (or defer to the LLM fallback).

### 7. Tests

- **Unit test (`tools/tier6_html/test_extract.py`):** a fixture of MIT's
  2024-25 HTML snapshot checked in to `tools/tier6_html/fixtures/`.
  Asserts `schema_fields_populated >= 100` and hand-picked spot checks for
  `A.1` (institution name), `B.1` (enrollment), and `C.1` (applications) match
  the visible HTML.
- **Worker integration test:** a dry-run invocation that loads the MIT
  fixture from a local file (not Storage) and verifies `_run_tier6` produces
  the expected artifact shape.
- **Regression smoke:** re-run `tools/extraction-validator/score_tier4.py`
  against Harvard / Yale / Dartmouth / HMC ground truth. Tier 4 code path
  must be unchanged. Any score delta is a regression.

### 8. End-to-end verification on MIT

1. Fetch MIT's 2024-25 HTML: `curl -sSLo scratch/mit-2024-25.html
   https://ir.mit.edu/projects/2024-25-common-data-set/`
2. Run the extractor standalone:
   `python tools/tier6_html/extract.py scratch/mit-2024-25.html
   schemas/cds_schema_2025_26.json --summary`
3. Verify ≥ 100 canonical schema fields populated.
4. Archive through the discovery pipeline:
   - Add MIT HTML URL to `tools/finder/manual_urls.yaml` (if not already).
   - Invoke `force_urls` edge function with the MIT URL and `cds_year=2024-25`.
   - Confirm `cds_documents` row lands with `source_format='html'` and a
     `cds_artifacts(kind='source')` row points at `sources/mit/2024-25/<sha>.html`.
5. Run the worker with `--school mit --limit 1`. Confirm a
   `cds_artifacts(kind='canonical', producer='tier6_html')` row lands with
   ≥ 100 fields populated.
6. Hit the live frontend at `collegedata.fyi/schools/mit` and confirm MIT's
   2024-25 data renders through the same field viewer used for every other
   tier.

## Files modified

| File | Change |
|---|---|
| `tools/tier6_html/extract.py` | **New.** HTML parser, ~200 lines. |
| `tools/tier6_html/aliases.json` | **New.** Per-question row-label alias table, seeded from MIT. |
| `tools/tier6_html/requirements.txt` | **New.** `beautifulsoup4>=4.12`, `lxml>=5.0`. |
| `tools/tier6_html/README.md` | **New.** Usage, tier strategy, alias-table maintenance. |
| `tools/tier6_html/fixtures/mit-2024-25.html` | **New.** Checked-in HTML snapshot for the unit test. |
| `tools/tier6_html/test_extract.py` | **New.** pytest module (first tests in the repo — see PRD 007's non-goal note). |
| `tools/extraction_worker/worker.py` | Extend `sniff_format_from_bytes` with HTML case. Add `_run_tier6`. Route `source_format='html'`. Update routing table docstring. |
| `tools/extraction_worker/requirements.txt` | Add `beautifulsoup4>=4.12`, `lxml>=5.0`. |
| `tools/extraction_worker/README.md` | Update tier routing table with a Tier 6 row. |
| `supabase/migrations/{ts}_html_source_format.sql` | **New.** Extend `source_format` CHECK constraint and `sources` bucket MIME allowlist. |
| `supabase/functions/_shared/storage.ts` | `extForContentType`, `sniffBytesForExt`, `normalizedContentType`, `extForResponse` recognize `html`. |
| `docs/ARCHITECTURE.md` | Extraction pipeline diagram + routing table: Tier 6 row. Status table at bottom. |
| `docs/extraction-quality.md` | New Tier 6 section with MIT as the reference school. |
| `docs/backlog.md` | Resolved entry pointing at this PRD. Add a follow-up for "automate HTML-native discovery." |
| `CONTRIBUTING.md` (if present) | No change unless it documents tier list. |

## Verification plan

### Acceptance criteria

1. MIT 2024-25 HTML extraction populates **≥ 100 canonical schema fields**,
   with values verifiable against the visible HTML for at least 15 hand-picked
   fields spanning all 10 sections.
2. Worker routes `source_format='html'` through Tier 6 without affecting
   Tier 1 / 2 / 4 / 5 paths.
3. `score_tier4.py` against Harvard / Yale / Dartmouth / HMC ground truth
   is **byte-identical** to the pre-change run. Any delta is a regression
   and blocks merge.
4. `sources` bucket accepts `text/html` uploads end-to-end (archive test
   against MIT's HTML URL succeeds without `unsupported content type`).
5. Frontend renders MIT's 2024-25 data at `collegedata.fyi/schools/mit/2024-25`
   identically to any other tier's output — the consumer API is schema-shape
   invariant.

### Specific checks

| Check | Expected | How measured |
|---|---|---|
| Fields populated on MIT 2024-25 | ≥ 100 | `--summary` stderr output |
| Sample value: C.1 applications Men | Matches MIT HTML | Manual spot check vs live page |
| Sample value: B.1 total enrollment | Matches MIT HTML | Manual spot check |
| Sample value: F.1 student-life percentage | Matches MIT HTML | Manual spot check |
| Unmapped cells | ≤ 25 | Drives alias table seeding |
| Existing tier 1/2/4/5 extractions | Byte-identical to baseline | `score_tier4.py` + 10-doc sample from each tier |

## Risks

| Risk | Mitigation |
|---|---|
| Alias table grows unboundedly as new HTML publishers surface with different paraphrase styles. | Each new publisher contributes paraphrases in one pass; unmapped cells are the operator signal. Tier 4 LLM fallback (PRD 006) handles the long tail without alias-table entries. |
| MIT's URL structure changes or the page is re-templatized (they're on a WordPress-ish CMS — class="wp-block-group" is in the HTML). | Archive the bytes at discovery time. The extractor reads archived bytes, not the live page, so a URL change doesn't break existing extracts. |
| `<h3>` segmentation is fragile if a publisher nests section headings differently. | Start with MIT's flat structure. When a second publisher shows a different pattern, extend the segmentation rule with publisher-pattern detection (the HTML equivalent of Tier 4's layered parser). |
| Question-number regex false positives: `A.D.` (someone writing "Anno Domini") or `B1` appearing in body text. | Only accept the match when it is the first `<strong>` child of a `<p>` — narrative text does not usually wrap question numbers in strong tags. Reject matches where the surrounding `<p>` has mixed content before the `<strong>`. |
| HTML MIME allowlist change to the `sources` bucket is a policy change with a blast radius wider than one tier. | Migration is small (ALTER CHECK + UPDATE bucket). Reviewed with the eng phase below. Revertible in one migration. |
| First-ever tests in the repo (per backlog). Adds a pytest dep and a CI consideration. | Scoped to `tools/tier6_html/test_extract.py` — no project-wide pytest setup. The file is runnable as `python -m pytest tools/tier6_html/test_extract.py`. A follow-up PRD can address repo-wide test infrastructure. |
| Narrative-text capture collects trailing boilerplate (footer, copyright) if section segmentation fails. | Segmentation anchors on `<h3>` only. Footer text lives below the last `<h3>` under its own `<footer>` / sibling markup, so the last section's narrative block stops at the expected boundary. Unit test covers the J-section trailing boundary. |

## Non-goals

- **JS-rendered HTML (Playwright at extraction time).** MIT is static. If a
  JS-rendered school surfaces, reuse PRD 004's Playwright URL collector to
  snapshot the rendered HTML at discovery time and archive the static
  snapshot. The Tier 6 extractor never runs a browser.
- **Auto-discovering which schools publish HTML-native CDS.** Separate
  corpus-survey task. Tracked in `docs/backlog.md` after this PRD ships.
- **LLM cleanup of paraphrased row labels.** The per-question alias table
  is first-line. An LLM fallback via PRD 006 handles residuals. No changes
  to PRD 006's prompts or scoring in this PRD.
- **Historic MIT years beyond 2024-25.** The extractor is schema-version
  aware (uses the same `cds_schema_YYYY_YY.json` join every other tier
  uses), so historical years work once their HTML is archived. Archiving
  historical MIT pages is a separate operator action.
- **Reducing the alias table to zero via pure regex.** Paraphrase matching
  is an open-ended problem; the alias table is the explicit mechanism
  that scales cleanly across publishers.

## Cross-references

- [ARCHITECTURE.md — extraction pipeline](../ARCHITECTURE.md)
- [PRD 002 — frontend](002-frontend.md) (consumer of the canonical JSON shape)
- [PRD 004 — JS-rendered resolver](004-js-rendered-resolver.md) (the
  Playwright path for future JS-rendered publishers)
- [PRD 005 — full-schema extraction](005-full-schema-extraction.md) (Tier 4
  cleaner expansion; complementary to Tier 6)
- [PRD 006 — LLM fallback](006-llm-fallback.md) (residual-field repair
  layer used when alias table misses)
- [PRD 007 — Tier 3 DOCX extraction](007-tier3-docx-extraction.md) (shape
  template for this PRD)
- [ADR 0006 — tiered extraction strategy](../decisions/0006-tiered-extraction-strategy.md)
