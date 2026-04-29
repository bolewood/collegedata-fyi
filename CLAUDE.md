# collegedata.fyi

Open-source archive of U.S. college Common Data Set (CDS) documents.

- **Live site:** https://collegedata.fyi (Next.js on Vercel)
- **API:** https://api.collegedata.fyi (PostgREST on Supabase)
- **Architecture:** `docs/ARCHITECTURE.md` (eight pipelines: schema, corpus, discovery, mirror, extraction, scorecard, consumer API, frontend)
- **Frontend PRD:** `docs/prd/002-frontend.md`
- **Design system:** `web/DESIGN_SYSTEM.md` (canonical tokens in `web/src/app/tokens.css`; live reference at `/design-system/`). **Read before writing any UI.**

## Project layout

- `web/` — Next.js 16 frontend (TypeScript, Tailwind, @supabase/supabase-js)
- `supabase/` — Postgres migrations, Edge Functions (Deno/TS), shared modules
- `tools/` — Python extraction pipeline, schema builder, corpus tools
- `schemas/` — Canonical CDS schema JSON (1,105 fields)
- `docs/` — Architecture, PRDs, ADRs, research, backlog
- `scratch/` — Throwaway operational outputs (gitignored). Default
  destination for any one-off run artifact: audit/drain JSON dumps,
  CSV worklists, screenshots, ZIP handoffs, debug exports. Scripts
  that emit these should write to `scratch/<tool-name>/` rather than
  into `tools/` or the repo root, so working trees stay clean and
  nothing important hides among the dumps.

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

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
