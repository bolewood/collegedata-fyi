# PRD 021: IPEDS coverage layer for non-CDS schools

**Status:** In implementation
**Created:** 2026-05-08
**Author:** Anthony + Codex
**Related:** [PRD 010](010-queryable-data-browser.md), [PRD 015](015-institution-directory-and-cds-coverage.md), [PRD 019](019-cds-change-intelligence.md), [PRD 020](020-accessible-cds-table-view.md), [Scorecard join recipe](../research/scorecard-join-recipe.md)

---

## Executive summary

IPEDS should become the federal baseline layer for collegedata.fyi.

It should **not** fully replace the Common Data Set. It can close most of the
coverage gap for directory-scale institution facts, enrollment, admissions,
cost, aid, completions, outcomes, and staffing. It cannot replace the CDS as the
best source for newest-year CDS-specific admissions detail, application-plan
behavior, wait-list detail, some aid-table definitions, or institution-authored
source-document accountability.

The product move is:

1. Keep CDS as the highest-authority source when a school publishes one.
2. Load annual IPEDS bulk files for all Title IV institutions keyed by UNITID.
3. Project a curated, source-labeled IPEDS fact layer into the same public
   surfaces that already use CDS and Scorecard data.
4. Use IPEDS to turn "no public CDS found" from an empty page into a useful,
   honest institutional profile.

This is likely the highest-leverage way to move from a CDS archive covering
hundreds of schools to a college-data product covering thousands.

## Official-source findings

This PRD is based on the official NCES/IPEDS documentation and a live probe of
the NCES data-file surfaces.

Primary references:

- IPEDS overview: https://nces.ed.gov/ipeds/use-the-data/overview-of-ipeds-data
- IPEDS survey components: https://nces.ed.gov/ipeds/survey-components
- IPEDS Access databases: https://nces.ed.gov/ipeds/use-the-data/download-access-database
- IPEDS complete data files / Data Center: https://nces.ed.gov/ipeds/datacenter/Default.aspx?fromIpeds=true&gotoReportId=7
- Component pages:
  - Admissions: https://nces.ed.gov/ipeds/survey-components/6
  - Fall Enrollment: https://nces.ed.gov/ipeds/survey-components/8
  - 12-month Enrollment: https://nces.ed.gov/ipeds/survey-components/5
  - Institutional Characteristics: https://nces.ed.gov/ipeds/survey-components/4
  - Cost: https://nces.ed.gov/ipeds/survey-components/13
  - Student Financial Aid: https://nces.ed.gov/ipeds/survey-components/12
  - Completions: https://nces.ed.gov/ipeds/survey-components/7
  - Graduation Rates: https://nces.ed.gov/ipeds/survey-components/9
  - Outcome Measures: https://nces.ed.gov/ipeds/survey-components/11
  - Human Resources: https://nces.ed.gov/ipeds/survey-components/3

What NCES says IPEDS is:

- A system of interrelated annual surveys run by NCES.
- Submitted by about 6,400 colleges, universities, technical, and vocational
  institutions participating in federal student aid programs.
- Aggregated institution-level data, not student-level records.
- Organized across 13 interrelated survey components and three reporting
  periods.
- Available through online tools, complete CSV data files, dictionaries, and
  annual Microsoft Access bundles with metadata.

Important release semantics:

- Provisional releases have gone through NCES quality control and include
  imputed values for nonresponding institutions.
- Final releases include prior-year institutional revisions and are the most
  up-to-date release for a collection year.
- Official docs describe provisional data as released about one year after
  initial collection and final data about two years after initial collection.
- The current Access page shows `2024-25` as provisional, released March 2026,
  and `2023-24` as final, also released March 2026.
- Operational probe cadence starts 10 months after the latest loaded
  provisional Access release date, so the March 2026 reference begins checking
  for `2025-26` provisional and `2024-25` final in January 2027. The earlier
  check leaves room for NCES to publish faster in future cycles.

Operational finding:

- The NCES Data Center complete-file UI is sessiony, but the download endpoints
  are scriptable after a cookie-initializing request.
