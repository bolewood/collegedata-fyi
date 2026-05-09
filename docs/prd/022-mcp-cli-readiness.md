# PRD 022: MCP and CLI readiness layer

**Status:** Draft
**Created:** 2026-05-09
**Author:** Anthony + Codex
**Related:** [PRD 010](010-queryable-data-browser.md), [PRD 015](015-institution-directory-and-cds-coverage.md), [PRD 017](017-match-list-builder.md), [PRD 018](018-open-college-fit-data.md), [PRD 019](019-cds-change-intelligence.md), [PRD 021](021-ipeds-coverage-layer.md), [API docs](../../web/src/app/api/page.tsx), [Architecture](../ARCHITECTURE.md)

---

## Executive summary

CollegeData.FYI already has the data agents and command-line users want:
source-linked Common Data Set records, NCES/IPEDS federal baselines, College
Scorecard context, coverage status, field-level provenance, and public
PostgREST access.

The missing layer is a small, task-oriented interface.

PostgREST is good for analysts who know table names, field IDs, headers, and
join paths. MCP clients, CLIs, notebooks, and LLM tool calls need verbs:

- search schools
- get school facts
- compare schools
- list source documents
- explain a field
- export a local slice

PRD 022 ships that layer quickly. The rule is: one shared JSON contract first,
then thin MCP and CLI wrappers over it. The wrappers should be boring. The fact
payload is the product.

## Product stance

Move fast. This is not a six-month platform program.

The goal is to make the current data easy to use from agents and terminals
without freezing every future data-model decision. Contracts should be explicit
where clients need stability and clearly marked experimental where the product
is still learning.

V1 should be useful even if it is narrow:

- one school facts endpoint with provenance;
- one school search endpoint;
- one compare endpoint with predictable sparse-data behavior;
- one sources endpoint;
- a small field dictionary for the shipped facts;
- a minimal OpenAPI spec;
- a minimal MCP server;
- a minimal CLI;
- versioned snapshots for people who want local files.

## Problem

### 1. The current API is database-shaped

The public API exposes powerful resources such as `cds_manifest`,
`cds_fields`, `school_browser_rows`, `school_merit_profile`,
`school_facts_unified`, `ipeds_facts`, and `cds_scorecard`.

That is the right substrate, but it pushes too much schema knowledge onto a
caller. A user or agent has to know:

- which resource is authoritative for a given question;
- when to prefer CDS over IPEDS or Scorecard;
- how to pass the anon key and PostgREST query syntax;
- how to translate a school name into a canonical `school_id`;
- which values are derived, imputed, stale, provisional, or CDS-specific;
- where to find the source URL for citation.

### 2. Agents need provenance by default

LLMs cite cleanly when source metadata is in the same object as the value. If a
tool returns only numbers, the agent has to make another call or infer
provenance from field names. That creates weak citations.

The response shape should make citation cheaper than omission.

### 3. CLI users want stable commands

Researchers, counselors, journalists, and developers should not need to copy the
Supabase anon key or hand-write PostgREST filters for common workflows. They
should be able to run:

```bash
collegedata search "mit"
collegedata facts mit
collegedata compare mit yale university-of-chicago --categories admissions,cost,outcomes
collegedata sources mit
collegedata export school_facts --format jsonl
```

### 4. Bulk local use needs pinned files

Live APIs are not enough for reproducible notebooks or local agent indexing.
Users need versioned JSONL/CSV/DuckDB snapshots with checksums. A mutable
`latest` alias is fine for convenience, but pinned paths must exist from day
one.

## Goals

1. Add stable, no-auth, task-oriented JSON endpoints for common school lookup,
   facts, source, and comparison workflows.
2. Make provenance first-class in every returned fact.
3. Publish a minimal OpenAPI spec for the friendly endpoints.
4. Ship a small MCP server that wraps the friendly endpoints as read-only tools.
5. Ship a small CLI that wraps the same endpoints.
6. Publish versioned snapshots for local/offline use.
7. Keep the implementation thin enough that future field additions do not
   require redesigning three separate products.

## Non-goals

