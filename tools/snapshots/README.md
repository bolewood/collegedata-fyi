# snapshots

`build_public_snapshots.mjs` builds a dated copy of the public data files that the site serves under `/snapshots/`.

```bash
# Node 20+; no install needed
COLLEGEDATA_API_BASE=https://www.collegedata.fyi \
COLLEGEDATA_SNAPSHOT_DATE=2026-11-09 \
  node tools/snapshots/build_public_snapshots.mjs
```

It downloads `schools.jsonl`, `school_facts.jsonl`, `sources.jsonl` and `field_dictionary.json` from `<api base>/snapshots/latest/`, writes them with a SHA-256 manifest to `web/public/snapshots/v1/<date>/manifest.json` (the date defaults to today, UTC), and builds `collegedata.duckdb` only if the `duckdb` CLI is installed. Both environment variables are optional.

## What the site serves today

The routes under `web/src/app/snapshots/` and `web/src/app/api/snapshots/route.ts` generate the files on request from the live data and cache them for an hour (`/snapshots/latest/<file>`). The dated URL `/snapshots/v1/<date>/<file>` currently serves the same live data, not a frozen copy, and the DuckDB file is not served. Output from this script is a local build artifact; it is not published anywhere automatically. Truly frozen, dated snapshots would need a separate design.

Related: `web/src/lib/snapshot-data.ts`, the `/api` page, and `llms.txt`.
