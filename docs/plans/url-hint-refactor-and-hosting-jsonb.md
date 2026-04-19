<!-- /autoplan restore point: /Users/santhonys/.gstack/projects/bolewood-collegedata-fyi/main-autoplan-restore-20260418-214517.md -->
# Plan: URL hint refactor + hosting environment JSONB sidecar

**Status:** Draft (in /autoplan review)
**Date:** 2026-04-18
**Owner:** Anthony Showalter
**Related:** ADR 0007 (year authority), `docs/schools_hint_rewrite_proposal.md`, backlog item "Retire cds_year as discovery output"

## Why we are here

The `cds_url_hint` field in `tools/finder/schools.yaml` is doing two semantically different jobs at once:

1. **Landing page** (e.g., `https://oir.brown.edu/institutional-data/common-data-set`) — a durable page the IR team owns for years. The resolver parses anchors, finds multiple year-tagged PDFs, archives them all.
2. **Direct file URL** (e.g., `https://www.alasu.edu/_qa/CDS_2017-2018_1.pdf`) — points at exactly one document for one year. The resolver verifies the file, optionally walks up to the parent directory, and gives up if no siblings exist.

Mixing these in one field has three concrete costs:

- **Dirty data the kids' worklist tool can't navigate.** When a hint is a direct PDF, sending kids to that URL only shows them one stale year. They can't browse to find the missing years. (See `tools/data_quality/kids_worklist.py`.)
- **Wasted resolver work.** Empirical: a force-resolve batch run on 460 active-but-missing schools shows **52% return `unchanged_verified`** — the resolver re-fetched a single direct-PDF hint, checked the sha256, found nothing new. Each call takes ~3-30 seconds and writes nothing.
- **Lost institutional knowledge.** We've learned hosting facts the hard way — Adelphi's intranet is behind Microsoft SSO, RPI hosts on Box, Indiana uses an opaque app server, dmi.illinois.edu is invisible to Brave's index. These facts live in commit messages and the finder README's narrative section, not in structured data. Every cron rediscovers them.

This plan addresses all three with a coordinated schema split + new hosting metadata layer.

## Empirical foundation (force-resolve batch, 460 schools)

A `force_school` operator backfill against every active school missing CDS data for 2022-23 through 2025-26 (448 schools after sub-institutional exclusions) produced:

| Outcome | Count | % | What it means |
|---|---:|---:|---|
| `unchanged_verified` | 231 | 52% | Resolver re-validated the single direct-PDF hint; no new docs |
| `permanent_other` | 56 | 12% | Landing page parsed, no CDS-ish docs found OR docs found but resolver couldn't assign year (Stage B limitation) |
| `dead_url` | 54 | 12% | Hint URL returns 404/410 — school moved/removed the file |
| `transient` | 34 | 8% | Timeout / 5xx — retry on next cron |
| `no_pdfs_found` | 33 | 7% | Landing page exists but resolver finds zero CDS-ish anchors (JS-rendered, behind iframe, etc.) |
| `outcome:marked_removed` | 20 | 4% | Dead URL flipped to `removed` status |
| `wrong_content_type` | 9 | 2% | File isn't PDF/XLSX/DOCX |
| `outcome:unchanged_repaired` | 3 | 1% | Existed but resolver repaired (e.g., URL canonicalisation) |
| `auth_walled_microsoft` | 2 | <1% | Files behind Microsoft 365 SSO (Adelphi) |
| `outcome:refreshed` | 2 | <1% | Re-fetched and updated |
| `auth_walled_google` | 1 | <1% | Google SSO redirect |
| `class:None` (uncategorised) | 3 | 1% | Edge cases — needs categoriser update |

Two implications drive this plan:
1. The 51% `unchanged_verified` bucket is almost entirely direct-PDF hints with no walkable parent directory. These schools need landing-page promotion or to be marked as "direct-only" so the resolver stops re-checking them every cron.
2. The 14% `permanent_other` bucket reveals JS-rendered / year-less landing pages — the same issue ADR 0007 deferred to "Bucket B." This plan records the hosting characteristics so we can route those schools to Playwright instead of the static resolver.

## What changes

### Change 1: split `cds_url_hint` into purpose-specific fields

In `tools/finder/schools.yaml`, replace the polymorphic `cds_url_hint` with two fields:

```yaml
- id: brown
  name: Brown University
  domain: brown.edu
  scrape_policy: active
  landing_page_url: https://oir.brown.edu/institutional-data/common-data-set
  direct_archive_urls: []     # optional fallback list, year-tagged when known
  hosting:                    # NEW — see Change 2
    cms: drupal
    file_storage: same_origin
    auth: none
    rendering: static_html
    waf: none
    last_observed: 2026-04-18
    observation_source: resolver
    notes: ""
```

For schools where we currently have a direct-PDF hint:
- **High-confidence landing-page promotion (67 schools):** `tools/finder/promote_landing_hints.py` already proposed these. Apply them, populate `landing_page_url`, drop the direct URL.
- **No proposable landing page (467 schools):** populate `direct_archive_urls` with the single known PDF, leave `landing_page_url` empty, set `hosting.observation_source = unconfirmed_landing` so they surface as a discovery target.
- **Active hint that's already a landing page (~373 schools):** populate `landing_page_url` directly.

