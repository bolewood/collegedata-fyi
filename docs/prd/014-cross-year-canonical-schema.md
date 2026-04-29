# PRD 014: Cross-year canonical schema and year-aware extraction

**Status:** Draft v3 — pre-implementation cross-check complete; data model revised after Codex review (tri-state equivalence + selected-result schema-awareness now first-class)
**Created:** 2026-04-28
**Author:** Claude + Anthony
**Related:** [PRD 005](005-full-schema-extraction.md), [PRD 010](010-queryable-data-browser.md), [PRD 011](011-academic-profile-llm-repair.md), [PRD 012](012-browser-field-expansion-after-v03.md), [Schema README](../../schemas/README.md), [Templates archive](../../schemas/templates/SOURCES.md)

---

## Context

The project just invested significant cleaner work to improve Tier 4
extraction quality on 2024-25 documents. That investment is partly self-defeated
by a structural assumption baked into the extractors:

- `tools/extraction_worker/tier4_cleaner.py:362` hardcodes
  `_SCHEMA_PATH = .../schemas/cds_schema_2025_26.json`.
- `tools/extraction_worker/worker.py` defaults `--schema` to the 2025-26 file.
- The Tier 1 XLSX extractor and Tier 2 acroform extractor both load whatever
  schema the worker passes them, which today is always 2025-26.

The result: every 2024-25 document is currently being extracted against a
slightly-wrong field set. Sections C, I, J have identical question counts
between 2024-25 and 2025-26 — those map cleanly today by accident. Sections
A (51 vs 63), B (219 vs 204), D (73 vs 88), and H (154 vs 165) carry real
drift. The Tier 4 cleaner's `_PHRASE_TO_QNUM` mapping is keyed on 2025-26
question text. The Tier 1 cell-mapping uses 2025-26 sheet layout. Tier 2
acroform looks up `pdf_tag` from 2025-26 against potentially-different
2024-25 fillable PDFs. PRD 012 phase 0 already observed this failure mode in
practice ("SAT/ACT parse errors in XLSX rows where C9 fields contain values
such as 'Very Important', 'Important', 'Considered'") — that is a value-type
mismatch caused by mapping 2024-25 cells against 2025-26 slots.

A canonical 2024-25 schema is now possible because the 2024-25 XLSX template
turned out to include an `Answer Sheet` tab, contradicting the prior
assumption (recorded in `schemas/README.md`) that only 2025-26 carries one.
The 2024-25 Answer Sheet is reduced — it omits `Sort Order`, `US News PDF Tag`,
and `Word Tag` columns, and uses an undotted question-number format
(`A01`, `B101`, `C916`) — but the question text and section structure are
authoritative.

This PRD makes year-awareness explicit across the schema pipeline and
extractor stack, ships the 2024-25 canonical schema, and documents the
contributor process so future template years can be onboarded predictably.

## Pre-implementation cross-check (2026-04-28)

Before defining milestones, two questions had to be answered against the actual
template files. Results below; they materially reshape the plan.

### Finding 1 — Section C academic-profile fields are EXACT match across years

PRD 012's launch-certified academic-profile fields all have byte-identical
question text and section assignment between 2024-25 and 2025-26:

| Field range | Status |
|---|---|
| `C.905`–`C.916` (SAT/ACT percentiles, 12 fields) | EXACT match |
| `C.1201`, `C.1202` (GPA fields) | EXACT match |
| `C.901`, `C.902` (SAT/ACT submit rates) | Minor drift — 24-25 says "Submitting SAT scores", 25-26 says "Percent Submitting SAT scores"; semantically identical |

**Implication:** PRD 012's academic-profile columns are SAFE for 2024-25 documents
under year-aware extraction. The `year_start >= 2024` scope can be confirmed,
not retreated from. This is the most valuable finding in this cross-check.

### Finding 2 — Section C admissions-count fields are COMPLETELY MISALIGNED

The `C.10x` admissions-count range underwent a structural change between years:

- **2024-25** uses 4 gender categories: men, women, another gender, unknown gender
- **2025-26** uses 3 categories: males, females, unknown sex

Result: the canonical IDs in the `C.101`–`C.116` range mean **completely
different fields** between years. Examples:

| ID | 2024-25 question | 2025-26 question |
|---|---|---|
| `C.103` | first-year another gender who applied | first-year unknown sex who applied |
| `C.116` | part-time first-year unknown gender who enrolled | first-year students who applied (total) |

The current production codebase (`tools/browser_backend/project_browser_data.py:138-145`)
maps:

```python
"applied"             → C.116
"admitted"            → C.117
"first_year_enrolled" → C.118
```

This works today because the cleaner uses 2025-26 schema for all years and
writes 2025-26 IDs into `cds_artifacts.notes.values`. **Once M3 ships year-aware
extraction**, 2024-25 documents will write `C.116` values that mean
"part-time-unknown-gender enrolled" rather than "applied" — and the
`applied`/`admitted`/`first_year_enrolled` browser columns will silently break
for every 2024-25 document. This is a critical correctness issue introduced
by year-aware extraction in its naive form.

### Finding 3 — Section C aggregate overlap

Of 268 section-C question numbers in 2024-25 and 278 in 2025-26:

- 254 IDs are shared
- Of those 254 shared IDs: 165 EXACT text match, 17 FUZZY (first-30-char match),
  72 DRIFT
- 14 IDs are 2024-25-only (mostly the "another gender" / "non-binary" fields)
- 24 IDs are 2025-26-only

The 72 "drift" cases concentrate in the C.10x and B.1xx ranges — the
gender-category restructure cascades through anywhere gender-by-cohort breakdowns
appear.

### Finding 4 — `pdf_tag` synthesis is highly viable

Of 1,116 AcroForm field names in the 2024-25 fillable PDF, **1,084 (97%) match
2025-26 schema `pdf_tag` values directly** by string equality. The 32
non-matches are all `*_NON_BINARY_*` fields — exactly the 2024-25-only "another
gender" category that 2025-26 dropped. Tier 2 acroform extraction for 2024-25
fillable PDFs is therefore feasible without complex matching logic.

### Finding 5 — 23 IDs use a sub-letter format the simple normalization rule misses

Both 2024-25 and 2025-26 contain IDs like `A0A`, `C8D`, `C8E01`, `C8G01`,
`H2A01` (in 2024-25) / `A.0A`, `C.8D`, `C.8E01`, `C.8G01`, `H.2A01` (in 2025-26).
The naive `<letter>.<digits>` normalization rule fails on these. Corrected rule:

```python
# After section letter, insert dot. If remainder is all digits, zero-pad to ≥3.
# Otherwise (sub-letter present), preserve remainder as-is.
def normalize_id(raw):
    m = re.match(r'^([A-Z])(.+)$', raw)
    if not m: raise ValueError(raw)
    rest = m[2]
    if rest.isdigit():
        rest = rest.zfill(3)
    return f"{m[1]}.{rest}"
```

Both years already follow this convention. The rule must be tested against:
`A01` → `A.001`, `A511` → `A.511`, `B2101` → `B.2101`, `A0A` → `A.0A`,
`C8G01` → `C.8G01`, `H2A01` → `H.2A01`.

## Goals

1. Produce a canonical `schemas/cds_schema_2024_25.json` that mirrors the
   2025-26 schema's shape (with documented gaps where the 2024-25 Answer
   Sheet is reduced).
