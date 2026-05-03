# PRD 018: Open college fit data — merit-aid + Scorecard intelligence (v3)

**Status:** Product slice in progress. H2A extraction-quality sprint complete; targeted Tier 4 redrain moved direct first-year institutional non-need grant aid coverage to 66.8%, and the public `school_merit_profile` contract is being added as a latest-primary-CDS view with explicit caveats.
**Created:** 2026-05-01
**Author:** Anthony + Claude (autoplan)
**Related:** [PRD 016](016-academic-positioning-card.md), [PRD 017](017-match-list-builder.md), [PRD 010](010-queryable-data-browser.md), [PRD 012](012-browser-field-expansion-after-v03.md), [Scorecard pipeline](../../tools/scorecard/README.md), [autoplan record](../../.claude/plans/system-instruction-you-are-working-starry-candle.md)

---

## Context

The autoplan strategic review surfaced a load-bearing observation: **academic positioning is the commodity surface in this category, not the defensible one.** Several paid college-planning platforms compete on positioning + merit + cost together, and the recurring revenue in those products is mostly tied to the financial intelligence layer (predicted aid, award comparison, net-cost transparency), not the positioning layer alone. Several free entrants in the space already ship positioning without source links. Where this project has a real advantage is the open archive of source-linked CDS extracts — and the higher-leverage application of that asset is **open, source-linked, machine-queryable college fit data** spanning academics, aid, and outcomes.

This PRD scopes that data asset.

## Why this might leapfrog PRD 017

If counselor adoption of PRD 016 is weak but the public API gets used by other tool builders — measured by the "give 5 tool builders the endpoint and see if they build" test — the right move is to skip the v2 microsite and go straight to merit-aid as the next data asset. The microsite competes where category incumbents are strongest (destination match/chance UIs); the data asset competes where this project's actual advantage is (open archive of source-linked extracts).

Decision tree at activation time, copied from PRD 017:

- PRD 016 has demand + tool-builder API adoption is weak → build PRD 017 (microsite).
- PRD 016 has demand + tool-builder API adoption is strong → skip PRD 017, build PRD 018.
- Both signals strong → build both, in parallel if budget allows, sequenced otherwise.
- Neither signal → stop and revisit the audience hypothesis.

## What ships (when activated)

### `school_merit_profile` denormalized view

A new Postgres view (or materialized table, if performance demands) on top of `cds_artifacts.canonical_json` aggregating CDS section H fields per school per year:

- **H1** — average annual freshman financial aid package
- **H2** — number receiving aid
- **H5** — average need-based scholarship/grant aid
- **H6** — average need-based self-help aid
- **H7** — average non-need-based scholarship/grant aid (the "merit" number)
- **H8** — average institutional grants

Plus, joined from `scorecard_summary`:

- Net-price-by-income-bracket (5 brackets: $0-30k, $30-48k, $48-75k, $75-110k, $110k+)
- Median federal debt at graduation
- Median debt monthly payment
- 6-year graduation rate
- Median earnings 6/8/10 years post-enrollment
- Pell share

The view exposes a single row per latest primary 2024-25+ school with both the CDS-derived merit numbers and the federal Scorecard outcome data side-by-side. This is the same pattern PRD 012's `school_browser_rows` follows for academic profile, applied to financial fit.

Implementation note: v1 is a SQL view over `cds_fields` plus `school_browser_rows` and `scorecard_summary`, not a separate projection worker. That keeps the contract easy to review and automatically benefits from future extraction re-drains.

### Public PostgREST endpoint + documentation

Same pattern as PRD 016's API documentation:

- `school_merit_profile` exposed read-only via PostgREST at `api.collegedata.fyi/rest/v1/school_merit_profile`.
- Methodology page at `/methodology/merit-profile` with worked examples.
- Curl examples + a Google Sheets template that pulls live from the API. The Sheets template is the lightest counselor-facing surface possible — it costs us 1 day of doc work and gives counselors a tool they can use today without us building any UI.

### Static "fit profile" pages per school

Lightweight UI: `/schools/[school_id]/fit` (or merge into the existing school detail page if the surface area stays small). Shows the academic + merit data side-by-side:

- Section 1: PRD 016's positioning card (academic fit).
- Section 2: merit profile — average non-need aid, % receiving, distribution if available.
- Section 3: net-price-by-income-bracket chart, with the user's family income (if entered) highlighting the relevant bracket.
- Section 4: outcomes — 6-year graduation, median earnings, median debt.

The focus is on the data layer being machine-queryable. The UI is a thin presentation; if a third party builds a better one, they should be able to.

### Methodology page extension

`/methodology/merit-profile`:

- "What is need-based vs non-need-based aid?" — plain-English explainer.
- "How does net price by income work?" — Scorecard's IRS-derived methodology, linked to ED's documentation.
- "Why do CDS H values vary so much across schools?" — practical guide to interpreting reported numbers.
- "What we don't capture" — outside scholarships, year-to-year aid changes, special-circumstance appeals, etc.

## Open question — extraction quality on CDS section H

**This is the critical pre-condition.** PRD 012's phase-0 audit measured C.9, C.11, C.12 (academic profile). Section H (financial aid) was not measured. The v3 scoping spike (1 week, before any v3 PRD work) must establish:

1. Section H field-by-field answerability across the latest 365 schools.
2. Which H fields are reliably extracted vs which the Tier 4 cleaner mangles.
3. Whether the LLM fallback (PRD 006) covers H gaps reliably enough to ship.
4. Coverage by selectivity tier — top 100 vs full corpus.

If H extraction quality is below ~60%, prioritize an H-section extraction sprint before building the data asset. Otherwise the merit profile will look more precise than the data supports — the same trap PRD 016 deliberately avoided.

## What does NOT ship

- **No merit prediction.** Some commercial tools in this space promise "what you might receive" as a personalized estimate. We promise "what this school reported giving on average," based on published CDS values. Different question, much smaller legal exposure, much easier to defend.
- **No appeal-letter generation.** Generating appeal letters tuned to a specific student's case is a separate product surface. Out of scope for v3; revisit if counselor demand pulls.
- **No financial-need calculator.** FAFSA / EFC calculation is a separate, complex domain. Link to authoritative public tools (e.g. the federal Net Price Calculator on each school's site).
- **No school-vs-school side-by-side comparison view in v3.** That's a v4 product surface.
- **No third-party tracking pixels or affiliate links.** Methodology page may link to public, authoritative resources for FAFSA help; no monetization.

## Architecture (sketch)

```
[arrows marked * already exist; arrow ! is new]

cds_artifacts (canonical_json)
   |  *  tools/browser_backend/project_browser_data.py
   v
cds_fields                                 <-- read for H-section fields
   |  !  new aggregation: tools/merit_backend/project_merit_data.py
   v
school_merit_profile                       <-- NEW denormalized view
   |  *  PostgREST
   |
scorecard_summary                          <-- already populated by tools/scorecard/refresh_summary.py
   |  *  joined into school_merit_profile via UNITID
   v
school_merit_profile (final)
   |  *  PostgREST
   v
   +- !  /schools/[id]/fit                 <-- NEW thin UI
   +- !  Google Sheets template            <-- NEW doc artifact
   +- *  third-party tools build their own UIs against the API
```

The pattern is identical to PRD 010 / 012 — a denormalized view on top of `cds_fields` plus Scorecard, served via PostgREST, documented, with thin UI on top.

## Critical files (when implementation begins)

This is illustrative; re-scope at activation.

**New:**
- `supabase/migrations/<ts>_school_merit_profile.sql` — view or materialized table
- `web/src/app/methodology/merit-profile/page.tsx` — methodology
- `web/src/app/schools/[school_id]/page.tsx` — thin existing-page section
- `web/src/components/MeritProfileCard.tsx` — visual
- `tools/sheets/merit-profile-template.csv` — Google Sheets template seed
- `docs/prd/018-open-college-fit-data.md` — this file, expanded

**Modified:**
- `docs/ARCHITECTURE.md` — note the new pipeline node
- `web/src/app/api/page.tsx` — document the new endpoint

**Reused:**
- `cds_artifacts.canonical_json` — H-section data already extracted by tier1/tier2/tier4/tier4_llm_fallback
- `scorecard_summary` — net-price-by-income, earnings, debt all already populated
- `school_browser_rows` — for the academic-fit join on the per-school fit page

## Failure modes (deferred)

- **H-section extraction quality is low.** Discovered by the scoping spike. Mitigation: H extraction sprint before v3 build.
- **CDS H values are reported on different scales across schools.** Some schools report aid as a fraction, some as dollars, some include institutional vs federal aid differently. Methodology page must call this out by name. The denormalized view normalizes where possible and flags where not.
- **Net-price calculator embeds.** Some schools' NPCs are linked from CDS section H; we can surface those links but cannot embed them (TOS varies per school).
- **Student-PII risk on a calculator surface.** If we ever add an income input, that's PII-adjacent. Default in v3: no income input; show all 5 brackets and let the user identify their own.

## Verification (deferred)

To be filled in at activation time. Sketch:

1. The scoping spike completes and reports H-section answerability.
2. `school_merit_profile` returns latest primary rows for the browser corpus with >60% core H-section answerability.
3. PostgREST endpoint returns expected shapes; contract test passes.
4. Google Sheets template imports the API correctly via `IMPORTDATA()`.
5. Manual spot checks: 5 schools across selectivity (Bowdoin, MIT, UMD, Texas A&M, Berea) — verify the merit profile matches the published CDS PDF.

## Effort estimate

4-8 weeks at the high end if H extraction quality is poor and we need a sprint first. 2-3 weeks if H extraction is already solid (likely for the schools where Tier 1 XLSX extraction or Tier 2 fillable PDF extraction worked — those producers tend to capture H reliably).

## Why this PRD is "deferred" not "cancelled"

The autoplan review's strongest claim was that this is the actual moat. We're shipping PRD 016 first because it's smaller and more defensible. PRD 018 stays defined and reviewable so:

1. Future contributors can see the full direction without re-deriving it.
2. If PRD 017 fails to activate (counselor signal weak), this PRD is the alternative next move.
3. If a contributor wants to drive H-extraction quality, they have a target use case to optimize for.
4. If a category incumbent expands a free tier to undercut PRD 016, this PRD is the response.

Don't let PRD 018 rot. Re-evaluate quarterly against PRD 016 telemetry.
