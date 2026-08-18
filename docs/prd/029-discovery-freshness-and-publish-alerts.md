# PRD 029: Discovery freshness — date observability and per-school publish alerts

**Status:** M0–M2 implemented (2026-08-18). Publish-events log, per-school RSS, date UI, and demand-shaped daily escalation.
**Created:** 2026-08-18
**Author:** Anthony Showalter (with Claude, via `/office-hours` → `/plan-eng-review` with a Codex outside-voice pass)
**Related:** [PRD 015](015-institution-directory-and-cds-coverage.md) (coverage/trust layer), [PRD 019](019-cds-change-intelligence.md) (change intelligence — adjacent, deliberately not reused), [PRD 028](028-organic-search-cds-queries.md) (freshness as a ranking/trust signal), [ADR 0008](../decisions/0008-takedown-process.md) (takedown process), [design doc (superseded)](../designs/discovery-freshness-notifications.md)

---

## Executive summary

Two related gaps. First, school and year pages show the *document's* vintage
(2025-26, etc.) but never collegedata.fyi's own pipeline timestamps — when we
found the file, when we archived it — so a visitor can't tell how current the
archive's read of a school actually is. Second, there's no way for someone
who cares about one school (a parent refresh-mashing a university's IR page
every day in the fall admissions cycle) to get notified the moment a new CDS
is found, without collegedata.fyi collecting emails or building push
infrastructure.

A per-school RSS/Atom feed solves the second problem with zero new
infrastructure risk: no email list, no push service, just a URL any RSS
reader or notification bridge already knows how to consume. But the feed
cannot safely be built by querying `cds_documents` directly, and that's the
central engineering finding of this PRD.

`cds_documents` is a **mutable state table** — a `refresh` updates a row in
place rather than inserting one, `unchanged_verified` runs re-touch
`last_verified_at` without new content, and a new row's `source_provenance`
can be `mirror_college_transitions` or `operator_manual` instead of the
school actually publishing something. Querying "recently discovered rows"
for a feed either misses genuine refresh events, double-counts
re-verifications, or fires a misleading "your school just published!" alert
on a third-party mirror catch-up. An RSS feed needs an **immutable event
log**, not a live-state table. This PRD adds one.

The good news: no new automated crawling is needed. `archive-enqueue` /
`archive-process` already re-check every school in the corpus weekly,
year-round, via Supabase `pg_cron` (live since 2026-04-15). This PRD adds an
event log, a `source_provenance`-filtered feed over it, and a daily-cadence
escalation for a demand-shaped top-N tier — it does not touch whether
discovery happens, only how precisely we observe and communicate it.

## Current state (what we're building on)

- `cds_documents.discovered_at` exists; `extraction_status` is a
  CHECK-constrained text column (not a native enum) with no timestamp on the
  `extracted` transition.
- `archive-enqueue` (`supabase/functions/archive-enqueue/`) runs daily via
  `pg_cron`, re-checking every "successful" school every 7 days year-round
  via a flat `archiveCooldownDaysForOutcome(outcome, now)` function — no
  per-school tiering, no school identity in the signature.
- `refreshDocumentWithNewSha` (`supabase/functions/_shared/db.ts`) **updates
  the existing `cds_documents` row** and inserts a new `cds_artifacts` row
  when a school's file changes — it does not create a new document row.
- `source_provenance` (`20260419100000_source_provenance.sql`) already
  distinguishes `school_direct` from `mirror_college_transitions` and
  `operator_manual` — exactly the signal needed to know whether a change
  represents the school publishing something, versus our own mirror/backfill
  activity.
- `source_http_last_modified` and extracted PDF/XLSX metadata dates
  (`20260505160000_archive_observability.sql`) already capture "is this file
  genuinely fresh" more accurately than our own crawl timing — documented in
  that migration as built for exactly this kind of freshness signal, and
  currently unused for it.
- `data/watchlists/top_200_change_intelligence.yaml` is PRD 019's launch
  watchlist, and PRD 019 states explicitly: **"operator-only until the first
  report ships."** This PRD does not read from or reference that file.
- `school_hosting_observations` is the existing precedent for an append-only,
  `school_id`-keyed side table — the pattern this PRD's new events table
  follows.

## Problem

