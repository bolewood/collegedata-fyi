# V2 Plan: Scorecard Summary Table

> **Status.** Shipped + first load complete 2026-04-20. `scorecard_summary`
> holds 6,322 rows (every Title-IV institution) from the March 2026
> Scorecard release (data vintage 2022-23). The `cds_scorecard` view is
> live at `https://api.collegedata.fyi/rest/v1/cds_scorecard`. See
> [`tools/scorecard/README.md`](../../tools/scorecard/README.md) for the
> operator runbook and the current state.
>
> **Deltas vs. this plan as written:**
> - Final column count is 41, not 46. Three Pell/non-Pell debt and
>   completion fields named in the original plan have either been
>   renamed or removed from the Scorecard data dictionary between when
>   this plan was written (2026-04-16) and the March 2026 release that
>   actually shipped. `GRAD_DEBT_MDN_PELL` was renamed to `PELL_DEBT_MDN`
>   (kept as `median_debt_pell`); `GRAD_DEBT_MDN_NOPELL` and
>   `C150_4_NONPELL` were removed entirely (no replacement, columns
>   dropped from `scorecard_summary` and `cds_scorecard`). Migration
>   `20260420180000_scorecard_pell_remap.sql` covers the adaptation. The
>   running schema-drift event log lives in
>   [`tools/scorecard/README.md`](../../tools/scorecard/README.md).
> - The pipeline is described as the project's "sixth pipeline" in the
>   original phrasing; it shipped as the eighth (the architecture grew
>   between plan and ship).
>
> **Last updated.** 2026-04-20

---

## Motivation

The College Scorecard has 3,439 institution-level fields. Most consumers
of collegedata.fyi will only care about 30-50 of them — the ones that
answer "what happens after admission?" in a way that complements the CDS
admissions data we already have. Rather than mirroring the entire
Scorecard (which is already freely available via its own API and bulk
CSVs), we host a curated **summary table** of the highest-value outcome
fields, pre-joined on IPEDS UNITID, and exposed through the same
PostgREST API.

### Design principles

1. **Complement, don't duplicate.** Only include Scorecard fields that
   CDS does not cover. If CDS already has it (e.g., SAT ranges), skip it.
2. **Outcome-focused.** Prioritize earnings, debt, repayment, net price,
   and completion — the fields that answer "is this school worth it?"
3. **Slim.** Target 40-50 columns, not 3,400. One row per UNITID.
4. **Attributable.** Every value traces back to a Scorecard vintage
   (data year) so consumers know the freshness.
5. **Low maintenance.** One bulk refresh per year after Scorecard's
   annual release, not a live sync.

---

## Proposed schema

### Step 1: Add `ipeds_id` to `cds_documents`

```sql
-- Migration: add ipeds_id to cds_documents and expose in cds_manifest
ALTER TABLE public.cds_documents
  ADD COLUMN ipeds_id text;

COMMENT ON COLUMN public.cds_documents.ipeds_id IS
  'IPEDS Unit ID (UNITID). Six-digit NCES identifier. '
  'Sourced from schools.yaml at archive time. Foreign key into '
  'scorecard_summary and the federal College Scorecard API.';

CREATE INDEX idx_cds_documents_ipeds_id ON public.cds_documents (ipeds_id);
```

Update `cds_manifest` to expose `ipeds_id`:

```sql
CREATE OR REPLACE VIEW public.cds_manifest AS
  SELECT
    d.id AS document_id,
    d.school_id,
    d.school_name,
    d.ipeds_id,                -- NEW
    d.sub_institutional,
    d.cds_year,
    d.source_url,
    d.source_format,
    d.participation_status,
    d.discovered_at,
    d.last_verified_at,
    d.removed_at,
    d.extraction_status,
    (SELECT a.id FROM public.cds_artifacts a
     WHERE a.document_id = d.id AND a.kind = 'canonical'
     ORDER BY a.created_at DESC LIMIT 1
    ) AS latest_canonical_artifact_id,
    (SELECT a.storage_path FROM public.cds_artifacts a
     WHERE a.document_id = d.id AND a.kind = 'source'
     ORDER BY a.created_at DESC LIMIT 1
    ) AS source_storage_path,
    d.detected_year,
    COALESCE(d.detected_year, d.cds_year) AS canonical_year
  FROM public.cds_documents d;
```

Backfill from `schools.yaml`:

```sql
-- Run once after deploying the migration
-- (generated from schools.yaml by a one-off Python script)
UPDATE public.cds_documents SET ipeds_id = '166027' WHERE school_id = 'harvard';
UPDATE public.cds_documents SET ipeds_id = '115409' WHERE school_id = 'harvey-mudd';
-- ... one row per school
```

