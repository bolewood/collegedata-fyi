# PRD 016: Academic positioning card (v1)

**Status:** Shipped 2026-05-02. Academic positioning card, profile controls, methodology page, and fit-tier tests are live on school pages.
**Created:** 2026-05-01
**Author:** Anthony + Claude (autoplan-reviewed)
**Related:** [PRD 010](010-queryable-data-browser.md), [PRD 012](012-browser-field-expansion-after-v03.md), [PRD 015](015-institution-directory-and-cds-coverage.md), [PRD 017](017-match-list-builder.md) (deferred), [PRD 018](018-open-college-fit-data.md) (deferred), [Design skeleton](../design/positioning-card-skeleton.md), [autoplan record](../../.claude/plans/system-instruction-you-are-working-starry-candle.md)

---

## Context

A student or parent visiting a `/schools/[school_id]` page today sees the school's archived Common Data Set documents, federal Scorecard outcomes, and coverage status. What they cannot see, even though the data is in our database, is: *where would my numbers land in this school's admitted class?*

That question is one of the highest-search-volume queries in the college-admissions space. PRD 012 already shipped the SAT/ACT percentile columns into `school_browser_rows` and exposes them via PostgREST. This PRD spends that data into a per-school positioning surface on the existing school detail page.

The strategic frame: collegedata.fyi's posture (per ADR 0004) is that no free public CDS API existed and we built one. Several paid tools in the academic-positioning category sell some version of "where you'd fit," and free entrants in the space ship it without source links. The defensible niche for this project is the **open, source-linked, methodology-transparent** version of the same primitive — every claim auditable against the school's own published CDS PDF.

The autoplan strategic review (CEO + Eng + Design) established the v1 shape:

1. Positioning is a commodity feature in this category; the more defensible asset is open data with linked sources (see PRD 018 for the deeper data layer).
2. A per-school card on existing SEO-ranked school pages beats a destination microsite (microsite deferred to PRD 017).
3. The data layer needs zero migrations because PRD 012 already shipped it.
4. GPA stays out of cross-school percentile scoring because scale comparability is unresolved (PRD 012 explicitly held this out).

## Problem

The reviewers' hardest constraint: **any positioning UI risks looking more precise than CDS C.9/C.11/C.12 actually support.** Test-optional schools publish percentiles only for the ~50% of admits who submitted scores. GPA scales are inconsistent. Holistic admit decisions weight institutional priorities (legacy, athletics, geographic balance, intended major) that are nowhere in CDS. The card must be honest about all of this without disappearing into caveats.

## What ships in v1

A per-school positioning card on `/schools/[school_id]` between the documents ledger (line 337 in `web/src/app/schools/[school_id]/page.tsx`) and `<OutcomesSection>` (line 339).

### Card behavior