Parents, counselors, and journalists who care about one school have no way
to know when collegedata.fyi's archive of that school changes, short of
checking back manually — the same behavior that already happens on the
school's own IR page during admissions season. Separately, nothing on a
school or year page discloses how current our own read of that school is,
only the document's own vintage.

## Goals

1. Show discovery and archival timestamps on school and year pages,
   alongside (not instead of) the document's own vintage.
2. Ship a per-school RSS feed that fires only on real, school-originated
   publish events — never on mirror catch-up, operator backfill, or
   re-verification of an unchanged file.
3. For a demand-shaped top-N tier, tighten detection latency from the
   default weekly cadence to daily once a school is far enough past its
   last known publish that a new one is plausible.
4. Do this without leaking PRD 019's operator-only watchlist membership.

## Non-goals

- **Not a rebuild of PRD 019's change intelligence.** PRD 019 emits
  field-level *delta* events (admit rate moved) behind a human-review gate.
  This PRD emits raw *publish-event* facts (a new school-direct file
  exists) with no inference risk, so it does not touch PRD 019's review
  queue or its event tables.
- **Do not reuse or reference `top_200_change_intelligence.yaml`.** PRD 019
  states that list is operator-only until report launch; this PRD's tier
  list must be independently computed from public data (see M2).
- **Do not build push notifications, email digests, or an account system.**
  RSS/Atom is the entire distribution mechanism — subscribing is the
  reader's problem to solve with a reader they already have.
- **Do not promise "within N hours of the school publishing."** The system
  only knows when it successfully probed a school, not when the school
  actually posted the file. Success criteria are phrased in terms of
  probe-to-alert latency, not publish-to-alert latency.
- **Do not emit retraction/correction feed entries in v1.** ADR 0008
  takedowns (`participation_status = 'withdrawn'`) and automated dead-link
  detection (`marked_removed`) both remove documents after a feed entry may
  already have gone out; RSS/Atom has no native retraction. Document as a
  known v1 limitation rather than building a correction mechanism now.
- **Do not make the "actively monitored since" badge idea a v1 requirement.**
  Real, worth building, but a fast-follow — it's pure UI on top of the
  escalation state this PRD already has to build.

## Users and jobs

### Parent or counselor watching one school

"I want to know the moment my kid's target school posts a new Common Data
Set, without giving anyone my email or checking their IR page every day
during application season."

### Journalist or researcher

"I want a durable way to know when a specific school's data changes, that I
can point an RSS reader or automation at, without collegedata.fyi knowing
who I am."

### IR professional

"If this archive alerts on my school, it should only be when we actually
published something — not when some third-party mirror or your own operator
backfill happened to touch the row."

## Product principles

