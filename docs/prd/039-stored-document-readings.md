# PRD 039: Stored document readings for school pages

**Status:** Draft. Owner decisions recorded 2026-11-17 (see [Decisions](#decisions)). Work starts no earlier than 2026-11-24 (see [Start gate](#start-gate)).
**Created:** 2026-11-17
**Author:** Claude. Two review rounds: Gemini 4 Hydrogen on the first draft (whole-page payloads), then Codex on the readings design. See [What the reviews changed](#what-the-reviews-changed). The text below is the design after both; it has not been reviewed a third time.
**Related:** [PRD 002: frontend](002-frontend.md), [PRD 038: template overlay extraction](038-template-overlay-extraction.md), PRs #236, #262, #333–#338

---

## Summary

A cold school hub page asks the live database about 21 questions. One of them, fetching a whole extraction artifact, is about 85% of school-page database time, and the hub page uses very little of what it fetches.

This PRD cuts that cost in two steps, cheapest first:

1. **Narrow the read.** More than half of each artifact is a field the web app never reads. Asking only for the parts it uses is a small change and is measured before anything else is built.
2. **Store parser results.** For what remains, store the small results of the page's parsers once per document, as **document readings**, so later renders do not fetch the artifact at all.

Step 2 is built only if step 1 leaves a problem worth solving.

All numbers below were measured on 2026-11-17 against production (read-only). See [How measured](#how-measured).

## Problem

### What a cold hub page costs

Supabase gateway logs, one minute of a crawl burst (2026-11-17 12:33 UTC, 76 hub renders):

| Read | Requests | Per page |
|---|---:|---:|
| `cds_artifacts` | 384 | 5.1 |
| `institution_directory` | 205 | 2.7 |
| `school_browser_rows` | 149 | 2.0 |
| `cds_manifest` | 142 | 1.9 |
| 8 other tables and views | 75–101 each | about 1 each |
| **Total** | about 1,600 | **about 21** |

`pg_stat_statements` since its last reset: the newest-canonical-artifact read (`select * from cds_artifacts where document_id = … and kind = 'canonical'`) has 91,435 calls at a mean of 46 ms, 4,229 s in total. The next 13 school-page statements together total about 730 s.

That read returns the whole artifact. Across the 5,371 newest canonical artifacts:

| Part of `notes` | Median | p95 |
|---|---:|---:|
| Whole row | 355 KB | 499 KB (max 6,075 KB) |
| `markdown` (document text) | 129 KB | |
| `values` | 13 KB | 111 KB |

By total bytes in a random sample of 200 of those artifacts: `native_tables` 38 MB, `markdown` 25 MB, `values` 5 MB, everything else under 1 MB. The web app reads `values`, `markdown`, `schema_version`, `stats` and `schema_fallback_used` from `notes`, and a few fields for fallback and overlay matching. It never reads `native_tables` (no reference under `web/src`).

Timed inside the database on the same 200 artifacts, warm, per artifact:

| Read | Time | Size |
|---|---:|---:|
| Whole row (today) | 6.2 ms | 349 KB |
| `values`, `markdown`, `stats`, schema version | 2.8 ms | 153 KB |
| `id` and `producer` only | 0.02 ms | |

These are database-side times on warm data. The 46 ms production mean also includes cold storage reads, JSON serialization by PostgREST and transfer, all of which scale with size.

### What the hub page takes from it

Read from `web/src/app/schools/[school_id]/page.tsx`, `web/src/lib/acceptance-history-data.ts` and `web/src/lib/acceptance-history.ts`:

| Use | Loader | Documents read |
|---|---|---|
| Schema-fallback note | `fetchExtract` → `schemaFallbackNoteFromArtifact` | newest extracted |
| Printed C1 counts | `gatedYearFacts` → `printedCountsForDocument` | one |
| Whether the acceptance-rate, early-decision and GPA pages exist | `fetch*PageServed` → `fetchAcceptanceHistory` | every candidate year, pilot schools only |

The printed counts feed the headline, the page metadata, the positioning card's acceptance rate, the summary and the fact ribbon.

**These results are not functions of the artifact alone.** The parsers (`c1-headline-totals.ts`, `c11-gpa.ts`, `c21-ed-counts.ts`, `c21-ed-note.ts`) read the artifact's `values` and document text and need the document's year. What the page finally shows also depends on:

- the projected counts in `school_browser_rows`, which fill in enrollment, replace unreadable C1 counts and supply Early Decision counts (`acceptance-history.ts`);
- IPEDS figures, pilot membership and the administrative-unit list, which gate the hub counts (`c1-hub-gate.ts`);
- choices made across a school's documents: the first usable document per year, gaps, exclusion reasons, minimum and recent-year rules, the newest school-written Early Decision note (`acceptance-history.ts`, `c11-gpa.ts`).

So the three page-exists flags are school-level decisions, and the counts are gated results. Neither can be stored per document. What can be stored per document is what the parsers return.

The **year page** shows the document itself (`MarkdownView` renders the full text and offers it as a download). It needs `values` and `markdown` and benefits from step 1 only.

### What happens under load

- **Crawl bursts.** 220–280 hub pages rendered inside one minute on Nov 8, 9 and 15. On Nov 8 and 15, PostgREST answered 503 to most requests in that minute (2,766 and 3,701).
- **Direct API scraping.** About 5,400 requests in one hour on Nov 17, mostly the same artifact read, pushed p95 to 2.5 s. This PRD does not change the public API; that traffic is out of scope.

PRs #334, #336, #337 and #338 reduce how often cold renders happen. None reduces what one cold render costs.

### Size of the surface

| | Count |
|---|---:|
| Schools with at least one visible document (full hub page) | 772 |
| Directory-only schools (stub hub page, no artifact read) | about 2,200 of 3,000 in scope |
| Extracted documents | 5,325 |
| Documents per school | median 6, p95 21, max 28 |
| Pilot schools (history read across all years) | 56 acceptance-rate; early-decision and GPA lists are shorter |

## Goals

1. A hub render fetches no more of an artifact than it uses, and after step 2 fetches no artifact when readings exist.
2. What every page shows is unchanged. Parity is proved against a frozen baseline before any switch.
3. Nothing gets staler than it is today.
4. Each step can be turned off with one environment variable, and any failure falls back to today's path.

## Non-goals

- Whole-page payloads, or storing final counts and page-exists flags. See [What the reviews changed](#what-the-reviews-changed).
- Changing gating, projection fallback or cross-document aggregation. They stay in the render.
- The CSV and XLSX downloads and the facts API, beyond what step 1 gives them for free.
- Changing hosts, object storage or a CDN for data.
- The public PostgREST API and its rate limits.

## Design

### Step 1: narrow artifact reads

`fetchExtract` and `fetchCanonicalArtifact` select `*`. Replace that with the columns and `notes` keys the web app uses: `values`, `markdown`, `schema_version`, `stats`, `schema_fallback_used`, and the keys the fallback and overlay matching read (source hash, markdown hash, hold flag). The returned object keeps its current shape so callers do not change.

A test lists the `notes` keys the web app reads and fails when code reads one that the select omits. Controlled by `ARTIFACT_READ_MODE=narrow|full`.

Expected effect, from the table above: bytes roughly halved. The effect on the 46 ms mean is not known until measured in production.

### Step 2: document readings

#### What a reading is

The parsers' own outputs for one document, before any gating or aggregation: the C1 resolution and totals, the C21 candidate counts and note, the C11 and C12 GPA bands, average and share submitting, and the facts the schema-fallback note is built from. Projected counts, IPEDS, allowlists and cross-document rules are applied afterwards, in the render, as they are today.

#### What makes a reading valid

A reading is computed from a set of inputs, and is served only when all of them still match:

| Input | Why |
|---|---|
| Canonical, fallback and overlay artifact ids | Which artifacts were read |
| A revision for each of those artifacts | Artifacts can be edited in place: `tools/data_quality/audit_b1_gender_2024.py` rewrites `notes.values` on an existing row. A new `revision` column on `cds_artifacts`, raised by a trigger on update, makes that visible |
| The document's `canonical_year` | C1 rejects some older layouts by year; C21 switches field ids at 2025; the fallback note takes the year |
| Overlay serving classes (PRD 038) | They change which values are merged |
| `reader_version` | Bumped when a parser changes; a test fails when a parser file changes without a bump |

These are hashed into one `input_fingerprint`.

#### Storage

```sql
create table public.cds_document_readings (
  document_id       uuid        not null references public.cds_documents(id) on delete cascade,
  input_fingerprint text        not null,
  reader_version    text        not null,
  reading           jsonb       not null,
  computed_at       timestamptz not null default now(),
  primary key (document_id, input_fingerprint)
);
```

Rows are never updated. A different fingerprint is a different row, so two deployments with different reader versions, or two renders racing, cannot overwrite each other. A cleanup step in the backfill script deletes rows whose fingerprint is no longer current.

Publicly readable (owner decision): `revoke all … from public, anon, authenticated`, then `grant select` to `anon, authenticated` and `grant all` to `service_role`; RLS on with one SELECT policy.

#### Selecting the current inputs

One database function, `cds_reading_inputs(p_document_ids uuid[])`, returns for each document the artifact ids and revisions the web app would select, and the matching stored reading if there is one.

It must reproduce the web app's selection rules exactly, which differ from the existing SQL view `cds_selected_extraction_result`:

- the newest canonical artifact regardless of producer;
- the newest fallback artifact, dropped if it does not match the canonical one;
- the overlay candidate chosen by schema version, recorded source hash and `held = false`, which can be an older row behind newer rejected ones.

Whether the fingerprint tracks the eligible overlay or only one that contributes values is settled in Phase 2a, with fixtures. So is an index to support the function; the existing one is `(document_id, kind, created_at desc)`. The function's plan and timing are measured for a 28-document school before anything depends on it.

#### Read path

```
1. call cds_reading_inputs for the page's documents
2. for each document:
     stored reading for the current fingerprint  -> use it
     otherwise -> fetch exactly the artifact ids from step 1 (not through the
                  7-day cache), compute the reading, use it, and store it
3. apply gating, projection fallback and aggregation as today
```

Fetching by exact id matters: `fetchExtract` sits behind a 7-day cache keyed by document, and pairing a fresh fingerprint with a cached older artifact would store a wrong reading under a valid key. The outer `fetchAcceptanceHistory` cache key gains the reader version and serving classes for the same reason.

#### Writing from a page render (owner decision: fill on read)

- A separate server-only client holds the service-role key. The anon client cannot write (#337).
- The key is present in Vercel production. CI and local builds do not have it; with no key, nothing is written and the page renders as today.
- The write runs after the response through Next's `after`, with caching disabled and a 2-second budget. Its failure is logged and ignored: the render already has its answer.
- School pages are static with on-demand regeneration, so fills happen during regeneration, not on every visit.

#### Failure behaviour

If the function call fails or times out, a stored row is malformed, or anything in the readings path throws, the page uses today's path for that render. `DOCUMENT_READINGS_MODE=off|shadow|on` controls the whole of step 2.

### Optional later step: one call for the rest

With artifacts out of the hub path, about 12 small reads remain. A Postgres function could return them in one round trip. Decided from measurements after step 2; those reads are indexed lookups under 1 ms each in `pg_stat_statements`.

## Milestones

### Phase 0: baseline and benchmark (about half a day)

- Freeze a benchmark slice of 60 distinct schools: all schools on the early-decision and GPA pilot lists, 10 acceptance-rate pilot schools, 10 with a scholarship record, the 10 with the most documents, 10 with exactly one document, and the rest chosen at random with a fixed seed. Check the list in.
- Freeze the inputs: export, for those schools, the artifacts, documents, projected rows and IPEDS rows the pages read, to a local fixture (not committed; artifacts are large).
- Record a baseline from the current code against that fixture: for every school, the full acceptance, early-decision and GPA histories, the hub's derived values, and the rendered text of the hub and three pilot pages.
- **Exit:** the baseline is reproducible (two runs are byte-identical).

### Phase 1: narrow the read (about 1 day)

- Implement step 1 behind `ARTIFACT_READ_MODE`.
- **Exit to `narrow`:** output for all 60 schools is byte-identical to the baseline.
- **After `narrow`:** for 20 controlled cold renders of fixed hub and year pages, before and after, report artifact requests, response bytes and origin time per render from the gateway logs (requests are attributed by a marker header the web tier adds).
- **Decision:** if the canonical read's share of database time falls below half, stop here and close the issue.

### Phase 2a: prove the reading and the selector (about 1 day)

- Typed `Reading`, `readDocument(extract, yearStart)`, and the pages refactored to compute through it. No table.
- `cds_reading_inputs` with fixtures for each selection rule above, its query plan, and its timing for a 28-document school.
- **Exit:** output for all 60 schools is byte-identical to the baseline; the function agrees with the web app's selection for every document in the slice; reading size is reported (stop if the median is over 4 KB).

### Phase 2b: store and serve (about 2 days)

- Migrations (`revision` on `cds_artifacts`, the readings table, the function), the server-only writer, the read path, a resumable backfill script with retry.
- Backfill cost is about three artifact requests per document (canonical, fallback, overlay page), 5,325 documents, paced.
- `shadow` in production for 3 days. Each comparison records a counter: compared, matched, mismatched, reading missing, reading stale, error. Mismatches also go to Sentry with the JSON paths that differ.
- **Exit to `on`:** at least 1,000 comparisons, covering every school in the slice, with zero mismatches and zero errors.
- **After `on`:** the same 20 controlled cold renders show zero artifact requests for hub pages whose readings exist.

### Phase 3: decide on the single call

Defined before measuring: build it only if, in the week after Phase 2b, any hour shows more than 100 PostgREST 503s attributable to hub renders, or gateway p95 for web-tier requests over 1 s in any hour with more than 5,000 requests.

## Start gate

Do not start before 2026-11-24. PR #336 shipped on 2026-11-17 and changes how often cold renders happen. The first task is a comparison of the week after it with Nov 5–17: requests per hour, 503s, p95, and the share of database time taken by the artifact read. If bursts are gone, this work is routine, not urgent; it is still worth doing because the artifact read is most of the database time either way.

## Decisions

Recorded 2026-11-17:

1. **Fill on read** (owner). Readings are computed and stored the first time a document is rendered, not built on write.
2. **Publicly readable** (owner). The readings table is readable with the public key, like the data it is derived from.

Open:

3. **Review size.** Phases 1, 2a and 2b are separate PRs. 2b is estimated at 500–800 changed lines including two migrations and needs owner review.
4. **Editing artifacts in place.** This design tolerates it through the `revision` column. The alternative is to forbid it and convert the one repair script that does it.

## Risks

| Risk | Mitigation |
|---|---|
| A parser changes and old readings are served | `reader_version` is in the fingerprint; a test fails when a parser file changes without a bump |
| An artifact is edited in place | `revision` is in the fingerprint |
| The selector disagrees with the web app's selection | Fixtures per rule and a full-slice agreement check in Phase 2a |
| The selector is slow | Plan and timing measured in Phase 2a before anything depends on it |
| A narrow select omits a key some code reads | Test that ties the select list to the keys read; byte-identical baseline |
| The write is lost, slow or rejected | Best effort after the response; the next regeneration tries again |
| No service key in an environment | No writes; pages render as today |
| The backfill loads the database | Paced and resumable; about 16,000 requests in total, spread out |

## What the reviews changed

**First draft: whole-page payloads (reviewed by Gemini 4 Hydrogen).** One JSON payload per school, rebuilt by a new route whenever data changed. The review found:

- a stored page payload does not expire, so changes no hook reports (coverage wording, federal loads, the scholarship cycle rolling over on July 1) stay wrong until a full rebuild;
- the builder would read through a 7-day cache and could store week-old data;
- the worker waits 5 seconds for the refresh call, and building 100 schools inside it does not fit;
- a full rebuild is about 3,000 schools, close to an hour;
- a payload row cannot say a school now redirects or returns 404;
- the exit criteria could not fail.

It suggested storing only the small values derived from the artifact.

**Second draft: per-document readings holding final values (reviewed by Codex).** The review found:

- the validity rule was wrong: final counts and page-exists flags also depend on projected rows, IPEDS, allowlists and cross-document rules, so identical artifacts can produce different correct values. Readings now hold parser output only;
- parsers need the document year, which was not an input;
- artifact ids are not content revisions, because one repair script edits artifacts in place;
- "one cheap read of newest ids" was not expressible as described, and the overlay selection rule needs values an id-only read does not have. It is now an explicit function with fixtures;
- the existing SQL view selects artifacts by different rules from the web app;
- filling through the cached loader could store an older artifact's reading under a current key;
- a single row per document can be overwritten by an older deployment. Rows are now keyed by fingerprint;
- the exit criteria again could pass without proving anything: a JSON round trip tests serialization, zero mismatch events can mean zero comparisons, and weekly request counts do not isolate the change.

It also suggested measuring a narrow artifact read first. That measurement is in this document and became step 1.

## How measured

- **Reads per page, bursts, 503s:** Supabase Management API `GET /v1/projects/<ref>/analytics/endpoints/logs`, table `logs`, `source = 'edge_logs'`, grouped by `log_attributes['request.path']`, windows as stated.
- **Query time:** `extensions.pg_stat_statements`, statements matching the PostgREST shape for each table.
- **Artifact sizes:** `octet_length` of `notes::text`, `notes->>'markdown'` and `notes->'values'` for the newest canonical artifact per document.
- **Counts:** `cds_manifest`, `institution_cds_coverage`, `web/src/lib/acceptance-pilot.ts`.
- **What the hub takes from the artifact:** reading the two files named above, and the review.

- **Narrow read timing and key sizes:** a `do` block timing 200 randomly chosen newest canonical artifacts three ways inside the database, and `jsonb_each` over the same sample.
- **Which `notes` keys the web app reads:** grep of `notes.<key>` under `web/src`, tests excluded.

Not measured: the production effect of the narrow read; the size of a reading; reads per render for the three pilot pages; the selector's plan and timing; whether the service-role key is present in every Vercel environment (it is listed for production); how much of the crawl hits expired pages versus pages never rendered. Gateway logs record database paths, not which page caused them, so "reads per hub render" is inferred from a minute dominated by hub renders.