- No write-capable MCP tools.
- No user accounts, saved lists, or private API keys for V1.
- No private operator data in any MCP/CLI/API response.
- No raw IPEDS table dump as the main product surface.
- No natural-language answer generation inside the API.
- No replacement for PostgREST.
- No large all-fields dictionary in V1.
- No custom vendor manifest unless a real consumer exists. OpenAPI and MCP are
  enough.

## User stories

1. A student can ask an MCP-enabled assistant, "Compare MIT, Yale, and Chicago
   on admissions, affordability, and outcomes," and the assistant can call one
   compare tool with cited results.
2. A counselor can run `collegedata facts mit --format table` and see CDS facts
   plus federal context with source labels.
3. A journalist can run `collegedata sources mit` and get the school page,
   original source URL, archived document URL, document year, extraction status,
   and last verification date.
4. A developer can call `/api/schools/mit/facts` without Supabase-specific
   headers.
5. A researcher can load a pinned `collegedata.duckdb` snapshot and query CDS,
   IPEDS, Scorecard, source documents, and field definitions locally.

## Product principles

1. **Task verbs over table names.** Friendly APIs should model user intent, not
   internal storage.
2. **Provenance travels with facts.** Every value should identify source layer
   and citeable URL when available.
3. **Narrow stable core, fast expansion.** Stabilize the fact contract; add
   fields and commands aggressively once the pattern works.
4. **No hidden source blending.** CDS, IPEDS, and Scorecard values can appear
   together, but the response must preserve source identity.
5. **Sparse data is honest data.** No-CDS schools should return useful IPEDS
   facts and explicit nulls for CDS-native facts.
6. **Thin wrappers.** MCP and CLI call the same JSON endpoints; they should not
   reimplement source-priority logic.

## V1 surface

### `GET /api/schools/search`

Purpose: resolve user-facing school names into canonical IDs.

Parameters:

- `q`: required search string
- `limit`: optional, default 10, max 25
- `include_directory_only`: optional boolean, default true

Example response:

```json
{
  "query": "mit",
  "results": [
    {
      "school_id": "mit",
      "school_name": "Massachusetts Institute of Technology",
      "aliases": ["MIT"],
      "city": "Cambridge",
      "state": "MA",
      "ipeds_id": "166683",
      "coverage_status": "cds_available",
      "has_cds": true,
      "has_federal_baseline": true,
      "school_url": "https://www.collegedata.fyi/schools/mit"
    }
  ]
}
```

### `GET /api/schools/{school_id}/facts`

Purpose: agent-ready school facts across CDS, IPEDS, and Scorecard.

Parameters:

- `categories`: optional comma-separated list:
  `identity,admissions,enrollment,cost,aid,outcomes,sources`
- `year`: optional CDS canonical year or federal data year where supported
- `format`: optional, default `json`

Example response:

```json
{
  "school_id": "mit",
  "school_name": "Massachusetts Institute of Technology",
  "generated_at": "2026-05-09T00:00:00Z",
  "facts": [
    {
      "key": "acceptance_rate",
      "label": "Acceptance rate",
      "value": 0.039,
      "display_value": "3.9%",
      "unit": "percent",
      "category": "admissions",
      "source": {
        "layer": "cds",
        "name": "Common Data Set",
        "url": "https://example.edu/mit-cds.pdf",
        "archive_url": "https://www.collegedata.fyi/schools/mit/2024-25",
        "canonical_year": "2024-25",
        "field_ids": ["C.116", "C.117"],
        "derivation": "admitted / applied"
      },
      "quality": {
        "flag": "derived",
        "note": "Derived from the school's CDS applicants and admitted counts."
      }
    }
  ],
  "sources": [
    {
      "kind": "school_page",
      "url": "https://www.collegedata.fyi/schools/mit"
    }
  ]
}
```

For directory-only or no-CDS schools, the same endpoint returns IPEDS and
Scorecard facts where available and explicit `null` values for CDS-native facts
when requested.

### `GET /api/schools/{school_id}/sources`

Purpose: citeable source ledger.

Includes:

