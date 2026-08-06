# Static Audit Design v2 — Execution NOT STARTED

**Status:** Design memo only. No R-class queries executed, no live snapshot, no measured findings.
**Commit:** `6938972` (2026-08-06). Prior `AUDIT_REPORT.md` mislabeled as "execution" — corrected here.
**Location:** `docs/plans/audit-2026-08-06-design-v2/` (tracked, replaces prior `audit-2026-08-06/`).

## What this is
Corrected v1 red-team fixes applied: path fixes, finance sign/identity corrections,
boundary model, R/O/N/M/T taxonomy, reproducibility framing. No counts.

## What this is NOT
- Not an executed audit. Manifest `live_db_access: false`.
- No P1 findings — prior P1 section demoted to hypotheses/control gaps.
- No 24-check coverage matrix, no evidence register.

## To execute (recommended follow-on, 8–10d)
1. Freeze snapshot (export cds_documents/cds_artifacts/school_browser_rows at as_of).
2. Write runnable SQL for 24 checks, produce coverage matrix (executed/rejected/deferred/blocked).
3. Emit evidence register with query hashes, input counts, numerators/denominators, checksums.
4. Re-issue as `audit-2026-08-06-final/` only when R/O measurements pass.

## Known gaps accepted from critique
- Manifest missing hashes/checksums, timestamps per check (see run_manifest.json notes).
- Distribution stratification requires T-class tooling (survey doesn't emit declared dims).
- Projection identity needs recompute-and-compare or provenance column.
- `detected_year` is worker-written; `0.3.14` is tier4-only.
