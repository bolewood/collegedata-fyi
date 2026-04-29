# PRD 015: Institution directory and CDS coverage transparency

**Status:** Shipped (M0–M6) 2026-04-29; M7 (first-party submission backend) deferred to backlog under "trigger-on-volume"
**Created:** 2026-04-29
**Updated:** 2026-04-29
**Author:** Codex + Anthony
**Related:** [PRD 001](001-collegedata-fyi-v1.md), [PRD 002](002-frontend.md), [PRD 009](009-last-mile-ci-and-preservation.md), [PRD 010](010-queryable-data-browser.md), [Scorecard pipeline](../../tools/scorecard/README.md), [Archive pipeline](../archive-pipeline.md)

---

## Context

collegedata.fyi currently feels comprehensive only when we have archived Common
Data Set documents for a school. If a user searches for a school that is known
to exist but has no CDS in our archive, the product often behaves like the
school is absent from the database entirely.

That is the wrong trust signal.

The stronger product stance is:

1. We know the institution exists.
2. We can show baseline federal data for it.
3. We can tell the user whether we found a public CDS, failed to extract one,
   could not access one, or have not checked yet.
4. We can show public-safe evidence and invite correction.

The existing Scorecard pipeline already gives us a strong base:
`scorecard_summary` contains one row per IPEDS UNITID for every Title-IV
institution in the loaded College Scorecard vintage. The missing layer is a
first-class institution directory plus a first-class CDS coverage state.

The product effect should be: searching for "Rice" never returns silence. It
returns Rice University, federal baseline data, and an honest CDS availability
message.

## Problem

### 1. Silent absence looks like an incomplete database

When search returns nothing for a known school, users cannot tell whether:

- we do not know the school exists
- the school publishes no public CDS
- the school publishes one but we have not found it
- the school publishes one behind an access barrier
- our extractor failed
- the school is outside the intended product scope

That ambiguity weakens credibility.

### 2. CDS coverage is not modeled as product data

Coverage currently exists implicitly across `cds_documents`, archive queue
state, source URLs, extraction status, and `schools.yaml`. There is no single
status that can power search, school pages, coverage dashboards, or public API
consumers.

### 3. Scorecard-only institutions have no discovery history yet

The current archive/discovery tables only cover the `schools.yaml` universe.
If we add all in-scope Scorecard institutions to search without first enqueueing
them for discovery, most will honestly be `not_checked`, not
`no_public_cds_found`. The product must not imply "we looked and did not find a
CDS" for schools that have never entered the resolver.

## MVP Scope Decision

MVP institution universe:

> Active, undergraduate-serving, degree-granting Title-IV institutions in the
> loaded College Scorecard institution file.

Public default filters:

- `CURROPER = 1` active/currently operating
- `UGDS > 0` undergraduate-serving
- `ICLEVEL in (1, 2)` four-year or two-year institution
- `PREDDEG in (2, 3, 4)` predominant degree is associate, bachelor's, or graduate
  degree; graduate-predominant rows stay only if `UGDS > 0`
- Scorecard row exists, giving us Title-IV / federal data backbone

Explicit default exclusions:

- closed institutions
- administrative/system offices with no undergraduate enrollment
- non-degree / certificate-only institutions
- foreign locations
- institutions missing both undergraduate enrollment and degree-level signal
- rows we cannot assign a stable public slug

This scope must be implemented before search or coverage stats. Directory
counts, "not checked" semantics, and missing-CDS percentages are meaningless
until the in-scope universe is fixed.

## Goals

1. Make the site feel comprehensive by giving every in-scope institution a
   searchable identity page, even when CDS data is missing.
2. Replace silent search failures with explicit CDS coverage states.
3. Use College Scorecard data as baseline context for schools without CDS data.
4. Add user-facing language that creates accountability pressure without making
   claims we cannot prove.