1. **An alert is a claim.** Every feed entry implicitly says "this school
   published something." That claim must be backed by `source_provenance =
   'school_direct'` — never a mirror or manual entry — or the claim is
   false and the archive looks unreliable.
2. **Events, not state.** The feed is built from an append-only log of what
   happened, not a query over the current shape of a mutable table. A row
   being updated in place must never cause a feed entry to silently
   disappear, duplicate, or rewrite.
3. **Say what we actually know.** Success criteria and UI copy describe
   probe latency and archival timestamps, never claim to know the school's
   true publish moment.
4. **No watchlist leakage.** Nothing about this feature — feed timing,
   badges, tier membership — may make PRD 019's operator-only Top 200 list
   inferable from the outside.

## What ships

### M0 — Publish-events substrate

1. New migration: `cds_publish_events` (append-only, mirrors the
   `school_hosting_observations` pattern):
   ```
   id                bigserial primary key
   school_id         text not null
   document_id       uuid not null references cds_documents(id)
   cds_year          text not null
   event_type        text not null check (event_type in ('inserted','refreshed'))
   source_provenance text not null
   source_sha256     text not null
   occurred_at       timestamptz not null default now()
   ```
   Indexed on `(school_id, occurred_at desc)`.
2. A `for each row` trigger (or explicit insert alongside
   `insertFreshDocument` / `refreshDocumentWithNewSha` in
   `supabase/functions/_shared/db.ts`) writes one `cds_publish_events` row on
   every `inserted` and `refreshed` outcome. This is the fix for the
   design doc's original bug: `refreshed` updates `cds_documents` in place,
   so a feed reading `cds_documents.discovered_at` would never see it —
   the event log captures it independently of what happens to the parent
   row afterward.
3. Same migration, additive: `cds_documents.extracted_at timestamptz`, set
   only by the extraction worker's central status-writing helper
   (`tools/extraction_worker/worker.py`) at the
   `extraction_status → 'extracted'` transition. Touches that helper, the
   `cds_manifest` view, generated `database.types.ts`, and the public API
   docs page (`/api`) — larger than a bare column add.

### M1 — Feed + date UI

1. `web/src/app/schools/[school_id]/feed.xml/route.ts` — RSS 2.0 (broader
   reader support than Atom for this use case). Reads `cds_publish_events`
   filtered to `source_provenance = 'school_direct'`, joined to
   `cds_documents` for display fields. One entry per event (not collapsed
   per school+year — a `sub_institutional` refile is a genuinely distinct
   event). Last 20 entries, unauthenticated, cached the same way existing
   pages are (`revalidate = 3600`).
2. School hub and year pages: add discovery/archival timestamps as a lead
   sentence or metadata row, using `source_http_last_modified` /
   extracted-metadata dates when present, falling back to `discovered_at`
   when the school's server doesn't send Last-Modified and the document has
   no embedded creation date. State which signal is being shown — don't
   present a fallback timestamp as if it were the precise one.
3. `<link rel="alternate" type="application/rss+xml">` on school pages
   pointing at the feed, so it's discoverable without a separate directory.

### M2 — Demand-shaped daily escalation

1. **Independently computed top-N tier list**, sourced from public CDS C1
   applicant-volume data (the same public-facing demand proxy PRD 028
   already uses for VT/HMC) — not derived from, referenced against, or
   overlapping-by-construction with `top_200_change_intelligence.yaml`.
   Two lists happening to both contain Harvard is fine; one being
   computable from the other is not.
2. Escalation state lives on `cds_publish_events`/a small derived table,
   not solely inside `archive-enqueue`'s scheduler: a school's "lock-on"
   timestamp is set from the first `cds_publish_events` row recorded after
   this feature ships, regardless of which path wrote it (resolver, mirror
   ingest, `force_school`, `archive-upload`). Writing the marker off the
   shared event log — the same one MO already introduced — avoids the
   original design's gap where only `archive-enqueue` remembering to update
   a side table would silently drift as soon as any other write path
   created a document.
3. `archiveCooldownDaysForOutcome` gets a signature change to accept tier +
   lock-on state (`archive-enqueue/index.ts` passes it in) and returns a
   1-day cooldown once a top-N school is 9+ months past its last-known
   `source_http_last_modified`/extraction-metadata date (falling back to
   `discovered_at`). This only widens the *success*-outcome window — failure
   outcomes (`auth_walled_*` 90d, `dead_url` 14d, etc.) keep their existing
   cooldowns regardless of tier, so a top-N school that starts 404ing
   doesn't get probed daily forever.
4. The 9-month lookback needs its own targeted query against
   `cds_publish_events` for the ~50 tier school_ids — `archive-enqueue`'s
   existing `latest_archive_terminal_rows` RPC is bounded to roughly a
   95-day lookback and cannot serve a 9-month check without either blowing
   up that bound for the whole corpus or adding a small dedicated read
   scoped to the tier. Use the latter — 50 rows, cheap, no shared-query
   risk.

## Implementation notes

- `cds_publish_events` is the load-bearing new piece of this PRD. Get its
  write path right before building anything downstream of it (the feed,
  the escalation lock-on) — both depend on it being complete and correct.
- The `extracted_at` column touches more surface than a migration: the
  worker's status helper, `cds_manifest`, generated types, and API docs all
  need the change landed together, not just the schema.
- Design: read `web/DESIGN_SYSTEM.md` before adding the date UI. Timestamps
  are typesetting, not a new card type.
- Freshness-signal precedence for both the UI and the 9-month clock:
  extracted-document metadata date → `source_http_last_modified` →
  `discovered_at`, in that order, and the UI states which one is being
  shown.

## Verification

- [ ] `cds_publish_events` gets one row per `inserted`/`refreshed` outcome,
      verified against a school that goes through both paths.
- [ ] A `refreshed` event with the same `cds_year` produces a feed entry —
      the specific bug the original design missed.
- [ ] A `mirror_college_transitions` or `operator_manual` insert produces
      **no** feed entry.
- [ ] Feed entries never disappear, duplicate, or change identity when the
      underlying `cds_documents` row is later updated again.
- [ ] `extracted_at` is only ever set at the `extraction_status → extracted`
      transition — an unrelated later edit to the row does not change it.
- [ ] A top-N school 404ing does not escalate to daily probing; it follows
      the existing failure-outcome cooldown.
- [ ] The tier list is inspected to confirm no derivation path traces back
      to `top_200_change_intelligence.yaml`.

## Failure modes

| Failure | Why it happens | Mitigation |
|---|---|---|
| Feed fires on a mirror/backfill event | Naively querying `cds_documents` instead of provenance-filtered `cds_publish_events` | M0's event log + `source_provenance = 'school_direct'` filter, verified in the checklist above |
| `refreshed` events silently missing from the feed | `refreshDocumentWithNewSha` updates a row in place; a feed keyed on `discovered_at` never sees it | `cds_publish_events` is written on both `inserted` and `refreshed`, independent of what happens to the parent row |
| Escalation state drifts out of sync | Lock-on marker written only by `archive-enqueue`'s scheduler while other paths (mirror ingest, `force_school`, `archive-upload`) also create documents | Lock-on derives from the shared `cds_publish_events` log, not from scheduler-only writes |
| PRD 019 watchlist membership becomes inferable | Reusing or trimming `top_200_change_intelligence.yaml` for a public-facing tier | Independently computed tier list from public applicant-volume data; verified no derivation path in the checklist |
| A false "just published" impression from stale metadata | `source_http_last_modified` missing and extracted metadata absent, silently falling back to `discovered_at` without saying so | UI states which freshness signal is being shown, never presents a fallback as the precise one |

## Open questions

1. Exact top-N list size and computation (top 50 by C1 applicant volume, as
   in PRD 028's VT/HMC comparison, or a different public-data formula) —
   compute during M2, not blocking M0/M1.
2. Whether `cds_publish_events` should also become the substrate PRD 019
   eventually reads from for its own event detection, or stays a
   deliberately separate, lighter-weight log. Leaning separate (Non-goals),
   revisit if the two features' maintenance cost argues otherwise.
3. Whether the "actively monitored since" badge ships as a fast-follow PR
   or waits for demand signal from the feed's actual usage.

## Recommendation

Ship M0 first and alone if useful — the publish-events log is valuable
independent of the feed (it's a better audit trail than the current
mutable-row-only history). M1 (feed + date UI) is the user-facing payoff and
should follow immediately after, since M0 is exactly the substrate it
needs. M2 (escalation) can trail by however long it takes to compute an
honest, independently-sourced tier list — there's no user-visible harm in
that gap, since a school without escalation just keeps the existing
weekly cadence, and nothing in this PRD promises daily probing on day one.

## References

- Superseded design doc: [`docs/designs/discovery-freshness-notifications.md`](../designs/discovery-freshness-notifications.md) — `/office-hours` session, three rounds of adversarial review, corrected by this PRD's `/plan-eng-review` + Codex outside-voice pass.
- [PRD 019 change intelligence](019-cds-change-intelligence.md) — adjacent, deliberately not reused (see Non-goals).
- [PRD 028 organic search](028-organic-search-cds-queries.md) — "freshness is a ranking feature," applicant-volume-as-demand-proxy precedent.
- [ADR 0008 takedown process](../decisions/0008-takedown-process.md) — governs the retraction limitation noted in Non-goals.
- `supabase/functions/_shared/db.ts` — `insertFreshDocument` / `refreshDocumentWithNewSha`, the write paths `cds_publish_events` hooks into.
- `supabase/migrations/20260419100000_source_provenance.sql` — the provenance filter this PRD depends on.
- `supabase/migrations/20260505160000_archive_observability.sql` — `source_http_last_modified` and extracted-metadata date fields.
- `supabase/migrations/20260419000000_school_hosting_observations.sql` — the append-only table pattern `cds_publish_events` follows.
