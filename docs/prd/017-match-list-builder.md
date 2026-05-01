# PRD 017: Match list-builder microsite (v2)

**Status:** Defined, not started. Activates after PRD 016 hits the engagement gate.
**Created:** 2026-05-01
**Author:** Anthony + Claude (autoplan)
**Related:** [PRD 016](016-academic-positioning-card.md), [PRD 018](018-open-college-fit-data.md), [autoplan record](../../.claude/plans/system-instruction-you-are-working-starry-candle.md)

---

## Context

PRD 016 ships per-school positioning on the existing `/schools/[school_id]` page. This PRD scopes the next surface: a destination list builder at `match.collegedata.fyi` that lets a user (most likely a counselor or anxious parent) enter a profile once and see a ranked list of schools across the corpus, grouped by tier, with the per-school card embedded inline.

The autoplan strategic review concluded this surface is the *second* deliverable, not the first, because:

1. The per-school card on existing SEO traffic is a smaller, more defensible artifact.
2. A destination microsite cold-starts its own SEO and dilutes the archive's authority.
3. Counselor adoption is unverified at v1 ship time. v2 should be conditional on engagement signal.
4. Destination list-builders are a crowded category with several entrenched competitors competing on distribution; entering it without an engagement signal from PRD 016 is premature.

This PRD therefore exists as a defined, pre-conditioned, deferred backlog item — so the future direction is documented but the build doesn't start until the data justifies it.

## Pre-conditions to activate this PRD

All three must be true before implementation begins:

1. **PRD 016 reaches >500 weekly active users on the positioning card.** Measured by Vercel analytics page-view + profile-entry counters. Validates that positioning is a real-user demand, not just a hypothesis.
2. **At least one IEC pilot has used the v1 surface with 3+ real students.** Direct outreach: 5-10 IECs in the user's network are given the PRD 016 surface plus a Google Sheet template. If 1+ uses it on a real list within 30 days, counselor demand is signaled. If 0 use it, audience hypothesis was wrong; revisit before building v2.
3. **Top-500 academic-profile coverage audit lands at >70% completeness.** The card on a single school can degrade per-school. The list builder cannot — partial data degrades the entire ranking.

If any pre-condition fails, do not build PRD 017. Consider PRD 018 (merit-aid intelligence) as the alternative next move.

## What ships in v2 (when activated)

### List-builder UI at `match.collegedata.fyi`

- **Side panel:** student profile entry (GPA + scale, SAT, ACT, optional state, optional intended-major). Reuses the same `StudentProfile` type from PRD 016's `positioning.ts`.
- **Main panel:** filterable, sortable list of schools across the full corpus, grouped by tier (Likely / Strong fit / Possible / Unlikely / Long shot). Each row uses the per-school positioning card from PRD 016 in a compact horizontal layout.
- **Filters:** public/private, region, admit-rate range, test-optional vs required, has-current-CDS, Carnegie classification.
- **Counselor-friendly export (CSV).** One row per school, columns covering tier, percentile, admit rate, source CDS year, source PDF URL. Matches what a counselor would paste into a Google Doc or share with a family.
- **Print-friendly view.** PDF generated client-side via `window.print()` with a print-only stylesheet. No server-side PDF rendering — simpler.

### Data layer

