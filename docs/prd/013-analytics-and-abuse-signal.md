# PRD 013: Analytics, abuse signal, and commercial-tier readiness

**Status:** Draft — measurement required before alerting thresholds set
**Created:** 2026-04-28
**Author:** Claude + Anthony
**Related:** [PRD 001](001-collegedata-fyi-v1.md), [PRD 010](010-queryable-data-browser.md), [PRD 012](012-browser-field-expansion-after-v03.md)

---

## Context

collegedata.fyi has Vercel Web Analytics wired into the frontend root layout
(`web/src/app/layout.tsx:3,65`) — page-view-level signal only, no named events,
no API-side observability, no abuse signal. Three blind spots all become real
once the queryable browser ships:

1. **Product/event signal.** PRD 010 and PRD 012 are landing filter UX without
   any feedback on which fields, operators, or query patterns users actually
   use. Vercel Analytics gives pageviews; not enough.
2. **API abuse signal.** A single bad-faith client could scrape-bomb
   `api.collegedata.fyi` until Supabase egress alerts fire — there is no earlier
   warning and no rate limit between the public internet and PostgREST.
3. **Commercial-tier readiness.** There is no way to see when an API consumer has
   crossed from "researcher with `curl`" to "company building on this backend." A
   commercial tier requires that signal first.

This PRD proposes three small, independent additions. None are billed as required
for the others. Vercel Analytics stays in place; PostHog adds the named-event
layer alongside it.

## Goals

1. Know which frontend features get used and how.
2. Know when API traffic is anomalous in volume, source, or pattern.
3. Get a weekly push signal — abuse candidates and commercial-tier candidates —
   without logging into a dashboard.

## Non-goals

- Not building a billing system or commercial-tier auth yet. This is the signal,
  not the product.
- Not adding user accounts or API keys. The API stays anonymous-public.
- Not building an event-streaming pipeline.
- Not storing PII beyond what Cloudflare and PostHog already see by default — but
  see §"Privacy posture" for what that means and what the project commits to.
- Not replacing Supabase logs as the source of truth for DB-level diagnostics.

## Required Pre-Implementation Work

This PRD is not approved for implementation until the following are resolved.

### 1. Privacy posture decision

The PRD assumes IP addresses are personal data under GDPR/CCPA the moment they
leave the user's device for a third-party processor (PostHog Cloud, Cloudflare,
Resend). That obligation does not depend on cookies — it depends on the data
flow. Before any tracking code ships, decide:

- **Option A — Consent banner.** Add a minimal banner to the frontend; PostHog
  initializes only after consent. Highest legal safety, worst UX.
- **Option B — EU self-host.** Run PostHog self-hosted in an EU region; treat as
  first-party. No banner. Highest infra cost.
- **Option C — Acceptance of risk with public posture.** No banner; publish a
  `/privacy` page describing exactly what is collected, retained, and shared.
  Provide a `mailto:` for deletion requests. Acceptable risk for a small
  open-source archive; not zero risk.

The project should pick one explicitly in this PRD before Phase 1. Default
recommendation: **Option C**, with the privacy page treated as a release
blocker.

### 2. Cloudflare free-tier reality check

Cloudflare WAF rate limiting on the free tier is **1 rule**, not 10 (Pro is 2,
Business is 5). Free-tier expression fields are limited. The MVP abuse design
must fit inside one coarse rule on the whole zone, or the PRD must explicitly
accept a paid tier or an alternate enforcement layer.

Decide before Phase 2:

- **Option F1 — One coarse free-tier rule.** A single `*.collegedata.fyi` rule
  with a generous request-rate ceiling (e.g., `1000 req/min` from a single IP).
  Imprecise but functional. Cannot split api vs functions vs frontend traffic.
- **Option F2 — Paid CF tier.** Pro ($25/mo) for 2 rules; Business ($250/mo)
  for 5. Buys split limits per subdomain. Probably overkill for current scale.
- **Option F3 — Cloudflare Worker rate limiting.** Use a Worker with the
  Rate Limiting API to enforce per-path limits. Free tier gives 100K Worker
  requests/day, enough for the public API at current scale.
