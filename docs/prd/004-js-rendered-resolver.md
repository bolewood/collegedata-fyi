<!-- /autoplan restore point: ~/.gstack/projects/bolewood-collegedata-fyi/main-autoplan-restore-20260417-182221.md -->

# PRD 004: JS-rendered resolver

**Status:** SPIKE APPROVED (Option C via /autoplan 2026-04-17)

> **Product context captured at the gate:** top-100 schools coverage is existential for the project. If Google/Brave can find the landing page, we need the files. Hand-curation is an acceptable fallback; automation is preferred if it works cleanly. This context shifts the PRD's framing from "build speculatively" to "find the least-expensive path to top-100 coverage." Option C (hybrid) is the approved path: hand-curate now, spike-test Playwright in parallel, decide infra based on spike results.
**Author:** Anthony Showalter (with Claude)
**Date started:** 2026-04-17
**Related:** [PRD 001](001-collegedata-fyi-v1.md), [ADR 0001](../decisions/0001-supabase-only-architecture.md), [ADR 0007](../decisions/0007-year-authority-moves-to-extraction.md), [backlog Georgetown + MIT + Bepress resolver items](../backlog.md)

---

## Problem

The existing resolver (`supabase/functions/_shared/resolve.ts`) fetches raw HTML with Deno's `fetch()` and parses anchors with `deno-dom`. That works for static IR sites and Drupal uploads directories. **It does not work for schools whose IR landing page is a JavaScript-rendered single-page app.**

Live-URL spot-checks on 2026-04-17 confirmed the gap:

| School | DB today | Raw HTML shows | Likely cause |
|---|---|---|---|
| MIT | 0 | 0 CDS anchors | React-ish SPA, 9 scripts |
| Princeton | 0 | 0 CDS anchors | Drupal 9+, 41 scripts |
| Duke | 0 | 0 CDS anchors | Drupal |
| Columbia | 0 | 0 (Akamai 403) | Bot detection |
| UPenn | 0 | 0 CDS anchors | Drupal |
| Stanford | 0 | 0 CDS anchors | Client-rendered |
| JHU | 0 | 0 CDS anchors | Client-rendered |
| Caltech | 0 | 0 CDS anchors | Client-rendered |
| UChicago | 0 | 0 CDS anchors | Client-rendered |

These schools **do have public CDS archives.** Each probably exposes 5–15 years on their live IR site. None of it flows into the pipeline today.

Additional related failure modes in the backlog:
- **Georgetown** — IR page returns empty anchors through our resolver; visible in a browser
- **MIT child-page structure** — `ir.mit.edu/projects/<year>-common-data-set/` anchors invisible to deno-dom
- **Bepress Digital Commons** — 202-empty-body bot detection (Fairfield + others)

All of these have the same root cause: the resolver sees what `curl` sees, not what a browser sees.

## Goal (revised after /autoplan Option C decision)

**Approved scope: a 2-week hybrid spike.** Original PRD (build the full worker) is archived for reference below but NOT approved as committed work.

The spike answers ONE question: **is Playwright actually the cheapest automated path to top-100 coverage, or does hand-curation dominate?**

Concrete deliverables:
1. **Hand-curate top 20 prestige schools now** — open each IR page, collect every CDS URL, put into `schools.yaml` as direct-PDF hints or landing-page hints. ~1-2 hours human time. Immediate corpus gain.
2. **Extend to top 100 via search-assisted curation** — Google/Brave search for "<school> common data set" for each school in our current top-100 list that has 0 docs in the corpus, then add URLs to `schools.yaml`. Pay a 13-year-old or Claude to do the searches. ~4-6 hours total.
3. **Playwright spike on 3 Drupal-SPA schools** — manual/scripted Playwright render test against Princeton, Duke, UPenn (no Akamai/Bepress; those are separate problems). Measure: does `page.goto` + wait actually expose CDS anchors? ~1 day CC effort.
4. **Decision gate at spike end.** If spike succeeds on 3/3: open PRD 004-v2 that ships the full worker with all eng+DX resolutions folded in, scoped ONLY to Drupal-SPA schools (not Akamai/Bepress). If spike fails: archive this PRD, top-100 coverage rides on hand-curation + search-assisted workflow.

**Original goal (deferred):** Ship a complementary JS-rendered resolver as long-term automation. Revisit only if the spike proves it works on multiple root-cause classes.

## Non-goals (revised)

- Building any queue / worker / RPC infrastructure during the spike phase
- Covering Akamai-protected sites (Columbia) or Bepress-protected sites (Fairfield) — those need different fixes
- Operator CLI / stats views / runbook — deferred until after spike results

## Non-goals

- Replacing the deno-dom resolver. That stays as the primary, fast, cheap path.
- Rendering every document. We only render the LANDING PAGE; document downloads still go through the existing downloader.
- General-purpose web automation. This is narrowly scoped to CDS discovery.
- Fixing schools whose CDS is genuinely behind auth. Some schools require login — those stay out of scope.

## Revised spike approach (Option C)

