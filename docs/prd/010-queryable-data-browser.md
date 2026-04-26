# PRD 010: Queryable data browser and filterable school finder

**Status:** Draft, revised after red-team review
**Created:** 2026-04-26
**Updated:** 2026-04-26
**Author:** Codex + Anthony
**Related:** [PRD 001](001-collegedata-fyi-v1.md), [PRD 002](002-frontend.md), [PRD 005](005-full-schema-extraction.md), [PRD 006](006-llm-fallback.md), [Extraction Quality](../extraction-quality.md), [Architecture](../ARCHITECTURE.md)

---

## Context

collegedata.fyi can already answer deep questions about a single school-year, but it
still does not expose the corpus as a true queryable browser for non-technical users.
Today the public product supports:

- search for one school
- browse that school's archived CDS years
- inspect a single school-year page
- query raw API resources if you know PostgREST and the schema

What it does **not** support yet is the most natural product question:

> Show me schools with 2024-25 or newer data, at least 3,000 students, and some
> combination of admissions, enrollment, price, or test-score traits.

That missing workflow is not only a frontend gap. It is also a data-shape gap.
The public API already exposes:

- `cds_manifest` for document-level metadata
- `scorecard_summary` and `cds_scorecard` for curated federal fields
- `cds_artifacts.notes.values` for canonical CDS field values

But most CDS values are still stored inside JSON blobs keyed by canonical question
number. That is fine for a school-year detail page. It is the wrong shape for a
filterable cross-school browser, an analyst-facing table UI, or a stable public API
for arbitrary field-level queries.

This PRD treats the browser as both:

1. a user-facing feature
2. a forcing function to improve the underlying data model for every API user

The browser should make the site meaningfully more useful for students, counselors,
journalists, and researchers. The backend work should make all future requests easier,
not create a one-off UI that bypasses the real data-quality problem.

## MVP scope guardrails

The red-team review surfaced one major constraint: MVP cannot pretend that CDS field
IDs are already stable across all historical years. Therefore:

1. MVP is explicitly limited to `2024-25` and newer documents.
2. `field_id` is not treated as a globally stable key on its own.
3. Any field exposed for public filtering must clear a measured answerability threshold
   on the `2024-25+` corpus before it becomes part of the default UI.

This keeps the first release honest and avoids overpromising cross-year semantics that
the current extraction stack does not yet support.

## Problem

There are three distinct problems to solve.

### 1. Product problem: no cross-school discovery UI

Users cannot currently express multi-school filter queries without writing raw API
calls or exporting data into their own spreadsheet.

### 2. Data-model problem: CDS values are not query-shaped

Canonical CDS values are stored as nested JSON in `cds_artifacts.notes.values`.
That makes it hard to:

- filter numerically across schools
- sort on CDS fields
- join multiple CDS fields into one row
- expose stable typed semantics in the public API
- annotate per-field quality in a reusable way

### 3. Trust problem: query-time quality semantics are too weak

The project is already honest that extraction quality varies by tier, especially on
flattened PDFs. But the query surface still needs first-class ways to express, at
minimum:

- where a value came from
- how it was typed
- whether it was reported, intentionally not applicable, or simply missing
- whether the document itself is known low-quality or wrong-file

Without that metadata, a browser risks feeling more precise than the data deserves.

## User stories

### Primary

1. A parent wants to find schools with:
   - recent CDS data
   - mid-sized or larger undergraduate population
   - highly selective test-score profile
2. A counselor wants to save or export a filtered list of peer schools.
3. A journalist wants a clean table of schools matching a public, reproducible rule.
4. A researcher wants a stable field-level API instead of scraping school pages or
   hand-parsing `cds_artifacts.notes`.

### Secondary

1. An internal maintainer wants to know which fields are safe enough to expose in the
   browser and which should still be hidden behind a quality gate.
2. A contributor wants a clear target for improving extraction quality that benefits
   both the website and the API.

## Product principles

1. **Queryability beats cleverness.** The browser should feel like a clear filtering
   tool, not a toy visualization.
2. **Quality metadata is part of the product.** Users should be able to tell when a
   value came from a deterministic extractor versus a flatter, noisier path.
3. **One backend improvement should power many surfaces.** The data layer for this
   feature should also improve recipes, exports, third-party API usage, and future
   comparison tools.
4. **Start with the common case.** Latest-per-school queries matter more than a full
   arbitrary historical explorer on day one.