- **Option F4 — Supabase-side enforcement.** Wrap PostgREST behind a thin Edge
  Function that enforces per-IP rate limits via Redis or a Postgres table. Most
  control, most code.

Default recommendation: **Option F1** at MVP, with F3 as the fallback if F1
proves too coarse during Phase 5 tuning. Do not ship assuming 10 rules.

### 3. PostgREST header-passthrough verification through Cloudflare

PostgREST relies on non-standard headers that some CDNs strip or rewrite.
Verification must precede DNS flip and be recorded as test output, not as a
"smoke test" bullet.

Required end-to-end checks against a CF-proxied test domain:

- `Prefer: count=exact` returns `Content-Range: 0-N/total`
- `Prefer: return=representation` returns the inserted row body
- `Range: items=0-9` returns the requested slice with `Content-Range`
- `Accept-Profile: <schema>` selects the requested schema
- `?select=*,joined(*)` embedded resource queries return the embedded data
- JSONB charset is preserved (`application/json; charset=utf-8`)

Failure on any check blocks DNS flip. Result captured in `.context/cf-postgrest-passthrough.md`.

### 4. Functions routing decision

`browser-search` is currently invoked at
`${NEXT_PUBLIC_SUPABASE_URL}/functions/v1/browser-search`
(`web/src/lib/browser-search.ts:180`) — the raw Supabase project URL, **not**
behind `api.collegedata.fyi`. Putting it behind Cloudflare requires an explicit
routing change. Decide before Phase 2:

- **Option R1 — `functions.collegedata.fyi` subdomain.** New CNAME proxied
  through CF to the Supabase Functions origin. Split env vars:
  `NEXT_PUBLIC_SUPABASE_REST_URL` for PostgREST,
  `NEXT_PUBLIC_SUPABASE_FUNCTIONS_URL` for Edge Functions. Cleanest separation.
- **Option R2 — Path routing under `api.collegedata.fyi`.** CF Page Rules /
  Workers route `/functions/*` to the Functions origin and everything else to
  the PostgREST origin. Keeps a single subdomain; more CF config to maintain.
- **Option R3 — Leave Functions outside CF.** Accept that `browser-search`
  isn't behind the rate limit. Public PostgREST is the only protected surface.

Default recommendation: **Option R1**. Splitting the env vars now is also good
hygiene independent of CF. Without this decision, "browser-search behind CF"
in §B is aspirational.

### 5. Baseline traffic collection

Thresholds for rate limiting, abuse alerts, and commercial-tier candidates must
be derived from observed traffic, not picked from the air. The implementation
plan below treats the first 4–6 weeks as collection-only: data is captured by
PostHog, Cloudflare, and Supabase logs, but no alerts fire and no rate-limit
rules are active. Threshold-setting happens after baseline.

### 6. Verify Supabase plan supports scheduled Edge Functions / pg_cron

Phase 4 depends on a weekly cron. Confirm the project's Supabase plan supports
either Supabase Cron (scheduled Edge Functions) or `pg_cron`. Fall back to
external cron (cron-job.org HTTP poke) only if neither is available.

## Recommendation

Three additions, shippable independently. Complementary, not alternatives.

### A. PostHog on the frontend (named events only)

Initialize `posthog-js` in the Next.js root provider with:

- `autocapture: false`
- `persistence: 'memory'` — no cookies
- `disable_session_recording: true`
- `mask_all_text: true` for any captured DOM (defensive)
- `respect_dnt: true` — honor `Do Not Track`

Privacy posture (per Pre-Implementation §1) determines whether this initializes
unconditionally or only after consent.

#### Event set (MVP)

Properties are deliberately pre-flattened to scalar values so PostHog's
breakdown UI is usable on the free tier. Capture richer context as separate
forensic-only properties (e.g., `filter_spec_json`) but do not rely on them for
dashboards.

| Event | Pre-flattened scalars | Forensic blob |
|---|---|---|
| `browse_filter_applied` | `field_count`, `has_act_filter`, `has_sat_filter`, `has_gpa_filter`, `has_enrollment_filter`, `op_inequality_count`, `op_blank_count`, `result_count`, `mode` (latest-per-school / all-years) | `filter_spec_json` |
| `browse_csv_export` | `filter_count`, `row_count`, `column_count` | `filter_spec_json` |
| `school_search_submitted` | `query_length`, `result_count` | — |
| `school_page_viewed` | `school_id`, `year` | — |
| `api_link_clicked` | `resource` | — |
| `external_pdf_opened` | `school_id`, `year` | — |