- Current CSV endpoint shape observed through the Data Center:

```text
https://nces.ed.gov/ipeds/data-generator?year=2024&tableName=ADM2024&HasRV=0&type=csv
```

- Current dictionary endpoint shape:

```text
https://nces.ed.gov/ipeds/dictionary-generator?year=2024&tableName=ADM2024
```

- Dictionary downloads are zipped Excel workbooks containing sheets such as
  `Varlist`, `Description`, `Frequencies`, `Statistics`, and `Imputation values`.
- Example `ADM2024` dictionary confirms admissions variables for applicants,
  admissions, enrolled students, SAT/ACT score percentiles, and admissions
  considerations. It also shows code labels and imputation flags.

### Input-source decision

Use only official NCES/IPEDS sources for v1, but do **not** parse the Microsoft
Access database in the first implementation. The Access page remains the release
discovery/provenance surface, and the Access ZIP URL is recorded on the release,
but the loader uses:

1. **Official IPEDS Tablesdoc workbook** for table, variable, value-label, and
   imputation metadata.
2. **Official IPEDS complete data / Data Center CSV ZIP downloads** for table
   rows, cached immutably under `scratch/ipeds/`.
3. **No third-party normalized package** as an authoritative input. External
   packages can be used later for comparison only if their transformations,
   cadence, and attribution are reviewed.

This keeps the v1 parser small, auditable, and source-labeled while avoiding
Access-driver/platform complexity.

### Measured starting coverage

Production public counts as of 2026-05-08:

- `institution_directory`: 6,322 rows, all keyed by IPEDS `ipeds_id`.
- `institution_directory WHERE in_scope = true`: 2,924 rows.
- `scorecard_summary`: 6,322 rows.
- `cds_manifest`: 3,999 rows.
- `cds_manifest` rows with `ipeds_id`: 3,840.
- `cds_manifest` rows without `ipeds_id`: 159.

This means the directory backbone is already UNITID-native. The immediate join
risk is not the `institution_directory`; it is the remaining manifest gap,
legacy slug variants, non-Title-IV/non-school rows, and sub-institutional cases
where one CDS row should not inherit a parent-campus federal value without an
explicit mapping.

Before implementation, rerun the same measurement and add a distinct-school
breakdown:

```sql
select count(*) from institution_directory;
select count(*) from institution_directory where in_scope = true;
select count(*) from cds_manifest;
select count(*) from cds_manifest where ipeds_id is not null;
select count(*) from cds_manifest where ipeds_id is null;
select count(distinct school_id) from cds_manifest where ipeds_id is null;
```

### Product-identity risk

Shipping PRD 021 changes the product shape. Today, collegedata.fyi is primarily
"the CDS archive." If most public school pages become federal-baseline-only, the
site risks becoming "an IPEDS viewer with some CDS documents."

That is not a strong enough moat by itself. College Navigator is the official
IPEDS consumer interface, and many commercial sites already package federal
college data.

Baseline-only pages are worth shipping only if they do work those alternatives
do not:

- clearly explain whether a school publishes a public CDS and preserve the
  source when it does;
- reconcile CDS, IPEDS, and Scorecard without hiding provenance;
- expose source labels and imputation/release status better than consumer sites;
- provide queryable/exportable open data and stable URLs;
- show "federal baseline plus school-authored document, when available" rather
  than generic college-marketing copy.

Indexing federal-baseline-only pages should be a separate launch decision. It is
reasonable to noindex those pages until source labels, attribution, and
definition notes are polished.

## Can IPEDS fully supplant CDS?

No. It can supplant a large share of the *facts* families need from CDS, but not
the CDS as a source type.

### Where IPEDS can beat CDS

IPEDS is stronger than CDS for broad coverage:

- It covers the Title IV universe, not just voluntary CDS publishers.
- It has a stable UNITID key, official metadata dictionaries, imputation flags,
  release status, and long historical availability.
- It is machine-readable from the start.
- It has consistent federal definitions across institutions.
- It covers many schools that will never publish a CDS.

IPEDS is also stronger for some analytics:

- Completions by 6-digit CIP code are richer than CDS Section J percentages.
- Outcome Measures include non-first-time and part-time cohorts that CDS
  graduation-rate tables do not fully cover.
- Finance and Human Resources expose institutional operating context beyond CDS.
- 12-month enrollment is better for year-round and nontraditional institutions.

### Where CDS remains better

CDS remains stronger for admissions-product specificity and public-document
accountability:

- **Current-year speed.** CDS files often publish months before equivalent IPEDS
  data becomes public. For 2025-26 admissions and change intelligence, CDS can
  show current institutional behavior while IPEDS remains a lagged federal
  baseline.
- **Admissions strategy detail.** IPEDS has admissions totals, acceptance/yield,
  test scores, and admissions considerations for non-open-admissions schools.
  CDS adds the strategy fields counselors and families actually ask about:
  Early Decision, Early Action, wait-list behavior, deferrals, deadlines,
  notification dates, application fees, fee waivers, class-rank distributions,
  GPA distributions, and school-specific test-policy context.
- **CDS-native C7 semantics.** CDS C7 reports the familiar "Very Important /
  Important / Considered / Not Considered" factor-importance matrix. IPEDS
  admissions consideration codes are valuable but more compliance-oriented and
  should not be treated as a drop-in C7 replacement without a definition note.
- **CDS-native C1 framing.** CDS C1 is the exact publisher-facing
  applicants/admitted/enrolled table, including the row/column framing used by
  schools, counselors, publishers, and institutional research offices. IPEDS ADM
  can cover many of the same totals, but the population, release timing, and
  gender/category treatment need explicit mapping before values are blended.
- **Financial-aid table shape.** IPEDS SFA and Cost tables are strong federal
  aid and net-price sources, but CDS H1/H2/H2A/H6/H7/H8 expose
  institution-authored aid-package, need/non-need, and grant-aid framing that is
  not always definitionally identical to IPEDS.
- **Other CDS-specific context.** CDS also carries school-authored student-life,
  housing, class-size, faculty, academic-offering, transfer, and policy fields
  in the format expected by CDS users. Some have IPEDS analogs; many do not.
- **Public-document provenance.** A CDS is a public document the institution
  chose to publish. That source type matters independently from the extracted
  facts because it supports archive, citation, and accountability use cases.
- **Disclosure-change signal.** CDS lets us detect "the school stopped
  publishing this field" or "the school changed how it reports this table" by
  comparing public documents year over year. IPEDS is standardized, lagged,
  imputed, and revised, so it is less useful for narratives about what a school
  chose to disclose in the current public cycle.

### Product conclusion

IPEDS should **not** be framed as "the new CDS." It should be framed as:

> Federal baseline facts for every Title IV institution, layered with
> institution-published CDS data where available.

That keeps trust high. We do not hide definition drift behind a common-looking
number, and we do not give up the unique value of preserving the original CDS
documents.

## Field-family coverage map

| Product family | IPEDS source | CDS replacement strength | Notes |
| --- | --- | --- | --- |
| Institution identity | HD, IC | Strong | UNITID, name, address, sector, control, calendar, awards, services. |
| Enrollment totals | EF, E12, DRVEF | Strong | Fall and 12-month headcounts, full/part-time, race/ethnicity, gender, level. |
| Retention | EF / DRVEF | Strong | First-time retention and student-to-faculty ratio are available. |
| Admissions totals | ADM, DRVADM | Medium-strong | Applicants, admitted, enrolled, acceptance/yield, test scores for non-open-admissions institutions. Timing lags CDS. |
| Admissions strategy | ADM | Medium | Admissions considerations exist, but not full CDS C7/C21/C22/wait-list semantics. |
| Test scores | ADM | Medium-strong | SAT/ACT percentiles and submit behavior exist where tests are required/considered; definitions must be checked against CDS C9. |
| Costs | IC, CST, DRVCOST | Strong | Tuition, fees, food/housing, cost of attendance, net price support. |
| Financial aid | SFA, CST | Medium-strong | Aid counts/amounts by student category and net-price inputs. Not a perfect CDS H2/H2A replacement. |
| Graduation rates | GR, GR200, DRVGR | Strong | Cohorts by race/gender/Pell and 150%/200% timing. |
| Outcomes for transfer/nontraditional students | OM, DRVOM | Stronger than CDS | Particularly useful for two-year and transfer-heavy institutions. |
| Degrees/majors | Completions, DRVC | Stronger analytically | CIP-coded awards by level/race/gender; different from CDS J presentation. |
| Faculty/staff | HR, DRVHR | Medium-strong | Staff and faculty counts/salaries. Not the same as every CDS class-size/faculty item. |
| Finance | F, DRVF | Additive | Useful institutional-health context, not a CDS replacement. |
| Academic libraries | AL | Additive | Not central to current product surfaces. |