5. **Public semantics must be stable.** Field IDs, typed columns, and query behavior
   should be documented and predictable.

## Recommendation

Ship this in two layers, but sequence them around one thin end-to-end slice:

### Layer A: a reusable field-query substrate

Build a public query surface for CDS field values that is typed, filterable, and
reusable by all API consumers. This is the core investment.

### Layer B: a browser UI on top of a curated row model

Ship a user-facing browser that operates on one row per school-year, with a default
mode of one row per school using the latest qualifying year.

This is a hybrid strategy:

- not just a UI on top of raw JSON
- not a fully generic ad hoc BI system first
- not a hand-built one-off table disconnected from the real data model

### Thin-slice rule

Before expanding into the full substrate, ship one narrow but real vertical slice:

- `2024-25+` scope only
- 5-8 launch-certified fields
- one browser page
- one export path
- one documented latest-row rule

This optimizes for learning instead of waiting for a perfect architecture.

## Alternatives considered

### Option A: Custom browser on the current API only

Build a React filter UI that fetches manifest rows and then hydrates per-school
artifacts client-side.

**Pros**
- low schema work upfront
- fast to prototype

**Cons**
- wrong data shape
- expensive query fan-out
- poor sort/filter performance
- no reusable API improvement
- weak quality semantics

**Verdict:** Reject.

### Option B: Off-the-shelf BI tool on the current schema

Point Metabase, Superset, NocoDB, or Baserow directly at the existing database/views.

**Pros**
- very fast path to something usable internally
- useful for validating whether users even want the workflow

**Cons**
- CDS field values are still trapped in JSON blobs
- public-facing polish is weak
- quality semantics are still missing
- likely produces a confusing data model for end users

**Verdict:** Useful only after a better query surface exists.

### Option C: Curated wide table only

Create one materialized view with 30-80 high-value columns and build the product
entirely on that.

**Pros**
- simplest public UX
- excellent performance
- easiest MVP

**Cons**
- caps future flexibility
- creates pressure to keep adding more and more bespoke columns
- does not fully solve the field-query API problem

**Verdict:** Good MVP serving layer, but not sufficient as the only backend shape.

### Option D: Long-form field table only

Create one row per `(document_id, field_id)` and force the frontend to compose
arbitrary school-year tables on top of it.

**Pros**
- flexible
- elegant data model
- best general API shape

**Cons**
- harder frontend
- slower time to useful UX
- more complex query semantics for common browser workflows

**Verdict:** Necessary substrate, but not sufficient product by itself.

### Option E: Hybrid long-form + curated browser view

Build:

1. a long-form typed field surface for API users
2. a curated row model for the browser

**Pros**
- best long-term architecture
- browser UX stays simple
- third-party API consumers also benefit
- quality metadata can live at the field level and roll up into the browser

**Cons**
- more backend work than a pure UI MVP

**Verdict:** Recommended.

## Part 1: Public field-query substrate

### 1.1 New public resource: `cds_fields`

Expose one row per school-year-field for the selected extraction result used by the
site. Suggested shape:

| Column | Meaning |
|---|---|
| `document_id` | CDS document row |
| `school_id` | Canonical school slug |
| `school_name` | Display name |
| `sub_institutional` | Variant key; `NULL` for the primary school row |
| `ipeds_id` | Join key to scorecard |
| `canonical_year` | Academic-year label |
| `year_start` | Numeric first year, e.g. `2024` for `2024-25` |
| `schema_version` | Source schema vintage for this row |
| `field_id` | Schema-local CDS question number, e.g. `C.916` |
| `canonical_metric` | Optional stable direct-field alias, e.g. `first_year_enrolled` |
| `field_label` | Human-readable label |
| `section` | CDS section |
| `subsection` | CDS subsection |
| `value_text` | Raw display string |
| `value_num` | Parsed numeric value where valid |
| `value_bool` | Parsed boolean/checkmark value where valid |
| `value_kind` | `number | percent | currency | text | yesno | checkbox | unknown | not_applicable` |
| `value_status` | `reported | missing | not_applicable | parse_error` |
| `source_format` | `xlsx | pdf_fillable | pdf_flat | pdf_scanned | html` etc. |
| `producer` | canonical extractor / fallback producer |
| `producer_version` | version string |
| `data_quality_flag` | document-level quality flag |
| `archive_url` | public school-year page |

`field_id` alone is not the cross-year contract. In MVP, the stable public handle is
`canonical_metric` for the subset of launch-certified fields, while `field_id` remains
schema-local and is always paired with `schema_version`.