#### Server-side capture

`browse_filter_applied` and `browse_csv_export` must be captured server-side
from the `browser-search` Edge Function, not only client-side. Ad-blockers
and privacy extensions block client-side analytics aggressively, and these
are the highest-value events for the queryable browser. Page-level events
(`school_page_viewed`, `external_pdf_opened`) stay client-side.

`browser-search` runs on Deno, so the Node SDK is the wrong tool. Use
PostHog's HTTP capture API directly via `fetch`:

```ts
await fetch(`${POSTHOG_HOST}/capture/`, {
  method: 'POST',
  body: JSON.stringify({
    api_key: POSTHOG_PROJECT_KEY,
    event: 'browse_filter_applied',
    distinct_id: anonymousId,
    properties: { ...flattenedScalars, $lib: 'collegedata-edge' },
  }),
});
```

Fire-and-forget; do not block the user response on the capture call.

#### Pageviews

Disabled at MVP. Reconsider after 4 weeks if named events alone don't explain
behavior.

#### Internal-traffic marker (analytics only)

The frontend includes a header `X-Internal-Traffic: 1` (set via a developer
build flag or browser extension) that the server-side capture skips. The
digest worker (Part C) also filters this header out of CF analytics. Avoids
the multi-IP problem of trying to allowlist Anthony's home/mobile/Conductor/CI
addresses.

**This header is for analytics filtering only.** It must never be honored by
rate-limit, abuse-classification, or auth logic — a client-set header is
spoofable and would be a free abuse-bypass. CF rate-limit rules and the
abuse-detection logic in §C apply to all traffic uniformly. For stronger
self-filtering on the rate-limit path (rare), use a secret-bearing operator
script or short-lived signed token, not this header.

#### Feature flags (deferred)

PostHog feature flags are available at no extra cost. Likely first uses are
PRD 012's submit-rate guard threshold and PRD 010's latest-window semantics.
Out of scope for MVP; flagged here so the integration can be reused.

### B. Cloudflare in front of `collegedata.fyi`, `api.collegedata.fyi`, and (per Pre-Implementation §4) `functions.collegedata.fyi`

DNS-only migration. Cloudflare proxies to Vercel (frontend), Supabase PostgREST
(API), and Supabase Edge Functions (`browser-search`).

Free-tier features used at MVP:

- **Analytics dashboard.** Traffic, top countries, top paths, error rates, bot
  share.
- **Basic bot management.** Flags known scrapers and crawlers.
- **Rate limiting.** **One free rule** (per Pre-Implementation §2). No rule
  active at launch; rule is configured after baseline (Pre-Implementation §5)
  provides ground truth for what "normal" first-party traffic looks like.
- **Edge cache.** Off at MVP. Reconsider once egress costs justify it; the right
  number is "1 hour with purge-by-URL on extraction worker writes," not the
  guessed 5 minutes from v1 of this PRD.

#### Rate-limit rule design (one rule)

With a single free rule, the choice is coarseness vs targeting:

- A zone-wide ceiling (e.g., `1000 req/min/IP` across `*.collegedata.fyi`)
  catches scrape bombs against any subdomain. Will not distinguish
  first-party browser traffic from API abuse.
- A targeted rule (e.g., `/cds_*` paths only) protects the heaviest abuse
  surface but leaves `browser-search` and the frontend unprotected.

Default recommendation: **zone-wide ceiling** at MVP. If baseline shows that
first-party traffic risks tripping it, fall back to Pre-Implementation §2
Option F3 (Cloudflare Worker) for per-path enforcement.

#### `browser-search` Edge Function

Per Pre-Implementation §4, `browser-search` is currently invoked at the raw
Supabase URL. It is **not** behind CF until the routing decision lands.
Phase 2 wires `functions.collegedata.fyi` (Option R1) and splits the env vars;
without that, the rate-limit rule cannot protect `browser-search`.

#### DNS TTL plan