2. Make the cleaner and the Tier 1 / Tier 2 extractors year-aware: given a
   document's `canonical_year`, load the matching schema. Fall back to the
   most-recent-available canonical schema when no year-specific schema exists,
   with explicit `notes.schema_fallback_used: true` on the artifact.
3. Ship a cross-year **field-equivalence layer with four classification
   kinds**, not a flat alias map: `direct` (same semantic field across years),
   `derived` (per-year formula like `applied_2024_25 = sum of gender-cohort
   sub-fields`), `preserved-only` (source field kept in `cds_fields` but not
   surfaced in browser metrics), and `unmapped` (year-specific field with no
   cross-year analogue). The projection layer (`MetricDefinition` mapping in
   `project_browser_data.py`) reads through this layer to apply year-correct
   formulas. Per Finding 2, this is a hard prerequisite for M3 — without it,
   year-aware extraction silently breaks `applied`/`admitted`/
   `first_year_enrolled` for all 2024-25 documents. The flat alias model
   proposed in v2 is insufficient because admissions counts genuinely require
   per-year aggregation, not relabeling.

   Critically: `cds_fields.field_id` remains the **source schema's field ID**.
   The equivalence layer adds `canonical_field_id`, `equivalence_kind`, and
   `schema_version` as separate columns. Source fidelity is preserved for
   debuggability; cross-year queries join through the equivalence layer.
4. Establish a reproducible contributor process for adding a new template year
   (this happens once a year, indefinitely — 2026-27 will exist).
5. Archive the 2024-25 templates in the repo so the schema pipeline is
   reproducible without depending on commondataset.org's CDN, which has
   already proven to rotate prior-year files.
6. Produce a documented 2024-25 vs 2025-26 canonical-field diff so PRD 010
   and PRD 012 can replace cross-year reconciliation hand-waving with
   explicit field-by-field equivalence rules.

## Non-goals

- Not solving the canonical-schema problem for 2019-20 through 2023-24. Those
  templates lack an Answer Sheet; the structural-schema approach in
  `schemas/README.md` remains the only path for those years. Any contributor
  effort on pre-2024 canonical mapping is welcome but is out of scope here.
- Not running a corpus-wide re-extraction. That decision is gated on milestone
  M4 below — re-extracting 3,000+ documents costs hours of wall-clock plus
  cascades through projection and fallback caches. The decision belongs in a
  follow-on PRD informed by M4's measured delta.
- Not rebuilding the Tier 4 fallback cache. Same reasoning: handle as a
  separate decision after M3 / M4 measurement.
- Not changing the public `cds_fields` or `school_browser_rows` API shape.
  This PRD adds correctness behind those surfaces; it does not break them.
- Not adopting a generic "schema registry" abstraction. Year-by-year file
  loading with a fallback is sufficient for the next several years.

## Required pre-implementation work

### 1. Decide which extractors must become year-aware in scope

All three deterministic extractors (Tier 1 XLSX, Tier 2 acroform, Tier 4
Docling cleaner) currently consume schemas. Tier 6 (HTML) and Tier 5
(force-OCR via Tier 4) inherit Tier 4's choice. Default scope: all three
deterministic extractors plus the Tier 4 fallback's schema lookups. Decide
explicitly before M3 whether any can be deferred; the test surface scales
with the count.

### 2. Confirm template-archival policy