5. Expose public-safe coverage status through the API so researchers can
   distinguish missing, failed, blocked, and not-yet-checked cases.
6. Create a contribution path for users who know where a missing CDS is hosted.

## Non-goals

1. Do not claim that a school "does not publish a CDS" unless a human has
   verified that assertion.
2. Do not label Scorecard-only institutions as `no_public_cds_found` until they
   have had a resolver attempt.
3. Do not expose raw resolver diagnostics, hosting observations, private notes,
   WAF details, or operator commentary in the public API.
4. Do not scrape or extract full Docling corpus work in PR CI.
5. Do not build a full community moderation system in the first slice.
6. Do not replace College Scorecard or IPEDS. Scorecard remains baseline
   federal context; CDS remains the richer voluntary dataset.
7. Do not expose a ranking or editorial judgment about schools. The product can
   be pointed without being reckless.

## Product Principle: Pressure, Not Libel

The working internal phrase is "shaming section," but the user-facing product
should use disciplined transparency language.

Good:

- "No public CDS found"
- "We could not find a public Common Data Set for this school in our latest scan."
- "A CDS may exist, but we have not located a public source yet."
- "If you know where this school publishes its CDS, send us the link."
- "Last checked April 2026."

Avoid:

- "This school refuses to publish a CDS."
- "This school hides its data."
- "Non-transparent."
- "Bad actor."

The sharper product move is not accusatory copy. It is making absence visible,
evidence-backed, and shareable.

## User Stories

### Primary

1. A prospective student searches for Rice University and gets a school result
   instead of an empty state.
2. A parent sees baseline federal outcomes for a school even when CDS fields
   are unavailable.
3. A journalist can filter for prominent schools where no public CDS was found
   after a real scan.
4. A counselor can explain why a school has fewer fields than peer schools.
5. A school staff member can submit the correct CDS URL if our scan missed it.

### Internal

1. An operator can see which in-scope institutions are `not_checked`,
   `no_public_cds_found`, `source_not_automatically_accessible`, or
   `extract_failed`.
2. A data-quality pass can target high-enrollment / high-interest schools with
   missing CDS first.
3. The archive resolver can record internal evidence that feeds sanitized
   product copy.

## Directory Data Model

### `institution_directory`

Create a new table keyed by IPEDS UNITID. Do not overload `scorecard_summary`;
that table should stay focused on curated outcome metrics.

```text
institution_directory
  ipeds_id text primary key
  school_id text unique not null
  school_name text not null
  aliases text[] not null default '{}'
  city text
  state text
  zip text
  website_url text
  scorecard_data_year text not null
  undergraduate_enrollment int
  control int
  institution_level int
  predominant_degree int
  highest_degree int
  currently_operating boolean
  main_campus boolean
  branch_count int
  latitude numeric
  longitude numeric
  in_scope boolean not null
  exclusion_reason text
  directory_source text not null default 'scorecard'
  refreshed_at timestamptz not null default now()
```

Scorecard source columns for MVP loader:

| Directory field | Scorecard CSV column |
|---|---|
| `ipeds_id` | `UNITID` |
| `school_name` | `INSTNM` |
| `city` | `CITY` |
| `state` | `STABBR` |
| `zip` | `ZIP` |
| `website_url` | `INSTURL` |
| `undergraduate_enrollment` | `UGDS` |
| `control` | `CONTROL` |
| `institution_level` | `ICLEVEL` |
| `predominant_degree` | `PREDDEG` |
| `highest_degree` | `HIGHDEG` |
| `currently_operating` | `CURROPER` |
| `main_campus` | `MAIN` |
| `branch_count` | `NUMBRANCH` |
| `latitude` | `LATITUDE` |
| `longitude` | `LONGITUDE` |

Loader requirements:

- Reuse `refresh_summary.py`'s UNITID normalization: cast to integer when
  possible, then zero-pad to at least six characters.
- Keep a required-column set for directory fields, separate from
  `scorecard_summary`'s metric columns.
