# Tier 4 Cleaner: Coverage Ceiling and What the LLM Fallback Needs to Know

**Created:** 2026-04-20
**Context:** Executed [PRD 005](../prd/005-full-schema-extraction.md) across 6 phases.
Went from 72 → ~380 fields on the 3-doc benchmark (Harvard, Yale, Dartmouth 2024-25).
The remaining ~60% of the schema resists deterministic mapping for reasons that will
matter to [PRD 006](../prd/006-llm-fallback.md).

---

## 1. Coverage snapshot (3-doc benchmark, post-Phase 6)

| Section family | Fill rate | Expected | Observed | Notes |
|---|---:|---:|---:|---|
| B4 (Grad rate current) | 100% | 32 | 96 | Letter-row grids are easy |
| B5 (Grad rate previous) | 100% | 32 | 96 | Same table shape |
| B2 (Race/ethnicity) | 87.8% | 30 | 79 | Clean 3-column matrix |
| I (Faculty + class size) | 86.4% | 49 | 127 | I1 letter-row grid + I3 size buckets |
| C7 (Basis for selection) | 84.2% | 19 | 48 | Checkmark-in-column |
| B3 (Degrees conferred) | 70.4% | 9 | 19 | Hand-coded baseline |
| C10 (Class rank) | 66.7% | 6 | 12 | Simple 2-col table |
| F (Student life) | 62.6% | 58 | 109 | Checkbox scan + F1 percentages |
| B1 (Enrollment) | 60.7% | 78 | 142 | Matrix with context tracking |
| C1 (Applications) | 56.7% | 30 | 51 | Gender rows + residency split |
| E (Academic offerings) | 52.9% | 34 | 54 | Checkbox scan |
| **B22** (Retention) | **33.3%** | 3 | 3 | Inline regex; only the % field |
| **C2** (Wait list) | **28.6%** | 7 | 6 | YesNo fields deferred |
| **H** (Financial aid) | **24.8%** | 165 | 123 | H1/H2/H2A/H4 covered |
| **G** (Annual expenses) | **18.8%** | 46 | 26 | G1 only; G5 fragmented |
| **C9** (Test scores) | **15.7%** | 87 | 41 | Percentiles covered; policies not |
| **J** (Disciplines) | **13.9%** | 120 | 50 | Most schools only fill one column |
| **C13–C22** (Policies) | **≤13%** | 56 | ~2 | Dates/YesNo/checkboxes interleaved |
| **C11** (GPA profile) | **11.1%** | 30 | 10 | Harvard only; Yale/Dart paragraph-ized |
| **A** (General info) | **9.0%** | 63 | 17 | Only the degree checkboxes |
| **D** (Transfer) | **1.5%** | 88 | 4 | Docling flattens D2 to paragraphs |
| **C5** (Carnegie units) | **0%** | 24 | 0 | Test schools don't fill it |
| **C3, C4, C6, C8** | **0%** | 10 | 0 | Single YesNo/checkbox fields |

The high-fill rows (>80%) share one property: the CDS template renders them as
a rectangular table with stable headers, and Docling's table parser preserves
that structure. Everywhere else, Docling flattens the table into paragraphs
and the deterministic parser can't recover positional context.

## 2. Docling failure modes the LLM will see

These are the input shapes to design prompts against:

### a. Table → paragraphs
Dartmouth's D2, Yale's C11, Harvard's G5 estimated-expenses all lose table
structure. What remains is an ordered list of cell *values* mixed with cell
*labels*, with no pipes or header row. Example:
```
Distribution of high school units
Total academic units
English
Mathematics
...
```
No value cells visible even though the PDF shows `4 | 4`, `3 | 3`. Docling
sometimes drops empty-cell pages entirely.

### b. Row merge
Two consecutive rows collapse into one table row. The single value array
belongs to *one* of them, but there's no reliable signal for which:
```
| Percent below 1.0 Totals should = 100% | 0.00% | 0.00% | 100.00% |
| Percent of women who join sororities Percent who live in college-owned | 100% | 97% |
```
The cleaner's current defense is "skip rows whose label matches ≥2 known
patterns" — safe but drops legitimate data too. An LLM can likely pick
the right parse because it sees the surrounding rows.

### c. Header promoted to data
When a header cell contains digits (e.g. "CIP 2020 Categories"), the parser
heuristic treats the header row as data and synthesizes an empty header.
J1 for every school has this; B5 for some. The cleaner recovers by
promoting row 0 back to header, but the LLM should expect tables where the
nominal header is blank and column meanings come from the first data row.

