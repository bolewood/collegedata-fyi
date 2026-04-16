# Common Data Set vs. College Scorecard: Schema Comparison

> **Purpose.** This document maps the overlap and differences between the
> Common Data Set (CDS) and the U.S. Department of Education's
> [College Scorecard](https://collegescorecard.ed.gov/data/api-documentation/)
> so that downstream consumers of collegedata.fyi can understand what each
> dataset uniquely provides and where a join between the two creates the most
> complete picture of a U.S. college.
>
> **Versions compared.**
> - CDS: 2025-26 canonical schema (1,105 fields) as published by the
>   [Common Data Set Initiative](https://commondataset.org/)
> - College Scorecard: March 2026 data dictionary (3,439 institution-level
>   fields + 178 field-of-study fields), API v1
>
> **Last updated.** 2026-04-16

---

## 1. What each dataset is

| | Common Data Set (CDS) | College Scorecard |
|---|---|---|
| **Publisher** | CDS Initiative (consortium of College Board, Peterson's, U.S. News) | U.S. Department of Education |
| **Primary purpose** | Standardized self-report template that colleges complete voluntarily for guidebook publishers | Federal consumer-information tool for prospective students comparing costs, outcomes, and debt |
| **Data collection** | Each institution fills out a single annual survey (Sections A-J); responses are self-reported | Aggregated from five federal administrative systems (see below) |
| **Unit of analysis** | One document per institution per year | One record per institution (with nested per-program records at CIP-4 level) |
| **Coverage** | ~2,000 four-year institutions (voluntary; participation varies) | 6,322 Title IV institutions (mandatory reporting through IPEDS; earnings/debt from administrative records) |
| **Update cadence** | Annual (published by each school on its own schedule, typically fall) | Annual bulk release + rolling API updates; data dictionary last updated March 2026 |
| **Schema governance** | CDS Initiative publishes an official Excel template each year; schools fill it in | ED publishes a data dictionary (XLSX); schema evolves across releases |
| **Machine readability** | Varies: fillable PDF, flattened PDF, XLSX, DOCX, scanned image | REST API with JSON responses; bulk CSV downloads |
| **Licensing** | No central ToS; each school owns its own responses; derived schemas freely publishable | Public domain (federal government work) |

### College Scorecard data sources

| Source | Approx. fields | Covers |
|---|---|---|
| IPEDS | 869 | School characteristics, admissions, enrollment, demographics, costs, retention, completion, programs |
| NSLDS | 2,208 | Loan debt, repayment, Pell status, completion outcomes by demographics |
| Treasury/IRS | 204 | Post-enrollment earnings (1-11 years after entry/completion) |
| FSA | 11 | Default rates, operating status, heightened cash monitoring |
| OPE | 6 | Minority-serving institution designations |
| ACS | 2 | Household poverty rate, unemployment near campus |

---

## 2. Domain-by-domain comparison

Each row below covers a topical domain. "CDS section" references the
CDS template letter; "Scorecard category" references the API namespace.

### 2.1 Institutional identity and classification

| Dimension | CDS (Section A, 63 fields) | Scorecard (`school`, 181 fields) |
|---|---|---|
| Name, address, URL | Yes | Yes |
| IPEDS Unit ID | Not in template (joinable via external crosswalk) | Primary key (`id` = UNITID) |
| OPE ID | No | Yes (6-digit and 8-digit) |
| Institutional control | Public / private nonprofit / for-profit | Same, plus PEPS ownership variant |
| Carnegie classification | No | Yes (basic, undergrad, size-setting) |
| Religious affiliation | No | Yes (coded) |
| Calendar system | Yes (semester, quarter, trimester, 4-1-4, etc.) | No |
| Degrees offered | Checkboxes (certificate through doctoral) | `degrees_awarded.predominant`, `degrees_awarded.highest` |
| Minority-serving flags | No | Yes (HBCU, HSI, tribal, AANIPI, ANNH, NANT, PBI) |
| Accreditation | No | Yes (accreditor name and code) |
| Endowment | No | Yes (begin/end of year) |
| Faculty salary (institutional avg) | No | Yes |

**Key takeaway.** Scorecard is the authoritative institutional-identity
dataset with federal IDs, Carnegie codes, and MSI flags. CDS adds
calendar system and a richer degree-offerings checklist. The two join
cleanly on IPEDS UNITID (which collegedata.fyi already carries in
`schools.yaml`).

### 2.2 Admissions

| Dimension | CDS (Section C, 278 fields) | Scorecard (`admissions`, 32 fields) |
|---|---|---|
| Applications received | Yes (by gender, FT/PT) | **No** (only the rate) |
| Applicants admitted | Yes (by gender, FT/PT) | **No** |
| Admitted students enrolled | Yes (by gender, FT/PT) | **No** |
| Admission rate | Derivable from counts | Yes (`admission_rate.overall`) |
| Yield rate | Derivable from counts | **No** |
| Early Decision applicants/admits | Yes | **No** |
| Early Action applicants/admits | Yes | **No** |
| Waitlist offered/accepted/admitted | Yes | **No** |
| SAT score ranges (25th/75th) | Yes (reading, math, writing) | Yes (reading, math, writing + midpoints) |
| ACT score ranges (25th/75th) | Yes (composite, English, math, writing) | Yes (same) |
| High school GPA distribution | Yes (ranges: 4.0, 3.75-3.99, etc.) | **No** |
| High school class rank | Yes (top 10%, 25%, 50%) | **No** |
| Basis for selection (importance ratings) | Yes (17 factors rated very important / important / considered / not considered) | **No** |
| Test-optional policy | Yes | Yes (coded integer) |
| Application fee, fee waiver | Yes | **No** |
| Application deadlines | Yes (regular, early decision, early action) | **No** |
| Transfer admission funnel | Yes (Section D, 79 fields) | **No** |

**Key takeaway.** CDS is dramatically richer for admissions. It provides
the raw funnel counts (applied/admitted/enrolled), yield, ED/EA data,
waitlist stats, GPA distributions, class rank, and the qualitative
"basis for selection" rubric. Scorecard reduces all of this to a single
admission rate and test score ranges. **This is one of the highest-value
areas for CDS data and a primary reason collegedata.fyi exists.**

### 2.3 Enrollment and student demographics

| Dimension | CDS (Section B, 204 fields) | Scorecard (`student`, 131 fields) |
|---|---|---|
| Headcount by gender x load | Yes (FT/PT x M/F/Unknown x UG/grad) | Yes (less granular) |
| Total enrollment | Yes | Yes (`size`, `enrollment.all`) |
| Race/ethnicity breakdown | Yes (9 categories) | Yes (9 categories + legacy variants) |
| Age at entry | No | Yes (mean, share over 23) |
| Family income | No | Yes (mean, median, quintile shares, by dependency) |
| First-generation status | No | Yes (share, parents' education level) |
| Veteran status | No | Yes |
| Part-time share | Derivable | Yes |
| Non-degree-seeking enrollment | Yes | Yes |
| Graduate enrollment | Yes | Yes |
| Student-to-faculty ratio | Yes (Section I) | Yes |
| Faculty demographics | No | Yes (gender, race/ethnicity) |
| Home ZIP demographics | No | Yes (poverty rate, education level, race composition) |

**Key takeaway.** Both provide enrollment counts and race/ethnicity. CDS
offers gender x load x cohort cross-tabs that Scorecard does not.
Scorecard adds socioeconomic dimensions (income, first-gen, age,
veteran status, home-ZIP context) that CDS does not collect at all.

### 2.4 Retention and graduation

| Dimension | CDS (Section B, ~50 fields) | Scorecard (`completion`, 1,367 fields; `student.retention_rate`) |
|---|---|---|
| First-year retention rate | Yes (FT and PT) | Yes (FT and PT, 4-year and <4-year) |
| 4-year graduation rate | Yes | Yes |
| 6-year graduation rate | Yes | Yes (plus 8-year) |
| Graduation by race/ethnicity | No | Yes (9 categories x multiple time horizons) |
| Graduation by Pell status | No | Yes |
| Graduation by loan status | No | Yes |
| Transfer-out rate | No | Yes |
| Still-enrolled rate (at 4/6/8 yr) | No | Yes |
| Outcome measures (award/transfer/enrolled/neither) | No | Yes (4yr, 6yr, 8yr) |

**Key takeaway.** Scorecard's completion data is vastly more granular,
with 1,367 fields covering every combination of time horizon, demographic
group, and outcome type. CDS provides headline retention and graduation
rates only. This is Scorecard's second-largest category and one of its
core strengths.

### 2.5 Cost and tuition

| Dimension | CDS (Section G, 46 fields) | Scorecard (`cost`, 85 fields) |
|---|---|---|
| Tuition (in-state / out-of-state) | Yes | Yes |
| Required fees | Yes (separate line) | Bundled with tuition |
| Room and board | Yes (on-campus, off-campus) | Yes |
| Books and supplies | Yes | Yes |
| Other expenses | Yes (on-campus, off-campus, with family) | Yes |
| Per-credit-hour charges | Yes | No |
| Tuition guarantee/freeze policy | Yes | No |
| Average net price | No | Yes (overall + by 5 income brackets) |
| Net price by income bracket | No | Yes (public/private x 5 brackets) |
| Program-year tuition (non-traditional) | No | Yes |

**Key takeaway.** CDS publishes sticker prices with more granularity
(per-credit charges, fee breakdowns, tuition policies). Scorecard adds
the critical **net price by income bracket**, which is not available in
CDS and is arguably the most consumer-relevant cost metric.

### 2.6 Financial aid

| Dimension | CDS (Section H, 164 fields) | Scorecard (`aid`, 111 fields) |
|---|---|---|
| Need-based grant aid (by source) | Yes (federal, state, institutional, external) | No (aggregate only) |
| Non-need-based aid | Yes (merit, athletic, ROTC, tuition waivers) | No |
| Average aid award amount | Yes (by type) | No |
| Number of students receiving aid | Yes (by type and source) | No |
| Federal loan rate | Yes (derivable) | Yes (overall + FT first-time + pooled) |
| Pell grant rate | Yes (derivable) | Yes |
| Median debt at graduation | No | Yes (overall + by income/Pell/gender/first-gen) |
| Cumulative debt percentiles | No | Yes (10th, 25th, 75th, 90th) |
| Parent PLUS loans | No | Yes (median, payment amounts) |
| Monthly payment estimates | No | Yes |
| Aid methodology (federal vs. institutional) | Yes | No |
| Financial aid deadlines/forms | Yes | No |
| Institutional need fully met (% of students) | Yes | No |
| Average % of need met | Yes | No |

**Key takeaway.** CDS provides granular aid-packaging detail: what
sources of aid, how much from each, how many students receive each type,
and whether need is fully met. Scorecard provides **debt outcomes** that
CDS cannot: median debt, percentile distributions, monthly payments, and
breakdowns by demographics. The two are strongly complementary here.

### 2.7 Earnings after enrollment

| Dimension | CDS | Scorecard (`earnings`, 185 fields) |
|---|---|---|
| Post-enrollment earnings | **Not collected** | Yes: median and mean at 6, 7, 8, 9, 10, 11 years after entry; 1, 3, 4, 5 years after completion |
| Earnings by gender | No | Yes |
| Earnings by dependency/income | No | Yes |
| Earnings percentile distribution | No | Yes (10th, 25th, 75th, 90th) |
| Comparison to HS-only earnings | No | Yes |
| Program-level earnings (CIP-4) | No | Yes (1yr, 4yr, 5yr after completion) |

**Key takeaway.** Earnings data is **entirely unique to Scorecard**
(sourced from IRS tax records). CDS does not collect any outcomes data.
This is the single most important reason to join the two datasets.

### 2.8 Loan repayment

| Dimension | CDS | Scorecard (`repayment`, 1,094 fields) |
|---|---|---|
| Repayment rates at 1/3/5/7yr | No | Yes (by demographics) |
| Borrower-based repayment (1-20yr) | No | Yes |
| Default rates (2yr, 3yr) | No | Yes |
| Repayment status breakdown | No | Yes (default, delinquent, forbearance, deferment, etc.) |

**Key takeaway.** Repayment is **entirely unique to Scorecard** (1,094
fields from NSLDS). CDS does not track post-graduation financial
outcomes.

### 2.9 Academic programs

| Dimension | CDS (Section J, 120 fields; Section E, 34 fields) | Scorecard (`academics`, 247 fields; `programs.cip_4_digit`, 178 fields/program) |
|---|---|---|
| Degrees by CIP-2 code | Yes (40 codes x 3 degree levels) | Yes (38 codes, percentage of awards) |
| Program availability by degree level | No | Yes (7 levels x 38 fields) |
| Program-level debt | No | Yes (Stafford + PLUS, by demographics) |
| Program-level earnings | No | Yes (1yr, 4yr, 5yr post-completion) |
| Program-level repayment | No | Yes (1-4yr borrower-based) |
| Special study options | Yes (study abroad, co-op, distance learning, honors, etc.) | No |
| Required coursework | Yes (foreign language, history, math, etc.) | No |
| Distance education flag | No | Yes (per program) |

**Key takeaway.** Both report degrees conferred by discipline. CDS adds
special study options and required coursework. Scorecard adds the
**program-level outcomes nexus** (earnings + debt + repayment per CIP-4
code) that makes field-of-study comparisons possible.

### 2.10 Student life and campus

| Dimension | CDS (Section F, 58 fields) | Scorecard |
|---|---|---|
| Housing capacity | Yes | No |
| On-campus residence requirement | Yes | No |
| Student organizations, activities | Yes | No |
| ROTC (Army, Navy, Air Force) | Yes | No |
| Locale (urban/suburban/rural) | No | Yes (coded) |
| Degree of urbanization | No | Yes |
| Region | No | Yes |

**Key takeaway.** Campus-life data is **unique to CDS**. Scorecard
provides geographic classification but no campus-experience detail.

### 2.11 Faculty and class size

| Dimension | CDS (Section I, 49 fields) | Scorecard |
|---|---|---|
| Faculty count by FT/PT x degree | Yes | No |
| Class size distribution (% in bands) | Yes | No |
| Student-to-faculty ratio | Yes | Yes |
| Full-time faculty rate | No | Yes |
| Faculty salary (institutional avg) | No | Yes |
| Instructional expenditure/FTE | No | Yes |
| Tuition revenue/FTE | No | Yes |

**Key takeaway.** CDS provides class-size distributions and faculty
composition detail. Scorecard provides financial efficiency metrics
(salary, expenditure per FTE).

---

## 3. Coverage and reliability

| Dimension | CDS | Scorecard |
|---|---|---|
| **Institutions covered** | ~2,000 (voluntary, predominantly 4-year) | 6,322 (all Title IV, including 2-year and for-profit) |
| **Reporting mechanism** | Self-reported by each institution | Administrative records (IPEDS mandatory; NSLDS/IRS/FSA automatic) |
| **Verification** | None (honor system) | Federal data quality controls; some suppression for small cells |
| **Consistency** | Varies; some institutions skip questions or interpret them differently | Standardized definitions enforced across all reporters |
| **Timeliness** | Varies by school; some publish months late | Annual release on a fixed schedule |
| **Granularity risk** | Single institution, single year; no suppression | Small-cell suppression (privacy); some fields null for small schools |

---

## 4. The join: IPEDS UNITID

The natural join key between CDS and Scorecard is the **IPEDS Unit ID**
(UNITID), a six-digit identifier assigned to every Title IV institution.

- **Scorecard** uses UNITID as its primary key (`id` field).
- **CDS** does not include UNITID in the template, but collegedata.fyi's
  `schools.yaml` corpus already carries UNITID for every school (sourced
  from the IPEDS HD file). The `school_id` slug in `cds_documents` maps
  to UNITID via `schools.yaml`.
- **Join rate**: We expect >95% of CDS-participating institutions to have
  a clean UNITID match, since the CDS corpus is drawn from IPEDS-listed
  schools.

---

## 5. Summary: what is unique to each dataset

### Unique to CDS (not available in Scorecard)

| Domain | Examples |
|---|---|
| **Admission funnel counts** | Total applications, admits, enrolled (by gender, FT/PT) |
| **Yield rate** | Derivable from funnel counts |
| **Early Decision / Early Action** | Applicants, admits, deadlines |
| **Waitlist** | Offered, accepted, admitted from waitlist |
| **GPA distribution** | % in each GPA band (4.0, 3.75-3.99, etc.) |
| **Class rank** | % in top 10th, quarter, half |
| **Basis for selection** | 17 factors rated on importance scale |
| **Application logistics** | Fees, fee waivers, deadlines, forms accepted |
| **Transfer admission detail** | Applied, admitted, enrolled; credit policies |
| **Aid packaging detail** | Source-by-source breakdown, % of need met, merit vs. need |
| **Per-credit-hour charges** | Useful for part-time cost estimation |
| **Tuition policies** | Guarantees, freezes, prepaid plans |
| **Campus life** | Housing capacity, residence requirements, organizations, activities |
| **Class size distribution** | % of sections in each size band |
| **Faculty composition** | FT/PT counts by terminal degree |
| **Required coursework** | HS units required/recommended by subject |
| **Special study options** | Study abroad, co-op, dual enrollment, honors, etc. |

### Unique to Scorecard (not available in CDS)

| Domain | Examples |
|---|---|
| **Post-enrollment earnings** | Median/mean at 6-11 years after entry; program-level earnings |
| **Loan repayment outcomes** | Repayment rates at 1-20 years; default, delinquency, forbearance |
| **Debt distributions** | Median debt by income/Pell/gender/first-gen; percentiles |
| **Net price by income** | Average net price across 5 income brackets |
| **Program-level outcomes** | Earnings + debt + repayment per CIP-4 code and credential level |
| **Completion by demographics** | Graduation rates by race, Pell, loan status at 4/6/8 years |
| **Transfer-out and still-enrolled rates** | Tracked as outcome categories |
| **Socioeconomic student profile** | Family income, first-gen share, age, veteran status |
| **Institutional finance** | Endowment, instructional expenditure/FTE, tuition revenue/FTE |
| **Federal identifiers and flags** | UNITID, OPE ID, Carnegie codes, MSI flags, accreditation |
| **Geographic context** | Home-ZIP demographics, locale classification |
| **For-profit and 2-year coverage** | 6,322 institutions vs. ~2,000 |

### Overlapping domains (both datasets, different angles)

| Domain | CDS angle | Scorecard angle |
|---|---|---|
| **Admission selectivity** | Raw funnel counts, GPA, class rank, selection criteria | Single admission rate, test scores |
| **Test scores** | SAT/ACT percentile ranges | SAT/ACT percentile ranges (nearly identical) |
| **Enrollment** | Gender x load x cohort cross-tabs | Total size + demographic shares |
| **Race/ethnicity** | 9 categories (headcounts) | 9 categories (shares) + legacy variants |
| **Retention** | FT/PT headline rates | FT/PT rates + pooled + suppressed variants |
| **Graduation rate** | Headline 4yr/6yr | 4yr/6yr/8yr x demographics x Pell x loans |
| **Tuition** | Sticker price with fee detail | Sticker price (bundled) + net price |
| **Financial aid** | Packaging detail (sources, amounts, % met) | Aggregate rates + debt outcomes |
| **Programs/degrees** | Degrees by CIP-2 x degree level | Degrees by CIP-2 + program-level outcomes at CIP-4 |
| **Student-to-faculty ratio** | Yes | Yes |

---

## 6. Field count comparison

| | CDS | Scorecard (institution) | Scorecard (per program) |
|---|---|---|---|
| **Total fields** | 1,105 | 3,439 | 178 per CIP-4 program |
| **Admissions** | 278 | 32 | -- |
| **Enrollment / students** | 204 | 131 | -- |
| **Cost / expenses** | 46 | 85 | -- |
| **Financial aid** | 164 | 111 | -- |
| **Completion / graduation** | ~50 | 1,367 | -- |
| **Repayment** | 0 | 1,094 | ~28 |
| **Earnings** | 0 | 185 | ~66 |
| **Academics / programs** | 154 | 247 | -- |
| **Institutional identity** | 63 | 181 | -- |
| **Student life / campus** | 58 | 0 | -- |
| **Faculty / class size** | 49 | ~6 | -- |

---

## 7. Implications for collegedata.fyi

1. **The CDS fills Scorecard's blind spots in admissions.** Scorecard
   has 32 admissions fields; CDS has 278. Application counts, yield,
   ED/EA, waitlist, GPA, class rank, and selection criteria are available
   nowhere else in a structured, cross-institutional format. This is the
   core value proposition of collegedata.fyi.

2. **Scorecard fills CDS's blind spots in outcomes.** Earnings,
   repayment, and debt data (2,473 fields combined) do not exist in CDS.
   A joined dataset would give consumers the full picture: *how hard is
   it to get in* (CDS) + *what happens after* (Scorecard).

3. **The join is straightforward.** UNITID is the shared key. We already
   carry it in `schools.yaml`. A `cds_manifest` + Scorecard join would
   produce the most complete open dataset on U.S. colleges available
   anywhere.

4. **Scorecard is freely queryable today.** Its REST API is public,
   well-documented, and rate-limited at 1,000 req/hr. Bulk CSV downloads
   are also available. No extraction pipeline is needed -- just API calls
   or CSV imports.

5. **CDS requires extraction; Scorecard does not.** The entire
   engineering challenge of collegedata.fyi (tiered PDF extraction,
   archival, schema normalization) exists because CDS data is locked in
   PDFs. Scorecard data is already in a clean API. The hard problem is
   the CDS side.

6. **Coverage gap.** Scorecard covers 6,322 institutions; CDS covers
   ~2,000. The joined dataset will be limited to the CDS-participating
   subset, but that subset includes the vast majority of selective
   four-year institutions where admissions data matters most.

---

## Appendix: Data source reference

- **CDS template**: https://commondataset.org/ (2025-26 Excel template,
  answer sheet tab)
- **College Scorecard API**: https://collegescorecard.ed.gov/data/api-documentation/
- **Scorecard data dictionary**: https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx
- **Scorecard institution documentation**: https://collegescorecard.ed.gov/files/InstitutionDataDocumentation.pdf
- **IPEDS**: https://nces.ed.gov/ipeds/ (source for both CDS corpus and
  Scorecard institution data)
- **collegedata.fyi schema**: `schemas/cds_schema_2025_26.json` (1,105
  fields, programmatically extracted)
