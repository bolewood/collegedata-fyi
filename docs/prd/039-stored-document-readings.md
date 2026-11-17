# PRD 039: Stored document readings for school pages

**Status:** Draft for owner review. Work starts no earlier than 2026-11-24 (see [Start gate](#start-gate)).
**Created:** 2026-11-17
**Author:** Claude. A first draft (whole-page payloads) was reviewed by Gemini 4 Hydrogen and replaced by this design; see [What the review changed](#what-the-review-changed). This revision has not had a second review.
**Related:** [PRD 002: frontend](002-frontend.md), [PRD 038: template overlay extraction](038-template-overlay-extraction.md), PRs #236, #262, #333–#338

---

## Summary

A cold school hub page asks the live database about 21 questions. One of them, fetching a whole extraction artifact, is about 85% of the database time, and the hub page uses almost none of what it fetches: from a median 355 KB row it derives three yes/no flags, three counts and one note.

This PRD stores those small derived values, called **document readings**, one row per document, the first time they are computed. Later renders read the stored row and never fetch the artifact. A second, optional phase folds the page's remaining small reads into one database call.

Phase 0 proves the readings are identical to what the page computes today, on a frozen set of 50 schools, before anything is served from them.

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

### What the hub page takes from it

Read from `web/src/app/schools/[school_id]/page.tsx` and `web/src/lib/acceptance-history-data.ts`:

| Use | Loader | Documents read | Result |
|---|---|---|---|
| Schema-fallback note | `fetchExtract` → `schemaFallbackNoteFromArtifact` | newest extracted | one string or null |
| Printed C1 counts for the headline | `gatedYearFacts` → `printedCountsForDocument` | one | three integers |
| Whether the acceptance-rate, early-decision and GPA pages exist | `fetch*PageServed` → `fetchAcceptanceHistory` | every candidate year, pilot schools only | three booleans |

The parsers behind these (`c1-headline-totals.ts`, `c11-gpa.ts`, `c21-ed-counts.ts`, `c21-ed-note.ts`) read both `values` and the document text. Their outputs are small objects.

The **year page** is different: it shows the document itself (`MarkdownView` renders the full text and offers it as a download). It needs the artifact and stays as it is.

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

1. A hub render does not fetch an artifact when readings exist for its documents.
2. What the page shows is unchanged. A parity check proves it before any switch.
3. Nothing gets staler than it is today. A reading depends only on the artifacts it was computed from, so it is correct for as long as those artifacts are the newest.
4. Rollback is one environment variable.

## Non-goals

- Whole-page payloads. The first draft proposed them; see [What the review changed](#what-the-review-changed).
- The year page, the CSV and XLSX downloads and the facts API. They serve the document's contents and keep reading the artifact.
- Changing hosts, object storage or a CDN for data.
- The public PostgREST API and its rate limits.

## Design

### 1. What a reading is

One row per document, holding everything the hub and the three pilot pages derive from that document's artifacts:

```sql
create table public.cds_document_readings (
  document_id           uuid        primary key references public.cds_documents(id) on delete cascade,
  canonical_artifact_id uuid        not null,  -- the artifacts this was computed from
  fallback_artifact_id  uuid,
  overlay_artifact_id   uuid,
  overlay_serve_key     text        not null default '',  -- PRD 038 serving classes in force
  reader_version        text        not null,  -- bumped when a parser or the shape changes
  reading               jsonb       not null,  -- c1, c11, c21, schema-fallback inputs; a few hundred bytes
  computed_at           timestamptz not null default now()
);
```

Privileges follow the recent convention: `revoke all … from public, anon, authenticated`, then `grant select` to `anon, authenticated` and `grant all` to `service_role`; RLS on with one SELECT policy. The readings are derived from already-public data.

A reading is valid when its three artifact ids, `overlay_serve_key` and `reader_version` match the current ones. Nothing else can make it stale: federal loads, coverage refreshes, scholarship changes and the date do not touch it.

### 2. One implementation, in TypeScript

`readDocument(extract)` is a pure function that runs the existing parsers on one document's merged extract and returns the reading object. The pages already call these parsers; this gathers the calls behind one function with a serializable result. There is no copy in Python or SQL.

### 3. Read path

```
1. cheap read: the newest canonical, fallback and overlay artifact ids for the page's documents
               (ids and producer only, never notes)
2. cheap read: the readings for those documents
3. for each document:
     reading present and valid  -> use it
     otherwise                  -> fetch the artifact as today, compute the reading,
                                   use it, and store it (best effort, service role)
```

So readings fill themselves in the first time each document is rendered and repair themselves when an artifact or the reader changes. No build route, no hooks in the worker or loaders, no sweep changes.

Step 1 replaces up to 28 full-artifact reads for a pilot school with one read of ids. The write in step 3 is an idempotent upsert; two renders computing the same reading write the same row.

Controlled by `DOCUMENT_READINGS_MODE`:

- `off`: today's behaviour.
- `shadow`: compute as today, also read the stored reading, record whether they match, serve today's result. Fill missing rows.
- `on`: serve from readings as above.

### 4. Backfill

A script computes readings for all 5,325 extracted documents at two per second (about 45 minutes, one artifact read each, spread evenly). Without it, `on` still works; each document just costs one last artifact read.

### 5. Recording parity in shadow

Mismatches go to Sentry as one event per document with the JSON paths that differ (no values). A count per day is the exit measure. Workflow logs are public and are not used for this.

### 6. Optional second step: one call for the rest

With artifacts out of the hub path, about 12 small reads remain (documents, coverage, scorecard, federal facts, merit profile, change events, nonpayment, brand colours, browser row, scholarships). A Postgres function `school_hub_data(p_school_id)` could return them in one round trip. Whether that is worth building is decided from measurements after Phase 1, not now: those reads are indexed lookups under 1 ms each in `pg_stat_statements`, and the gain is fewer connections, not less work.

## Milestones

### Phase 0: prove the reading (about 1 day)

- Freeze a benchmark slice of 50 distinct schools, filled in this order so groups do not overlap: 10 acceptance-rate pilot schools, 10 with a scholarship record, 10 with the most documents, 10 with exactly one document, 10 more chosen at random with a fixed seed. Check the list in.
- Write `readDocument` and refactor the hub's three uses to go through it. No table, no behaviour change.
- Parity script: for every document of the 50 schools, compare the reading computed fresh with the same reading after a JSON round trip, and compare the hub's derived values (note, counts, three flags) before and after the refactor.
- **Exit:** zero differences. Any difference is fixed or listed by JSON path in an allowlist in the PR. Report the size distribution of `reading`; if the median is over 4 KB, stop and revisit what is in it.

### Phase 1: store and serve (about 2 days)

- Migration, read path, backfill script, `DOCUMENT_READINGS_MODE`.
- Run the backfill, then `shadow` in production for 3 days.
- **Exit to `on`:** zero mismatch events over the shadow period.
- **After `on`:** over 24 hours, `cds_artifacts` requests from the web tier that select `notes` drop by at least 80% against the week before (gateway logs, by request URL). Year pages and downloads account for the remainder.

### Phase 2: decide on the single call

Compare a week of gateway logs with Nov 5–17 and with the week before Phase 1. Build `school_hub_data` only if hub renders still cause 503s or p95 over 1 s during bursts.

## Start gate

Do not start before 2026-11-24. PR #336 shipped on 2026-11-17 and changes how often cold renders happen. The first task is a comparison of the week after it with Nov 5–17: requests per hour, 503s, p95, and the share of database time taken by the artifact read. If bursts are gone, this work is routine, not urgent; it is still worth doing because the artifact read is most of the database time either way.

## Decisions for the owner

1. **Fill on read or build on write.** Recommended: fill on read, as designed. It needs no hooks and cannot miss a write path. The cost is that a page render performs a database write the first time a document is seen. The alternative is to have the extraction worker ask the web app to compute readings after each run.
2. **Who can read the table.** Recommended: public, like the data it is derived from. The alternative is service-role only, with the web app reading it through the service key.
3. **Review size.** Phase 0 and Phase 1 are separate PRs. Phase 1 is estimated at 400–700 changed lines and needs owner review.

## Risks

| Risk | Mitigation |
|---|---|
| A parser changes and old readings are served | `reader_version` is part of validity; a test fails when a parser file changes without a bump |
| The reading misses something a page needs | Phase 0 routes all three uses through `readDocument`, so a missing value fails parity |
| Writing from a page render fails or is slow | Best effort with a short timeout; the page already has its answer and renders regardless |
| The cheap id read is not cheap | It selects ids only; measured in Phase 0 against the largest school (28 documents) |
| Overlay serving classes change (PRD 038) | `overlay_serve_key` is part of validity |
| The backfill loads the database | Two documents per second, about one artifact read each; less than one crawl minute per minute |

## What the review changed

The first draft stored one JSON payload per school holding everything the hub shows, rebuilt by a new route whenever data changed. Gemini 4 Hydrogen's review found that design had problems this one avoids:

- **Staleness without a bound.** A stored page payload does not expire. Changes that no hook reports (coverage wording, federal loads, the scholarship cycle rolling over on July 1) would have stayed wrong until a full rebuild. Readings depend only on artifacts.
- **Stale inputs.** The builder would have called loaders that sit behind a 7-day cache and could have stored week-old data.
- **Timeouts.** The worker waits 5 seconds and the loader workflow 20 for the refresh call; building 100 schools inside that call would not fit.
- **Rebuild cost.** A full rebuild is about 3,000 schools, not 772, close to an hour at one per second.
- **Removed schools.** A payload row had no way to say a school now redirects or returns 404.
- **Uncheckable milestones.** The first draft compared the builder with the loaders it wrapped, which tests nothing, and its "explained differences" exit could not fail.

It also corrected two facts: `c1-headline-totals.ts` parses document text too, and the year page renders the whole document, so what it needs from the text was never an open question.

The review suggested this design's core idea: store only the small values derived from the artifact, and optionally fetch the rest in one call.

## How measured

- **Reads per page, bursts, 503s:** Supabase Management API `GET /v1/projects/<ref>/analytics/endpoints/logs`, table `logs`, `source = 'edge_logs'`, grouped by `log_attributes['request.path']`, windows as stated.
- **Query time:** `extensions.pg_stat_statements`, statements matching the PostgREST shape for each table.
- **Artifact sizes:** `octet_length` of `notes::text`, `notes->>'markdown'` and `notes->'values'` for the newest canonical artifact per document.
- **Counts:** `cds_manifest`, `institution_cds_coverage`, `web/src/lib/acceptance-pilot.ts`.
- **What the hub takes from the artifact:** reading the two files named above, and the review.

Not measured: the size of a reading; reads per render for the three pilot pages; how long the id read takes for a 28-document school; how much of the crawl hits expired pages versus pages never rendered. Gateway logs record database paths, not which page caused them, so "reads per hub render" is inferred from a minute dominated by hub renders.