Reuses `school_browser_rows` (already shipped by PRD 012) and `cds_fields` (for the GPA tiebreaker if PRD 016's GPA scale-resolution sprint has landed). The list builder queries `school_browser_rows` filtered to rows with sufficient data (`sat_composite_p50 IS NOT NULL OR act_composite_p50 IS NOT NULL` AND `acceptance_rate IS NOT NULL`).

Performance gate: the list query must return ranked results in <500ms p95. If `school_browser_rows` row count exceeds a threshold where in-memory ranking becomes slow (~5,000 rows), introduce a server-side ranked view; otherwise rank client-side.

### Sharing — "save game code"

Instead of `?sat=1450&act=33` URL params (which leak scores through referrers, search history, browser sync), v2 introduces a short shareable code pattern modeled on the Porsche configurator:

A 6-7 character alphanumeric code, e.g. `K9F-3XQ`, encodes the profile. Two implementation candidates, picked at v2 design time:

- **Stateless (default).** Base32-encoded packed integer of `(gpa × 100, sat, act, flags)`. Fully client-side, no server lookup, no PII storage. ~30 bits of payload covers GPA(0-450), SAT(400-1600), ACT(1-36), 4 boolean flags. Code is decoded on the receiving end purely in the browser.
- **Stateful.** Server-side lookup keyed on the code; allows richer profiles (state, major, intended ED/EA, etc.) but requires a Supabase table and brings COPPA/FERPA posture back into scope.

Default to stateless unless v2's feature set demands more capacity than ~40 bits of packed state. The stateless pattern is the cleanest privacy posture: a code can be shared in a Slack message or text without ever leaving a server-side trail.

### Optional saved counselor profiles

**Only if** PRD 016 telemetry shows counselor-driven traffic. If counselor demand is unproven, ship localStorage-only and skip this surface entirely.

If counselor accounts ship:

- Supabase Auth, magic-link only (no password handling).
- Counselor-asserted "I have parental consent for any minors" checkbox at signup, stored as a boolean on the user row.
- Saved cohorts: a counselor can name a list, save profiles by student initials only (no full names, no DOB beyond grade level), and track multiple students.
- Privacy policy update: data minimization, deletion-on-request, no third-party sale.

### Naming

`match.collegedata.fyi`. The user explicitly accepted the brand-collision cost with collegedata.com's "College Match" tool. "match" is non-proprietary and used by dozens of services in the category. Subdomain SEO cold-start cost is the price of audience separation.

DNS + Vercel project setup is operational, not a code concern. The microsite is a separate Next.js app or a Vercel rewrite to a subdirectory of the main app. Pick at implementation time based on bundle weight.

## What does NOT ship in v2

Deferred to v3 or beyond:

- **In/out-of-state stratification for publics.** CDS does not publish state-stratified percentiles. The list-builder cannot reflect this; methodology page calls this out by name.
- **Per-program / per-major calibration.** CDS only publishes institution-wide numbers. Major-level competitiveness is tribal knowledge; we don't have it.
- **Saved profiles server-side without proven counselor demand.** Default is localStorage + save-game-code only. Auth is conditional.
- **Reach/target/safety hard labels.** Same vocabulary as PRD 016 (Likely / Strong fit / Possible / Unlikely / Long shot). The reviewers' constraint about implying counselor-grade calibration applies in v2 as much as v1.
- **Merit-aid layer.** Lives in PRD 018.

## Critical files (when implementation begins)

This section is illustrative, not final. Re-scope at activation time.

**New:**
- `web/src/app/(match)/...` — separate route group for the microsite, OR a new Next.js app under `match/` if Vercel rewrites are too costly
- `web/src/lib/savecode.ts` — encode/decode for the save-game-code pattern
- `web/src/components/SchoolListItem.tsx` — compact horizontal positioning card for the list view
- `web/src/components/ListBuilderFilters.tsx` — filter panel
- `web/src/lib/list-builder.ts` — ranking + filtering logic (pure TS)
- `docs/prd/017-match-list-builder.md` — this file, expanded into implementation detail
- DNS/Vercel: `match.collegedata.fyi` configured as a subdomain or rewrite

**Modified:**
- `docs/ARCHITECTURE.md` — note the new microsite surface
- `web/src/app/page.tsx` — link to the microsite from the main site nav (lightly, to avoid muddying the archive's brand)

**Reused:**
- `web/src/lib/positioning.ts` — same scoring function as PRD 016
- `web/src/components/PositioningCard.tsx` — embedded per-row in the list

## Failure modes (deferred)

- **Coverage drops mid-list.** Schools with NULL percentiles must render visibly degraded inside the list, not silently mis-ranked.
- **Save-game-code collisions.** Stateless codes have no collision concern; stateful codes need a UNIQUE check on insert and a regenerate-on-collision retry.
- **Counselor session leak.** If saved profiles ship, a stale session token must not expose another counselor's cohort. Standard auth hygiene.
- **PDF print fidelity.** Client-side `window.print()` produces inconsistent output across browsers; build with explicit print stylesheets and test on Chrome / Safari / Firefox at PR time.

## Verification (deferred)

To be filled in at activation time. Sketch:

1. Unit tests for save-game-code encode/decode round-trip across 1000 random profiles.
2. List ranking correctness against the same 10 fixture schools used in PRD 016.
3. Filter combinations: public + test-optional + admit rate < 25% returns the expected subset.
4. CSV export round-trips: paste into Google Sheets, verify columns + values.
5. Save-game-code share: encode in browser A, decode in browser B, verify identical render.

## Effort estimate (rough, refine at activation)

2-3 weeks (1 person, CC+gstack pace). Most of the cost is the list-builder UI itself — the data layer reuses PRD 016 + PRD 012 entirely.

## Decision tree at activation

```
PRD 016 telemetry + counselor pilot signal
    |
    +-- positioning has demand AND coverage > 70%? --- YES --> build PRD 017
    |
    +-- positioning has demand BUT coverage < 70%?   --- spend a sprint on extraction quality first
    |
    +-- positioning lacks demand, API has demand?    --- skip PRD 017, jump to PRD 018
    |
    +-- neither has demand?                          --- stop. The hypothesis was wrong. Revisit.
```

This decision tree is the actual deliverable of this PRD. The build is conditional, not committed.
