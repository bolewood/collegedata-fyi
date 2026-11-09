# data_quality

Audit and reporting tools that run against the live archive to answer "how are we doing?" questions. None of these own the data. They read `cds_documents`, `cds_artifacts`, `archive_queue`, `school_hosting_observations`, and the `cds_manifest` / `latest_school_hosting` views, and either print a report or write a small flag back.

Some tools also produce CSV batches for human contributors (the kids worklist pipeline) or drive the edge-function operator endpoints (`force_resolve_missing`).

## What's in the directory

| File | Purpose |
|---|---|
| `audit_manifest.py` | Post-ingest data-quality audit. Reads canonical artifacts, flags documents with <5 populated fields as `blank_template` or `low_coverage`, optionally writes `data_quality_flag` back to `cds_documents`. Frontend surfaces this as an amber badge. |
| `audit_visual_ocr_candidates.py` | Finds Tier 4 PDFs with C1/C9 labels present but key admissions/test-score values absent. Use it to queue managed local re-drains through the visual-OCR supplement and to confirm which documents were repaired by `tier4_docling` 0.3.5+. |
| `completeness_report.py` | Top-to-bottom funnel pivot per `cds_year`: corpus → discovered → archived → extracted → high_quality. Default window = past 5 CDS years. Output: terminal table + optional JSON. Use this to size the coverage picture before scoping any discovery work. |
| `active_schools_missing_recent.py` | Per-school CSV of which active schools lack docs for which recent years. Feeds the kids worklist; also useful standalone for operator spot-checks. |
| `kids_worklist.py` | Generates batched Google-Sheets-ready CSVs (50 schools per batch, sorted highest-yield first) of active schools missing recent years. Queries `latest_school_hosting` to skip auth-walled schools, prefers `browse_url` over `discovery_seed_url`, and surfaces a `hosting_note` so contributors know what to expect (Box folder, JS-rendered, "needs landing page", etc.). Applies `tools/finder/school_overrides.yaml` on top of DB observations. Output: `tools/data_quality/kids-worklist/batch-NNN.csv` (gitignored; the number of batches depends on the data). |
| `run_data_integrity_audit.py` | Read-only, database-backed data-integrity audit using raw PostgREST range requests with stable ordering and captured `Content-Range` headers. Pair with `reprobe_resolver_cohort.ts` (Deno, read-only resolver reprobe of a fixed cohort). |
| `audit_schema_alignment.py` | Read-only check of selected extraction keys against a declared CDS schema. |
| `audit_reclean_candidates.py` | Finds Tier 4 artifacts whose stored Docling markdown has an answerable subsection that the canonical values are missing, i.e. candidates for a deterministic re-clean. |
| `audit_b1_gender_2024.py` | Compares stored `tier4_docling` B1 gender values against a fresh `clean()` of the artifact markdown (use after B1 mapping fixes). |
| `audit_tier6_version_contract.py` | Read-only measure of Tier 6 producer/idempotency exposure. |
| `cleanup_bad_html_sources.py` | Audits and quarantines archived HTML sources that are not CDS documents (login walls, WAF challenges, error pages). |
| `probe_source_corpus.py` | Read-only measure of source-format sniff risk plus a byte/year check on a deterministic 100-PDF sample. |
| `published_years.py` | Shared paginated "published year" coverage queries used by the kids worklist and the priority-100 scorer. |
| `force_resolve_missing.py` | Parallel caller of the `archive-process?force_school=<id>` operator endpoint. `--all` runs against every active school with a `discovery_seed_url`; default targets schools missing recent years. Captures structured `ProbeOutcome` categories into JSONL for analysis. Used post-deploy to populate `school_hosting_observations` without waiting for the monthly cron. |

## Typical usage

```bash
cd /path/to/collegedata-fyi
mkdir -p scratch/data_quality

# "How are we doing?" — the completeness pivot
tools/extraction_worker/.venv/bin/python tools/data_quality/completeness_report.py

# "Which CDS files look broken?" — audit canonical artifacts
tools/extraction_worker/.venv/bin/python tools/data_quality/audit_manifest.py --write

# "Which extracted PDFs likely need visual OCR?" — emit a re-drain review CSV
tools/extraction_worker/.venv/bin/python tools/data_quality/audit_visual_ocr_candidates.py \
    --csv-output scratch/data_quality/visual-ocr-candidates.csv

# "Generate a kids worklist" — regenerates the batch CSVs
tools/extraction_worker/.venv/bin/python tools/data_quality/kids_worklist.py

# "Drain the whole active corpus through the resolver right now"
tools/extraction_worker/.venv/bin/python tools/data_quality/force_resolve_missing.py \
    --all --concurrency 4 --timeout 180 \
    --log scratch/data_quality/full-drain-$(date +%Y%m%d).jsonl
```

All tools read `.env` at the repo root for `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. They share the `tools/extraction_worker/.venv/` venv (`supabase`, `python-dotenv`, `pyyaml` are the only deps beyond stdlib).

## Output files (uncommitted)

These tools emit JSON/JSONL/CSV point-in-time snapshots. Write them to `scratch/data_quality/` (gitignored, per the repo convention for one-off run artifacts). Older runs wrote into `tools/data_quality/`, where `*.json`, `*.jsonl`, `*.csv` and `kids-worklist/` are also gitignored. Examples:

- `audit-report-YYYYMMDD.json` — output of `audit_manifest.py`
- `visual-ocr-candidates.csv` — output of `audit_visual_ocr_candidates.py`
- `completeness-YYYYMMDD.json` — output of `completeness_report.py`
- `full-drain-YYYYMMDD.jsonl` — output of `force_resolve_missing.py --all`
- `active-schools-missing-recent.csv` — output of `active_schools_missing_recent.py`
- `kids-worklist/` — output of `kids_worklist.py`

Add a new line to `.gitignore` if a new tool starts emitting something noisy.
