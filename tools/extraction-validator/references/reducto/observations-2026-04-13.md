# Reducto extraction — field notes (2026-04-13)

**Producer:** Reducto (third-party hosted extractor)
**System prompt:** the CDS-specific prompt drafted in this session with hard rules targeting the HMC failure modes (one-integer-per-cell, merged headers, honest null on ambiguous checkboxes, strip running page headers, normalize kerned years, section-letter reading order, boxed-value labels, Section A may be absent)
**Schools tested:** Harvey Mudd 2025-26, Yale 2024-25
**Source PDFs:** same files used for the Docling baseline audit
**Artifacts:**

- `references/reducto/harvey-mudd-2025-26/extract.json` (46 pages)
- `references/reducto/yale-2024-25/extract.json` (43 pages)

## Headline

Reducto + the hard-rules prompt resolves **every data-corrupting issue** recorded in `docs/known-issues/` for both schools. All hand-verified ground-truth values in `ground_truth/*.yaml` match. The Docling regressions we were trying to fix are gone, and the cosmetic structural issues are gone too because a reasoning extractor doesn't produce orphan heading lines, `nan` cells, or kerned year numerals in the first place.

This is a materially different extraction shape from Docling, not just a better-tuned version of the same thing.

## Harvey Mudd — the Docling regression cases

| Field | Ground truth | Docling | Reducto |
|---|---|---|---|
| C1 applied men | 3452 | `"3452 1761"` | **3452** ✓ |
| C1 applied women | 1761 | `"4"` | **1761** ✓ |
| C1 applied other | 4 | blank | **4** ✓ |
| C1 admitted men | 276 | `"276 365"` | **276** ✓ |
| C1 admitted women | 365 | `"2"` | **365** ✓ |
| C1 admitted other | 2 | blank | **2** ✓ |
| C1 applied total | 5217 | — | **5217** ✓ |
| C1 admitted total | 643 | — | **643** ✓ |
| C2 waitlist offered / accepted / admitted | 685 / 439 / 0 | `685`, `"439 0"`, blank | **685 / 439 / 0** ✓ |
| C2 waiting-list policy | Yes | silently dropped to `false` | **`true`** ✓ |
| C2 waitlist is ranked | No | silently dropped | **`false`** ✓ |
| B1 full-time vs part-time | merged header | collapsed | **preserved** ✓ |

The C1 row-shift bug is the consumer-dangerous failure mode — a naive reader of Docling's HMC JSON would silently compute wrong admit rates, wrong yield, wrong gender ratios. Reducto eliminates this entirely for HMC.

## Yale — the Docling cosmetic cases

Yale was already mostly clean under Docling; the issues were structural, not data-corrupting. Reducto resolves them too:

| Docling quirk | What happened | Reducto behavior |
|---|---|---|
| Single-cell boxed values promoted to H2 headings (`## 1665`, `## 489`, `## $83,878.16`) | Labels lost; a section splitter would treat "1665" as a new section | All three values land in labeled fields: `H4_undergraduate_class_size_graduates_count: 1665`, `H6_H7.number_of_nonresidents_awarded_institutional_aid: 489`, `H6_H7.average_institutional_aid_award_to_nonresidents: "$83,878.16"` |
| Empty C11 / C12 GPA tables flattened to paragraph runs | Parsers keying off table grammar miss the fields entirely | Reducto emits the full field skeleton with explicit `null` values and preserves the section shape |
| `nan` in empty H3 cells | Pandas-default string leaks into output | None observed |
| Duplicate header rows at page breaks | Cosmetic noise | None observed |
| Kerned year numerals (`Fall 202 5`) | Downstream regex bait | None observed |
| Reading-order confusion around centered headings | `C1-C2` appeared before `C.` | Sections are keyed by letter, so reading order is structurally correct regardless |

Ground-truth spot checks all match: B1 full-time men=782 / women=769 / another=3, total undergrads 3234/3422; B2 nonresident=169, Hispanic=289, White=463, Asian=320; B3 bachelors=1665, masters=2757, doctoral research=438, doctoral professional=318; C9 SAT composite 1480/1530/1560; C9 ACT composite 33/34/35.

## What the prompt bought us

The "one integer per cell" hard rule generalized beyond C1. Reducto's `_notes` arrays at both the top level and at subsection level show the model spotting and repairing cell-merge artifacts in tables the prompt didn't name, with its reasoning preserved:

