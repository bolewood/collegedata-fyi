# data_quality

Audit and reporting tools that run against the live archive to answer "how are we doing?" questions. None of these own the data. They read `cds_documents`, `cds_artifacts`, `archive_queue`, `school_hosting_observations`, and the `cds_manifest` / `latest_school_hosting` views, and either print a report or write a small flag back.

Some tools also produce CSV batches for human contributors (the kids worklist pipeline) or drive the edge-function operator endpoints (`force_resolve_missing`).

## What's in the directory

| File | Purpose |
|---|---|
| `audit_manifest.py` | Post-ingest data-quality audit. Reads canonical artifacts, flags documents with <5 populated fields as `blank_template` or `low_coverage`, optionally writes `data_quality_flag` back to `cds_documents`. Frontend surfaces this as an amber badge. |
| `completeness_report.py` | Top-to-bottom funnel pivot per `cds_year`: corpus → discovered → archived → extracted → high_quality. Default window = past 5 CDS years. Output: terminal table + optional JSON. Use this to size the coverage picture before scoping any discovery work. |
| `active_schools_missing_recent.py` | Per-school CSV of which active schools lack docs for which recent years. Feeds the kids worklist; also useful standalone for operator spot-checks. |
| `kids_worklist.py` | Generates batched Google-Sheets-ready CSVs (50 schools per batch, sorted highest-yield first) of active schools missing recent years. Queries `latest_school_hosting` to skip auth-walled schools, prefers `browse_url` over `discovery_seed_url`, and surfaces a `hosting_note` so contributors know what to expect (Box folder, JS-rendered, "needs landing page", etc.). Applies `tools/finder/school_overrides.yaml` on top of DB observations. Output: `tools/data_quality/kids-worklist/batch-NNN.csv`. |
| `force_resolve_missing.py` | Parallel caller of the `archive-process?force_school=<id>` operator endpoint. `--all` runs against every active school with a `discovery_seed_url`; default targets schools missing recent years. Captures structured `ProbeOutcome` categories into JSONL for analysis. Used post-deploy to populate `school_hosting_observations` without waiting for the monthly cron. |

## Typical usage

```bash
cd /path/to/collegedata-fyi

# "How are we doing?" — the completeness pivot
tools/extraction_worker/.venv/bin/python tools/data_quality/completeness_report.py

# "Which CDS files look broken?" — audit canonical artifacts
tools/extraction_worker/.venv/bin/python tools/data_quality/audit_manifest.py --write

# "Generate a kids worklist" — regenerates 16 batch CSVs
tools/extraction_worker/.venv/bin/python tools/data_quality/kids_worklist.py

# "Drain the whole active corpus through the resolver right now"
tools/extraction_worker/.venv/bin/python tools/data_quality/force_resolve_missing.py \
    --all --concurrency 4 --timeout 180 \
    --log tools/data_quality/full-drain-$(date +%Y%m%d).jsonl
```

All tools read `.env` at the repo root for `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. They share the `tools/extraction_worker/.venv/` venv (`supabase`, `python-dotenv`, `pyyaml` are the only deps beyond stdlib).

## Output files (uncommitted)

`tools/data_quality/` accumulates JSON/JSONL/CSV output files from the above tools. These are deliberately left out of git — they're point-in-time snapshots and would churn noisily. Examples:

- `audit-report-YYYYMMDD.json` — output of `audit_manifest.py`
- `completeness-YYYYMMDD.json` — output of `completeness_report.py`
- `full-drain-YYYYMMDD.jsonl` — output of `force_resolve_missing.py --all`
- `active-schools-missing-recent.csv` — output of `active_schools_missing_recent.py`
- `kids-worklist/` — output of `kids_worklist.py`

Add a new line to `.gitignore` if a new tool starts emitting something noisy.