- school page URL
- latest and historical CDS source URLs
- archived source document URLs
- source format
- source provenance
- extraction status
- data quality flag
- discovered/last verified/removed dates
- federal release metadata for IPEDS facts
- Scorecard data vintage

### `GET /api/compare`

Purpose: compare a list of schools across categories.

Parameters:

- `schools`: comma-separated canonical IDs
- `categories`: optional comma-separated list, default
  `admissions,cost,aid,outcomes`
- `fields`: optional comma-separated fact keys
- `format`: optional `json` or `csv`, default `json`

Sparse-data rule:

- The response uses a fixed column set chosen from `fields` or `categories`.
- Every requested school appears in every requested column.
- Missing values are explicit `null` with `quality.flag`.
- CDS-native fields are not silently replaced with IPEDS approximations.
- If a federal field is definition-adjacent but not equivalent, it uses its own
  field key and a definition note.

Example:

```json
{
  "schools": [
    { "school_id": "mit", "school_name": "Massachusetts Institute of Technology" },
    { "school_id": "example-directory-only", "school_name": "Example Directory-Only College" }
  ],
  "columns": [
    {
      "key": "acceptance_rate",
      "label": "Acceptance rate",
      "category": "admissions",
      "unit": "percent"
    }
  ],
  "rows": [
    {
      "school_id": "mit",
      "values": {
        "acceptance_rate": {
          "value": 0.039,
          "display_value": "3.9%",
          "source": { "layer": "cds", "canonical_year": "2024-25" },
          "quality": { "flag": "derived", "note": null }
        }
      }
    },
    {
      "school_id": "example-directory-only",
      "values": {
        "acceptance_rate": {
          "value": null,
          "display_value": "Not available",
          "source": null,
          "quality": {
            "flag": "not_available",
            "note": "No public CDS is available for this CDS-native field."
          }
        }
      }
    }
  ]
}
```

### `GET /api/fields`

Purpose: small public dictionary for the V1 friendly facts.

V1 scope is deliberately limited to the shipped fact keys, not every CDS, IPEDS,
and Scorecard variable.

Minimum fields:

- key
- label
- category
- source layer
- unit
- value type
- definition
- source field IDs or variables where applicable
- derivation note for computed facts
- caveats/definition-alignment note

Target size: roughly 30-60 fields in V1.

### Experimental: `GET /api/schools/{school_id}/changes`

Purpose: public-reviewed PRD 019 change events for a school.

This endpoint is explicitly experimental until PRD 019 is fully settled. It only
returns `public_visible=true` events and must not expose review queue or
operator-only event candidates.

## Response contract

All friendly endpoint responses should:

- include `generated_at` for non-trivial responses;
- use stable snake_case keys;
- return numeric values as JSON numbers where possible;
- include `display_value` for human-readable formatting;
- include source metadata next to each fact;
- use explicit `null` for unavailable values;
- use quality objects instead of magic strings.

Recommended V1 quality flags:

- `reported`
- `derived`
- `imputed`
- `provisional`
- `definition_mismatch`
- `not_reported`
- `not_available`
- `low_confidence_extract`

Suggested shared type:

```ts
type PublicFact = {
  key: string;
  label: string;
  value: string | number | boolean | null;
  display_value: string;
  unit: string | null;
  category: "identity" | "admissions" | "enrollment" | "cost" | "aid" | "outcomes" | "sources";
  source: {
    layer: "cds" | "ipeds" | "scorecard" | "derived" | "directory";
    name?: string;
    url?: string | null;
    archive_url?: string | null;
    data_year?: number | null;
    canonical_year?: string | null;
    release_type?: string | null;
    source_table?: string | null;
    source_variable?: string | null;
    field_ids?: string[];
    derivation?: string | null;
    imputation_label?: string | null;
    definition_alignment?: string | null;
  } | null;
  quality: {
    flag: string;
    note: string | null;
  };
};
```

OpenAPI may use a relaxed schema for `source` in V1 rather than a fully
discriminated `oneOf` by source layer. Do not let schema tooling block shipping
the endpoint.

## Source priority