## Product goals

1. Expand useful school-level coverage from CDS-publishing schools to the full
   Title IV institution universe we choose to list.
2. Make every value source-labeled: `CDS`, `IPEDS provisional`, `IPEDS final`,
   `College Scorecard`, or `school fact book`.
3. Preserve CDS-first authority for source-backed admissions/change
   intelligence.
4. Create a stable federal-baseline profile for schools with `no_public_cds_found`.
5. Use IPEDS to power broader comparison, filtering, and time-series analysis.
6. Make definition differences visible enough that we do not accidentally compare
   incompatible facts.

## Non-goals

- No claim that IPEDS and CDS fields are identical unless explicitly mapped.
- No student-level data.
- No scraping of authenticated IPEDS reporting portals.
- No public editing of IPEDS values.
- No attempt to ingest every IPEDS variable in v1.
- No replacement of the CDS archive, finder, or extraction QA work.
- No silent blending of CDS and IPEDS values into one unlabeled number.

## User stories

1. A family searches for a school that does not publish a CDS and still sees
   enrollment, cost, aid, admission, and outcome facts with federal source labels.
2. A counselor filters schools by admit rate, retention, student size, graduation
   rate, and net price across thousands of institutions, not just CDS publishers.
3. A journalist comparing 2025-26 CDS deltas can add IPEDS context without
   confusing a latest CDS cycle with a lagged federal release.
4. An analyst can query a stable table keyed by UNITID, year, field, source
   table, variable, release status, and imputation flag.
5. A maintainer can update the annual IPEDS release without hand-mapping every
   CSV column again.

## Data model

### `ipeds_releases`

One row per NCES collection/release pull.

Fields:

- `id`
- `collection_year` such as `2024-25`
- `data_year` such as `2024`
- `release_type`: `provisional` or `final`
- `release_date`
- `downloaded_at`
- `source_url`
- `source_sha256`
- `notes`

### `ipeds_tables`

One row per IPEDS source table in a release.

Fields:

- `release_id`
- `table_name` such as `ADM2024`, `EF2024A`, `SFA2324`, `DRVADM2024`
- `survey_component`
- `title`
- `data_url`
- `dictionary_url`
- `row_count`
- `source_sha256`
- `loaded_at`

### `ipeds_columns`

Metadata from dictionary workbooks.

Fields:

- `release_id`
- `table_name`
- `var_name`
- `var_title`
- `data_type`
- `format`
- `field_width`
- `long_description`
- `imputation_var`

### `ipeds_value_labels`

Categorical code labels from dictionary `Frequencies`.

Fields:

- `release_id`
- `table_name`
- `var_name`
- `code_value`
- `value_label`

### Raw row storage

Raw rows are for provenance and forensics, not for product filtering. Do not
build browse/search on JSONB extraction at scale.

Use a JSONB landing table for raw table preservation:

```sql
create table ipeds_raw_rows (
  release_id uuid not null references ipeds_releases(id),
  table_name text not null,
  unitid integer not null,
  row_data jsonb not null,
  loaded_at timestamptz not null default now(),
  primary key (release_id, table_name, unitid)
);
```

The authoritative product storage is `ipeds_facts`, not `ipeds_raw_rows`. The
loader should parse wide source rows once and write typed long-form facts with
numeric values, units, source variables, release status, and imputation flags.
That is what makes range filters across thousands of institutions practical.