### Step 2: Create `scorecard_summary` table

```sql
CREATE TABLE public.scorecard_summary (
  -- ── Identity ─────────────────────────────────────────────────────
  ipeds_id              text PRIMARY KEY,
  school_name           text NOT NULL,
  scorecard_data_year   text NOT NULL,      -- e.g., "2023-24"
  refreshed_at          timestamptz NOT NULL DEFAULT now(),

  -- ── Earnings (Treasury/IRS) ──────────────────────────────────────
  -- Post-enrollment earnings at various time horizons
  earnings_6yr_median   int,    -- 6 years after entry
  earnings_8yr_median   int,    -- 8 years after entry
  earnings_10yr_median  int,    -- 10 years after entry
  earnings_10yr_p25     int,    -- 25th percentile at 10yr
  earnings_10yr_p75     int,    -- 75th percentile at 10yr

  -- ── Debt (NSLDS) ────────────────────────────────────────────────
  median_debt_completers        int,    -- at graduation
  median_debt_noncompleters     int,    -- for those who didn't finish
  median_debt_monthly_payment   numeric(8,2),
  cumulative_debt_p90           int,    -- 90th percentile
  median_debt_pell              int,    -- Pell recipients
  median_debt_non_pell          int,    -- non-Pell

  -- ── Net price (IPEDS) ───────────────────────────────────────────
  -- Average net price (sticker minus grants) by income bracket
  avg_net_price                 int,
  net_price_0_30k               int,    -- family income $0-$30,000
  net_price_30k_48k             int,    -- $30,001-$48,000
  net_price_48k_75k             int,    -- $48,001-$75,000
  net_price_75k_110k            int,    -- $75,001-$110,000
  net_price_110k_plus           int,    -- $110,001+

  -- ── Completion (IPEDS + NSLDS) ──────────────────────────────────
  graduation_rate_4yr           numeric(5,4),  -- 100% time
  graduation_rate_6yr           numeric(5,4),  -- 150% time (headline)
  graduation_rate_8yr           numeric(5,4),  -- 200% time
  grad_rate_pell                numeric(5,4),  -- Pell recipients, 150% time
  grad_rate_non_pell            numeric(5,4),  -- non-Pell, 150% time
  transfer_out_rate             numeric(5,4),

  -- ── Repayment (NSLDS + FSA) ─────────────────────────────────────
  repayment_rate_3yr            numeric(5,4),  -- % making progress at 3yr
  default_rate_3yr              numeric(5,4),  -- 3-year cohort default rate

  -- ── Student profile (IPEDS + NSLDS) ─────────────────────────────
  -- Socioeconomic dimensions CDS does not collect
  enrollment                    int,
  pell_grant_rate               numeric(5,4),
  federal_loan_rate             numeric(5,4),
  first_generation_share        numeric(5,4),
  median_family_income          int,
  female_share                  numeric(5,4),
  retention_rate_ft             numeric(5,4),

  -- ── Institutional context (IPEDS + OPE) ─────────────────────────
  -- Classification fields useful for filtering/grouping
  carnegie_basic                int,
  locale                        int,
  historically_black            boolean,
  predominantly_black           boolean,
  hispanic_serving              boolean,
  endowment_end                 bigint,
  instructional_expenditure_fte int,
  faculty_salary_avg            int
);

COMMENT ON TABLE public.scorecard_summary IS
  'Curated subset of College Scorecard fields that complement CDS data. '
  'One row per IPEDS UNITID. Refreshed annually after the Scorecard '
  'bulk release. Join to cds_manifest via ipeds_id.';

-- Public read access (same pattern as cds_documents)
ALTER TABLE public.scorecard_summary ENABLE ROW LEVEL SECURITY;
CREATE POLICY scorecard_summary_public_read ON public.scorecard_summary
  FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON public.scorecard_summary TO anon, authenticated;
```

**Total: 46 columns** (1 PK + 2 metadata + 43 data fields).

### Step 3: Create the joined view

