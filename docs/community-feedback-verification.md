# PRD 037 implementation evidence

Prepared 2026-11-09 in the isolated `community-feedback-prd037` worktree.
Production writes are disabled; no production migration, deployment, real email,
third-party outreach or submitted-story publication occurred.

| Check | Evidence and boundary |
|---|---|
| Web types | `npm --prefix web run typecheck` passed |
| Web unit/regression suite | 813 passed, 5 existing skipped tests (81 passed files, one skipped); includes request validation, limits, fixed errors, context sanitizers, Sentry filters, content approval and existing usage-model checks |
| Python/SQL/ops/API usage | 103 passed using real isolated PostgreSQL 17 plus worker/provider mocks; all anon/authenticated table operations and RPC calls denied, real concurrent admission/idempotency, both windows, midnight bucket, leases, retention, publication-record constraints, count-only delivery, retries, workflow/freshness wiring, usage exclusions |
| Enabled browser flow | Desktop and mobile Chrome with real Next → local prefix gateway → PostgREST 16.5 → PostgreSQL 17; only provider delivery mocked; no production credentials/storage. 10 passed with no retries; the checked harness prints the final test count and verifies private canaries stay out of non-form outbound bodies, persistent storage and local server logs |
| Disabled production-mode smokes | 29 passed, 7 skipped: six enabled-flow cases deliberately skipped outside isolated storage, plus the preexisting desktop skip for a mobile-only layout case; checked footer, API/usage invitations, four references, school/year context links and existing homepage/Compare/school/API/MCP behavior |
| Production build | Standard `npm --prefix web run build` passed with public read-only configuration from CI; existing acceptance/GPA artifact requests logged some timeouts and used their fallback paths, with no nonzero exit |
| Workflow/static checks | GHA heredoc lint and `git diff --check` passed; feature migration timestamp follows current main without colliding with PRD 036 |

The form's axe checks cover WCAG 2 A/AA, 2.1 AA and 2.2 AA selectors. Small-screen
geometry, keyboard focus/error announcement markup, no-JS fallback, long URLs,
mode-specific email requirement, retained drafts and identical retry ids are
covered. The zoom test emulates the CSS viewport/device scale of a 1280×800
screen at 200% zoom; no human screen-reader session is claimed. Browser source
inspection found and fixed default blue native controls by applying forest.

Local development uses Webpack after a local Turbopack Google-font import-map
error; the standard production Turbopack build passes. An interrupted bundled
Chromium install was replaced by Playwright's supported installed-Chrome channel
(`PLAYWRIGHT_BROWSER_CHANNEL=chrome`). Initial no-JS locator failures were fixed
by inspecting noscript DOM content because Playwright's text matcher omits that
node. The local proof's prefix gateway matches Supabase's `/rest/v1` routing;
RPC persistence and SQL access checks are real, not mocked.

Live sender verification, actual delivery to the monitored mailbox, production
trusted-IP behavior, production retention cron execution and final story approval
remain unproven launch checks. See [the runbook](community-feedback.md). M3 is
intentionally deferred until the 30-day review; future message processing and
publication require real submissions and separate final approval.

All local logs/screenshots/traces live under ignored `scratch/community-feedback`
or Playwright's ignored outputs, never as public message artifacts. Reproduction
commands and isolation guards are in the runbook and `tools/community/`.