Derived metrics like `acceptance_rate` and `yield_rate` should not be modeled as
direct field aliases in `cds_fields`. They belong in the derived browser/API layer.

**Implementation note:** this should be materialized from day one, not a plain view.
JSON unrolling across the corpus is too expensive to put on the hot path.

### 1.2 Typed parsing rules

The field surface must not just re-export strings. It must centralize type parsing so
all consumers stop reimplementing this logic.

Needed outputs:

- `value_num` for numeric comparisons and sorting
- `value_bool` for yes/no and checkbox filters
- stable `value_kind`

The parser should preserve `value_text` as the public source-of-display truth.

The parser is explicitly **best-effort**. `value_num` is a filtering convenience, not
proof that every CDS value has perfect numeric normalization on day one.

For all percent/rate fields, the stored numeric contract should be fractional `0..1`.
Example: `58%` in the source becomes `value_text = "58%"` and `value_num = 0.58`.

### 1.3 Artifact selection rule

Some documents can accumulate multiple extraction artifacts over time. The browser must
not select “most recent” blindly. It needs a documented producer-precedence ladder and
an explicit rule for Tier 4 fallback overlays.

**MVP rule:**

1. Tier 1 filled XLSX canonical artifact
2. Tier 2 fillable PDF canonical artifact
3. Tier 6 structured HTML canonical artifact
4. Tier 4 deterministic cleaner canonical artifact
5. Tier 4 fallback cleaned artifact, merged as a gap-filling overlay onto the selected
   deterministic Tier 4 artifact when present

If multiple artifacts of the same producer family exist, use the latest one within
that family. This rule should live in a reusable selection surface rather than in the
browser alone, and that surface cannot be limited to `kind='canonical'` rows only.

### 1.4 Explicit quality semantics

Every field row should carry enough metadata for downstream consumers to make trust
decisions. **MVP quality semantics are intentionally modest** and limited to what the
project can support honestly today:

- extractor producer
- source format
- document-level `data_quality_flag`
- `value_status`
- schema version

This is enough to support browser behaviors like:

- show all rows and mark noisier sources
- distinguish blank / not applicable / missing
- explain why a field is unavailable

**Out of MVP:** a normalized per-field confidence score. That should become its own
design problem if the project decides it is worth building.

### 1.5 Latest-row semantics

The browser needs a stable answer to "latest."

Two supported semantics:

1. **Latest per school overall**
2. **Latest per school within the filtered year window**

For example, if the user says `year_start >= 2024`, the school should contribute its
latest row among `2024-25`, `2025-26`, etc.

But one more rule is required:

3. **Latest row with all selected filter fields populated**

If the browser is filtering on `first_year_enrolled` and `applied`, a school
should not be excluded just because its newest row is missing one of those fields
while an older row in the requested window has both. The UI must surface how many
schools were excluded due to missing values versus failing the filter itself.

This behavior must be documented and reproducible at the API level.
By default, the public browser should apply these semantics to primary school rows
where `sub_institutional IS NULL`. Variant-aware API consumers can opt into explicit
`sub_institutional` handling.

## Part 2: Curated browser-serving row model

### 2.1 New public resource: `school_browser_rows`

Create one row per school-year, backed by the field surface and selective joins to
`scorecard_summary`.

This is the serving layer for the website and a friendlier public export surface.

Suggested columns for MVP:

- `school_id`
- `school_name`
- `sub_institutional`
- `document_id`
- `canonical_year`
- `year_start`
- `schema_version`
- `source_format`
- `producer`
- `data_quality_flag`
- `admitted`
- `applied`
- `enrolled_first_year`
- `acceptance_rate`
- `yield_rate`
- `undergrad_enrollment_scorecard`
- `retention_rate`
- `avg_net_price`
- `pell_rate`
- `archive_url`

This row model is intentionally curated. The website should not try to expose all
1,105 CDS fields as first-class table columns in the first version.

`acceptance_rate` and `yield_rate` are versioned derived metrics in this serving
layer, not direct `cds_fields.canonical_metric` aliases.

**Not in MVP launch fields:** SAT/ACT percentiles. Those remain v1.1 candidates until
their `2024-25+` answerability is strong enough for a public demo.

When SAT/ACT fields do ship, they must come with companion semantics for:

- `reported`
- `test_optional`
- `not_used`
- `not_applicable`
- `missing_extraction`

### 2.2 Enrollment decision