The resolver's behaviour:
- When `landing_page_url` is set: use the existing Case C HTML-landing-page path (`extractCdsAnchors` → `pickCandidates` → multi-doc fanout). This is the only path the resolver should use going forward.
- When only `direct_archive_urls` is set: enqueue each URL as a `force_urls`-style direct archive (one row per year). No parent-walk, no well-known-paths fallback, no year-parsing — the URL is treated as authoritative provenance and the extraction worker assigns the canonical year from page content (per ADR 0007).
- Both: treat `landing_page_url` as authoritative; `direct_archive_urls` is supplementary historical coverage.

### Change 2: `hosting` JSONB sidecar

Captures durable facts about how the school publishes its CDS. Lives in two places:

**In `schools.yaml`** — the human-readable, version-controlled canonical record. Lets contributors see "this school is on Box" without consulting the DB.

**In a new `school_hosting` Postgres table** — for resolver writes and queryable filters:

```sql
create table public.school_hosting (
  school_id              text primary key,
  landing_page_url       text,                       -- mirrors schools.yaml
  cms                    text,                       -- drupal | wordpress | sharepoint | static | custom | unknown
  file_storage           text,                       -- same_origin | box | google_drive | sharepoint | dropbox | intranet
  auth_required          text,                       -- none | microsoft_sso | okta | google_sso | basic
  rendering              text,                       -- static_html | js_required | unknown
  waf                    text,                       -- none | cloudflare | akamai | imperva | unknown
  last_observed          timestamptz not null default now(),
  observation_source     text not null,              -- resolver | playwright | manual
  last_outcome           text,                       -- last force_school category (unchanged_verified, dead_url, etc.)
  last_outcome_at        timestamptz,
  notes                  text,
  raw                    jsonb not null default '{}'::jsonb
);
```

The resolver writes this row as a side effect of every `archiveOneSchool()` call. The schema is intentionally a `text` column per dimension (not free JSON) so we can index and aggregate on it.

### Change 3: resolver writes hosting JSONB on every probe

`resolveCdsForSchool()` in `supabase/functions/_shared/resolve.ts` already gathers most of these facts implicitly during its probe. Wire them through:

- **`auth_required`:** detect Microsoft SAML / Okta / Google SSO redirects in the `fetchText()` final URL host (`login.microsoftonline.com`, `okta.com`, `accounts.google.com`).
- **`file_storage`:** detect Box (`*.box.com`), Google Drive (`drive.google.com`, `docs.google.com`), SharePoint (`*.sharepoint.com`), Dropbox (`*.dropbox.com`) by scanning anchor hosts vs. the school's primary domain.
- **`cms`:** sniff response headers (`x-generator: Drupal`, `x-powered-by: WordPress`) and URL patterns (`/wp-content/`, `/sites/default/files/`, `/_layouts/`).
- **`waf`:** sniff response headers (`server: cloudflare`, `cf-ray`, etc.).
- **`rendering`:** infer `js_required` when the static HTML response contains zero CDS-ish anchors AND the page body is small/SPA-like (heuristic; conservative). When unknown, leave as `unknown` rather than guessing.
- **`last_outcome`:** mirror the `archiveOneSchool` outcome category, so we can query "show me all schools whose last probe was `auth_walled_microsoft`."

`archive.ts:archiveOneSchool()` upserts the `school_hosting` row at the end of every run.

A nightly job exports the latest `school_hosting` rows back into `schools.yaml` so the YAML stays in sync — gated on diff-only writes to avoid YAML formatting churn (also addresses the open backlog item about `probe_urls.py` destroying schools.yaml formatting).

## What we are NOT doing in this plan

- **Not touching `cds_year`'s unique constraint** (per ADR 0007 backlog item "Retire cds_year as discovery output"). That refactor is independent and larger; keeping `cds_year` as the partitioning signal in `pickCandidates` lets this plan ship without a schema migration on `cds_documents`. We can do it later in a separate PR.
- **Not solving Bucket B (JS-rendered schools)** end-to-end. The hosting JSONB *records* `rendering: js_required` and `auth_required: microsoft_sso` so we know which schools need Playwright or are effectively non-publishing. But routing those schools to a Playwright-based resolver is a follow-up.
- **Not building a generic landing-page discovery tool.** The 467 direct-only schools that lack a proposable landing page stay direct-only until either (a) someone hand-curates a landing page, (b) a future Playwright-based discoverer finds one, or (c) the school is reclassified.

## Migration strategy (3 stages)

**Stage 1: Schema additions, dual-read** (PR 1)
- Add `landing_page_url`, `direct_archive_urls`, `hosting` fields to `schools.yaml` schema.
- Add `school_hosting` Postgres table.
- Migration script populates new fields from existing `cds_url_hint`: heuristic split based on URL extension. Direct-PDF hints → `direct_archive_urls`; everything else → `landing_page_url`.
- Resolver: read both old `cds_url_hint` and new fields, prefer new when present. No behavior change.
- `tools/finder/promote_landing_hints.py --apply` runs against the 67 high-confidence proposals.