Drop both apex/CNAME TTLs to 60 seconds at least 24 hours before the migration.
Hold low TTL for the first 30 days post-migration. Raise after stable. A CF
outage during peak traffic without low TTL is hour-scale recovery; with low
TTL it is minute-scale.

### C. Weekly digest worker

A Supabase Edge Function (`weekly-analytics-digest`) that runs Mondays at 09:00
local time and sends one email.

Data sources:

- **Cloudflare Analytics API** — traffic, top IPs, top paths, top countries,
  error rate, 429 counts (none until rate limits are turned on)
- **PostHog API** — top named events, week-over-week deltas
- **Supabase logs / `pg_stat_statements`** — top SQL queries, slow queries

#### Email sections

1. **Frontend.** Top events this week with WoW % delta. Anomalies flagged.
2. **API.** Total requests, top 10 paths, top 10 IPs by volume excluding
   `X-Internal-Traffic`, country mix, error rate.
3. **Commercial-tier lead hypotheses.** Not "candidate truth" — IP/UA/ASN
   patterns are noisy (NAT, CGN, shared cloud egress, researcher notebooks
   running in Colab/Codespaces all produce false positives). Surface as leads
   when an IP or UA+ASN meets *all* of (a) sustained traffic across 30+ days,
   (b) regular request intervals suggestive of programmatic use, (c) traffic
   from a cloud ASN (AWS/GCP/Azure/Hetzner/etc.), and (d) repeated hits on
   high-value endpoints (`cds_fields`, `school_browser_rows`, CSV export
   paths). Threshold counts derived from baseline (Pre-Implementation §5).
   Treat the list as "worth a closer look," not as billable customers.
4. **Abuse candidates.** IPs triggering rate-limit 429s, or appearing in CF's
   bot-flagged traffic at high volume.
5. **Anomalies.** Per-metric definitions (see §"Alert definitions"), not free-form.

If a section is empty, omit it rather than report "no anomalies." Digest fatigue
is the failure mode; an empty section communicates the same fact silently.

#### Candidate-to-action workflow

A candidate appearing 3 weeks running triggers a one-line outreach: a
`mailto:` link is included in the digest entry so Anthony can reply with one
keystroke asking "What are you building? Would a paid tier help?" The signal
is operationalized; it isn't a list that grows forever.

#### Self-traffic exclusion

The digest worker filters out:

- Requests carrying `X-Internal-Traffic: 1`
- IPs in a small allowlist (`internal_ip_allowlist` config)
- UA strings matching a configured pattern (`internal_ua_pattern`)

Configuration lives in env vars or a small `analytics_config` table, not source.

#### Send

Via **Resend** (recommendation; not currently configured). Free tier covers 100
emails/day, well above weekly cadence. Recipient is a single address (Anthony)
at MVP — exact address kept in env vars, not in the PRD.

### Alert definitions

Quantitative, per-metric, set after baseline:

| Metric | Alert condition |
|---|---|
| API total requests | `>2σ` from rolling 4-week mean OR `>100%` WoW change |
| Top-event count | A top-5 event drops out of top 20 |
| Error rate | `>2%` of total requests in any 24h window |
| 429 rate | `>1%` of total requests OR `>100` per IP per day |
| New top-IP | An IP enters the top 10 with `>5x` the historical median for top-10 |

These get tuned after Phase 4 (week 8+) once the worker has produced 4 digests
and the false-positive rate is observable. They live in config, not source.

## Privacy posture

Per Pre-Implementation §1, the project's default recommendation is **Option C**:
no consent banner, with a public `/privacy` page documenting the data flow.

**This PRD has not had legal review.** The posture below is documented for
transparency and operational clarity, not as a guarantee of GDPR/CCPA compliance.
A real legal review is a follow-on; until then, treat the posture as
best-effort.

- **What is collected.** IP address, user agent, request path, request count,
  named events with their pre-flattened properties. No form contents, no
  free-text from search queries beyond length.
- **Who processes it.** Cloudflare (CDN/analytics), PostHog Cloud (US-region
  product analytics), Supabase (logs), Resend (digest delivery), Vercel
  (hosting + Web Analytics).