The example query uses "schools with 3000+ students." That sounds simple but needs a
policy decision because the project has two possible enrollment sources:

1. **CDS-derived enrollment**
   - closer to the school-year document
   - requires a documented aggregation policy across the B.1xx matrix
2. **Scorecard enrollment**
   - already typed and clean
   - may lag the CDS year by 1-2 years

**Recommendation:** MVP uses `undergrad_enrollment_scorecard` only. CDS-derived
enrollment becomes a versioned derived metric later (`undergrad_enrollment_cds_v1`)
once its aggregation policy is written down and tested.

This avoids pretending the lag does not exist.

### 2.3 Browser modes

#### Mode A: Latest per school (default)

One row per school, best for discovery and list-building.

For MVP, this mode should operate on primary rows only: `sub_institutional IS NULL`.

#### Mode B: All school-years

One row per school-year, best for historical browsing and export.

Mode A should be the homepage for the feature. Mode B should be a deliberate toggle.

## Part 3: Website feature

### Page: `/browse` or `/finder`

Recommended route: `/browse`

The core interaction:

1. pick fields to display
2. add filters
3. sort results
4. export CSV
5. click through to the source school-year page

### MVP filter UX

Top controls:

- Mode: `Latest per school` / `All school-years`
- Year filter: `year_start >= [2024]`
- Add filter button
- Export CSV button
- Answerability summary (`X schools in scope, Y with all required fields`)

Filter builder rows:

- field selector
- operator selector (`=`, `!=`, `>`, `>=`, `<`, `<=`, `is blank`, `is not blank`)
- value input

Null behavior must be explicit:

- `=`, `!=`, `>`, `>=`, `<`, `<=`, and `is not blank` require a populated value
- `is blank` intentionally targets missing/blank values and does not count as a
  “missing required field” in the latest-row ranking step

MVP launch-certified fields:

- CDS year
- acceptance rate
- first-year enrolled
- undergraduate enrollment (Scorecard)
- net price
- Pell share
- retention rate
- source format
- document quality flag

Fields such as ACT/SAT percentiles are **v1.1 candidates**, not default launch fields.
They can ship only after their `2024-25+` answerability is measured and deemed good
enough for a public demo.

### Launch-safe example query

User selects:

- `Year start >= 2024`
- `Undergraduate enrollment (Scorecard) >= 3000`
- `First-year enrolled >= 1000`

Results table shows:

- School
- CDS year
- First-year enrolled
- Scorecard enrollment
- Source format
- Quality indicator
- Link to school-year page

### Advanced query, post-launch

The original motivating query:

- `Year start >= 2024`
- `Undergraduate enrollment >= 3000`
- `ACT Composite 75th percentile >= 34`

is a valid **post-launch** target, but should not be the public hero query until C.9xx
coverage improves materially and test-optional / not-applicable semantics are exposed.

### Result-table principles

1. Every number should be sortable.
2. Every row should link to the underlying school-year page.
3. A visible quality/status column should be present by default.
4. Export should include `schema_version` and enough metadata to make cross-row
   semantics understandable.
5. MVP result sets should be paginated server-side.
6. The filter builder must remain usable on mobile and keyboard-accessible.

## Underlying data-quality improvements this feature should force

This feature is valuable partly because it creates pressure to clean up the right
shared abstractions.

### 1. First-class typed field values

Parsing numeric and boolean values once in a public field surface is better than
having every caller reinvent string coercion.

### 2. Field-level value status

Expose `value_status` and document-level quality flags at query time so callers can
distinguish “missing,” “not applicable,” and “known low-quality document.”

### 3. Canonical derived metrics

If the browser offers acceptance rate, yield, or total undergraduate enrollment, those
derivations should become shared API features, not frontend-only math.

### 4. Stable latest-row logic

The project needs a documented, reusable definition of "latest available row" under
year filters.

### 5. Better visibility into missingness

A query surface makes it much easier to measure:

- which high-value fields are missing most often
- which source formats drag down availability
- where a resolver or cleaner would improve the most public value

That should feed the extraction roadmap directly.

## Off-the-shelf path

An off-the-shelf browser is still valuable, but only after the field substrate exists.

### Best candidate: Metabase

If the goal is fast validation, Metabase is the best fit after `school_browser_rows`
exists.

Why:

- strong table filtering
- easy public sharing / embedding
- CSV export
- low setup burden
- familiar for analyst users

### Acceptable alternatives

