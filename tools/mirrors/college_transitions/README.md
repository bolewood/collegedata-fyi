# college_transitions mirror

Re-hosts CDS PDFs (and a handful of XLSX files) on Google Drive for 333 US colleges across 2019-20 through 2024-25. Curated by College Transitions, a college admissions consulting firm. Not a live IR directory: when a school revises their CDS after CT's capture date, CT's copy becomes the older version.

Source page: https://www.collegetransitions.com/dataverse/common-data-set-repository/

## What's in the directory

| File | Purpose |
|---|---|
| `fetch.py` | Playwright-driven refresh. Loads the CT page, pulls the FooTable's in-memory row data (all rows, not just the paginated slice), matches each school against schools.yaml, writes `catalog.json`. |
| `catalog.json` | Committed snapshot of the CT repository at the last fetch. Diffs against this in PRs show what CT added since last time. |
| `ingest.py` | Reads `catalog.json`, queries `cds_documents` for existing coverage, POSTs gap-filling URLs to `archive-process?POST force_urls` with `source_provenance='mirror_college_transitions'`. Idempotent. |
| `spot_check.py` | Diagnostic: pick a sample of (school, year) pairs, download both CT's and our copy, compare sha256. |
| `content_diff.py` | Diagnostic: for one mismatched pair, download both and diff per-page text so you can see whether the bytes differ cosmetically (re-save) or structurally (data revision). |

## Re-run the mirror

```bash
# Setup (one-time)
pip install playwright pyyaml supabase python-dotenv requests
playwright install chromium

# 1. Refresh the catalog
python tools/mirrors/college_transitions/fetch.py

# 2. Review the diff
git diff tools/mirrors/college_transitions/catalog.json

# 3. Dry-run the ingest to see what gaps exist
python tools/mirrors/college_transitions/ingest.py --dry-run

# 4. Ingest (calls force_urls for each gap)
python tools/mirrors/college_transitions/ingest.py --concurrency 4

# 5. Commit the updated catalog
git add tools/mirrors/college_transitions/catalog.json
git commit -m "mirrors(college-transitions): refresh $(date +%Y-%m-%d)"
```

## Policy

**Never overwrite existing rows.** The ingest script checks `cds_documents` for each (school_id, cds_year) — or (school_id, detected_year) — and skips if we already have it, regardless of provenance. The school's own publication always wins.

**Never call refresh.** Mirror ingest uses `force_urls` which routes to `archiveManualUrls` which takes the Branch A (fresh insert) path. Branch C (new sha for existing row) is reserved for the resolver's school-direct pipeline, where a refresh semantically upgrades provenance to `school_direct`.

**Tag with provenance.** Every row ingested here carries `source_provenance = 'mirror_college_transitions'`. Consumers who want authoritative data filter on `= 'school_direct'`; consumers who want maximum coverage include all.

## Caveats from the 2026-04-19 spot-check

A 15-pair spot-check against our existing `school_direct` archive surfaced three findings:

- **2 bit-identical** — same file exactly (Nevada-Reno 2024-25, Bucknell 2018-19).
- **7 we don't have** — real coverage gaps the mirror fills (7/15 of the sample).
- **3 mismatches** — both sources have the year, different bytes. Content-diffed UNC Asheville 2021-22 and confirmed the difference is a genuine data revision: the school republished with corrected graduation rates ~7 months after the first publication. CT has the first-published version; we have the revised version. Policy ("school wins") puts the right version in our primary and leaves CT's earlier snapshot out of the archive.

See [`spot-check-results.json`](ct-spot-check-results.json) for the raw sample.

## Unmatched schools

`catalog.json` has an `unmatched` array for CT schools whose name didn't fuzzy-match a slug in `schools.yaml`. The typical fix is to add a lowercased alias to `ALIAS_MAP` in `fetch.py` and re-run. Examples where this came up: "College of William and Mary" → "william & mary", "CUNY Brooklyn College" → "brooklyn college", "Rensselaer Polytechnic Institute" → "rpi".

If a CT school isn't in our corpus at all, it stays in `unmatched` and is skipped by ingest. Add the school to `tools/finder/schools.yaml` first if you want to include it.
