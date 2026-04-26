# Technical Design: `school_browser_rows` serving layer

**Status:** Draft
**Date:** 2026-04-26
**Owner:** Anthony Showalter
**Related:** [PRD 010](../prd/010-queryable-data-browser.md), [cds_fields technical design](./cds-fields-technical-design.md), [Scorecard Summary Table](../research/scorecard-summary-table-v2-plan.md), [Architecture](../ARCHITECTURE.md)

## Purpose

`school_browser_rows` is the curated serving layer for the website browser and the
friendliest export surface for non-technical API consumers.

It sits above `cds_fields` and `scorecard_summary` and answers a different question:

- not “what raw field values exist for this document?”
- but “what comparable school-year row should the browser filter and display?”

This design keeps the browser fast and understandable without forcing the website to
pivot arbitrary long-form field data at request time.

## Scope

### In scope

- one curated row per school-year document
- `2024-25` and newer documents only
- only launch-certified browser metrics in MVP
- explicit CDS-vs-Scorecard provenance where year semantics differ
- latest-per-school behavior defined as a search rule, not hidden storage behavior
- browser/export-serving shape for website and public API consumers
- preservation of `sub_institutional` identity in the public row model

### Out of scope

- exposing all CDS fields as first-class browser columns
- pre-2024 cross-year reconciliation
- SAT/ACT launch support
- saved searches or user-specific state
- a generic BI query engine implemented in SQL alone

## Core decisions

### 1. Use a curated materialized table, not a live pivot

`school_browser_rows` should be a real table or materialized relation refreshed from
`cds_fields` and `scorecard_summary`.

Reasons:

- browser queries should stay simple and index-friendly
- curated derived metrics should be computed once
- website export should use the same row semantics as the UI
- the serving shape should not depend on ad hoc frontend joins

This table is a serving layer. The sources of truth remain:

- `cds_fields` for CDS-derived values
- `scorecard_summary` for federal values

### 2. Store all qualifying school-years; do not store “latest only”

The base serving layer should contain one row per qualifying school-year document.

Do **not** collapse storage to one row per school. “Latest” depends on the query:

- overall latest
- latest within `year_start >= X`
- latest row that has the selected filter fields populated

That means the durable table should stay school-year-granular. Latest-per-school is a
search behavior layered on top.

### 3. Keep `sub_institutional` in the row identity

The existing corpus supports multiple document variants per school/year via
`sub_institutional`. The new serving layer must preserve that identity instead of
collapsing everything into `school_id`.

MVP rule:

- store `sub_institutional` on every row
- default website browser mode to primary rows where `sub_institutional IS NULL`
- reserve variant-aware browsing for explicit API access or a later UI toggle

This avoids Columbia-style variant collisions while keeping the first browser simple.

### 4. MVP launch metrics must be answerability-certified

MVP should include only fields with strong `2024-25+` answerability and clear
semantics.

Launch-certified metrics:

- `applied`
- `admitted`
- `enrolled_first_year`
- `acceptance_rate`
- `yield_rate`
- `undergrad_enrollment_scorecard`
- `retention_rate`
- `avg_net_price`
- `pell_rate`

Deferred to v1.1:

- SAT/ACT percentiles
- test-optional reporting fields
- CDS-derived undergraduate enrollment

The launch set should be versioned in docs and gated by measured fill rate before any
field becomes publicly filterable in the website defaults.

### 5. Use Scorecard enrollment for MVP

The product example “schools with 3000+ students” needs one honest definition.

MVP uses `scorecard_summary.enrollment` as `undergrad_enrollment_scorecard` because it
is already typed and operationally stable.

Do **not** expose a generic `undergrad_enrollment` column in MVP. That name implies a
precision the project does not yet have across sources.

When CDS-derived enrollment is ready, ship it as a distinct metric:

- `undergrad_enrollment_cds_v1`

### 6. Use one numeric scale for all rates and percentages

All stored rate/percent values in this serving layer should use fractional `0..1`
numeric form.

Examples:

- `acceptance_rate = 0.0612`
- `yield_rate = 0.4281`
- `retention_rate = 0.9720`
- `pell_rate = 0.1840`

Display formatting can render those as percentages. Storage and query semantics should
never mix `58` and `0.58`.

### 7. “Latest per school” needs a search contract, not just SQL `DISTINCT ON`

The PRD requirement “latest row with all selected filter fields populated” is not a
plain view problem.

If a school’s newest row is missing `enrolled_first_year`, but an older `2024-25` row
has it, the browser should be able to use that older row when the user filters on
`enrolled_first_year` or `yield_rate`.

That behavior requires a query-time ranking rule aware of:

- year window
- selected filters
- which metrics are required for the current query

This should be implemented as a documented browser-search contract, not as a static
table that pretends one “latest” row works for every query.

## Proposed schema

## Table: `school_browser_rows`