**Stage 2: Resolver writes `school_hosting`** (PR 2)
- `archiveOneSchool` upserts hosting metadata on every run.
- Backfill job runs against all 851 active schools to seed the table.
- New audit tool `tools/data_quality/hosting_audit.py` prints distribution: how many auth-walled, how many JS-rendered, etc.
- Resolver routing: skip schools where `auth_required != none` (return early with `verified_walled` outcome instead of re-trying every cron).

**Stage 3: Drop `cds_url_hint`, lock in landing-only** (PR 3)
- Resolver stops reading `cds_url_hint`; only reads `landing_page_url` and `direct_archive_urls`.
- Remove `cds_url_hint` from `schools.yaml` schema.
- Update `tools/finder/probe_urls.py` to write to `landing_page_url` (not `cds_url_hint`).
- Update kids worklist tool: when `landing_page_url` is set, use it; when only `direct_archive_urls` is set, surface a different prompt ("we only have direct files for this school — please find their actual IR landing page if one exists").

## Observability

Per the recent thread on this — observability of resolver runs is currently weak. This plan piggybacks on the schema work to fix it:

- `school_hosting.last_outcome` + `last_outcome_at` is queryable: "schools whose last probe was `auth_walled_microsoft`" → 1-line SQL instead of grepping stdout.
- `hosting_audit.py` produces a structured report per cron run: success rate, drop-off by category, schools transitioned (e.g., went from `unchanged_verified` to `dead_url`).
- A new view `cds_completeness` joins `cds_documents` + `school_hosting` so we can ask "how many active schools with `auth = none` have a 2024-25 doc?" cleanly.

## Open / taste decisions for the gate

1. **Do we delete `cds_url_hint` in this plan, or defer to Stage 3?** Deleting earlier removes ambiguity but increases blast radius (every consumer that reads it needs updating in lockstep). Recommend defer to Stage 3 (simpler PRs, easier to revert).
2. **For the 467 schools with no proposable landing page: keep them as `direct_archive_urls` only, OR demote them to `scrape_policy: unknown` and force re-discovery?** Keeping them preserves coverage we already have. Demoting forces a more thorough discovery pass but risks losing schools where the direct PDF is genuinely all that exists publicly. Recommend keep, with a `direct_only_pending_landing_promotion` flag in `hosting.notes` so they surface as a future work target.
3. **Hosting JSONB in `schools.yaml` or DB-only?** YAML is human-readable and version-controlled but churns on every probe. DB-only is cleaner but contributors lose visibility. Recommend dual: DB is authoritative, nightly diff-export to YAML on changes only (no churn for unchanged schools).
4. **`auth_required` short-circuit: should the resolver skip auth-walled schools entirely, or keep probing in case the school later un-walls?** Skipping saves cron cost. Re-checking quarterly catches recovery. Recommend short-circuit with a 90-day re-check cooldown.

## Success criteria

1. Stage 1 ships: `schools.yaml` has `landing_page_url`/`direct_archive_urls`/`hosting` fields populated for all 851 active schools. The 67 high-confidence rewrites are applied. `school_hosting` table exists and is written-to by the resolver.
2. Stage 2 ships: a re-run of the force-resolve batch (the 460-school equivalent) shows `unchanged_verified` count drop by >70% (because we short-circuit before re-fetching auth-walled and dead-URL schools).
3. Stage 3 ships: kids worklist tool only sends contributors to landing pages. `cds_url_hint` is removed from the YAML schema and the codebase.
4. The hosting audit shows known-correct values for our reference schools: Adelphi → `auth_required: microsoft_sso`, RPI → `file_storage: box`, dmi.illinois.edu → `cms: custom; rendering: static_html; notes: brave-index-blind`.

## Effort estimate

CC-assisted estimates only:
- Stage 1: 4-6 hours (schema additions, migration script, 67-promotion apply, dual-read in resolver)
- Stage 2: 6-8 hours (resolver hosting writes, backfill, audit tool, routing)
- Stage 3: 3-4 hours (cleanup, kids tool update, ADR write-up)

Total: ~15 hours of CC-assisted work, 3 PRs.

---

## CEO Review (Phase 1 / autoplan)

### 0A. Premise Challenge

This plan rests on five premises. Each is worth saying aloud so we can stress-test them before building.

