# PRD 005: Full-Schema Extraction — Expand Tier 4 Cleaner to 1,105 Fields

**Status:** Draft (rev 2 — incorporates review findings)
**Created:** 2026-04-19

---

## Context

The Tier 4 Docling cleaner currently maps **72 of 1,105** CDS schema fields (~6.5%).
It uses hand-coded substring tuples in `_FIELD_MAP` (38), `_PERCENTILE_MAP` (16), and
`_INLINE_PATTERNS` (2) — covering only sections B1/B2/B3/C1/C9/C10. With 4,142
documents archived and 1,913 freshly queued for extraction, now is the time to expand
coverage.

## Measured schema ambiguity

Before designing the disambiguation strategy, we measured the schema:

| Disambiguation level | Unique buckets | Ambiguous buckets |
|---|---|---|
| Raw question text | 694 | — |
| (section, subsection, question) | 809 | 151 |
| + gender, cohort, unit_load, student_group | 977 | 90 |
| + residency, category | 1,075 | 20 |
| Fully unique (including table position) | 1,105 | 0 |

**What resolves the 90 buckets that gender/cohort/unit_load/student_group miss:**
- 64 resolved by `category` (e.g., "Required" vs "Recommended" in C5)
- 6 resolved by `residency` (e.g., C.119/C.122/C.125/C.128 for in-state/out-of-state)
- 20 require table-position context (not capturable from schema metadata alone)

**The 20 irreducibly ambiguous fields:**
- 10 GPA profile rows (C.11xx) — same question × 3 sub-tables (score-submitters /
  non-submitters / all entering). Distinguished only by `pdf_tag` prefix
  (`FRSH_GPA_SUBMIT` / `FRSH_GPA_NO_SUB` / `EN_FRSH_GPA`), meaning the resolver must
  know which sub-table it's in.
- 4 H.2A financial aid fields — full-time vs less-than-full-time columns. The schema
  has a metadata error (`unit_load: FT` for both), but `pdf_tag` distinguishes
  (`UG_FT_` vs `UG_PT_`).
- 4 D.13–D.16 transfer credit fields — number-of-credits vs unit-type within the same
  row. Two columns in one row, not two rows.
- 2 C.16/C.17 date fields — same "Date: Month" / "Date: Day" across two different
  deadline contexts.

**Conclusion:** Schema metadata resolves 98% of fields (1,075/1,105). The remaining 2%
require table-position-aware or bespoke logic. A universal matcher that ignores
`residency`, `category`, and table position will silently mis-assign fields.

## Premises

1. **Schema metadata assists, but does not replace, section-specific logic.** The
   schema's question text and dimensional metadata are useful join keys, but the
   observable Docling markdown varies enough that each section family needs its own
   resolver — not one generic engine.
2. **Docling markdown is not standardized.** The CDS *template* is standardized; what
   Docling produces from it is not. Known variations include: headerless
   one-metric-per-row tables, wrapped labels across rows, tables flattened into
   paragraph blocks, section context embedded as table rows rather than `##` headers,
   and wrong-file / blank-template archives. Each section family encounters a different
   mix of these.
3. **Zero regressions requires more than "overrides take priority."** Adding a
   schema-driven pass that operates over the same rows as the hand-coded maps creates
   a new regression surface. A false positive in the new pass can claim an empty field
   that the hand-coded map intentionally left blank. Regression protection requires
   per-section isolation, not just first-match ordering.
4. **`residency` and `category` are required disambiguation dimensions.** The PRD v1
   relied only on gender/cohort/unit_load/student_group. That leaves 90 fields
   ambiguous. Adding residency and category resolves 70 of them.
5. **Not every field needs extraction accuracy day one.** Phased rollout by section
   family, starting with sections where schema + table structure are actually clean.
   If a section needs bespoke logic, admit it early instead of forcing it through the
   generic resolver.
6. **Existing tooling is the primary validation loop.** `corpus_survey_tier4.py` already
   measures corpus-wide per-question-number coverage against stored markdown. Extend
   it rather than inventing a parallel `--coverage` mode elsewhere.

## What to build

### Schema-assisted resolver framework

Not one `SchemaMatcher` class but a **library of section-family resolvers** backed by
shared schema metadata. Each resolver encodes the table structure knowledge for its
section family and uses schema metadata for field lookup.

**Shared infrastructure:**