```sql
CREATE VIEW public.cds_scorecard AS
SELECT
    m.document_id,
    m.school_id,
    m.school_name,
    m.ipeds_id,
    m.canonical_year        AS cds_year,
    m.source_format,
    m.extraction_status,
    m.latest_canonical_artifact_id,
    m.source_storage_path,

    -- Scorecard outcomes
    sc.scorecard_data_year,
    sc.earnings_10yr_median,
    sc.earnings_10yr_p25,
    sc.earnings_10yr_p75,
    sc.median_debt_completers,
    sc.median_debt_monthly_payment,
    sc.avg_net_price,
    sc.net_price_0_30k,
    sc.net_price_30k_48k,
    sc.net_price_48k_75k,
    sc.net_price_75k_110k,
    sc.net_price_110k_plus,
    sc.graduation_rate_6yr,
    sc.grad_rate_pell,
    sc.grad_rate_non_pell,
    sc.repayment_rate_3yr,
    sc.default_rate_3yr,
    sc.pell_grant_rate,
    sc.federal_loan_rate,
    sc.first_generation_share,
    sc.median_family_income,
    sc.retention_rate_ft,
    sc.endowment_end,
    sc.instructional_expenditure_fte
FROM public.cds_manifest m
LEFT JOIN public.scorecard_summary sc ON sc.ipeds_id = m.ipeds_id;

COMMENT ON VIEW public.cds_scorecard IS
  'CDS manifest joined with Scorecard summary. One row per CDS document '
  'with outcome data appended. NULL scorecard columns mean the school '
  'has no Scorecard match (rare for CDS-participating institutions).';

GRANT SELECT ON public.cds_scorecard TO anon, authenticated;
```

This gives API consumers a single endpoint:

```bash
# "Show me schools where I can get in and what happens after"
curl 'https://api.collegedata.fyi/rest/v1/cds_scorecard?select=school_name,cds_year,extraction_status,earnings_10yr_median,median_debt_completers,avg_net_price,graduation_rate_6yr&extraction_status=eq.extracted&order=earnings_10yr_median.desc' \
  -H 'apikey: YOUR_ANON_KEY'
```

---

## Refresh pipeline

### Annual bulk refresh (once per year, ~30 minutes)

```
1. Download Scorecard "Most Recent Institution-Level Data" CSV
   from https://collegescorecard.ed.gov/data/

2. Run refresh script:
   python tools/scorecard/refresh_summary.py \
     --csv ~/Downloads/Most-Recent-Cohorts-Institution.csv \
     --dry-run

3. Review diff (new schools, changed values, dropped schools)

4. Apply:
   python tools/scorecard/refresh_summary.py \
     --csv ~/Downloads/Most-Recent-Cohorts-Institution.csv \
     --apply
```

The refresh script:
- Reads the Scorecard CSV (one row per UNITID)
- Selects only the ~43 columns we care about
- Maps Scorecard column names to our schema
- Upserts into `scorecard_summary` via `supabase-py`
- Logs: rows inserted, rows updated, rows with null earnings (expected
  for small/new schools)

### Column mapping (Scorecard CSV → our schema)

| Our column | Scorecard CSV column | Notes |
|---|---|---|
| `ipeds_id` | `UNITID` | Cast to text |
| `school_name` | `INSTNM` | |
| `earnings_6yr_median` | `MD_EARN_WNE_P6` | |
| `earnings_8yr_median` | `MD_EARN_WNE_P8` | |
| `earnings_10yr_median` | `MD_EARN_WNE_P10` | |
| `earnings_10yr_p25` | `PCT25_EARN_WNE_P10` | |
| `earnings_10yr_p75` | `PCT75_EARN_WNE_P10` | |
| `median_debt_completers` | `GRAD_DEBT_MDN` | |
| `median_debt_noncompleters` | `WDRAW_DEBT_MDN` | |
| `median_debt_monthly_payment` | `GRAD_DEBT_MDN10YR` | |
| `cumulative_debt_p90` | `CUML_DEBT_P90` | |
| `median_debt_pell` | `GRAD_DEBT_MDN_PELL` | |
| `median_debt_non_pell` | `GRAD_DEBT_MDN_NOPELL` | |
| `avg_net_price` | `NPT4_PUB` or `NPT4_PRIV` | Pick based on `CONTROL` |
| `net_price_0_30k` | `NPT41_PUB` or `NPT41_PRIV` | |
| `net_price_30k_48k` | `NPT42_PUB` or `NPT42_PRIV` | |
| `net_price_48k_75k` | `NPT43_PUB` or `NPT43_PRIV` | |
| `net_price_75k_110k` | `NPT44_PUB` or `NPT44_PRIV` | |
| `net_price_110k_plus` | `NPT45_PUB` or `NPT45_PRIV` | |
| `graduation_rate_4yr` | `C100_4` | |
| `graduation_rate_6yr` | `C150_4` | Headline rate |
| `graduation_rate_8yr` | `C200_4` | |
| `grad_rate_pell` | `C150_4_PELL` | |
| `grad_rate_non_pell` | `C150_4_NONPELL` | |
| `transfer_out_rate` | `TRANS_4` | |
| `repayment_rate_3yr` | `RPY_3YR_RT` | |
| `default_rate_3yr` | `CDR3` | |
| `enrollment` | `UGDS` | Degree-seeking UG |
| `pell_grant_rate` | `PCTPELL` | |
| `federal_loan_rate` | `PCTFLOAN` | |
| `first_generation_share` | `PAR_ED_PCT_1STGEN` | |
| `median_family_income` | `MD_FAMINC` | |
| `female_share` | `FEMALE` | |
| `retention_rate_ft` | `RET_FT4` | |
| `carnegie_basic` | `CCBASIC` | |
| `locale` | `LOCALE` | |
| `historically_black` | `HBCU` | |
| `predominantly_black` | `PBI` | |
| `hispanic_serving` | `HSI` | |
| `endowment_end` | `ENDOWEND` | |
| `instructional_expenditure_fte` | `INEXPFTE` | |
| `faculty_salary_avg` | `AVGFACSAL` | |