| # | Premise | Confidence | Counter-evidence to look for |
|---|---|---|---|
| P1 | The polymorphic `cds_url_hint` field is the *root cause* of the kids-worklist UX problem and the resolver's wasted-work problem, not just a symptom. | High | If we split the field but the resolver still wastes 50%+ of its calls on dead URLs (irrespective of hint shape), the field shape wasn't the bottleneck. |
| P2 | A hosting JSONB sidecar is worth structuring. The information is durable enough that recording it once saves real cost on every future cron. | Medium | If hosting facts churn often (schools migrate CMSs, change auth, swap WAFs every 6-12 months), the sidecar becomes maintenance overhead. The 2-year ADR audit history suggests this is rare; a 12-month re-validation policy is cheap insurance. |
| P3 | The 467 schools without a proposable landing page genuinely have no findable landing page. They are not a discovery-tooling gap. | Medium-Low | The proposal file (`docs/schools_hint_rewrite_proposal.md`) used Playwright probes from `manual_urls.yaml` — that's a snapshot of what we tried, not a proof of impossibility. A more aggressive probe (e.g., site-search at `school.edu/search?q=common+data+set`, or LLM-assisted IR-page discovery) might find landing pages for 50-200 of them. |
| P4 | ADR 0007's content-layer year detection is sufficient that direct-only schools work without URL-derived year parsing in `pickCandidates`. | High | This is empirically validated: `direct_archive_urls` schools bypass `pickCandidates` entirely; the extraction worker assigns the year from page content. Stage A harness measured 80% recall on PDFs. |
| P5 | The cost of running this refactor (~15 CC-hours, 3 PRs) is justified by the marginal coverage gain plus the resolver-cost savings. | Medium | If the actual coverage gain is small (kids find 50 new years instead of 500), the JSONB sidecar is the more durable win. We should track both metrics. |

### 0B. Existing Code Leverage

Mapping each sub-problem to the code that already exists, so we are not reinventing.

| Sub-problem | Existing code | Reuse strategy |
|---|---|---|
| Resolve a landing page → multiple year-tagged docs | `extractCdsAnchors`, `pickCandidates`, `findSiblingDocsFromParents`, `findDocsViaWellKnownPaths` in `_shared/resolve.ts` | No new resolver code. The split simply directs which path the resolver uses. |
| Force-archive a specific URL | `force_urls` body endpoint in `archive-process/index.ts` | Direct-only schools are essentially `force_urls` lists. Reuse same code path. |
| Promote direct PDFs to landing pages | `tools/finder/promote_landing_hints.py` (67 high-confidence proposals already generated) | Apply via `--apply`, then drop the residual into `direct_archive_urls`. |
| Per-school metadata | `cds_documents.data_quality_flag` (per-doc), `archive_queue.last_error` (per-attempt) | Neither is per-school-durable. New table is justified. |
| YAML-write protection | None — `probe_urls.py` is the open backlog item that destroys formatting | Build YAML write helper that diff-only edits, addressing this backlog item as a side benefit. |
| Detection of CMS / WAF / auth from response | None today, but `fetchText()` already captures `finalUrl`, `contentType`, headers, status | Wire signals into a small `inferHosting()` pure function. |

### 0C-bis. Implementation Alternatives

Three paths considered. The plan picks (A); the others are documented for posterity.

| | (A) Split fields + DB-authoritative JSONB (CHOSEN) | (B) Keep single field, rich JSONB | (C) Schema-less observation log |
|---|---|---|---|
| `schools.yaml` change | New `landing_page_url`, `direct_archive_urls`, `hosting`. Drop `cds_url_hint` in Stage 3. | Keep `cds_url_hint` (any URL kind), add `hosting` JSONB only. | Keep `cds_url_hint`. No YAML change. |
| Persistence | New `school_hosting` Postgres table + nightly diff-export to YAML. | YAML carries everything; no new table. | New `resolver_observations` append-only table; aggregate at query time. |
| Resolver change | Reads `landing_page_url` first, falls back to `direct_archive_urls`. | Same logic as today (sniff URL extension to pick path). | Resolver writes a row per probe; hosting facts are derived via a SQL view. |
| Pros | Strict per-purpose semantics. Kids tool always lands on a browseable page. Resolver cost predictable. | Simplest migration. No YAML schema churn. | Maximum observability; full history queryable. |
| Cons | 3 stages, blast radius across YAML + DB + resolver + tools. | Polymorphism survives — kids tool problem unsolved unless we add a derived "is-landing" flag (essentially recreating the split). | Big aggregation overhead. Hosting facts have no canonical row. JSONB writes per probe = high churn. |
| Effort (CC-hours) | 15 | 6 | 10 |
| Long-term coherence | Best | Worst (kicks the polymorphism can) | Middling |

(A) wins on long-term coherence and on solving all three stated problems (kids UX, resolver cost, lost knowledge). (B) is a shortcut that doesn't fix the core data-shape problem. (C) over-engineers the observability dimension at the expense of canonicality.

### 0D. Mode Selection — SELECTIVE EXPANSION

Hold the stated scope (URL split + hosting sidecar). Cherry-pick two adjacent expansions that are in blast radius and cheap:

1. **Fix `probe_urls.py` YAML formatting destruction** (open backlog item). Reusing the YAML-write helper this plan must build for the diff-export path costs ~30 minutes extra. In-blast-radius (same file, related write-path).
2. **Mark known auth-walled and Box-hosted schools at the same time as the migration** (e.g., Adelphi, RPI). Prevents a re-discovery cycle when the resolver short-circuits in Stage 2. ~1 hour of hand-curation.

Defer everything else (the five other backlog items adjacent to schools.yaml) to TODOS.md. Notably defer:
- "Retire `cds_year` as discovery output" — paired well with this plan logically, but it requires a unique-constraint migration that doubles the blast radius. Keep it as a Stage 4 follow-up.
- LLM-assisted IR-page discovery for the 467 direct-only schools — exciting but speculative. Defer.