### d. Header/column concatenation
Docling occasionally merges two adjacent column headers:
```
| CLASS SUB- SECTIONS | 73 | 67 | ... |
```
The hyphenated "SUB- SECTIONS" splits across newlines in the PDF and lands
in one cell. `_normalize_label()` strips hyphens for matching but the
original text is surprising.

### e. Values rendered as prose
Harvard C11's B22 retention = `98%` appears ~1,700 chars after the `## B22`
header, separated by explanatory notes, definitions, and footnotes. The
deterministic approach uses anchored windows; an LLM should be instructed
that CDS fill-values can appear anywhere within a section boundary.

### f. Checkbox dialects
Three coexisting formats just in our 3-doc sample:
- `- [x] Label` (canonical markdown)
- `- [ ] X Label` (Harvard — unchecked brackets, literal X prefix)
- `| ☒ Label |` (Yale — inside a table cell)
- `- X Label` (Harvard F2 — list marker + X)

An LLM prompt should enumerate these explicitly.

### g. Wrong-file / blank-template archives
Not observed in the benchmark but documented in the PRD: some uploaded PDFs
are other-school CDSes or blank templates. The LLM fallback needs a "this
document does not describe the school" signal, not just empty values.

## 3. Schema ambiguities the LLM must disambiguate

From PRD 005 §"Measured schema ambiguity":

**1,075 of 1,105 fields** are uniquely identified by
`(section, subsection, question_norm, gender, cohort, unit_load, student_group,
residency, category)`. The remaining **20 are irreducibly ambiguous** without
table-position context:

| Fields | What they are | pdf_tag differentiator |
|---|---|---|
| 10 × C.11xx | GPA rows × 3 sub-tables | `FRSH_GPA_SUBMIT` / `FRSH_GPA_NO_SUB` / `EN_FRSH_GPA` |
| 4 × H.2Axx | H2A FT vs PT columns | `UG_FT_` vs `UG_PT_` (schema's `unit_load` has a metadata error) |
| 4 × D.13–D.16 | Credits count vs unit type | Position within row |
| 2 × C.16/C.17 | Date MM/DD × two deadlines | Surrounding anchor text |

For the LLM prompt: when a schema field has the same question text as
another in the same subsection, surface the `pdf_tag` as an extra
disambiguation hint. The existing `SchemaIndex.lookup_by_pdf_tag_prefix`
shape is already built for this.

**Residency and category matter.** Earlier drafts of PRD 005 ignored these
dimensions and left 90 buckets ambiguous. Adding them resolves 70 more.
C.119–C.130 (In-State / Out-of-State / Nonresidents / Unknown) and C.501–C.524
(Required vs Recommended units) both ride on dimensions the LLM must be told
to extract from column headers and prose context, not just row labels.

## 4. Deterministic heuristics that worked

Worth re-using in the LLM prompt or as post-LLM validators:

### a. Gender word-normalization
```
males|male → men; females|female → women;
another gender|unknown gender|unknown sex → unknown;
nonresident aliens → nonresidents;
freshman|freshmen → first-year  (pre-2020 templates)
```
Without these, every CDS filed before the 2019-20 template rename silently
misses B1 and C1. The LLM should receive post-normalized text or be told to
apply these rewrites before matching.

### b. Row-merge guards
A row whose label contains ≥2 known patterns is ambiguous; skip. This
protected F1 and C11 from bad values. The LLM should flag such rows rather
than guess.

### c. `pdf_tag` prefix as a structural signal
For the 20 irreducibly ambiguous fields, tag prefix encodes which sub-table
the field belongs to. The LLM prompt can pre-filter its field list to only
the prefix-matching subset when it knows which sub-table it's processing.

### d. Section detection signals
Most sections are findable by either:
- A `##`-prefixed header containing the section code ("B1", "J1")
- A distinctive header-row signature (C7 "Very Important / Important /
  Considered"; B5 "Recipients of a Federal Pell Grant ...")
- A row-label signature ("CLASS SECTIONS" for I3)

When all three fail (Dartmouth J1 whose "CIP 2020" promoted row 0 to header),
fall back to the section-code anchor.

### e. Context tracking within concatenated tables
B1 has sub-table dividers as row labels ("Undergraduate Students: Full-Time",
"Graduate Students: Part-Time", etc.). Track the current `(unit_load,
student_group)` as you walk rows. Works for Harvard (one big table) and
Yale (separate `##`-headed tables) with the same code.

### f. Numeric validators
- `_extract_number()` strips `$`, `%`, `,` then requires `float()` succeeds.
- `_extract_currency()` is the same but preserves thousands-formatted dollar
  amounts for post-extraction typing.
These reject "Not Applicable", "varies", "n/a", and free-text leakage from
merged rows before a wrong value lands in the output.

## 5. Sections most in need of LLM rescue (priority for 006)

Ordered by combination of (schema weight × current gap × structural
fixability):

1. **H5/H6/H7/H8 (~80 fields)** — loan totals, aid to nonresidents,
   financial-aid forms and deadlines. Cleanable if the LLM is given a
   section-scoped prompt; currently zero coverage because these mix small
   tables, free-text prose, and checkbox dialects.
2. **C13–C22 (~56 fields)** — application fee, deadlines, reply dates, early
   decision. The MM/DD pairs with multiple deadlines per page are exactly
   the kind of "paired-anchor" extraction that breaks inline regex but works
   well with a schema-aware LLM.
3. **D2–D16 (~80 fields)** — transfer applicants + transfer credit policies.
   Docling flattens these aggressively. An LLM fed the whole `## D.` window
   can reconstruct what a table parser can't.
4. **C11 GPA profile on Yale/Dartmouth (~20 additional fields)** — Harvard's
   C11 table parses cleanly, but Yale/Dartmouth render it as paragraphs.
   Same schema, same rows, different renderer output. High-value because
   the all-enrolled column is consumer-facing.
5. **G5 estimated expenses (~13 fields)** — Residents/Commuters/Living-with-
   family blocks of Books/Housing/Food/Transport/Other. Currently zero
   coverage on Harvard because Docling fragments this section into isolated
   dollar amounts with no row label.
6. **C9 test-score policy fields (~46 fields)** — percentiles are handled;
   what's missing are the composite use-policy Yes/No and "which tests does
   your institution accept" matrices.
7. **A address / admissions office (~26 fields)** — contact fields with
   phone numbers, URLs, email. Low consumer value but near-trivial for an
   LLM with named-entity extraction.

## 6. Sections where LLM will struggle too

These are rendering artifacts the LLM can't fix without the raw PDF:

- **C3, C4, C6** — single YesNo checkboxes buried inside prose. Without the
  ✗/☒ glyph preserved, impossible to tell which option is checked from text
  alone.
- **C5 Carnegie units** — all three test schools leave this blank in the
  PDF. Not a parsing problem, a "school didn't answer" problem. The LLM
  should emit `null` rather than hallucinate.
- **Comment/explanation text fields** (A.402, C.1608, E.120, H.1801, ...) —
  these are free-text. The LLM can extract them, but validation is
  impossible without a human or a corpus-level sanity check.

## 7. What PRD 006 should pre-compute at prompt time

Hand-off shape suggested by this work:

```python
{
  "school_id": "...",
  "cds_year": "2024-25",
  "section_code": "H5",           # <-- scope the LLM's task
  "section_markdown": "...",       # extracted from full markdown by
                                   # section-code anchors, NOT the whole doc
  "schema_fields": [
    {
      "question_number": "H.501",
      "question": "Number of students borrowing from federal loans",
      "pdf_tag": "FED_LOAN_N",
      "value_type": "Number",
      "dimensions": {
        "cohort": "2024 graduating class",
        "unit_load": "All"
      },
      "note": "Must be ≤ H.401 (total class size)"
    },
    ...
  ],
  "already_extracted": {            # <-- so the LLM doesn't duplicate
    "H.401": "1753",
    "H.2203": "98"
  },
  "known_hints": [                  # from heuristic §4a
    "template uses 'men/women' for gender — gender fields in schema"
    " say 'males/females'; treat as synonyms"
  ]
}
```

Validation post-LLM:

- Type-check every value against `value_type` (Number / Nearest $1 / MM / DD /
  YesNo / Text / x).
- Numeric ranges: MM in 1–12, DD in 1–31, percentages in 0–100, cohort
  counts ≤ total-enrolled.
- Cross-field constancy: if a school's G.101 (FY tuition) is $59,320 and
  G.102 (UG tuition) is populated by the LLM, flag a discrepancy >5%.
- `notes.markdown` should stay the authoritative evidence — every LLM value
  needs a markdown offset so reviewers can verify.

## 8. Non-goals for the LLM fallback

Learned the hard way during PRD 005:

- **Don't ask the LLM to infer which CDS template year** the doc uses. The
  schema-year authority moved to the extractor (ADR 0007); pass the year in
  explicitly.
- **Don't ask the LLM to compute** totals, ratios, or percentages. Every
  time the CDS template has a "Total = sum of columns" row, the school
  authoritatively fills it — and when they don't, the value should stay
  null. Computed totals are a data-quality signal, not an extraction task.
- **Don't prompt-inject documents into the cache.** The section markdown
  is the uncached tail; the schema fragment, field list, and validation
  rules are the cached head. Mixing them kills the cache hit rate.
