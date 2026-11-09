# Community feedback operations (PRD 037)

Implementation prepared 2026-11-08. **Not launched.** Website writes and mail
sends are off by default. This branch does not apply production migrations,
deploy, send live mail, contact project owners, or publish private stories.
[PRD](prd/037-feedback-stories-and-github-stars.md) ·
[copy deck](copy/037-feedback-stories-and-github-stars.md).
[Verification evidence](community-feedback-verification.md).

## What is implemented

`/feedback` offers feedback, stories, and data problems, with optional email
except when discussing being featured. In its default disabled state, the page
explains that the website form is unavailable and keeps email available without
showing an unusable form. With
JavaScript off and writes enabled, send stays disabled and the email alternative remains visible.
Drafts and retry identity live only in the current tab's memory. Successful
storage returns a private receipt; no public lookup exists. Nothing is published
from the queue automatically. Star links measure outbound clicks only.

Permanent invitations are in the footer, API documentation, usage page and
school hub/year pages. Repository, CLI and MCP documentation link the form;
runtime CLI/MCP output is unchanged. Four factual project references were
rechecked against their own source on 2026-11-08 and carry dates/evidence links.
There are no approved submitted stories. `/usage.json` and public usage tables
are unchanged; aggregation excludes all `community_*` RPC/table traffic.

## Launch checks: still required, not inferred from local tests

Keep `COMMUNITY_FEEDBACK_ENABLED` unset/false until all checks are recorded here
or in a private operator checklist. Never paste keys or inbox dumps into GitHub.

1. Merge and apply the migration **from fresh main only**, per `CLAUDE.md`.
   Verify three private tables have RLS and no anon/authenticated grants; verify
   all five functions deny anon/authenticated execution. Verify no public view,
   export, or publication includes private fields. Replay this feature migration
   on isolated test storage before applying; full corpus replay has separate seed
   requirements. These tests do not claim a full Supabase migration replay.
2. Confirm the existing `pg_cron` extension is installed and the hourly
   `community-feedback-retention` job exists and is active (`41 * * * *`).
   The migration intentionally skips scheduling on vanilla PostgreSQL without
   the extension, allowing isolated tests; production must not skip it.
   `tools/ops/automation_health.py` includes the retention job in its cron checks.
3. Confirm the maintainer can sign in to the Supabase dashboard and open the
   `public.community_submissions` table. Record a fixed inbox HTTPS URL matching
   `https://supabase.com/dashboard/project/<20-character-ref>/editor[/table-path]`.
   Never use a public inbox URL, token, query or fragment in that link.
4. Verify `contact@bolewood.com` is monitored and receives mail. Set two review
   sessions weekly (initial budget: ten minutes each); no reply SLA is promised.
5. Verify the Resend sending subdomain and restricted sending key. Sender must
   be exactly `CollegeData.fyi <feedback@notify.collegedata.fyi>`. Disable provider
   open/click tracking in domain settings. No SDK or marketing list is involved.
   No sender verification or provider delivery was performed in this worker run.
6. Provision server-only Vercel production environment:

   | Name | Value / requirement |
   |---|---|
   | `COMMUNITY_FEEDBACK_ENABLED` | `true` only after launch proof |
   | `COMMUNITY_FEEDBACK_ORIGINS` | exact comma-separated origins, e.g. `https://www.collegedata.fyi,https://collegedata.fyi`; no host-derived values or wildcards |
   | `COMMUNITY_RATE_LIMIT_SECRET` | separate random secret, at least 32 characters; never reuse a Supabase key |
   | `NEXT_PUBLIC_SUPABASE_URL` | existing project URL |
   | `SUPABASE_SERVICE_ROLE_KEY` | server-only existing privileged credential |

   The gate allows Vercel `production` only; preview remains unwritable even if
   flags are copied. Local development additionally requires
   `COMMUNITY_ALLOW_LOCAL_WRITES=true` and `NODE_ENV` other than production.
   Use only explicitly isolated local storage for that setting.
