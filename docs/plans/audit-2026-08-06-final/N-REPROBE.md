# Deterministic N=20 resolver reprobe

Population: 1,342 schools whose latest `archive_queue` row is `failed_permanent/no_pdfs_found`. Sampling was declared before network access: take the 20 smallest `SHA-256("audit-2026-08-06-n1\0" + school_id)` values. The queue population was fully paged: 17,044/17,044 rows in 18 pages with no gap, duplicate, cap, or short-page mismatch.

The probe calls the real `resolveCdsForSchool` implementation, including redirects, direct-document handling, two-hop discovery, and production candidate selection. When a supplied homepage hint did not resolve, it called the same resolver on each of the 15 existing well-known paths; this extension is not currently used for unsuccessful homepage hints in production.

Results: all 20 base calls returned `no_cds_found`. All 300 extension attempts failed: 253 `upstream_gone`, 47 `no_cds_found`. The only supported cohort verdict is 20/20 `not_found_from_supplied_hint`. There was no extension win in this sample, so the audit neither recommends broad manual seed enrichment nor claims that the fallback will improve recall. No result is extrapolated to all unresolved schools, and no school is labeled “truly absent.”

The prior Adams State explanation is rejected. `findDownloadLinks()` emits `year:null`; the caller does not recover year-bearing link text/path/parent context; `pickCandidates()` rejects multiple yearless candidates before sentinel assignment. A safe fix direction is to inherit year evidence before selection, not to create multiple `unknown` rows that can collide on school/year uniqueness.

Machine-readable cohort, pagination, method, and verdict counts: `evidence/n-reprobe-summary.json`. Runnable implementation: `tools/data_quality/reprobe_resolver_cohort.ts`.