```sql
create table public.school_browser_rows (
  document_id                      uuid primary key,
  school_id                        text not null,
  school_name                      text not null,
  sub_institutional                text,
  ipeds_id                         text,

  canonical_year                   text not null,
  year_start                       integer not null,
  schema_version                   text not null,

  source_format                    text,
  producer                         text not null,
  producer_version                 text,
  data_quality_flag                text,
  archive_url                      text not null,

  applied                          integer,
  admitted                         integer,
  enrolled_first_year              integer,
  acceptance_rate                  numeric(7,6),
  yield_rate                       numeric(7,6),

  undergrad_enrollment_scorecard   integer,
  scorecard_data_year              text,
  retention_rate                   numeric(7,6),
  avg_net_price                    integer,
  pell_rate                        numeric(7,6),

  updated_at                       timestamptz not null default now()
);
```

Suggested indexes:

```sql
create index idx_browser_rows_school_year
  on public.school_browser_rows (school_id, sub_institutional, year_start desc);

create index idx_browser_rows_year
  on public.school_browser_rows (year_start desc);

create index idx_browser_rows_acceptance
  on public.school_browser_rows (acceptance_rate);

create index idx_browser_rows_enrollment
  on public.school_browser_rows (undergrad_enrollment_scorecard);

create index idx_browser_rows_price
  on public.school_browser_rows (avg_net_price);

create index idx_browser_rows_quality
  on public.school_browser_rows (source_format, data_quality_flag);
```

RLS:

- public read for `anon` / `authenticated`
- service-role writes only

## Metric definitions

### CDS-derived metrics

These come from `cds_fields.canonical_metric` rows selected from the chosen canonical
artifact for each document.

#### `applied`

- source: `canonical_metric = applied`
- type: integer
- null when missing or parse-unreliable

#### `admitted`

- source: `canonical_metric = admitted`
- type: integer

#### `enrolled_first_year`

- source: `canonical_metric = first_year_enrolled`
- type: integer

#### `acceptance_rate`

Derived at projection time:

```text
acceptance_rate = admitted / applied
```

Rules:

- only compute when both values are present and `applied > 0`
- otherwise `NULL`
- store as a fractional `0..1` rate
- do not round away precision in storage; round only in display

#### `yield_rate`

Derived at projection time:

```text
yield_rate = enrolled_first_year / admitted
```

Rules:

- only compute when both values are present and `admitted > 0`
- otherwise `NULL`
- store as a fractional `0..1` rate

### Scorecard-derived metrics

These are joined by `ipeds_id` from `scorecard_summary`.

#### `undergrad_enrollment_scorecard`

- source: `scorecard_summary.enrollment`
- note: may lag the CDS row by 1-2 years

#### `retention_rate`

- source: `scorecard_summary.retention_rate_ft`

#### `avg_net_price`

- source: `scorecard_summary.avg_net_price`

#### `pell_rate`

- source: `scorecard_summary.pell_grant_rate`

### Metadata fields

#### `scorecard_data_year`

Mandatory in the serving table whenever any Scorecard-derived field is present.

This lets the browser say, for example:

- CDS year: `2024-25`
- Scorecard year: `2022-23`

without implying that all metrics refer to the same reporting year.

## Build pipeline

## Step 1: define launch metric dependencies

The projection job should read from:

- `cds_fields` where `canonical_metric` is in the launch-certified CDS metric set
- `cds_fields` where `canonical_metric` is in the launch-certified direct-field set
- `scorecard_summary` for the approved federal fields

The launch-certified set should be explicit in code, not inferred loosely from all
`mvp_certified` aliases.

Example constant:

```text
BROWSER_MVP_DIRECT_CDS_METRICS = [
  "applied",
  "admitted",
  "first_year_enrolled"
]
```

Scorecard metrics are curated separately and joined by name.

## Step 2: select one browser-eligible document row

Source documents must satisfy:

- `canonical_year` parses to `year_start >= 2024`
- `cds_fields` projection exists for the selected extraction result
- document is not excluded by hard quality blockers

Hard blockers:

- `data_quality_flag = wrong_file`
- no selected extraction result

Non-blocking but visible:

- `blank_template`
- `low_coverage`
- flattened/scanned formats

Those remain queryable and visible in the browser with clear metadata.

## Step 3: pivot CDS metrics into one row

For each document:

- read the needed `cds_fields` rows
- pivot them into scalar columns
- compute derived rates
- join Scorecard values on `ipeds_id`

This can be implemented as:

1. a staging SQL view for the pivot
2. a projection worker that upserts the final rows

Recommendation: match the `cds_fields` design and use a projection worker so parsing,
selection, and derived-metric rules stay in one application-controlled pipeline.

## Step 4: refresh behavior

Refresh when any of these change:

- the selected extraction result for a document changes
- `cds_fields` rows for a document change
- `scorecard_summary` refreshes
- browser metric definitions change

Support:

- incremental upsert by `document_id`
- full rebuild command
- nightly reconciliation rebuild

## Latest-row search contract

## Why a base table is not enough

`school_browser_rows` supports:

- all-school-years browsing
- direct exports
- simple table filters

But it does **not** fully solve latest-per-school semantics when the required fields
change per query.

Example:

- school has `2025-26` row with `applied` and `admitted`
- school has `2024-25` row with `applied`, `admitted`, and `enrolled_first_year`
- user filters on `enrolled_first_year`