Source priority is field-specific:

- CDS wins for current-year CDS-native admissions, application-plan, wait-list,
  factor-importance, class-rank, GPA, and Section H details.
- IPEDS wins for directory-scale federal baseline facts and no-CDS schools.
- Scorecard wins for federal outcomes, debt, earnings, and net-price fields
  already sourced from Scorecard.
- Derived facts must cite the inputs or identify the serving view/function that
  derives them.
- Do not coerce IPEDS into CDS semantics without a definition note.

## Machine-readable discovery

Ship:

- `/openapi.json`: minimal OpenAPI 3.1 spec for the friendly endpoints.
- `/llms.txt`: cheap human/agent-readable guide with API examples and citation
  guidance.

Do not ship `/.well-known/collegedata-tools.json` in V1. There is no consumer
for a project-specific manifest yet.

`llms.txt` is not a launch dependency for agents; it is a lightweight
documentation affordance. MCP clients discover tools from the MCP server.

## MCP server

Ship a minimal read-only MCP server that wraps the friendly endpoints.

Suggested package path:

```text
packages/mcp-server/
```

V1 tools:

- `search_schools(query, limit?)`
- `get_school_facts(school_id, categories?)`
- `compare_schools(school_ids, categories?, fields?)`
- `get_source_documents(school_id)`
- `get_field_dictionary(category?)`

Later tools:

- `get_school_profile(school_id)`
- `get_recent_changes(school_id?)`

Design constraints:

- No service role key.
- No write tools.
- No mutation-like names.
- No hidden calls that change state.
- Preserve source metadata exactly as returned by the endpoint.

## CLI

Ship a minimal CLI that calls the same friendly endpoints as the MCP server.

Suggested package path:

```text
packages/cli/
```

V1 commands:

```bash
collegedata search <query>
collegedata facts <school_id> [--categories admissions,cost,outcomes]
collegedata compare <school_id...> [--categories admissions,cost,outcomes]
collegedata sources <school_id>
collegedata fields [--category admissions]
collegedata export <snapshot> [--format jsonl|csv|duckdb]
```

Output modes:

- `table`: default for TTY
- `json`: default when piped
- `csv`: for compare/export
- `jsonl`: for export

CLI constraints:

- No auth setup in V1.
- Respect `COLLEGEDATA_API_BASE` for staging/local testing.
- Use non-zero exit codes for not found, bad arguments, network failure, and
  unexpected response shape.
- Keep stdout machine-readable when `--format json|jsonl|csv` is selected.
- Send warnings and progress to stderr.

`export` is allowed to fetch static snapshot files instead of JSON endpoints.
That is a separate channel by design.

## Bulk snapshots

Publish snapshots under immutable versioned paths and maintain a convenience
`latest` alias.

Path shape:

```text
https://www.collegedata.fyi/snapshots/v1/2026-05-09/schools.jsonl
https://www.collegedata.fyi/snapshots/v1/2026-05-09/school_facts.jsonl
https://www.collegedata.fyi/snapshots/v1/2026-05-09/sources.jsonl
https://www.collegedata.fyi/snapshots/v1/2026-05-09/field_dictionary.json
https://www.collegedata.fyi/snapshots/v1/2026-05-09/collegedata.duckdb
https://www.collegedata.fyi/snapshots/v1/2026-05-09/manifest.json
https://www.collegedata.fyi/snapshots/latest/manifest.json
```

V1 snapshot set:

- `schools.jsonl`: identity, directory, coverage, useful URLs.
- `school_facts.jsonl`: one row per source-labeled fact in the V1 dictionary.
- `sources.jsonl`: one row per document/release/source record.
- `field_dictionary.json`: V1 fact dictionary.
- `collegedata.duckdb`: local analytics database with the same tables.
- `manifest.json`: generated timestamp, row counts, checksums, schema version,
  and pinned file URLs.

Snapshot requirements:

- Generated by a repeatable script.
- Uses stable column names aligned with the JSON endpoint contract.
- Includes checksums.
- Does not include operator-only data.
- Can be regenerated manually before automation.

