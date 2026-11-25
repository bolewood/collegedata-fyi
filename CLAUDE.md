# collegedata.fyi

Open-source archive of U.S. college Common Data Set (CDS) documents.

- **Live site:** https://collegedata.fyi (Next.js on Vercel)
- **API:** https://api.collegedata.fyi (PostgREST on Supabase)
- **Architecture:** `docs/ARCHITECTURE.md` (thirteen pipelines: schema, corpus, discovery, mirror, extraction, scorecard, institution directory + coverage, IPEDS federal baseline, FSA institutional nonpayment, change intelligence, consumer API, frontend, scholarship directory)
- **Frontend PRD:** `docs/prd/002-frontend.md`
- **Design system:** `web/DESIGN_SYSTEM.md` (canonical tokens in `web/src/app/tokens.css`; live reference at `/design-system/`). **Read before writing any UI.** Public copy: `web/VOICE.md`.

## Project layout

- `web/` — Next.js 16 frontend (TypeScript, Tailwind, @supabase/supabase-js)
- `supabase/` — Postgres migrations, Edge Functions (Deno/TS), shared modules
- `tools/` — Python extraction pipeline, schema builder, corpus tools
- `schemas/` — Canonical CDS schema JSON (1,105 fields)
- `data/` — Versioned content datasets: `data/discovery/` (PRD 026 guided-discovery
  card library, ontology, deck, scenarios — CC BY-SA 4.0 with a contribution gate,
  see its README), `data/scholarships/` (PRD 036 named scholarship records, one
  YAML file per program — CC BY-SA 4.0 with the same contribution gate, see its
  README) and `data/watchlists/` (change-intelligence school watchlists)
- `docs/` — Architecture, PRDs, ADRs, research, backlog
- `scratch/` — Throwaway operational outputs (gitignored). Default
  destination for any one-off run artifact: audit/drain JSON dumps,
  CSV worklists, screenshots, ZIP handoffs, debug exports. Scripts
  that emit these should write to `scratch/<tool-name>/` rather than
  into `tools/` or the repo root, so working trees stay clean and
  nothing important hides among the dumps.

## Data quality loop

When doing whack-a-mole CDS data improvements, treat each fix as a signal about the
whole corpus, not a one-off.

- For canary-style extraction issues, search the corpus for other documents with the
  same failure shape and redrain the similar files after the parser/cleaner fix.
- For finding/discovery issues, find and archive the most recent two CDS years when
  available, then add a durable finder or archiver hint so the next year's document
  can be found automatically. If the school took the live PDFs down, pin complete
  Archive.org `id_` snapshots in `tools/finder/school_overrides.yaml` (toolbar
  URLs return HTML; some captures truncate at 1 MB without `%%EOF`).
- For school identity changes, run `python tools/finder/identity_guard.py` before
  writing generated data, then run `python tools/finder/school_redirect_guard.py`
  to verify the checked-in web redirect manifest. After the change is live, run
  `python tools/ops/revalidate_pages.py --all`: the slug crosswalk is one cached
  read shared by every school page and is otherwise held for up to 7 days. Treat `retired_aliases` as
  durable redirects: preserve them across refreshes and never promote a retired
  slug to another institution.
- Close the loop across current state, prior-year baseline, future discovery, and
  similar files before calling the issue handled.
- Count the reach of any corpus-wide fix before calling it done. Compare what it
  caught plus what it skipped with the total that has the problem, and say why
  each skip rule is safe. A sweep that reports only what it caught looks the same
  whether it found every case or a third of them.
- Fix the mechanism, not the shape of the first case, and fix every copy of it.
  The August stuck-seed job copied the first school's details ("few archived
  years") and missed 115 of 190 schools; the `unknown`-year sort was fixed in the
  coverage SQL while the same comparison lived on in Python for three months.
  When fixing a bug, search for other code that makes the same comparison.
- A green job means it ran, not that it worked. For discovery, the outcome is
  current-year renewal: of schools with a live document filed under the
  previous CDS year, the share that also have one for the current year
  (`cds_freshness_floor()`; `unknown` years don't count). Check it a month after
  any discovery fix. See `docs/postmortems/2026-11-24-stale-discovery-seeds.md`.

## Migrations

Migrations are applied to production **only from `main`**, never from a
feature branch. Out-of-band applies (running a migration against prod
from an unmerged branch) leave production ahead of `main` and break
fresh `supabase db reset` for everyone else — don't do this.

**The agent applies migrations after a PR merges, not the user.** Once
a migration PR is merged, the agent's standard sequence is:

```
cd /Users/santhonys/Projects/Owen/colleges/collegedata-fyi
git switch main && git pull --ff-only
supabase db push --linked
```

(`supabase` CLI is at `/opt/homebrew/bin/supabase`; the project is
already linked. Credentials live in `~/Projects/Owen/colleges/collegedata-fyi/.env`
as `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.)

The user shouldn't need to drive `supabase db push` manually — that's
the operational step that follows every migration PR merge. The
"migrations only from main" rule is still load-bearing: the apply
must happen from a fresh `main` checkout, never from a feature
branch, never from a Conductor worktree pinned to a not-yet-merged
branch.

CI runs a `Migration filename hygiene` check on every PR (timestamp
prefix uniqueness + sort order). Full replay against a clean DB is a
manual pre-merge step (`supabase db reset` locally), not CI — several
migrations contain verification DO blocks that assume production data,
which would always fail in a clean CI database. The actual drift
between prod and `main` isn't detectable from CI without prod
credentials anyway; it's a policy safeguard.

## Edge Functions

The `Deploy Edge Functions` workflow deploys every function in
`supabase/functions/` to production when function code or
`supabase/config.toml` changes on `main`. Don't run
`supabase functions deploy` from a feature branch or worktree: the next merge
overwrites it, and an unmerged deploy leaves production ahead of `main`.
To redeploy without a code change, dispatch the workflow.

## IPEDS federal baseline operations

PRD 021 adds official NCES/IPEDS baseline facts. CDS remains the
school-authored source; IPEDS facts are federal baseline/context and must keep
source table, source variable, release type, release date, imputation status,
and definition-alignment notes visible.

- Loader/runbook: `tools/ipeds/README.md`
- Release probe workflow: `.github/workflows/ipeds-release-probe.yml`
- Core public serving view: `school_facts_unified`
- Public school-page component: `web/src/components/FederalBaselineTable.tsx`

The release probe is monthly and intentionally no-ops until 10 months after the
latest loaded provisional Access release date. When it opens an issue, run the
suggested download/load dry run first, review the report, apply any needed
migrations from fresh `main`, and only then run `load_release.py --apply`.