Templates older than the current year are now considered archival artifacts
worth committing to the repo. See `schemas/templates/SOURCES.md` for the
provenance convention. The existing `tools/schema_builder/README.md:109`
language ("templates ... live in `scratch/` as working artifacts rather than
being committed") needs an update to reference the new archival directory
and the "no longer on commondataset.org → archive here" rule.

### 3. Confirm fallback semantics for unknown years

If a document's `canonical_year` is `2026-27` and no matching schema exists
yet (because the contributor hasn't run the onboarding process), the
extractor should use the closest prior schema and log a clear warning, not
crash or silently fall back to a default. Default recommendation: use the
most-recent-available schema with a one-line warning recorded in the
artifact's `notes.schema_fallback_used: true`.

## Recommendation

Execute as five milestones (was four; M2.5 added by the cross-check) with
explicit go/no-go decisions between them. Stop at any milestone if the next
one's value isn't clear from the prior one's output.

Effort estimates have been revised upward by 2x from the original draft based
on the project's history of optimistic milestone sizing and the new equivalence-
layer scope.

### M1 — Canonical 2024-25 schema in the repo

**Effort:** ~half day (was ~2h).

1. Adapt `tools/schema_builder/build_from_xlsx.py` to handle the reduced
   2024-25 column layout. Detect columns by header name, not position. Emit
   `pdf_tag: null` and `word_tag: null` for years where those columns are
   absent.
2. Normalize question-number format per Finding 5's corrected algorithm:
   insert `.` after the section letter; zero-pad to ≥3 if remainder is all
   digits, otherwise preserve. Test cases: `A01`→`A.001`, `A511`→`A.511`,
   `B2101`→`B.2101`, `A0A`→`A.0A`, `C8G01`→`C.8G01`, `H2A01`→`H.2A01`.
3. Run the adapted builder against
   `schemas/templates/cds_2024-25_template.xlsx`, producing
   `schemas/cds_schema_2024_25.json`. Verify it builds 2025-26 byte-identically
   too (no regression).
4. Update `schemas/README.md` to:
   - Reflect that 2024-25 has a (reduced) Answer Sheet
   - Update the cross-year coverage table (2024-25 row flips from `—` to `✅`)
   - Remove the stale "Build a schema diff tool" Next-Steps bullet (the diff
     files already exist) and the "Get the 2024-25 XLSX" bullet (done)
   - Document the corrected normalization rule from Finding 5

**Stop condition:** if the column-detection adaptation turns into a rewrite,
stop and decide whether to fork `build_from_xlsx_2024.py` instead of
generalizing.

**Value delivered:** schema exists, can be referenced by future code without
behavior change. Unblocks M2 / M2.5 / M3.

### M2 — Synthetic `pdf_tag`, decoded checkboxes, and semantically-classified diff

**Effort:** ~1 day (was ~half day).

1. Walk `schemas/templates/cds_2024-25_template.pdf`'s AcroForm field names.
2. Match each AcroForm field name to the corresponding 2025-26 `pdf_tag`
   value via direct string equality. Per Finding 4, this lands ~97%; the 32
   non-matches are all `*_NON_BINARY_*` fields specific to the 2024-25 4-gender
   model. Leave those `pdf_tag: null`.
3. **Validate `pdf_tag` matches by question text** before accepting them.
   For each matched (24-25 AcroForm name → 25-26 pdf_tag), confirm the 24-25
   Answer Sheet's question text for the field is semantically equivalent to
   the 25-26 schema's question text for that pdf_tag. Tag-name match without
   question-text match indicates the CDS Initiative renamed the form field
   to mean something else; treat as `pdf_tag: null` and log for review.
4. Update `schemas/cds_schema_2024_25.json` in place with the validated
   `pdf_tag` values.
5. Adapt `tools/schema_builder/decode_checkboxes.py` to handle the case where
   some fields have `pdf_tag: null`. Run it against the 2024-25 PDF.
6. Generate a 2024-25 vs 2025-26 cross-year diff with **four semantic
   classification kinds** (not just renamed/added/removed):
   - `direct` — same canonical ID, same semantic field, question text
     equivalent (modulo trivial wording drift like "Percent " prefix)
   - `derived` — different per-year structure, but a 2025-26 metric can be
     computed from a known formula over 2024-25 fields. C.10x admissions
     counts are the leading example: `applied_total_2024_25 = sum(C.101 + C.102 + C.103 + C.104)`.
   - `preserved-only` — field exists in source year, captured in `cds_fields`,
     but no cross-year analogue suitable for browser metrics
   - `unmapped` — field exists in source year, no 2025-26 analogue at all
     (e.g., 2024-25 non-binary fields)
   Save the classified diff as
   `schemas/cds_schema_2024_25-to-2025_26.diff.{json,md}`. Make the diff
   generator parameterized so future-year diffs reuse it.
7. Per Finding 1, confirm: SAT/ACT/GPA fields (C.901, C.902, C.905–C.916,
   C.1201, C.1202) all classify as `direct`. Per Finding 2, admissions counts
   (C.10x range) classify as `derived` with documented per-year formulas.

**Value delivered:** Tier 2 acroform extraction usable for 2024-25 fillable
PDFs. Cross-year diff becomes a real artifact citable by PRD 010 / 012, with
explicit semantic classifications that drive M2.5's data model.

### M2.5 — Tri-state field-equivalence layer (NEW; required by Finding 2)

**Effort:** ~1 day (was ~half day; expanded scope from flat alias to tri-state).

The naive M3 plan would silently break `applied`/`admitted`/`first_year_enrolled`
for 2024-25 documents (Finding 2). M3 cannot ship without an equivalence layer
that handles `direct`, `derived`, and `preserved-only` cases distinctly.

**Data model — `cds_fields` table changes:**

`cds_fields.field_id` continues to record the **source schema's** field ID
(e.g., 2024-25 docs write `C.103` even when 2025-26 has no semantic equivalent).
Source fidelity is preserved. Three new columns are added:

- `schema_version` — the schema version of the artifact that produced this row
  (probably already present; verify in M2.5 step 1)
- `canonical_field_id` — the equivalent 2025-26 ID, or NULL if `unmapped` /
  `preserved-only`
- `equivalence_kind` — one of `direct`, `derived`, `preserved-only`, `unmapped`

A new table `cds_canonical_field_equivalence(schema_version, field_id, canonical_field_id, equivalence_kind, derivation_formula)` stores the M2 classification.
`derivation_formula` is non-null only for `derived` rows and stores the SQL or
Python expression used by the projection layer.

**`MetricDefinition` model changes:**

Today: `MetricDefinition(canonical_metric, field_id, ...)` — single source field.
Revised: `MetricDefinition(canonical_metric, source_spec, ...)` where
`source_spec` is one of:

- `DirectAlias(field_id="C.916")` — the 2025-26 reference frame field, looked
  up via `canonical_field_id` from any year's source rows
- `DerivedFormula(per_year_formulas={"2024-25": "C.101 + C.102 + C.103 + C.104", "2025-26": "C.116"})` — explicit per-year aggregation rule

This means `applied`/`admitted`/`first_year_enrolled` become `DerivedFormula`-
backed metrics with two per-year rules. Other metrics (SAT/ACT/GPA) stay
`DirectAlias` since Finding 1 confirms they're cross-year identical.

**Steps:**

1. Audit current `cds_fields` schema; confirm/add the three new columns
   (`schema_version`, `canonical_field_id`, `equivalence_kind`).
2. Create `cds_canonical_field_equivalence` table; populate from M2's diff
   output. Ship as a SQL migration for reviewability.
3. Refactor `MetricDefinition` and `DIRECT_METRIC_DEFINITIONS` to support
   both `DirectAlias` and `DerivedFormula` source specs. Existing PRD 012
   metrics (SAT/ACT/GPA) become `DirectAlias`; admissions counts become
   `DerivedFormula`.
4. Update `project_browser_data.py` `build_projection_rows` to evaluate
   `DerivedFormula` per-year, reading the relevant source `field_id` values
   from `cds_artifacts.notes.values`.
5. Update `cds_field_definitions` seeding to include both schema versions
   (the new schema must seed alongside 2025-26).
6. Add tests with **value-level assertions**, not just counts:
   - Known 2024-25 fixture: `C.901` → `sat_submit_rate = 0.62` (or whatever
     the actual fixture value is) via `DirectAlias`
   - Known 2024-25 fixture: `C.101 + C.102 + C.103 + C.104` (gender-split
     applied counts) → `applied = N` via `DerivedFormula`
   - Known 2024-25 fixture: a non-binary field (e.g., `C.103`) lands in
     `cds_fields` with source `field_id = "C.103"`, `canonical_field_id = NULL`,
     `equivalence_kind = "unmapped"`, and is omitted from `school_browser_rows`
   - Known 2025-26 fixture: every field maps to itself via `DirectAlias`
     (identity equivalence under the same model)
7. Document the data model in `docs/queryable-browser-backend.md`.

**Stop condition:** if M2's classification reveals that any PRD 012
launch-certified metric requires `derived` semantics with non-trivial formulas
(e.g., the per-year aggregation needs a coefficient or filter), surface to
PRD 012 owners before implementing — the formula design becomes a separate
review.

**Value delivered:** `MetricDefinition`-based projection works correctly under
year-aware extraction with proper handling of derived metrics. PRD 012's
launched browser columns remain valid for 2024-25 documents. Cross-year query
consumers have a real data-model home.

### M2.75 — Selected-result schema awareness and rollback semantics (NEW)

**Effort:** ~half day.

`cds_manifest`'s "latest canonical artifact by `created_at`" rule is unsafe
under year-aware re-extraction. After M3 ships, every 2024-25 document gets a
new artifact (year-matched schema). If the year detection failed and the
artifact uses the fallback schema, it will silently beat the previous correct
artifact by recency. Need schema-awareness in selection.

**Steps:**

1. Update the selected-result logic in `project_browser_data.py` (or
   `cds_manifest` view, depending on where the precedence lives) to prefer
   artifacts whose `notes.schema_version` matches the document's expected
   year. Specifically:
   - Among canonical artifacts for a document, prefer those with
     `schema_version` matching `cds_documents.canonical_year`
   - Among year-matched artifacts, prefer producer order
     (`tier1 > tier2 > tier6 > tier4`) per existing logic
   - Among same-year same-producer artifacts, fall back to `created_at DESC`
   - Skip artifacts with `notes.schema_fallback_used = true` for documents
     where a non-fallback artifact also exists
2. Define a rollback script: given a document_id (or a list), revert the
   selected canonical artifact to the prior `created_at` value. Useful for
   recovering from a bad year-aware drain.
3. Add observability: log when an artifact is rejected for schema mismatch,
   when a fallback artifact is selected because no better option exists,
   and when the rollback script runs.
4. Tests: same-document with both a year-matched and a fallback artifact;
   verify year-matched wins regardless of `created_at`.

**Value delivered:** safe to run year-aware re-extraction; bad artifacts can
be rolled back without DB surgery; selected-result logic understands schema
correctness as a first-class concern.

### M3 — Year-aware extractor dispatch (narrowed scope)

**Effort:** ~1 day.

**Explicit scope:** schema loading and dispatch for **Tier 1, Tier 2, and
schema-aware lookups in Tier 4** (`SchemaIndex.filter()` and value-type
metadata). **Out of scope for M3:** the Tier 4 cleaner's phrase-matching
logic (`_PHRASE_TO_QNUM`), which remains 2025-26-keyed and ships its
correctness improvement in M6. Calling this out explicitly because the v2
draft's "year-aware extractors" framing was misleading — the cleaner's actual
extraction routing isn't fixed by this milestone.

**Schema-year dispatch precedence chain.** Per source format:

- PDFs (Tier 2 fillable, Tier 4 flat, Tier 5 scanned): use
  `cds_documents.canonical_year`. Fall back to a parsed year from the
  document filename if `canonical_year` is null. If both are null, use the
  fallback policy.
- XLSX (Tier 1): use `cds_documents.canonical_year`. The XLSX itself doesn't
  carry a reliably-detectable year header, so `canonical_year` is the only
  source of truth.
- HTML (Tier 6): use `cds_documents.canonical_year`. HTML has no in-document
  year detection.
- DOCX (Tier 3, future): same as XLSX.

For all formats: if `canonical_year` is unset and no other reliable signal
exists, log a warning and use the most-recent-available schema with
`notes.schema_fallback_used: true`. Test each source format independently —
the dispatch path is uniform but the year-source resolution differs.

**Steps:**

1. Audit every schema consumer before touching code. Run:
   ```bash
   grep -rn 'cds_schema_2025\|load_schema\|SchemaIndex' tools/ supabase/ web/
   ```
   Confirmed consumers from prior audit:
   - `tools/extraction_worker/tier4_cleaner.py:362` — `_SCHEMA_PATH` constant
   - `tools/extraction_worker/worker.py` — main dispatch
   - `tools/extraction_worker/tier4_llm_fallback.py` — fallback context
   - `tools/extraction_worker/llm_fallback_worker.py` — second fallback worker
     (missed in v2 audit; verify schema usage)
   - `tools/browser_backend/project_browser_data.py` — `load_schema_definitions()`
   - `tools/extraction-validator/run_matrix.py` — validator harness
   Each match must be reviewed and either made year-aware or explicitly
   exempted with rationale.

2. `tools/extraction_worker/tier4_cleaner.py`: replace the module-level
   `_SCHEMA_PATH` constant with a function that resolves the schema path from
   a `canonical_year` argument. Update `SchemaIndex` to be constructed
   per-year. Update `_get_schema()` to take a year. Cache instances per year.
   **`_PHRASE_TO_QNUM` is unchanged in this milestone** — see scope note above.

3. `tools/extraction_worker/worker.py`: load all available canonical schemas
   at startup, dispatch per-document via the precedence chain above. Update
   Tier 1, Tier 2 paths to receive the year-matched schema. Standardize on
   `notes.schema_version` as the artifact write location (matches the
   existing `worker.py:585` write path).

4. Implement the fallback policy: unknown year → most-recent-available
   canonical schema, log a warning, set `notes.schema_fallback_used: true`
   AND `notes.schema_version` to the actually-used version. Per Codex
   feedback, **artifacts produced via fallback for pre-2024 documents are
   marked low-confidence in the projection layer** (one new column on
   `cds_artifacts.notes` or computed at projection time). The browser
   projection should exclude or downgrade fallback-extracted older-year
   artifacts from launch-certified columns until those years get their own
   canonical schemas.

5. Update `tools/extraction_worker/tier4_llm_fallback.py` and
   `llm_fallback_worker.py` if they consume the schema for context —
   make both year-aware.

6. Add tests with **value-level assertions** (not just counts):
   - `SchemaIndex(year="2024-25")` loads `schemas/cds_schema_2024_25.json`
     and a known field's question text matches the file
   - `SchemaIndex(year="2026-27")` (no file) returns the most recent, logs a
     warning, and the test asserts the warning was emitted
   - Worker dispatches correctly for fixture documents of each source format
     (XLSX, fillable PDF, flat PDF, HTML)
   - Tier 1 fixture: 2024-25 XLSX with known cell value `1450` for SAT 50th
     yields `cds_fields.value_text = "1450"`, `value_num = 1450`,
     `field_id = "C.912"`, `canonical_field_id = "C.912"`,
     `equivalence_kind = "direct"`
   - Tier 1 fixture: 2024-25 XLSX with known applied count from
     C.101/C.102/C.103/C.104 yields `school_browser_rows.applied = sum`
     via the M2.5 derived formula
   - Existing 2025-26 cleaner tests still pass (regression gate)

7. Spot-check by running the worker against a 2024-25 fixture document with
   both old and new behavior; confirm field-count delta and value-level
   correctness. Document in `docs/extraction-quality.md`.

**Stop condition:** if making `SchemaIndex` year-aware breaks the cleaner's
test suite materially, retreat to passing the year through the public
`clean()` entry point and having `_get_schema()` close over it, without
restructuring the index.

**Value delivered:** Tier 1 / Tier 2 / Tier 6 extract against the right
schema for 2024-25 documents. Tier 4's `SchemaIndex.filter()` and value-type
lookups are also correct. The cleaner's phrase matcher is unchanged
(2025-26-keyed) — Tier 4 may still emit slightly-wrong shapes for 2024-25
docs until M6 ships. PRD 012's launched columns work correctly via M2.5's
derived-formula machinery.

### M4 — Small validation drain with value-level assertions

**Effort:** ~1 day.

1. Stratified fixture sample: 5 documents from each of XLSX (Tier 1),
   fillable PDF (Tier 2), flat PDF (Tier 4), scanned PDF (Tier 5). Pick from
   real production failures where possible. For each, hand-curate a small set
   of expected (`canonical_metric`, `expected_value`) pairs from the source
   PDF/XLSX directly — these are the value-level assertions, not just field
   counts.
2. Run each fixture through the year-aware extractor pair-wise: current
   production behavior (2025-26 schema for everything) vs new behavior
   (year-matched schema + tri-state equivalence). Capture per-fixture:
   - `schema_fields_populated` (count metric)
   - `parse_error` rate
   - For each hand-curated assertion: did the new pipeline produce the
     expected value? Did the old one?
3. For each section family, summarize: did year-matching recover fields that
   the 2025-26 schema missed? Did it correct values that were previously
   parse-errored? Are the C.10x admissions counts now correct (post-M2.5)?
4. Write findings to `docs/plans/prd-014-validation-findings.md`. Three
   outcomes:
   - **Big delta (≥10% additional fields populated on average, or any
     value-level assertion shifts from wrong→right or right→wrong):** decide
     on M5 (corpus drain) explicitly.
   - **Modest delta (1–10%):** ship M3+M2.5 to production, accept that
     historical artifacts remain on the old schema until they next refresh.
   - **No meaningful delta:** ship for correctness; close out without M5.

**Stop condition:** none — this is a measurement.

**Value delivered:** evidence-based go/no-go for M5.

### M5 — Corpus drain (decision; not auto-included)

**Effort:** depends on M4 outcome; corpus is ~3,000+ Tier 4 documents.

Run year-aware re-extraction across the corpus. Triggers projection refresh
per the recent ops PR. Tier 4 fallback `markdown_sha256` cache partially
invalidates; the rollback script from M2.75 stands ready. Surface progress
in the worker summary; gate on M4's "big delta" outcome.

If M4 shows big delta but M5 budget isn't approved, ship M3+M2.5 anyway
(correctness for new artifacts) and let the corpus transition naturally over
time as documents re-extract on other cadences. Mixed-schema artifacts in
`cds_fields` during the transition are acceptable because M2.75's selected-
result logic prefers year-matched artifacts.

### M6 — Schema-derived phrase matcher (FOLLOW-ON; separate PRD)

**Effort:** ~2-3 days, separate PRD.

Make `_PHRASE_TO_QNUM` schema-derived at cleaner load time. Removes the
hand-tuned 2025-26 dependency. Required eventually for the Tier 4 cleaner to
fully benefit from year-aware extraction; not blocking PRD 012's correctness
once M2.5 ships. May be promoted ahead of M4 if M3's spot-check shows the
phrase-matcher mismatch is the dominant remaining error source.

## Cross-year schema conventions

Codified here so M1's adapted builder and M3's year-aware extractors share
ground rules.

### Question-number canonical format

All canonical schemas, regardless of source year, must emit question numbers
in either of two forms (per Finding 5):

```
<section-letter>.<digits-zero-padded-to-3+>     # most common
<section-letter>.<sub-letter-suffix>            # 23 IDs use this; preserve as-is
```

Examples: `A.001`, `B.101`, `C.916`, `H.1418`, `J.220` (digit form);
`A.0A`, `C.8D`, `C.8G01`, `H.2A01` (sub-letter form).

Normalization algorithm:

```python
def normalize_id(raw: str) -> str:
    m = re.match(r'^([A-Z])(.+)$', raw)
    if not m:
        raise ValueError(f"unparseable question number: {raw!r}")
    rest = m[2]
    if rest.isdigit():
        rest = rest.zfill(3)
    return f"{m[1]}.{rest}"
```

Required test cases: `A01`→`A.001`, `A511`→`A.511`, `B2101`→`B.2101`,
`A0A`→`A.0A`, `C8G01`→`C.8G01`, `H2A01`→`H.2A01`.

A schema that emits raw source-year IDs is broken and the test suite must
catch it.

### Cross-year ID equivalence

Two questions in different years with the same canonical ID *and* the same
section, sub-section, and (substantively) the same question text are
considered equivalent. The diff tool from M2 produces an explicit equivalence
record per ID:

- `equivalent` — same ID, same section, matching text
- `renamed` — same ID, different text (semantic drift)
- `removed` — present in older year, absent in newer
- `added` — absent in older year, present in newer

Public consumers of `cds_fields` should treat `equivalent` as safe for
cross-year filtering; `renamed` requires per-field judgment; `removed` /
`added` are year-specific.

PRD 012's "scope to `year_start >= 2025`" hedge is replaceable with an
explicit list of `equivalent` fields that are safe for `year_start >= 2024`.

### Schema-version metadata in artifacts

Every Tier 1 / 2 / 4 / 5 / 6 artifact must record which schema version the
extractor used in `notes.schema_version`. The projection worker (PRD 010 /
012) already reads this; M3 must guarantee it's set correctly when the
year-matched schema is selected, and that `notes.schema_fallback_used: true`
is also set when the fallback policy fired.

## Contributor process: adding a new template year

This is the steady-state process for handling 2026-27, 2027-28, and beyond.
Documented here once so future contributors do not need to reverse-engineer
it from PRD diffs.

### When the CDS Initiative releases a new template

1. **Download both files** — XLSX and fillable PDF — from commondataset.org.
2. **Capture a Wayback snapshot** of both URLs immediately. Five-minute job
   that protects future contributors when the CDN rotates the file.
3. **Archive into `schemas/templates/`** using the naming convention
   `cds_<academic-year>_template.{xlsx,pdf}`. Add a row to
   `schemas/templates/SOURCES.md` with source URL, Wayback URL, and SHA-256.
4. **Inspect the Answer Sheet structure.** Compare column headers against
   prior years. If columns are added/removed, the canonical builder may need
   another adapter (analogous to the 2024-25 reduced-column path). Question-
   number format may also change — apply the canonical-format normalization
   rules above.
5. **Run the canonical builder:**
   ```bash
   python tools/schema_builder/build_from_xlsx.py \
     schemas/templates/cds_<year>_template.xlsx \
     schemas/cds_schema_<year>.json
   ```
6. **Synthesize `pdf_tag` if the Answer Sheet doesn't include it** (M2's
   approach). Skip if the Answer Sheet ships its own `pdf_tag` column.
7. **Run `decode_checkboxes.py` against the fillable PDF** to populate
   `value_options`.
8. **Generate the cross-year diff:**
   ```bash
   # Tooling for this lands in M2; the diff format is documented there.
   ```
9. **Review the diff.** Look for unexpected renames, large removals, or
   value-type changes. Renames in section C (admissions) deserve particular
   scrutiny since they touch the headline browser filters.
10. **Update extractors if needed.** New fields may require
    cleaner phrase-matcher updates (`tier4_cleaner.py`'s `_PHRASE_TO_QNUM`).
    Removed fields may require browser projection adjustments.
11. **Add the new year to the year-aware schema dispatch** in the worker.
    Confirm the fallback policy still produces the right schema for prior
    years.
12. **Run the validation suite** — same shape as M4 — on a small fixture set
    from the new year, comparing year-matched extraction against falling-back
    extraction.
13. **Update `schemas/README.md` cross-year coverage table** and any docs that
    cite the most-recent year explicitly.
14. **PR the schema, the templates, the SOURCES.md update, and the diff in a
    single change.** No drive-by code edits — keep the schema-onboarding PR
    isolated for review clarity.

### Estimated effort per year

- Best case (no column-layout changes, AcroForm names stable): ~1 hour.
- Median case (minor column changes, some `pdf_tag` synthesis): ~half day.
- Worst case (Answer Sheet redesigned): ~1 day plus another extractor PR.

## Older years (2019-20 through 2023-24)

Out of scope for this PRD by Goal #1 / Non-goal #1. Recorded here for
contributor reference:

- These years have no Answer Sheet tab. Canonical schemas are not directly
  derivable.
- The structural-schema approach (`build_from_tabs.py`) works for these
  years and produces `cds_schema_*.structural.json` files.
- An OSS contributor wanting canonical IDs for older years would need to
  fuzzy-match each year's structural schema against the 2025-26 canonical
  schema by row-label and column-header similarity. The result is best-effort,
  not authoritative. `schemas/README.md` "Next steps" still lists this as
  open work.
- The year-aware extractor in M3 must handle the case where a document's
  `canonical_year` matches a structural-only year: fall back to the most
  recent canonical schema and mark `notes.schema_fallback_used: true`.

## Open questions

**Resolved by the 2026-04-28 cross-check and verification:**

- **`pdf_tag` synthesis fidelity:** 97% (1,084 of 1,116) AcroForm names match
  2025-26 `pdf_tag` directly. The 32 misses are all `*_NON_BINARY_*` fields
  intrinsic to 2024-25's 4-gender model (Finding 4).
- **Section C identity for PRD 012 launch-certified fields:** all SAT/ACT
  percentile and GPA fields EXACT match. C.901 / C.902 carry minor drift
  (Finding 1).
- **Section C admissions counts:** complete misalignment in C.10x range due
  to gender-category restructure (Finding 2). Drives M2.5's tri-state model.
- **Filename convention:** existing files use underscores
  (`cds_schema_2025_26.json`). New file is `cds_schema_2024_25.json`. Display
  version remains `2024-25`.
- **Schema metadata location:** `worker.py:585` writes `notes.schema_version`;
  `project_browser_data.py:354-356` reads with dual-fallback (top-level OR
  inside notes). Standardize on `notes.schema_version` for new writes; preserve
  the dual-read fallback for legacy artifacts.
- **M2.5 model:** tri-state equivalence (`direct` / `derived` / `preserved-only` /
  `unmapped`) with `cds_canonical_field_equivalence` table and `MetricDefinition`
  refactored to `DirectAlias | DerivedFormula`. The flat alias model from v2
  is insufficient for admissions counts.

**Remaining open:**

1. **C.10x derivation formula content:** what's the exact per-year aggregation
   for `applied`/`admitted`/`first_year_enrolled`? Likely `sum(C.101 + C.102 +
   C.103 + C.104)` for 2024-25 applied, but the actual field membership of
   each metric needs to be confirmed against the 2024-25 Answer Sheet during
   M2's classification. Decide before M2.5 codes the formulas.
2. **Tier 4 fallback re-cache (M5):** if M5 runs, the
   `markdown_sha256`-keyed fallback cache partially invalidates. Is the
   re-cache cost acceptable, or do we need a migration strategy that carries
   existing fallback values forward where the underlying markdown is unchanged?
3. **Worker `--schema` CLI flag (M3):** the current flag accepts one schema
   path. Once the worker is year-aware, what does it mean? Suggest: keep as
   an override that disables year-awareness for the run (useful for debugging
   or for replaying old behavior), with a warning logged when used.
4. **2025-26 template archival:** the 2025-26 XLSX still lives in `scratch/`
   (gitignored); 2024-25 is now in `schemas/templates/`. Move 2025-26 too in
   M1's PR for consistency. Update `tools/extraction_worker/worker.py:1001`,
   `tools/schema_builder/README.md`, `tools/schema_builder/build_from_xlsx.py:15`,
   `tools/schema_builder/decode_checkboxes.py:32`, and
   `tools/extraction_worker/tier4_extractor.py` to point at the new location.
5. **`llm_fallback_worker.py` schema usage:** verify whether this second
   fallback worker (separate from `tier4_llm_fallback.py`) consumes schemas.
   Add to M3's audit step.
6. **Older-year confidence marking:** how exactly is "low-confidence" surfaced
   for 2019-23 documents extracted via fallback? New column on
   `cds_artifacts.notes`? Computed at projection time? PRD 012-style
   value_status? Decide before M3.
7. **M5 corpus drain trigger criteria:** PRD lists M4 outcomes (big/modest/
   no delta) but doesn't specify who decides M5 go/no-go. Anthony? A
   threshold check in the validation script? Make this explicit.

## Risks

- **Adapter generalization vs forking.** Making `build_from_xlsx.py` handle
  both 2024-25 and 2025-26 gracefully invites future drift (each new year
  may want its own special case). Mitigation: detect column layout from
  headers, fail loudly on unknown column names, and document the adapter
  pattern so future years follow it. If a year requires structural changes
  beyond column presence (e.g., a redesigned Answer Sheet), prefer a forked
  builder over a multi-branch generalization.

- **`pdf_tag` synthesis is a guess.** M2's matching logic relies on
  AcroForm field names being stable across years. If the CDS Initiative
  renamed any form fields between 2024-25 and 2025-26, the synthesized
  `pdf_tag` will silently mis-route. Mitigation: spot-check the synthesis
  against a known-extracted 2024-25 fillable-PDF document; if Tier 2 output
  with synthesized `pdf_tag` matches Tier 4 cleaner output for the same
  document on common fields, the synthesis is good. If they diverge, treat
  `pdf_tag` as null and fall back to text-based matching.

- **`_PHRASE_TO_QNUM` maintenance doubles.** The cleaner's hand-tuned phrase
  matcher is keyed on 2025-26 question text. After M3, if 2024-25 question
  text differs for any field, the matcher needs year-aware variants. Each
  added year compounds this. Mitigation: build the phrase matcher from the
  schema at load time rather than maintaining it as a hand-tuned constant.
  This is a follow-on, not blocking M3.

- **Re-extraction cascade.** If M4 recommends re-extraction, the work
  cascades through the projection refresh (which the recent ops PR already
  added) and the Tier 4 fallback cache. Wall-clock cost is hours and write
  volume is meaningful. Mitigation: M4 deliberately defers this decision;
  the cascade is explicit and budgeted as a follow-on PRD.

- **Cleaner regression on 2025-26 documents.** Year-aware code paths
  introduce a class of bugs where the "wrong" schema gets selected for a
  given document. Mitigation: the test surface in M3 covers both years
  explicitly; a regression on 2025-26 production behavior fails the M3
  acceptance criteria.

- **Wayback Machine availability.** This PRD's archival policy assumes the
  Internet Archive will keep the 2024-25 source URL accessible. The
  templates are now committed to the repo, so even if Wayback later loses
  the snapshot, the files themselves remain. The provenance record may
  become a dead URL, which is acceptable.

- **2025-26 schema version drift.** If the CDS Initiative ever republishes
  the 2025-26 template with corrections, our committed artifact and our
  generated schema may go out of sync with the published version. Mitigation:
  record the source URL, snapshot date, and SHA-256 in
  `schemas/templates/SOURCES.md`; on a republish, re-archive and regenerate.

- **Bad year-aware artifacts.** Re-extraction with year-aware logic could
  produce worse artifacts than the existing 2025-26-against-everything
  artifacts in edge cases (year detection wrong, derivation formula bug, or
  `_PHRASE_TO_QNUM` mismatch dominates). M2.75's selected-result schema-
  awareness mitigates by preferring year-matched non-fallback artifacts;
  M2.75's rollback script provides recovery. Both are required before M5.

- **Older years (2019-23) misextraction.** Documents from these years fall
  back to 2025-26. Without explicit low-confidence marking (per Open Question
  #6), browser users see fallback-extracted values that look identical to
  year-matched values. Fix: M3 marks fallback-produced artifacts low-
  confidence; the projection layer either excludes them from launch-certified
  columns or surfaces the low-confidence state visibly.

- **Tier 4 partial-correctness ambiguity.** M3 ships year-aware schema
  loading but `_PHRASE_TO_QNUM` stays 2025-26-keyed. Stakeholders may assume
  "year-aware extraction" means full Tier 4 correctness. Mitigation:
  acceptance criteria explicitly call out the M3 → M6 split; release notes
  are clear about what M3 fixes and what it doesn't.

- **Equivalence formula authoring errors.** A wrong derivation formula for
  `applied` (e.g., missing the part-time category) produces silently wrong
  browser values for all 2024-25 documents. Mitigation: M2.5's value-level
  test assertions catch known-fixture mismatches; M4's validation drain
  catches systematic errors before M5 runs at scale.

## Rollback plan

If M3 / M4 / M5 surfaces a regression:

- **Single-document recovery:** M2.75's rollback script reverts
  `cds_manifest`'s selected canonical artifact for one or many documents to
  the prior `created_at` value. Effects propagate through the recent ops
  PR's auto-projection refresh on next worker run.
- **Full rollback of the equivalence model:** revert the M2.5 SQL migration
  (drop `cds_canonical_field_equivalence`, drop new `cds_fields` columns).
  The projection layer falls back to its pre-M2.5 behavior.
- **Full rollback of year-aware extraction:** revert M3's worker changes,
  `tier4_cleaner.py` reverts to the hardcoded 2025-26 schema path, and a
  second drain (with `--skip-projection-refresh` to stage) re-extracts
  affected documents under the old behavior.

Explicit rollback effort: ~2 hours per layer. The schema-version-aware
selected-result logic in M2.75 means the rollback can be incremental rather
than cliff-edge.

## Acceptance criteria

The PRD is implemented when:

**M1 (schema + templates):**

- `schemas/templates/cds_2024-25_template.{xlsx,pdf}` are committed with
  provenance recorded in `schemas/templates/SOURCES.md`. **(Done in this
  PRD's same change.)**
- `schemas/cds_schema_2024_25.json` exists.
- `tools/schema_builder/build_from_xlsx.py` produces byte-identical output
  for the 2025-26 template (no regression).
- `schemas/README.md` is updated: cross-year coverage table refreshed,
  stale "Next steps" bullets removed, normalization rule documented,
  cross-references to PRD 014 and `schemas/templates/SOURCES.md` added.
- `tools/schema_builder/README.md` references the new
  `schemas/templates/` archive policy.

**M2 (diff + classification):**

- `schemas/cds_schema_2024_25-to-2025_26.diff.{json,md}` exists with each
  field classified as `direct`, `derived`, `preserved-only`, or `unmapped`.
- All PRD 012 launch-certified academic-profile fields classify as `direct`.
- C.10x admissions fields classify as `derived` with documented per-year
  formulas in the diff.
- `pdf_tag` synthesis is question-text-validated, not just AcroForm-name-
  matched.

**M2.5 (equivalence layer + tri-state model):**

- `cds_canonical_field_equivalence` table exists with rows for both schema
  versions; populated from M2's diff.
- `cds_fields` retains source `field_id`; new columns `canonical_field_id`,
  `equivalence_kind`, and `schema_version` are populated correctly.
- `MetricDefinition` supports both `DirectAlias` and `DerivedFormula` source
  specs.
- Value-level tests pass: known 2024-25 fixture's `applied` derives correctly
  from C.10x sums; known 2025-26 fixture's metrics map identity-equivalent;
  unmapped 2024-25 non-binary fields land in `cds_fields` with
  `canonical_field_id = NULL` and are excluded from `school_browser_rows`.
- `cds_field_definitions` is seeded for both schema versions.

**M2.75 (selected-result + rollback):**

- `cds_manifest`'s selected-result logic prefers year-matched non-fallback
  artifacts over fallback or wrong-year artifacts, regardless of `created_at`.
- Test asserts: a 2024-25 document with both a year-matched and a fallback
  artifact selects the year-matched artifact even when the fallback is newer.
- Rollback script exists and is documented in `docs/archive-pipeline.md`
  for reverting bad year-aware artifacts.

**M3 (year-aware extractor dispatch — narrowed scope):**

- `tier4_cleaner.py`, the worker, and Tier 1 / Tier 2 paths dispatch schema
  by document `canonical_year` per the precedence chain in M3 step 0.
- Fallback policy is implemented: unknown year → most-recent canonical schema,
  `notes.schema_version` recorded, `notes.schema_fallback_used: true` set.
- Older-year documents (pre-2024) extracted via fallback are marked
  low-confidence in the projection layer per Open Question #6's resolution.
- `_PHRASE_TO_QNUM` remains 2025-26-keyed; this is documented explicitly
  as a known M3 limitation deferred to M6.
- All schema consumers in M3 step 1's audit list have been reviewed and
  either made year-aware or documented as exempt.
- `docs/extraction-quality.md` reflects M3's measured behavior delta.

**Process:**

- The contributor process in this PRD is verified by a dry-run: simulate
  adding a hypothetical 2026-27 by following each step against a stub file,
  confirming the documented commands and locations are accurate.

## Verification

```bash
# Schema build is reproducible
python tools/schema_builder/build_from_xlsx.py \
  schemas/templates/cds_2024-25_template.xlsx \
  /tmp/cds_schema_2024_25.json
diff schemas/cds_schema_2024_25.json /tmp/cds_schema_2024_25.json

# Backwards compatibility — 2025-26 still builds identically
python tools/schema_builder/build_from_xlsx.py \
  schemas/templates/cds_2025-26_template.xlsx \
  /tmp/cds_schema_2025-26.json
diff schemas/cds_schema_2025_26.json /tmp/cds_schema_2025-26.json

# Year-aware extractor tests
python -m unittest discover -s tools/extraction_worker -p "test_*.py"
python -m unittest tools.browser_backend.project_browser_data_test

# Spot-check that a 2024-25 document picks up the right schema
python tools/extraction_worker/worker.py --school <known-2024-25-school> \
  --limit 1 --dry-run --skip-projection-refresh
# Verify log line includes "schema_version=2024-25"
```

## Verdict

Ship M1 → M2 → M2.5 → M2.75 → M3 in sequence; M4 as a separate go/no-go
informed by M3; M5 only on M4's "big delta" outcome; M6 as a follow-on PRD.

**Revised effort estimate: ~5 engineer-days for M1+M2+M2.5+M2.75+M3**
(was ~3 days in v2; ~10-14 hours in v1). Codex's review correctly identified
that the v2 estimate underweighted M2.5's tri-state model and entirely
missed M2.75 (selected-result schema-awareness). Realistic breakdown:

- M1: ~half day
- M2: ~1 day
- M2.5: ~1 day
- M2.75: ~half day
- M3: ~1 day
- audit + buffer: ~1 day
- **Subtotal: ~5 engineer-days**
- M4: ~1 day, separate
- M5: depends on M4 outcome
- M6: ~2-3 days, separate PRD

**Two pieces of news worth highlighting separately:**

- **Good news for PRD 012:** all SAT/ACT percentile and GPA fields map
  EXACTLY between 2024-25 and 2025-26. PRD 012's `year_start >= 2024` scope
  for academic-profile fields is verified, not deferred. (Finding 1.)
- **Pre-existing correctness issue surfaced:** the cleaner currently runs
  2025-26 schema against 2024-25 documents and "happens to work" for
  admissions counts because both extract and project use the same wrong-year
  IDs together. Year-aware extraction uncovers the real semantic mismatch
  in C.10x; M2.5's `DerivedFormula` machinery closes it. (Finding 2.)

The 2024-25 templates are now archived in the repo. From here, the project
no longer depends on commondataset.org's CDN to be reproducible for the most
valuable year of data. That defensive-archival posture should be the default
for any year past current.

The contributor-process documentation gains weight given v3's tri-state
model: future template years may bring further structural restructures
(the 4-gender → 3-gender change is a precedent), and the
`DirectAlias | DerivedFormula` pattern is now the standard shape for
handling them.
