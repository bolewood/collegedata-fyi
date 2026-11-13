# collegedata.fyi Frontend

How the frontend works, what's in each file, and how the data flows from
Supabase to the browser. Complements [`docs/prd/002-frontend.md`](prd/002-frontend.md)
(the original plan and review decisions) and [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)
(the full system architecture).

**Live site:** [collegedata.fyi](https://collegedata.fyi)
**Source:** [`web/`](../web/)

---

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Framework | Next.js 16 (App Router) | SSR/ISR for SEO, Vercel-native |
| Language | TypeScript | Type safety on API responses |
| Styling | Tailwind CSS + project design tokens | Utility composition over the "paper, ink, and one quiet green" system |
| Data client | @supabase/supabase-js + browser-search fetch client | PostgREST queries and the ranked browser Edge Function |
| Analytics | @vercel/analytics | Zero-cookie, one line |
| Error monitoring | @sentry/nextjs | Errors and sampled traces; `/feedback` events are dropped (see `lib/sentry.ts`) |
| Fonts | `next/font/local` | Self-hosted faces in `src/app/fonts/`; a Vitest check fails `npm test` and CI on Google Fonts |
| Unit tests | Vitest | `npm test`; includes the alias-link and no-remote-font guards |
| Browser tests | Playwright + axe | `npm run test:smoke`; 13 spec files in `web/tests/` |
| Hosting | Vercel | Auto-deploy from GitHub, custom domain |

No additional component library. No ORM. Local state is React state; the
browser MVP uses client-side state because filters are interactive and backed
by one public Edge Function call.

---

## Route inventory

Every public route in `web/src/app/`, with caching. Details for the main pages follow in [Pages](#pages).

| Route | Purpose | Caching |
|---|---|---|
| `/` | Search-first landing page, live corpus stats | ISR, 1 h |
| `/schools` | School directory | ISR, 1 h |
| `/schools/[school_id]` | School detail: cards, document ledger, federal baseline; directory-only stub for non-CDS schools | static, 24 h + `school:<id>` tag |
| `/schools/[school_id]/[year]` | Year detail: key stats, field viewer, spreadsheet downloads | static, 24 h + tag |
| `/schools/[school_id]/[year]/cds.xlsx`, `cds.csv` | PRD 025 spreadsheet downloads | route handler, 1 h |
| `/schools/[school_id]/acceptance-rate`, `/early-decision`, `/gpa` | PRD 031 stat pages | static, 24 h + tag |
| `/schools/[school_id]/feed.xml` | PRD 029 per-school RSS of new CDS publications | route handler, 1 h |
| `/schools/[school_id]/opengraph-image`, `/[year]/opengraph-image`, `/opengraph-image` | Social cards for school, school-year, and site | static, 24 h (site card 1 h) |
| `/browse` | Queryable CDS browser over `browser-search` | ISR, 1 h |
| `/match` | Local-only match-list builder | ISR, 1 h |
| `/discover` | Guided discovery (noindex, unlinked) | default (no explicit revalidate) |
| `/coverage` | Institution coverage dashboard | ISR, 15 min |
| `/recipes`, `/recipes/{acceptance-vs-yield, alignment-gap, endowment-draw-rate, waitlist-odds, test-optional-tracker}` | Worked analyses | default (no explicit revalidate) |
| `/methodology`, `/methodology/{positioning, admission-strategy, merit-profile}` | Card methodology | default (no explicit revalidate) |
| `/about`, `/about/{common-data-set, college-scorecard, ipeds}` | Background pages | default (no explicit revalidate) |
| `/usage`, `/usage.json` | PRD 033 public usage page and open data | ISR, 1 h |
| `/pipeline-observation`, `/pipeline-observation.json` | PRD 030 public pipeline board and feed | `force-dynamic` |
| `/feedback`, `/privacy` | Feedback form, privacy notice | default (no explicit revalidate) |
| `/api` | API reference page | ISR, 1 h |
| `/api/schools/search`, `/api/schools/[school_id]/{facts, sources}`, `/api/facts/[school_id]`, `/api/compare`, `/api/fields`, `/api/snapshots`, `/api/mcp` | No-auth JSON API and hosted MCP | 1 h (search 5 min; MCP `force-dynamic`) |
| `/api/revalidate` | `POST` cache expiry hook, bearer-token protected | `force-dynamic` |
| `/snapshots/latest/[file]`, `/snapshots/v1/[snapshot_date]/[file]` | Open-data files | 1 h |
| `/openapi.json`, `/llms.txt`, `/robots.txt`, `sitemap.xml` | Machine-readable surfaces | 1 h (`robots.txt` `force-static`) |
| `/changes` | Operator-only change digest (noindex, env-gated) | `force-dynamic` |
| `/ink-lab` | Design experiment (noindex) | default (no explicit revalidate) |

School pages are the largest set. They were hourly until PR #262 because hourly regeneration let crawler sweeps saturate PostgREST; now they revalidate daily, and `POST /api/revalidate` expires `school:<id>` tags on demand after the extraction worker changes data.

---

## Pages

### `/` Landing page (`web/src/app/page.tsx`)

Search-first design. The hero is an autocomplete text input backed by the
PRD 015 `search_institutions` RPC, so it can return directory-only institutions
with coverage badges as well as schools with archived CDS data. Below it, a
stats bar shows live corpus numbers pulled from the API (institutions, documents,
field rows, extraction %).

**Data flow:** `fetchManifest()` returns live rows from `cds_manifest` via
paginated range queries (PostgREST caps at 1,000 rows per request), filtering
out `removed_at` rows and excluded public participation statuses. Client-side
aggregation computes school summaries and corpus stats. ISR revalidates every
hour (`revalidate = 3600`), as do `/schools`, `/browse`, and `/usage`.

### `/schools` School directory (`web/src/app/schools/page.tsx`)

Sortable, filterable table of every school with archived CDS data. Columns:
school name (linked), document count, latest year, format badges. Client-side
search filters by school name. Shares the same `fetchManifest()` data as
the landing page.

### `/browse` Queryable school browser (`web/src/app/browse/page.tsx`)

Curated PRD 010 browser for the `school_browser_rows` serving table. The
first public slice stays deliberately narrow: primary school rows,
`2024-25+`, and launch-certified visible filters only.

**Default query behavior:**
- `mode = latest_per_school`
- `variant_scope = primary_only`
- `min_year_start = 2024`
- filter fields become answerability requirements except `is blank`

The page calls the deployed `browser-search` Edge Function, displays the
answerability summary returned by the backend, renders source links for each
row, and exports the current curated result set as CSV. It does not expose
arbitrary `cds_fields` filtering yet.

PRD 012 added SAT/ACT academic-profile fields to the backend contract and CSV
export, but not to the default visible filter UI. Future score filters must pair
score percentiles with submit-rate caveats because SAT/ACT score rows describe
score submitters, not the entire admitted or enrolled class.

### `/schools/[school_id]` School detail (`web/src/app/schools/[school_id]/page.tsx`)

School-scoped pages check the reviewed aliases in
`web/src/data/school-redirects.json` before consulting the live
`institution_slug_crosswalk`. Next.js issues permanent redirects for page and
year routes from that checked-in manifest, preserving scalar, repeated, and
empty query parameters. Metadata, Open Graph images, public facts/source APIs,
and XLSX/CSV download routes use the same reviewed alias authority before the
live crosswalk, so an annual directory refresh cannot make an old link serve
another institution's data.

All archived CDS documents for one school, sorted newest first. Each
document is a card showing year, format badge, extraction status badge,
and a source download link. The label is format-aware (`Download PDF`,
`Download XLSX`, `Download DOCX`, `Download HTML`, or `Download source`) and is
derived from the archived storage path when available.

**Status badge behavior:**
- Green "Extracted": year is clickable, links to `/schools/{id}/{year}`
- Yellow "Pending": not clickable, source download only
- Red "Failed": not clickable, source download only

This prevents dead-end navigation to year pages with no structured data.

**Sub-institutional support:** Schools like Columbia that publish multiple
CDS files per year show each variant with its `sub_institutional` label.
Documents are grouped by sub-institution when more than one exists.

Large document archives use `SchoolDocumentsLedger`: the school page shows the
three most recent CDS files first and tucks older files into an expandable
ledger so the school-page product cards are not pushed below a long historical
document list.

PRD 019 adds `WhatChangedCard`, but it intentionally renders only after an event
has cleared the public change-event gate. Generated change candidates stay
operator-only in `cds_field_change_events` until `verification_status` is
`not_required` or `confirmed` and `public_visible = true`.

PRD 021 adds `FederalBaselineTable` for schools with
`school_facts_unified` rows. On CDS-backed pages the table is federal context
below the school-authored document narrative. On directory-only/no-CDS pages it
is the main facts surface after the "No public CDS found" box. The table shows
NCES/IPEDS release status prominently and keeps source table/variable visible;
status and CDS-definition alignment details are exposed on hover/focus under
the Source column.

School pages are `force-static` with `revalidate = 86400` and carry a
`school:<school_id>` cache tag (plus a shared `school-data` tag).
`POST /api/revalidate` (bearer `REVALIDATE_SECRET`, body `{"school_ids": [...]}`
up to 100 or `{"all": true}`) expires those tags; the extraction worker calls it
best-effort after data changes. The same daily window applies to the year,
acceptance-rate, early-decision, and GPA pages and their social images.

School pages are themed from `institution_brand_colors` (a two-plate ink pair
derived in `lib/derive-inks.ts`; schools without a reviewed color use the house
pair). FSA institutional nonpayment appears as a cited number where
`fsa_nonpayment_current` has a matched row.

Directory-only pages with `can_submit_source` render a compact `SubmissionForm`
CTA inside the no-CDS box. Clicking "Email us!" opens the same structured
Formspree-backed form inline when `NEXT_PUBLIC_FORMSPREE_ENDPOINT` is set.
There is no `mailto:` fallback.

### `/schools/[school_id]/[year]` Year detail (`web/src/app/schools/[school_id]/[year]/page.tsx`)

The SEO answer page. Designed to rank for queries like "Yale acceptance
rate 2025" or "Stanford SAT scores 2024-25."

**Layout (when extracted):**
1. Breadcrumb: Schools / {name} / {year}
2. School name + year heading
3. Format badge + source download link, plus "Download spreadsheet"
   (XLSX) and CSV links (PRD 025) on the first variant when structured
   values exist
4. **KeyStats block:** 4-8 stat cards showing acceptance rate, applications,
   admitted, enrolled, SAT composite/math/reading ranges, and ACT Composite
   when available. Only renders cards for fields that have values. Acceptance rate is computed from
   `C.101+C.102+C.103` (applied) / `C.104+C.105+C.106` (admitted).
   ACT Composite uses `C.914` and `C.916` for the 25th/75th percentile range.
5. **FieldsView:** All extracted fields grouped by CDS section (A-J), each
   with a human-readable label from the 2025-26 schema and the extracted
   value. Shows a field count indicator ("47 of ~200 fields extracted").

**Sub-institutional variants:** If multiple documents match the school+year
(e.g., Columbia College + SEAS and General Studies), all variants are shown
on the same page with their own KeyStats and FieldsView sections.

**When not extracted:** Shows document metadata + source download + a
"Structured data coming soon" message.

**Spreadsheet download routes (PRD 025):**
`/schools/[school_id]/[year]/cds.xlsx` and `cds.csv` route handlers serve
the same merged extract the page renders as a downloadable workbook (README
sheet + one sheet per CDS section that has extracted values) or flat CSV. Multi-variant school-years
land in one workbook; a Variant column appears when there is more than one
document. Both routes 404 when the
school/year has no structured values; CSV cells are neutralized against
spreadsheet formula injection. See `lib/spreadsheet-source.ts`,
`lib/spreadsheet.ts`, and `lib/xlsx.ts`.

**SEO:** Schema.org `Dataset` JSON-LD markup plus breadcrumb markup. Dataset
JSON-LD includes `name`, `description`, `url`, `creator`, `temporalCoverage`,
`license`, `provider`, and `isAccessibleForFree` so Google Search Console's
Dataset structured-data checks have the required fields. Unique `<title>` and
`<meta description>` per page come from `generateMetadata()`.

### `/schools/[school_id]/acceptance-rate`, `/early-decision`, `/gpa` Stat pages

PRD 031. Each page answers one plain question for one school ("what is the
acceptance rate", "do early decision applicants get in more often", "what GPA do
admitted students have") from multi-year CDS history (`lib/acceptance-history*.ts`),
with the copy rules in `docs/copy/wave-6-acceptance-rate.md`, `wave-7-early-decision.md`,
and `wave-8-gpa.md`. A school gets a page only when it has enough usable years;
the sitemap lists the pages that exist. Searchable canonical slugs (for example
`uf` rather than the legal-name slug) are pinned in `tools/finder/public_slugs.yaml`.

### `/schools/[school_id]/feed.xml` Publication feed

PRD 029. An RSS feed per school built from the append-only `cds_publish_events`
log, school-direct publications only. Mirror and operator uploads never appear.

### `/coverage` Coverage dashboard (`web/src/app/coverage/page.tsx`)

PRD 015 accountability page. Server-fetches `institution_cds_coverage`;
`CoverageDashboard` renders a histogram, status/state/enrollment/recency
filters, and a virtualized sortable table. The default view emphasizes schools
where a CDS is missing or not current.

### `/match` Match list builder (`web/src/app/match/page.tsx`)

PRD 017 client-heavy builder. It reads `school_browser_rows`, directory rows,
and Scorecard enrichment, ranks schools with the same profile model used by the
academic positioning card, and supports local save/share codes without writing
student profile data to the backend.

### `/discover` Guided discovery (`web/src/app/discover/page.tsx`)

PRD 026, soft-launched: the route exports `noindex` metadata and is not linked
from navigation. The client-side `DiscoverFlow` walks a geographic boundary
step, an accessible 24-card experience sort, a plain-language preference
ledger, and then the discovery rounds loop: an interests step
(`InterestsStep`), six-school rounds (`RoundsStep`) with evidence-grounded
reasons that fail closed when the evidence is thin, reactions to each school, a
research shelf (`ShelfStep`), and a profile strip (`ProfileStrip`). Everything
runs in the browser. A TypeScript engine (`lib/discovery/rounds.ts`) executes
`discovery_policy_v1` against a versioned evidence bundle
(`web/public/discovery/evidence-v1.json`, built by
`tools/discovery/build_evidence_bundle.py`) and is conformance-tested against
the Python reference through a committed fixture. The session (localStorage
only, 30-day TTL, discarded on deck/library/policy version mismatch) never
leaves the device, and the ZIP resolves to a committed ZIP3 centroid locally.
The sort follows the PRD accessibility contract: no dragging, one card at a
time with four buttons, polite live-region announcements, nothing communicated
by color alone. Content (card library, opening deck, policy) is bound at build
time from committed mirrors in `lib/discovery/content/` of the CC BY-SA
artifacts in `data/discovery/`; `content-sync.test.ts` fails the suite when a
mirror drifts. The schema-constrained AI reflection step from the PRD has not
shipped; the flow uses the non-AI path.

### `/changes` Operator digest (`web/src/app/changes/page.tsx`)

PRD 019 internal review surface. This route is disabled unless
`CHANGE_INTELLIGENCE_DIGEST_ENABLED=true` is present in the server environment,
and it requires `SUPABASE_SERVICE_ROLE_KEY` because it reads generated candidate
events before they are public. It exports `noindex` metadata and is not linked
from public navigation.

The digest groups generated events into admissions changes,
international-student signals, aid/affordability shifts, reporting gaps, and
extraction-quality blockers. It is an operator calibration surface, not a public
claims page.

### `/methodology/*` Methodology pages

Static methodology pages explain the academic positioning, admission strategy,
and merit profile cards. Keep these pages factual and source-semantics focused;
they are not marketing pages and should not imply personalized admissions or aid
predictions.

### `/api` API page (`web/src/app/api/page.tsx`)

Public API reference. Covers the friendly JSON API (`/api/schools*`,
`/api/compare`, `/api/fields`, `/api/snapshots`), the hosted MCP endpoint and
CLI, rate limits and the `X-CollegeData-Client` header, `llms.txt` and
`openapi.json`, the snapshot files, and the raw PostgREST resources (anon-key
headers, `browser-search`, `school_merit_profile`, and the other served views
listed in [`ARCHITECTURE.md`](ARCHITECTURE.md#served-views)). Per-route
endpoint details live in `web/src/app/openapi.json/route.ts` and
`web/src/app/llms.txt/route.ts`.

### `/about` About page (`web/src/app/about/page.tsx`)

Static content adapted from the "Uncommon Data Set" blog post draft.
Explains what the CDS is, what we found building the archive, how the
pipeline works, and credits.

### `/recipes` Worked examples (`web/src/app/recipes/page.tsx`)

Static index for reproducible analyses built from CDS and federal data.
`/recipes/endowment-draw-rate` renders an FY2020–FY2024 private nonprofit
IPEDS Finance Part H distribution and selection-neutral school history from a
versioned, checked-in generated dataset. The public-data generator and full
methodology live in `tools/ipeds/build_endowment_draw_rate_recipe.py` and
[`recipes/endowment-draw-rate.md`](recipes/endowment-draw-rate.md).

### `/usage` and `/pipeline-observation` Public operations pages

`/usage` (PRDs 032 and 033) charts daily unique downloads of archived CDS files
split into browser, program, and bot traffic, API use by others, and demand by
school, with a table alternative for each chart. It reads only the
`usage_public_*` tables and publishes the same data at `/usage.json`.
`/pipeline-observation` (PRD 030) is a live board of pipeline stations and their
clocks, plus the last 14 days of extraction finishes. It is `force-dynamic`
because ISR served build-time seed data as stale; `/pipeline-observation.json`
is the feed the Discord alert poller reads. See `docs/api-usage-attribution.md`
and `docs/ops-discord.md`.

### `/feedback` and `/privacy`

`/feedback` posts directly from the browser to Formspree (`FeedbackForm`; see
[`community-feedback.md`](community-feedback.md)) and sends only bounded
properties to analytics and nothing to Sentry. `/privacy` states what the site and API store.

### Snapshot and agent surfaces

`/snapshots/latest/*` and `/snapshots/v1/{date}/*` serve `schools.jsonl`,
`school_facts.jsonl`, `sources.jsonl`, and `field_dictionary.json`;
`/api/snapshots` returns the manifest. The files are currently built from live
views on request (see `lib/snapshot-data.ts`), so a dated URL is not a frozen
copy. `/llms.txt`, `/openapi.json`, and `/api/mcp` serve agents.

### Error and 404 pages

- `error.tsx`: Root error boundary with "Try again" button. Catches
  Supabase downtime, network errors, and malformed data.
- `not-found.tsx`: 404 page with links to school directory and home.

---

## Data flow

```
Browser
  -> Next.js page (SSR with ISR: hourly for home/browse/schools, daily + on-demand tags for school pages)
    -> supabase-js client (NEXT_PUBLIC_SUPABASE_ANON_KEY)
      -> https://isduwmygvmdozhpvzaix.supabase.co/rest/v1/
        -> Postgres (RLS: public SELECT on all tables/views)

Browser
  -> /browse client component
    -> https://isduwmygvmdozhpvzaix.supabase.co/functions/v1/browser-search
      -> school_browser_rows ranked latest-per-school query
```

Most page data fetching happens server-side. The `/browse` client component
calls the public `browser-search` Edge Function directly so filter changes do
not require a route transition. The Supabase anon key is in the browser (it's
designed to be public, RLS enforces read-only). No server-side auth, no write
paths.

**Key queries:**

| Page | Query | Notes |
|------|-------|-------|
| Landing + Directory | `cds_manifest WHERE removed_at IS NULL` (paginated) | Range-based pagination to work around PostgREST 1,000-row cap |
| School detail | `cds_manifest WHERE school_id = ? AND removed_at IS NULL` | Ordered by canonical_year DESC |
| Year detail | `cds_manifest WHERE school_id = ? AND canonical_year = ? AND removed_at IS NULL` | Returns all sub-institutional variants |
| Year detail (fields) | `cds_artifacts WHERE document_id = ?` | Loads canonical + `tier4_llm_fallback`, then merges cleaner-wins |
| Queryable browser | `browser-search` Edge Function | Ranked latest-per-school search over `school_browser_rows` with answerability metadata, including SAT/ACT submit-rate companion metadata for active score filters |
| School positioning/admission cards | `school_browser_rows WHERE school_id = ?` | Latest primary row with SAT/ACT, admissions, ED/EA, wait-list, and C7/app-fee columns |
| Match builder | `school_browser_rows` + `institution_directory` + `scorecard_summary` | Client-side ranked school list, with local-only profile persistence |
| Merit profile | `school_merit_profile WHERE school_id = ?` | Latest primary Section H merit/need-aid facts plus Scorecard context |
| Federal baseline facts | `school_facts_unified WHERE school_id = ?` | Source-labeled NCES/IPEDS baseline facts for in-scope schools, including release type/date, source table/variable, status, and CDS-definition alignment |
| What changed card | `cds_field_change_events WHERE school_id = ? AND public_visible = true` | Public-reviewed PRD 019 events only; RLS also requires `verification_status in ('not_required','confirmed')` |
| Operator changes digest | service-role `cds_field_change_events` query | Server-only route, disabled unless explicitly enabled by env var |

**Deduplication:** `fetchSchoolDocuments` and `fetchDocumentsBySchoolAndYear`
are wrapped in `React.cache()` so `generateMetadata()` and the page
component share the same Supabase response within a single render.

---

## Components

### Data display

| Component | File | Purpose |
|-----------|------|---------|
| `StatsBar` | `components/StatsBar.tsx` | 4-column stat grid (schools, docs, year range, extraction %) |
| `SchoolSearch` | `components/SchoolSearch.tsx` | Autocomplete input with keyboard nav, filters client-side |
| `SchoolBrowser` | `components/SchoolBrowser.tsx` | PRD 010 browser filters, answerability stats, result table, pagination, CSV export. CSV includes PRD 012 SAT/ACT backend columns. |
| `PositioningCard` | `components/PositioningCard.tsx` | PRD 016 academic fit card. Compares a local student profile against school SAT/ACT bands and selectivity context. |
| `AdmissionStrategyCard` | `components/AdmissionStrategyCard.tsx` | PRD 016B card for ED/EA, wait-list, yield, C7 factors, and application-fee signals from `school_browser_rows`. |
| `MatchListBuilder` | `components/MatchListBuilder.tsx` | PRD 017 ranked list-builder experience for `/match`. |
| `MeritProfileCard` | `components/MeritProfileCard.tsx` | PRD 018 Section H + Scorecard merit/aid profile card. |
| `WhatChangedCard` | `components/WhatChangedCard.tsx` | PRD 019 public-reviewed year-over-year CDS change events. Hides when the school has no published events. |
| `FederalBaselineTable` | `components/FederalBaselineTable.tsx` | PRD 021 accessible table for source-labeled NCES/IPEDS facts from `school_facts_unified`. |
| `EndowmentDrawRateExplorer` | `components/EndowmentDrawRateExplorer.tsx` | Interactive sector distribution, threshold table, and school-history explorer for the endowment draw-rate recipe. |
| `DiscoverFlow` | `components/discover/DiscoverFlow.tsx` | PRD 026 guided discovery for `/discover`: boundary step, 24-card sort, ledger, interests, rounds, reactions, shelf (`InterestsStep`, `RoundsStep`, `ShelfStep`, `ProfileStrip`). Session is browser-local only. |
| `SchoolDocumentsLedger` | `components/SchoolDocumentsLedger.tsx` | Collapses long CDS-document histories after the three most recent files. |
| `SpreadsheetDownloadLinks` | `components/SpreadsheetDownloadLinks.tsx` | PRD 025 XLSX + CSV download links on the year page; fires a `spreadsheet_downloaded` analytics event. |
| `SubmissionForm` | `components/SubmissionForm.tsx` | Formspree-backed public CDS source submission form; compact mode opens inline from no-CDS pages. |
| `FeedbackForm` | `components/FeedbackForm.tsx` | `/feedback` form; posts `FormData` to Formspree from the browser. |
| `SchoolTable` | `components/SchoolTable.tsx` | Sortable/filterable school list with search input |
| `DocumentCard` | `components/DocumentCard.tsx` | CDS year card with status badge, format badge, and format-aware source link |
| `KeyStats` | `components/KeyStats.tsx` | Grid of stat cards (acceptance rate, SAT, enrollment) |
| `FieldsView` | `components/FieldsView.tsx` | Full field listing grouped by CDS section |
| `Badge` | `components/Badge.tsx` | Colored pill badge (green/yellow/red/gray) |

### Layout

| Component | File | Purpose |
|-----------|------|---------|
| `Nav` | `components/Nav.tsx` | Top nav bar with links to Schools, About, API, GitHub |
| `Footer` | `components/Footer.tsx` | Footer with project description, links, MIT license note |

---

## Lib modules

| Module | File | Purpose |
|--------|------|---------|
| `supabase.ts` | `lib/supabase.ts` | Supabase client singleton + Storage base URL |
| `queries.ts` | `lib/queries.ts` | Typed query functions + client-side aggregation |
| `school-alias.ts` | `lib/school-alias.ts` | Validates the checked-in retired-alias manifest, builds permanent school and school-year redirects, and resolves reviewed aliases before live crosswalk queries. |
| `browser-search.ts` | `lib/browser-search.ts` | Typed request/response wrapper for the `browser-search` Edge Function |
| `positioning.ts` | `lib/positioning.ts` | Student-profile fit tiering and academic-positioning copy logic |
| `admission-strategy.ts` | `lib/admission-strategy.ts` | ED/EA/wait-list/admission-factor calculations and quality gating |
| `list-builder.ts` | `lib/list-builder.ts` | PRD 017 match ranking, tiering, and list presentation helpers |
| `change-intelligence-admin.ts` | `lib/change-intelligence-admin.ts` | Server-only service-role query helper for the gated `/changes` digest |
| `endowment-draw-rate-recipe-analysis.ts` | `lib/endowment-draw-rate-recipe-analysis.ts` | Pure filtering and presentation helpers for the endowment draw-rate recipe. |
| `endowment-draw-rate-recipe-data.ts` | `lib/endowment-draw-rate-recipe-data.ts` | Generated, versioned FY2020–FY2024 IPEDS recipe dataset and source-release provenance. |
| `savecode.ts` | `lib/savecode.ts` | Stateless local profile/list share code encoding |
| `types.ts` | `lib/types.ts` | TypeScript interfaces for API responses |
| `format.ts` | `lib/format.ts` | Display formatters (badge labels, status colors, storage URLs) |
| `spreadsheet.ts` | `lib/spreadsheet.ts` | PRD 025 workbook/CSV builder; same section grouping and labels as `FieldsView`, CSV output neutralized against formula injection |
| `spreadsheet-source.ts` | `lib/spreadsheet-source.ts` | Assembles `SpreadsheetInput` for the `cds.xlsx`/`cds.csv` routes from the same queries the year page uses |
| `xlsx.ts` | `lib/xlsx.ts` | Dependency-free minimal XLSX writer (zip of XML parts, inline strings, deterministic output); reusable for other export surfaces |
| `discovery/content.ts` | `lib/discovery/content.ts` | Build-time binding to the versioned PRD 026 content mirrors in `lib/discovery/content/` (card library, opening deck, `discovery_policy_v1`); `content-sync.test.ts` keeps mirrors in lockstep with `data/discovery/` |
| `discovery/geography.ts` | `lib/discovery/geography.ts` | Boundary-step validation with plain-language, field-associated errors; validates shape only (the ZIP3 centroid lookup is `resolveZip` in `content.ts`) |
| `discovery/rounds.ts`, `bundle.ts`, `reasons.ts`, `matchers.ts` | `lib/discovery/` | Rounds engine, evidence-bundle loader, evidence-grounded reasons, and matchers for `/discover` |
| `usage.ts`, `usage-data.ts` | `lib/` | `/usage` model and `usage_public_*` fetch |
| `pipeline-observation.ts`, `pipeline-lamps.ts` | `lib/` | Pipeline board data and lamp logic |
| `acceptance-history*.ts` | `lib/` | PRD 031 stat-page data, copy, and sitemap helpers |
| `derive-inks.ts`, `school-inks.ts` | `lib/` | Brand-color ink derivation for school themes |
| `revalidate-schools.ts`, `school-cache-tags.ts` | `lib/` | Cache tags and the `/api/revalidate` request handling |
| `sentry.ts` | `lib/sentry.ts` | Sentry init options, noise filters, and the `/feedback` drop rule |
| `api-usage.ts` | `lib/api-usage.ts` | Request attribution for the friendly API |
| `discovery/session.ts` | `lib/discovery/session.ts` | Browser-local (localStorage-only) discovery session: 30-day TTL, discarded on deck/library/policy version mismatch |
| `discovery/signals.ts` | `lib/discovery/signals.ts` | Pure card-response → preference signal/ledger mapping per `discovery_policy_v1` bucket weights |
| `discovery/types.ts` | `lib/discovery/types.ts` | Discovery runtime types mirroring the versioned `data/discovery/` artifact shapes |
| `labels.ts` | `lib/labels.ts` | Auto-generated CDS field ID to plain-English label map (1,105 fields from `cds_schema_2025_26.json`) |

---

## Field label translation

`labels.ts` is auto-generated from `schemas/cds_schema_2025_26.json` by a
Python script that runs at build time. It maps every CDS question number
(like `B.101`) to a plain-English label (like "Degree-seeking, first-time
first-year students: males"), plus section name and value type metadata.

The `FieldsView` component prefers labels from the artifact data itself
(each field value object includes a `question` string from the extraction
pipeline), falling back to `labels.ts` when the artifact doesn't carry
inline labels. This means Tier 2 extracts (which include rich per-field
metadata) display their own labels, while any future extracts that only
carry raw values can still render human-readable field names.

**Schema version limitation:** V1 ships with labels from the 2025-26
schema only. Documents targeting older schema years may have field IDs
that don't appear in the label map. The `FieldsView` component falls
back to displaying the raw field ID when no label is found.

---

## Visual design

The canonical visual system is [`web/DESIGN_SYSTEM.md`](../web/DESIGN_SYSTEM.md)
and [`web/src/app/tokens.css`](../web/src/app/tokens.css). The short version:
paper background, ink text, one muted forest accent, rules instead of shadows,
and tabular numbers. Do not introduce blue UI, large rounded cards, or
marketing-style decoration.

**KeyStats, product cards, and browser rows:** only render values that exist.
Do not invent confidence scoring or fill blanks with authoritative-looking
placeholders. SAT/ACT browser fields should be described as submitter-profile
values unless the UI also shows the submit-rate context. Merit profile copy must
preserve the distinction between school-reported Section H non-need grants and
a personalized award estimate.

---

## SEO

- **Metadata:** Every page has a unique `<title>` and `<meta description>`
  via `generateMetadata()` or static `metadata` exports.
- **Sitemap:** `sitemap.ts` generates URLs for all indexable static pages, all
  school pages, all extracted year detail pages, and the acceptance-rate,
  early-decision, and GPA pages that exist. Noindex routes
  (`/discover`, `/changes`, `/ink-lab`) are omitted.
- **Robots:** `/robots.txt` allows all crawlers, points to the sitemap, and comments point automated clients at `/api` and `/llms.txt`.
- **Schema.org:** School pages include `CollegeOrUniversity` + archive
  `Dataset` JSON-LD. Year detail pages include `Dataset` + `BreadcrumbList`
  JSON-LD with required `description`, `creator`, and `license` fields.
- **Open Graph:** Root metadata includes OG title, description, and URL, and
  `opengraph-image` routes generate cards for the site, school pages, and
  school-year pages.
- **Agents:** `/llms.txt` summarizes the API for LLM crawlers and `robots.txt`
  points automated clients at `/api`. Sentry filters known crawler noise.

---

## Security

- **No dangerouslySetInnerHTML on user data.** All artifact field values
  are rendered as plain text nodes. The one use of `dangerouslySetInnerHTML`
  (JSON-LD script tag) escapes `<` as `\u003c` to prevent script injection.
- **Public write path is isolated to Formspree.** The app has no public
  Supabase write path. The optional source-submission and feedback forms post
  directly from the browser to the configured Formspree endpoints. The Supabase
  anon key only allows SELECT via RLS policies. (The `community_feedback`
  migration, `20261108210000`, creates private tables that no web code reads or
  writes since the form moved to Formspree in PR #255.)
- **`POST /api/revalidate` is bearer-protected** with `REVALIDATE_SECRET` and
  returns 503 when the secret is unset.
- **No auth.** No user accounts, no server-side sessions, no cookies (except
  Vercel Analytics which is zero-cookie). The `/discover` session is
  browser-local localStorage only and never leaves the device.

---

## Environment variables

```
NEXT_PUBLIC_SUPABASE_URL=https://isduwmygvmdozhpvzaix.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```

Set in Vercel dashboard for production, in `web/.env.local` for local dev.
The `.env.local` file is gitignored.

Operator-only PRD 019 digest, disabled by default:

```
CHANGE_INTELLIGENCE_DIGEST_ENABLED=true
SUPABASE_SERVICE_ROLE_KEY=<service role key>
```

Do not expose the service-role key to client components. The public school-page
card uses the anon client and RLS-filtered rows only.

Optional public source-submission and feedback forms:

```
NEXT_PUBLIC_FORMSPREE_ENDPOINT=<formspree endpoint>
NEXT_PUBLIC_FEEDBACK_FORMSPREE_ENDPOINT=<formspree endpoint for /feedback>
```

When unset, the compact no-CDS CTA is disabled and full source-submission forms
render an unavailable state. `/feedback` reads its own endpoint first and falls
back to `NEXT_PUBLIC_FORMSPREE_ENDPOINT`; with neither set it shows an
unavailable notice.

Page revalidation:

```
REVALIDATE_SECRET=<shared secret>
```

Set in Vercel; the extraction worker needs the same value plus
`COLLEGEDATA_REVALIDATE_URL` (the full `/api/revalidate` URL).

Sentry (all optional; the public DSN is also the SDK default):

```
NEXT_PUBLIC_SENTRY_DSN=<public DSN>
SENTRY_ORG=bolewood
SENTRY_PROJECT=collegedata-fyi
SENTRY_AUTH_TOKEN=<build-time only; source-map upload is skipped when unset>
```

See [`web/README.md`](../web/README.md) for the tag details.

---

## Development

```bash
cd web
npm ci
npm run dev        # http://localhost:3000
npm run typecheck  # tsc --noEmit
npm test           # vitest unit tests (also run in CI)
npm run test:smoke # Playwright smoke tests (13 spec files in web/tests); starts the dev server itself
npm run build      # production build, type-checks
```

---

## What's not built yet

See the frontend section of [`docs/backlog.md`](backlog.md) for the full list.
Key items:

- `supabase gen types` for typed Supabase client (currently using manual types)
- Schema-version-aware labels (dependency resolved: structural schemas for 6 years now exist)
- Paginated full CSV export for `/browse` when result sets exceed the Edge Function page-size cap
- Public `/changes` launch, methodology page, and report charts after PRD 019
  calibration and human verification
- Cross-year comparison views beyond PRD 019's operator/reporting scope (V2)