**HMC notes:**
- `B4 (Fall 2019) row D Pell cell showed '24 24' due to a layout artifact; recorded as 24`
- `B4 (Fall 2018) several cells displayed extra numbers (e.g., '49 49' in C subsidized, '40 10' and '121 21' in D); retained the correct first values consistent with row sums`
- `C14 application closing date cells displayed '1 5' in both month and day; interpreted as Month=1, Day=5 (January 5) per CDS convention`
- `H2 row A 'Less than full-time Undergrad' cell showed '24 24'; recorded as 24`

**Yale notes:**
- `H2 row D (Less Than Full-time Undergrad) shows '6555' in the source, which is inconsistent with other entries and likely a misalignment artifact; set to null`
- `J Interdisciplinary studies CIP field appears as '2222-227777 30' (scraping artifact); recorded as CIP '30'`
- `C1 enrolled by gender includes zeros for 'another gender' whereas B1 shows 3 'another gender' full-time first-time students; differences may reflect reporting guidance`

The honest-uncertainty rule also fired correctly. Ambiguous checkbox glyphs in HMC C6 / C8 and Yale C6 come back as `null` with notes explaining the glyph was unreadable — exactly what we wanted. Docling's failure mode was silently emitting `false` for every checkbox, which is strictly worse than admitting ignorance.

This is the extractor behavior we actually wanted: see the artifact, repair or flag it, record why. Docling had no mechanism for either step.

## Problems and caveats

### 1. Schema is not stable across schools

**Same prompt, same settings, different schema shape.** Compare the subsection keys:

| Section | HMC keys | Yale keys |
|---|---|---|
| B1 | `B1` | `B1_institutional_enrollment` |
| B2 | `B2` | `B2_enrollment_by_racial_ethnic_category` |
| B4-B21 | `B4_B21` | `B4_B21_graduation_rates_bachelors_or_equivalent_programs` |
| C1 | `C1` | `C1_applications_first_time_first_year_fall_2024` |
| C8 | `C8` (contains `C8A_entrance_exams_use_in_admission`) | `C8_SAT_ACT_policies` |
| C9-C12 | `C9_C12` | `C9_C12_first_time_first_year_profile_fall_2024` |

Both schools grouped some related subsections (`B4_B21`, `C9_C12`, etc.) even though the prompt asked for `B4`, `B5`, ..., `B21` as separate keys. That's tolerable — the grouping is sometimes structurally honest (B4-B21 really is one big graduation-rate table in the source). What is **not** tolerable is the inconsistent key naming: HMC emitted `B1` while Yale emitted `B1_institutional_enrollment`. A consumer can't write `row = r["B"]["B1"]` once and have it work for every school.

