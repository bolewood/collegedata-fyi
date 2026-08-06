# Data Integrity Audit — Design v2 (not execution)

See README.md for status. This replaces prior AUDIT_REPORT.md which falsely claimed execution.

## Verified code facts (static, correct)
- Schema 2025-26: 1105 fields.
- Producers: tier4_docling 0.3.14 (current), tier4_llm_fallback 0.1.0.
- Finance: `numeric<0 && value_label → status` else numeric; draw rate `abs(F2H03C)/F2H01`, F2H03D preserved raw.
- API: finance via `categories=finance`, compare rejects finance intentionally, spreadsheet ≠ browser_rows.

## Hypotheses / control gaps (NOT P1 findings — unmeasured)
- H1 Single-section CDS loss: unquantified; needs N reprobe cohort.
- H2 Projection staleness: missing per-document control, not demonstrated stale data.
- H3 Admissions withholding: correct flagged behavior (`low_confidence_extract`), count withholdings only.
- Severity rubric undefined — define weights/thresholds before scoring.

## Deferred / needs disposition (24-check matrix pending)
Historical-schema leakage, synthesized-schema validation, direct ipeds_facts readers,
finance provenance parity, label fuzzing, OCR ground truth, format sniffing,
producer-bump history, reconciliation, loaded-but-unserved, API tests — all pending
explicit executed/rejected/deferred/blocked rows.

## Execution contract for final
Per-check as_of snapshot, query hashes, input counts, numerators/denominators/exclusions,
checksums. See README.md step 1-4.
