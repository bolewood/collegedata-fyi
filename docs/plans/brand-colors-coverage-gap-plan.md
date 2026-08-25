# Plan: closing brand-color coverage gaps for the school glyph feature

Written 2026-08-24. Context: a scouting effort (see `supabase/migrations/2026082*_seed_batch*.sql`
and `tools/brand-colors/`) just populated `institution_directory.brand_colors` for ~842 schools.
This plan covers what's left, verified against production at the time of writing — **re-run the
queries below before starting Phase 1, the counts move as scouting continues.**

## Implementation result (2026-08-25)

Phases 0 and 1 shipped in this branch. The eight reviewed batches record 204 sourced color
sets and 33 explicit null results across all 237 in-scope gaps. Alias-aware glyph lookup plus
three reviewed manual aliases reduce the unmatched identity bucket to the deliberately unresolved
Houston system-administration record. After the migrations are applied, projected `/schools`
coverage is 682 colored schools, 33 in-scope nulls, 9 out-of-scope nulls, and 1 unmatched record.
Phase 2 remains deferred because it requires a separate directory-scope decision.

## Current state (verified against production, 2026-08-24)

Of the **725 schools** visible on `/schools` (distinct `cds_manifest.school_id`, active
participation status, not removed):

| Bucket | Count |
|---|---|
| Already has `brand_colors` → renders a real glyph | **469** |
| `institution_directory` row exists, `in_scope=true`, `brand_colors IS NULL` | **237** |
| `institution_directory` row exists, `in_scope=false`, `brand_colors IS NULL` | **9** |
| No matching `institution_directory` row at all (identity mismatch) | **10** |

Confirmed via one atomic query (`469+237+9+10=725`).

**Callout — the 10 identity mismatches are not equally hard.** `institution_slug_crosswalk`
(alias → canonical `school_id`, already used by `fetchCanonicalSchoolId` for school-detail-page
redirects) **already contains correct aliases for 6 of the 10**:

| `cds_manifest.school_id` (alias) | → canonical `school_id` | has colors? |
|---|---|---|
| `caltech` | `california-institute-of-technology` | yes — `#FF6C0C` |
| `university-of-chicago` | `uchicago` | yes — `#800000` |
| `rutgers-university-new-brunswick` | `rutgers` | yes — `#CC0033,#000000,#FFFFFF` |
| `university-of-virginia-main-campus` | `uva` | yes — `#232D4B,#E57200` |
| `georgia-institute-of-technology-main-campus` | `georgia-tech` | no — still needs scouting |
| `university-of-washington-seattle-campus` | `uw` | no — still needs scouting |

Independently re-verified 2026-08-24: all 6 crosswalk rows exist exactly as listed
(`source` is `manual` for caltech, `scorecard` for the other 5); the 4 "yes" rows' colors are
confirmed live in `institution_directory`. **4 schools already have real, verified colors that
never display** — the bug is that `fetchBrandColorIndex()` in `web/src/lib/queries.ts` does a
plain `school_id` string match against `institution_directory` and never consults
`institution_slug_crosswalk`, even though a sibling function (`fetchCanonicalSchoolId`) already
reads from that same table for a different purpose (school-page URL redirects).

`cds_manifest.ipeds_id` is populated for 711/725 schools project-wide (only 14 blank overall) —
it just happens to be blank for 9 of these 10 specific mismatched rows. An IPEDS-ID fallback join
would be reasonable general hardening but would not, by itself, fix these 10.

The remaining 4 mismatches have no crosswalk row yet:
- `texas-a-and-m-university-college-station` → likely `texas-am` (name-obvious, needs a crosswalk row)
- `tulane-university` → likely `tulane-university-of-louisiana` (already has colors — name-obvious)
- `virginia-tech` → likely `virginia-polytechnic-institute-and-state-university` (name-obvious)
- `university-of-houston-system-administration` (IPEDS `229407`) → **does not correspond to any
  `institution_directory` row at all**; that IPEDS unit isn't a Title-IV in-scope institution.
  Needs a human to open the actual archived CDS document and confirm whether it reports
  University of Houston main-campus data before crosswalking it to UH's colors — don't assume.

## Phase 0 — the 10 identity mismatches (human sign-off required)

**Recommendation:** extend `fetchBrandColorIndex()` (and the `/schools` page's join generally) to
also resolve through `institution_slug_crosswalk` when no direct `school_id` match exists — the
same alias-resolution pattern already shipped for `fetchCanonicalSchoolId`. This requires **no
database identity changes** for 6 of the 10 cases; it's a pure code change plus a read of existing
data. For the 3 name-obvious remaining cases, add 3 new `institution_slug_crosswalk` rows
(`source='manual'`) pointing the `cds_manifest` slug at the existing canonical `school_id`. This is
additive, reviewable, and far lower-risk than renaming a primary key or touching `cds_manifest`.

For `university-of-houston-system-administration`: treat as its own from-scratch scouting target
unless a human confirms otherwise after reading the actual document. This is exactly the kind of
school-identity call this repo's root `CLAUDE.md` reserves for human review (run
`tools/finder/identity_guard.py` before writing generated data; migrations land only from `main`).

