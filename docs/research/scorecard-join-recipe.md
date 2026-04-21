# How to Join collegedata.fyi with College Scorecard

> **Audience.** Developers and researchers who want to combine CDS
> admissions data from collegedata.fyi with federal outcomes data from the
> College Scorecard. No account or API key is needed for collegedata.fyi;
> Scorecard requires a free API key from [api.data.gov](https://api.data.gov/signup/).
>
> **Now mostly historical.** As of 2026-04-20 the join is built into the
> public API: `GET /rest/v1/cds_scorecard` returns one row per archived
> CDS document with the curated Scorecard outcome slice attached
> (earnings, debt, net price by income, completion, retention). Use the
> built-in view for the common case; this manual recipe is still useful
> when you need Scorecard fields outside the 41-column curated subset
> (per-program earnings, full repayment-status breakdown,
> race-stratified completion). See
> [`tools/scorecard/README.md`](../../tools/scorecard/README.md) for the
> curated subset and the data vintage currently loaded.
>
> **Last updated.** 2026-04-20

---

## The join key: IPEDS UNITID

Both datasets identify institutions via the IPEDS Unit ID (UNITID), a
six-digit code assigned by the National Center for Education Statistics
to every Title IV institution.

| Dataset | Where the UNITID lives |
|---|---|
| **College Scorecard** | Primary key: the `id` field on every record |
| **collegedata.fyi** | `school_id` slug in `cds_manifest` maps to `ipeds_id` in [`schools.yaml`](../../tools/finder/schools.yaml) |

> **Note (April 2026, updated 2026-04-20).** `ipeds_id` is now exposed
> on `cds_manifest` directly — `GET /rest/v1/cds_manifest?select=school_id,ipeds_id`
> works. The manual `schools.yaml` crosswalk shown below remains useful
> if you want the canonical mapping in code (e.g. for client-side joins
> against a Scorecard API call) or for the ~130 `cds_documents` rows
> whose slug variant doesn't yet match a `schools.yaml.id`.

---

## Quick start: curl + jq

### 1. Get a school's CDS data from collegedata.fyi

```bash
# Fetch Harvard's CDS manifest row
curl -s 'https://api.collegedata.fyi/rest/v1/cds_manifest?school_id=eq.harvard' \
  -H 'apikey: YOUR_SUPABASE_ANON_KEY' | jq '.[0]'
```

### 2. Look up the IPEDS ID

From `schools.yaml`, Harvard's `ipeds_id` is `166027`.

Or programmatically:

```bash
# One-liner: extract ipeds_id for a school_id from schools.yaml
# Requires yq (https://github.com/mikefarah/yq)
yq '.schools[] | select(.id == "harvard") | .ipeds_id' \
  tools/finder/schools.yaml
# → "166027"
```

### 3. Fetch the matching Scorecard record

```bash
# Fetch Harvard's Scorecard data (selected fields)
curl -s 'https://api.data.gov/ed/collegescorecard/v1/schools.json?api_key=YOUR_API_KEY&id=166027&fields=id,school.name,latest.admissions.admission_rate.overall,latest.earnings.10_yrs_after_entry.median,latest.cost.avg_net_price.overall,latest.aid.median_debt.completers.overall,latest.student.size,latest.completion.consumer_rate' | jq '.results[0]'
```

### 4. Join them

```bash
#!/usr/bin/env bash
# join-cds-scorecard.sh — join one school's CDS + Scorecard data
# Usage: ./join-cds-scorecard.sh harvard 166027

SCHOOL_ID="${1:?Usage: $0 <school_id> <ipeds_id>}"
IPEDS_ID="${2:?Usage: $0 <school_id> <ipeds_id>}"
ANON_KEY="${SUPABASE_ANON_KEY:?Set SUPABASE_ANON_KEY}"
SC_KEY="${SCORECARD_API_KEY:?Set SCORECARD_API_KEY}"

# Fetch CDS manifest
cds=$(curl -s "https://api.collegedata.fyi/rest/v1/cds_manifest?school_id=eq.${SCHOOL_ID}" \
  -H "apikey: ${ANON_KEY}")

# Fetch Scorecard
scorecard=$(curl -s "https://api.data.gov/ed/collegescorecard/v1/schools.json?api_key=${SC_KEY}&id=${IPEDS_ID}&fields=id,school.name,latest.admissions.admission_rate.overall,latest.earnings.10_yrs_after_entry.median,latest.cost.avg_net_price.overall,latest.aid.median_debt.completers.overall,latest.student.size,latest.completion.consumer_rate")

# Merge with jq
jq -n \
  --argjson cds "$cds" \
  --argjson sc "$scorecard" \
  '{
    school_id: $cds[0].school_id,
    school_name: $cds[0].school_name,
    ipeds_id: $sc.results[0].id,
    cds_year: $cds[0].canonical_year,
    cds: {
      document_id: $cds[0].document_id,
      source_format: $cds[0].source_format,
      extraction_status: $cds[0].extraction_status,
      artifact_id: $cds[0].latest_canonical_artifact_id
    },
    scorecard: {
      admission_rate: $sc.results[0]["latest.admissions.admission_rate.overall"],
      median_earnings_10yr: $sc.results[0]["latest.earnings.10_yrs_after_entry.median"],
      avg_net_price: $sc.results[0]["latest.cost.avg_net_price.overall"],
      median_debt: $sc.results[0]["latest.aid.median_debt.completers.overall"],
      enrollment: $sc.results[0]["latest.student.size"],
      graduation_rate: $sc.results[0]["latest.completion.consumer_rate"]
    }
  }'
```

---

## Python example

```python
"""Join collegedata.fyi CDS data with College Scorecard for a batch of schools."""

import os
import requests
import yaml

# ── Config ──────────────────────────────────────────────────────────────
CDS_API = "https://api.collegedata.fyi/rest/v1"
SC_API = "https://api.data.gov/ed/collegescorecard/v1/schools.json"
ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SC_KEY = os.environ["SCORECARD_API_KEY"]

# Scorecard fields to fetch (customize as needed)
SC_FIELDS = ",".join([
    "id",
    "school.name",
    "latest.admissions.admission_rate.overall",
    "latest.earnings.10_yrs_after_entry.median",
    "latest.earnings.10_yrs_after_entry.mean_earnings",
    "latest.cost.avg_net_price.overall",
    "latest.cost.tuition.in_state",
    "latest.cost.tuition.out_of_state",
    "latest.aid.median_debt.completers.overall",
    "latest.aid.cumulative_debt.90th_percentile",
    "latest.student.size",
    "latest.student.demographics.female_share",
    "latest.completion.consumer_rate",
    "latest.student.retention_rate.four_year.full_time",
])

# ── Load the IPEDS crosswalk from schools.yaml ──────────────────────────
with open("tools/finder/schools.yaml") as f:
    schools = yaml.safe_load(f)["schools"]
crosswalk = {s["id"]: s["ipeds_id"] for s in schools if s.get("ipeds_id")}

# ── Fetch CDS manifest ──────────────────────────────────────────────────
cds_rows = requests.get(
    f"{CDS_API}/cds_manifest",
    headers={"apikey": ANON_KEY},
    params={"extraction_status": "eq.extracted", "select": "*"},
).json()

# ── Join with Scorecard ─────────────────────────────────────────────────
for row in cds_rows:
    ipeds_id = crosswalk.get(row["school_id"])
    if not ipeds_id:
        continue

    sc = requests.get(SC_API, params={
        "api_key": SC_KEY,
        "id": ipeds_id,
        "fields": SC_FIELDS,
    }).json()

    if not sc.get("results"):
        continue

    sc_data = sc["results"][0]
    print(f"\n{'='*60}")
    print(f"{row['school_name']} (IPEDS {ipeds_id})")
    print(f"  CDS year:            {row['canonical_year']}")
    print(f"  Admission rate:      {sc_data.get('latest.admissions.admission_rate.overall', 'N/A')}")
    print(f"  Median earnings @10y: ${sc_data.get('latest.earnings.10_yrs_after_entry.median', 'N/A'):,}")
    print(f"  Avg net price:       ${sc_data.get('latest.cost.avg_net_price.overall', 'N/A'):,}")
    print(f"  Median debt:         ${sc_data.get('latest.aid.median_debt.completers.overall', 'N/A'):,}")
    print(f"  Graduation rate:     {sc_data.get('latest.completion.consumer_rate', 'N/A')}")
    print(f"  Retention rate (FT): {sc_data.get('latest.student.retention_rate.four_year.full_time', 'N/A')}")
```

---

## SQL example (if you have both datasets in Postgres)

If you import Scorecard CSVs into a local Postgres alongside the
collegedata.fyi schema, the join is a single line:

```sql
-- Join CDS manifest with a local Scorecard import
SELECT
    m.school_id,
    m.school_name,
    m.canonical_year,
    m.source_format,
    m.extraction_status,
    sc.adm_rate           AS admission_rate,
    sc.md_earn_wne_p10    AS median_earnings_10yr,
    sc.npt4_pub           AS net_price_public,
    sc.npt4_priv          AS net_price_private,
    sc.md_comp_orig       AS median_debt,
    sc.c150_4             AS graduation_rate_150pct,
    sc.ugds               AS enrollment
FROM cds_manifest m
JOIN scorecard_latest sc
    ON sc.unitid = (
        -- Until ipeds_id is on cds_manifest, use a crosswalk table
        SELECT ipeds_id FROM school_crosswalk
        WHERE school_id = m.school_id
    )
WHERE m.extraction_status = 'extracted';
```

> **Scorecard bulk CSVs** are available at
> https://collegescorecard.ed.gov/data/ — download "Most Recent
> Institution-Level Data" for the `latest` snapshot or individual year
> files for historical data.

---

## Field mapping cheat sheet

High-value fields that exist in both datasets but use different names:

| Concept | collegedata.fyi (CDS field) | Scorecard API field |
|---|---|---|
| Admission rate | Derivable from `C.101`-`C.106` (applied/admitted counts) | `latest.admissions.admission_rate.overall` |
| SAT Math 75th | `C.901` | `latest.admissions.sat_scores.75th_percentile.math` |
| SAT Reading 75th | `C.902` | `latest.admissions.sat_scores.75th_percentile.critical_reading` |
| ACT Composite 75th | `C.911` | `latest.admissions.act_scores.75th_percentile.cumulative` |
| Total enrollment | `B.113` (computed) | `latest.student.size` |
| Retention rate (FT) | `B.174` | `latest.student.retention_rate.four_year.full_time` |
| In-state tuition | `G.001`-`G.006` | `latest.cost.tuition.in_state` |
| Out-of-state tuition | `G.007`-`G.012` | `latest.cost.tuition.out_of_state` |
| Room and board | `G.101`-`G.102` | `latest.cost.roomboard.oncampus` |
| Student-to-faculty ratio | `I.101` | `latest.student.demographics.student_faculty_ratio` |

---

## Gotchas

1. **Year alignment.** CDS data is labeled by academic year (e.g.,
   "2025-26" means fall 2025 enrollment). Scorecard's `latest` object
   pulls from the most recent IPEDS survey, which may lag by 1-2 years.
   Check `Scorecard.metadata.latest_year` to confirm the vintage.

2. **Admission rate discrepancy.** CDS reports raw application /
   admission / enrollment counts that let you compute the rate yourself.
   Scorecard's `admission_rate.overall` comes from IPEDS and may differ
   slightly due to timing, cohort definition, or rounding.

3. **Multi-campus schools.** Some schools (e.g., Columbia) publish
   separate CDS files for sub-institutions. Scorecard has one UNITID per
   campus. The join is clean for single-CDS schools; for sub-institutional
   variants, decide whether to match on the parent UNITID or skip.

4. **Coverage asymmetry.** collegedata.fyi covers ~2,000 schools (the
   CDS-participating subset). Scorecard covers 6,322. The joined dataset
   is limited to the CDS intersection.

5. **Rate limits.** Scorecard API allows 1,000 requests/hour per IP.
   For bulk joins, use the CSV download instead of per-school API calls.

---

## See also

- [CDS vs. College Scorecard schema comparison](cds-vs-college-scorecard.md)
- [V2 Scorecard summary table plan](scorecard-summary-table-v2-plan.md)
- College Scorecard [API documentation](https://collegescorecard.ed.gov/data/api-documentation/)
- College Scorecard [data dictionary (XLSX)](https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx)