If later product surfaces need full-table analytical performance beyond
`ipeds_facts`, add typed projection tables for those specific table families.

### `ipeds_facts`

Curated long-form fact table used by public products.

Fields:

- `unitid`
- `institution_id` / `school_id` when mapped
- `collection_year`
- `data_year`
- `field_key`
- `value_numeric`
- `value_text`
- `value_label`
- `unit`
- `cohort`
- `population`
- `source_table`
- `source_variable`
- `source_title`
- `release_type`
- `imputation_flag`
- `quality_flag`
- `definition_alignment`: `direct`, `near`, `context_only`, `not_cds_equivalent`
- `created_at`

This table is the contract. Raw IPEDS data can be wide and weird; public
consumers should not need to understand every IPEDS CSV layout.

### `school_facts_unified`

Public serving view that merges source layers without hiding provenance.

Precedence rules:

1. CDS value wins for CDS-native fields when a current selected primary CDS row
   exists.
2. IPEDS fills absent fields when the mapping is `direct` or `near`.
3. IPEDS supersedes Scorecard for fields whose direct source is an IPEDS survey
   table and where the IPEDS loader carries release/imputation metadata.
4. Scorecard remains the source for consumer-outcome fields that are not fully
   available from IPEDS raw, especially earnings, debt, repayment, and
   borrower-outcome measures.
5. Fact-book or arbitrary-layout extraction can fill only fields with explicit
   source labels and confidence metadata.

The view must expose both:

- a `display_value` for UI cards and filters
- all provenance columns needed to audit where the value came from

## MVP field slice

Start with fields that give maximum coverage and minimum definition risk.

### Phase 1: Federal baseline profile

Tables:

- `HD2024`
- `IC2024`
- `EF2024A`
- `EF2024D`
- `DRVEF2024`
- `COST1_2024`
- `DRVCOST2024`
- `SFA2324`
- `DRVADM2024`
- `ADM2024`
- `DRVGR2024`
- `DRVOM2024`
- `DRVC2024`

Fields:

- school name, city, state, sector, control
- undergraduate enrollment
- graduate enrollment
- total enrollment
- full-time / part-time undergraduate counts
- race/ethnicity enrollment counts
- retention rate
- student-to-faculty ratio
- tuition and fees
- food/housing / cost of attendance
- average net price where available
- applicants, admitted, enrolled, admit rate, yield
- SAT/ACT 25th/50th/75th percentiles where available
- graduation rate
- outcome-measure completion/enrollment status
- degrees awarded by level

### Phase 2: CDS-aligned public comparison

Map only fields with defensible CDS equivalents:

- C1-like applicants/admitted/enrolled totals
- C9-like score percentiles
- B1/B2-like enrollment totals and demographic counts
- G-like cost fields
- selected H-like aid counts/amounts
- B retention/graduation analogs

Every mapped field needs an alignment note:

- `direct`: same concept and population
- `near`: usable comparison with a visible definition note
- `context_only`: useful context, not a CDS replacement
- `not_cds_equivalent`: do not surface in CDS-comparison UI

### Phase 3: Full directory expansion

Use `institution_directory` as the public list backbone:

- CDS schools show archived documents plus the federal baseline.
- Non-CDS Title IV schools show a federal baseline page.
- Schools with no CDS and no useful IPEDS row remain directory stubs only.

This should turn the product from "hundreds of CDS schools" into "thousands of
college pages with honest source depth."

## Pipeline

### Annual release loader

When the release checker detects a new or changed IPEDS release:

1. Fetch the official Access database page and detect the latest annual bundle.
2. Detect changed release rows by table name, release type, and SHA.
3. Download the annual Access bundle and companion Excel metadata workbook.
   Fallback to selected Complete Data Files only when the Access bundle path is
   unavailable or a narrow emergency refresh is required.
4. Store raw release bytes in Supabase Storage under:

```text
federal/ipeds/{collection_year}/{release_type}/access.zip
federal/ipeds/{collection_year}/{release_type}/tablesdoc.xlsx
federal/ipeds/{collection_year}/{release_type}/fallback/{table_name}.zip
federal/ipeds/{collection_year}/{release_type}/fallback/{table_name}-dictionary.zip
```