**Implication for V1b:** Reducto's per-PDF accuracy is excellent, but the raw output needs a normalizer before it's queryable across schools. The normalizer either lives in the prompt (force a stricter JSON Schema, probably via Reducto's schema-constrained extraction mode rather than free-form output) or in post-processing (map `B1_institutional_enrollment` → `B1` via key-prefix regex). Prompt-side is cleaner and likely worth testing next.

This is the `cds_schema_v1` problem ADR 0002 anticipated, arriving earlier than expected. Reducto makes a target schema worth publishing sooner because the underlying data is now trustworthy enough to normalize.

### 2. Cross-table inconsistencies in the source PDF propagate

Yale's C1 shows `enrolled_by_gender: {men: 782, women: 772, another: 0}` while B1 shows `first-time first-year: {men: 782, women: 769, another: 3}`. Same cohort, same school, different numbers across two CDS tables. Reducto reproduced both faithfully and flagged the discrepancy in `_notes` rather than picking one. Same story for HMC: `C1 enrollees by gender: 'another/unknown' blank, but status table shows 2 full-time unknown; both values are preserved as-is per their respective tables`.

This is correct extraction behavior — the source PDF is inconsistent, not Reducto. But any downstream consumer merging B1 and C1 into a single "number of enrolled first-year men" field will need to pick a source and document the choice. Worth adding to the `known-issues/` notes for both schools.

### 3. Citations are not populated

The Reducto response payload has a `citations` key at the top level but both runs returned `null` / empty. If Reducto can return per-field bounding boxes or page coordinates, that would be a meaningful provenance win over Docling (which has nothing beyond "somewhere in the document"). Worth checking the Reducto API docs to see whether citations need to be explicitly requested, or whether we'd need to move to their schema-constrained extraction mode to get them.

### 4. Section A absent field is handled inconsistently

HMC correctly set `_section_a_present: false` per the prompt. Yale set `_section_a_present: null` and then emitted a populated `A` section anyway. The prompt's instruction was "if absent, omit A and set the flag to false" — Yale should have flipped the flag to `true` and kept the section, or just omitted the flag entirely when A is present. Minor. Worth tightening in the prompt.

### 5. Checkbox honest-nulls are not free

Reducto sets `null` on ambiguous checkboxes, which is what the prompt asked for and strictly better than Docling's silent-false. But "null" still isn't "yes" or "no" — any consumer wanting a definitive answer for a specific school's specific policy field (e.g., "is Yale test-optional?") will still need to go to the source PDF and verify. This is a real limit of even a good extractor: glyph ambiguity doesn't fully go away, it just becomes explicit.

## What this does and doesn't prove

**What this proves for V1b:**
- A well-prompted reasoning extractor can produce data quality Docling cannot match on the schools where Docling currently corrupts numbers.
- The "one integer per cell" hard rule is the single most load-bearing instruction — it catches the most common PDF-layout artifact class and repairs it with reasoning.
- The prompt's honest-uncertainty contract generalizes to table cells as well as checkboxes, which Docling has no mechanism for.

**What this does not yet tell us:**
- Per-page cost. Reducto is a paid API; Docling is self-hosted and effectively free. The accuracy win is only worth paying for if the price is reasonable at corpus scale (500 schools × 5 years = 2,500 extractions for the V1 target).
- Latency. Reducto response time is not captured here.
- Behavior on the long tail: image-only scans, JS-gated downloads, poorly scanned old PDFs, non-standard layouts. Two well-produced PDFs from well-resourced institutions is not a corpus.
- Cross-school schema stability at corpus scale. We have N=2 and the schemas already diverge.
- Whether Reducto's schema-constrained extraction mode would fix the key-naming inconsistency at no accuracy cost.

**Next concrete tests worth running:**
1. Re-run both PDFs through Reducto using its schema-constrained extraction mode with a fixed JSON Schema derived from this observation doc. If accuracy holds and keys stabilize, schema drift stops being a concern.
2. Pick 3 more HMC-class "known-hard" PDFs (merged headers, layout quirks) and verify the hard-rules prompt still repairs them.
3. Get Reducto per-page cost and compute the corpus-scale price. Compare against a Docling-plus-post-processing path that specifically targets the C1 row-shift artifact.
4. Check whether citations can be returned, and what they look like. Per-field page coordinates would meaningfully upgrade the provenance story beyond the PDF+JSON pair V1b currently plans.

## File locations

```
tools/extraction-validator/references/reducto/harvey-mudd-2025-26/extract.json
tools/extraction-validator/references/reducto/yale-2024-25/extract.json
tools/extraction-validator/references/reducto/observations-2026-04-13.md  (this file)
```

`references/` holds curated reference extracts from producers other than the transient Docling scoring runs under `runs/`. Reducto can still be scored against the same ground truth once the validator learns to read JSON schemas in addition to markdown.

## Postscript: the HMC audit was solving the wrong problem

**Added 2026-04-13, after the AcroForm discovery below.**

A day after these notes were written, we checked HMC's source PDF with `pypdf.get_fields()` and found **1,026 AcroForm fields with 558 populated**, including every single C1/C2 ground-truth value under canonical US News tag names (`AP_RECD_1ST_MEN_N = 3452`, `AP_RECD_1ST_WMN_N = 1761`, `AP_RECD_1ST_UNK_N = 4`, and so on). The row-shift corruption this document compares Docling and Reducto on was never a parser bug at the source — the source had the data cleanly in named form fields. We picked OCR/layout parsing on a fillable PDF and benchmarked two extractors against a problem that did not exist.

The Reducto-vs-Docling comparison above is still meaningful for Yale and Harvard, which are genuinely flattened (0 AcroForm fields). For HMC specifically, both extractors were the wrong tool and the right tool is `pypdf.get_fields()`.

See `docs/known-issues/harvey-mudd-2025-26.md` for the corrected interpretation.
