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
| Hosting | Vercel | Auto-deploy from GitHub, custom domain |

No additional component library. No ORM. Local state is React state; the
browser MVP uses client-side state because filters are interactive and backed
by one public Edge Function call.

---

## Pages

### `/` Landing page (`web/src/app/page.tsx`)

Search-first design. The hero is an autocomplete text input that filters
617 schools as you type. Below it, a stats bar shows live corpus numbers
pulled from the API (total schools, documents, year range, extraction %).

**Data flow:** `fetchManifest()` returns all rows from `cds_manifest` via
paginated range queries (PostgREST caps at 1,000 rows per request).
Client-side aggregation computes school summaries and corpus stats. ISR
revalidates every hour.

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

All archived CDS documents for one school, sorted newest first. Each
document is a card showing year, format badge, extraction status badge,
and a PDF download link.

**Status badge behavior:**
- Green "Extracted": year is clickable, links to `/schools/{id}/{year}`
- Yellow "Pending": not clickable, PDF download only
- Red "Failed": not clickable, PDF download only

This prevents dead-end navigation to year pages with no structured data.

**Sub-institutional support:** Schools like Columbia that publish multiple
CDS files per year show each variant with its `sub_institutional` label.
Documents are grouped by sub-institution when more than one exists.

### `/schools/[school_id]/[year]` Year detail (`web/src/app/schools/[school_id]/[year]/page.tsx`)

The SEO answer page. Designed to rank for queries like "Yale acceptance
rate 2025" or "Stanford SAT scores 2024-25."

**Layout (when extracted):**
1. Breadcrumb: Schools / {name} / {year}
2. School name + year heading
3. Format badge + PDF download link
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

**When not extracted:** Shows document metadata + PDF download + a
"Structured data coming soon" message.

**SEO:** Schema.org `Dataset` JSON-LD markup. Unique `<title>` and
`<meta description>` per page via `generateMetadata()`.

### `/about` About page (`web/src/app/about/page.tsx`)

Static content adapted from the "Uncommon Data Set" blog post draft.
Explains what the CDS is, what we found building the archive, how the
pipeline works, and credits.

### Error and 404 pages

- `error.tsx`: Root error boundary with "Try again" button. Catches
  Supabase downtime, network errors, and malformed data.
- `not-found.tsx`: 404 page with links to school directory and home.

---

## Data flow

```
Browser
  -> Next.js page (SSR with ISR, revalidate every hour)
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
| Landing + Directory | `cds_manifest` (all rows, paginated) | Range-based pagination to work around PostgREST 1,000-row cap |
| School detail | `cds_manifest WHERE school_id = ?` | Ordered by canonical_year DESC |
| Year detail | `cds_manifest WHERE school_id = ? AND canonical_year = ?` | Returns all sub-institutional variants |
| Year detail (fields) | `cds_artifacts WHERE document_id = ?` | Loads canonical + `tier4_llm_fallback`, then merges cleaner-wins |
| Queryable browser | `browser-search` Edge Function | Ranked latest-per-school search over `school_browser_rows` with answerability metadata, including SAT/ACT submit-rate companion metadata for active score filters |

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
| `SchoolTable` | `components/SchoolTable.tsx` | Sortable/filterable school list with search input |
| `DocumentCard` | `components/DocumentCard.tsx` | CDS year card with status badge, format badge, PDF link |
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
| `browser-search.ts` | `lib/browser-search.ts` | Typed request/response wrapper for the `browser-search` Edge Function |
| `types.ts` | `lib/types.ts` | TypeScript interfaces for API responses |
| `format.ts` | `lib/format.ts` | Display formatters (badge labels, status colors, storage URLs) |
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

**KeyStats and browser rows:** only render values that exist. Do not invent
confidence scoring or fill blanks with authoritative-looking placeholders. SAT/ACT
browser fields should be described as submitter-profile values unless the UI also
shows the submit-rate context.

---

## SEO

- **Metadata:** Every page has a unique `<title>` and `<meta description>`
  via `generateMetadata()` or static `metadata` exports.
- **Sitemap:** `sitemap.ts` generates URLs for all static pages, all school
  pages, and all extracted year detail pages.
- **Robots:** `robots.ts` allows all crawlers and points to the sitemap.
- **Schema.org:** Year detail pages include `Dataset` JSON-LD markup.
- **Open Graph:** Root metadata includes OG title, description, and URL.

---

## Security

- **No dangerouslySetInnerHTML on user data.** All artifact field values
  are rendered as plain text nodes. The one use of `dangerouslySetInnerHTML`
  (JSON-LD script tag) escapes `<` as `\u003c` to prevent script injection.
- **No write paths.** The frontend is read-only. The Supabase anon key
  only allows SELECT via RLS policies.
- **No auth.** No user accounts, no sessions, no cookies (except Vercel
  Analytics which is zero-cookie).

---

## Environment variables

```
NEXT_PUBLIC_SUPABASE_URL=https://isduwmygvmdozhpvzaix.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```

Set in Vercel dashboard for production, in `web/.env.local` for local dev.
The `.env.local` file is gitignored.

---

## Development

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run build      # production build, type-checks
```

---

## What's not built yet

See the frontend section of [`docs/backlog.md`](backlog.md) for the full list.
Key items:

- `supabase gen types` for typed Supabase client (currently using manual types)
- Schema-version-aware labels (dependency resolved: structural schemas for 6 years now exist)
- Automated Playwright smoke tests in the repo
- OG images (per-school social cards)
- Paginated full CSV export for `/browse` when result sets exceed the Edge Function page-size cap
- Cross-year comparison views (V2)
