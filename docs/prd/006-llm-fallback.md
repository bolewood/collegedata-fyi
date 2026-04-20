# PRD 006: LLM Fallback for Tier 4 Extraction — Cheap, Cached, and Selective

**Status:** Draft (rev 2 — incorporates PRD 005 execution learnings)
**Created:** 2026-04-19
**Updated:** 2026-04-20
**Related:** [PRD 003](003-ai-driven-data-quality.md), [PRD 005](005-full-schema-extraction.md), [Tier 4 cleaner learnings](../research/tier4-cleaner-learnings-for-llm-fallback.md), [ADR 0006](../decisions/0006-tiered-extraction-strategy.md), [ADR 0007](../decisions/0007-year-authority-moves-to-extraction.md), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)

---

## Context

The current extraction worker has a strong split:

- **Tier 2 (`pdf_fillable`)** is deterministic and already good enough. It should stay
  the primary path for fillable PDFs.
- **Tier 4 (`pdf_flat`)** converts flattened PDFs to markdown via Docling, then runs
  `tier4_cleaner.py` to map the markdown into canonical CDS question numbers.

PRD 005 executed six phases of hand-coded resolvers on the Tier 4 cleaner. The
3-doc benchmark (Harvard, Yale, Dartmouth 2024-25) went from **72 → ~380
fields** — meaningful, but still leaves ~60% of the 1,105-field schema
untouched. The remaining fields are not untouched because nobody got to them;
they resist deterministic mapping because Docling flattens tables to
paragraphs, merges rows, promotes headers to data, and renders checkboxes in
three incompatible dialects. See
[`docs/research/tier4-cleaner-learnings-for-llm-fallback.md`](../research/tier4-cleaner-learnings-for-llm-fallback.md)
for the measured breakdown.

That document is the primary input to this PRD. It tells us exactly which
sections the LLM should attempt (§5), which Docling failure modes the prompt
must handle (§2), which schema ambiguities the prompt must disambiguate (§3),
which deterministic heuristics to preserve as pre/post-processing (§4), and
which sections the LLM cannot help with either (§6).

The right question is not "LLM or cleaner?" It is:

**Can we add a low-cost, section-scoped LLM fallback that repairs low-coverage Tier 4
documents without replacing the deterministic pipeline or turning extraction into an
open-ended API bill?**

This PRD assumes:

1. Tier 2 remains deterministic.
2. Docling remains the primary PDF-to-text/layout layer for Tier 4.
3. The current cleaner remains the first-pass extractor for Tier 4.
4. The LLM is a **repair layer**, not a new primary pipeline.

## Premises

1. **Markdown-first is the default low-cost path.** For `pdf_flat`, we already have
   Docling markdown. Running a cheap text model on section markdown is much cheaper than
   running a multimodal model on full PDF pages.
2. **LLM extraction should be selective, not universal.** Most docs should not invoke
   the LLM. The fallback only runs when the cleaner's coverage is below threshold or
   specific high-value sections are missing.
3. **Prompt caching only matters if the prompt is stable.** The schema fragment,
   extraction instructions, JSON schema, and section-level field list are stable and
   should be cached. The document markdown is variable and should be the only uncached
   tail.
4. **Section-scoped prompts are the cost and correctness boundary.** Whole-document
   prompts are harder to debug, harder to cache, and more expensive. The LLM should see
   one CDS section family at a time.
5. **The LLM must not silently override deterministic output.** Tier 2 and the current
   Tier 4 cleaner are the baseline. The LLM fills gaps or writes a separate artifact.
6. **Validation remains deterministic.** Any LLM-extracted value that cannot survive
   schema-based type checks, section-local consistency checks, or evidence verification
   should be dropped or flagged.
7. **Cost control is a product requirement, not an optimization.** This is a hobby
   open-source project. The fallback must have per-doc, per-day, and per-run budget
   controls built in from day one.

## Goal

Ship a **measured LLM fallback path** for Tier 4 extraction that:

1. Improves coverage on low-coverage flat PDFs
2. Uses cached section prompts plus a cheap text model to keep cost low
3. Writes auditable artifacts with provenance
4. Preserves deterministic extraction as the primary path
5. Gives the project a practical answer to "do we keep building PRD 005 aggressively,
   or let the LLM absorb the long tail?"

## Non-goals

- Replacing Tier 2 deterministic extraction
- Replacing Docling
- Running multimodal extraction on every PDF by default
- Asking a model for all 1,105 fields in one prompt
- Letting the LLM overwrite deterministic values without a policy gate
- Building a full human-review UI in this PRD
- **Asking the LLM to infer which CDS template year the doc uses.** Year
  authority moved to the extractor per ADR 0007; pass it in explicitly.