7. Confirm the actual deployment receives Vercel's overwritten
   `x-vercel-forwarded-for` header as one valid IP. The handler refuses missing,
   malformed, comma-separated or untrusted non-Vercel production sources. It does
   not read `x-forwarded-for`, `Host`, or `Referer`. If the platform/proxy topology
   changes, re-prove the trust boundary before enabling. Do not “fix” a failure by
   accepting a sender-supplied fallback header.
8. Provision GitHub Actions secrets: `SUPABASE_URL` (the project's canonical
   `<ref>.supabase.co` origin), `SUPABASE_SERVICE_ROLE_KEY`, `RESEND_API_KEY`,
   `COMMUNITY_NOTIFICATION_FROM`, `COMMUNITY_INBOX_URL`. The recipient is fixed
   in code/SQL to `contact@bolewood.com`; there is no request/config recipient.
   Set repository variable `COMMUNITY_NOTIFICATIONS_ENABLED=true` only once
   sender/inbox checks pass. The workflow runs only on main at minute 17 hourly.
   Missing/disabled configuration fails visibly instead of pretending delivery
   is healthy. Until configured, the new workflow may report a configuration
   failure; the form must remain disabled.
9. Perform an authorized launch proof using a non-sensitive maintainer message
   and approved isolated test delivery, then verify a real production digest only
   when separately authorized for launch. Inspect the receipt, count-only email,
   authenticated inbox and review routine. Mark synthetic receipts using the
   operator-only `synthetic` flag before ordinary worker runs. Synthetic rows are
   excluded from digest admission and operating counts; never accept a public
   request flag for it. Do not use live visitor messages as test fixtures.
10. Confirm failure/recovery alerts and scheduled freshness. The exact workflow
    name `Community feedback notifications` is in both Discord allowlists.
    The hourly notifier checks the last **successful scheduled** run on an
    eight-hour threshold and alerts even if none exists. A disabled schedule,
    repeated failing schedule, or no initial success is visible. A worker sees
    unresolved batches older than 24 hours as a failure even after recovering
    delivery; the following healthy run establishes recovery. Review retention
    cron health too. No private message content goes to Discord.

Only after those checks enable website writes. Record the real invitation launch
date, aggregate star count and reference count (four at implementation); this
branch does not fabricate a launch baseline or delivery result. Review at 30 and
60 days. Unique, non-spam, non-synthetic receipts are the operating total;
browser saved events are approximate. API requests, stars and people are separate.

## Queue, retries, privacy and incident response

A transaction-scoped admission lock makes receipt identity and shared rate
limits atomic across server instances. Exact normalized-payload retries return
the existing receipt before consuming a limit. Reusing an id with changed data
conflicts. Five messages per rolling ten minutes, twenty per UTC day, with a
previous-day HMAC bucket included across midnight. The database uses its clock
for admission times. The server HMAC includes UTC date and verified IP; only
bucket/counters are stored, never raw IPs. Secret rotation may reset quotas, so
avoid routine mid-window rotation; keep the secret out of client bundles/logs.

The worker claims the oldest unresolved batch before creating another. A short
transaction associates at most 500 new non-spam/non-synthetic rows with one batch;
then releases the DB lock before HTTP delivery. Five-minute leases have unique
claim tokens; a stale worker cannot acknowledge a newer lease. The immutable
payload contains only count, fixed recipient/sender, and fixed private inbox link.
Provider requests have a 20-second bound. Failure records only `provider`,
`timeout`, or `configuration` and backs off across scheduled runs (up to six
hours); it never deletes messages. Operators retry by rerunning the workflow,
not by clearing associations or generating a new batch. If a retry needs to be
advanced, change only `next_retry_at` on the existing batch while no live lease
exists, then run the workflow. Waiting on an unresolved retry/lease is a visible
`retry_pending` failure, so a backoff-only run cannot report false delivery
recovery. Diagnose using counts/statuses, never queue dumps.

