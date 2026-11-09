# collegedata.fyi web app

Next.js 16 frontend for [collegedata.fyi](https://collegedata.fyi).

The full frontend architecture is documented in [`../docs/frontend.md`](../docs/frontend.md).
Read [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) before changing UI.

## What this app renders

Route-by-route detail lives in [`../docs/frontend.md`](../docs/frontend.md).
In short:

- `/` search-first home page backed by the `search_institutions` RPC.
- `/schools` and `/schools/[school_id]` school directory/detail pages, with
  cards for academic profile, admission strategy, merit/aid profile, and PRD 019
  public-reviewed change intelligence, plus source-labeled NCES/IPEDS baseline
  facts through `FederalBaselineTable`.
- Per-school sub-pages: `/schools/[school_id]/[year]` (field viewer, with
  `cds.xlsx` and `cds.csv` downloads, PRD 025), `acceptance-rate`,
  `early-decision` and `gpa` stat pages (PRD 031), and `feed.xml` (PRD 029).
  Every school and school-year page also has an `opengraph-image`.
- `/browse` queryable CDS browser, `/match` local-only match-list builder,
  `/coverage` public coverage dashboard.
- `/discover` guided discovery (PRD 026): card sort, preference ledger, and the
  rounds loop with reactions and a research shelf. Soft-launched: noindex,
  unlinked, session kept in localStorage only.
- `/recipes/*` (alignment gap, acceptance vs. yield, endowment draw rate,
  waitlist odds, test-optional tracker), `/methodology/*`, `/about/*`.
- `/usage` and `/usage.json` (public API usage), `/pipeline-observation` and
  `/pipeline-observation.json` (public pipeline board, rendered live, not ISR).
- `/feedback` and `/privacy`.
- `/api` documentation page and the no-auth JSON API under `/api/*` (including
  the hosted MCP endpoint at `/api/mcp`), plus `/openapi.json`, `/llms.txt`, and
  `/snapshots/*` open-data files.
- `POST /api/revalidate`, a bearer-token endpoint that expires cached school
  pages after data changes (see below).
- `/changes` operator-only PRD 019 digest, disabled by default.

## Caching

- Home, `/browse`, `/schools`, and `/usage` use hourly ISR (`revalidate = 3600`).
  `/coverage` revalidates every 15 minutes.
- School detail, school-year, acceptance-rate, early-decision, and GPA pages are
  static and revalidate daily (`revalidate = 86400`). They carry `school:<id>`
  cache tags, so data changes show up sooner through `POST /api/revalidate`.
- `/pipeline-observation` is `force-dynamic`.

`POST /api/revalidate` takes `Authorization: Bearer $REVALIDATE_SECRET` and a JSON
body of `{"school_ids": ["yale", "mit"]}` (up to 100) or `{"all": true}`. It
returns 503 when `REVALIDATE_SECRET` is unset. The extraction worker calls it
best-effort after data changes (`tools/extraction_worker/revalidate_notify.py`,
which also needs `COLLEGEDATA_REVALIDATE_URL`).

## Development

```bash
npm ci
npm run dev
npm run typecheck
npm test            # Vitest unit tests
npm run test:smoke  # Playwright specs in tests/ (13 spec files)
npm run build
```

Fonts are self-hosted with `next/font/local`. A Vitest check
(`src/lib/no-remote-fonts.test.ts`) fails `npm test` (and so CI) on `next/font/google` imports
or Google Fonts URLs in app code, so add new faces as local files.

## Required environment

```bash
NEXT_PUBLIC_SUPABASE_URL=https://isduwmygvmdozhpvzaix.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```

Sentry error monitoring (optional overrides; the public DSN is also the SDK default):

```bash
NEXT_PUBLIC_SENTRY_DSN=<public DSN>
SENTRY_ORG=bolewood
SENTRY_PROJECT=collegedata-fyi
SENTRY_AUTH_TOKEN=<org token with org:read + project:releases>
```

`SENTRY_AUTH_TOKEN` is build-time only. When it is unset, `next build` skips
source-map upload and still succeeds. Vercel already supplies `VERCEL_ENV` /
`NEXT_PUBLIC_VERCEL_ENV` and `VERCEL_GIT_COMMIT_SHA` /
`NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA` for `environment` and `release`. Client
bundles have to read those as static `process.env.NEXT_PUBLIC_*` /
`process.env.NODE_ENV` members — a lookup through a passed `env` object is
not inlined, so production browsers used to tag events `development`.

Page revalidation (set in Vercel; the extraction worker needs the same secret):

```bash
REVALIDATE_SECRET=<shared secret>
```

Optional source-submission and feedback forms:

```bash
NEXT_PUBLIC_FORMSPREE_ENDPOINT=<formspree endpoint>
NEXT_PUBLIC_FEEDBACK_FORMSPREE_ENDPOINT=<formspree endpoint for /feedback>
```

When configured, no-CDS school pages show a compact "Email us!" CTA that opens
the structured Formspree source-submission form inline. When unset, the CTA is
disabled and the app does not fall back to `mailto:`. The `/feedback` form uses
its own endpoint and falls back to `NEXT_PUBLIC_FORMSPREE_ENDPOINT`.

Operator-only PRD 019 digest:

```bash
CHANGE_INTELLIGENCE_DIGEST_ENABLED=true
SUPABASE_SERVICE_ROLE_KEY=<service role key>
```

Never import the service-role key into client components. Public pages use anon
queries plus RLS; `/changes` uses `src/lib/change-intelligence-admin.ts`, which
is marked `server-only`.
