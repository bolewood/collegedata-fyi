# api_usage

Privacy-preserving API usage capture (PRD 032) and the public `/usage` page's data (PRD 033). Reads Supabase gateway logs, classifies requests, and writes aggregates. It never stores raw IP addresses or full user-agent strings: client rows carry a salted hash and a product token only.

| File | Purpose |
|---|---|
| `ingest_gateway_logs.py` | Entry point. Pulls grouped log rows, classifies and aggregates them, and writes `api_gateway_*` tables plus daily unique downloads (`api_usage_downloads_daily`). |
| `logs_api.py` | Supabase Management API logs client. The endpoint allows 10 queries per minute per token, truncates at 1,000 rows, and keeps 90 days; the client paces calls, backs off on 429, and pages with LIMIT/OFFSET. |
| `queries.py` | ClickHouse SQL for the logs endpoint. Every query orders by all group keys so paging is deterministic. |
| `classify.py` | Pure functions that classify log groups into `internal_pipeline`, `friendly_api_upstream`, `first_party_site`, `browser_unattributed` and `third_party`. Returns no IPs, full user agents, or query strings. |
| `aggregate.py` | Turns grouped rows into the JSON payloads for `api_usage_replace_window()` and `api_usage_replace_downloads_day()`. |
| `publish.py` | Publishes ready days and complete months into `usage_public_daily` and `usage_public_school_months` through `api_usage_publish_pending()`, then scans with `usage_public_violations()` and fails if a privacy rule is broken. |
| `test_*.py` | Unit tests, including `test_pipeline_identity.py`: pipeline tools that reach public surfaces must send a `collegedata-pipeline` User-Agent so they are not counted as third-party traffic. |

## Running

The `ops-api-usage-ingest.yml` workflow runs at :20 and :50 every hour and on dispatch. It needs the `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_LOGS_TOKEN` secrets. Locally:

```bash
# Hourly mode (default): reprocess whole UTC hours since the last good window
python tools/api_usage/ingest_gateway_logs.py --mode hourly --dry-run --out-json scratch/api_usage/report.json

# Backfill N whole days (gateway logs are kept for 90 days), or recount downloads only
python tools/api_usage/ingest_gateway_logs.py --mode backfill --days 7
python tools/api_usage/ingest_gateway_logs.py --mode daily --days 3

# Publish ready public rows
python tools/api_usage/publish.py --out-json scratch/api_usage/publish.json
```

`--dry-run` queries and aggregates without writing to the database. The repository is public, so workflow logs and `--out-json` carry counts only. Other flags: `--slice-hours`, `--heartbeat-json`.

Background: [`docs/api-usage-attribution.md`](../../docs/api-usage-attribution.md), [`docs/prd/032-api-usage-capture.md`](../../docs/prd/032-api-usage-capture.md), [`docs/prd/033-public-usage-page.md`](../../docs/prd/033-public-usage-page.md).