- **Asking the LLM to compute totals, ratios, or percentages.** If the CDS
  template has a "Total = sum of columns" row, the school either filled it
  authoritatively or the value stays null. Computed totals are a data-quality
  signal, not an extraction task.
- **Mixing document markdown into the cached prompt prefix.** The section
  markdown is the uncached tail; the schema fragment, field list, and
  validation rules are the cached head. Mixing them destroys the cache hit
  rate.
- **Attempting sections where no textual evidence survives Docling:** C3, C4,
  C6 (YesNo buried in prose without glyph preservation), and documents a
  school simply left blank (C5 Carnegie units on all three benchmark schools).
  The fallback emits `null`, not a hallucinated value.

## Measured cleaner ceiling

The 3-doc benchmark (Harvard, Yale, Dartmouth 2024-25) after PRD 005 Phase 6:

| Section family | Fill rate | Expected | Observed | Status for LLM fallback |
|---|---:|---:|---:|---|
| B4 / B5 (grad rates) | 100% | 32+32 | 96+96 | **Skip** — cleaner owns |
| B2 (race/ethnicity) | 87.8% | 30 | 79 | Skip |
| I (faculty + class size) | 86.4% | 49 | 127 | Skip |
| C7 (basis for selection) | 84.2% | 19 | 48 | Skip |
| B3 / C10 / F / E | 50-70% | — | — | Likely skip; spot-check |
| B1 / C1 | 55-60% | 78 / 30 | — | Likely skip; re-evaluate |
| **B22 (retention)** | 33.3% | 3 | 3 | Candidate |
| **C2 (wait list)** | 28.6% | 7 | 6 | Candidate |
| **H (financial aid)** | 24.8% | 165 | 123 | **High priority** (H5–H8) |
| **G (annual expenses)** | 18.8% | 46 | 26 | **High priority** (G5) |
| **C9 (test-score policy)** | 15.7% | 87 | 41 | Candidate |
| **J (disciplines)** | 13.9% | 120 | 50 | Candidate |
| **C13–C22 (policies/dates)** | ≤13% | 56 | ~2 | **High priority** |
| **C11 (GPA profile)** | 11.1% | 30 | 10 | Candidate (Yale/Dart only) |
| **A (general info)** | 9.0% | 63 | 17 | Candidate (contact fields) |
| **D (transfer)** | 1.5% | 88 | 4 | **High priority** (D2–D16) |
| **C5 (Carnegie units)** | 0% | 24 | 0 | Non-goal (schools leave blank) |
| **C3, C4, C6, C8** | 0% | 10 | 0 | Non-goal (prose-buried YesNo) |

The high-fill rows (>80%) share one property: the CDS template renders them
as a rectangular table with stable headers, and Docling preserves that
structure. Everywhere else, Docling flattens tables to paragraphs and the
deterministic parser loses positional context — which is where the LLM earns
its keep.

## Docling failure modes the prompt must handle

From the learnings doc §2. The prompt should explicitly acknowledge each shape:

1. **Table → paragraphs** — ordered value+label stream, no pipes or headers
   (Dartmouth D2, Yale C11, Harvard G5).
2. **Row merge** — two consecutive label rows collapse into one; value array
   belongs to one but there's no reliable signal which.