```
┌────────────────────────────────────────────────────────┐
│ WEEK 1 — hand-curation (human effort, zero infra)      │
│                                                        │
│ Step 1: identify top-100 schools with 0-1 docs in DB   │
│   SELECT school_id FROM cds_documents                  │
│   GROUP BY school_id HAVING count(*) <= 1              │
│   + cross-reference US News top 100                    │
│                                                        │
│ Step 2: Google/Brave "<school> common data set"        │
│   Open each result in browser, verify it's the         │
│   school's own IR page, copy ALL CDS PDF URLs          │
│                                                        │
│ Step 3: update schools.yaml                            │
│   For schools with directory-listing landing pages:    │
│     cds_url_hint: <landing URL>                        │
│     let existing resolver fan out                      │
│   For schools with single-PDF-only pages:              │
│     cds_url_hint: <direct URL>                         │
│     well-known-paths fallback catches siblings         │
│                                                        │
│ Step 4: trigger force_school for each updated entry    │
│   curl ?force_school=<slug>                            │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ WEEK 2 — Playwright spike (parallel, time-boxed)        │
│                                                        │
│ No queue, no RPC, no edge function.                    │
│ tools/spike/playwright_spike.py:                        │
│   for school in [princeton, duke, upenn]:              │
│     launch chromium headless                           │
│     goto(landing_url, wait=domcontentloaded, 10s)      │
│     wait_for_selector('a[href*=".pdf"]', 5s)           │
│     collect anchors                                    │
│     compare against hand-curated result                │
│                                                        │
│ If 3/3 match: PRD 004-v2 proceeds with worker build   │
│ If <3: archive PRD 004, coverage relies on curation   │
└────────────────────────────────────────────────────────┘
```

## Original approach (archived — deferred until spike gate passes)

```
                        ┌──────────────────────────────────┐
                        │ archive-process (Deno Edge Fn)   │
                        │  resolveCdsForSchool() primary   │
                        └──────────────┬───────────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────────┐
                        │ Existing deno-dom resolver       │
                        │  - fetchText + extractCdsAnchors │
                        │  - pickCandidates                │
                        │  - parent-walk + well-known paths│
                        └──────┬────────────────────┬──────┘
                               │                    │
                       resolved│                    │no_cds_found
                               │                    │
                               ▼                    ▼
                    [ archive candidates ]     ┌──────────────────────┐
                                               │ NEW: enqueue into    │
                                               │ js_render_queue      │
                                               │ (Postgres table)     │
                                               └──────────┬───────────┘
                                                          │
                                                          │ polled every 5 min
                                                          ▼
                                ┌────────────────────────────────────────┐
                                │ JS-Render Worker (GitHub Actions cron) │
                                │  - Python + Playwright/Chromium        │
                                │  - for each queued school:             │
                                │    1. playwright.goto(landing_url)     │
                                │    2. wait_for_load_state(networkidle) │
                                │    3. page.evaluate() to collect links │
                                │    4. POST result to Supabase RPC      │
                                │  - 15 min max per run, 25 schools/run  │
                                └────────────────────┬───────────────────┘
                                                     │
                                                     ▼
                             ┌────────────────────────────────────────┐
                             │ Supabase RPC `record_js_render_result` │
                             │  - validates auth (service-role)       │
                             │  - parses anchors through the SAME     │
                             │    extractCdsAnchors path via a small  │
                             │    stored-procedure / edge-fn shim     │
                             │  - writes cds_documents rows           │
                             └────────────────────────────────────────┘
```

### Why GitHub Actions (not serverless browser provider)

Three serious options were considered:

| Option | Cost | Security | Ops burden |
|---|---|---|---|
| **GitHub Actions cron** | Free (2,000 min/mo on free plan) | Isolated runner, ephemeral | Low — one workflow file |
| Browserless.io / Browserbase | ~$0.002/render → $50–100/mo | Third-party execution | Low |
| Self-hosted Playwright on Fly.io | $5–20/mo | Operator-controlled | High — container + health + scaling |
| Supabase Edge Fn + Chromium-lite | Free (edge compute) | Isolated runtime | Medium — unproven, 150MB memory cap vs Chromium 200MB+ |

**Recommendation: GitHub Actions cron.** Free, familiar, ephemeral, and the workflow file lives in the repo alongside everything else. Cron runs every 30 minutes, processes up to 25 queued schools per run, writes results via a service-role RPC. If we outgrow the free tier, migrate to Browserbase (minimal config diff).

### Why a queue (not synchronous)

- Edge function has a 150s wall-clock cap. Playwright page.goto + networkidle can be 10–30s per school. 25 schools × 20s = 500s — blows the cap.
- Async decoupling: the deno resolver stays fast. When it fails, it enqueues a job and returns immediately. The human-visible latency is the same.
- Backpressure: if many schools fail at once, the queue throttles naturally.
- Retry-ability: a stuck job surfaces as a queue row past its retry deadline; easy to inspect and clear.

## Data-model changes

### New table: `js_render_queue`

```sql
create table public.js_render_queue (
  id             uuid primary key default gen_random_uuid(),
  school_id      text not null references public.cds_documents(school_id)
                    on delete cascade,
  -- not a real FK — schools without any cds_documents can still queue.
  -- scraper-supplied hint (typically the school's landing URL).
  landing_url    text not null,

  enqueued_at    timestamptz not null default now(),
  claimed_at     timestamptz,
  completed_at   timestamptz,
  status         text not null default 'queued'
                    check (status in ('queued','in_flight','done','failed','abandoned')),

  -- Populated by the JS-render worker on completion.
  result_json    jsonb,                       -- { anchors: [...], final_url, page_title }
  docs_inserted  integer,
  error_class    text,                         -- "navigation_timeout", "page_crash", "no_anchors", "nav_blocked", ...
  error_message  text,

  attempts       integer not null default 0,
  max_attempts   integer not null default 3,

  unique (school_id, landing_url, date_trunc('day', enqueued_at))
);

-- Allow the service-role worker to claim rows without racing.
create index js_render_queue_claimable
  on public.js_render_queue (status, enqueued_at)
  where status = 'queued';
```