## Caching, rate limits, and usage signal

V1 is public and no-auth, but it should not be an accidental blank check.

Default policy:

- Use aggressive edge caching for facts, fields, sources, OpenAPI, and
  snapshots.
- Keep search cacheable for short windows by query string.
- Add lightweight IP-based rate limiting if Vercel/Supabase usage shows
  obvious abuse.
- Do not require users to paste the Supabase anon key for friendly endpoints.
- Keep raw PostgREST as-is for power users.

Basic usage counters should be enough:

- endpoint path
- status code
- cache hit/miss if available
- response time bucket

Use existing analytics/logging infrastructure where possible. Do not build a
custom analytics product for this PRD.

## Implementation plan

### Milestone 0: shared fact contract

1. Inventory existing public views and frontend query helpers.
2. Pick 30-60 V1 fact keys across identity, admissions, enrollment, cost, aid,
   outcomes, and sources.
3. Define source-priority rules for those keys.
4. Create fixtures for:
   - CDS-backed school
   - no-CDS or directory-only school with federal facts
   - older-CDS school
   - unknown school

### Milestone 1: friendly endpoints

Build:

- `/api/schools/search`
- `/api/schools/{school_id}/facts`
- `/api/schools/{school_id}/sources`
- `/api/compare`
- `/api/fields`

Keep existing `/api/facts/{school_id}` as a compatibility alias or document it
as legacy.

### Milestone 2: OpenAPI and docs

Build:

- `/openapi.json`
- `/llms.txt`

Update:

- public `/api` page
- README quickstart
- `docs/ARCHITECTURE.md` consumer API section
- `docs/recipes/README.md`

### Milestone 3: MCP server

Build `packages/mcp-server/` with the V1 tools listed above.

Manual QA:

- tool list works
- search school works
- facts include sources
- compare preserves sparse-data semantics
- no mutation tools exist

### Milestone 4: CLI

Build `packages/cli/` with the V1 commands listed above.

Manual QA:

- table output in a normal terminal
- JSON output when piped or `--format json`
- non-zero exits for bad school IDs and network failures
- `COLLEGEDATA_API_BASE` works

### Milestone 5: snapshots

Build repeatable snapshot generation and publish a first pinned V1 snapshot.

Manual QA:

- files download
- checksums match
- DuckDB opens locally
- `collegedata export school_facts --format jsonl` works

## Testing

API:

- fact normalization tests
- source-priority tests for V1 keys
- route tests for search, facts, sources, compare, fields
- error-shape tests

MCP:

- tool-list smoke test
- mocked endpoint tool-call tests
- one manual run against production or preview

CLI:

- command parsing tests
- output formatting tests
- exit-code tests

Snapshots:

- manifest checksum tests
- schema smoke tests
- DuckDB open/query smoke test

## Launch checklist

- Friendly endpoints deployed.
- Public API docs updated.
- OpenAPI live.
- MCP server can run locally.
- CLI can run locally.
- First versioned snapshot published.
- Production smoke checks:
  - search MIT
  - get MIT facts
  - get source documents for MIT
  - compare MIT, Yale, Chicago
  - retrieve field dictionary
  - download `manifest.json`

## Open questions

1. Should the first CLI be Node (`npx collegedata`) or Python
   (`uvx collegedata`)? Bias: Node first because the repo is already a Next app;
   Python can follow if researchers ask for it.
2. Should snapshots live in Vercel public assets, Supabase Storage, GitHub
   Releases, or all three? Bias: Supabase Storage for files, linked from the
   website.
3. Should the first compare endpoint allow arbitrary fact keys? Bias: yes, but
   only for keys present in `/api/fields`.
4. Is `collegedata.duckdb` too large for V1 hosting? Bias: try it; fall back to
   JSONL if hosting cost or build time is unreasonable.

## Success criteria

- A developer can retrieve one school fact with a citation in under one minute.
- An MCP client can compare three schools without manual endpoint construction.
- CLI `facts`, `compare`, and `sources` work without an API key.
- Snapshot files are pinned and reproducible.
- No operator-only fields are exposed.

