# PRD 014 M4 Validation Findings

Generated: 2026-04-28T19:41:55.339045+00:00

## Outcome

**big_delta**.

The validation found value-level assertion shifts, so the PRD's M5 decision gate is open. The observed right-to-wrong shifts are not evidence for a corpus drain yet; they point to Tier 4's remaining 2025-keyed C1 mappings, which M6 is intended to fix.

## Scope

- Measured local Tier 4 markdown fixtures for Harvard 2024-25 and Yale 2024-25.
- Included Harvey Mudd 2025-26 Tier 2 as a Supabase-backed control when credentials were available.
- No local Tier 1 XLSX or Tier 5 scanned fixtures with hand-curated value assertions were available in this checkout.

## Summary

| Metric | Value |
|---|---:|
| Fixtures measured | 3 |
| Value assertions | 22 |
| Old assertions passing | 21 |
| New assertions passing | 19 |
| Wrong -> right shifts | 0 |
| Right -> wrong shifts | 2 |
| Average field-count delta | -4.37% |

## Fixture Results

| Tier | School | Year | Old schema | Old fields | Old parse errors | New schema | New fields | New parse errors |
|---|---|---|---|---:|---:|---|---:|---:|
| tier4 | harvard | 2024-25 | 2025-26 | 479 | 3 | 2024-25 | 448 | 1 |
| tier4 | yale | 2024-25 | 2025-26 | 467 | 5 | 2024-25 | 436 | 3 |
| tier2 | harvey-mudd | 2025-26 | 2025-26 | 558 | 6 | 2025-26 | 558 | 6 |

## Assertion Shifts

| Fixture | Metric | Expected | Old | New | Shift |
|---|---|---:|---:|---:|---|
| harvard 2024-25 | applied | 54008 | 54008 | 54928 | right_to_wrong |
| harvard 2024-25 | admitted | 1970 | 1970 | 2697 | right_to_wrong |
| harvard 2024-25 | first_year_enrolled | 1647 | - | - | both_wrong |

## Interpretation

- Harvard 2024-25 is the critical regression case: old projection used the 2025-26 total fields and matched the hand-verified admissions totals; year-matched Tier 4 projection switched to the 2024-25 derived formula but the cleaner still emits several C1 values under 2025-shaped IDs.
- Yale 2024-25 keeps SAT/ACT assertions correct but field count drops under year-matched cleaning, again because the cleaner still has 2025-keyed maps in places.
- Harvey Mudd 2025-26 is stable, as expected, because old and new schema selection are identical for 2025-26.

## Recommendation

Do not run M5 as a broad Tier 4 corpus drain yet. Promote M6 or a narrow C1 mapping fix before draining 2024-25 Tier 4 artifacts. M3 remains useful for Tier 1/Tier 2/Tier 6 and for correctly tagging new artifacts by schema version, but the M4 evidence says Tier 4 does not fully benefit until its hard-coded mappings are schema-derived.

Raw results: `.context/prd-014-validation/results.json`.