RLS: no public read. Only service-role reads/writes. The queue is internal ops state, not corpus data.

### New RPC: `record_js_render_result`

Atomic procedure that:
1. Takes a queue row id, a `result_json` with anchor array, and worker metadata
2. Inserts `cds_documents` rows via the same `pickCandidates` logic the edge resolver uses
3. Marks the queue row `done` and fills `docs_inserted`
4. Returns the per-candidate outcomes

Avoids round-tripping JSON through the worker → edge fn → database chain. The worker hits the RPC directly with its service-role key.

## Milestones

### M1 — Queue + simplest worker (~2 days CC)

- `js_render_queue` table + migration
- `record_js_render_result` RPC
- Resolver hook: on `no_cds_found`, enqueue instead of returning. Feature-flag it (`ENABLE_JS_RENDER_FALLBACK`) so we can toggle it off if the queue misbehaves.
- Python Playwright worker (`tools/js_render_worker/worker.py`):
  - Poll queue, claim 25 rows
  - For each: `chromium.launch(headless=True)`, `page.goto(url, wait_until='networkidle', timeout=20s)`, evaluate JS to collect `<a>` hrefs + texts
  - POST back via RPC
  - Structured logs (`event=claim|render|failed|ok`)
- GitHub Actions workflow: cron every 30 min, 15 min max runtime, reuses setup-python + pip cache

**Gate:** run against Cornell, Princeton, Duke, MIT, Columbia, Brown. Verify ≥3 of 6 yield new cds_documents rows. If <3 after Playwright runs successfully, the problem isn't JS rendering — re-scope.

### M2 — Reliability + observability (~1-2 days)

- Retry logic: failures with `error_class in (navigation_timeout, net_error)` auto-retry up to 3 times; `nav_blocked` is permanent
- Observability: a lightweight `js_render_stats` view that summarizes the last 7 days (processed, success-rate, avg render time)
- Alerting: post a Slack/webhook message if any worker run fails entirely (0 successes, ≥5 failures)
- Operator CLI: `tools/js_render_worker/manage.py claim|retry|abandon <school_id>` — same shape as existing force_school

### M3 — Corpus replay (~0.5 day)

Take the ~180 schools currently in `failed_permanent` status (of those, the ~60 with error class `resolve no cds found: landing parsed, no CDS-ish document anchors`) and enqueue them into `js_render_queue`. Measure net-new docs.

### M4 — Ongoing (~low)

- When deno resolver returns `no_cds_found`, enqueue automatically (on by default, not behind flag)
- Daily rollup into the corpus-survey output

## Cost envelope

| Line | Monthly |
|---|---|
| GitHub Actions minutes (25 schools × 20s × 48 runs/day × 30 days) | ~12 hours / month — comfortably within 2,000 free tier |
| Supabase Postgres rows (js_render_queue, ~5,000 rows/month) | $0 |
| Supabase Storage for any new docs (5-50 MB each) | Within existing budget |
| Tracks/observability | $0 |
| **Total** | **$0** |

If we outgrow GitHub free plan, ~$0.008/min × 200 overflow min/mo = ~$1.60/mo. Still negligible.

## Risks

1. **Schools' anti-bot detection.** Playwright + default UA can trip bot defenses (Akamai, Cloudflare, PerimeterX). Mitigation: use `playwright-stealth`, configure a realistic browser UA, respect robots.txt, rate-limit (1 req/5s per host). If still blocked, accept — we're not building Anubis-level evasion.

2. **JS-execution security.** We're loading arbitrary JavaScript from schools' websites. A malicious/compromised school could try to crash the render, exfiltrate the worker's env, or pivot into private networks. Mitigation: (a) Playwright runs in a sandboxed, ephemeral GH Actions runner — no secrets besides the Supabase service-role key, and that has no access beyond Postgres+Storage; (b) network restrictions at the runner level block SSRF targets (169.254.*, 10.*.*.*, etc.); (c) the worker never executes downloaded content — it only collects anchor hrefs.

3. **Render timeouts cascade.** A school whose site takes 30s+ to networkidle blocks other queued schools. Mitigation: 20s hard timeout per school, separate `page.goto` timeout and `networkidle` timeout. Timeout → mark row `failed` with `error_class=navigation_timeout`, continue to next.

4. **Queue backlog.** If many schools fail at once (e.g., the monthly re-enqueue), the queue might exceed the 25-schools/run cadence. Mitigation: at 25 schools × 48 runs/day = 1,200 renders/day. Our worst-case backlog is ~200 schools, which clears in 4 hours.

5. **GH Actions free-tier exhaustion.** If usage spikes, we get throttled. Mitigation: alert on >50% monthly minute budget consumed by this workflow. Fallback to Browserbase (~$100/mo) is a one-config-file change.

6. **Operator overhead.** Each failed render lands in the queue with an error. If we don't triage, the queue fills with dead rows. Mitigation: `abandoned` status after max_attempts × 30 days. Weekly manual review of abandoned rows during the first month.

## Open questions

