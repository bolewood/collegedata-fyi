# PRD 016B: Admission strategy card — round-stratified ED admit rate, yield, wait-list, and admission factors (v1)

**Status:** Shipped 2026-05-03. Phase 0 gate passed, C21/C22 Tier 4 cleanup and targeted redrain shipped, `school_browser_rows` admission-strategy columns are live, and `AdmissionStrategyCard` is on school pages with ED/EA names and quality gating.
**Created:** 2026-05-02
**Author:** Anthony + Claude
**Related:** [PRD 010](010-queryable-data-browser.md), [PRD 012](012-browser-field-expansion-after-v03.md), [PRD 015](015-institution-directory-and-cds-coverage.md), [PRD 016](016-academic-positioning-card.md), [PRD 017](017-match-list-builder.md) (deferred), [PRD 018](018-open-college-fit-data.md) (deferred)

---

## Context

The single "admit rate" published in college guides and chance-me tools is a weighted average across application rounds whose actual odds differ by 3–5x. A school that publishes "8% admit rate" might be running roughly 25% Early Decision and 5% non-early in practice. That single headline number obscures the structural reality of the admissions market and disadvantages applicants who don't have access to a counselor who explains it.

The Common Data Set publishes part of the round-stratified data needed to surface this honestly. Section **C.21 (Early Decision)** publishes ED applicant and admit counts. Section **C.22 (Early Action)** publishes only an EA-offered flag and a restrictive-EA flag — **not** EA applicant or admit counts. Section **C.2 (Wait List)** publishes wait-list activity. Section **C.7** publishes the importance schools assign to each admission factor (demonstrated interest, legacy, first-generation, etc.).

This PRD ships an **admission strategy card** on `/schools/[school_id]` exposing what the CDS actually publishes, honestly framed, with a Phase 0 measurement gate before any migration ships:

1. **ED admit rate** (where data is present and extraction is verified)
2. **Whether EA is offered** and whether it is restrictive — *no EA rate, because the CDS does not publish the underlying counts*
3. **A "non-early residual" admit rate** (clearly labeled as not-quite-RD)
4. **A "second-binding-round-offered" signal** for ED-2 schools, derived from "other ED" deadline fields
5. **Yield rate** with both interpretations explicit (top-choice signal *or* yield protection)
6. **Wait-list activity** including the conditional rate (admitted-off / accepted-off)
7. **C.7 admission factor importance** for legacy, first-gen, demonstrated interest — already in `cds_fields`
8. Each number linked to the source CDS question and PDF

This is the natural companion to PRD 016's positioning card. PRD 016 answers *"where would I fit?"*; this PRD answers *"how does this school admit people, and what does that mean for how I should apply?"*

### Why we are rewriting from v1.0 → v1 (the ratchet)

A dual-voice adversarial review on 2026-05-02 caught the following load-bearing errors in the first draft and shaped this version:

