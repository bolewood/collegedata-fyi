# Partial execution — manual OCR ground truth, isolated concurrency, and full-universe serving inventory remain

This is the canonical result of the 2026-08-06 read-only data-integrity audit. It is deliberately not called final: all 24 original checks have a disposition, but F2 needs human ground truth, C3 needs an isolated database, and D3 remains bounded to endowment reporters. The sole canonical matrix is `24-check-matrix.json`.

The audit was worth running even without a P1/P2 incident because it corrected truncated-query, authorization, denominator, and causal errors while establishing a reproducible baseline. Repeat the complete audit annually, run cheap health checks daily through quarterly, and rerun affected tracks after extractor, resolver, schema, projection, IPEDS-loader, or public-API changes. The operating schedule and follow-up work are in `RECOMMENDED-CADENCE.md`.

## Outcome

- 11 checks executed, 11 partial, one deferred, one rejected/reframed.
- No defensible P1/P2 was demonstrated. Five checks retain `H` control/data-review hypotheses; surprising counts alone were not assigned incident severity.
- No production data, storage object, RPC, queue, or projection was mutated. Requests were GET-only; public source/reprobe requests were authorized.
- The live run is sequential, from `2026-08-06T18:50:04Z` to `2026-08-06T18:53:53Z`, not an atomic snapshot. Each paged query carries its own capture time, result hash, page size/count, Content-Range list, and assertions.

## Corrections to the abandoned partial report

The former `no_pdfs_found=240` result was exactly an unpaged 1,000-row artifact. Full paging found 2,848/17,044 queue rows across 1,356 schools. Completed rows with null outcome are 2,470/10,945 (22.57%), not “mostly null.”

`cds_fields` service-role reads succeeded. All 262,537 rows were fetched in 263 explicit pages, producing 1,157 per-question rows and full A–J distributions. The previous RLS diagnosis was not reproduced.

The resolver reprobe is now a declared deterministic 20-school sample from 1,342 schools whose latest queue row was `failed_permanent/no_pdfs_found`. All 20 remained `not_found_from_supplied_hint`; all 300 well-known-path extensions also failed. It is not called a 20% miss rate and no school is called “truly absent.” Adams State’s code-path cause is lost year evidence before multi-yearless candidate selection, not an `UNKNOWN_YEAR_SENTINEL` guard.

Projection freshness now uses an eligible denominator: 563 extracted, selected documents with canonical year start >=2024. Eight expected browser rows and 12 expected field projections are missing; three failed documents remain in the browser table. Present rows never had `updated_at` before the selected artifact. Two SQL-view identity proxies disagree, but one is expected because the Python projector rejects an unusable label-only Tier 2 artifact; only one remains a likely stale-selection candidate. Projection rows do not persist `artifact_id` or copied `source_sha256`, so exact identity remains a control gap.

## Other measured results

- `cds_documents=4,071`, `cds_artifacts=24,802`, `school_browser_rows=558`, `cds_fields=262,537`, `ipeds_facts=4,424,512`, `archive_queue=17,044`.
- The attempt ledger has 4,795/4,795 terminal attempts: p50 866 ms, p95 32.06 s, max 1,321.5 s, and 111 timeouts (2.315%).
- The deterministic byte-confirmed PDF sample completed 100/100 with zero artifact-SHA mismatch and zero detected-year mismatch where both years were observable. Two document-level source hashes differ from the latest artifact bytes while artifact hashes match.
- All 4,071 current source objects were attempted. 4,056 head probes succeeded; 15 returned explicit HTTP errors. Among accessible objects: 3,610 PDF, 389 ZIP, 56 HTML, one other; zero leading-junk PDF and zero HTML markers first appearing after byte 512 within 4 KiB. All ZIPs were fully sniffed: 370 XLSX and 19 DOCX, with 28 stale declared formats but zero SHA mismatch or probe error. The byte sniffer heals these labels; no silent loss was demonstrated.
- The synthesized 2023–24 schema currently has only three selected artifacts. Their union hits 691/1,053 schema IDs and contains 27 keys outside the schema; 362 zero-hit fields cannot be retired from a sample of three.
- The endowment slice contains 39,918 facts across five releases and six fields. It preserves 8,425 unlabeled negative numerics and has zero labeled negative numerics, consistent with the projector contract. Draw-rate eligibility is 6,645/6,653 reporter-years; the eight exclusions are three accounting mismatches and five nonpositive beginnings.
- Current FY2024 Scorecard reconciliation passes: 1,085/1,085 reporting entities (1,066 direct plus 19/19 consolidated), 97.222% population coverage, and 5/5 fixtures. This is a new run against the declared current input, not the inherited 99.907% narrative baseline.
- Tier 6 has five canonical artifacts across four documents, all producer version 0.1.0 and all without source-SHA provenance. Current rows therefore do not block a SHA-known redrain, but once a SHA-tagged row exists, a cleaner-only change can be skipped unless Tier 6’s version also changes.

## Unfinished gates

- F2: manually reviewed OCR precision/hallucination ground truth.
- C3: concurrent enqueue invariant on an isolated local/test database.
- D3: full all-IPEDS loaded-but-unserved institution inventory; the executed population is FY2020–FY2024 endowment reporters.
- A1/F1: section-specific visual recall and corpus-derived cleaner near-miss labels.
- A4/D1: selected artifact identity on projection rows and auditable IPEDS cache refresh timestamps.

These gates are explicit in the matrix; none is represented as executed by implication.

## Reproduction

From the repository root with a local `.env` containing the read-only service credentials:

```bash
python3 tools/data_quality/run_data_integrity_audit.py \
  --output scratch/data-integrity-audit/live-readonly.json \
  --pagination-output scratch/data-integrity-audit/pagination.json

deno run --allow-env --allow-net --allow-read \
  --allow-write=scratch/data-integrity-audit \
  tools/data_quality/reprobe_resolver_cohort.ts \
  --output scratch/data-integrity-audit/n-reprobe.json

python3 tools/data_quality/probe_source_corpus.py \
  --output scratch/data-integrity-audit/source-corpus.json

python3 tools/data_quality/audit_schema_alignment.py \
  --output scratch/data-integrity-audit/schema-2023-24-alignment.json

python3 tools/data_quality/audit_tier6_version_contract.py \
  --output scratch/data-integrity-audit/tier6-version-contract.json

python3 tools/ipeds/reconcile_endowment_scorecard.py \
  .context/scorecard-directory-refresh-03232026/Most-Recent-Cohorts-Institution.csv \
  --min-year 2020 --max-year 2024 --threshold 0.99 \
  --out scratch/data-integrity-audit/scorecard-reconciliation.json
```

The manifest records source/input/query/result hashes. Evidence files are summaries sufficient to review every conclusion without committing credentials, authorization headers, response bodies, institutional source bytes, or the 100 MB Scorecard input.