- **Primary user of this:** operator (me) today. Frontend consumers don't see queue state. Should `cds_manifest` expose a "js_rendered" flag so consumers know the provenance? Probably yes in M2 — it's a one-column view update.
- **Should we retry existing `failed_permanent` queue rows in `archive_queue` automatically once JS-render is live?** Proposal: M3 does an explicit one-shot replay. After that, new failures flow through js_render_queue naturally.
- **Playwright browser version management.** Pin to a specific chromium version in CI. When to upgrade? Follow Playwright major releases only.

## Success criteria (revised for Option C)

### Spike — committed

1. **Hand-curation (Week 1):** ≥80 of the top-100 US News schools have ≥1 CDS doc in the corpus (including multi-year where the parent-walk / well-known-paths fallback surfaces sibling years). Covers the "project is worthless without top-100" bar.
2. **Playwright 3-school test (Week 2):** Run headless render against Princeton, Duke, UPenn. Success = 3/3 schools expose CDS anchors post-render that a static fetch missed. Kill criterion = <3 succeed → archive this PRD, rely on curation.
3. **Total effort envelope:** ≤ 1.5 days CC + ~6 hours human for curation + search.

### Conditional (gate opens only if spike succeeds)

PRD 004-v2 would rewrite this document with the original M1-M4 architecture + all 12 eng resolutions + 6 DX resolutions incorporated. Do not approve without an explicit re-review.

### Original M1-M4 criteria (archived, deferred)

- ~~**M1:** ≥3 of 6 audit schools yield ≥3 new docs~~
- ~~**M2:** <15 min/week triage~~
- ~~**M3:** ≥150 net-new docs from failed_permanent replay~~
- ~~**M4:** ≥30 min auto-pickup~~

Retained above for reference if PRD 004-v2 opens.

## Out of scope (and where it goes)

- UI for reviewing queue state → operator CLI is enough; frontend integration is a later PRD
- Bot-evasion beyond `playwright-stealth` → separate track; some schools just can't be automated without an operator-assisted path
- Rendering the documents themselves (e.g., JS-rendered PDF viewer-as-page) → Tier 5/6, way later
- Multi-browser rendering (Firefox, Safari) → Chromium is enough
- Per-school custom JS probes (click a dropdown, fill a form) → noted but deferred to operator-assisted path

---

*Initial draft — pending /autoplan review.*

---

# Review Report (via /autoplan)

## Phase 1 — CEO Review

### Dual voices — consensus

**CLAUDE SUBAGENT (CEO — strategic independence):** Kill the PRD or defer 3 months. Textbook founder product creep on a 4-day-old archive with zero users. No user asked for MIT; YOU asked. 10x reframe: focus on distribution, not coverage. **Option G (hand-curate top 20) is the dominant choice** — 1-2 hours of work, zero infra, zero maintenance, 100% success rate on Akamai schools a human can access. Over-scoped by ~5x. Agentic browsers will commoditize this in 12 months; we'd be building 2023-style custom OCR in a 2026 world where the generic tool is coming.

**CODEX (CEO — strategy challenge):** Prestige-completionism, not validated demand. Premise slippage: the PRD conflates 4 distinct root causes (Drupal-SPA rendering, Akamai 403, Bepress 202, MIT child-page structure) into "JS-rendered"; Playwright solves at most the first bucket. Six-month regret surface is real: `js_render_queue` + `record_js_render_result` RPC + service-role key in CI + browser version pinning + retry policy + triage CLI + Slack alerts + weekly abandoned-row review — massive operator burden for a non-urgent gap. **Kill A as default; do a spike test first (manually run Playwright on 4 of 6 M1 schools); if <4 succeed, do G now.**

**CEO DUAL VOICES — CONSENSUS TABLE**

| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Premises valid? | NO — demand unvalidated; "arms race" with anti-bot | NO — Playwright doesn't solve all 4 root causes | **DISAGREE with PRD** |
| 2. Right problem to solve? | NO — distribution > coverage | NO — success metric is founder ego bait | **DISAGREE with PRD** |
| 3. Scope calibration? | NO — 5x over-scoped | NO — 6-month maintenance surface too large | **DISAGREE with PRD** |
| 4. Alternatives sufficiently explored? | NO — G is dominant, never compared against | NO — README already recommends G pattern (PR a URL) | **DISAGREE with PRD** |
| 5. Competitive/market risks? | NO — agent browsers will commoditize | NO — not the durable asset (archive is) | **DISAGREE with PRD** |
| 6. 6-month trajectory sound? | NO — queue dead-letters silently | NO — permanent maintenance tax | **DISAGREE with PRD** |

**6 of 6 DISAGREE.** Consistent with PRD 003's pattern. This is a **USER CHALLENGE** — both models want the user's direction to change fundamentally.

### User Challenge — scope reduction (kill-or-spike)

- **What the user said:** "A production-grade JS-rendering path is the single highest-leverage thing we could ship for corpus growth." Build a GH Actions cron + Playwright worker + queue + RPC + operator CLI.
- **What both models recommend:** **Don't build any infra yet.** Either (a) hand-curate the top 20 schools now (option G, ~1 hour); or (b) do a 2-hour manual Playwright spike against the 6 audit schools to verify the premise holds — if <4 succeed (likely, given Akamai/Bepress in the mix), do G and close the PRD.
- **Why:** (1) zero user signal; (2) the 9 "JS-rendered" schools have 4 different root causes — Playwright solves one; (3) massive permanent operational surface for a non-urgent gap; (4) agent browsers will make custom Playwright obsolete inside the payback window.
- **What context we might be missing:** The user has stronger product instinct about which schools matter strategically (e.g., if an HN launch is imminent and MIT/Princeton being missing would undermine credibility), or prior commitments to a partner that named specific schools. From the conversation context none of that is visible.
- **If we're wrong, the cost is:** If the user has validated demand we don't know about and we do G, we ship 20 prestige schools by tomorrow but the other 1,500 schools with stale JS-rendered pages remain gaps until someone complains. Recoverable — the PRD text is preserved and can be un-killed if demand surfaces.