- **How long it's kept.** See "Data retention" below.
- **How to delete.** A `mailto:` to a privacy contact. Deletion is best-effort
  via vendor tooling — PostHog supports per-distinct-id deletion via API; CF
  and Vercel Analytics aggregate at the IP level and per-IP deletion is not
  always exposed in the UI. Document what is and isn't reasonably possible on
  the `/privacy` page rather than promising more.
- **Opt-out.** `Do Not Track` browser header is honored for PostHog. CF,
  Vercel Analytics, and Supabase logs are unavoidable on a request-served
  basis (no client-side opt-out).

If a future EU traffic spike makes this posture untenable, fall back to Option B
(self-host EU PostHog) as the next step before Option A (consent banner).

## Data retention

Documented for transparency:

| Source | Retention |
|---|---|
| PostHog events | Configured to 90 days at project level (PostHog free tier defaults to 1 year; we deliberately shorten via PostHog data-management settings). Verify the configuration is in place before launch. |
| Vercel Web Analytics | Per Vercel free-tier defaults |
| CF analytics | Per CF free-tier default (typically 90 days for the dashboard; longer via Logpush, which we do not enable) |
| Supabase logs | Per plan default; do not extend without re-evaluating |
| Digest emails | Indefinite in Anthony's mailbox; not stored elsewhere |
| `analytics_config` (allowlists, thresholds) | Indefinite; non-personal |

Retention reductions can be made unilaterally; extensions require updating the
`/privacy` page. PostHog retention specifically requires a configuration step,
not a default — confirm in PostHog UI before declaring Phase 1 done.

## Alternatives considered

### Alt 1: Skip Cloudflare, observe via Supabase logs only

Possible, but PostgREST has no native rate limit. Without an edge layer, the
only abuse response is reactive — pull logs after egress alerts fire. **Reject.**

### Alt 2: Plausible / Fathom / GoatCounter instead of PostHog

Lighter weight, more privacy-respecting (often EU-hosted, IP-stripping by
default), but pageview-only. We need to know which filter combos and operators
get used in `/browse` — that requires named events. **Reject for MVP. Revisit
if PostHog's privacy posture is rejected at Pre-Implementation §1.**

### Alt 3: Skip the digest, rely on dashboards

A one-person project without push notifications won't check dashboards on a
regular cadence. Push beats pull. **Reject.**

### Alt 4: API keys + per-key rate limit now

Forces auth on the API and breaks the "anonymous-public" property the project
has deliberately preserved. Only worth doing once a paid tier exists. **Defer
until this PRD's signal proves the need.**

## Implementation plan

### Phase 1: Privacy decision, PostHog wiring, env split

1. Resolve Pre-Implementation §1 (privacy posture). Publish `/privacy` if Option C.
2. Resolve Pre-Implementation §4 (functions routing). If Option R1, split env:
   `NEXT_PUBLIC_SUPABASE_REST_URL` and `NEXT_PUBLIC_SUPABASE_FUNCTIONS_URL`.
   Update `web/src/lib/browser-search.ts` and any other Functions callers.
3. Add the PostHog provider in the Next.js root.
4. Implement the 6 named events with pre-flattened scalar properties.
5. Wire server-side capture in `browser-search` via PostHog HTTP capture API
   (Deno `fetch`, not `posthog-node`) for `browse_filter_applied` and
   `browse_csv_export`.
6. Implement the `X-Internal-Traffic` analytics-only marker; verify it is
   filtered server-side and explicitly **not** honored by any rate-limit /
   abuse logic.
7. Configure PostHog project retention to 90 days in PostHog UI.
8. Verify in PostHog Live Events that events arrive with expected properties.

No alerts, no thresholds. Collection only.

### Phase 2: Cloudflare migration with verified passthrough

1. Resolve Pre-Implementation §2 (CF tier choice — F1/F2/F3/F4).
2. Drop apex/CNAME TTLs to 60 seconds. Hold for 24 hours.
3. Run the PostgREST passthrough verification suite (Pre-Implementation §3)
   against a CF-proxied test domain.
4. Add CF zones for `collegedata.fyi`, `api.collegedata.fyi`, and (if Option R1)
   `functions.collegedata.fyi`.
5. Flip DNS for all proxied domains.
6. Hold low TTL for 30 days.

No rate limits active, no edge cache rules. CF is in observation-only mode.

