# PRD 014 M4 Validation Findings

Generated: 2026-04-28T20:35:36.391882+00:00

## Outcome

**modest_delta**.

No value-level assertions changed. The measured delta is field-count only and falls in the PRD's modest-delta band.

## Scope

- Measured local Tier 4 markdown fixtures for Harvard 2024-25 and Yale 2024-25.
- Included Harvey Mudd 2025-26 Tier 2 as a Supabase-backed control when credentials were available.
- No local Tier 1 XLSX or Tier 5 scanned fixtures with hand-curated value assertions were available in this checkout.

## Summary

| Metric | Value |
|---|---:|
| Fixtures measured | 3 |
| Value assertions | 22 |
| Old assertions passing | 22 |
| New assertions passing | 22 |
| Wrong -> right shifts | 0 |
| Right -> wrong shifts | 0 |
| Average field-count delta | -4.49% |

## Fixture Results

| Tier | School | Year | Old schema | Old fields | Old parse errors | New schema | New fields | New parse errors |
|---|---|---|---|---:|---:|---|---:|---:|
| tier4 | harvard | 2024-25 | 2025-26 | 479 | 3 | 2024-25 | 444 | 1 |
| tier4 | yale | 2024-25 | 2025-26 | 471 | 5 | 2024-25 | 442 | 3 |
| tier2 | harvey-mudd | 2025-26 | 2025-26 | 558 | 6 | 2025-26 | 558 | 6 |

## Assertion Shifts

| Fixture | Metric | Expected | Old | New | Shift |
|---|---|---:|---:|---:|---|

## Interpretation

- Harvard 2024-25 and Yale 2024-25 keep the hand-verified browser-level assertions correct under year-matched extraction.
- Field counts drop on the Tier 4 fixtures because schema-local 2024-25 IDs no longer keep 2025-only fields that were previously projected under the wrong schema.
- Harvey Mudd 2025-26 is stable, as expected, because old and new schema selection are identical for 2025-26.

## Recommendation

M5 is optional rather than required by the evidence. If an operator chooses to drain, use a staged cohort drain with rollback snapshots.

Raw results: `.context/prd-014-validation/results.json`.