5. Load metadata into `ipeds_releases`, `ipeds_tables`, `ipeds_columns`, and
   `ipeds_value_labels`.
6. Load CSV rows into `ipeds_raw_rows`.
7. Project curated facts into `ipeds_facts`.
8. Refresh `school_facts_unified` and public cache views.
9. Emit a release report with row counts, missing tables, schema drift, and
   changed variable definitions.

### Schema drift guard

Abort the whole release load only if:

- the release artifact cannot be downloaded or checksummed
- the metadata workbook/database cannot be parsed
- core identity tables cannot be loaded
- row counts are implausibly low across the release
- imputation-value metadata is missing globally

Do **not** block the entire release because one public field variable was
renamed or removed. NCES variable churn is expected. Instead:

- load the release;
- mark the affected mapping as `inactive`, `renamed_candidate`, or `missing`;
- suppress that field from public `ipeds_facts` until reviewed;
- show the issue in the operator dashboard and release report.

Allow the load but flag QA if:

- a new relevant variable appears
- a variable title changes but type remains stable
- a provisional file is replaced by final
- high-value fields have unexpected null spikes

### Cadence

- Check NCES monthly year-round.
- Check weekly from September through March, when major collection releases and
  final/provisional updates appear.
- Manual operator run is allowed after NCES posts a new release memo.

This cadence is separate from CDS finder cadence. IPEDS is a bulk federal data
release process, not a per-school discovery process.

### Provisional-to-final revisions

Federal revisions are not school-disclosure changes. If a value changes because
IPEDS provisional data was replaced by final data, treat it as a federal data
revision:

- preserve both release records;
- update the current serving value to final;
- expose previous provisional provenance in operator/audit views;
- do not emit a PRD 019 school-facing change event unless the story explicitly
  says "IPEDS revised" rather than "the school changed."

## UI and API behavior

### School pages

Add a source-labeled federal profile section:

- Show "IPEDS federal baseline" on all pages with UNITID.
- On CDS-backed pages, keep CDS as the hero/source-document narrative.
- On non-CDS pages, show "No public CDS archived yet" plus available IPEDS
  facts.
- Label release status: "IPEDS provisional 2024-25" or "IPEDS final 2023-24."
- Show definition notes where a value is not CDS-equivalent.
- Show reporting status on values that are not direct institutional reports:
  `reported`, `imputed`, `not applicable`, or `suppressed/unusable`.

Imputation UX rule:

- A reported value may render as plain source text:
  `IPEDS final 2023-24`.
- An imputed value must render with a visible badge or parenthetical:
  `IPEDS final 2023-24 · imputed`.
- A hover/disclosure note should explain the NCES imputation flag in plain
  language and link to the methodology page.
- Imputed values may appear in baseline profiles, but they must not power
  ranking badges, editorial claims, or change narratives without an explicit
  "imputed federal value" label.
- If the imputation flag is `not applicable` or `value not usable`, show
  "Not applicable" or "Not reported in IPEDS" instead of coercing to zero.

Open-admissions rule:

- For open-admissions institutions or schools outside the ADM reporting universe,
  admit-rate filters must treat admissions values as `not_applicable`, not as
  zero or missing-by-error.
- Browse should offer an explicit admissions availability facet:
  `reported`, `open admissions / not applicable`, and `missing/unknown`.

### Browse

Add a coverage toggle:

- `CDS only`
- `CDS + IPEDS baseline`
- `IPEDS baseline only`

Default should remain CDS-focused until the federal-baseline QA gate passes.

### API

Expose:

- `ipeds_facts`
- `school_facts_unified`
- `ipeds_releases`
- `ipeds_tables`

Do not expose raw JSONB rows as the default public API. They can be public later,
but the product API should first privilege curated facts with provenance.

Scorecard v1 position:

- Keep Scorecard as the federal consumer-outcomes layer.
- Use IPEDS as the preferred source for direct IPEDS-origin facts once PRD 021
  has release/imputation metadata loaded.