### 0E. Temporal Interrogation

- **Hour 1 of Stage 1:** schema additions to `schools.yaml` and `school_hosting` migration. Heuristic split run (regex on URL extension). Inspect a 20-school sample by hand.
- **Hour 6 of Stage 1:** apply 67 high-confidence promotions, write YAML helper, dual-read in resolver, ship PR 1. Resolver behavior unchanged externally.
- **Hour 12 (Stage 2):** resolver writes `school_hosting` on every run. Backfill against all 851 active schools. Audit tool prints distribution. Routing: short-circuit auth-walled schools.
- **Hour 18 (Stage 3):** drop `cds_url_hint`, kids tool update, ADR write-up. Re-run force-resolve batch and check `unchanged_verified` dropped >70%.
- **Hour 6+ (failure mode):** if Stage 1's heuristic split misclassifies hints (e.g., a `.pdf` URL that's actually a landing page that returns HTML), the audit tool catches it in Stage 2's distribution print. Recovery: hand-fix and re-export.

### 0F. Mode confirmed: SELECTIVE EXPANSION
Two expansions accepted (YAML helper backlog fix + hand-curation of known-walled schools). Six expansions deferred to TODOS.md.


---

## Dual-Voice Review

Two independent reviewers (Claude subagent, Codex) read the plan and the relevant code without seeing each other's output. Convergent findings are flagged.

### Consensus Table — Strategy / Scope

| Dimension | Subagent | Codex | Consensus |
|---|---|---|---|
| P1 (field shape is root cause of resolver waste) | REJECT — real cause is re-probe cadence | REJECT — cost knob is cooldown, not schema | **DISAGREE WITH PLAN** — both want a cooldown short-circuit first |
| P2 (hosting JSONB worth structuring) | accept with caveat (need history table) | accept but observations belong in DB only, not YAML | **DISAGREE on storage** — both want DB-only |
| P3 (467 schools genuinely have no landing page) | challenge — needs one more discovery pass | not directly addressed | **PARTIAL DISAGREE** — subagent challenges |
| P4 (ADR 0007 makes direct-only safe) | accept | REJECT — `cds_year` unique constraint still load-bearing; `direct_archive_urls` collides | **DISAGREE WITH PLAN** — Codex finds a real collision risk |
| 6-month regret | second migration when cds_year retirement lands | second migration on YAML when generator finally gets rewritten | **CONFIRMED** — both flag a forward-compat risk |
| Right problem | challenges P1 framing | challenges P1 framing | **CONFIRMED** — both want re-framing |

### Consensus Table — Engineering / Architecture

| Dimension | Subagent | Codex | Consensus |
|---|---|---|---|
| Write-amplification on hosting writes | CRITICAL — diff-export will churn nightly | not flagged directly | **subagent unique** |
| `last_outcome` semantics under multi-candidate fan-out | CRITICAL — undefined | CRITICAL — categories don't exist in current pipeline (typed enum required first) | **CONFIRMED CRITICAL** |
| Hosting JSONB has no history | HIGH — overwrite-only loses 6-month timeline | implicitly addressed via append-only alternative | **CONFIRMED** |
| `school_id` foreign key | HIGH — orphan dimension | not flagged | **subagent unique** |
| Concurrency: resolver write vs nightly export | HIGH — partial snapshot risk | implicitly addressed by "DB-only, no export" | **CONFIRMED** |
| Migration heuristic split is unsafe | HIGH — Case B PDFs misclassified | HIGH — Box/Drive no-extension cases misclassified | **CONFIRMED CRITICAL** — both flag |
| `fetchText` doesn't return headers | not flagged | CRITICAL — plan's "wire facts through" is fiction | **Codex unique — CRITICAL** |
| `SchoolInput` lacks domain | not flagged | CRITICAL — needed for same-origin detection | **Codex unique** |
| `direct_archive_urls` must be typed objects with `year` | not flagged | CRITICAL — collision with `UNIQUE (school_id, sub_inst, cds_year)` for Box/Drive URLs | **Codex unique — CRITICAL** |
| Test plan absence | MEDIUM | MEDIUM | **CONFIRMED** |
| Rollback story | MEDIUM (no `--dry-run`) | HIGH (queue denormalised around `cds_url_hint`; archive-process, discover, schools.ts all hard-code it) | **CONFIRMED HIGH** |
| Plan internally inconsistent (Stage 1 says no behavior change but success criteria implies writes) | not flagged | MEDIUM | **Codex unique** |
| Conflict with ADR 0007 / cds_year backlog | flagged as forward-compat risk | flagged as collision risk | **CONFIRMED** |

### Consensus Table — Contributor Experience