- Abort on Scorecard schema drift with a clear missing-column list.
- Upsert by `ipeds_id`.
- Write a small refresh summary: total rows, in-scope rows, excluded rows by
  reason, slug collisions, and rows without usable website URL.
- Commit the loader and migration. Do not commit the raw Scorecard CSV.

## Slug and Crosswalk Rules

Existing public routes are slug-based. Scorecard rows do not provide stable
site slugs, so slug creation is a first-class milestone.

Rules:

1. If an IPEDS ID already appears in `schools.yaml`, preserve that canonical
   `school_id`.
2. If multiple `schools.yaml` IDs map to one IPEDS ID, choose the active
   canonical parent and store the rest as aliases or redirects after manual
   review.
3. For new Scorecard-only rows, generate a deterministic slug from `INSTNM`.
4. Detect slug collisions before writing:
   - same name in multiple states: append `-{state}`.
   - same name and state: append `-{city}`.
   - still colliding: append `-{ipeds_id}`.
5. Store aliases for common normalized names and prior slugs.
6. Add redirects for any existing public slug that changes.
7. Do not publish directory rows that fail slug assignment.

Deliverables:

- `institution_slug_crosswalk` table or generated artifact:

```text
institution_slug_crosswalk
  ipeds_id
  school_id
  alias
  source
  is_primary
  reviewed_at
```

- collision report checked into `scratch` or emitted by the loader
- tests for deterministic slug generation and collision handling

## Discovery Coverage Path

Coverage claims require resolver attempts. M1/M2 cannot infer
`no_public_cds_found` for Scorecard-only institutions from absence alone.

Add an explicit enqueue path for in-scope directory institutions:

1. Generate resolver seeds from `website_url` / `INSTURL` plus existing
   `schools.yaml.discovery_seed_url` when present.
2. Enqueue in-scope institutions that have no `cds_documents` row and no recent
   archive attempt.
3. Use conservative limits in ops runs; do not fan out the whole Scorecard
   universe in PR CI.
4. Persist attempt state even when no CDS candidate is found.
5. Only after a resolver attempt can an institution move from `not_checked` to
   `no_public_cds_found` or `source_not_automatically_accessible`.

This is the key honesty constraint: the directory can launch before every
institution is checked, but the missing-CDS language must say "not checked yet"
until discovery actually runs.

## Coverage Status Model

Coverage is year-aware. The status should consider:

- `latest_available_cds_year`: newest year with usable extracted CDS data
- `latest_found_cds_year`: newest year where a source document was found
- `latest_attempted_year`: newest year or cycle attempted by discovery
- `latest_attempt_status`: resolver/extraction outcome for that newest attempt
- `latest_field_count`: selected extraction field count for the latest available
  CDS

Initial public statuses:

| Status | Meaning | Product copy direction |
|---|---|---|
| `cds_available_current` | Newest found/attempted year has a usable selected extraction. | "CDS available" |
| `cds_available_stale` | Older CDS is usable, but the newest expected/attempted year is missing, failed, or not found. | "Older CDS available" |
| `cds_found_processing` | Newest source is found but extraction has not completed. | "CDS found; processing" |
| `latest_found_extract_failed_with_prior_available` | Newer source failed extraction, but older usable CDS exists. | "Latest CDS needs review; older CDS available" |
| `extract_failed` | Source found and extraction failed, with no prior usable CDS. | "CDS found; extraction needs review" |
| `source_not_automatically_accessible` | Public label for sources/resolver paths that could not be accessed automatically. | "Source could not be accessed automatically" |
| `no_public_cds_found` | Resolver ran and found no credible public CDS candidate. | "No public CDS found in latest scan" |
| `verified_absent` | Human or corpus metadata says CDS is absent/not applicable. | "CDS not published or not applicable" |
| `not_checked` | Institution is in scope, but resolver has no recent attempt. | "Not checked yet" |
| `out_of_scope` | Institution exists in Scorecard but is excluded from MVP. | Hidden by default |