Resend idempotency is 24 hours, with key `community-feedback/<batch UUID>`.
A provider timeout is ambiguous. After that window, a repeated digest may occur;
delivery is at least once. The private queue is the source of truth. Completed
batch metadata expires after 30 days; unresolved batches never expire silently.
`notified_at` prevents a retained receipt from being rebatched when its completed
batch metadata is deleted. Count-only payloads remain safe after raw rows expire.

Hourly SQL maintenance is independent of mail. Rate records expire at 47 hours
(leaving one scheduled-hour margin before 48). Raw messages/contact/request ids
and digests are scrubbed an hour before 180 days, spam before 30 days. Unapproved
rows are removed; approved rows retain only final publication permissions.
Withdrawal evidence expires an hour before 90 days. Unresolved notification FKs
do not prolong raw-content retention. Alert/check cron health after database
outages and run `select public.community_expire()` when recovering.

The feedback page and handler are excluded from Sentry error capture; feedback
breadcrumbs are dropped. The installed Sentry 11 SDK streams spans by default,
ignoring `beforeSendTransaction`, so shared setup explicitly uses static traces
and drops private-route traces as well as refusing sampling them. Analytics
strips feedback query/hash data and emits only bounded community properties.
No replay, request body logs, receipts, school ids, messages, or contact details
are added to analytics. Hosting/security logs remain separate as privacy explains.

For a form/privacy incident, unset `COMMUNITY_FEEDBACK_ENABLED` first, pause
active invitations if necessary, retain email fallback, and investigate private
receipts without publishing dumps. Disable notifications separately for provider
incidents; durable receipts remain saved. Check queue health and retention before
reenabling. No college-data API contract/count export changes are needed.

## Review and final publication

Read plain text in the authenticated dashboard; never execute submitted Markdown,
HTML, scripts or terminal snippets. Do not fetch private links or create previews.
Treat links as untrusted; if you choose to open one after review, use ordinary
browser precautions. Restrict service-role credentials to necessary operators.

Set review `new → reviewed → closed` (or `spam`), record `reviewed_at`, and reply
through the existing mailbox only if supplied and warranted. Move actionable data
problems into normal issues after removing personal information. Do not copy a
private message verbatim into GitHub. No automatic outbound reply exists.

Publication state is separate: `none → candidate → awaiting_approval → approved`,
or `withdrawn`. Initial story interest only permits a conversation. For each story:

1. Draft the exact final write-up, credit, project link and any quote.
2. Send the copy deck's final approval template manually only in an authorized
   conversation. Explain publication on the website and source repository under
   CC BY-SA 4.0, ownership, reuse with credit, and limits of removing Git history
   or third-party copies. Silence is never approval.
3. Store separately in `publication_permission` only: `text`, `credit`, `link`,
   optional `quote`, `version`, `approved_at`, and a private `evidence_ref` to
   affirmative approval. Do not retain the whole original message/contact there.
4. Add only approved public fields to `web/src/data/community/projects.ts`.
   Use `kind: approved_story`, `publicationStatus: approved`, and identical
   `contentVersion` / `approvedVersion`. The checked loader rejects extra private
   fields, contact addresses, unsafe links and duplicate slugs; it omits unapproved,
   withdrawn or mismatched-version stories. Private evidence
   refs, contact addresses and receipt ids never go in Git. A different final
   text/credit/quote/link requires a new version and renewed approval.
5. Review content and tests in an ordinary PR. Remove withdrawn entries from the
   live/current source promptly, set `withdrawn_at`, and let permission retention
   expire. Do not leave withdrawn quotes committed merely hidden by a filter.
   Usage statistics remain available independently.

Public references use factual paraphrases, dates and exact source links, not
borrowed testimonials. Review quarterly/on requests. Curated descriptions are
CC BY-SA 4.0 under the scoped data README, usage statistics CC0, application
code MIT, linked projects retain their own terms.