| Dimension | Subagent | Codex | Consensus |
|---|---|---|---|
| New YAML schema is less guessable | HIGH | HIGH (build_school_list.py preserves narrow key set; nested fields will be silently dropped on next regen) | **CONFIRMED CRITICAL** — Codex finds a guaranteed-data-loss failure mode |
| Hosting JSONB cannot be hand-edited safely | HIGH (no schema validator) | implicitly addressed by "DB-only" | **CONFIRMED** |
| Operator rollback story | HIGH (no dry-run, no staging) | HIGH (queue denormalised) | **CONFIRMED CRITICAL** |
| Resolver error messages mixed | MEDIUM | implicit in re-spec | **CONFIRMED** |
| Kids-tool fix too thin | MEDIUM | MEDIUM — strategic overkill for what is essentially "add a `browse_url` column" | **CONFIRMED** |
| Tools/CLI vocabulary will fragment | not flagged | MEDIUM (kids_worklist, active_schools_missing_recent, discover, force_school all hard-code old terms) | **Codex unique** |

### Cross-cutting findings

**FATAL FLAW — `schools.yaml` is a generated artifact.** Codex found that `tools/finder/build_school_list.py:190` only preserves `id`, `name`, `cds_url_hint`, `scrape_policy`, `notes`, and `sub_institutions`. Any new nested fields in `schools.yaml` will be **silently dropped on the next IPEDS rebuild**. The plan's entire "YAML + DB dual-storage" strategy is structurally incompatible with the existing generator. This is a guaranteed-data-loss failure mode, not a stylistic concern.

**FATAL FLAW — `fetchText()` does not expose headers.** The plan's Change 3 claims the resolver "already gathers most of these facts implicitly." It does not. `fetchText()` returns only `{ status, contentType, body, finalUrl }` — no headers, no redirect chain, no origin context. The plan would require redesigning `fetchText()` and threading a `ProbeObservation` object through the entire resolver/archiver/queue/test surface. The "small pure-function add" framing is wrong by an order of magnitude.