- The CDS does not publish EA application/admit counts (the schema verifies this).
- ED counts at `C.2110` / `C.2111` (2025-26) and `C.2106` / `C.2107` (2024-25) are *not* currently extracted by Tier 4 — Tier 4 today extracts only `C.2101`, `C.2201`, and `C.2206` (verified at `tools/extraction_worker/tier4_cleaner.py:2918`). The "data is already extracted" assumption is materially false. We need to build the resolver.
- "RD admit rate" computed as `(c1_admitted − ed_admitted) / (c1_applicants − ed_applicants)` is not regular-decision admit rate — deferred-from-ED applicants get reviewed in the RD pool, so this is a "non-early residual," not RD.
- The recruited-athlete bias on ED rates at selective schools is large enough (NBER's research on the Harvard ALDC pipeline puts athlete admits alone at ~10% of admitted-class share, with admit rates near 100%) that an inline caveat is banner-blindness. Disclosure must be visually load-bearing.

This v1 fixes all four. It also adds a Phase 0 measurement gate matching the precedent set by [PRD 012](012-browser-field-expansion-after-v03.md), which deliberately blocked schema migration on answerability measurement.

## Phase 0 — measurement gate (mandatory before migration)

This PRD is **not approved for schema migration** until Phase 0 completes and the results are written back into this PRD or a sibling findings note at `docs/plans/prd-016b-phase-0-findings.md`.

### 0.1 Build the Tier 4 ED-count resolver

`tier4_cleaner.py` currently surfaces only `C.2101`/`C.2201`/`C.2206` for the C.21/C.22 block (the plan-offered booleans + restrictive flag). We need to extend the existing Section C.21 resolver to extract ED applicant and admit counts at `C.2110` and `C.2111` for the 2025-26 schema and `C.2106`/`C.2107` for the 2024-25 schema. The wait-list resolver at `tier4_cleaner.py:2027` is the right shape to mirror.

This is real extraction work, not a projection extension. Tier 1 (XLSX) already pulls these fields correctly via the cell-position map. Tier 2 (acroform) likely does too on the schools where the form is fillable. Tier 4 (flattened-PDF Docling) is the gap.

### 0.2 Run the answerability audit

Across the latest-clean 2024-25+ schools in `school_browser_rows`, project ED counts via the new resolver and report:

- ED count answerability per producer (tier1_xlsx, tier2_acroform, tier4_docling, tier4_llm_fallback) — counts and percentages.
- Distribution of populated `ed_offered=true` vs `ed_offered=false`.
- Distribution of `ed_has_second_deadline=true` (derived from non-null "other ED" deadline fields — `C.2106`/`C.2107` in 2025-26 schema, `C.2103`/`C.2104` or equivalent in 2024-25; verify exact field IDs against `schemas/cds_schema_*.json`).
- Distribution of `(ed_admitted + ea_implied) / c1_admitted` *if* a meaningful estimate of EA-implied is reachable (likely no — drop unless the audit reveals a path).
- Top 200 selectivity-weighted schools answerability (by `c1_applicants` desc) — the schools where the card matters most.
- Verifier-rejection rate: how often does `ed_admitted > ed_applicants` or `ed_admitted > c1_admitted` fire?

### 0.3 Decide threshold and scope

Three decisions must be settled by Phase 0 findings, not assumed:

1. **Card eligibility floor.** What's the minimum ED-count answerability for a school's card to render the ED rate? Default candidate: 70% of selectivity-weighted top 200, mirroring PRD 012's gate. Phase 0 reports the actual number.
2. **Class-composition emphasis threshold.** A "loud" visual signal fires when `(ed_admitted + ea_implied_lower_bound) / c1_admitted` exceeds some threshold. Codex review noted the original 50% choice was design noise, not data-grounded. Phase 0 computes the corpus distribution; threshold is set at the natural elbow (likely the 75th percentile of corpus-wide early share). Without a measurable EA component, this signal is "ED share of admits" — narrower but cleaner.
3. **Verifier policy.** Phase 0 quantifies how often the verifier would reject; if the rejection rate is above ~5%, the verifier suppresses the *card*, not the *document*, so we don't poison unrelated surfaces. See §"Verifier mechanism" below.

Phase 0 is approximately **3–5 days** of work and gates the schema migration. PRD 012 set this precedent and is the right pattern.

## What ships in v1

After Phase 0 completes and clears its gates: a server-rendered card on `/schools/[school_id]` placed below the positioning card and above `<OutcomesSection>`. Internally referenced as the *admission strategy card*; user-facing name TBD at design time.

### Card behavior

- **Server-renders** the round breakdown for the latest available CDS year. No profile entry; no client-side state. The card is data-only.
- **ED admit rate** (single rate, not three) — `ed_admitted / ed_applicants` when school offers ED *and* extraction is verified for that school. Adjacent to the rate, a visually load-bearing block-style caveat about recruited-athlete and legacy bias (see "Caveats" below). At schools with overall admit rate < 15%, the published ED rate is rendered with reduced visual emphasis and the caveat block is full-width adjacent — *not* a footnote.
- **Non-early residual admit rate** — `(c1_admitted − ed_admitted) / (c1_applicants − ed_applicants)`, **labeled as such**. Methodology page explains: this is not "regular decision admit rate" because deferred-from-ED applicants get reviewed in the RD pool, and EA-pool applicants (which the CDS does not publish) are also folded in. The name on the card is "Non-early-round residual" or similar.
- **Class composition signal** — a single sentence: *"At this school, X% of admitted students entered via Early Decision."* Threshold for "loud emphasis" set by Phase 0 corpus measurement, not assumed. Computed from `ed_admitted / c1_admitted` only — not `(ed_admitted + ea_admitted) / c1_admitted` because ea_admitted is not available.
- **EA offered flag.** A factual "this school offers Early Action" or "...Restrictive Early Action" or "...Single-Choice Early Action" line, with no rate. The methodology page explains *why* — the CDS does not publish EA applicant/admit counts.
- **ED-2 detection.** When the "other ED" deadline fields are populated, render a small inline note: *"This school also runs a second binding round (often called ED-2). The ED rate above is blended across both rounds."* Detection is derived from the schema, not inferred.
- **Yield rate** — already in `school_browser_rows`. The plain-English gloss surfaces *both* interpretations honestly: *"X% of admitted students enrolled. High yield can mean a school admits applicants who treat it as a top choice, or it can mean the school predicts demonstrated interest carefully and yield-protects against overqualified applicants who look unlikely to enroll. Cross-link: this school marks demonstrated interest as ____."*
- **Wait-list activity** — three raw counts (offered, accepted, admitted-off) *plus* two computed rates: wait-list offer rate (`offered / applicants`) and conditional admit rate (`admitted_off / accepted`). Methodology page documents that year-to-year wait-list admits are noisy — treat the conditional rate as a rough range, not a precise number.
- **C.7 admission factors block.** A small section showing *"This school weighs..."* with the factors marked "Important" or "Very Important" in C.7 — specifically:
  - C.711 (First-generation status)
  - C.712 (Alumni/ae relation — legacy)
  - C.718 (Level of applicant's interest — demonstrated interest)
  - C.713 (Geographical residence)
  - C.717 (State residency)
  - Plus: a callout when demonstrated interest is "Important" or "Very Important" — that is the yield-protection signal made explicit.
- **Application fee + waiver** (one-line block): from `C.1301`/`C.1302`/`C.1305`. *"Application fee: $90, waivers available online."* Operational input for an applicant strategizing across schools.
- **Mandatory caveats**, inline (not buried), in every applicable state:
  - **Recruited-athlete and legacy bias.** Block-style adjacent caveat at the ED rate. Copy: *"ED admit rates include recruited athletes (often 5–15% of admitted-class share at highly selective schools, admitted at near-100% rates) and legacy / institutional-priority applicants. Non-recruited general-pool ED admit rates are typically lower than the published number — sometimes substantially."* Methodology page links to NBER and academic research.
  - **ED-1 / ED-2 blending.** Inline when `ed_has_second_deadline=true`, see above.
  - **Deferred-from-early.** One-line: *"Some applicants deferred from ED are admitted in the non-early round. Both numbers reflect that overlap."*
  - **CDS year**, with the existing `<CoverageBadge>` for staleness signal.
- **Graceful degradation.** Card hides itself entirely when:
  - School has no row in `school_browser_rows`
  - ED rate is unavailable AND yield is unavailable AND wait-list is unavailable AND no C.7 factors are marked "Important" or "Very Important" (i.e. the card has nothing to say)
  - Per-card quality flag is set (see "Verifier mechanism" below)
  - `data_quality_flag IN ('wrong_file', 'blank_template', 'low_coverage')` on the document itself
- **Source link footer:** `§ SOURCE: COMMON DATA SET YYYY–YY · §C.21 §C.22 §C.2 §C.7 §C.13 · ARCHIVED PDF →` matching the PRD 016 footer pattern.

### Methodology page

New page at `/methodology/admission-strategy` (sibling to `/methodology/positioning`). Anatomy:

- **Lede:** *"The headline 'admit rate' you see in most college guides is a weighted average across application rounds whose actual odds differ by 3–5x. This page explains what we surface, what the numbers mean, and what they don't."*
- **What we use:** subsection per CDS field family (C.1, C.2, C.21, C.22, C.7, C.13), each with the specific use, a worked example, and a link to a real archived PDF.
- **Why we don't show an EA admit rate.** Plain-English: the CDS publishes whether a school offers EA and whether it is restrictive, but does not publish per-round application or admit counts for EA the way it does for ED. Any "EA admit rate" you see on a competitor site is sourced from a school's own press release or a non-canonical data point, not the CDS.
- **Why "non-early residual" instead of "regular decision."** Deferred-from-ED applicants get re-reviewed in the non-early pool. Schools with EA also pool those applicants in non-early review. The number we publish is honest: it's the residual after subtracting ED, not the actual RD slate.
- **The recruited-athlete and legacy reality.** Reference to NBER paper on Harvard's ALDC pipeline ([NBER w26316](https://www.nber.org/papers/w26316)). Sensitivity worked example: a school with published 25% ED rate and ~10% of admits being recruited athletes admitted at ~95% — the non-recruit ED rate is ~22%. At schools with stronger ALDC weight, the gap can be 8–12 points. We do not estimate non-recruit ED rates in v1 (deferred to a future v1.5 build that joins IPEDS Athletics / EADA data on UNITID).
- **The "ED-1 / ED-2" reality.** CDS reports a single combined `C.2110`/`C.2111` figure. Schools running both rounds — examples: Vanderbilt, WashU, Emory, Tufts, NYU, Johns Hopkins, Boston College, Tulane, UChicago, Wake Forest, plus many liberal arts colleges — have meaningfully different round dynamics that this number blends. We surface the existence of the second round but do not disaggregate counts.
- **Yield, both readings.** Three paragraphs explaining yield as both a "school is desired" signal and a "school yield-protects" signal, with C.7 demonstrated-interest as the bridge between the two readings.
- **Wait-list interpretation.** Year-to-year noise. The conditional rate (admitted-off / accepted) is the actionable number; the offer rate (offered / applicants) is the "how broad is their hedge" number.
- **The lawsuit context.** *"Early Decision is presented by schools as a binding commitment. The legal effect and competitive constraints around ED are disputed in pending litigation: D'Amico v. Consortium on Financing Higher Education was filed 2025-08-08 and is pending in the District of Massachusetts. We take no legal position on the case; the methodology page links to the public docket and to mainstream news coverage so readers can audit the framing themselves."* Links: [Justia docket](https://dockets.justia.com/docket/massachusetts/madce/1%3A2025cv12221/287691), one mainstream news source.
- **What we don't capture:** likely letters (informal advance-admission notices), athletic recruiting decisions at the granularity that would matter, ED-2 / ED-zero / ED-3 round disaggregation, "Restrictive EA" vs "Single-Choice EA" granular policy variants beyond the binary `ea_restrictive` flag, per-major / per-program admit rates, deferral-vs-rejection breakdown for ED applicants.
- **Sources and audit trail** — every claim links to a CDS question number; the worked-example school's PDF is linked from the archive.

## What does NOT ship

- **No EA admit rate.** The CDS does not publish the underlying counts. Any tool that publishes one is using non-canonical data.
- **No "RD admit rate" labeled as such.** The non-early residual is what we can compute honestly. Methodology page explains.
- **No "ED budget" list-builder UI.** That's the reframed PRD 017 surface. This PRD is per-school card only.
- **No yield-protection scoring** as a numeric flag. The dual-reading framing of yield + the C.7 demonstrated-interest cross-link is the v1 surface. (Future PRD 016 v1.1 may add a `'yield_protection_risk'` flag to the positioning scorer.)
- **No likely-letter tracker.** Not in CDS; out of scope.
- **No counselor saved profiles, no exports, no PDF generation.** Same as PRD 016.
- **No ED-2 / ED-zero / ED-3 disaggregation.** Schema doesn't publish round sub-divisions; we surface "ED-2 offered" only.
- **No major-level admit rates.** Not in CDS.
- **No application-strategy *recommendations*.** This card surfaces data; it doesn't tell the user where to apply ED.
- **No new public API resource.** PostgREST already serves `school_browser_rows`; we're adding columns, not endpoints.
- **No IPEDS Athletics non-recruit estimate in v1.** Deferred to v1.5 future-work item.
- **No `data_quality_flag` enum extension.** That column is a free-text tag at the document level, not an enum, and using it for card-level invalidation is the wrong mechanism. See "Verifier mechanism" below.

## Architecture

```
[arrows marked * already exist; arrows ! are new]

CDS PDF / XLSX (school IR site)
   |  *  discovery + mirror
   v
cds_documents + Storage archive
   |  *  tools/extraction_worker/  (tier1/2/4/4_llm/6)
   v
cds_artifacts (notes.values keyed to canonical question numbers)
   |
   |  !  EXTEND tier4_cleaner.py with C.21 count resolver         [NEW: §0.1]
   |  *  tools/browser_backend/project_browser_data.py
   v
cds_fields                                 <-- C.21, C.2, C.7, C.13 long-form here
   |
   |  !  extend project_browser_data.py to project new columns
   v
school_browser_rows                        <-- !  add ed_*, wait_list_*, ed_has_second_deadline,
   |                                              c7_*_factor_importance, app_fee_*,
   |                                              admission_strategy_card_quality columns
   |  *  PostgREST (api.collegedata.fyi)
   v
   +-- *  /browse  (existing)
   |
   +-- !  fetchAdmissionStrategyBySchoolId(school_id)        [NEW: 1 cached query]
            |
            v
        web/src/app/schools/[school_id]/page.tsx
            |
            v
        <AdmissionStrategyCard> (RSC)                        [NEW]
            |
            +- ED rate block (with mandatory recruited-athlete caveat block-adjacent)
            +- Non-early residual rate
            +- ED share of admits + class composition signal
            +- EA offered + restrictive flags (no rate)
            +- ED-2 inline note when ed_has_second_deadline
            +- Yield, both-readings gloss
            +- Wait-list block (raw counts + conditional rate + offer rate)
            +- C.7 admission factors block (importance flags only)
            +- App fee + waiver block
            +- Source-link footer
```

The Tier 4 resolver build (§0.1) is the load-bearing precondition. Migration follows; UI follows after.

## New columns on `school_browser_rows`

After Phase 0 completes and clears its gates, the migration adds these columns. Naming follows PRD 012's pattern (snake_case, with `_offered` / `_applicants` / `_admitted` / `_rate` postfixes where applicable). All new numeric columns get range-check constraints.

| Column | Type | Source | Notes |
|---|---|---|---|
| `ed_offered` | `boolean` | `C.2101` (already extracted) | True/False/NULL |
| `ed_applicants` | `integer` | `C.2110` (2025-26) / `C.2106` (2024-25) | Range check ≥ 0; per-schema field map |
| `ed_admitted` | `integer` | `C.2111` (2025-26) / `C.2107` (2024-25) | Range check 0 ≤ admitted ≤ applicants |
| `ed_has_second_deadline` | `boolean` | derived from non-null "other ED" deadline fields | Surface the ED-2 signal without claiming separate counts |
| `ea_offered` | `boolean` | `C.2201` (already extracted) | |
| `ea_restrictive` | `boolean` | `C.2206` (already extracted) | True for REA / SCEA |
| `wait_list_policy` | `boolean` | `C.201` | "Does this school have a wait list policy?" |
| `wait_list_offered` | `integer` | `C.202` | Range check ≥ 0 |
| `wait_list_accepted` | `integer` | `C.203` | Range check 0 ≤ accepted ≤ offered |
| `wait_list_admitted` | `integer` | `C.204` | Range check 0 ≤ admitted ≤ accepted |
| `c711_first_gen_factor` | `text` | `C.711` (already extracted) | Enum: 'Very Important' / 'Important' / 'Considered' / 'Not Considered' |
| `c712_legacy_factor` | `text` | `C.712` (already extracted) | Same enum |
| `c718_demonstrated_interest_factor` | `text` | `C.718` (already extracted) | Same enum |
| `c717_state_residency_factor` | `text` | `C.717` (already extracted) | Same enum |
| `app_fee_amount` | `integer` | `C.1302` (already extracted) | USD |
| `app_fee_waiver_offered` | `boolean` | `C.1305` (already extracted) | |
| `admission_strategy_card_quality` | `text` | computed at projection time | Enum: 'ok' / 'ed_math_inconsistent' / 'wait_list_math_inconsistent' / 'insufficient_data' |

**Computed in TypeScript serving layer (not stored):**

- `edAdmitRate = ed_admitted / ed_applicants` (null when `ed_offered != true` or applicants is null/zero)
- `nonEarlyResidualAdmitRate = (c1_admitted - (ed_admitted ?? 0)) / (c1_applicants - (ed_applicants ?? 0))` (null when computation is non-meaningful)
- `edShareOfAdmitted = ed_admitted / c1_admitted`
- `waitListConditionalAdmitRate = wait_list_admitted / wait_list_accepted` (null when accepted is null/zero)
- `waitListOfferRate = wait_list_offered / c1_applicants`
- `appFeeWaiverAvailable = app_fee_waiver_offered === true`

Per-schema field-ID mappings live in `tools/browser_backend/project_browser_data.py` alongside the existing `applied`/`admitted` mappings (see [project_browser_data.py:156](../../tools/browser_backend/project_browser_data.py)). The RPC insert contract in `supabase/migrations/20260428190000_canonical_field_equivalence.sql` must be updated alongside.

## Verifier mechanism (replaces document-level `data_quality_flag`)

The first draft of this PRD proposed extending `data_quality_flag` with an `'admission_strategy_invalid'` value. Adversarial review caught the error: `data_quality_flag` is a free-text column at the *document* level (`cds_documents`, [migration:7](../../supabase/migrations/20260418120000_data_quality_flag.sql)). Marking a whole document invalid because one card's math doesn't add up would suppress unrelated surfaces.

This PRD instead introduces a **card-specific quality column on `school_browser_rows`** named `admission_strategy_card_quality`. Values:

- `'ok'` — math is consistent, card renders normally.
- `'ed_math_inconsistent'` — `ed_admitted > ed_applicants` OR `ed_admitted > c1_admitted`. Card renders other blocks (yield, wait-list, C.7 factors, EA flags, ED-2 detection, app fee) but suppresses the ED rate block with a one-line note: *"ED counts for this school could not be reconciled and have been omitted. Other admissions data below."*
- `'wait_list_math_inconsistent'` — `wait_list_accepted > wait_list_offered` OR `wait_list_admitted > wait_list_accepted`. Wait-list block suppressed with a note; everything else renders.
- `'insufficient_data'` — none of (ED rate, yield, wait-list, C.7 factors marked ≥ Important, app fee) are computable. Card hides itself entirely.

This is the right granularity: the card decides whether its own components are presentable, and unrelated downstream surfaces are unaffected.

## Critical files

**New:**
- `supabase/migrations/<ts>_admission_strategy_columns.sql` — adds the columns above with range checks and the `admission_strategy_card_quality` column
- `tools/extraction_worker/tier4_cleaner.py` — extend the C.21 resolver to extract `C.2110`/`C.2111` (2025-26) and `C.2106`/`C.2107` (2024-25), plus the "other ED" deadline fields needed to derive `ed_has_second_deadline`
- `tools/extraction_worker/test_tier4_cleaner.py` — fixture-based unit tests for the new resolver
- `web/src/lib/admission-strategy.ts` — pure-TS computation of derived rates from raw counts + card-quality interpretation
- `web/src/lib/admission-strategy.test.ts` — vitest unit tests with 8–10 fixture schools (see Verification §)
- `web/src/components/AdmissionStrategyCard.tsx` — server component
- `web/src/app/methodology/admission-strategy/page.tsx` — methodology, static SSR
- `tests/api/admission_strategy_contract.sh` — PostgREST contract guard
- `docs/plans/prd-016b-phase-0-findings.md` — written during Phase 0; preserves the answerability data and threshold decisions for posterity

**Modified:**
- `tools/browser_backend/project_browser_data.py` — add per-schema field mappings for the new columns, populate from `cds_fields`, compute `admission_strategy_card_quality` at projection time
- `supabase/migrations/20260428190000_canonical_field_equivalence.sql` — extend the RPC insert contract to include the new columns
- `supabase/functions/browser-search/index.ts` — extend the row contract; `/browse` UI doesn't need to filter on these in v1, but the columns travel with the row regardless
- `web/src/lib/queries.ts` — add `fetchAdmissionStrategyBySchoolId` helper or extend the existing PRD 016 fetch to include the new columns
- `web/src/app/schools/[school_id]/page.tsx` — slot the card. **Card placement is an open design question** (see "Open questions"); default to placing it between `<PositioningCard>` and `<OutcomesSection>` pending the design pass.
- `docs/ARCHITECTURE.md` — note the new pipeline node and the Tier 4 resolver extension
- `web/src/app/api/page.tsx` — describe the new fields

**Reused:**
- `cds_artifacts.notes.values` — extraction output keyed to canonical question numbers (this is the actual source — not `canonical_json`, contrary to a wording mistake in PRD 016 that should also be fixed when convenient)
- `cds_fields` — long-form substrate for C.7 / C.13 fields already populated
- `school_browser_rows` (PRD 010 + 012 pattern) — extending, not creating
- Design tokens, `.cd-card`, `.rule-2` etc.

## Verification

### Phase 0 (gating)

1. Tier 4 resolver extension passes new fixture-based unit tests with at least 5 hand-audited schools.
2. Answerability audit completes; results written to `docs/plans/prd-016b-phase-0-findings.md` with:
   - Per-producer ED-count answerability across 2024-25+ corpus
   - Selectivity-weighted top-200 ED-count answerability (the gate threshold)
   - Class-composition (ED share of admits) corpus-wide distribution
   - Verifier-rejection rate
3. Threshold and scope decisions written into the PRD before migration is opened.

### v1 (after gate clears)

1. **Migration applies cleanly.** `supabase db reset` locally; new columns present with range checks; `admission_strategy_card_quality` column populated correctly during projection.
2. **Projection script unit + integration tests.** Run against a corpus snapshot; verify ED counts populate from each producer (Tier 1 / Tier 2 / Tier 4), that the per-schema 2024-25 vs 2025-26 mapping is correct, and that `admission_strategy_card_quality` is set to 'ok' when math is consistent.
3. **Unit tests** for `admission-strategy.ts` covering 10 fixture schools:
   - **Vanderbilt** — ED-1 + ED-2 (ED-2 detection should fire), high yield, C.718 = "Very Important"
   - **Tulane** — high ED share of admits, ED-2 also offered
   - **Cornell** — Ivy with high ED share of admitted class; ~24% ED rate, ~5% non-early residual
   - **Stanford** — SCEA, no ED. Verify ED rate is null, EA flags surface, ea_restrictive=true.
   - **Notre Dame** — REA only (no ED, contrary to my first draft). Verify ED rate is null, ea_restrictive=true.
   - **University of Michigan** — newly added ED this year. Verify card handles a school whose latest CDS shows ED but prior years did not (no crash; uses latest only).
   - **A rolling-admissions public flagship** (e.g. UConn or Pitt) — verify card handles a school where rolling admissions makes the round model not apply meaningfully; non-early residual rate is rendered with appropriate caveat.
   - **An open-admission school** (community college or open-enrollment public, where C.601 = "open admission") — card hides cleanly per `'insufficient_data'`.
   - **A school with `ed_admitted > ed_applicants`** (deliberate bad-data fixture) — verify `admission_strategy_card_quality = 'ed_math_inconsistent'` and the ED block suppresses with the inline note while other blocks render.
   - **A school with C.21 NULL but yield + wait-list populated** (partial-data path) — verify card renders the populated blocks only.
4. **Component tests** (RTL snapshots) for: card with full data, card with ED suppressed, card with wait-list suppressed, card hidden entirely, card with ED-2 inline note, card with high-yield-protection demonstrated-interest callout.
5. **Contract test** — `tests/api/admission_strategy_contract.sh` confirms the new columns are served via PostgREST.
6. **Manual spot checks** at PR-review time on the 10 fixture schools, comparing rendered numbers against each school's archived CDS PDF.
7. **Methodology page** renders, all source links resolve, worked example matches the actual computation, NBER paper link valid, lawsuit docket link valid.
8. `cd web && npm run build && npm run lint && npm run typecheck` clean.

## Risks

- **Phase 0 reveals C.21 extraction is harder than expected.** Tier 4's flattened-PDF parsing of the C.21 numeric table may have layout edge cases the wait-list resolver doesn't have. Mitigation: budget for iteration. If extraction quality on the top 200 is below ~60%, scope v1 to "Tier 1 + Tier 2 schools only" and add an explicit "ED data not extracted for this school" coverage note for Tier 4 schools.
- **Recruited-athlete bias is real and large.** The block-style adjacent caveat is the v1 mitigation. The IPEDS Athletics non-recruit estimate is the v1.5 fix. The risk is that a v1 reader still walks away thinking ED is a meaningfully bigger lift than it is at top schools. Mitigation: methodology page sensitivity worked example is mandatory at ship time, not a follow-up.
- **ED-1 vs ED-2 invisibility on counts.** Schema-derivable existence detection is a partial fix. The risk is that an ED-1 applicant at an ED-2 school sees the blended rate and over-estimates their odds for the round they're actually applying in. Mitigation: the ED-2 inline note is mandatory and the methodology page documents named ED-2 schools.
- **Year-over-year policy changes.** Michigan added binding ED in 2025-26. The card uses the latest CDS year, which is correct. The risk is that an applicant looking at a school that just changed policy sees the new ED rate but no historical context. Mitigation: prominent CDS-year display, reuse of existing staleness badge.
- **Antitrust lawsuit framing.** The methodology page describes ED as "presented by schools as a binding commitment" with the legal effect "disputed in pending litigation." This is neutral and verifiable. The risk is that the case is decided one way or the other while v1 is shipping, and the language needs to be updated. Mitigation: methodology page is small, easy to update; we monitor the case.
- **Verifier rejection rate higher than expected.** Phase 0 measures this. If the rate is above ~5%, we need a more lenient policy (suppress only the affected block, not the card; don't poison `admission_strategy_card_quality` for the whole row).

## Coverage audit (parallel to v1 ship)

Same shape as PRD 016. The card hides per-school when data is missing or invalid, so coverage is non-blocking for ship after the Phase 0 gate clears. In parallel, projection-rebuild output goes to `scratch/admission-strategy-coverage/` listing schools where C.1 is populated but C.21 is missing, schools that fail the verifier, schools that added ED this year (year-over-year delta), and schools where Tier 4 missed counts that Tier 1 or Tier 2 caught. Feeds extraction-quality work; tracked in `docs/extraction-quality.md`.

## Future work (not in v1)

- **PRD 016 extension: yield-protection caveat.** Add a `'yield_protection_risk'` flag to PRD 016's positioning scorer, fired when student scores are above the 75th percentile *and* school yield is high *and* C.718 demonstrated-interest is "Considered" or higher. Cross-referenced from this PRD's yield gloss.
- **IPEDS Athletics non-recruit ED estimate (v1.5).** Join NCAA EADA / IPEDS Athletics scholarship-counts on UNITID; surface a "non-recruit ED admit rate ≈ X%" estimate alongside the published rate at sub-15% admit-rate schools. Standalone PRD when scoped.
- **PRD 017 reframe to "ED budget" mode.** When activated, the deferred match list-builder microsite uses this PRD's data layer as the primary input for an "ED budget" recommendation surface.
- **Antitrust / research dataset.** Same data, repackaged: CSV + Sheets template + methodology page documenting longitudinal ED admit rates and ED-share-of-class trends across schools. The 2025 antitrust suit can use the open archive as empirical foundation.
- **Common App application-volume context page.** Static page visualizing the 46%-since-2015 increase in apps-per-student as the engine driving the round-stratification dynamic. Public-good content.
- **Deferral-vs-rejection rate for ED applicants.** Some schools volunteer this in the C.2112 free-text field. Could be parsed for a meaningful subset of schools as a v1.5 improvement.

## Effort

**Phase 0:** 3–5 days (Tier 4 resolver build + answerability audit + threshold decisions written into the PRD)

**v1 after gate:** 7–10 days (1 person, CC+gstack pace)

- Migration + projection extension + RPC insert contract update: 2–3 days
- Card component + C.7 factor block + methodology page: 3 days
- Tests (unit + RTL + Playwright + contract) + manual verification across 10 schools: 2–3 days
- Coverage audit + documentation: 1 day

**Total: 2 weeks of focused work** at the realistic end. The first draft's "1 week" estimate assumed extracted data; correcting that assumption is the largest single shift in this v2.

## Open questions deferred to design pass

- **Card title.** "Admission Rounds" / "How to Apply" / "Apply Strategy" / "Admission Dynamics" — pick at design time. Internal name: *admission strategy card.*
- **Card placement order on `/schools/[school_id]`.** Strategy-first vs positioning-first is a real design question (the strategy card works in empty state, the positioning card requires user input). Default to PRD 016 → 016B → OutcomesSection pending the design pass; revisit after page-view telemetry on each card individually.
- **Visual treatment for the ED rate + recruited-athlete caveat.** The caveat must be visually load-bearing, not a footnote. Options: full-width adjacent block, two-column row, or strip below the rate with colored marker. Pick at design time given the precision constraint.
- **Class-composition signal threshold.** Phase 0 measures the corpus distribution; design picks the elbow.
- **C.7 factor block visual.** A small badge cluster vs a plain-text "this school weighs..." sentence vs a tabular layout. Pick at design time.
- **Wait-list block density.** Three numbers + two computed rates = five numbers. Probably too many. Design pass picks the two or three that lead and demotes the others.
- **Yield gloss copy.** The dual-reading framing is mandatory; the exact phrasing is open. Design pass workshops it with the methodology page lead.