**Two options considered and rejected:**
- Renaming one side's primary key + adding a redirect entry — heavier, touches `cds_manifest`,
  more blast radius for no added benefit since the crosswalk table already exists.
- IPEDS-ID fallback matching in code alone — doesn't help here since 9/10 have blank
  `cds_manifest.ipeds_id`, though worth doing separately as defense-in-depth for the wider corpus.

**Size:** one small PR (crosswalk-aware join + up to 3 crosswalk rows), one human review pass for
the Houston case. Do not bundle into the scouting batches below.

## Phase 1 — the 237-school gap

Coverage-status breakdown of the 237: `cds_available_current` 112, `cds_available_stale` 70,
`cds_found_processing` 50, `extract_failed` 2, `no_public_cds_found` 2,
`latest_found_extract_failed_with_prior_available` 1.

**Crosswalk-coverable vs. from-scratch** (ran `tools/brand-colors/build_crosswalk.py` live against
current Wikipedia data + a fresh `institution_directory` export, intersected with the 237):
- **22 schools** have a genuinely usable (edu/other-cited) crosswalk lead — fastest path,
  verify-then-seed like the prior effort (e.g. Princeton, Bowdoin, Lafayette, Kentucky State,
  South Carolina State).
- **52 more** match an NCAA nickname but only via `trucolor.net` or an uncited Wikipedia entry —
  still need real from-scratch scouting of the school's own site; the crosswalk just confirms
  they're NCAA-affiliated.
- **163 schools** have no NCAA crosswalk match at all (community colleges, non-athletic
  institutions, or names the matcher's conservative tie-break rules correctly refused to guess) —
  pure from-scratch scouting, same as the prior effort's non-NCAA schools.

**Ordering:** `coverage_status = cds_available_current` first (most-visited, most likely a user
lands there today), then `cds_available_stale`, then `cds_found_processing`; within each tier, sort
by `undergraduate_enrollment` descending — matches the prior effort's implicit "biggest schools
first" pattern. Route the 22 usable-crosswalk schools first regardless of enrollment — they're
nearly free wins.

**Non-negotiables to carry forward** (from the batch migration notes — see
`supabase/migrations/2026082*_seed_batch*.sql` for worked examples):
- Never eyedrop; a hex must be explicitly printed as text (page, PDF text, or a rendered PDF page
  read directly — never a swatch fill color).
- No-neutral-append: don't tack white/black onto an already-complete chromatic pair — but a
  genuinely-labeled 3-color primary set is fine (e.g. Marshall, Brown, Ohio State all kept 3).
- Pantone-only sources (no literal hex/RGB on the school's own domain) are tier 4 (low confidence),
  not medium — converting via a third-party Pantone table doesn't count as "the school states it."
- Watch for wrong-swatch citation traps: a cited PDF/page section belonging to a *different*
  school (shared conference style guides are a repeat offender), or a secondary/athletics-only
  palette mislabeled as primary. This caught real errors in roughly a third to half of
  verifications in the prior effort — don't rubber-stamp candidates.
- Independently spot-verify a sample of each batch's migration against the live cited source
  before trusting it — this caught one fabricated citation and one confidence-tier
  miscalibration during the prior effort.

**Effort:** the prior 842-school effort ran 29 batches of ~30 schools each in a single day. At the
same cadence, 237 schools ≈ **8 batches of 30** (last one partial). The 22 crosswalk-fast-path
schools are batch 1; the rest follow enrollment/coverage order.

## Phase 2 — the 9 `in_scope=false` schools

`in_scope=false` here means excluded from `institution_directory`'s scope by a Scorecard-derived
filter (`exclusion_reason`), not "not a real school" — 8 of the 9 are `non_degree_predominant`, 1
is `no_undergraduate_enrollment`. All 9 have real archived CDS documents and appear on `/schools`
today (e.g. `front-range-community-college`, 11,476 undergrads; `utah-tech-university`, 8,552
undergrads). **Recommend skip** for this pass — fixing them means revisiting the directory
pipeline's scope criteria, a separate decision from color scouting, not something to fold into
this effort.

## Summary sizing

- **Phase 0:** 1 small code PR (crosswalk-aware `fetchBrandColorIndex()` join) + up to 3
  crosswalk rows, human-reviewed, not batched. Surfaces 4 already-scouted schools immediately.
- **Phase 1:** ~8 batches of 30, crosswalk-fast-path batch first, then
  enrollment/coverage-status order.
- **Phase 2:** no action this round.