- `NocoDB` or `Baserow` if a spreadsheet-like browser is preferred
- `Superset` if the audience is primarily technical/analytical

### Recommendation on buy vs build

#### Short term

Use Metabase internally or as a hidden beta surface **after the substrate exists** to
learn which fields matter most. It is not useful on the current raw artifact schema.

#### Public product

Build a custom browser UI on top of the same query surfaces. The public site wants a
cleaner, calmer, more guided interface than a generic BI tool.

This is not a binary choice. The correct sequence is:

1. build the data substrate
2. validate via Metabase if useful
3. ship the custom UI on top of the same backend

## Non-goals

- A full drag-and-drop BI tool in v1
- Arbitrary chart builder
- User accounts, saved workspaces, or collaboration
- Free-text natural-language querying in the first release
- Full support for all 1,105 fields as curated table columns
- Hiding uncertainty. The feature should expose quality metadata, not bury it.

## Rollout plan

### Phase 0: thin vertical slice

Ship:

- `2024-25+` scope only
- `school_browser_rows` for 5-8 launch-certified fields
- `/browse` beta page
- export for the same curated fields
- documented latest-row rule and answerability summary

Success criteria:

- a non-technical user can reproduce one real browser workflow in under 30 seconds
- the site learns whether this interaction is actually used

### Phase 1: substrate hardening

Ship:

- `cds_fields`
- typed value parsing
- artifact-precedence selection
- `value_status`

Success criteria:

- API consumers can express multi-field filters without touching raw artifacts
- recipes and exports can move to the new surface

### Phase 2: curated browser row model expansion

Ship:

- expand `school_browser_rows`
- add documented derived metrics
- add more launch-certified fields as answerability allows

Success criteria:

- the website can answer the example query in one request path
- CSV export is stable and understandable

### Phase 4: off-the-shelf / embedded analyst surface (optional)

Ship only if useful:

- Metabase instance or embed
- internal saved questions
- field-demand analytics

## Open decisions

1. Should MVP enrollment default to Scorecard or CDS-derived values?
   - Recommendation: Scorecard default, CDS later as a toggle.

2. Should the browser exclude noisier extractions by default?
   - Recommendation: no. Show all, mark quality clearly.

3. Should the first public browser be latest-per-school only?
   - Recommendation: latest-per-school should be the default, with all-school-years
     available in beta if it does not complicate the first slice.

4. Should `cds_fields` be a view or a materialized view?
   - Recommendation: materialized from day one.

5. Should the field surface expose only the latest selected extraction result, or also
   alternative producer rows?
   - Recommendation: expose the selected extraction path by default using the producer
     precedence rule, with producer metadata kept visible. Multi-producer comparative
     browsing is out of scope for MVP.

6. Is a normalized per-field confidence score part of MVP?
   - Recommendation: no. MVP should ship without pretending this exists.

## Risks

### Risk 1: frontend ships before data semantics are stable

The UI could become tightly coupled to ad hoc parsing logic.

**Mitigation:** do not start with frontend-only filtering over raw artifacts.

### Risk 2: users over-trust flattened-PDF values

A polished browser can make noisier extracted values look authoritative.

**Mitigation:** visible quality columns are mandatory. Strict default exclusion filters are not.

### Risk 3: row explosion / performance problems

One row per field across the corpus can grow quickly.

**Mitigation:** keep the browser-serving layer curated; materialize as needed.

### Risk 4: semantic confusion between CDS year and Scorecard year

Users may assume all values refer to the same academic year.

**Mitigation:** label year sources clearly and document enrollment-source behavior.

## Success metrics

### Product

- Users can reproduce the motivating query in under 30 seconds.
- Browser export is used in recipes, analysis, or public reporting.
- Users click through from filtered rows to school-year detail pages at a healthy rate.

### Platform

- New API consumers stop depending on raw `cds_artifacts.notes.values`.
- At least one existing recipe migrates to `cds_fields` / `school_browser_rows`.
- Missingness and noisy-source hotspots become measurable by field and source format.

### Data quality

- High-value browser fields have explicit answerability gates.
- The project gains reusable typed parsing and value-status semantics.
- Extraction work can be prioritized based on observed filter demand, not guesswork.

## Immediate next step

Before implementation expands past the thin slice, write the technical design for:

1. `cds_fields`
2. `school_browser_rows`
3. typed parsing rules
4. artifact-precedence selection
5. latest-row semantics

That design should then go through `/plan-eng-review` before implementation begins.
