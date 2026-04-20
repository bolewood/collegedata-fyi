<!-- /autoplan restore point: ~/.gstack/projects/bolewood-collegedata-fyi/main-autoplan-restore-20260420-121156.md -->

# PRD 008: HTML CDS Extraction via Tier 4 Cleaner Reuse

**Status:** Reviewed (autoplan 2026-04-20) — approved reframe from "bespoke Tier 6" to "HTML normalized into markdown and passed through the existing Tier 4 cleaner."
**Created:** 2026-04-20

---

## Context

A small but strategically important set of schools publish their Common Data
Set as structured HTML directly on their IR landing page instead of as a
downloadable PDF, XLSX, or DOCX. MIT is the archetype:
https://ir.mit.edu/projects/2024-25-common-data-set/. Other WCAG-driven
HTML publishers likely exist but have not been surveyed. Today all of them
fail the extraction pipeline because the discovery resolver expects a
downloadable document anchor and the worker has no format handler for
`text/html` bytes.

**What changed after /autoplan review.** The initial draft proposed a new
`tools/tier6_html/` extractor with its own parser, segmentation rules, and
per-question alias table. Both independent strategy voices and the eng
subagent rejected that shape and converged on a cheaper, safer architecture:
normalize HTML to markdown and pass it through `tools/extraction_worker/
tier4_cleaner.py`, which already does header-heuristic table parsing
(`_parse_markdown_tables`, lines 134-168), row-label normalization
(`_normalize_label` / `_normalize_gender`, lines 36-75), and the
`(section, row_label, question) → question_number` join
(`SchemaIndex.filter`, 357+). MIT's structured HTML → markdown is cleaner
input than Docling produces from flat PDFs, so the existing cleaner should
score higher on MIT than it does on Harvard's or Yale's flattened PDFs. The
reusable unit is the schema-to-markdown binding layer, not a second
transport-format-specific parser.

Separately, the review flagged a **critical security issue** with the
original plan: the `sources` Storage bucket is `public: true`, and adding
`text/html` to the MIME allowlist would mean a future archived HTML file
with `<script>` tags becomes stored XSS at the Supabase CDN URL. This PRD
addresses that before a single HTML byte lands in the bucket.

## Premises

1. **HTML→markdown is a shape transform, not a parser.** BeautifulSoup + a
   30-line table serializer produces pipe-delimited markdown from MIT's
   HTML. That output is structurally identical to what Docling produces from
   a PDF — and usually cleaner, because HTML preserves `<thead>` and
   `<tbody>` explicitly rather than relying on TableFormer layout recovery.