```
class SchemaIndex:
    """Loaded once from cds_schema_2025_26.json. Provides lookup by
    (section, subsection, question_norm, gender, cohort, unit_load,
    student_group, residency, category) → question_number.
    
    Also exposes pdf_tag and word_tag for the 20 irreducibly ambiguous
    fields where table-position is the only differentiator."""
    
    def lookup(self, *, section, subsection, question_norm,
               gender='All', cohort='All', unit_load='All',
               student_group='All', residency='All', 
               category='All') -> str | None:
        """Returns question_number or None if no unique match."""
    
    def lookup_by_pdf_tag_prefix(self, prefix: str) -> list[SchemaField]:
        """Fallback for the 20 irreducible fields."""
```

**Section-family resolvers** (each a function or small class):

| Resolver | Sections | Why bespoke |
|---|---|---|
| `resolve_b1_enrollment` | B1 (75 fields) | Gender × cohort × unit_load matrix. Table headers carry unit_load context. Must detect FT/PT sub-tables from section headers or table position. |
| `resolve_b2_race` | B2 (30 fields) | Column header carries cohort context ("First-time, first-year" vs "Total"). |
| `resolve_b5_graduation` | B5 (84 fields) | Matrix: Pell/Stafford/Neither/Total columns × lettered rows × 2 cohort-year tables. `student_group` metadata maps to row letters. |
| `resolve_c1_applications` | C1 (30 fields) | Gender rows + residency splits + unit_load totals. Must add `residency` dimension. |
| `resolve_c5_requirements` | C5 (25 fields) | Required vs Recommended distinguished by `category`, not gender/cohort. Two-column or single-column table depending on school. |
| `resolve_c7_selection` | C7 (22 fields) | Checkmark-in-column detection. Value = header name of checked column. |
| `resolve_c11_gpa` | C11 (30 fields) | 3 sub-tables with identical row labels. Distinguished only by sub-table position. `pdf_tag` prefix is the fallback signal. |
| `resolve_c_dates` | C13–C21 (51 fields) | Paired MM/DD extraction. Inline anchor + date pattern. |
| `resolve_g_expenses` | G (46 fields) | Dollar amounts in clean tables. Multiple sub-tables (public/private/all, residents/commuters). |
| `resolve_h_financial_aid` | H (164 fields) | Need/non-need column splits. Lettered rows. `subsection` metadata disambiguates sub-tables. H.2A has schema metadata error on `unit_load`. |
| `resolve_i_faculty` | I (49 fields) | Lettered rows + FT/PT columns. I2 ratio is fragmented in Docling output — inline regex. I3 class size headers match schema question exactly. |
| `resolve_j_disciplines` | J (120 fields) | 40-row × 3-column table. Schema question IS discipline name. `subsection` selects column. Cleanest section family. |
| `resolve_checkboxes` | A, E, F (generic) | Scan `- [x]`/`- [ ]` lines. Schema question text matches checkbox label. ~70 fields. |
| `resolve_remaining` | D, misc | Transfer admission, remaining text/date fields, mop-up. |

### Integration with `clean()`

```python
def clean(markdown: str, schema: SchemaIndex = None) -> dict:
    tables = _parse_markdown_tables(markdown)
    values = {}
    
    # 1. Existing hand-coded maps (regression-safe baseline)
    values |= _run_handcoded_maps(tables)
    
    # 2. Section-family resolvers (each operates on its own table slice)
    if schema:
        for resolver in _RESOLVERS:
            new = resolver(tables, markdown, schema)
            # Only write fields not already claimed
            for qn, v in new.items():
                if qn not in values:
                    values[qn] = v
    
    return values
```

Each resolver sees the full table list but only claims fields in its own section. A
resolver MUST NOT claim a field that belongs to a different section family. This
isolation prevents false positives from generic label matches like "Total", "Specify:",
"History", "English".

### Why `question` is the primary join key (but not the only one)

`question` text is the primary key because it's what appears in the rendered PDF and
what Docling extracts. `pdf_tag` and `word_tag` are fillable-form field identifiers —
they don't appear in the rendered output of flattened PDFs (Tier 4's input). However,
`pdf_tag` is useful as a **structural signal** for the 20 irreducibly ambiguous fields:
the tag prefix encodes which sub-table a field belongs to (e.g., `FRSH_GPA_SUBMIT` vs
`FRSH_GPA_NO_SUB`). Resolvers for those specific fields use `pdf_tag` prefix to
identify the sub-table pattern they should look for, then match row labels within that
sub-table.

## Phasing

Ordered by: (1) cleanliness of schema-to-markdown match, (2) consumer value,
(3) complexity. Each phase is a self-contained PR with its own validation loop.

### Phase 0: Prove the framework on J and B2

Build `SchemaIndex`, wire it into `clean()`, and prove the approach on the two cleanest
section families before committing to full-schema architecture.

