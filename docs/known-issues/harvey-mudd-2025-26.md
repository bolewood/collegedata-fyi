# Harvey Mudd College, CDS 2025-26 — known extraction issues

**Source PDF:** `CDS-HMC-2025.2026_shared.pdf`
**Docling extraction quality:** Degraded; contains real data corruption
**Last verified:** 2026-04-11

**⚠️ Consumers of the raw Docling JSON for this school will read wrong numbers from the C1 applicants/admits tables unless they specifically handle the issues below.** Validate against the source PDF before trusting any enrollment or admissions figure.

HMC's CDS exposes the real shape of the extraction-quality problem. Clean numeric tables (B2 race/ethnicity, B4-B21 graduation rates, C9 test-score 25/50/75 percentiles, C9 SAT range distribution, C10 class rank) all came through correctly. But several layout quirks produced values in the wrong rows — not just structural noise.

## Data-corrupting issues (high priority)

### 1. C1 applicants/admits table — values shifted by one row

The PDF's C1 section has three sub-blocks (Applicants, Admits, Enrollees) with a merged "TOTAL" column on the right. Docling misaligned the cells so values collapsed into the wrong rows:

```
| Total first-time, first-year men who applied                    | 3452 1761 |
| Total first-time, first-year women who applied                  | 4         |
| Total first-time, first-year another/unknown gender who applied |           |
```

**Ground truth from the PDF:** men=3452, women=1761, another/unknown=4.

The same row-shift pattern occurs in the Admits block (276/365/2 became "276 365" in men, "2" in women, blank in other) and in the C2 waiting-list table (685/439/0 became 685, "439 0", blank). **Every applicant/admit field for HMC is wrong in the raw Docling JSON.**

**Mitigation:** Template-aware validator that knows C1's expected shape (single integer per cell, rows sum in known ways). Any cell containing a space-separated pair of integers in a field expecting one integer is flagged for manual review.

### 2. B1 enrollment header collapse

The PDF has a two-row merged header: `FULL-TIME | PART-TIME` spanning three sub-columns each (Men/Women/Unknown). Docling flattened both rows, emitting `FULL-TIME PART-TIME` in every column slot and repeating "Men Women Unknown" unhelpfully. Body values are correct, but the column semantics (is "109" full-time men or part-time men?) are lost.

**Mitigation:** Hardcode HMC's B1 layout in a per-school override, or write a heuristic that detects merged-header collapse when column names repeat.

### 3. Checkboxes silently dropped throughout Section C

PDF shows clear ☒ marks on waiting-list policy questions in C2 ("Yes" on policy, "No" on ranked). Docling emitted all as unchecked `☐`. Also C3/C4/C5 are all blank in the extract even though the PDF has actual selections. Root cause unknown — possibly a different checkbox glyph or image the detector isn't catching.

**Mitigation:** Until resolved, treat all Section C checkbox fields from HMC as unknown rather than "unchecked."

## Structural issues (lower priority)

### 4. Section reading-order wrong

The extract emits `C1-C2: Applications` *before* the section heading `C. FIRST-TIME, FIRST-YEAR ADMISSION`, because of a centered-heading layout confusion. Any splitter that assumes `C` contains `C1`…`C20` will break.

### 5. Running page header emitted as H2 heading

"Common Data Set 2025-2026" appears as `##` five times in the extract — it's the page header, not a section. Yale's extract didn't have this problem (different page-numbering layout).

**Mitigation:** Post-processor strips recurring page-header text that appears ≥3 times at identical positions in the document.

### 6. Kerned digits in year numerals

Text like `## Fall 201 8 Cohort`, `## Common Data Set 202 5 -202 6`, and `Fall 202 5` appear throughout. The PDF has character kerning that inserts a narrow space inside year numerals on some pages.

**Mitigation:** Regex `20[12]\s?[0-9]` → `20\1\2` normalization during post-processing.

### 7. Section A missing entirely

HMC's shared PDF begins with "B. ENROLLMENT AND PERSISTENCE." This is **not** a Docling bug — Section A really is absent from the source document. The manifest should note "source PDF begins at Section B."

### 8. Boxed retention values flattened

B22's "231 / 220 / 95" boxed answers (retention cohort, still enrolled, percentage) come through as bare paragraphs without their labels attached — same pattern as Yale's H4/H6/H7 orphan headings.