Internal subreasons may include `auth_wall`, `waf_blocked`, `timeout`,
`dead_url`, `wrong_content_type`, and `no_candidate_links`. Public copy should
not expose those raw labels by default.

### Status Precedence

Compute status around the newest attempted/found year, not merely "any extracted
row exists."

1. Manual `verified_absent` override wins when present.
2. If there is a usable extraction for the newest found/attempted qualifying
   year, status is `cds_available_current`.
3. If the newest found source is processing, status is `cds_found_processing`.
4. If the newest found source failed extraction and an older usable extraction
   exists, status is `latest_found_extract_failed_with_prior_available`.
5. If the newest found source failed extraction and no older usable extraction
   exists, status is `extract_failed`.
6. If no source was found in the latest discovery attempt and an older usable
   extraction exists, status is `cds_available_stale`.
7. If no source was found in the latest discovery attempt and no usable
   extraction exists, status is `no_public_cds_found`.
8. If latest resolver evidence says the source/path could not be accessed
   automatically, status is `source_not_automatically_accessible`, unless an
   older usable extraction exists, in which case use `cds_available_stale` with
   an inaccessible-latest note.
9. If there is no resolver attempt, status is `not_checked`.

Tests must cover old extracted + newer failed, old extracted + newer missing,
processing with prior extraction, and Scorecard-only no-attempt rows.

## Public-Safe Coverage Table

Prefer a materialized serving table, not a deep SQL view, for search and public
API usage.

```text
institution_cds_coverage
  ipeds_id text primary key
  school_id text unique not null
  school_name text not null
  aliases text[] not null
  city text
  state text
  website_url text
  undergraduate_enrollment int
  scorecard_data_year text
  coverage_status text not null
  coverage_label text not null
  coverage_summary text not null
  latest_available_cds_year text
  latest_found_cds_year text
  latest_attempted_year text
  latest_document_id uuid
  latest_public_source_url text
  latest_field_count int
  last_checked_at timestamptz
  can_submit_source boolean not null
  search_text text not null
  updated_at timestamptz not null
```

Public API rules:

- Enable RLS and grant read access only to this sanitized table/view.
- Do not expose `school_hosting_observations` directly.
- Do not expose raw resolver notes, internal `notes`, WAF/auth-wall details,
  error stack traces, or operator comments.
- `latest_public_source_url` is allowed only when it is already a public source
  URL we would show elsewhere.
- `coverage_summary` is generated from a fixed copy map, not free-form notes.

Refresh triggers:

- after Scorecard directory loads
- after archive discovery drains
- after extraction worker drains
- after manual coverage overrides

Indexes:

- unique `ipeds_id`
- unique `school_id`
- btree `(coverage_status)`
- btree `(state)`
- btree `(undergraduate_enrollment)`
- generated/search column for name + aliases

## Manual Overrides

Add an override table for human-reviewed public claims:

```text
institution_cds_coverage_overrides
  ipeds_id
  school_id
  status
  public_note
  evidence_url
  reviewed_by
  reviewed_at
```

Use overrides for `verified_absent`, source URL corrections, and rare cases
where automated resolver state is misleading. Do not use overrides for routine
automated outcomes.

## Search Behavior

Search should query `institution_cds_coverage`, not only CDS-backed rows.

Result behavior:

1. Exact or high-confidence name matches should always appear if the institution
   is in scope and has a published slug.
2. Results with CDS data should show the latest available CDS year and key
   available metrics.
3. Results without CDS data should still show Scorecard context and a coverage
   badge.
4. Empty state should mean "we do not track this institution," not "we did not
   find a CDS for it."

Recommended result badges:

- `CDS available`
- `Older CDS available`
- `CDS processing`
- `CDS found with gaps`
- `No public CDS found`
- `Source could not be accessed automatically`
- `Not checked yet`