Correct latest-per-school answer: choose `2024-25`, not `2025-26`.

## Proposed query surface

Expose two public read paths:

### Path A: direct table access

`/rest/v1/school_browser_rows`

Use for:

- all-school-years mode
- CSV exports of the base serving table
- advanced users who want explicit control

### Path B: browser search endpoint

Implement a documented search endpoint for latest-per-school behavior.

Recommended shape:

- Next.js server route or Supabase Edge Function
- accepts a structured filter payload
- validates requested fields/operators against an allowlist
- compiles one SQL query over `school_browser_rows`
- returns rows plus answerability metadata

Example request contract:

```json
{
  "mode": "latest_per_school",
  "variant_scope": "primary_only",
  "min_year_start": 2024,
  "filters": [
    { "field": "undergrad_enrollment_scorecard", "op": ">=", "value": 3000 },
    { "field": "avg_net_price", "op": "<=", "value": 30000 }
  ],
  "columns": [
    "school_name",
    "canonical_year",
    "undergrad_enrollment_scorecard",
    "avg_net_price",
    "source_format",
    "data_quality_flag"
  ],
  "sort": { "field": "avg_net_price", "direction": "asc" },
  "page": 1,
  "page_size": 50
}
```

## Ranking rule for latest-per-school

Within the requested year window, rank candidate rows for each search identity by:

- `school_id` in `primary_only` mode after filtering to `sub_institutional IS NULL`
- `(school_id, sub_institutional)` in `include_variants` mode

Required fields are derived from the filter operators:

- `=`, `!=`, `>`, `>=`, `<`, `<=`, `is not blank` => field is required
- `is blank` => field is intentionally queried for blankness and is **not** counted as
  a missing required field

For `!=`, `NULL` does not satisfy the predicate. It counts as missing for ranking and
answerability purposes.

Then rank rows by:

1. rows that have all filter-required fields populated
2. newest `year_start`
3. newest `canonical_year`
4. stable tie-breaker on `document_id`

Then:

- evaluate filter rules only against the winning eligible row
- count schools with no fully populated row as “missing required fields”
- keep that count visible in the response metadata

This satisfies the PRD requirement without silently discarding schools or pretending
the latest row is always the correct one.

## Answerability metadata

The browser response should return summary counts alongside rows:

- `schools_in_scope`
- `schools_with_required_fields`
- `schools_missing_required_fields`
- `schools_failing_filters`
- `rows_returned`

This is critical product behavior, not analytics garnish. It tells users whether a
small result set reflects the filter itself or corpus missingness.

## Quality semantics in the browser

MVP quality behavior:

- show all rows by default
- expose `source_format` and `data_quality_flag` in both UI and export
- never silently hide flattened/scanned sources

Recommended display grouping:

- `clean`: xlsx, fillable pdf, structured html, no quality flag
- `review`: pdf_flat, pdf_scanned, or `low_coverage`
- `blocked`: wrong_file

Only `blocked` rows are excluded from the serving table. The others remain available.

This grouping is a UI affordance, not a stored truth column, unless later user
testing proves the grouping deserves to be materialized.

## API and export semantics

Exports from the browser should include:

- `document_id`
- `school_id`
- `school_name`
- `sub_institutional`
- `canonical_year`
- `scorecard_data_year`
- all displayed metrics
- `source_format`
- `producer`
- `data_quality_flag`
- `archive_url`

This is enough for downstream users to understand year mismatch and trace rows back to
the source page.

## Performance notes

- The direct table should stay small enough for indexed PostgREST filters because it
  is one row per school-year, not one row per field.
- Latest-per-school mode should push ranking into SQL with window functions rather
  than fetching all rows into the app.
- Sort fields must be limited to indexed or low-cost curated columns.
- CSV export should reuse the same query path as the on-screen results, not rerun a
  separate ad hoc export query with different semantics.

## Migration plan

### Stage A: source dependency landing

- ship `cds_fields`
- certify the launch metric set
- confirm `scorecard_summary` columns and names

### Stage B: base serving table

- create `school_browser_rows`
- build projection worker
- backfill `2024-25+` rows
- verify counts by school and year

### Stage C: latest-per-school search path

- implement browser-search endpoint
- return answerability metadata
- document ranking semantics

### Stage D: website integration

- build `/browse`
- wire mode toggle: latest-per-school / all-school-years
- add CSV export

## Open questions

1. Should `blank_template` remain queryable in the browser table, or should it move
   from “review” to “blocked” if user testing shows it mostly creates noise?

2. Should the browser-search endpoint be public and documented immediately, or should
   it start as a website-only server route until the filter contract settles?

3. Do we want a second curated serving table later for “latest stable school profile”
   semantics, or is `school_browser_rows` plus ranked search enough?

4. When SAT/ACT fields become viable, do they land in this same table as nullable
   columns, or do we create a v2 browser-serving table after the metric set expands?

## Recommended next implementation order

1. land `cds_fields`
2. measure answerability for the proposed launch metrics on `2024-25+`
3. build `school_browser_rows`
4. implement latest-per-school ranked search
5. build the `/browse` UI on top of that contract
