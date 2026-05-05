# collegedata.fyi web app

Next.js 16 frontend for [collegedata.fyi](https://collegedata.fyi).

The full frontend architecture is documented in [`../docs/frontend.md`](../docs/frontend.md).
Read [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) before changing UI.

## What this app renders

- `/` search-first home page backed by the `search_institutions` RPC.
- `/schools` and `/schools/[school_id]` school directory/detail pages.
- School-page cards for academic profile, admission strategy, merit/aid profile,
  and PRD 019 public-reviewed change intelligence.
- `/browse` queryable CDS browser.
- `/match` local-only match-list builder.
- `/coverage` public institution coverage dashboard.
- `/changes` operator-only PRD 019 digest, disabled by default.
- Static methodology, API, about, and recipe pages.

## Development

```bash
npm install
npm run dev
npm run typecheck
npm test
npm run build
```

## Required environment

```bash
NEXT_PUBLIC_SUPABASE_URL=https://isduwmygvmdozhpvzaix.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```

Optional source-submission form:

```bash
NEXT_PUBLIC_FORMSPREE_ENDPOINT=<formspree endpoint>
```

Operator-only PRD 019 digest:

```bash
CHANGE_INTELLIGENCE_DIGEST_ENABLED=true
SUPABASE_SERVICE_ROLE_KEY=<service role key>
```

Never import the service-role key into client components. Public pages use anon
queries plus RLS; `/changes` uses `src/lib/change-intelligence-admin.ts`, which
is marked `server-only`.
