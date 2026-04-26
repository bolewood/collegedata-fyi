# Technical Design: `cds_fields` substrate

**Status:** Draft
**Date:** 2026-04-26
**Owner:** Anthony Showalter
**Related:** [PRD 010](../prd/010-queryable-data-browser.md), [Extraction Quality](../extraction-quality.md), [ADR 0006](../decisions/0006-tiered-extraction-strategy.md), [Architecture](../ARCHITECTURE.md)

## Purpose

`cds_fields` is the normalized field-query substrate behind the future browser and a
better public API for everyone else.

Today, most CDS values live inside `cds_artifacts.notes.values` JSON blobs keyed by
question number. That shape is fine for school-year detail pages. It is the wrong
shape for:

- numeric filtering
- sorting
- cross-school comparisons
- reusable quality semantics
- off-the-shelf table UIs

This design creates a projected, query-friendly field layer without changing the
canonical artifact format.

## Scope

### In scope

- `2024-25` and newer documents only
- one projected row per `(document_id, schema_version, field_id)`
- typed projections (`value_text`, `value_num`, `value_bool`)
- materialized public table, not a live JSON-unrolling view
- stable direct-field aliases via `canonical_metric`
- explicit producer-precedence selection
- best-effort value-status semantics

### Out of scope

- universal cross-year field reconciliation before 2024-25
- a normalized per-field confidence score
- changing the extractor artifact JSON shape
- full browser-serving row semantics

## Core decisions

### 1. Use a materialized table, not a view

`cds_fields` should be a real table populated by a projection step. Reasons:

- JSON unrolling across the corpus is too expensive to do on every request.
- typed parsing is easier in application code than in SQL alone.
- artifact-precedence logic should be computed once, not re-decided per read.
- public filters need predictable latency.

This is a projection table, not the canonical source of truth. The canonical source
remains `cds_artifacts.notes.values`.

### 2. `field_id` is schema-local, not the public cross-year contract

For MVP, cross-year stability only exists where we define it explicitly.

That means:

- keep `field_id` and `schema_version` together
- add `canonical_metric` only for vetted direct field aliases
- do not pretend every CDS field is already cross-year-stable

Examples:

- `canonical_metric = first_year_enrolled`
- `canonical_metric = applied`
- `canonical_metric = admitted`

For many fields, `canonical_metric` will be `NULL` until the project explicitly maps
them across years.

Derived metrics like `acceptance_rate` and `yield_rate` do **not** belong in
`cds_metric_aliases`. They should be versioned derived metrics computed by a serving
layer or documented query surface.

### 3. Producer precedence must be explicit

The current “latest canonical artifact wins” behavior in `cds_manifest` is not good
enough for a browser/query substrate.

The projection step should build one selected extraction result per document using
this precedence:

1. Tier 1 filled XLSX
2. Tier 2 fillable PDF
3. Tier 6 structured HTML
4. Tier 4 deterministic cleaner
5. Tier 4 fallback cleaned overlay

Within a producer family, latest `created_at` wins.

Important nuance: the Tier 4 fallback currently writes `kind='cleaned'`, not
`kind='canonical'`. The selected-artifact surface therefore cannot be implemented as
“latest canonical artifact only.”

Recommended behavior:

- choose the strongest base canonical artifact using steps 1-4 above
- if that base artifact is Tier 4 deterministic and a newer/later
  `tier4_llm_fallback` `kind='cleaned'` artifact exists for the same document, merge
  it as a gap-filling overlay
- deterministic values win on key conflicts; fallback only fills gaps

This selection rule should also be reusable for future public views, ideally via a
shared helper surface like `cds_selected_extraction_result`.

### 4. Quality semantics in MVP are modest

MVP does **not** invent a fake confidence score.

The quality semantics exposed by `cds_fields` will be:

- `source_format`
- `producer`
- `producer_version`
- `data_quality_flag`
- `value_status`
- `schema_version`

That is enough to support “show all, mark quality” without overselling precision.

## Proposed schema

## Table 1: `cds_field_definitions`

Separates repeated label metadata from the projected field rows.

```sql
create table public.cds_field_definitions (
  schema_version    text not null,
  field_id          text not null,
  field_label       text not null,
  section           text,
  subsection        text,
  value_kind_hint   text,
  primary key (schema_version, field_id)
);
```

Notes:

- populated from the committed schema artifacts
- public read
- updated only when a new schema version lands

## Table 2: `cds_metric_aliases`

Maps schema-local fields to stable direct-field aliases.

```sql
create table public.cds_metric_aliases (
  canonical_metric  text not null,
  schema_version    text not null,
  field_id          text not null,
  value_kind        text not null,
  mvp_certified     boolean not null default false,
  notes             text,
  primary key (canonical_metric, schema_version, field_id),
  foreign key (schema_version, field_id)
    references public.cds_field_definitions (schema_version, field_id)
);
```

Examples:

- `first_year_enrolled` may map to a specific C1 row
- `applied` may map to a specific C1 row
- `admitted` may map to a specific C1 row
- ACT/SAT aliases can exist before they are `mvp_certified`

Non-examples:

- `acceptance_rate`
- `yield_rate`

Those are derived metrics and belong outside this alias table.

The browser should only expose aliases where `mvp_certified = true`.

## Table 3: `cds_fields`