### Phase 3: Baseline period

4–6 weeks of collection. No work besides waiting and occasionally checking
PostHog and CF dashboards for "does the data look sane."

Specifically watching for:

- First-party `browser-search` request rate distribution (informs the
  rate-limit rule's ceiling)
- Public-API request rate distribution per IP (informs the rate-limit rule's
  threshold)
- Cloud-ASN traffic share (informs the commercial-tier lead-hypothesis pattern)
- Error rate baseline (informs the anomaly threshold)

### Phase 4: Digest worker + thresholds

1. Confirm Supabase Cron / `pg_cron` availability (Pre-Implementation §6).
2. Write the Edge Function and wire three secrets:
   `CLOUDFLARE_API_TOKEN`, `POSTHOG_PERSONAL_API_KEY`, `RESEND_API_KEY`.
3. Set initial thresholds derived from Phase 3 baseline data.
4. Send the first digest manually to verify formatting before enabling cron.
5. Enable weekly cron.
6. Activate the single CF rate-limit rule (or chosen alternate enforcement
   from Pre-Implementation §2) using thresholds derived from baseline.

### Phase 5: Tune

After the first 4 weekly digests:

- Drop events that produced no useful signal.
- Tighten or loosen the rate-limit threshold based on observed false positives.
- Decide whether the commercial-tier lead stream is real (leads appearing 3+
  weeks running, with eventual outreach replies) or noise.
- If Option F1 proves too coarse, escalate to F3 (Worker-based per-path limits).

## Open questions

1. **Privacy posture:** A, B, or C? Default recommendation: C, with the
   `/privacy` page as a release blocker. Legal review not yet performed.
2. **CF rate-limit enforcement:** F1 (one coarse free rule), F2 (paid tier),
   F3 (Worker-based), or F4 (Supabase-side)? Default: F1 at MVP, F3 if
   F1 is too coarse.
3. **Functions routing:** R1 (subdomain), R2 (path-based), or R3 (leave
   outside CF)? Default: R1.
4. **Email sender:** Resend vs SendGrid vs Loops vs a webhook to a personal
   inbox? Default: Resend.
5. **Public dashboard later?** Some open-source projects publish their
   analytics openly as a trust signal. Revisit at the 6-month mark or at
   PRD 014, whichever first.
6. **Digest cadence:** weekly. Daily is too noisy at this scale; monthly
   delays abuse signal too much. Reconsider only if abuse becomes acute.
7. **Cloud-ASN list maintenance:** the commercial-tier lead pattern checks for
   AWS/GCP/Azure/Hetzner/etc. ASNs. Use a maintained list (PeeringDB, BGP
   data) rather than a hard-coded snapshot, or accept staleness.

## Risks

- **Cloudflare dependency.** A CF outage takes both surfaces dark for the
  duration of DNS propagation. Low TTL during the first 30 days makes recovery
  minute-scale, not hour-scale; revisit TTL after stable.
- **PostgREST header breakage through CF.** Mitigated by Pre-Implementation §3.
  If the verification suite fails late, DNS flip is blocked until fixed.
- **PostHog privacy posture.** Even cookieless, IPs reach PostHog. Mitigated by
  Pre-Implementation §1 (explicit choice) and the `/privacy` page.
- **Rate-limit false positives.** A researcher running a legitimate batch read
  could trip the limit. Mitigation: include a `mailto:` contact in the 429
  response body for whitelisting; thresholds derived from baseline rather than
  guessed.
- **Digest fatigue.** Empty sections omitted, not reported. If the digest
  becomes mostly noise, drop sections aggressively in Phase 5.
- **Self-traffic skew.** Mitigated by `X-Internal-Traffic` header rather than IP
  allowlisting.
- **Threshold drift.** Thresholds live in `analytics_config` / env vars, not
  source. Revisit quarterly.
- **Vendor cost cliff.** PostHog 1M events/month, CF 1 free rate-limit rule
  (verify against current CF docs at implementation time — they have changed
  before), Resend 100 emails/day. At current scale, comfortable runway. At
  10x scale, reconsider the stack rather than upgrade plans reflexively.
- **Spoofable internal-traffic header.** The `X-Internal-Traffic` header is
  client-set and trivially forgeable. Mitigation: it gates analytics
  filtering only — never rate limiting, abuse classification, or auth.

## Acceptance criteria

The PRD is implemented when:

- Privacy posture is decided and (if Option C) the `/privacy` page is published.
- CF tier choice (F1/F2/F3/F4) and Functions routing choice (R1/R2/R3) are
  recorded.
- Env split (`NEXT_PUBLIC_SUPABASE_REST_URL` and
  `NEXT_PUBLIC_SUPABASE_FUNCTIONS_URL`) is in place if R1 is chosen.
- All checks in Pre-Implementation §3 pass against a CF-proxied test domain;
  results recorded in `.context/cf-postgrest-passthrough.md`.
- DNS is flipped for all proxied domains; site, API, and Functions serve
  correctly.
- PostHog captures 6 named events with pre-flattened properties, including
  server-side captures from `browser-search` via the HTTP capture API
  (no `posthog-node` dependency in Edge Functions).
- PostHog project retention is configured to 90 days (verified in PostHog UI).
- The `X-Internal-Traffic` marker is honored for analytics filtering only and
  is explicitly **not** honored by any rate-limit or abuse-classification logic.
- 4–6 weeks of baseline data exist before any rate-limit rule is activated.
- The first weekly digest is sent and reviewed; thresholds are derived from
  baseline data, documented in `analytics_config`.
- A 429 response from CF includes a `mailto:` contact in its body.

## Verification

Backend / API (run against CF-proxied test domain before DNS flip):

```bash
# PostgREST header passthrough
curl -sI \
  -H 'Prefer: count=exact' \
  'https://test.api.collegedata.fyi/cds_manifest?limit=10' \
  | grep -E '^(content-range|content-type):'
curl -s \
  -H 'Range: items=0-9' \
  'https://test.api.collegedata.fyi/cds_manifest' \
  | jq 'length'
curl -s \
  -H 'Accept-Profile: public' \
  'https://test.api.collegedata.fyi/cds_manifest?limit=1' \
  | jq '.[0] | keys'

# Functions routing (Option R1) — verify CF proxies Functions correctly
curl -s -X POST \
  'https://test.functions.collegedata.fyi/browser-search' \
  -H 'Content-Type: application/json' \
  -d '{"filters":[],"mode":"latest","limit":1}' \
  | jq '.rows | length'

# browser-search end-to-end against the new URL
deno test supabase/functions/browser-search/*.test.ts

# CF rate-limit fire test (post-Phase 4) — confirm 429 with mailto: in body
for i in $(seq 1 1500); do
  curl -s -o /dev/null -w '%{http_code}\n' \
    'https://api.collegedata.fyi/cds_manifest?limit=1'
done | sort | uniq -c
```

Frontend:

```bash
cd web
npm exec tsc -- --noEmit
npm run build
# Manual: open /browse, apply a filter, confirm browse_filter_applied appears
# in PostHog Live Events with pre-flattened scalar properties only
# Manual: confirm filter call hits NEXT_PUBLIC_SUPABASE_FUNCTIONS_URL, not the
# raw NEXT_PUBLIC_SUPABASE_URL
```

Digest worker:

```bash
# Manual trigger before enabling cron
supabase functions invoke weekly-analytics-digest --no-verify-jwt
# Verify email arrives with the expected sections
```

## Verdict

Ship in five phases over ~2 engineer-weeks plus a 4–6 week passive baseline.
Effort breakdown:

- Phase 1 (PostHog + privacy decision): 3–4 days
- Phase 2 (CF migration + verification): 2–3 days
- Phase 3 (baseline): no engineering work, calendar wait
- Phase 4 (digest worker + threshold setting): 3–4 days
- Phase 5 (tune): ongoing, ~1 day per quarter

Total ongoing cost $0 at current scale, conditional on PostHog 1M
events/month, CF 10 free rate-limit rules, and Resend 100 emails/day. First
paid tier triggers at any of those caps; estimated runway is 6+ months on
current growth.

The bar is intentionally low: this PRD is a sensor, not a product. Its job is
to make the next product decision (commercial tier? heavier rate limiting?
public analytics dashboard?) data-driven instead of guessed.