## School Page Behavior

Every in-scope institution with a stable slug gets a page.

For schools with CDS:

- Keep the existing school detail experience.
- Add a small coverage panel with latest available year, latest attempt status,
  source URL, field count, and last checked date.

For schools without CDS:

- Show school name, location, Scorecard baseline metrics, and source/vintage.
- Show a clear CDS coverage panel.
- Include a source-submission CTA.
- Link to methodology explaining automated discovery and false negatives.

Example copy for a missing-CDS school:

> We could not find a public Common Data Set for Rice University in our latest
> scan. A CDS may exist somewhere we did not locate. We still show baseline
> federal data from College Scorecard. If you know where Rice publishes its CDS,
> send us the link.

Example copy for a not-yet-checked school:

> Rice University is in our institution directory, but we have not completed a
> public CDS scan for it yet. We show baseline federal data from College
> Scorecard until CDS coverage is checked.

Example copy for automated access failure:

> We found a possible CDS source, but it could not be accessed automatically.
> We show federal Scorecard data until a public source can be verified.

## Coverage Page

Add a public coverage page after the directory and coverage table are live.

Possible routes:

- `/coverage`
- `/coverage/missing-cds`
- `/schools?coverage=no_public_cds_found`

MVP sections:

1. Overall coverage stats:
   - in-scope institutions
   - CDS available
   - older CDS available
   - found but processing/failed
   - no public CDS found
   - source could not be accessed automatically
   - not checked yet
2. Missing-CDS table:
   - school
   - state
   - enrollment
   - coverage status
   - last checked
   - submit link
3. Methodology note:
   - CDS is voluntary
   - automated discovery can miss buried sources
   - `not_checked` means we know the school exists but have not scanned it
   - Scorecard data comes from federal sources and has a different vintage

This page is where the accountability pressure lives. It should be factual,
sortable, and easy to share.

## API Surface

Expose:

```text
/rest/v1/institution_directory
/rest/v1/institution_cds_coverage
```

Keep `scorecard_summary` as the lower-level Scorecard metric table. Keep
`cds_scorecard` as the CDS-document join. The new coverage API answers a
different question: "What do we know about this institution's CDS availability?"

## Implementation Milestones

> **Status legend:** ✅ shipped (with PR + commit reference) · 🗂 deferred to backlog · ⏳ in flight

### M0: Scope and Status Contract ✅ shipped 2026-04-29

- Lock MVP scope to active, undergraduate-serving, degree-granting Title-IV
  institutions.
- Encode public exclusions.
- Finalize the public coverage status vocabulary and precedence.
- Write the public copy map for each status.

### M1: Directory and Slug Substrate ✅ shipped 2026-04-29 (PR #20, hotfix #21)

- Add `institution_directory` migration.
- Add directory loader using the exact Scorecard columns listed above.
- Add schema-drift checks and refresh summary output.
- Add slug/crosswalk generation with collision handling.
- Preserve existing `schools.yaml` slugs where IPEDS IDs match.
- Add tests for slug determinism and collision cases.

**Shipped:** `tools/scorecard/load_directory.py` populates 6,322 directory rows + ~6,500 crosswalk rows on prod. `schools.yaml` self-collision pre-pass picks the largest-UGDS IPEDS as canonical and demotes the rest to auto-slug + state suffix.

### M2: Scorecard-Only Discovery Enrollment ✅ shipped 2026-04-29 (PRs #22, #23)

- Add an enqueue path for in-scope directory institutions missing resolver
  attempts.
- Generate conservative seed URLs from `INSTURL` / `website_url`.
- Persist no-candidate and inaccessible-attempt outcomes.
- Keep run limits operator-controlled; no full discovery drain in PR CI.