**Why J and B2:**
- J (120 fields): Schema question text IS the discipline name. `subsection` selects
  the column. One table, zero ambiguity, clean Docling output. If schema-driven
  matching can't work here, it can't work anywhere.
- B2 (30 fields → extend from 9): Already partially covered. Column header matching
  by substring generalizes cleanly. Adding 21 fields tests the column-hint resolver
  without touching complex matrix logic.

**Deliverables:**
- `SchemaIndex` class loaded from schema JSON
- `resolve_j_disciplines()` — 120 new fields
- `resolve_b2_race()` — 21 new fields (9 already hand-coded)
- Extended ground truth for J (5–10 disciplines per school) and B2 (all columns)
- `corpus_survey_tier4.py` confirms field count increase on stored markdown
- Regression gate: all 4 existing ground truth files pass unchanged

**Exit criteria:** 141 new fields, corpus survey shows ≥80% population rate for J
fields on current-year docs.

### Phase 1: B1 + B5 + B22 (+172 fields → 384 total)

**B1 enrollment matrix (75 fields):** Gender × cohort × unit_load. The resolver must
detect FT/PT sub-tables from section headers or table position. Schema question text
with `: males/females/unknown` suffix stripped matches row labels. `gender` metadata
selects column. Current 11 hand-coded fields stay as overrides.

**B5 graduation rates (84 fields):** Matrix table with Pell/Stafford/Neither/Total
columns × rows (A–H) × 2 cohort-year tables. Row letter prefix + column header +
`student_group` metadata → unique field. This is the first resolver that must track
cohort-year context from section headers ("Fall 2018 Cohort").

**B22 retention + persistence (12 fields):** Simple table/inline values.

**Validation:** Freeze a benchmark slice of ~50 tier4 docs. Run corpus survey before
and after. Expand GT for B1 (all FT enrollment rows for 2 schools), B5 (Pell column
spot-check for 2 schools), B22 (retention rate for all 4 schools).

### Phase 2: C Section — clean subsections first (+87 fields → 471 total)

Ship the C subsections where table structure is clean:
- C1 applications (30) — add residency splits, part-time totals
- C2 wait list (7) — YesNo + counts
- C9/C10 — already covered, verify and preserve

Defer the hard C subsections (C5, C7, C11, C13–C21) to Phase 3.

### Phase 3: C Section — hard subsections (+188 fields → 659 total)

Each of these is its own parser design:
- **C5 Carnegie units (25):** Two-column or single-column table. `category` dimension
  distinguishes Required vs Recommended. Some schools don't fill this at all.
- **C7 basis for selection (22):** Checkmark-in-column detection. Value = header text
  of the column containing a check.
- **C11 GPA profile (30):** Three sub-tables with identical row labels. Resolver must
  detect sub-table boundaries. `pdf_tag` prefix signals which sub-table pattern to
  match within the markdown.
- **C13–C21 policies/dates (51):** Paired MM/DD extraction. Mixed inline text and
  small tables. Each deadline is its own anchor context.
- **C8/C12 profile data (60):** GPA summary stats, test score distributions.

### Phase 4: G + I + F (+153 fields → 812 total)

- **G expenses (46):** Dollar amounts in clean tables. `_extract_currency()` handles
  "$69,207.00". Multiple sub-tables resolved by header.
- **I faculty/class size (49):** I1 lettered rows + FT/PT columns. I2 inline ratio.
  I3 size-range headers match schema question text exactly.
- **F student life (58):** F1 percentages. F2/F4 checkboxes. F3 ROTC hybrid.

### Phase 5: H + D (+243 fields → 1,055 total)

- **H financial aid (164):** Most complex section. Need/non-need splits, lettered rows,
  mixed value types. H.2A has a schema `unit_load` metadata error. This section will
  likely need the most bespoke logic.
- **D transfer admission (79):** Parallels C1 + C5 structure for transfer students.

### Phase 6: A + E + Remaining (~50 fields → 1,105 total)

- **E academic offerings (34):** Pure checkboxes. Trivial.
- **A general info (54):** Mostly low-value contact fields. Degree checkboxes (12) are
  the only consumer-facing data.
- **Remaining/unassigned (22):** Mop-up.

## Summary

| Phase | Fields Added | Cumulative | Key Work |
|---|---|---|---|
| 0 | +141 | 213 | SchemaIndex + prove on J (120) + B2 (21) |
| 1 | +172 | 384 | B1 matrix, B5 grad rates, B22 retention |
| 2 | +87 | 471 | C1 clean subsections, C2 wait list |
| 3 | +188 | 659 | C5, C7, C11, C13–C21 (each its own parser) |
| 4 | +153 | 812 | G expenses, I faculty, F student life |
| 5 | +243 | 1,055 | H financial aid, D transfer |
| 6 | +50 | 1,105 | A, E, remaining |

