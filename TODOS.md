# TODOS

## Completed

### Commit a sanitized M0 join report

**What:** After the May 2026 FSA workbook is downloaded, commit a sanitized join report (URL, sha256, OPEID storage type, match counts, named canaries) so the M1 gate is visible in git.

**Why:** `scratch/` is gitignored. A PR cannot prove the M0 gate passed if the report only exists on one laptop.

**Context:** Eng review 2026-09-17. Do not commit the xlsx. Institution-level FSA has no borrower PII. Likely path: `docs/designs/fsa-m0-join-report.md` or `tools/fsa/fixtures/m0-summary.json`. Depends on proving Excel OPEID is text vs numeric.

**Effort:** S
**Priority:** P1
**Depends on:** M0 workbook download to `scratch/fsa/2026-05/` — **done.** Report: `docs/designs/fsa-m0-join-report.md`.
**Completed:** v0.6.3.0 (2026-09-17)