**Shipped:** `archive_queue.source` column distinguishes `schools_yaml` from `institution_directory`. `directory-enqueue` edge function (operator-triggered, no cron) seeds the queue with 10/50/100-school batches; first live batch on 2026-04-29 produced 9 `no_public_cds_found` + 1 `transient` outcome — exactly the honest-failure data M3 needs. Pagination hotfix (#23) handled the PostgREST 1K row cap.

### M3: Public-Safe Coverage Table ✅ shipped 2026-04-29 (PRs #24, #25, #26)

- Add `institution_cds_coverage` as a materialized serving table.
- Build refresh job/function from directory + discovery + extraction state.
- Add RLS and public-safe field selection.
- Add status precedence tests.
- Add indexes for search and coverage filters.

**Shipped:** `coverage_status_t` Postgres ENUM (10 values, shared by the materialized table and the override table). `derive_coverage_status()` SQL helper encodes the 9-rule precedence with `archive_queue.last_outcome` as the freshness anchor (a precedence-semantics bug found by the inline self-test on first prod push and fixed in #26: the doc's `cds_year` is NOT the freshness signal — the resolver's most recent attempt is). `refresh_institution_cds_coverage()` does atomic `TRUNCATE+INSERT` inside a single transaction, sub-second lock window. 9-scenario inline self-test guards every status path. 15-minute pg_cron tick on `refresh-coverage` removes one item from the manual operator runbook. Production state at launch: 571 `cds_available_current`, 87 `cds_available_stale`, 136 `no_public_cds_found`, 2,119 `not_checked`.

### M4: Search Over All In-Scope Institutions ✅ shipped 2026-04-29 (PRs #27, #28)

- Change search to query `institution_cds_coverage`.
- Return missing-CDS and not-yet-checked schools as first-class results.
- Add coverage badges to search results.
- Preserve latest-per-school CDS ranking where CDS data exists.

**Shipped:** `search_institutions(p_query, p_limit)` SQL RPC backs the homepage autocomplete; `SchoolSearch` rewritten to call it via debounced (220ms) requests. `CoverageBadge` component maps status → cd-chip variants from `tokens.css`. Decision: search means homepage autocomplete, not `/browse` (filtering by acceptance/yield requires CDS data — schools without CDS would clutter `/browse` rather than help). Cross-linking from search badges back to `/coverage` deferred per scoping. Live: typing "Rice" returns Rice with `cds_available_stale`, "tarrant county" returns `no_public_cds_found` — the PRD's headline product moment.

### M5: Directory-Only School Pages ✅ shipped 2026-04-29 (PR #29)

- Allow school detail routes for directory-only schools.
- Render Scorecard baseline metrics via existing `scorecard_summary` data.
- Add the CDS coverage panel and source-submission CTA.
- Add metadata/OG behavior for directory-only schools.

**Shipped:** `/schools/[school_id]` falls through to `fetchInstitutionCoverage` when `fetchSchoolDocuments` is empty; renders `DirectoryOnlySchoolPage` with name + location + coverage badge + summary + Scorecard `OutcomesSection` + Formspree-backed `SubmissionForm`. Form is env-driven (`NEXT_PUBLIC_FORMSPREE_ENDPOINT`) with mailto fallback to `anthony+collegedata@bolewood.com` so the CTA is never broken.

### M6: Coverage Page ✅ shipped 2026-04-29 (PR #30)

- Build `/coverage` with status counts and sortable missing-CDS table.
- Add filters by state, enrollment band, status, and last checked recency.
- Link coverage status from school pages and search result badges.

**Shipped:** `/coverage` route with histogram banner, virtualized sortable table via `@tanstack/react-virtual` (only ~20 of 2,353 default-filtered rows mount in DOM), URL-persisted filter state for shareable views, methodology note grounding the tone (factual, never alarmist). Default view "missing CDS only"; one-click toggle for full universe. Cross-linking from search badges to `/coverage` was deferred per scoping discussion.

### M7: Submission Path 🗂 deferred to backlog (PR #31)

- MVP: `mailto:` or lightweight form that captures school, URL, and note.
- Later: reuse the public upload/moderation plan from backlog if submissions
  become frequent.
- Store accepted source links as resolver hints, not direct canonical claims,
  until archived and extracted.

**Deferred:** M5 ships a Formspree-backed form that routes submissions to `anthony+collegedata@bolewood.com`. The first-party backend (table + edge function + operator review surface) is on the backlog under "Trigger-on-volume" (`docs/backlog.md`) — build trigger is roughly 10+ submissions/week or first abuse pattern. The M5 `SubmissionForm` is already env-driven so swapping endpoints is a one-config change.

### M8: Ops and Refresh ⏳ partial

- Add an operator report for coverage status deltas after archive drains.
- Add a periodic "not checked recently" report.
- Keep Scorecard refresh annual and separate from CDS extraction drains.
- Do not add full discovery, extraction, or Docling corpus drains to PR CI.

**Status:** The 15-minute `refresh-coverage` cron means coverage state is always current; the per-refresh histogram in the edge function response gives operators a regression signal at a glance. Dedicated operator reports (status deltas, "not checked recently") are not yet built and live on the backlog.

## Design Notes

This is a product trust feature, not just a data plumbing task.

Visual hierarchy:

- Search result: compact badge.
- School page: one explicit coverage panel near the top, not buried below raw
  fields.
- Coverage page: factual accountability table.

Tone:

- "We could not find" is better than "does not publish" for automated states.
- "Not checked yet" must remain visible while the Scorecard-only universe is
  being enrolled into discovery.
- "Last checked" matters as much as the status.
- "Submit a source" turns false negatives into collaboration instead of user
  frustration.

## Edge Cases

1. **Multi-campus systems:** one Scorecard UNITID may not map cleanly to one CDS
   source. Preserve `sub_institutional` and avoid collapsing branch campuses
   without explicit mapping.
2. **Schools with Scorecard rows but no undergraduate CDS relevance:** mark
   `out_of_scope` and hide by default.
3. **Scorecard/CDS name mismatch:** use aliases and IPEDS IDs as the stable join
   key; never rely on name matching alone for writes.
4. **Resolver false negatives:** soften copy, show last checked date, and provide
   a submission path.
5. **Extraction failures:** do not show them as "no CDS found." They are "CDS
   found; extraction needs review."
6. **Old CDS only:** use `cds_available_stale` when a newer expected/attempted
   year is missing or failed but older usable data exists.
7. **Scorecard-only no-attempt rows:** show `not_checked`, never
   `no_public_cds_found`.

## Success Metrics

1. Exact-name searches for known in-scope institutions return a result even
   without CDS.
2. Search no-result rate drops materially.
3. School directory count reflects the fixed in-scope institution universe, not
   only CDS-archived schools.
4. Users can distinguish missing, failed, blocked, stale, and not-yet-checked
   cases.
5. Coverage page becomes a useful operator queue for high-interest missing
   schools.
6. Source submissions produce at least a few corrected resolver hints.

## Open Questions

1. Should the public default include two-year associate institutions, or should
   `/schools` default to four-year while the API includes both?
2. Should `institution_directory` be entirely Supabase-backed, or should a
   generated directory snapshot be committed for reviewability?
3. How aggressive should the coverage page be in default sorting: enrollment,
   search popularity, selectivity, or missing-status recency?
4. Do we need a manual review workflow before showing `verified_absent`?
5. Should source submissions be anonymous at first, or require email to reduce
   spam?

## References

- College Scorecard API documentation: https://collegescorecard.ed.gov/data/api/
- College Scorecard data explorer: https://data.ed.gov/data_explorer/college-scorecard-explorer
- Existing Scorecard pipeline: [`tools/scorecard/README.md`](../../tools/scorecard/README.md)
- Existing queryable browser PRD: [PRD 010](010-queryable-data-browser.md)