## Files modified

| File | Change |
|---|---|
| `tools/extraction_worker/tier4_cleaner.py` | Add `SchemaIndex`, section-family resolvers, expand `clean()` |
| `tools/extraction-validator/corpus_survey_tier4.py` | Extend with per-section-family reporting, benchmark-slice mode |
| `tools/extraction-validator/ground_truth/*.yaml` | Expand per phase |
| `schemas/cds_schema_2025_26.json` | Read-only (consumed by SchemaIndex) |

## Validation strategy

### Primary loop (per phase)

1. **Freeze a benchmark slice** of ~50 tier4 docs (representative sample by school
   type, template year, page count). This slice does not move between phases.
2. **Run GT scorer** (`score_tier4.py`) against all ground truth files → 100%
   regression pass on existing fields.
3. **Run corpus survey** (`corpus_survey_tier4.py`) on existing tier4 artifacts (stored
   markdown) → confirm field count increase, check per-question-number population
   rates.
4. **Expand ground truth** for the section family just shipped: 10–20 new fields per
   school, hand-verified against source PDFs.
5. **Only then** do a wider extraction run when the phase is stable.

### Safeguards

- **Per-section isolation:** Each resolver only claims fields in its own section
  family. Prevents "Total" in J from stealing "Total" in B5.
- **Type validation:** Reject non-numeric values for Number fields, validate MM is
  1–12, DD is 1–31, currency parses correctly.
- **Corpus survey as primary progress signal** — not a new `--coverage` mode, but
  extensions to the existing `corpus_survey_tier4.py` which already measures
  per-question-number coverage on stored markdown.
- **Hard stop rule:** If a section family needs >50 lines of bespoke logic beyond what
  the schema resolver provides, it gets its own resolver function and its own phase.
  Don't force it through a generic path.

## Risks

| Risk | Mitigation |
|---|---|
| Schema question text doesn't match Docling labels | `_normalize_label()` handles known rewrites. Extend to strip `: males/females` suffix. Hand-coded overrides for stubborn mismatches. Proved on J + B2 in Phase 0 before committing. |
| Dimensional ambiguity from missing residency/category | Added residency + category to SchemaIndex. Resolves 70 of 90 previously-ambiguous buckets. |
| 20 irreducibly ambiguous fields | Table-position-aware logic in bespoke resolvers (C11 GPA, H.2A, D transfer credits). `pdf_tag` prefix used as structural signal. |
| Generic labels ("Total", "Specify:", "History") match wrong section | Per-section resolver isolation. Each resolver narrows to its own table slice before matching. |
| Docling renders tables as flat text | Known issue. Existing `_INLINE_PATTERNS` fallback. Each resolver handles its own degraded-input mode. |
| Performance (resolver dispatch per table) | SchemaIndex loaded once at module init. Section-header dispatch narrows resolver set per table. Measured: cleaner currently runs in <100ms per doc; 10x more matching is still <1s. |
| Template-year variation (pre-2020 CDS) | `_normalize_label()` handles freshman→first-year, nonresident aliens→nonresidents. Schema-driven matching returns empty for fields absent in older templates. |
| Full corpus drain after each phase is expensive and noisy | Removed as default. Benchmark slice + corpus survey on existing artifacts is the validation loop. Wider drain only after a phase is stable. |

## Open questions (from review)

1. ~~How will the matcher distinguish fields where the schema repeats the same question
   and the differentiator is residency or category?~~ **Resolved:** Added residency and
   category to SchemaIndex. Measured: resolves 70 of 90 ambiguous buckets.

2. ~~What is the fallback when subsection context is not present as a clean header?~~
   **Answer:** Each resolver has its own context-detection strategy. Some use `##`
   headers, some use table-row-as-header patterns, some fall back to sequential table
   ordering within a known page range. No single generic answer — this is why
   section-family resolvers exist.

3. ~~How will you prevent generic labels from matching the wrong section-family?~~
   **Answer:** Per-section resolver isolation. Each resolver only claims fields in its
   own section. A match for "Total" in the J resolver cannot steal "Total" in B5.

4. ~~One general engine, or section-specific resolvers?~~ **Answer:** Section-specific
   resolvers backed by shared SchemaIndex. The latter is the realistic path.

5. ~~Why invent `score_tier4.py --coverage` instead of extending
   `corpus_survey_tier4.py`?~~ **Answer:** Corrected. `corpus_survey_tier4.py` is the
   right tool. Extend it with per-section-family reporting and benchmark-slice mode.
