# Recommended data-integrity audit cadence

## Recommendation

Run the complete 24-check audit once a year, with the next full execution targeted for August 2027. Do not wait a year to detect the failures this audit was best at finding. Convert the cheap, objective checks into scheduled health checks and rerun the relevant track after any material pipeline change.

This audit was worth running even though it found no P1/P2 incident. It corrected three misleading audit conclusions before they became institutional knowledge:

- an unpaged query understated `no_pdfs_found` from 2,848 rows to 240;
- a page-size problem was mislabeled as `cds_fields` RLS failure;
- resolver and projection reports used incorrect causes or denominators.

It also established bounded evidence for missing projections, inaccessible source objects, document-hash drift, schema discrepancies, and a prospective Tier 6 versioning risk. Proving that an alarming claim is false is part of the value: it prevents engineering time from being spent on the wrong fix.

## Operating cadence

| Cadence | Checks | Output and alert condition |
|---|---|---|
| Daily | Current-year projection completeness and freshness; selected artifact → projection lag; IPEDS cache refresh timestamp once instrumented | Alert when less than 95% of selected current-year documents project within 24 hours, or any selected document remains unprojected for seven days |
| Weekly | Exact core counts, explicit PostgREST pagination assertions, archive attempt terminal/open counts, source-object accessibility | Alert on a gap/cap/duplicate, an unfinished attempt older than its timeout contract, or a new inaccessible current source |
| Monthly | Full archive outcome taxonomy, attempt p50/p95/timeout rate, loaded-but-unserved bounded inventory, projection identity discrepancies | Retain a dated machine-readable result and compare against the prior month; investigate step changes rather than absolute counts alone |
| Quarterly | Deterministic unresolved-school resolver cohort, full 4 KiB format-head corpus probe, ZIP byte sniff, per-question `cds_fields` distribution | Use a versioned sampling salt; alert on resolver regressions, new byte-routing exposure, or section/question distribution breaks |
| Per IPEDS release | Sign contract by release/field, accounting identity, draw-rate exclusions, provenance completeness, Scorecard/OPEID6 reconciliation | Block release when labeled negatives remain numeric, provenance is missing, raw components are erased, or the declared reconciliation gate fails |
| Annually | All 24 matrix checks, historical/schema drift, full loaded-but-unserved universe, manual OCR ground truth, producer-version history, consumer honesty review | Publish one canonical matrix and manifest. Preserve partial/deferred labels wherever evidence is unavailable |

## Change-triggered reruns

Do not wait for the calendar when any of these changes lands:

- extractor, cleaner, OCR, or producer-version logic: rerun A1–A4 and F1–F4;
- resolver, archive queue, finder hints, or storage routing: rerun C1–C3, F3, and the N cohort;
- schema registry or projection selector: rerun B2–B3, A4, D1, and G3;
- IPEDS loader, field registry, release fallback, or finance UI: rerun D2–D3, E1–E4, and G1–G2;
- public API/friendly-field behavior: rerun A3 and G1–G3.

## Work to finish before the annual rerun

These should be closed as targeted follow-ups, not carried untouched until 2027:

1. Build and review a declared OCR ground-truth set for F2, stratified by section and source family.
2. Exercise C3 concurrent enqueue behavior against an isolated database and retain the interleaving/result log.
3. Add selected `artifact_id` and copied `source_sha256` to projection provenance, then replace A4's producer/version/schema proxy with exact identity.
4. Instrument the IPEDS raw → facts → current-cache refresh chain before adopting an enforceable IPEDS freshness SLO.
5. Produce the full D3 loaded-but-unserved inventory through a bounded server-side aggregate rather than transferring all 4.4 million facts.
6. Decide whether the 27 observed keys outside the synthesized 2023–24 schema are valid aliases, cleaner leakage, or missing schema entries.
7. Couple Tier 6's producer version to cleaner behavior so a SHA-tagged artifact cannot suppress a required cleaner-only redrain.

## Automation plan

### Phase 1: preserve the baseline (shipped with this audit)

- Keep the runnable read-only collectors in `tools/data_quality/`.
- Keep one canonical matrix, a manifest with input/query/result hashes, and summarized evidence safe to commit.
- Treat every collection read as invalid unless stable order, `Content-Range`, uniqueness, and fetched-equals-expected assertions pass.

### Phase 2: scheduled health checks

- Add a lightweight scheduled workflow for daily/weekly checks.
- Store compact trend rows or workflow artifacts, not institutional source bytes or credentials.
- Open or update one operations issue only when a declared threshold fails; do not alert merely because a raw count changes.

### Phase 3: quarterly and release gates

- Run public-network probes with deterministic, versioned cohorts so results can be compared without convenience sampling.
- Attach the finance audit to each IPEDS release workflow as a blocking dry-run gate.
- Record drift against the prior successful result, including denominator changes and exclusions.

### Phase 4: annual independent review

- Re-read the implementation rather than trusting last year's matrix.
- Reproduce every retained severity from raw evidence.
- Retire checks only by explicitly replacing them with a stronger control; never silently remove an original ID.

## Evidence and ownership rules

- Each run records source commit, base commit, start/end times, input hashes, query hashes, result checksums, denominators, exclusions, and snapshot limitations.
- Production access remains read-only. Mutation and concurrency checks require an isolated environment.
- A wrong public value outranks a missing or explicitly flagged value. Control gaps remain hypotheses until affected data is demonstrated.
- The data-pipeline owner owns automated failures. A named data reviewer owns manual OCR/schema judgments. Release owners own the IPEDS gate for their release.

## Annual exit criteria

The annual audit is complete only when all 24 IDs have explicit dispositions, every paged result proves completeness, the resolver cohort is declared before fetching, `cds_fields` has a per-question distribution, severities cite demonstrated consumer impact, and the report does not imply an atomic snapshot where none exists.