2. **The cleaner's normalizer is the paraphrase-handling layer.** The CDS
   ecosystem paraphrases row labels ("Men" vs "Total first-time, first-year
   men who applied"). `_normalize_label` already drops punctuation,
   pluralization, and gender-term variants. Any new paraphrase that clears
   the normalizer but doesn't match the schema surfaces as an unmapped
   cell, which is the existing Tier 4 operator signal — same mechanism,
   no new maintenance surface.
3. **PRD 006's LLM fallback is the residual layer.** Subsections that fall
   through the cleaner are eligible for PRD 006's Claude Haiku fallback
   unchanged. HTML input becomes just another markdown source for the
   fallback — no prompt, cache-key, or validator change.
4. **Static HTML only.** MIT is server-rendered. JS-rendered schools reuse
   PRD 004's Playwright collector to snapshot the rendered HTML at
   discovery time. The extraction path never runs a browser.
5. **XSS mitigation is required before the bucket allowlist opens.** HTML
   bytes in a public-read bucket without mitigation is an XSS primitive.
   The mitigation ships in the same migration as the allowlist change.

## What to build

The work splits into four small, reviewable pieces.

### 1. HTML-to-markdown normalizer

`tools/extraction_worker/html_to_markdown.py` — a single function:

```python
def html_to_markdown(html_bytes: bytes) -> str:
    """Convert CDS-shaped HTML to pipe-delimited markdown the tier4
    cleaner consumes. No schema awareness. Pure shape transformation."""
```

**Algorithm:**

1. Guard the byte budget. Reject > `MAX_HTML_BYTES` (5 MB — CDS HTML pages
   are well under 500 KB). Bound the parse.
2. Parse with BeautifulSoup (`lxml` parser), `from_encoding` honoring
   `<meta charset>` or Content-Type sniff, `resolve_entities=False` to
   disarm XXE.
3. Strip `<script>`, `<style>`, `<noscript>`, `<svg>`, `<iframe>`,
   `<head>` entirely. We want visible structured content only.
4. Walk top-level content. For each element:
   - `<h1>` / `<h2>` / `<h3>` → emit `### ` + text (Docling's section
     style). Section numbering (`A.`, `B.`, `I-1.`) stays in the text;
     the cleaner's section detection already handles it.
   - `<p>` with leading `<strong>` matching a question anchor → emit the
     paragraph as `**Question text**` on its own line so the cleaner
     recognizes it as a subsection anchor.
   - `<table>` → serialize as pipe-delimited markdown table. Skip tables
     with no `<th>` and only one column (layout tables). Use `<thead>`
     cells as headers; fall back to first `<tr>` if absent. Collapse
     cell contents with `get_text(" ", strip=True)`.
   - Everything else → `get_text(" ", strip=True)` prefixed with a blank
     line.
5. Return a single string. No JSON, no schema binding — that's the
   cleaner's job.

**Dependencies:** `beautifulsoup4>=4.12`, `lxml>=5.0`. Added to
`tools/extraction_worker/requirements.txt` (the worker's existing venv).

**Note on markdownify.** A prebuilt library (`markdownify`, `html2text`)
was considered. Rejected because CDS HTML tables need conservative
serialization (skip layout tables, preserve `<thead>` headers, drop
inline style). 30 lines of BS4 beats a dependency that would still need
wrapping. If the normalizer grows past ~100 lines, revisit.

### 2. Worker routing + XSS mitigation

`tools/extraction_worker/worker.py`:

- Extend `sniff_format_from_bytes(data: bytes) -> str`. Current order:
  `%PDF` → pdf_*; `PK\x03\x04` → xlsx/docx. New case **after** those:
  if the first 512 bytes (case-folded) contain `<html`, `<!doctype html`,
  or `<head`, return `"html"`.
- Add `_run_tier6(client, document_id, school_id, html_bytes,
  source_format, schema, dry_run) -> str`. It:
  1. Calls `html_to_markdown(html_bytes)`.
  2. Calls the existing `tier4_cleaner.clean(markdown)` to produce
     `values`.
  3. Assembles the canonical artifact dict with
     `producer="tier6_html"`, `producer_version="0.1.0"`, the same shape
     every tier emits.
  4. Inserts `cds_artifacts` and marks `extraction_status='extracted'`
     on success. On an empty-values result (cleaner returned fewer than
     5 fields), marks `failed` with reason `html_no_tables`.
- Route `if source_format == "html": return _run_tier6(...)`.
- Update the routing-table docstring.

**Why `producer="tier6_html"` and not `producer="tier4_docling"`.** The
artifact format is Tier 4 shape, but the input transport is HTML. Keeping
a distinct producer name makes it queryable and lets the cleaner evolve
for HTML-specific paraphrases without polluting the PDF code path.
`producer_version` tracks the `html_to_markdown` module version.

**Minimum output threshold.** If `_run_tier6` returns fewer than 5
populated fields, mark the row `failed` with reason `html_no_tables`.
This catches the silent-success mode where a login-wall or stub page
returns a 200 with valid HTML but no CDS content.

### 3. Discovery archival + migration

`supabase/migrations/{ts}_html_source_format.sql`:

```sql
-- Extend source_format allowlist.
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
  'with AcroForm fields (Tier 2). pdf_flat = flattened PDF (Tier 4). '
  'pdf_scanned = image-only PDF + OCR (Tier 5). xlsx = filled Excel (Tier 1). '
  'docx = filled Word template (Tier 3). html = structured HTML normalized to '
  'markdown and passed through the Tier 4 cleaner (PRD 008).';

-- Extend the sources bucket MIME allowlist to include HTML.
update storage.buckets
set allowed_mime_types = array[
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/html'
]
where id = 'sources';
```

**XSS mitigation.** The storage layer must never serve stored HTML with a
`text/html` Content-Type. Two defensive layers:

- `supabase/functions/_shared/storage.ts`:
  - `normalizedContentType("html")` returns `"text/plain; charset=utf-8"`
    — the bucket is configured to accept `text/html` for upload validation,
    but stored objects are served as `text/plain` so browsers render the
    markup as text, not execute it.
  - `uploadSource` for `ext === "html"` sets an explicit
    `cacheControl` + `contentType` override to `text/plain`. The Supabase
    storage API uses `contentType` as both the validation signal and the
    response header, so this closes the loop.
- `extForContentType`: recognize `text/html` → `"html"`. URL-suffix
  fallback for `.html` / `.htm`.
- `sniffBytesForExt`: add a text sniff for `<html`, `<!DOCTYPE html`,
  `<head` in the first 512 bytes (case-folded).
- `extForResponse`: unchanged (it composes the above).

**Why serve as `text/plain` rather than force-download.** `Content-Disposition:
attachment` is not directly settable on Supabase public-bucket objects
through the standard upload API. Swapping the response Content-Type to
`text/plain` is the supported, durable mitigation. Anyone who truly wants
the raw HTML with a browser can View Source or download manually; we do not
need to render HTML from our CDN.

**Type regeneration.** After the migration runs, regenerate
`web/src/lib/database.types.ts` via `supabase gen types typescript
--project-id <ref>` and commit. Listed in verification steps below.

**Migration ordering.** The ALTER CHECK must run before any HTML row is
inserted. The bucket UPDATE can run in any order relative to the CHECK.
Both are idempotent (`drop constraint if exists`, MIME allowlist as full
replacement). No down migration shipped — reverting the CHECK is mechanical
if required (drop + re-add with the old allowlist).

### 4. Frontend source-format label

`web/src/lib/labels.ts` (or wherever `formatBadgeLabel` lives): add the
`html` case returning `"HTML"`. Surfaced on `DocumentCard` and year detail
views. Verify in the UI.

## Files modified

| File | Change |
|---|---|
| `tools/extraction_worker/html_to_markdown.py` | **New.** ~80 lines. BS4 + `lxml` → pipe-delimited markdown. |
| `tools/extraction_worker/worker.py` | Extend `sniff_format_from_bytes` with HTML case. Add `_run_tier6`. Route `source_format='html'`. Update routing table docstring. Min-field threshold check. |
| `tools/extraction_worker/requirements.txt` | Add `beautifulsoup4>=4.12`, `lxml>=5.0`. |
| `tools/extraction_worker/README.md` | New Tier 6 row in routing table. Document HTML→markdown reuse of Tier 4 cleaner. |
| `tools/extraction_worker/tier4_cleaner.py` | No change expected. If MIT surfaces a paraphrase the normalizer misses, extend the normalizer there; do not create a separate HTML-only path. |
| `supabase/migrations/{ts}_html_source_format.sql` | **New.** Extend CHECK constraint + bucket MIME allowlist. |
| `supabase/functions/_shared/storage.ts` | Recognize `html`. Serve stored HTML as `text/plain`. |
| `supabase/functions/_shared/storage.test.ts` (if present) | Test sniffer + content-type mapping. |
| `web/src/lib/database.types.ts` | Regenerated from migration. |
| `web/src/lib/labels.ts` | `formatBadgeLabel("html") → "HTML"`. |
| `docs/ARCHITECTURE.md` | Extraction pipeline diagram: add HTML input to Tier 4 cleaner box. Routing table row. |
| `docs/extraction-quality.md` | New HTML section with MIT as the reference. |
| `docs/backlog.md` | Resolved entry linking this PRD. Add follow-up: "Auto-discover HTML-native CDS publishers at resolver time." |

**No new directory under `tools/`.** The original draft proposed
`tools/tier6_html/` with its own extractor, aliases, README, and pytest
suite. All removed. The normalizer lives next to the worker because it's
worker-internal. No first-ever pytest — the spike covers correctness;
regression safety comes from `score_tier4.py` re-running unchanged
against ground truth.

## Verification plan

### Order of operations

1. **Spike.** Before writing the normalizer, fetch MIT's HTML and prototype
   `html_to_markdown` in a scratch file. Pipe through
   `tier4_cleaner.clean()` and measure `schema_fields_populated`.
   - **Gate:** if the spike clears ≥ 100 fields, commit to the full
     reframe. If it clears 40-99, extend the normalizer (nested tables,
     additional section patterns) and re-measure. If it clears < 40,
     **stop and reopen the PRD** — the cleaner may be PDF-markdown-shaped
     in ways HTML doesn't produce, and a bespoke parser may be justified
     after all.
2. **Ship the normalizer + worker route + migration + XSS mitigation in
   one PR.** All four pieces must land together — partial deploy is a
   security regression (allowlist without mitigation = XSS hole).
3. **End-to-end test on MIT.**
4. **Regression proof.**
5. **Docs update.**

### Acceptance criteria

1. MIT 2024-25 HTML extraction populates **≥ 100 canonical schema fields**,
   values verifiable against visible HTML for ≥ 15 hand-picked fields
   spanning all 10 sections.
2. `sources` bucket accepts `text/html` uploads and serves them as
   `text/plain; charset=utf-8`. Verify with
   `curl -I https://<ref>.supabase.co/storage/v1/object/public/sources/mit/2024-25/<sha>.html`
   returning `Content-Type: text/plain; charset=utf-8`.
3. Upload a test HTML file containing `<script>alert(1)</script>`.
   Confirm the Supabase-served response does not execute when loaded in
   a browser.
4. Worker routes `source_format='html'` through `_run_tier6` → tier4
   cleaner without affecting Tier 1 / 2 / 4 / 5 paths.
5. `score_tier4.py` against Harvard / Yale / Dartmouth / HMC ground truth
   is **byte-identical** to the pre-change run.
6. Frontend renders MIT's 2024-25 data at `collegedata.fyi/schools/mit/2024-25`
   with source-format badge `HTML`.
7. PRD 006 LLM fallback runs against MIT's extracted artifact if
   coverage < threshold. No prompt or cache-key change required.

### E2E verification on MIT

```bash
# 1. Fetch MIT HTML.
curl -sSLo scratch/mit-2024-25.html https://ir.mit.edu/projects/2024-25-common-data-set/

# 2. Run the spike (standalone script).
cd tools/extraction_worker
python -c "
from pathlib import Path
from html_to_markdown import html_to_markdown
from tier4_cleaner import clean
html = Path('../../scratch/mit-2024-25.html').read_bytes()
md = html_to_markdown(html)
values = clean(md)
print(f'markdown chars: {len(md)}, fields populated: {len(values)}')
"

# 3. Apply migration + redeploy storage.ts.
supabase db push
supabase functions deploy archive-process

# 4. Archive MIT through force_urls.
#    (MIT already on manual_urls.yaml; update to HTML URL if not present.)

# 5. Drain.
python worker.py --school mit --limit 1

# 6. Confirm artifact.
#    SELECT producer, jsonb_array_length(notes->'values') FROM cds_artifacts
#      WHERE document_id = (SELECT id FROM cds_documents WHERE school_id='mit' AND cds_year='2024-25')
#      AND kind='canonical';

# 7. Regenerate types + regression check.
supabase gen types typescript --project-id <ref> > web/src/lib/database.types.ts
python tools/extraction-validator/score_tier4.py --schools harvard,yale,dartmouth,harvey-mudd
```

## Risks

| Risk | Mitigation |
|---|---|
| Spike shows < 100 fields — cleaner doesn't handle HTML shape. | The gate in verification step 1 stops work and reopens this PRD. No speculative parser code written before measurement. |
| `html_to_markdown` misses a structural pattern (layout-nested tables, `<dl>` lists, `<table>` inside `<figure>`). | Normalizer stays narrow; misses surface as low-field-count extractions, then either extend the normalizer OR promote to the `failed` bucket with `html_no_tables` reason. No alias table, no publisher-specific parser. |
| XSS via the public sources bucket. | Storage.ts serves stored HTML as `text/plain; charset=utf-8`. Upload-time MIME validation still accepts `text/html`. Tested via the `<script>` upload E2E. |
| Migration applied but worker not deployed (or vice versa). | All four pieces ship in one PR. Partial deploy is flagged by the HTML row sitting at `extraction_pending` forever without a matching handler, or by an upload succeeding but serving with wrong content type. Mitigation: deploy in strict order — migration → storage edge function → worker. |
| JS-rendered HTML surfaces in discovery. | Out of scope. PRD 004's Playwright collector snapshots the rendered DOM at discovery time; the resulting static HTML archives via the same path. Tracked in backlog. |
| MIT re-templates and the normalizer's `<h3>` anchor stops working. | Archived bytes survive. Re-run the normalizer against the archived SHA; the existing extraction can be replayed. Normalizer versioning via `producer_version` lets a re-run insert a new artifact without breaking the old one. |
| Cleaner dev velocity: extending `_normalize_label` for HTML-specific paraphrases might regress PDF extraction. | Every `_normalize_label` change runs against `score_tier4.py`'s ground truth before merge. That gate exists already. |
| Alias-table maintenance. | Removed from scope entirely. |
| First-ever pytest in the repo. | Removed from scope. The spike + score_tier4 regression + E2E on MIT are the validation. |

## Non-goals

- **Bespoke HTML extractor.** Explicitly dropped. The architecture is
  HTML → markdown → existing cleaner.
- **Per-question alias table.** Explicitly dropped. Paraphrases flow
  through the cleaner's existing normalizer and the PRD 006 LLM fallback.
- **New `tools/tier6_html/` directory with its own README, tests,
  requirements.** All removed.
- **JS-rendered HTML.** Handled via PRD 004's Playwright collector at
  discovery time, then reuses this path.
- **Auto-discovering HTML publishers.** Corpus-survey task, tracked in
  backlog.
- **Historical MIT years.** Extraction works once the HTML is archived;
  archiving historical pages is an operator task.
- **Serving archived HTML as `text/html`.** Security mitigation — HTML is
  served as `text/plain` from the public bucket. Raw HTML is still
  downloadable (View Source on any browser or `curl` with custom
  headers).

## Cross-references

- [ARCHITECTURE.md — extraction pipeline](../ARCHITECTURE.md)
- [PRD 004 — JS-rendered resolver](004-js-rendered-resolver.md)
- [PRD 005 — full-schema extraction](005-full-schema-extraction.md)
- [PRD 006 — LLM fallback](006-llm-fallback.md)
- [PRD 007 — Tier 3 DOCX extraction](007-tier3-docx-extraction.md)
- [ADR 0006 — tiered extraction strategy](../decisions/0006-tiered-extraction-strategy.md)

---

## /autoplan Review Report

Reviewed 2026-04-20 on branch `main`.

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/autoplan` Phase 1 | Scope & strategy | 1 | clean (post-reframe) | Pre-reframe: 5 high (wrong abstraction, N=1 archetype, alias debt, dismissed alternatives, 6-month regret). All resolved by reframe. |
| CEO Voices (Claude + Codex) | `/autoplan` Phase 1 | Independent strategy challenge | 1 | clean | DISAGREE → CONFIRMED on all 6 consensus dimensions after reframe. |
| Eng Review | `/autoplan` Phase 3 | Architecture & tests | 1 | clean (post-reframe) | Pre-reframe: 1 critical (XSS via public bucket + text/html), 3 high (wrong seam, size bounds, reusability), 6 medium. XSS mitigation + reuse path + size bounds addressed in this PRD. |
| Eng Voices (Claude subagent) | `/autoplan` Phase 3 | Independent architecture challenge | 1 | `[subagent-only]` | Codex eng voice unavailable in this session (empty output twice). Single-reviewer. Findings strong enough to act on without second voice. |
| Design Review | N/A | No UI scope | 0 | — | Skipped — verification mentions frontend badge only, no new UI components. |
| DX Review | N/A | No developer-facing SDK/API | 0 | — | Skipped — all interfaces are internal operator CLI / worker. |

### Cross-Phase Themes

1. **Reuse tier4_cleaner.** CEO Claude (alternative 4a) and Eng Claude
   (reusability, high) landed on this independently. Addressed.
2. **Alias table is ontology debt.** CEO both voices + Eng cost analysis
   converged. Removed from scope.
3. **MIT-specific ≠ category-ready.** Addressed via the spike gate in
   verification step 1 — no speculative code before measurement.

### Decisions Made

- **USER CHALLENGE accepted** (via AskUserQuestion at final gate):
  architecture reframed from bespoke Tier 6 extractor to
  HTML→markdown→tier4_cleaner reuse.
- **Auto-decided:** skip Design + DX phases (no scope); treat user-supplied
  premises as confirmed (auto mode); mark Codex eng as unavailable after
  two retries; XSS fix is blocking, not deferrable.

### Deferred to backlog

- Auto-discover HTML-native CDS publishers at resolver time.
- Historical MIT year archival (operator task once pattern holds on 2024-25).
- Revisiting bespoke HTML parser **only if** spike gate fails with < 40
  fields populated.

**VERDICT:** APPROVED with reframe. Ready to implement. Suggested next
action: `/ship` after the spike completes and clears the ≥100-field gate.
