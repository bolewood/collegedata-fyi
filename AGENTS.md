# AGENTS.md

Project overview, layout, and operational conventions live in [`CLAUDE.md`](CLAUDE.md)
and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Contributor setup basics are in
[`CONTRIBUTING.md`](CONTRIBUTING.md); frontend specifics in [`web/README.md`](web/README.md).

## Cursor Cloud specific instructions

The environment update script already installs dependencies on boot
(`npm --prefix web ci`, a repo-root `.venv`, and `tools/ci-requirements.txt`).
Toolchains not covered by the update script (Node 22, Python 3.12, Deno 2.x, the
`python3.12-venv` and `unzip` apt packages) are baked into the environment
snapshot. Notes below are the non-obvious bits for running/testing here.

### Services

- **Next.js frontend + friendly JSON API** (`web/`, the primary product) — the only
  long-running service you normally start. It talks to the **hosted production
  Supabase** backend (PostgREST + Edge Functions at `https://api.collegedata.fyi`),
  so there is **no local database to run**. Everything else in the repo
  (`tools/*` Python pipelines, `supabase/functions/*` Deno functions) is offline
  batch tooling or serverless code exercised only through its test suites.

### Running the web app

- Requires `web/.env.local` with `NEXT_PUBLIC_SUPABASE_URL` and
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`. This file is gitignored and NOT recreated by the
  update script. The anon key is public (RLS-scoped) and is the same one committed in
  the `web` job of [`.github/workflows/ci.yml`](.github/workflows/ci.yml); copy the
  `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` values from there. Without
  this file the dev server boots but all data-backed pages/APIs return empty results.
- Start it with `npm run dev` in `web/` (serves `http://localhost:3000`, including the
  `/api/*` friendly API). Standard scripts (`dev`, `build`, `typecheck`, `test`,
  `test:smoke`) are in `web/package.json`.

### Tests / lint / build

- Canonical commands per surface live in [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
  (web build/typecheck/test, Python unit suites, Deno function tests, migration hygiene).
- Python tools: run with the repo-root venv, e.g. `.venv/bin/python -m pytest tools/discovery -q`
  or the `unittest` invocations from CI. All CI Python jobs run against
  `tools/ci-requirements.txt` alone (the heavier `tools/*/requirements.txt` files are only
  needed to actually run those pipelines, not their unit tests).
- Deno function tests need `deno` on `PATH` (`~/.deno/bin`, already added to `~/.bashrc`);
  run with `--allow-env --allow-read` as in CI.
- Playwright smoke tests (`web/npm run test:smoke`) hit the live hosted API and require a
  one-time `npx playwright install --with-deps chromium`; they are optional for most work.

### Gotchas

- This is Next.js 16 with breaking changes from older versions — read
  `web/node_modules/next/dist/docs/` before writing frontend code (see
  [`web/AGENTS.md`](web/AGENTS.md)).
- Do NOT run database migrations from this environment. Per [`CLAUDE.md`](CLAUDE.md),
  migrations are applied to production only from a fresh `main` checkout after a PR merges,
  never from a feature branch.