- **Server-renders** the school's published 25/50/75 SAT and ACT bars, % submitting captions, CDS year, and a source link to the archived PDF. SEO-meaningful.
- **Progressively enhances** with a client component (`'use client'`) that takes a student profile (GPA, SAT, ACT) via inline mini-form, persists in localStorage as `cdfyi.positioningProfile.v1`, and renders the student's position against the school's bands.
- **Lead with a positional sentence**, not a tier badge. Sentence form: *"Your SAT is above the 75th percentile of admitted students who submitted scores. Your GPA falls in the modal admit bucket. This school admits 9% of applicants."* The sentence reads as interpretation; a badge reads as verdict.
- **Tier label is secondary** — small mono caption beneath the sentence in the form `§ TIER · STRONG FIT · BASIS: SAT IN MID-50%, ADMIT RATE 25%`. Vocabulary: **Likely / Strong fit / Possible / Unlikely / Long shot.** Not safety/target/reach (which implies counselor-grade calibration the data doesn't support).
- **Tier label suppressed** when admit rate < 15% AND scores are inside the school's mid-50%. At that selectivity, numerical position barely moves the outcome, and showing a tier overstates precision. Render the sentence + admit rate only.
- **Test-optional caveat** is mandatory and inline with the SAT strip in every applicable state: `§ FROM THE 47% OF ADMITS WHO SUBMITTED SCORES · 2024-25 CDS · METHOD →`.
- **Graceful degradation** for missing fields: card hides itself entirely for schools with no row in `school_browser_rows` or with `data_quality_flag IN ('wrong_file', 'blank_template', 'low_coverage')`. Existing page renders unaffected.

### GPA in v1 — soft tiebreaker only

The card reads `cds_fields` for `C.1201` (avg HS GPA) and `C.1202` (% submitting GPA) per-school via a new `fetchAvgGpaBySchoolId` helper. Renders a side-by-side display: *"School avg HS GPA 3.91 — your entered 3.85."* No percentile claim, no contribution to the tier label.

**Mandatory follow-up — track separately as a focused sprint.** PRD 012 held GPA out of `school_browser_rows` because weighted vs unweighted vs unknown scales make cross-school comparison unsound. v1's soft tiebreaker is the cheapest defensible thing to ship. The system fix is a separate workstream:

1. Extract scale evidence from CDS source PDFs where available (some schools state the scale explicitly, most do not).
2. Define an `unknown_scale` fallback and a normalization rule.
3. Manually audit a sample of 100 schools across selectivity tiers.
4. Decide whether `school_browser_rows` can ever responsibly carry GPA in normalized form.

This sprint is a precondition for any v1.1 GPA promotion and any v2 list-builder GPA filter. Track in `docs/backlog.md`.

### Methodology page

`/methodology/positioning` (under `web/src/app/methodology/positioning/page.tsx`). Static SSR. Anatomy:

- **One-line lede:** "This page shows where your scores would land in a school's admitted-class numbers. It is not a chance-me, and it does not predict admissions decisions."
- **What we use:** sub-sections per CDS field (C.7 / C.8 / C.9 / C.11 / C.12 / C.1 / C.2), each with the specific use and a worked example. Use one real school (e.g. Bowdoin's 2024-25 CDS) for the worked-example numbers.
- **What we don't use:** legacy, athletic recruitment, geographic balance, demonstrated interest, intended major, in/out-of-state stratification, essays, ED/EA timing. Each bullet is one sentence with a one-clause rationale.
- **Why this isn't a chance-me:** three plain-English paragraphs explaining the difference between a position and a prediction.
- **Sources and audit trail:** every claim links to a CDS question number; the worked example links to the school's archived PDF.

### Public API documentation

The "public API endpoint" deliverable is **already shipped** — PostgREST serves `school_browser_rows` today. This PRD adds documentation only:

- A curl example block on the methodology page showing how to fetch `school_browser_rows` filtered by `school_id`.
- A note in `web/src/app/api/page.tsx` (the existing public API doc page) referring to the academic-positioning endpoint specifically.

No API code change, no new resource.

## What does NOT ship

This list is load-bearing. Eng review will hold the line on it:

- **No list builder.** No `/list-builder` route, no cross-school filtering by tier. Per-school only. Reserved for PRD 017.
- **No counselor accounts.** No Supabase auth wiring, no saved profiles server-side. localStorage only.
- **No URL-shareable profiles in v1.** No `?sat=1450&act=33` deep-linking. v2 introduces a "save game code" pattern (PRD 017).
- **No PDF or CSV export.** The existing `/browse` export is unaffected.
- **No reach/target/safety SQL function.** Tier classification is pure TS, client-side. Postgres stays out of the scoring path.
- **No merit-aid layer.** Codex flagged this is the actual moat; deferred to PRD 018.
- **No microsite, no `match.collegedata.fyi`** in v1. Reserved for PRD 017.
- **No GPA percentile scoring.** PRD 012's holdout reason still applies. v1 ships soft tiebreaker only (see above).
- **No major-level / residency-stratified scoring.** CDS doesn't publish it; methodology page calls this out as a known limitation by name.
- **No ML scoring.** Pure publishable rubric, auditable line-by-line.
- **No new schema columns.** Migration count for v1 = 0.
- **No new public API resource.** PostgREST on `school_browser_rows` already serves it.
- **No third-party product names in copy.** Surface and methodology language uses neutral terms ("academic positioning," "where you'd fit"). Do not reference, parody, or reproduce the naming or visual layout of any specific competitor product.

## Architecture

```
[arrows marked * already exist; arrow ! is the only new wiring]

CDS PDF (school IR site)
   |  *  discovery + mirror (Edge Function on cron)
   v
cds_documents + Storage archive
   |  *  tools/extraction_worker/  -> tier1/tier2/tier4/tier6
   v
cds_artifacts (canonical_json keyed to C.901..C.916, etc.)
   |  *  tools/browser_backend/project_browser_data.py
   v
cds_fields (long-form)              <-- read here for GPA tiebreaker
   |  *  PRD 012 projection logic
   v
school_browser_rows                 <-- SAT/ACT columns from PRD 012
   |  *  PostgREST (api.collegedata.fyi)
   v
   +- *  /browse  (existing SchoolBrowser)
   |
   +- !  fetchBrowserRowBySchoolId(school_id)             [NEW]
   +- !  fetchAvgGpaBySchoolId(school_id)                 [NEW]
        |
        v
    web/src/app/schools/[school_id]/page.tsx
        |
        |  *  ssr passes typed row
        v
    <PositioningCard> (RSC)        <-- NEW
        +- 25/50/75 range bars rendered server-side (SEO)
        +- <PositioningCardProfile> (client)
              | reads localStorage 'cdfyi.positioningProfile.v1'
              v
          scorePosition(profile, school)                  [NEW pure fn]
              v
          tier label + score plotted
```

Every upstream arrow already exists. New wiring is one server query helper + one optional `cds_fields` query helper + one server component + one client sub-component + one pure TS module + one static methodology page.

## Critical files

**New:**
- `web/src/lib/positioning.ts` — pure scoring functions + types (~150 LOC)
- `web/src/lib/positioning.test.ts` — vitest unit tests with 10 inline-fixture schools
- `web/src/components/PositioningCard.tsx` — server component
- `web/src/components/PositioningCardProfile.tsx` — `'use client'` component
- `web/src/app/methodology/positioning/page.tsx` — static SSR
- `web/tests/e2e/positioning-card.spec.ts` — Playwright e2e
- `tests/api/positioning_contract.sh` — PostgREST contract guard

**Modified:**
- `web/src/app/schools/[school_id]/page.tsx` (+5 lines, +1 import)
- `web/src/lib/queries.ts` (add `fetchBrowserRowBySchoolId` + `fetchAvgGpaBySchoolId` helpers, ~30 lines)
- `web/src/app/api/page.tsx` (add positioning endpoint reference)
- `docs/ARCHITECTURE.md` (note the new pipeline node)
- `docs/backlog.md` (track GPA scale-resolution sprint)

**Reused (do not rewrite):**
- `cds_artifacts.canonical_json` — extraction output already keyed to CDS questions
- `school_browser_rows` (PRD 012 migration `20260428120000_browser_academic_profile_fields.sql`) — SAT/ACT columns already present with range checks
- `cds_fields` — long-form substrate for the GPA soft-tiebreaker read
- `institution_cds_coverage` — coverage states for the staleness micro-copy
- Design tokens in `web/src/app/tokens.css`; `.cd-card`, `.rule-2`, `.cd-btn`, `.mono`, `.serif`, `.nums`

## Scoring function contract

```ts
// web/src/lib/positioning.ts
export type StudentProfile = {
  sat?: number;            // 400-1600
  act?: number;            // 1-36
  gpa?: number;            // 0.0-5.0 raw
  gpaScale?: 'unweighted_4' | 'weighted' | 'unknown';
};

export type SchoolAcademicProfile = {
  schoolId: string;
  schoolName: string;
  cdsYear: string;            // e.g. "2024-25"
  acceptanceRate: number | null;
  satSubmitRate: number | null;     // 0..1
  actSubmitRate: number | null;
  satCompositeP25: number | null;
  satCompositeP50: number | null;
  satCompositeP75: number | null;
  actCompositeP25: number | null;
  actCompositeP50: number | null;
  actCompositeP75: number | null;
  avgHsGpa: number | null;          // from cds_fields C.1201
  hsGpaSubmitRate: number | null;   // from cds_fields C.1202
  dataQualityFlag: string | null;
};

export type Tier =
  | 'likely' | 'strong_fit' | 'possible' | 'unlikely' | 'long_shot' | 'unknown';

export type Caveat =
  | 'no_sat_data' | 'no_act_data' | 'low_sat_submit_rate'
  | 'no_test_data' | 'stale_cds' | 'student_not_submitting'
  | 'data_incomplete' | 'sub_15_admit_rate_suppression';

export type PositionResult = {
  satPercentile: number | null;     // clamped to [5, 95] outside published anchors
  actPercentile: number | null;
  tier: Tier;
  caveats: Caveat[];
  cdsYear: string;
  positionalSentence: string;       // pre-rendered, ready to display
};

export function scorePosition(
  profile: StudentProfile,
  school: SchoolAcademicProfile,
): PositionResult;

export function interpolatePercentile(
  score: number,
  p25: number,
  p50: number,
  p75: number,
): number;  // piecewise-linear, clamped to [5, 95]

export function classifyTier(
  satPct: number | null,
  actPct: number | null,
  acceptanceRate: number | null,
): Tier;
```

Tier rubric (publishable, in methodology page):

- **Likely** — admit rate ≥ 50% AND scores at-or-above mid-50%.
- **Strong fit** — admit rate ≥ 25% AND scores in or above mid-50%.
- **Possible** — scores in mid-50%, admit rate 10–25%.
- **Unlikely** — scores below mid-50% OR admit rate < 10%.
- **Long shot** — scores below 25th AND admit rate < 25%, or admit rate < 10% regardless of scores.
- **Unknown** — caveat-suppressed (test-optional non-submitter, missing data, sub-15% admit + mid-50%).

## Failure modes

| # | Failure mode | Detection | Mitigation |
|---|---|---|---|
| 1 | Non-monotonic 25/50/75 (extraction error) | `p25 > p50 \|\| p50 > p75` in scorer | `satPercentile=null`, caveat `data_incomplete`, "range published, position not computable" microcopy |
| 2 | Test-optional + low submit rate | `satSubmitRate < threshold` | Pair every percentile with submit-rate caption; suppress percentile + emit `student_not_submitting` if profile has no SAT/ACT |
| 3 | SAT populated, ACT NULL (or vice versa) | per-test null check | Render only the populated bar; "ACT not reported in this CDS year" microcopy |
| 4 | Old CDS year with schema drift | gate on `year_start >= 2024` | Card hides if year_start < 2024; methodology page documents the floor |
| 5 | GPA scale ambiguity | per PRD 012 — held out of school_browser_rows | v1 does not score GPA percentile; soft tiebreaker only |
| 6 | Withdrawn school | `participation_status='withdrawn'` already filtered by `PUBLIC_EXCLUDED_STATUSES` (queries.ts:21) | Card never renders; defense-in-depth check in helper |
| 7 | localStorage profile schema versioning | versioned key `cdfyi.positioningProfile.v1` | Future v2 readers migrate forward; never break v1 |
| 8 | URL-encoded profile XSS | not in v1 (no URL deep-linking) | n/a until v2 |
| 9 | School with no `school_browser_rows` row | `fetchBrowserRowBySchoolId` returns null | Card returns null; existing page renders unaffected |
| 10 | Schema drift in `school_browser_rows` | CI contract test (`tests/api/positioning_contract.sh`) | Fails CI at PR time |
| 11 | `data_quality_flag='wrong_file'` row | check in card | Card hides itself |
| 12 | `acceptance_rate` NULL | tier classifier handles null | tier=`unknown`; percentile rendering still works |

## Verification

End-to-end test plan:

1. **Unit tests (vitest):** `cd web && npm run test`. 10 fixture schools spanning selectivity tiers + test-optional/required mix. Specifically test interpolation correctness, non-monotonic guard, test-optional caveat firing, and tier classification at boundaries.
2. **Component tests:** RTL snapshots for empty / loaded / ACT-NULL / test-optional / stale-CDS / wrong-file states.
3. **Contract test:** `bash tests/api/positioning_contract.sh` — fails CI if any column disappears from PostgREST.
4. **Playwright e2e:** load `/schools/university-of-maryland-college-park`, verify SAT bars render server-side (view-source check), enter SAT=1450, verify tier label + percentile, navigate to `/schools/mit`, verify profile auto-populates.
5. **Manual spot checks:** 5 named schools at PR-review time:
   - **Bowdoin** — test-optional, low submit rate. Verify caveat prominence.
   - **MIT** — test-required, ultra-selective. Most realistic profiles → `long_shot`.
   - **UMD** — mid-selectivity, test-optional, public. Methodology worked example.
   - **Cal Poly SLO** — public, residency-stratified in reality (card cannot reflect; methodology page calls this out).
   - **Howard** — HBCU, mid-selectivity, lower sample sizes. Stress-test edge cases.
6. **Build + lint:** `cd web && npm run build && npm run lint && npm run typecheck` clean.

## Coverage audit (parallel, non-blocking)

The card degrades gracefully when fields are missing for a given school, so this PRD does not gate ship on coverage. In parallel, run a coverage audit during the v1 month:

- Re-run `tools/browser_backend/project_browser_data.py --full-rebuild` weekly.
- Output a JSON report to `scratch/positioning-coverage/` listing schools where `sat_composite_p50` is null but a 2024-25+ CDS document exists, schools with non-monotonic percentiles, and schools where `act_submit_rate` looks implausible.
- Track on `docs/extraction-quality.md`. Feeds extraction-quality work; does not block PRD 016.

## Rollout plan

- **No feature flag.** Single PR. Blast radius is bounded to one page; rollback is the one-line revert of the slot insertion in `page.tsx`.
- **Post-ship telemetry:** basic page-view counter for `/methodology/positioning` and a no-PII counter for "profile entered" via Vercel analytics. Validates demand without saving anything.

## Open questions deferred to Claude Design

The full UX skeleton lives at `docs/design/positioning-card-skeleton.md`. Two open design questions explicitly left for the design pass:

- **D1.** SAT range strip geometry — hairline ticks at 25/50/75, filled bar between 25–75, or distribution sketch? Each carries a different precision implication.
- **D2.** Test-optional submitter-only caveat loudness — tight inline, card-level banner, or sticky? Tradeoff: visible vs. boilerplate-blindness when ~50% of the Top 200 fires the caveat.

## Effort

~1 week (1 person, CC+gstack pace). The original 2-3 week estimate collapsed once eng review confirmed PRD 012 already shipped the data layer.