Projected field rows, one per selected extraction-result field.

```sql
create table public.cds_fields (
  document_id        uuid not null,
  school_id          text not null,
  school_name        text not null,
  sub_institutional  text,
  ipeds_id           text,
  canonical_year     text not null,
  year_start         integer not null,
  schema_version     text not null,
  field_id           text not null,
  canonical_metric   text,

  value_text         text,
  value_num          numeric,
  value_bool         boolean,
  value_kind         text not null,
  value_status       text not null, -- reported | missing | not_applicable | parse_error

  source_format      text,
  producer           text not null,
  producer_version   text,
  data_quality_flag  text,

  archive_url        text not null,
  updated_at         timestamptz not null default now(),

  primary key (document_id, schema_version, field_id)
);
```

Suggested indexes:

```sql
create index idx_cds_fields_school_year on public.cds_fields (school_id, sub_institutional, year_start desc);
create index idx_cds_fields_metric_num on public.cds_fields (canonical_metric, value_num);
create index idx_cds_fields_field_num on public.cds_fields (schema_version, field_id, value_num);
create index idx_cds_fields_status on public.cds_fields (value_status, source_format, data_quality_flag);
create index idx_cds_fields_year on public.cds_fields (year_start);
```

RLS:

- public read for `anon` / `authenticated`
- service role writes only

## Value parsing contract

The projection step owns all public typed parsing.

### Stored outputs

- `value_text`: literal display string from the artifact
- `value_num`: parsed numeric value when reliable enough for comparison
- `value_bool`: parsed boolean for yes/no and checkbox-like values
- `value_kind`: one of `number | percent | currency | text | yesno | checkbox | unknown | not_applicable`
- `value_status`: one of `reported | missing | not_applicable | parse_error`

Contract: when `value_kind = percent`, `value_num` is stored as a fractional `0..1`
value, not a `0..100` display percentage.

### Parsing rules

#### Numbers

Accept:

- `1450`
- `1,450`
- `58`
- `58.2`
- `$54,330`
- `58%` -> `0.58`

Do not parse to `value_num` when the value is structurally ambiguous:

- `1400-1500`
- `see footnote`
- `N/A`
- `Not required`
- `~1450`

Those still keep `value_text`; `value_num` remains `NULL`.

If the field definition or parser determines the source value is a percent/rate, the
public numeric form must be fractional `0..1` even when the source displays `58%`.

#### Booleans / checkboxes

Normalize obvious yes/no and checked/unchecked cases to `value_bool`.

#### Not-applicable semantics

Use `value_status = not_applicable` when the source indicates the school did not
report the value because it does not apply, not because extraction failed.

This matters later for test-optional fields and policy filters.

## Refresh model

## Write path

The projection is refreshed when:

1. a selected extraction result is inserted, superseded, or re-merged
2. a document’s `data_quality_flag` changes
3. a metric alias mapping changes
4. a parser/version change requires backfill

### Recommended implementation

Use a small projection worker, not a database trigger with complex parsing logic.

Responsibilities:

- find the selected extraction result per document
- delete prior `cds_fields` rows for that document
- parse the artifact’s `notes.values`
- join field definitions and metric aliases
- upsert fresh rows

This can live alongside the existing extraction workers and be runnable in two modes:

- `--document-id <uuid>` for incremental projection
- `--full-rebuild` for backfills

## Rebuild strategy

Support two commands:

1. **Incremental projection** after artifact writes
2. **Full rebuild** after parser/alias changes

Nightly reconciliation job:

- sample documents
- compare selected artifact timestamp vs `cds_fields.updated_at`
- repair drift if projection is stale

## Freshness contract

Target: `cds_fields` should refresh within the same operational cycle as extraction.

Public contract:

- eventual consistency is acceptable
- same-day freshness is expected
- docs should explicitly say it is a projection of selected extraction results, not the
  authoritative artifact store itself

## Public API shape

PostgREST surface:

```text
/rest/v1/cds_fields
```

Example:

```bash
curl 'https://api.collegedata.fyi/rest/v1/cds_fields?year_start=gte.2024&canonical_metric=eq.first_year_enrolled&value_num=gte.1000&select=school_id,school_name,canonical_year,value_num,source_format,data_quality_flag'
```

## Migration plan

### Stage A: metadata tables

- create `cds_field_definitions`
- create `cds_metric_aliases`
- backfill 2024-25 and 2025-26 definitions

### Stage B: projection table

- create `cds_fields`
- run first full rebuild
- expose public read

### Stage C: incremental refresh

- wire projector to artifact updates
- add nightly reconciliation

## Open questions

1. Should the projection worker live in Python next to extraction, or as a separate TS
   service closer to the API code?
   - Recommendation: Python, to stay close to extractor semantics and batch rebuilds.

2. Should `value_num` use `numeric` or more specialized column types?
   - Recommendation: `numeric` for v1 simplicity.

3. How many aliases should be `mvp_certified` initially?
   - Recommendation: 5-8 only.

4. Should `cds_fields` include raw provenance snippets?
   - Recommendation: no, not in v1. Keep the projection slim.

## Success criteria

- API consumers can filter across schools without reading `cds_artifacts.notes.values`
- the browser can build MVP queries off `canonical_metric` + typed values
- latency is stable under public filtering use
- the system can explain “missing” vs “not applicable” vs “parse failed”