- Keep Scorecard fields for earnings, debt, repayment, and borrower outcomes
  unless and until we separately prove a better official source path.
- Do not build an opaque "federal arbiter" that silently chooses between
  Scorecard and IPEDS. The source must remain visible.

### Attribution

Add persistent NCES/IPEDS attribution to the methodology page and source notes.
Exact wording should be finalized during implementation, but every public
IPEDS-backed surface must make clear that data comes from NCES/IPEDS and that
collegedata.fyi is transforming and presenting it, not collecting it.

### Accessibility

All IPEDS-driven public tables should inherit PRD 020 constraints:

- native table semantics
- captions and source notes
- no semantic collapse on mobile
- explicit missing-data language
- source labels visible in text, not color only

## QA plan

### Fixture schools

Use a mixed fixture set:

- Harvard, Yale, Michigan, UCLA: CDS + IPEDS comparison
- Connecticut College: CDS discovered by submitter, useful for source precedence
- Crowder College: non-CDS/fact-book-style use case with IPEDS facsimile already
  inspected locally
- Goshen and Crowder-style non-CDS publishers: compare IPEDS baseline to
  school fact-book facts only as a manual validation exercise. This PRD does not
  scope arbitrary fact-book ingestion.
- Two-year publics and open-admissions schools: admissions-null behavior
- Branch-campus systems: UNITID/source mapping stress tests

### Validation checks

- Compare 20 high-value fields from IPEDS Data Center facsimile PDFs against
  loaded `ipeds_facts` values for the same UNITIDs.
- Compare CDS C1/C9 values against ADM/DRVADM for 25 schools and classify
  differences as definition drift, timing drift, extraction issue, or school
  reporting inconsistency.
- Verify imputation flags flow through to public source notes.
- Verify final releases supersede provisional releases without erasing prior
  provenance.
- Verify no value appears in CDS change intelligence unless its source is CDS or
  explicitly labeled as IPEDS context.

### Success gates

Phase 1 can ship when:

- At least 95% of `institution_directory` rows with UNITID have a loaded IPEDS
  identity row.
- At least 90% of degree-granting Title IV rows have enrollment and cost facts.
- All MVP variables have dictionary metadata and value labels loaded.
- At least 50 fixture facts are manually validated against NCES facsimile or CSV
  source rows.
- Public UI source labels pass visual, keyboard, and screen-reader checks.

Phase 2 can ship when:

- Every observed CDS-vs-IPEDS mismatch in the 25-school fixture set is
  classified into one of: timing drift, population drift, gender/category
  treatment, imputation, extraction error, school inconsistency, or unresolved.
- No `unresolved` mismatch remains for a field we plan to label `direct` or
  expose in CDS-comparison UI.
- Each CDS-aligned field has a `definition_alignment` classification.
- Browse filters cannot silently mix CDS and IPEDS values without a visible
  source-mode label.

## Risks and mitigations

### Definition drift

Risk: A CDS value and an IPEDS value look identical but use different
populations, cohorts, or reporting periods.

Mitigation: classify field mappings and expose definition notes. Never collapse
sources into one unlabeled value.

### Timeliness

Risk: IPEDS lags current CDS publication cycles.

Mitigation: use IPEDS as baseline/context, not as the latest-year change source.
Keep CDS finder/freshness work for schools publishing current CDS files.

### Imputation and revisions

Risk: Provisional/final revisions or imputed values create false year-over-year
stories.

Mitigation: keep release type and imputation flags in every projected fact.
Change intelligence remains CDS-first.

### UNITID complexity

Risk: campus systems, branch campuses, and CDS sub-institutional rows do not
align one-to-one with UNITID.

Mitigation: preserve existing `sub_institutional` logic; add explicit mapping
confidence and do not infer a campus-level federal value for a sub-campus CDS
row without a verified UNITID.

Verified UNITID means one of:

- exact `schools.yaml` / `institution_directory` match on known `ipeds_id`;
- deterministic `institution_slug_crosswalk` match with no competing alias;
- manual operator review recorded with reviewer, date, source URL, and reason;
- explicit sub-institution mapping row when the CDS publisher represents a
  campus, system, college, or program that differs from the parent UNITID.

If none of those conditions holds, the UI may show institution-directory
coverage status but must not blend CDS and IPEDS values as if they describe the
same reporting entity.

### NCES endpoint fragility

Risk: Data Center endpoints use session redirects or temporary downtime.

Mitigation: prefer annual Access bundles; use cookie-initialized Data Center
fetches only as a fallback; include a clear User-Agent, low concurrency,
retry/backoff, immutable raw artifact storage, and release-level caching.

### Product trust

Risk: Users think "IPEDS baseline" means the same thing as "school-published
CDS."

Mitigation: source labels are part of the UI contract. Use language such as
"Federal baseline" and "School-published CDS" consistently.

## Rollout plan

### M0: Field mapping spike

- Download current IPEDS dictionaries for the MVP table set.
- Decide input strategy after comparing Access bundle, Complete Data Files, and
  third-party normalized packages. Default to Access bundle unless the spike
  proves another path preserves metadata and reduces maintenance.
- Build a mapping spreadsheet from IPEDS variables to product field keys.
- Classify definition alignment.
- Validate 10 schools manually.
- Rerun UNITID coverage counts and produce a manifest gap list.

Decision gate:

- If the Access-bundle loader is materially harder than a third-party package
  that preserves release metadata, imputation flags, and attribution, pause M1
  and rewrite this PRD around that input.
- If fewer than 15 high-value fields are direct/near mappings, do not build the
  public unified serving view yet; ship only an internal loader spike.
- If 15-30 high-value fields are direct/near mappings, limit v1 to a
  federal-baseline profile and do not ship CDS-aligned comparison surfaces.
- If 30+ high-value fields are direct/near mappings, proceed with both baseline
  profile and carefully labeled CDS-aligned comparison fields.

### M1: Loader and metadata

- Add migrations for `ipeds_releases`, `ipeds_tables`, `ipeds_columns`,
  `ipeds_value_labels`, and `ipeds_raw_rows`.
- Build `tools/ipeds/download_release.py`.
- Build `tools/ipeds/load_release.py`.
- Add schema drift tests.

### M2: Curated facts

- Add `ipeds_facts`.
- Project MVP fields.
- Add unit tests around value labels, imputation flags, and release status.
- Generate a QA report for fixture schools.

### M3: Unified serving layer

- Add `school_facts_unified`.
- Thread source labels into TypeScript types.
- Add API documentation.

### M4: School page federal baseline

- Add source-labeled IPEDS facts to school pages.
- Add non-CDS federal baseline stub pages.
- Add PRD 020-style accessible tables for high-value groups.

### M5: Browse expansion

- Add source-mode controls to browse.
- Add filters backed by `school_facts_unified`.
- Add export columns for source and release type.

### M6: Annual operations

- Add monthly/weekly scheduled release checker. **Shipped follow-up:** monthly
  GitHub Actions release probe with a 10-month no-op window from the latest
  loaded provisional Access release date.
- Add operator dashboard rows for last IPEDS load, tables loaded, row counts,
  schema drift, and unresolved mapping issues.

## Open questions

1. What is the public institution universe we want to expose: all 6,400 Title IV
   institutions, only degree-granting institutions, or the current
   `institution_directory` filter set?
2. Should non-CDS federal baseline pages be indexed immediately, or noindexed
   until the UI and source labels are polished?
3. How much UI copy should explain provisional vs final data without making pages
   feel bureaucratic?
4. Should IPEDS facsimile PDFs be stored as human-readable source artifacts, or
   is CSV/dictionary provenance enough?

## Recommendation

Build this.

The CDS archive stays the differentiated source-preservation product. IPEDS
becomes the coverage engine that makes the site useful for the much larger
universe of schools that do not publish a CDS. The right mental model is not
"IPEDS replaces CDS"; it is "CDS is the school-authored primary source, IPEDS is
the federal baseline, and collegedata.fyi is the place where both are reconciled
with source labels."