**ARCHITECTURAL ALTERNATIVE — both reviewers independently recommended the same architecture:**
1. **Rename `cds_url_hint` → `discovery_seed_url`** (semantic clarity, preserves the resolver's existing direct-seed → parent-walk → well-known-paths upgrade path that currently recovers Brown, Cornell, Williams, etc.)
2. **Add `browse_url`** as a separate field for human/contributor browsing (this is the actual kids-tool fix — one CSV column change)
3. **Add `school_overrides.yaml`** as a separate committed file for hand-curated direct PDFs and manual browse URLs. Keeps `schools.yaml` as the generated-only IPEDS merge artifact.
4. **Add `school_hosting_observations` (append-only) + `latest_school_hosting` view** in DB only — never exported to YAML. Preserves history, avoids YAML churn.
5. **Add `last_verified_at` cooldown short-circuit** as a tiny standalone PR — empirically projected to kill 70-80% of the `unchanged_verified` waste in ~1 hour of work, validating P1 vs the 15-hour refactor.
6. **Define a typed `ProbeOutcome` enum** as a prerequisite PR — so `last_outcome` (in the eventual hosting table) can be populated from structured categories, not string-scraping.

This alternative addresses every convergent finding and preserves the working direct-seed upgrade path. The user's stated direction ("delete direct URLs entirely") would actively *reduce* current automatic coverage for ~467 schools because it removes the parent-walk + well-known-paths fallback that currently rescues those schools.


---

## ✅ APPROVED ARCHITECTURE (post-review)

The original "What changes" section above is **superseded** by this section per the user's response to the autoplan gate. Above is preserved as audit trail of how we got here. Below is what we're actually building.

### The new shape

Six PRs, each independently shippable and revertable. Earlier PRs validate later ones.

#### PR 1 — Cooldown short-circuit (the cheap probe of P1)

**Goal:** kill the 52% `unchanged_verified` waste before committing to the bigger refactor. If this works, P1 (field shape is the cost driver) is empirically falsified — the cost driver was re-probe cadence, and we save ~14 CC-hours of refactor work. If it doesn't, the bigger refactor is genuinely justified.

**Changes:**
- Add `last_verified_at timestamptz` column to `cds_documents` (already exists per the migration, just needs to be written-to consistently).
- In `archiveOneSchool()`: when a single direct-doc hint is verified to match an existing sha256 row, write `last_verified_at = now()` and skip the verification on subsequent crons until the cooldown expires.
- Cooldown: 30 days for `unchanged_verified`, 90 days for `auth_walled_*`, 7 days for `transient` (already retried in current attempt budget).
- Add a `force_recheck` boolean param to `force_school` so operators can bypass the cooldown.

**Effort:** ~1 hour CC-assisted.

**Success criterion:** re-run the 460-school force-resolve batch. If `unchanged_verified` count drops by >70% on the *second* run (after cooldowns fire), P1 is falsified and PRs 4-6 below get re-evaluated against the new cost picture.

**No schema migration needed.** No YAML change. Pure runtime behaviour.

#### PR 2 — Typed `ProbeOutcome` enum (prerequisite for everything observability-related)

**Goal:** structured outcome categories the rest of the work depends on. Today the resolver throws `PermanentError`/`TransientError` with free-text reasons; my Python categoriser at `tools/data_quality/force_resolve_missing.py` does the categorisation client-side by string-matching. That categoriser belongs in the pipeline.

**Changes:**
- New TypeScript enum `ProbeOutcome` in `supabase/functions/_shared/probe_outcome.ts` mirroring the categories produced by the categoriser (`unchanged_verified`, `dead_url`, `auth_walled_microsoft`, `auth_walled_okta`, `auth_walled_google`, `no_pdfs_found`, `wrong_content_type`, `transient`, `success_new_docs`, `success_repaired`, `marked_removed`).
- `archiveOneSchool()` returns `{ action, outcome: ProbeOutcome, ... }` instead of just `action`.
- `archive-process` logs the outcome alongside the existing `event` field.
- `archive_queue.last_outcome ProbeOutcome` column added — preserves outcome history beyond `last_error` text.
- Backfill migration: classify existing `archive_queue.last_error` strings into the new enum where possible.
- `tools/data_quality/force_resolve_missing.py` reads the structured outcome instead of pattern-matching.

**Effort:** ~3-4 hours.

**Success criterion:** running the categorisation report against `archive_queue.last_outcome` produces the same distribution as the Python categoriser produces against the JSONL log.

#### PR 3 — `school_hosting_observations` (append-only) + `latest_school_hosting` view

**Goal:** persistent hosting metadata, owned by the DB, with full history.

**Schema:**
```sql
create table public.school_hosting_observations (
  id                     bigserial primary key,
  school_id              text not null,
  observed_at            timestamptz not null default now(),
  observation_source     text not null check (observation_source in ('resolver', 'playwright', 'manual')),

  -- Inferred dimensions (each nullable — populated when the probe can determine them)
  cms                    text,                -- drupal | wordpress | sharepoint | static | custom | unknown
  file_storage           text,                -- same_origin | box | google_drive | sharepoint | dropbox | intranet | mixed
  auth_required          text,                -- none | microsoft_sso | okta | google_sso | basic
  rendering              text,                -- static_html | js_required
  waf                    text,                -- none | cloudflare | akamai | imperva
  origin_domain          text,                -- the school's own domain at observation time
  final_url_host         text,                -- where the discovery_seed_url actually resolved to

  -- Outcome of this specific probe
  outcome                text,                -- ProbeOutcome enum value (FK soft-coded for now)
  outcome_reason         text,                -- free text for diagnostics (the [200 char] error message tail)
  redirect_chain         jsonb,               -- [{from, to, status}, ...] from fetchText (requires fetchText redesign — see PR 4)

  notes                  text                 -- operator-set on `manual` observations
);

create index school_hosting_observations_school_observed_idx
  on public.school_hosting_observations (school_id, observed_at desc);

create view public.latest_school_hosting as
  select distinct on (school_id) *
  from public.school_hosting_observations
  order by school_id, observed_at desc;
```

**Why append-only:** validates P2 — we can ask "how stable is this fact?" by querying the history. Adelphi flipping from `auth_required: none` → `microsoft_sso` is a row-level event we can graph over time.

**No YAML export.** Hosting data lives in DB only. The kids tool, audit reports, and any future routing logic query `latest_school_hosting`.

**Effort:** ~2 hours (table + view + permissions). The resolver's writes to it land in PR 4.

#### PR 4 — `fetchText()` redesign + resolver hosting writes

**Goal:** give the resolver enough information to populate `school_hosting_observations` correctly. This is the redesign Codex flagged that my original plan understated.

**Changes:**
- `fetchText()` returns `{ status, contentType, body, finalUrl, headers, redirectChain }` (currently returns first four). Headers needed for CMS/WAF inference; redirect chain needed for auth-wall detection (the SSO redirect happens DURING fetch, not after — must be captured per-hop).
- Thread the `school_id` and `domain` through `resolveCdsForSchool()` (currently takes only `hint`). Required for same-origin vs third-party file storage detection.
- New pure function `inferHosting(probeData)` in `_shared/hosting.ts` that takes the redirect chain + headers + final URL host + origin domain and returns inferred dimensions.
- `archiveOneSchool()` writes one row to `school_hosting_observations` per probe, regardless of outcome.
- Update existing `resolve.test.ts` with golden-fixture tests for `inferHosting()`: Adelphi (microsoft_sso), RPI (box), dmi.illinois.edu (custom CMS), a Drupal IR site, a WordPress IR site, a Cloudflare-fronted school.
- Backfill: replay the 448-row force-resolve JSONL through the new `inferHosting()` to seed initial observations.

**Effort:** ~6-8 hours. This is the riskiest PR — gate behind a `HOSTING_OBSERVATIONS_ENABLED` env var so it can be reverted without a code rollback.

**Success criterion:** `select count(*) from latest_school_hosting where auth_required = 'microsoft_sso'` returns ≥ 2 (Adelphi + at least one other school the batch surfaced).

#### PR 5 — `discovery_seed_url` rename + `browse_url` + `school_overrides.yaml`

**Goal:** the actual data-shape work, but in the form Codex/subagent recommended.

**Changes:**
- `tools/finder/schools.yaml`: rename `cds_url_hint` → `discovery_seed_url` everywhere. Pure rename — same semantics. The resolver's existing direct-seed → parent-walk → well-known-paths upgrade path is preserved.
- Add optional `browse_url` field to schools. Used by the kids tool and any human-facing surface. Distinct from the resolver's seed.
- New file `tools/finder/school_overrides.yaml`: hand-curated overrides keyed by school_id. Schema:
  ```yaml
  - school_id: rpi
    browse_url: https://rpi.box.com/v/CDS  # human-friendly Box folder
    direct_archive_urls:
      - { url: https://rpi.box.com/shared/static/abc.pdf, year: "2023-24" }
      - { url: https://rpi.box.com/shared/static/def.pdf, year: "2024-25" }
    hosting_override:
      file_storage: box
      notes: "Box does not serve to crawlers. Manual list maintained quarterly."
  ```
- `build_school_list.py` updated to preserve `discovery_seed_url`, `browse_url` in its preserved-key set. The `school_overrides.yaml` file is NOT touched by `build_school_list.py` — it lives independently and is read at resolver-load time.
- `_shared/schools.ts` reads both `schools.yaml` and `school_overrides.yaml`, merges them, exposes a single `SchoolInput` to the resolver.
- `manual_urls.yaml` (the existing hand-curated file) is consolidated into `school_overrides.yaml` via a one-time migration script.
- All operator-facing tools (`kids_worklist.py`, `active_schools_missing_recent.py`, `force_resolve_missing.py`, `discover/index.ts`, `archive-process/index.ts`) updated to use the new field names in the SAME PR — Codex flagged that fragmenting vocabulary is a real risk.

**Effort:** ~5-6 hours. Includes the build_school_list.py rewrite to handle the new key set safely.

**Success criterion:** running `tools/finder/build_school_list.py` against a fresh IPEDS pull and then diffing against the current `schools.yaml` shows ONLY changes from IPEDS data — no loss of any hand-curated `discovery_seed_url` or `browse_url`.

#### PR 6 — Apply landing-page promotions + hand-curate known-walled schools + kids tool relaunch

**Goal:** ship the operational benefits.

**Changes:**
- Apply the 67 high-confidence landing-page promotions from `docs/schools_hint_rewrite_proposal.md` into `discovery_seed_url` (or `browse_url` where appropriate — some are landing pages, some are direct files).
- Hand-curate `school_overrides.yaml` for the known-hard cases surfaced by the batch: Adelphi (auth: microsoft_sso, no public archive), RPI (Box folder), Indiana (opaque app server), dmi.illinois.edu (custom CMS notes).
- Rewrite `tools/data_quality/kids_worklist.py` to:
  - Query `latest_school_hosting` to skip schools where `auth_required != 'none'` (no point sending kids to auth-walled schools).
  - Use `browse_url` if set, otherwise `discovery_seed_url` if it's a landing page (heuristic), otherwise add a "needs landing page" prompt instead of the direct-PDF URL.
  - Show the school's hosting fingerprint inline (e.g., "this school is on Box — kids may need to download files individually") so kids understand context.
- Update CSV column headers and README.txt accordingly.
- Re-generate the kids worklist batches.

**Effort:** ~3-4 hours.

**Success criterion:** new kids worklist excludes the 3+ confirmed auth-walled schools; surfaces the ~467 direct-only schools with a "find a landing page if one exists" framing instead of sending kids to the stale PDF URL.

### Total effort: ~20 CC-hours, 6 PRs

vs. ~15 CC-hours, 3 PRs in the original plan. The increase is because PR 1 (cooldown) and PR 2 (ProbeOutcome enum) are honest about prerequisite work that the original plan elided.

### Why this serves the long term

1. **Preserves working capabilities.** The direct-seed upgrade path that recovers Brown/Cornell/Williams stays intact. The rename is purely semantic; resolver behavior is unchanged.
2. **Validates premises empirically.** PR 1 either falsifies P1 cheaply (and we stop), or validates it (and we proceed to the bigger work with confidence).
3. **Respects existing architecture.** `schools.yaml` stays generated-only. `school_overrides.yaml` is a clean side-file (matches the pattern the repo already recommends in the backlog).
4. **Forward-compatible with cds_year retirement.** No fields in the new YAML schema reference `cds_year` directly. When the unique-constraint migration ships later, this work doesn't have to be redone.
5. **Append-only history.** Hosting facts are queryable as a timeline, not a snapshot. We can answer "how often do these change?" empirically in 6 months.
6. **Testable.** Golden fixtures for `inferHosting()` (PR 4) and idempotent contract tests for `school_overrides.yaml` round-trip (PR 5).
7. **Vocabulary consolidated.** PR 5 updates every operator surface in lockstep. No half-migrated vocabulary stranding maintainers.

### What's deferred (TODOS.md candidates)

- LLM-assisted IR-page discovery for the 467 direct-only schools (P3 challenge — worth one more discovery pass eventually, but not in this work)
- Combining this work with the `cds_year` retirement (still independent; see backlog item)
- A real `hosting_audit.py` dashboard tool (post-PR 4, once we have data)
- Routing JS-rendered schools to a Playwright-based resolver (PR 4 records the rendering classification; the routing is a follow-up)

### Status

✅ APPROVED via /autoplan gate, 2026-04-18.

