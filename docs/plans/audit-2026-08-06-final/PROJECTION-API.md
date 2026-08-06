# Projection and API findings

The freshness denominator is not all 4,071 historical documents. It is the 563 documents that are extracted, have a selected extraction result, and have canonical year start >=2024. `school_browser_rows` intentionally excludes `wrong_file`; this cohort contains no such exclusion. `cds_fields` projects all selected values.

Against that denominator, eight expected browser documents are missing and 12 expected field-projection documents are missing. Three browser documents are unexpected because their current document extraction status is failed. For present rows, zero browser or field projections have `updated_at` before the selected artifact's `created_at`.

The apparent two-row browser identity mismatch is a proxy result. One UVA row is likely stale (browser Tier 4 0.3.0 while the selected result is Tier 4 0.3.1). The Swarthmore mismatch is expected: the SQL selected view chooses a newer Tier 2 artifact with 581 AcroForm labels, zero mapped fields, and 581 unmapped fields, while the Python projector deliberately rejects unusable label-only Tier 2 and selects Tier 4. Therefore the SQL view is not a complete oracle for projector selection.

Both projection tables have `updated_at`, and delete/reinsert makes it a practical refresh timestamp. Neither stores the selected `artifact_id` or a copied `source_sha256`; producer/version/schema/time are only identity proxies. The daily extraction worker runs at 09:17 UTC, but there is no independent full-rebuild/freshness-reconciliation cron.

The friendly admissions API behavior is intentional and visible: 5/558 browser rows have incoherent applied/admitted/enrolled counts, and 15 non-null values are withheld with `low_confidence_extract` plus a reason. The underlying rows remain queryable. No P1/P2 is assigned because the API flags rather than silently substitutes the values.

Proposed initial CDS projection SLO: at least 95% of selected current-year documents projected within 24 hours, with no selected document older than seven days lacking a projection. Instrument artifact identity and the IPEDS cache refresh chain before enforcing a cross-pipeline SLO.

Machine-readable evidence: `evidence/live-readonly-summary.json`, `evidence/pagination.json`, and `evidence/static-contracts.json`.