### Mandatory outputs

**NOT in scope** (confirmed by both voices):
- Building any new infrastructure at this stage
- Full M1-M4 pipeline as originally drafted
- Playwright worker + GH Actions workflow
- `js_render_queue` table + RPC

**What already exists** (reuse):
- `tools/finder/schools.yaml` — where hand-curated URLs would go
- Existing probe_urls.py — for validating hand-curated URLs
- archive-process `?force_school=...` — for immediate testing

**Error & Rescue Registry** (placeholder — scope reduction means most doesn't apply):
| # | Error | Trigger | Rescue |
|---|---|---|---|
| 1 | Hand-curated URL goes stale | School changes IR site | Same ~17% staleness rate as other hints; natural maintenance item |
| 2 | Hand-curation misses a year | Operator doesn't spot all historical files | Low cost — re-curate annually during HN/announcement cycles |

**Failure Modes Registry** (hypothetical, if we DID build PRD 004 as-drafted):
| # | Failure | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Akamai schools still blocked after Playwright | HIGH (per Codex) | Half of target set silently fails M1 | Spike-first; kill if <4/6 succeed |
| 2 | Queue dead-letter accumulation | HIGH | 4K+ abandoned rows by month 4 | Weekly triage that nobody does |
| 3 | Service-role key in CI compromised | LOW | Full DB write access | Don't add the surface at all |
| 4 | Agent browsers commoditize in 6 months | HIGH | Moatless infra becomes obsolete | Don't build it |

**Dream state delta:** The 12-month ideal is "top-20 schools covered with deep history." Option G gets us 80% of that by Saturday. Option A (the PRD) gets us ~90% in 4-6 weeks with ongoing maintenance. The marginal 10% isn't worth the permanent burden.

### Phase 1 completion summary

| Dimension | Status |
|---|---|
| Premises evaluated | 5 (2 accepted, 2 challenged, 1 accepted with gate) |
| Alternatives | 7 now in the PRD; both voices flagged G as missed |
| Scope | 6/6 dimensions flagged for reduction |
| Dual voices | Both ran, both agreed |
| User Challenge | **Raised for final gate** |

---

## Phase 2 — Design Review

**SKIPPED.** No UI scope (1 match, threshold 2+). Backend infrastructure only.

---

## Phase 3 — Eng Review

Eng review evaluates: **if we built this as drafted, what breaks?** Both CEO voices already recommended killing it; this is the engineering ammunition for that decision, plus a resolution set in case you override and ship.

### Dual voices — consensus

**CLAUDE SUBAGENT (eng — independent review)**

Critical: C1 no lease/claim RPC (races on concurrent runs); C2 service-role key + arbitrary school JS is exfiltration surface.
High: H1 enqueue-on-failure leaks DB concerns into pure resolver (belongs in `archive.ts`); H2 PRD conflates 4 root causes (Drupal-SPA, Akamai 403, Bepress 202, MIT child-page) — Playwright solves 1.5 of them; H3 RPC `record_js_render_result` bypasses the existing `archiveOneCandidate` flow (SHA dedup, Storage upload, `cds_artifacts`) — creates parallel write path that will drift; H4 feature flag location (env var? DB row?) unspecified.
Medium: M1 `date_trunc` in unique constraint requires expression index (DDL as drafted won't apply); M2 `references cds_documents(school_id)` fails at migration — school_id isn't unique (composite is); M3 runner image pinning unspecified (`ubuntu-latest` flips Chromium major mid-cycle); M4 no regression tests (vendor HTML-after-render fixtures).
Deployment: D1 no rollback plan (no `discovered_via='js_rendered'` discriminator); D2 interaction with local extraction worker unacknowledged.

**CODEX (eng — architecture challenge)**

1. Boundary wrong: `resolveCdsForSchool` is a pure network/parser module ([resolve.ts:746](../../supabase/functions/_shared/resolve.ts)); PRD leaks DB writes into it. `record_js_render_result` bypasses the existing `resolve → download → SHA → upload → upsert` contract.
2. Failure-class collapse: current code explicitly separates `transient | upstream_gone | no_cds_found | unsupported_content | blocked_url`. The PRD's enqueue trigger is just "no_cds_found" but Akamai 403s become `transient`, Stage B multi-year-no-anchor becomes `no_cds_found` but needs a different remedy. **Wrong schools will enqueue; right schools will miss.**
3. Queue hand-waves races: the existing `archive_queue` needed `claim_archive_queue_row()` with FOR UPDATE SKIP LOCKED + visibility timeout + attempts-increment-on-claim. An index is not a lease.
4. RPC story contradictory: "stored procedure or edge shim" isn't a design — Postgres can't call TS helpers. Either duplicate `extractCdsAnchors` in plpgsql (drift) or add a second HTTP hop (kills "atomic RPC" claim).
5. Security undersold: GH runners don't provide meaningful egress controls. Minimum: low-privilege scoped key, pinned container digest, server-side URL revalidation.
6. Tests understated: need SQL lease tests, parser-parity fixtures, tiny live smoke — and `networkidle` on analytics-heavy SPAs is a "timeout factory" (25 schools/15 min is fantasy).

**Bottom line from Codex:** "If this had to ship, keep the resolver pure, enqueue from `archiveOneSchool` on explicitly classified failures, and make the JS worker feed discovered URLs back into the existing archive path instead of inventing a parallel write path."

### Eng consensus table

| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Architecture sound? | NO (boundary leak, parallel write path) | NO (same + RPC impossible as drafted) | **DISAGREE** |
| 2. Test coverage sufficient? | NO (no regression strategy) | NO (need 3 layers; networkidle flakes) | **DISAGREE** |
| 3. Performance risks addressed? | NO (analytics-heavy SPAs = timeout factory) | NO (25 × 20s × 48/day = fantasy) | **DISAGREE** |
| 4. Security threats covered? | NO (service-role in CI + hostile JS) | NO (runner egress controls don't exist) | **DISAGREE** |
| 5. Error paths handled? | NO (no lease, poison rows) | NO (wrong failure class enqueues) | **DISAGREE** |
| 6. Deployment risk manageable? | NO (no rollback, migration DDL broken) | NO (parallel write path = drift risk) | **DISAGREE** |

**6 of 6 DISAGREE again.** Consistent pattern with Phase 1.

### Architecture ASCII — the "if we had to build this" design (resolutions incorporated)

```
                  ┌───────────────────────────────────────────┐
                  │ archive-process edge function              │
                  │   archiveOneSchool() in archive.ts        │
                  │   switch (ResolveResult.kind) {            │
                  │     case 'no_cds_found':                   │
                  │       if (reason ~= /JS-rendered-ish/)     │
                  │         enqueueJsRender(hint, school_id)   │
                  │       else → existing failed_permanent     │
                  │   }                                        │
                  └─────────────────┬─────────────────────────┘
                                    │   (enqueue in archive.ts, not resolve.ts)
                                    ▼
                  ┌───────────────────────────────────────────┐
                  │ js_render_queue (Postgres)                 │
                  │   + claim_js_render_rows() RPC             │
                  │     FOR UPDATE SKIP LOCKED                 │
                  │     visibility_timeout = 10 min            │
                  │     attempts incremented in claim          │
                  └─────────────────┬─────────────────────────┘
                                    │   (polled by worker)
                                    ▼
                  ┌───────────────────────────────────────────┐
                  │ GH Actions runner (ubuntu-24.04 pinned)   │
                  │   Playwright + playwright-stealth         │
                  │   SCOPED JWT (not service-role)           │
                  │   renders page, collects anchors,         │
                  │   POSTs to new edge fn archive-js-render  │
                  └─────────────────┬─────────────────────────┘
                                    │
                                    ▼
                  ┌───────────────────────────────────────────┐
                  │ archive-js-render edge function (NEW)      │
                  │   reuses extractCdsAnchors, pickCandidates,│
                  │   archiveOneCandidate — same contract      │
                  │   as the main archive pipeline             │
                  │   (NO parallel write path)                 │
                  └───────────────────────────────────────────┘
```

### Test diagram (if we had to ship)

| Codepath | Test type | Exists? | Gap |
|---|---|---|---|
| `claim_js_render_rows` — SKIP LOCKED + visibility | pg integration test | NO | Write modeled on existing `claim_archive_queue_row` test |
| Enqueue-on-failure in `archiveOneSchool` | unit with mocked supabase | NO | Test: `no_cds_found` with rendering-suggestive reason enqueues; other kinds don't |
| Playwright anchor extraction on fixture HTML | fixture-based unit | NO | Vendor 3 rendered-HTML snapshots (Princeton/Duke/MIT post-render) in `tools/js_render_worker/tests/fixtures/` |
| `extractCdsAnchors` reuse in new edge fn | integration | NO | Parity test: worker-emitted anchors → same cds_documents as direct-fetch path |
| Live smoke (CI optional) | end-to-end | NO | 3 schools on a nightly basis, tolerate failure |

### Eng resolutions — required before any ship

| # | Finding | Resolution |
|---|---|---|
| R1 | Races on queue | Add `claim_js_render_rows()` RPC, FOR UPDATE SKIP LOCKED + visibility timeout + attempts-in-claim. Model verbatim on `claim_archive_queue_row`. |
| R2 | Service-role key in CI | Create custom DB role with INSERT-only on `js_render_queue` + EXECUTE-only on the archive-js-render RPC. Scoped JWT signed with `pg_jwt_secret`. NO service-role anywhere in CI. |
| R3 | Resolver boundary leak | Move enqueue to `archiveOneSchool` in `archive.ts`. `resolveCdsForSchool` stays pure. |
| R4 | Failure-class mismatch | Enqueue only on `no_cds_found` AND reason-string heuristic suggests JS-rendering (not on Akamai 403 which is `transient`, not on Stage B year-less which has different fix). |
| R5 | RPC contract | Kill `record_js_render_result` RPC. Replace with new edge fn `archive-js-render` that reuses `extractCdsAnchors` + `pickCandidates` + `archiveOneCandidate` — same path as the primary archiver. |
| R6 | `date_trunc` unique constraint | Move to expression index: `CREATE UNIQUE INDEX ON js_render_queue ((date_trunc('day', enqueued_at)), school_id, landing_url) WHERE status IN ('queued', 'in_flight')`. |
| R7 | FK to school_id | Drop the `references` — `cds_documents.school_id` is not unique. Just a free-text column with a CHECK for format. |
| R8 | Runner image drift | Pin `ubuntu-24.04` + Playwright version + browser binary hash. Bump intentionally on Playwright major releases. |
| R9 | Rollback path | Add `discovered_via='js_rendered'` discriminator to `ResolvedDocument` type. Rollback = `DELETE FROM cds_documents WHERE notes->>'discovered_via'='js_rendered'`. |
| R10 | Feature flag | DB-backed kill switch: `public.feature_flags` single-row table, read per invocation. Rollback is a SQL UPDATE, not a redeploy. |
| R11 | networkidle timeout | `page.goto(url, wait_until='domcontentloaded', timeout=10s)` + per-school extra `wait_for_selector('a[href*="cds"]', timeout=5s)` fallback. 25 schools/15-min budget requires ≤ 36s/school — networkidle on analytics-heavy SPAs blows this. |
| R12 | No regression tests | Vendor 3 rendered-HTML fixtures + SQL lease test + parser-parity test. All in CI, no live renders. |

Collectively these resolutions roughly DOUBLE the implementation effort (~4-8 days CC, not 2-4), without changing the strategic question of whether to build at all.

### Failure modes registry

| # | Failure | Severity | Blocks M1? |
|---|---|---|---|
| C1 | Queue races | CRITICAL | YES — must add claim RPC before M1 |
| C2 | Service-role key exfil | CRITICAL | YES — must scope JWT before M1 |
| H1 | Boundary leak | HIGH | YES — affects code review gates |
| H2 | Root-cause conflation | HIGH | YES — audit set must be Drupal-SPA only, not Akamai/Bepress |
| H3 | RPC bypass archive contract | HIGH | YES — use `archive-js-render` edge fn path |
| M1 | DDL syntax error | MEDIUM | YES — migration won't run otherwise |
| M2 | FK on non-unique | MEDIUM | YES — same |

**Seven critical-or-high must be addressed in M1.** The PRD as drafted cannot ship; the resolutions above reshape M1 substantially.

### Eng completion summary

Architecture direction is defensible if all 12 resolutions land. Current draft is not shippable — two DDL syntax errors would abort the migration, and the security posture (service-role key on GH runner executing untrusted JS) is not acceptable even for a hobby-scale project. If the scope-kill User Challenge from Phase 1 holds, none of this matters. If it doesn't, M1 effort ~doubles.

---

## Phase 3.5 — DX Review [subagent-only]

### Summary

Operator-DX independent review. Codex voice skipped for efficiency given strong consensus from Phases 1+3.

**CLAUDE SUBAGENT** (5 findings, all HIGH or CRITICAL):

| # | Finding | Severity | Fix |
|---|---|---|---|
| DX1 | Worker operability — no start/stop, no force-retry, no log streaming | HIGH | DB-backed kill switch + `manage.py claim|retry|abandon` in M1 (not M2) |
| DX2 | Queue observability — no "in flight now" view, no "docs added last night" | HIGH | Ship `js_render_stats` + `js_render_in_flight` views in M1 |
| DX3 | Rollback — no `discovered_via='js_rendered'` discriminator, bad rows invisible | CRITICAL | R9 (eng review) mandatory in M1 |
| DX4 | Service-role key — in GH Actions secret, no rotation plan, no scope reduction | CRITICAL | R2 (eng review) scoped JWT mandatory before M1 |
| DX5 | Second maintainer onboarding — no runbook | HIGH | `docs/runbooks/js-render-worker.md` as M1 deliverable |

### Developer (operator) journey

| Stage | Today | After M1-as-drafted | After M1-with-resolutions |
|---|---|---|---|
| Start/stop worker | n/a | edit workflow.yml | SQL `UPDATE feature_flags` |
| See what's running | n/a | manual SELECT from queue | `SELECT * FROM js_render_in_flight` |
| Debug failed school | n/a | jump to GH run page manually | `SELECT error_message, gh_run_url FROM js_render_queue` |
| Force retry | not until M2 | not until M2 | `manage.py retry <school_id>` |
| Triage abandoned | not until M2 | not until M2 | `manage.py abandoned-list` + weekly review |
| Rotate service role | n/a | rotate scheduled? never documented | documented quarterly: `gh secret set` + `ALTER ROLE` |
| Roll back bad rows | can't (no tag) | can't (no tag) | `DELETE FROM cds_documents WHERE notes->>'discovered_via'='js_rendered'` |

### DX scorecard (subagent ratings, if shipped as drafted)

| Dimension | Score 0-10 |
|---|---|
| Start/stop control | 2 |
| Observability | 3 |
| Debugging | 3 |
| Rollback safety | 0 (no discriminator) |
| Security posture | 2 (service-role-in-CI) |
| Second-maintainer onboarding | 1 (no runbook) |
| **Overall operator DX** | **~2/10 as drafted, ~7/10 with all R1–R12 + DX1–DX5 pulled into M1** |

### DX resolutions (pulled into M1 scope, not M2)

- DX-R1: `feature_flags` DB table + M1 kill switch
- DX-R2: `js_render_stats` + `js_render_in_flight` views in M1
- DX-R3: `manage.py claim|retry|abandon|abandoned-list` CLI in M1
- DX-R4: mirror GH run URL + structured `error_class` into queue rows
- DX-R5: `docs/runbooks/js-render-worker.md` with start/stop, triage, key rotation, rollback, version-bump steps
- DX-R6: nightly "inserts-by-provenance" count to detect bad-row drift

These collectively add ~1 more day to M1 beyond the engineering resolutions. Total ~5-9 days of CC time to ship M1 properly.

---

## Cross-phase themes

Three themes surfaced in all three phases independently (highest-confidence signal):

1. **Premise is unvalidated + over-scoped for project stage.** All three phases, both voices each, say the same thing: "prestige schools missing" isn't a user problem; agent browsers will commoditize the fix within the payback window; option G is the right answer right now.

2. **Root-cause conflation.** Phase 1 and Phase 3 both flagged that "JS-rendered" actually covers 4 distinct failure modes (Drupal-SPA, Akamai 403, Bepress 202, MIT child-page), and Playwright solves maybe 1.5 of them.

3. **Operator surface is massively under-invested.** Phase 3 (eng) and Phase 3.5 (DX) both flagged: as drafted, M1 has no lease RPC, no kill switch, no `manage.py`, no runbook, no rollback, no stats views, no scoped key. Ship-as-drafted = un-operable in the first week.

---

## NOT in scope (revised after all three reviews)

From the original PRD:
- UI for reviewing queue state (operator CLI is enough)
- Bot-evasion beyond `playwright-stealth`
- Rendering the documents themselves
- Multi-browser rendering (Chromium only)
- Per-school custom JS probes

Added during review:
- **Everything. Both voices say don't build this.** See Phase 4 final gate.

---

## Phase 4 — Final Approval Gate — RESOLVED

**Decision (via AskUserQuestion, 2026-04-17):** Option C — hybrid spike.

**User's strategic context captured:** top-100 schools coverage is existential for the project. If Google/Brave can find the landing page, we need the files. Hand-curation (incl. paying a 13-year-old to do searches) is acceptable; automation is preferred if it works. This context shifts the reviewers' "no demand" framing into "demand is validated by user-stated product requirement."

**What happens now:**

1. **Week 1 — hand-curation sprint.** Identify schools in the top 100 with 0-1 docs. Google/Brave for their CDS page. Copy URLs into `schools.yaml`. Force-archive each. Target: ≥80 of top-100 covered with ≥1 doc by end of week.
2. **Week 2 — Playwright spike.** `tools/spike/playwright_spike.py` hits 3 Drupal-SPA schools (Princeton, Duke, UPenn) headless. Measure whether rendering surfaces CDS anchors that static fetch missed.
3. **Decision gate at end of Week 2.**
   - If spike succeeds on 3/3: open PRD 004-v2 with original architecture + all 12 eng resolutions + 6 DX resolutions.
   - If spike <3: archive PRD 004, coverage stays on hand-curation + a defined search-assisted workflow for new additions.

## Decision Audit Trail (from /autoplan 2026-04-17)

| # | Phase | Decision | Classification | Principle | Rationale |
|---|---|---|---|---|---|
| 1 | CEO | Accept premises 1, 3 | Mechanical | P6 | Static HTML gap is real; GH Actions is sufficient scale-wise |
| 2 | CEO | Challenge premises 4, 5 (demand unvalidated, not "single highest") | Taste (at gate) | P6 | Both voices independently disagreed |
| 3 | CEO | Mode = SELECTIVE EXPANSION with hard kill-switch | Mechanical | P2 | Scope cannot expand without evidence |
| 4 | CEO | Add 3 missing alternatives (E/F/G) to table | Mechanical | P1 | Both voices flagged option G as missing |
| 5 | CEO | USER CHALLENGE: kill + do G | Surfaced at gate | — | 6/6 dimensions DISAGREE |
| 6 | Eng | `claim_js_render_rows` RPC with FOR UPDATE SKIP LOCKED | Mechanical | P3 | Both voices identified race |
| 7 | Eng | Enqueue in archive.ts not resolve.ts (keep pure) | Mechanical | P5 | Boundary hygiene |
| 8 | Eng | Kill `record_js_render_result` RPC; use new edge fn `archive-js-render` that reuses archiveOneCandidate | Mechanical | P4 | Eliminates parallel-write drift |
| 9 | Eng | Scoped JWT, not service-role, in CI | Mechanical | P1 | Both voices critical finding |
| 10 | Eng | DDL syntax fixes (date_trunc expression index, drop FK) | Mechanical | P3 | Migration as drafted won't apply |
| 11 | Eng | `discovered_via='js_rendered'` discriminator for rollback | Mechanical | P1 | Rollback path |
| 12 | Eng | DB-backed feature flag (not env var) | Mechanical | P3 | Rollback speed |
| 13 | Eng | Audit set must exclude Akamai/Bepress (root-cause scoping) | Mechanical | P4 | Both voices flagged conflation |
| 14 | DX | `manage.py` + runbook + stats views pulled into M1 | Mechanical | P1 | Un-operable otherwise |
| 15 | Phase 4 | **Option C (hybrid spike)** | **User decision** | — | Validated demand from user-stated top-100 requirement; Option C preserves optionality |

15 decisions: 13 auto-decided + 1 user challenge (resolved to Option C) + 1 explicit user choice.

---