## Deferred by design

M3, the export-adjacent inline prompt, is **not implemented**. Consider it only
at the 30-day review after real delivery/triage works and evidence shows permanent
invitations are missed. There are no timers, popup, local display/dismissal storage,
export hooks, fabricated outcomes, review widgets, or rating schema in this PR.
The first submitted story must wait for real final consent; no placeholder quote
or public reference is substituted for permission.

## Verification commands and limits

Use the public read-only variables already in `.github/workflows/ci.yml` for
ordinary web build/smokes; never load the coordinator's production `.env` for tests.

```
npm --prefix web ci
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
python3 -m unittest tools.community.test_notify_feedback tools.community.test_usage_exclusion tools.ops.test_notify_discord tools.ops.test_automation_health tools.api_usage.test_ingest_gateway_logs tools.api_usage.test_publish
```

For SQL use a fresh localhost PostgreSQL 17 database named
`community_feedback_test`. Tests refuse other hosts/names, apply only this feature
migration, and truncate only that isolated database's three feature tables.
`psql` must be on PATH, or set `PSQL` explicitly. CI provides a PostgreSQL 17
service and runs these checks without production secrets.

```
export COMMUNITY_TEST_DATABASE_URL=postgresql://127.0.0.1:55437/community_feedback_test
python3 -m unittest tools.community.test_database
# Optional real browser flow; requires local PostgREST, npm deps and Chromium:
cd web && npx playwright install chromium && cd ..
python3 -m tools.community.local_web_smoke
```

The latter uses Next’s Webpack development mode for the local proof (the
standard Turbopack production build is checked separately). If the bundled
Playwright browser is unavailable, an installed Chrome can be used with
`PLAYWRIGHT_BROWSER_CHANNEL=chrome`. It starts temporary Next/PostgREST servers on 3047/55439 with a local prefix
proxy on 55438, connects only to
that isolated DB, runs desktop/mobile Playwright and axe, then uses the real
notification RPCs with a **mocked Resend HTTP delivery**. It checks browser canaries
stay out of non-form outbound payloads, persistent storage and local server logs.
The SQL suite exercises real grants/RLS, 20 concurrent identical retries, 30
concurrent admissions, daily/rolling windows, previous-day rotation, claims/leases,
retry identity, overdue monitoring and retention with simulated dates. The unit
suite covers request validation, streaming limits, exact Origin, unavailable
storage/config/IP, redaction and publication filters. Browser tests exercise
no-JS fallback, small screens, accessible errors, 429/503/timeout draft retention,
identity reuse and an actual durable receipt. The production disabled-state smoke
is separate; enabled browser cases deliberately require isolated storage.

These checks do not prove sender verification, live mailbox delivery, Vercel's
production proxy/header behavior, a running production retention schedule,
human screen-reader output or human publication approval. All remain launch or
manual review checks, not results asserted by mocks.


## Implementation review notes

- Supabase's standalone local PostgREST serves `/rpc` rather than the hosted
  gateway's `/rest/v1/rpc`. The proof harness supplies only that prefix rewrite;
  storage, grants, admission, leases and retention remain real PostgreSQL/RPCs.
- Preview writes are kept completely off. This is stricter than the planning
  document's optional trusted-preview path because no isolated deployed preview
  project was provisioned; the complete write flow was proved locally instead.
- Sender verification and mailbox monitoring are launch dependencies. Local mock
  delivery is never described as real notification receipt.
- The shipped disabled state offers email without an unusable form; the enabled
  no-JS state explains JavaScript and keeps the submit button disabled.
- The approved planning/copy documents were copied from the coordinator checkout
  before coding and preserved, with an implementation-status note. PRD 036 and
  scholarship implementation are outside this branch's scope.
- This is a draft feature PR, not a release. Release/version bookkeeping and
  production rollout remain with the coordinator's later landing work; no worker
  or external review agent was spawned, per the task's explicit restriction.
