# PRD 012 Phase 0 Findings

**Generated:** 2026-04-28T14:39:27.885136+00:00

## Decision

Promote SAT/ACT submission-rate and percentile fields to `school_browser_rows` backend columns. Keep GPA and class-rank out of first-class browser columns.

This is a backend/API expansion only. The public `/browse` UI should not add default score filters until the UI can pair scores with submit-rate caveats.

## Before / After

The PRD 012 production refresh materially changed the public browser substrate:

| Measure | PRD 010 launch | PRD 012 refresh | Delta |
|---|---:|---:|---:|
| `cds_fields` rows | 113,836 | 217,910 | +104,074 (+91.4%) |
| `school_browser_rows` rows | 472 | 469 | -3 stale rows |
| Processed documents | 507 | 503 | -4 stale/non-qualifying rows |
| Mean field rows per processed document | 224.5 | 433.2 | +208.7 (+93.0%) |

This is a coverage improvement, not a blanket accuracy claim. Field count tells us
that more deterministic values are reaching the public substrate; correctness still
depends on producer-specific extraction quality and spot checks.

## Denominators

| Metric | Count |
|---|---:|
| `school_browser_rows_2024_plus` | 469 |
| `primary_clean_browser_rows_2024_plus` | 439 |
| `primary_clean_latest_schools_2024_plus` | 365 |
| `primary_clean_pdf_flat_rows_2024_plus` | 302 |
| `manifest_primary_clean_2024_plus` | 461 |
| `no_selected_result_extracted_primary_clean` | 0 |
| `extraction_error_primary_clean` | 22 |

## Promoted SAT/ACT Metrics

| Metric | Field | Primary clean reported | Primary clean coverage | pdf_flat coverage | Parse errors | Latest-row coverage | Latest-with-field coverage | Missing submit-rate rows |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `sat_submit_rate` | `C.901` | 287 | 65.4% | 67.2% | 1 | 65.2% | 67.7% | 0 |
| `act_submit_rate` | `C.902` | 255 | 58.1% | 57.3% | 2 | 57.8% | 60.0% | 0 |
| `sat_composite_p25` | `C.905` | 290 | 66.1% | 70.9% | 18 | 67.1% | 68.0% | 35 |
| `sat_composite_p50` | `C.906` | 295 | 67.2% | 71.9% | 3 | 68.0% | 68.8% | 34 |
| `sat_composite_p75` | `C.907` | 288 | 65.6% | 70.2% | 3 | 66.6% | 67.7% | 33 |
| `sat_ebrw_p25` | `C.908` | 269 | 61.3% | 63.2% | 17 | 63.0% | 63.8% | 32 |
| `sat_ebrw_p50` | `C.909` | 272 | 62.0% | 63.9% | 0 | 63.6% | 64.1% | 31 |
| `sat_ebrw_p75` | `C.910` | 268 | 61.1% | 62.6% | 2 | 62.7% | 63.8% | 30 |
| `sat_math_p25` | `C.911` | 304 | 69.2% | 74.5% | 16 | 70.4% | 71.2% | 36 |
| `sat_math_p50` | `C.912` | 306 | 69.7% | 75.2% | 1 | 70.7% | 71.2% | 35 |
| `sat_math_p75` | `C.913` | 301 | 68.6% | 73.8% | 3 | 69.6% | 71.0% | 34 |
| `act_composite_p25` | `C.914` | 287 | 65.4% | 70.9% | 42 | 65.8% | 67.1% | 50 |
| `act_composite_p50` | `C.915` | 295 | 67.2% | 72.9% | 23 | 67.7% | 68.5% | 55 |
| `act_composite_p75` | `C.916` | 290 | 66.1% | 71.2% | 5 | 66.6% | 68.0% | 50 |

## Held Out

### class_rank

- Field IDs: `C.1001`, `C.1002`, `C.1003`, `C.1006`
- Primary clean reported values across family: 1,022
- Parse errors across family: 49
- Source-format mix: `{"html": 4, "pdf_fillable": 192, "pdf_flat": 747, "xlsx": 79}`

### gpa

- Field IDs: `C.1201`, `C.1202`
- Primary clean reported values across family: 431
- Parse errors across family: 22
- Source-format mix: `{"pdf_fillable": 123, "pdf_flat": 268, "xlsx": 40}`

## Notes

- SAT/ACT score values describe score submitters, not the full admitted or enrolled class.
- Submit-rate columns are stored fractionally in `0..1` and included beside score fields.
- The backend does not hard-code a submit-rate threshold. `browser-search` reports companion submit-rate missingness for active SAT/ACT score filters.
- GPA remains long-form only because scale comparability is not resolved.
- Class-rank remains long-form only because denominator semantics are ambiguous without a dedicated UI.
