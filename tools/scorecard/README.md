# Scorecard pipeline

Scripts that populate `scorecard_summary` — a curated 43-column subset of
the federal [College Scorecard](https://collegescorecard.ed.gov/data/) —
and keep it joined to the CDS archive via IPEDS UNITID.

Design rationale, field selection, and the list of deliberately-excluded
Scorecard fields live in
[`docs/research/scorecard-summary-table-v2-plan.md`](../../docs/research/scorecard-summary-table-v2-plan.md).

## Files

- [`backfill_ipeds_ids.py`](./backfill_ipeds_ids.py) — one-shot fill of
  `cds_documents.ipeds_id` for rows inserted before the
  `20260420170000_ipeds_id.sql` migration shipped. New rows get
  `ipeds_id` automatically via the archive edge functions.
- [`refresh_summary.py`](./refresh_summary.py) — annual upsert of
  `scorecard_summary` from the Scorecard Most-Recent Institution CSV.

## First-time setup (once)

1. Apply the three Phase A–C migrations in order:

   ```bash
   supabase db push
   # Or paste each file into the Supabase SQL editor:
   #   20260420170000_ipeds_id.sql
   #   20260420170100_scorecard_summary.sql
   #   20260420170200_cds_scorecard_view.sql
   ```

2. Backfill `ipeds_id` for pre-existing `cds_documents` rows:

   ```bash
   # Preview the SQL
   python tools/scorecard/backfill_ipeds_ids.py > /tmp/backfill.sql
   head /tmp/backfill.sql

   # Option A — apply via supabase-py service-role client
   python tools/scorecard/backfill_ipeds_ids.py --apply

   # Option B — paste /tmp/backfill.sql into the Supabase SQL editor
   ```

3. Download the Scorecard CSV and load it:

   ```bash
   # Grab the current bulk download from https://collegescorecard.ed.gov/data/
   # The filename in the zip is something like
   # Most-Recent-Cohorts-Institution.csv
   unzip ~/Downloads/Most-Recent-Cohorts.zip -d /tmp/scorecard

   # Dry run — parse + print a sample row
   python tools/scorecard/refresh_summary.py \
     --csv /tmp/scorecard/Most-Recent-Cohorts-Institution.csv \
     --data-year 2022-23

   # Apply — full 6K-row upsert, takes ~2-3 minutes
   python tools/scorecard/refresh_summary.py \
     --csv /tmp/scorecard/Most-Recent-Cohorts-Institution.csv \
     --data-year 2022-23 \
     --apply

   # Or, only load the ~2,400 schools referenced in cds_documents:
   python tools/scorecard/refresh_summary.py \
     --csv /tmp/scorecard/Most-Recent-Cohorts-Institution.csv \
     --data-year 2022-23 --apply --only-cds
   ```

## Annual refresh (once per year)

Scorecard releases a new Most-Recent-Cohorts bundle each fall. Rerun
step 3 above with the new CSV and updated `--data-year`. Upserts are
keyed on `ipeds_id`, so the refresh is idempotent; schools that drop
out of Scorecard keep their last known row until manually deleted.

## Checking the data

```bash
# Highest 10-year median earnings among CDS-archived schools
curl 'https://api.collegedata.fyi/rest/v1/cds_scorecard?select=school_name,earnings_10yr_median,graduation_rate_6yr,avg_net_price&earnings_10yr_median=not.is.null&order=earnings_10yr_median.desc&limit=25' \
  -H "apikey: $ANON_KEY" -H "Authorization: Bearer $ANON_KEY"

# Net price by income bracket for one school
curl 'https://api.collegedata.fyi/rest/v1/cds_scorecard?school_id=eq.harvard&select=school_name,net_price_0_30k,net_price_30k_48k,net_price_48k_75k,net_price_75k_110k,net_price_110k_plus' \
  -H "apikey: $ANON_KEY" -H "Authorization: Bearer $ANON_KEY"
```

## Requirements

```bash
pip install pandas supabase python-dotenv pyyaml
```

`.env` at repo root:

```
SUPABASE_URL=https://isduwmygvmdozhpvzaix.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...   # for --apply paths; never check in
```