3. **Header promoted to data** — header cell with digits ("CIP 2020
   Categories") parsed as data row; actual header is empty.
4. **Header concatenation** — "SUB- SECTIONS" split across newlines lands in
   one cell.
5. **Values rendered as prose** — fill-value may appear 1,700 characters after
   the section header, past definitions and footnotes.
6. **Checkbox dialects** — at least four coexisting formats: `- [x] Label`,
   `- [ ] X Label`, `| ☒ Label |`, `- X Label`.
7. **Wrong-file / blank-template archives** — the LLM needs a "this document
   does not describe the school" signal, not empty values.

## What to build

### New producer: `tier4_llm_fallback`

Add a new extraction producer that operates **after** the existing Tier 4 cleaner and
consumes the stored markdown plus the current cleaner output.

**Input:**
- `notes.markdown` from the `tier4_docling` canonical artifact
- `notes.values` from the current cleaner
- section-specific schema subset from `schemas/cds_schema_2025_26.json`

**Output:**
- a new `cds_artifacts` row with `kind='cleaned'` or `kind='canonical'` and
  `producer='tier4_llm_fallback'`
- a `values` object in the same question-number-keyed shape as Tier 2 / Tier 4
- per-field provenance and verification metadata

### Extraction shape

The artifact is a `cds_artifacts` row. Top-level keys are real table columns;
everything payload-shaped (strategy, stats, values, unresolved sections) lives
inside `notes` (jsonb), mirroring the existing `tier4_docling` producer.
`schema_version` is resolved from `cds_documents.detected_year`, not
hardcoded — see ADR 0007.

```json
{
  "document_id": "<uuid>",
  "kind": "cleaned",
  "producer": "tier4_llm_fallback",
  "producer_version": "0.1.0",
  "schema_version": "<derived from cds_documents.detected_year>",
  "storage_path": "<path>",
  "sha256": "<hash of response bundle>",
  "notes": {
    "strategy": "markdown_section_fill_gaps",
    "stats": {
      "sections_attempted": 3,
      "sections_skipped": 7,
      "fields_added": 24,
      "fields_rejected": 3,
      "cache_hits": 2,
      "cache_misses": 1,
      "input_tokens": 0,
      "output_tokens": 0,
      "estimated_cost_usd": 0.0
    },
    "values": {
      "C.1302": {
        "value": "85",
        "source": "tier4_llm_fallback",
        "evidence_text": "Amount of application fee: $85",
        "evidence_section": "First-Time, First-Year Admission",
        "verification": "exact_substring",
        "confidence": 0.9
      }
    },
    "unresolved_sections": ["H", "D"]
  }
}
```

The inner `notes.values[question_number]` shape stays intentionally close to
the current Tier 4 cleaner contract so downstream code does not need a second
viewer path.

## Core approach

### Step 1: Tier 4 runs unchanged

Current flow stays:

1. `worker.py` routes `pdf_flat` to `tier4_extractor.py`
2. `tier4_extractor.py` runs Docling
3. `tier4_cleaner.py` extracts what it can
4. canonical artifact is written with markdown + values

### Step 2: LLM fallback evaluates whether to run

The fallback only runs if at least one of these is true:

- `notes.stats.schema_fields_populated < LOW_COVERAGE_THRESHOLD`
- one or more of the **measured-gap sections** has fill rate below the
  per-section threshold in the cleaner output:
  - H5 / H6 / H7 / H8 (loan totals, aid to nonresidents, aid forms/deadlines)
  - C13–C22 (application fee, deadlines, reply dates, early decision)
  - D2–D16 (transfer applicants and transfer credit policies)
  - G5 (estimated expenses: residents/commuters/living-with-family)
  - C11 (GPA profile — Yale/Dartmouth paragraph renderings only)
  - C9 (test-score use policy fields, not percentiles)
  - A (contact fields: phone, URL, email)
- document is tagged by the data-quality audit as `low_coverage` but not
  `blank_template` or `wrong_file`

Sections where the cleaner already hits ≥80% (B2, B3, B4, B5, C7, C10, I,
F partial) are **excluded** from fallback attempts by default — adding LLM
calls there is pure cost with no expected lift.

Mirror-pipeline docs (`source_provenance='mirror_*'`) are eligible on the same
terms as school-direct docs. Benchmark runs should tag mirror vs school-direct
separately so Docling-quality variance can be isolated if needed.

This prevents waste on docs where the cleaner already did enough.

### Step 3: Locate and slice subsections

**Prior art (partial):** `tools/extraction-validator/inspect_tier4_doc.py:78-98`
splits markdown at `^##` headers; `tier4_cleaner.py:86-95`
(`_parse_markdown_tables`) tracks `current_section` from `##` headers. Reuse
these for the coarse top-level section slice.

**The real work is subsection-level.** The PRD targets are subsection-scoped
(H5-H8, C13-C22, D2-D16), not section-scoped, and Docling's output is
inconsistent at that granularity:

- Yale 2024-25 renders H5 as a proper `## H5` header
  (`tools/extraction-validator/runs/yale-2024-25/baseline/output.md:1373`).
- Harvard 2024-25 renders H5 as a single bullet line
  (`tools/extraction-validator/runs/harvard-2024-25/baseline/output.md:1469`).
- Dartmouth flattens D2 to paragraphs with no heading at all.

A simple `^## H5` regex will miss Harvard entirely. The slicer needs a
**subsection locator** with layered strategies, tried in order:

1. `^##\s+<subsection_code>\b` — the Yale case.
2. `^###\s+<subsection_code>\b` — third-level heading variant.
3. Bold/bulleted line containing the subsection code:
   `^(?:\*\*|\-\s+)?<subsection_code>[.:]?\s` — the Harvard case.
4. **Row-label anchor:** a known lead question text for that subsection
   (e.g. "Number of students borrowing from federal loans" anchors H5.01).
   Maintain a small `{subsection_code: [anchor_phrases]}` map per schema year.
5. **Forward-walk from nearest section header:** if H4 ends at line X and
   H6 starts at line Y, the H5 slice is `[X, Y)` — bounded-window fallback
   for fully flattened cases.
6. If all strategies fail, the subsection is marked unresolved and the LLM
   is not called for it. Cost is zero on unresolvable slices.

Output shape remains flat per attempted subsection:

```python
{
  "H5": "...markdown slice...",
  "H6": "...markdown slice...",
  "C1302_anchor": "...bounded window...",  # for single-field anchors
}
```

This is a **real parser**, not a regex one-liner. Phase 0's validator layer
includes a "slicer correctness" report: per benchmark doc, which strategy
succeeded for each subsection, and which fell through to bounded-window or
unresolved. If the fallthrough rate is high on target subsections, the
cost/correctness assumptions for section-scoped prompts do not hold, and
the decision gate should capture that.

### Step 4: Build cached section prompt

The prompt payload is split into a **cached head** (stable across docs) and
an **uncached tail** (this doc's markdown + gap set). Concrete shape:

```python
# Cached head — keyed by (section_code, schema_version, prompt_version)
{
  "extraction_instructions": "...",        # stable prose
  "output_json_schema": {...},             # stable
  "docling_failure_modes": [...],          # the seven shapes enumerated above
  "checkbox_dialects": [                   # so the LLM recognizes all four
    "- [x] Label",
    "- [ ] X Label",
    "| ☒ Label |",
    "- X Label"
  ],
  "schema_fields": [                       # section-scoped
    {
      "question_number": "H.501",
      "question": "Number of students borrowing from federal loans",
      "pdf_tag": "FED_LOAN_N",             # disambiguates 20 irreducibly
                                           # ambiguous fields
      "value_type": "Number",
      "dimensions": {
        "cohort": "2024 graduating class",
        "unit_load": "All",
        "residency": "All",
        "category": "All"
      },
      "cross_field_note": "Must be ≤ H.401 (total class size)"
    }
  ]
}

# Uncached tail — per doc
{
  "school_id": "...",
  "cds_year": "2024-25",                   # derived from detected_year; not inferred
  "section_code": "H5",
  "section_markdown": "...",               # from the slicer, NOT the whole doc
  "already_extracted": {                   # so the LLM doesn't duplicate
    "H.401": "1753",
    "H.2203": "98"
  },
  "known_hints": [                         # deterministic heuristics as hints
    "template uses 'men/women' for gender but schema says 'males/females' — treat as synonyms",
    "rows where the label contains ≥2 known field names are ambiguous — flag, don't guess",
    "pre-2020 templates use 'freshman/freshmen' — schema uses 'first-year'",
    "'nonresident aliens' and 'nonresidents' are the same dimension"
  ]
}
```

This is where prompt caching pays off:

- the cached head is keyed by `(section_code, schema_version, prompt_version)`
  and invariant across documents in the same year's schema
- the doc-specific tail (markdown + `already_extracted`) is the only uncached
  portion
- pre-normalization of gender/cohort labels happens in-code before the
  markdown is sent, so the model sees canonical labels
- `pdf_tag` disambiguates **only 14 of the 20** irreducibly ambiguous fields
  via tag prefix:
  - 10 × C.11xx GPA rows (`FRSH_GPA_SUBMIT` / `FRSH_GPA_NO_SUB` / `EN_FRSH_GPA`)
  - 4 × H.2A FT/PT columns (`UG_FT_` vs `UG_PT_`)
- The remaining 6 need other strategies surfaced as prompt hints:
  - **D.13–D.16 (4 fields):** credits-count vs unit-type are two *columns*
    within the same row. The prompt must tell the LLM to return both
    column values per row, not pick one. Disambiguated by position within
    the row, not by tag.
  - **C.16 / C.17 (2 fields):** same "Date: Month" / "Date: Day" text
    across two different deadline contexts. Disambiguated by **surrounding
    anchor text** (the deadline label that precedes the date pair). The
    prompt should ask for each date tied to its nearest preceding
    deadline-label anchor.

### Step 5: LLM returns only missing fields

The model is asked to:

- extract only the listed fields
- omit anything unsupported by the text
- return evidence text for every field
- never infer values from neighboring rows
- never synthesize totals

### Step 6: Deterministic verification layer

Every returned field goes through:

1. **Type check** against schema `value_type`. Reuse `_extract_number()` and
   `_extract_currency()` from `tier4_cleaner.py` — they already reject
   "Not Applicable", "varies", "n/a", and free-text leakage before a bad
   value lands.
2. **Evidence check**: `evidence_text` must exist in `notes.markdown` exactly
   or via bounded fuzzy match, and include a markdown offset so reviewers
   can verify.
3. **Section-local sanity checks**:
   - percentages in 0-100
   - month in 1-12, day in 1-31
   - dollar values parse as currency
   - cohort counts ≤ total-enrolled
   - admissions counts satisfy basic inequalities (admitted ≤ applied,
     enrolled ≤ admitted)
4. **Cross-field consistency** where the schema gives us constraints:
   - if G.101 (FY tuition) = $59,320 and the LLM populates G.102 (UG
     tuition), flag any >5% discrepancy
   - Total-rows from the CDS template are authoritative only when the school
     filled them; the LLM must not synthesize totals to fill in blanks
5. **Row-merge guard**: if the evidence text's label matches ≥2 known field
   patterns (e.g. "Percent below 1.0 Totals should = 100%"), flag and drop.
   The cleaner already uses this guard; the LLM output should be held to
   the same rule.
6. **No-clobber merge policy**

Any field that fails validation is dropped or flagged. `notes.markdown`
remains the authoritative evidence source for human review.

## Merge policy

Three rollout modes:

### Mode A: `shadow`

- LLM artifact is written separately
- no merge into user-facing canonical values
- used for benchmark/evaluation only

### Mode B: `fill_gaps` (recommended default)

- deterministic values win
- LLM can only populate missing question numbers
- no overrides

### Mode C: `promote`

- LLM may replace existing Tier 4 cleaner values, but only under explicit rules
- not in scope for initial launch

This PRD approves **Mode B** only.

## Model strategy

### Default model

Use a **cheap text-first structured-output model** as the default for markdown-section
repair. The exact vendor/model can stay configurable, but the operating assumption is:

- low-cost model first
- prompt caching enabled
- structured JSON output required

### Escalation model

Only escalate to a stronger or multimodal model if:

- the markdown slice is clearly broken or empty
- the section is high value
- the cheap model failed validation
- budget allows

This escalation path is optional and should not ship in v1 of the fallback.

### Multimodal path

Multimodal PDF-page extraction is explicitly **not** the default Tier 4 fallback. It is
reserved for future `pdf_scanned` or pathological markdown corruption cases. The whole
point of this PRD is to avoid paying multimodal rates on the common case.

## Prompt caching design

### Cache key

The cache key must invalidate on all meaningful extraction changes:

```text
(
  source_sha256,           -- from cds_documents.source_sha256
  markdown_sha256,         -- hashed locally from notes.markdown
  section_name,
  schema_version,
  model_name,
  prompt_version,
  strategy_version,
  cleaner_version,         -- NOT NULL default '' — no coalesce() needed
  missing_fields_sha256
)
```

`missing_fields_sha256` matters because the prompt is different when the cleaner
improves and the gap set shrinks. `markdown_sha256` matters because a re-run of
Docling on the same PDF can produce different markdown (Docling version bumps),
and we should not reuse a stale response against new markdown.

### What gets cached

Cache the final model response for a section prompt, not just token accounting.

Stored metadata:

- model
- prompt version
- input tokens
- output tokens
- estimated cost
- created_at
- status (`ok`, `validation_failed`, `budget_skipped`)
- raw response json

### Cache hit policy

If the same document + same section + same missing-field set + same prompt version shows
up again, reuse the cached response and re-run deterministic verification locally.

That means:

- stable results across reruns
- no re-billing on unchanged docs
- cheap reprocessing after worker restarts

## Cost envelope

The fallback is only viable if cost is boring.

### Budget rules

- hard cap per document per run: `$0.02`
- hard cap per document per day: `$0.05`
- hard cap per full worker run: `$5.00`
- environment-variable override for manual benchmark runs

### Expected low-cost shape

If the cleaner already covers much of the document, most docs should:

- invoke 0-3 section prompts
- send markdown slices, not full docs
- hit cached prefixes

That keeps the fallback in the "few mills to few cents per doc" range rather than
"LLM wrapper around the whole corpus."

## Data-model changes

### New table: `cds_llm_cache`

Hash sources — grounded in what actually persists today:

- **`source_sha256`** mirrors `cds_documents.source_sha256` (the PDF bytes hash
  — the one persisted hash we have in production today, see
  `supabase/migrations/20260413201910_initial_schema.sql:38`).
- **`markdown_sha256`** is hashed locally at runtime from `notes.markdown` on
  the `tier4_docling` artifact. We do *not* rely on `cds_artifacts.sha256` —
  that column exists but is not populated by the current Tier 4 canonical
  writer (`tools/extraction_worker/worker.py:420`).

```sql
create table public.cds_llm_cache (
  id                     uuid primary key default gen_random_uuid(),
  document_id            uuid not null references public.cds_documents(id) on delete cascade,
  source_sha256          text not null,          -- from cds_documents.source_sha256
  markdown_sha256        text not null,          -- sha256(notes.markdown) computed at runtime
  section_name           text not null,
  schema_version         text not null,
  model_name             text not null,
  prompt_version         text not null,
  strategy_version       text not null,
  cleaner_version        text not null default '',  -- NOT NULL + default so unique index is simple
  missing_fields_sha256  text not null,
  status                 text not null check (status in ('ok','validation_failed','budget_skipped','in_flight')),
  input_tokens           integer,
  output_tokens          integer,
  estimated_cost_usd     numeric(10,6),
  response_json          jsonb,
  created_at             timestamptz not null default now()
);

-- Uniqueness enforced by a dedicated unique index (not a table UNIQUE
-- constraint) so we can include any future expression columns if needed.
-- With cleaner_version NOT NULL + default '', no coalesce() is required.
create unique index cds_llm_cache_key_idx on public.cds_llm_cache (
  source_sha256,
  section_name,
  schema_version,
  model_name,
  prompt_version,
  strategy_version,
  cleaner_version,
  missing_fields_sha256
);
```

Internal table only. No public read.

### New artifact producer

No new base-table columns required if the fallback writes a separate `cds_artifacts`
row:

- `kind = 'cleaned'` is preferred for the benchmark and first launch
  (already in the CHECK constraint; no migration needed)
- `producer = 'tier4_llm_fallback'` (producer is freeform text)
- `schema_version` is derived from `cds_documents.detected_year` per ADR 0007,
  not hardcoded.
- **Schema-year compatibility:** the CDS schema changes minimally year-over-year.
  For Phase 0 benchmarking, the 2025-26 schema JSON (the only schema currently
  in `schemas/`) is used as a near-identical proxy for 2024-25 benchmark docs.
  The benchmark harness MUST compute and log a field-drift check (count of
  `question_number` values present in one schema and absent/renamed in the
  other) and fail the run if drift exceeds a configured threshold for the
  attempted sections. Without this, a schema-year mismatch silently lowers
  apparent coverage.
- **Production gate (Phase 1+):** exact-year match only. If `detected_year` is
  `2022-23` and no `cds_schema_2022_23.json` exists, the document is skipped.
  Near-year proxying is explicitly a benchmark-only affordance; production
  writes must match the schema year they claim.
- The `schema_version` column on the artifact always reflects the schema
  *used for extraction*, not the document's year. If the benchmark runs a
  2024-25 doc against the 2025-26 schema, `schema_version='2025-26'` and the
  artifact notes carry a `schema_year_proxy_for='2024-25'` field.

Using `cleaned` keeps it clearly separate from the existing canonical Docling output
while the benchmark is still proving itself.

### Optional later view

If `fill_gaps` proves reliable, add a view that merges:

- latest `tier4_docling` canonical values
- latest `tier4_llm_fallback` cleaned values

without rewriting source artifacts.

## Worker integration

### New worker

Add:

`tools/extraction_worker/llm_fallback_worker.py`

Responsibilities:

1. Find eligible documents with a `tier4_docling` artifact
2. Read markdown + current values
3. Decide whether to run fallback
4. For each selected section:
   - compute missing fields
   - check cache
   - call model if needed
   - validate response
5. Write `tier4_llm_fallback` artifact

### Why a separate worker

Keep it separate from `worker.py` initially because:

- it has budget logic
- it has cache logic
- it should be easy to disable
- it should support benchmark runs without perturbing the main extraction loop

If it proves stable, it can be called as a post-step from `worker.py` for `pdf_flat`.

## Phasing

### Phase 0: Benchmark harness only

Phase 0 is intentionally scoped as a **standalone benchmark script** that writes
JSON to disk. No new worker, no DB writes, no migration. The decision gate
(coverage lift / no regression / cheap enough) must fire on real numbers
**before** DB-shaped infrastructure lands. If the gate passes, Phase 1 adds the
worker and the `cds_llm_cache` migration.

**Deliverables (Phase 0):**
- Standalone benchmark CLI (e.g., `tools/extraction_worker/llm_fallback_bench.py`)
  that reads existing `tier4_docling` artifacts, runs section-scoped prompts,
  validates responses, writes a single JSON report per run.
- Factored section slicer (shared with `inspect_tier4_doc.py`).
- Prompt builder.
- Validator layer.
- LLM client module at `tools/extraction_worker/llm_client.py` with:
  - default model + vendor picked now (recommend **Claude Haiku 4.5** with
    prompt caching via the Anthropic SDK — cheapest structured-output path in
    the SDKs we already understand)
  - API key via `ANTHROPIC_API_KEY` env var (consistent with existing
    `tools/` conventions; document in `tools/extraction_worker/README.md`)
  - structured JSON output + prompt-cache flags
- No DB writes in Phase 0. No migration.

**Benchmark set:**
- **3 Tier 4 GT docs** (dartmouth, harvard, yale 2024-25). Harvey Mudd is
  explicitly *excluded* — it is a Tier 2 fillable-PDF GT case
  (`docs/backlog.md:47`, `docs/known-issues/harvey-mudd-2025-26.md:4`) and
  belongs to the deterministic path, not the Tier 4 fallback. Including it
  would either inflate apparent benchmark quality or force the harness to
  special-case a non-target format.
- 20 low-coverage Tier 4 docs sampled from the corpus survey's bottom quintile.
- 10 pathological docs with known weird markdown (row-merged, header-promoted,
  fully flattened-to-paragraphs) sampled deliberately to cover the seven
  Docling failure modes.
- Expanding the Tier 4 GT set to 8-10 docs is a Phase 0 side-deliverable if
  time allows — current count (3) is the regression gate, not the coverage
  gate.

**Success criteria:**
- no changes to the main extraction path
- benchmark JSON report written cleanly to disk
- cost tracked accurately
- decision gate (see end of PRD) can be evaluated from the report alone

Phases 1–3 are ordered by the learnings doc §5 priority list — combination
of (schema weight × current gap × structural fixability). This is a
deliberate inversion of the original PRD 006 phasing, which started with
B/C. Measured cleaner coverage shows B-section sections are already ≥60%
filled; the LLM's leverage is in H, D, C13-C22, G5 — where the cleaner is
at single-digit or teens coverage.

### Phase 1: H5–H8 + C13–C22 (highest-leverage)

Start where the cleaner coverage gap is largest on fields users actually
care about:

- **H5 / H6 / H7 / H8 (~80 fields)**: loan totals, aid to nonresidents,
  financial-aid forms and deadlines. Mixes small tables, free-text prose,
  checkbox dialects — currently zero coverage.
- **C13–C22 (~56 fields)**: application fee, deadlines, reply dates, early
  decision. Paired-anchor MM/DD pairs with multiple deadlines per page —
  breaks inline regex, works well with a section-scoped LLM.

**Success criteria:**
- no regression on existing GT docs
- ≥50% coverage on H5–H8 and C13–C22 fields on the benchmark slice
- median cost per attempted doc ≤$0.01

### Phase 2: D2–D16 + G5 + C11 (Yale/Dart paragraph-rendered)

Sections where Docling flattens tables and the LLM should reconstruct:

- **D2–D16 (~80 fields)**: transfer applicants + transfer credit policies.
  Docling flattens aggressively; an LLM fed the whole `## D.` window can
  reconstruct what the table parser can't.
- **G5 (~13 fields)**: residents / commuters / living-with-family blocks of
  books / housing / food / transport / other. Currently zero on Harvard.
- **C11 GPA profile — paragraph renderings only (~20 fields)**: Yale and
  Dartmouth render C11 as paragraphs where Harvard renders it as a table.
  Same schema, different output. The cleaner skips Yale/Dart; the LLM should
  recover them.

### Phase 3: C9 policies + A contact + J disciplines long tail

Lower-leverage but structurally fixable:

- **C9 test-score policy (~46 fields)**: composite-use YesNo and
  "which tests your institution accepts" matrices (not percentiles — those
  are cleaner-owned).
- **A contact fields (~26 fields)**: phone, URL, email. Low consumer value
  but near-trivial for named-entity extraction.
- **J disciplines remaining (~70 fields)**: most schools only fill one
  column; fallback can pick up the second and third where the school
  actually populated them.

Proceed only if Phases 1 and 2 show the fallback is cheaper than hand-coding
for their targeted sections.

## Validation strategy

### 1. Existing GT scorer

Extend `score_tier4.py` with:

- `--include-llm-artifact <json>`
- or a merge mode that evaluates cleaner-only vs cleaner+fallback

Hard rule: no regression on the current audited schools.

### 2. Existing corpus survey

Do not invent a separate coverage universe. Extend `corpus_survey_tier4.py` to
load both `tier4_docling` and `tier4_llm_fallback` artifacts for each document
in a single pass and compute the delta in-script (not by running the tool
twice and diffing). The current `field_coverage: Counter` structure under
`--json` supports this directly.

Compare:

- cleaner only
- cleaner + fallback (merged per Mode B: fallback fills gaps only)

Track:

- per-question coverage delta
- docs with positive lift
- docs with suspiciously large jumps

### 3. Cost dashboard

Per run, report:

- docs attempted
- docs skipped
- sections attempted
- cache hit rate
- median/95p estimated cost per doc

### 4. Manual spot-checks

After each phase:

- randomly inspect 20 new fallback-populated fields
- inspect 10 rejected fields
- inspect 5 docs with the biggest field-count jump

## Risks

| Risk | Mitigation |
|---|---|
| LLM fills wrong repeated labels | Section-scoped prompt + schema subset + deterministic validation + no-clobber merge |
| Prompt caching does not save much | Keep prompts section-stable and markdown-tail small; benchmark actual cache hit rate before rollout |
| Cheap model is too weak | Benchmark first; escalate model only for proven cases |
| Fallback becomes primary path by stealth | Run only on low-coverage docs; keep separate artifact producer |
| Cost drifts upward | Hard budget gates in worker; skip when budget exhausted |
| Markdown is too broken (flattened tables, merged rows, promoted headers) | Prompt explicitly enumerates the seven Docling failure modes from learnings §2; leave section unresolved if the model cannot anchor evidence |
| Wrong-file / blank-template archives | LLM must emit a `document_mismatch` or `blank_template` signal rather than hallucinate — validator rejects any artifact where evidence coverage is suspiciously near zero across all attempted sections |
| LLM hallucinates totals the school left blank | Non-goal explicitly prohibits computing totals/ratios; validator rejects any field whose evidence text is a computed sum rather than a verbatim substring |
| Artifact sprawl/confusion | Keep producer/kind explicit and merge only through a deliberate view or fill-gaps mode |

## Decision gate

This PRD should only proceed past Phase 0 if the benchmark shows all three:

1. **Coverage lift:** meaningful improvement on low-coverage docs
2. **No regression:** current GT stays green
3. **Cheap enough:** steady-state cost is comfortably hobby-project small

If any of those fail, the fallback should remain an experiment and the project should
either:

- keep investing in PRD 005's section-family resolvers
- or revisit a stronger-model path only for a narrower subset of documents

### PRD 005 vs PRD 006 section ownership

PRD 005 (hand-coded section-family resolvers) and PRD 006 (LLM fallback)
target overlapping sections (B, C, G, I, J, H). To prevent duplicated work,
the tiebreaker is per-section and evaluated from the Phase 0 benchmark report:

> For a given section S, if the LLM fallback achieves **≥20% absolute
> coverage lift** over the cleaner at **≤$0.01 per doc** on the benchmark
> slice, PRD 006 owns S and PRD 005 does not build a hand-coded resolver for
> it. Otherwise PRD 005 owns S and the fallback does not attempt it.

Thresholds are starting points — the first benchmark run may adjust them
once we see real numbers. The rule, not the exact cutoffs, is what matters:
sections are owned by exactly one PRD.

## Files modified

| File | Change | Phase |
|---|---|---|
| `tools/extraction_worker/llm_fallback_bench.py` | Standalone Phase 0 benchmark CLI; no DB writes | 0 |
| `tools/extraction_worker/llm_client.py` | Anthropic SDK wrapper with prompt-cache flags, `ANTHROPIC_API_KEY` env | 0 |
| `tools/extraction_worker/tier4_llm_fallback.py` | Prompt builder, factored section slicer (shared with `inspect_tier4_doc.py`), validators, merge policy | 0 |
| `tools/extraction_worker/llm_fallback_worker.py` | Production worker; loads `cds_llm_cache`; writes `tier4_llm_fallback` artifacts | 1 |
| `tools/extraction-validator/score_tier4.py` | Add cleaner-vs-fallback comparison mode | 1 |
| `tools/extraction-validator/corpus_survey_tier4.py` | Load both producers per doc; in-script delta | 1 |
| `supabase/migrations/*_cds_llm_cache.sql` | New cache table | 1 |
| `tools/extraction_worker/README.md` | Document `ANTHROPIC_API_KEY` env var and fallback operation | 0 |
| `docs/ARCHITECTURE.md` | Document fallback layer once shipped | 2+ |

## Summary

The recommended path is not "replace the cleaner with an LLM." It is:

1. Keep Tier 2 deterministic
2. Keep Docling
3. Keep the current Tier 4 cleaner
4. Add a **cheap, cached, section-scoped markdown fallback**
5. Let the benchmark decide how much of the long tail belongs to the LLM versus
   section-specific code

That gives the project an adaptive path: deterministic where the corpus is clean,
LLM-assisted where the markdown long tail is not worth hand-coding immediately, and
without committing the project to full-document multimodal spend.
