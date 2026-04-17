# PRD 002: collegedata.fyi Frontend

**Status:** Shipped (2026-04-16). Live at [collegedata.fyi](https://collegedata.fyi).
**Created:** 2026-04-16
**Reviewed via:** /autoplan (CEO + Design + Eng review pipeline), then /review with adversarial (Claude + Codex)
**Post-ship fixes:** PostgREST pagination (commit `b829ce9`), XSS in JSON-LD, sub-institutional year pages, error boundary

---

## Context

collegedata.fyi has a fully built backend: 1,675 archived CDS documents across 617
schools, a Docling-based extraction pipeline, and a live PostgREST API at
`api.collegedata.fyi/rest/v1/`. The project has no frontend. The v1-plan explicitly
scoped out a web UI ("Explicitly out of scope for V1: a web UI"). This plan promotes
the frontend to V1 scope because the backend is shipped and the data is queryable.
A frontend turns "curl the API" into "visit the site", which is the difference between
a tool for developers and a product for everyone.

The blog post draft ("The Uncommon Data Set") is ready. The preservation-archive
narrative is the launch story. The frontend needs to serve that story while being
genuinely useful as a data browser.

## Premises

1. **The audience is mixed.** Parents, students, journalists, IR professionals, and
   developers. The frontend must be usable without knowing what PostgREST is.
2. **The data is the product.** The frontend is a read-only viewer. No auth, no user
   accounts, no write paths. Every page is public and cacheable.
3. **The backend is stable.** The API, schema, and storage paths are settled. The
   frontend consumes what exists, it doesn't need to change the backend.
4. **Vercel for hosting is fine.** ADR 0001 says Supabase-only for data infrastructure.
   A frontend on Vercel is presentation layer, not data layer.
5. **Ship fast, iterate later.** This is the first frontend. Get the pages live,
   then improve based on what people actually use.

## What to build

### Page 1: Landing page (`/`)

The first thing anyone sees. Search leads, not narrative.

1. **Hero: school search.** Autocomplete text input as the dominant element.
   "Search 617 schools..." placeholder. Typing filters a dropdown of matching
   school names. Click -> school detail page. This is the front door.

2. **Social proof stats bar** below the hero. Live from the API:
   - Total schools with archived data
   - Total documents archived
   - Year range (earliest to latest `canonical_year`)
   - Extraction coverage (% with `extraction_status = 'extracted'`)
   - "Last updated" timestamp (from API response date header)

3. **One-line mission tagline.** "College facts pulled straight from each school's
   Common Data Set, archived so the numbers stay public." Link to About page
   for the full story.

4. **Clear CTAs.** "Browse all schools" -> directory. "View on GitHub" -> repo.
   "API docs" -> `api.collegedata.fyi`.

**API query:**
```
GET /rest/v1/cds_manifest?select=school_id,canonical_year,extraction_status
```
Client-side aggregation for stats (total schools = distinct school_id count, etc.).
This is ~1,675 rows of 3 small fields, ~50KB. Fine for a single fetch on page load.

### Page 2: School directory (`/schools`)

List every school with archived CDS data. One row per school.

| Column | Source |
|--------|--------|
| School name | `school_name` (first row per school_id) |
| Documents | Count of rows per school_id |
| Latest year | Max `canonical_year` per school_id |
| Formats | Distinct `source_format` values |

**Features:**
- Text search by school name (client-side filter, dataset is small)
- Sort by name, document count, latest year
- Click row -> school detail page

**API query:**
```
GET /rest/v1/cds_manifest?select=school_id,school_name,canonical_year,source_format,extraction_status&order=school_name
```
Same dataset as landing page stats, just displayed differently. Cache and share.

### Page 3: School detail (`/schools/[school_id]`)

Everything we know about one school's CDS archive. This is the SEO landing
page for "[School] Common Data Set" queries.

**Header:** School name, total documents, year range.

**Sub-institutional handling:** Schools like Columbia publish multiple CDS docs
per year (e.g., "Columbia College + SEAS" and "General Studies"). When
`sub_institutional` is non-null, display it as a subtitle on the document card.
Group documents by sub-institution if more than one exists. URL scheme:
`/schools/columbia?sub=columbia-college-seas` as a query param filter (not a
path segment, to keep the common case clean).

**Document list:** One card per CDS year, sorted newest first.
Each card shows:
- `canonical_year`
- `source_format` (badge: "Fillable PDF", "Flat PDF", etc.)
- `extraction_status` badge with color map:
  - Green: "Extracted" -> links to `/schools/[slug]/[year]`
  - Yellow: "Pending" -> no link to year page, PDF download only
  - Red: "Failed" -> no link to year page, PDF download only
- Download PDF button (always present)

Non-extracted years never link to year detail pages. Only documents with
`extraction_status = 'extracted'` get a clickable year link. This prevents
"two clicks to a dead end" on pending/failed docs.

**API query:**
```
GET /rest/v1/cds_manifest?school_id=eq.{id}&order=canonical_year.desc
```

**Storage URL construction:**
```
https://isduwmygvmdozhpvzaix.supabase.co/storage/v1/object/public/sources/{source_storage_path}
```

### Page 4: School year detail (`/schools/[school_id]/[year]`)

The answer-engine page. This is what should rank for "Yale acceptance rate 2025"
or "Stanford SAT scores 2024-25." One page per school per year.

If `extraction_status = 'extracted'`, render the structured CDS fields as
**human-readable content** with plain-English labels, not raw field IDs.

**Layout:**
- School name + year in H1
- Key stats summary (acceptance rate, enrollment, SAT/ACT ranges, tuition)
  computed from high-value CDS fields (C.101-C.106, C.901-C.912, G.001-G.012)
- Full field listing grouped by CDS section (A-J), each field with:
  - Plain-English label (from `labels.ts` translation layer, sourced from
    `schemas/cds_schema_2025_26.json` field descriptions)
  - Value
  - Section heading
- Download source PDF link
- Link back to school overview

If not extracted: show document metadata + PDF download + "Structured data
coming soon" message.

**API queries:**
```
GET /rest/v1/cds_manifest?school_id=eq.{id}&canonical_year=eq.{year}
GET /rest/v1/cds_artifacts?document_id=eq.{uuid}&kind=eq.canonical&order=created_at.desc&limit=1
```

**SEO:** Each page gets a unique `<title>` like "Yale University Common Data Set
2024-25 | collegedata.fyi" and structured data (Schema.org `Dataset` markup).

### Page 5: About (`/about`)

- The "Uncommon Data Set" story (adapted from `docs/blog/the-uncommon-data-set.md`)
- What the CDS is and why it matters (short explainer)
- How the archive works (simplified pipeline diagram)
- MIT license notice
- Link to GitHub repo
- Credits (Reducto as extraction benchmark reference, Docling for Tier 4, CDS
  Initiative for the schema)
- Link to Scorecard comparison doc

## Tech stack

| Choice | Why |
|--------|-----|
| **Next.js 15 (App Router)** | Industry standard for React SSR/SSG. Vercel-native. ISR for hourly stats refresh. Better ecosystem for future features (comparison charts, Scorecard join). |
| **TypeScript** | Type safety for API response shapes. |
| **Tailwind CSS** | Fast to ship, no custom design system needed for V1. |
| **@supabase/supabase-js** | Official client, handles auth header injection. |
| **@vercel/analytics** | Zero-cookie web analytics, one-line integration. |
| **Vercel** | Zero-config Next.js hosting, preview deploys, custom domain. |

**No additional dependencies.** No state management library (React state + fetch is
enough for a read-only viewer). No component library (Tailwind + HTML). No ORM
(Supabase client is the query layer).

**Security:** Never use `dangerouslySetInnerHTML` for artifact data. If Tier 4
markdown rendering is needed in the future, use a sanitizing pipeline (e.g.,
`remark` + `rehype-sanitize`). For V1, all artifact values are rendered as plain
text nodes only.

## File structure

```
web/
  src/
    app/
      layout.tsx          -- Root layout, nav, footer
      page.tsx            -- Landing page
      schools/
        page.tsx          -- School directory
        [school_id]/
          page.tsx        -- School detail (all years)
          [year]/
            page.tsx      -- School year detail (SEO answer page)
      about/
        page.tsx          -- About page
    lib/
      supabase.ts         -- Supabase client singleton
      queries.ts          -- Typed API query functions
      types.ts            -- TypeScript types for API responses
      format.ts           -- Display formatters (year ranges, format badges)
      labels.ts           -- CDS field ID -> plain-English label map (from schema JSON)
    components/
      StatsBar.tsx         -- Live corpus stats
      SchoolTable.tsx      -- Searchable/sortable school list
      DocumentCard.tsx     -- CDS year card
      KeyStats.tsx         -- Hero stats block (acceptance rate, SAT, tuition)
      FieldsView.tsx       -- Full structured CDS field viewer (grouped by section)
      Badge.tsx            -- Format/status badges
      Nav.tsx              -- Top navigation
      Footer.tsx           -- Footer with links
  public/
    favicon.ico
  next.config.ts
  tailwind.config.ts
  tsconfig.json
  package.json
  .env.local              -- NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
```

## Data flow

```
Browser
  -> Next.js page (SSR or client)
    -> supabase-js client (with NEXT_PUBLIC_SUPABASE_ANON_KEY)
      -> api.collegedata.fyi/rest/v1/ (PostgREST)
        -> Postgres (RLS: public SELECT)
```

**SSR vs client fetch decision:**
- Landing page stats: **SSR with revalidation** (ISR, revalidate every hour). Stats
  change slowly. Good for SEO, fast initial load.
- School directory: **SSR with revalidation** (same). The full school list is cacheable.
- School detail: **SSR** for the document list (good for SEO, school pages should be
  indexable). **Client-side** for artifact data (lazy-loaded on expand).
- About: **Static** (no API data).

## Environment variables

```
NEXT_PUBLIC_SUPABASE_URL=https://isduwmygvmdozhpvzaix.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

These are public (anon key, RLS allows public SELECT). Safe in the browser.

## Visual design spec

**Colors (Tailwind classes):**
- Primary text: `text-gray-900` / `text-gray-100` dark mode
- Secondary text: `text-gray-600`
- Links: `text-blue-600 hover:text-blue-800`
- Badge extracted: `bg-green-100 text-green-800`
- Badge pending: `bg-yellow-100 text-yellow-800`
- Badge failed: `bg-red-100 text-red-800`
- Format badges: `bg-gray-100 text-gray-700`

**Typography:** System font stack (Next.js default). No custom fonts for V1.

**KeyStats block:** Grid of 4-6 stat cards, only rendered for fields that have
values. No "N/A" placeholders. If a school reports SAT but not ACT, only SAT
appears. Cards show: label, value, optional delta from prior year (V1.1).

**Loading states:** Skeleton loaders with fixed dimensions matching final content
height to prevent CLS. School directory: table with 10 placeholder rows. Stats
bar: 4 fixed-width boxes.

**URL format:** `school_id` in the API is already a human-readable slug
(e.g., `yale`, `harvard`, `harvey-mudd`). URLs are `/schools/yale`,
`/schools/yale/2024-25`. No numeric IDs in URLs.

**Year in URL:** The `[year]` path segment always maps to `canonical_year`
(which is `COALESCE(detected_year, cds_year)`). The API query is
`?canonical_year=eq.2024-25`. Never filter on `cds_year` directly in the frontend.

## Artifact JSON shape

The `cds_artifacts.notes` column for a `kind='canonical'` artifact looks like:

```json
{
  "values": {
    "C.101": "3452",
    "C.102": "1761",
    "C.103": "4",
    "C.201": "Yes",
    "B.101": "847",
    "B.102": "792"
  },
  "stats": {
    "total_fields": 47,
    "unmapped_count": 3
  }
}
```

For Tier 4 (Docling) artifacts, `notes.markdown` contains the raw markdown
and `notes.values` may be sparse or absent until the schema-targeting
cleaner runs. The `FieldsView` component should:
1. Read `notes.values` (object keyed by question number)
2. Group by section letter (A, B, C, ... J) using `labels.ts`
3. Display label + value for each field
4. Show a field count indicator: "47 of ~200 fields extracted"

## SEO and social

- Each school detail page gets an `<title>` like "Yale University - Common Data Set Archive | collegedata.fyi"
- `<meta description>` per page with school name, year count, latest year
- Open Graph tags for social sharing
- `robots.txt` allowing all crawlers
- `sitemap.xml` generated from the school list (Next.js built-in)

## Implementation order

1. **Scaffold** (`npx create-next-app@latest web --typescript --tailwind --app --src-dir`)
2. **Supabase client + types** (`web/src/lib/`)
3. **Field label translation layer** (`labels.ts` from `cds_schema_2025_26.json`)
4. **Landing page** with live stats
5. **School directory** with search and sort
6. **School detail** with document list and PDF download links
7. **School year detail** (SEO answer page with KeyStats + FieldsView)
8. **About page** (adapted from blog post)
9. **SEO** (metadata, sitemap, OG tags, Schema.org Dataset markup)
10. **Vercel Web Analytics** (one-line `@vercel/analytics` integration)
11. **Deploy to Vercel**, configure custom domain

## States to handle

| State | Where | What to show |
|-------|-------|-------------|
| Loading | All pages | Skeleton/shimmer with fixed dimensions |
| Empty school list | Directory | "No schools found matching your search" |
| School not found | Detail | 404 page |
| No documents for school | Detail | "No archived documents yet" |
| Extraction pending | Document card | Yellow "Pending" badge, PDF download only |
| Extraction failed | Document card | Red "Failed" badge, PDF download only |
| No canonical artifact | Year detail | "Structured data not yet available" + PDF download |
| Artifact with sparse values | Field viewer | Show available fields + "47 of ~200 fields extracted" |
| PDF unavailable (storage 404) | Document card | "PDF unavailable" instead of broken link |
| API error | All pages | "Unable to load data. Try refreshing." |

## NOT in scope

- User accounts or authentication
- Write operations (no data submission forms)
- School comparison or ranking features
- Cross-year time series charts (V2)
- Scorecard joined data (V2, per `docs/research/scorecard-summary-table-v2-plan.md`)
- Mobile app
- Custom design system (Tailwind is sufficient for V1)
- Full-text search of CDS content (search is school-name-only for V1)
- Heavy analytics (Vercel Web Analytics is included, zero-cookie, one line)

## What already exists (reuse)

| Sub-problem | Existing code/artifact |
|-------------|----------------------|
| CDS schema field metadata | `schemas/cds_schema_2025_26.json` (section names, labels) |
| API response shape | `supabase/migrations/20260415160009_detected_year.sql` (cds_manifest view) |
| Blog post content | `docs/blog/the-uncommon-data-set.md` |
| School list with IPEDS IDs | `tools/finder/schools.yaml` |
| Supabase project config | `.env` (URL, anon key, project ref) |

## Type safety

Generate TypeScript types from the Supabase schema:
```bash
npx supabase gen types typescript --project-id isduwmygvmdozhpvzaix > web/src/lib/database.types.ts
```

Re-run whenever a migration ships. The Supabase client is typed via
`createClient<Database>(url, key)` so API responses are type-checked at
compile time. This catches column renames before they reach production.

**Schema-version note for `labels.ts`:** V1 ships with labels from the
2025-26 schema only. Documents targeting older schema years may have field
IDs that don't appear in the label map. The `FieldsView` component should
fall back to displaying the raw field ID when no label is found. When the
cross-year schema diff tool ships (backlog P1), `labels.ts` should become
schema-version-aware, keyed by `(schema_version, field_id)`.

## Automated tests

| Test | What it catches | When it runs |
|------|----------------|-------------|
| `npm run build` | Type errors, import failures | CI on every push |
| `supabase gen types` diff check | Schema drift between DB and frontend types | CI on every push |
| Integration smoke test | API reachability, response shape validation | CI + post-deploy |
| Playwright smoke (V1.1) | Page renders, search works, PDF link resolves | Post-deploy |

For V1, the build + type-diff check is the minimum. Playwright smoke tests
are a V1.1 follow-up.

## Verification (manual)

1. `cd web && npm run dev` starts the dev server
2. Landing page loads and shows live stats from the API
3. School directory lists 617+ schools, search filters correctly
4. Click a school -> detail page shows all archived years
5. Click "Download PDF" -> browser downloads the source file
6. Click an extracted year -> structured fields appear grouped by section
7. About page renders the blog post content
8. `npm run build` succeeds with no type errors
9. Deploy to Vercel, confirm pages work at the production URL
10. SEO: check `<title>`, `<meta>`, OG tags render correctly

## Review history

This plan was reviewed via `/autoplan` on 2026-04-16:

- **CEO Review:** 5 findings (1 critical, 2 high, 2 medium). All resolved. Key
  additions: SEO-first year pages, field label translation, Vercel Web Analytics.
- **Design Review:** 5 findings (2 critical, 1 high, 2 medium). All resolved. Key
  additions: search-first landing, no dead-end year pages, visual spec, artifact
  JSON shape documented.
- **Eng Review:** 6 findings (0 critical, 3 high, 3 medium). All resolved. Key
  additions: sub_institutional routing, XSS prevention, type generation, test plan.
- **DX Review:** Skipped (no developer-facing scope).

18 decisions auto-decided (17 mechanical, 1 taste). 0 unresolved issues.
