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