> **Note.** Scorecard CSV column names are from the March 2026 data
> dictionary. Verify against the current `CollegeScorecardDataDictionary.xlsx`
> before building the refresh script, as ED occasionally renames columns.

---

## Implementation phases

### Phase A: `ipeds_id` on `cds_documents` (prerequisite, ~30 min)

- [ ] Write migration adding `ipeds_id` column + index
- [ ] Update `cds_manifest` view to include `ipeds_id`
- [ ] Backfill `ipeds_id` from `schools.yaml` (one-off script or SQL)
- [ ] Update `archive-process` edge function to write `ipeds_id` at
      archive time (read from `schools.yaml` entry)
- [ ] Deploy migration + edge function update

### Phase B: `scorecard_summary` table (core, ~2 hours)

- [ ] Write migration creating table + RLS + grants
- [ ] Write `tools/scorecard/refresh_summary.py` (CSV → upsert)
- [ ] Download latest Scorecard CSV, run refresh, verify row counts
- [ ] Deploy migration

### Phase C: `cds_scorecard` view (consumer-facing, ~30 min)

- [ ] Write migration creating the joined view
- [ ] Deploy and verify via PostgREST
- [ ] Update API documentation / README

### Phase D: Documentation (~30 min)

- [ ] Update `docs/ARCHITECTURE.md` with sixth pipeline description
- [ ] Update `docs/research/scorecard-join-recipe.md` to reference the
      native endpoint (replacing the manual join workaround)
- [ ] Add Scorecard attribution note per ED's data use requirements

---

## What we deliberately exclude

These Scorecard fields are available but not worth hosting:

| Category | Why excluded |
|---|---|
| **Admissions fields** (32) | CDS already has these with far more granularity (278 fields) |
| **Per-program earnings/debt** (178 fields/program) | Too large to denormalize; consumers who need CIP-4 data should query Scorecard directly |
| **Repayment status breakdown** (1,094 fields) | Niche; 3yr repayment rate + default rate cover 90% of consumer questions |
| **Completion by race/ethnicity** (~200 fields) | Important but would triple our column count; defer to V3 or a separate `scorecard_completion_detail` table |
| **Historical year data** | We host `latest` only; historical queries go to Scorecard's year-specific CSVs |

---

## Open questions

1. **Should `scorecard_summary` cover all 6,322 Scorecard schools or
   only the ~2,000 in our CDS corpus?** Hosting all 6,322 costs almost
   nothing (one table, ~6K rows) and lets consumers query outcomes even
   for schools we don't have CDS data for. Recommendation: include all;
   the `cds_scorecard` view uses LEFT JOIN so CDS-only consumers are
   unaffected.

2. **Scorecard attribution requirements.** ED's data use policy does not
   require attribution but does require that the data not be
   misrepresented. We should include a `scorecard_data_year` column and
   a note in the API docs clarifying the vintage and source.

3. **Refresh trigger.** Annual manual refresh is fine for V2. If the
   project scales, a GitHub Actions cron that checks for new Scorecard
   releases and auto-refreshes would be a V3 improvement.

---

## See also

- [CDS vs. College Scorecard schema comparison](cds-vs-college-scorecard.md)
- [Join recipe (manual, pre-V2)](scorecard-join-recipe.md)
- [Backlog: Join CDS with Scorecard](../backlog.md) (strategic context)
- College Scorecard [bulk data downloads](https://collegescorecard.ed.gov/data/)
- College Scorecard [data dictionary](https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx)
