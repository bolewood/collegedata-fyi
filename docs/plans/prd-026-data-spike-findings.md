# PRD 026 Milestone 0 — Data spike findings

**Date:** 2026-07-12
**Verdict: FEASIBILITY GATE PASS — 13/13 criteria** for the
environment/climate/sustainability interest family.

Reproduce: `python3 tools/discovery/data_spike.py` after fetching the inputs
listed in the script header (IPEDS `C2024_A` + dictionary into
`scratch/discovery-spike/`, plus `institution_directory` / `scorecard_summary`
dumps from the public API); `python3 tools/discovery/cds_card_coverage.py`
regenerates the per-card CDS coverage numbers. Full machine-readable output:
`scratch/discovery-spike/audit.json`, which embeds SHA-256 manifests of every
input file so a re-run against drifted dumps is detectable. Unit tests for the
audit logic and artifact invariants: `python3 -m pytest tools/discovery/`.

## Inputs and versions

| Input | Version |
|---|---|
| Completions | IPEDS `C2024_A` provisional (2023-24 awards), `MAJORNUM=1`, `AWLEVEL=05` |
| Institution universe | `institution_directory` (6,322 rows, refreshed 2026-04-29) |
| Scorecard context | `scorecard_summary` (2022-23 data year) |
| Ontology | `data/discovery/ontology/v1.json` (6 concepts, 45 edges, **approved 2026-07-12**) |
| Scenarios | `data/discovery/scenarios/v1.json` (5 origins × 4 profiles = 20) |

## Gate results

| Criterion | Threshold | Result | |
|---|---|---|---|
| Academically plausible eligible institutions | ≥ 75 | **895** | PASS |
| Direct-path institutions | ≥ 30 | **838** | PASS |
| Additional adjacent-path institutions | ≥ 40 | **57** | PASS |
| States represented | ≥ 15 | **53** (incl. DC/territories) | PASS |
| Both control types | both | 480 private-nonprofit / 415 public | PASS |
| Rounds with ≥ 4 schools | 100% | 20/20 | PASS |
| Rounds with 6 schools | ≥ 80% | 17/20 (85%) | PASS |
| Anchor fill | 100% | 100% | PASS |
| Flexible-path fill | ≥ 80% | 100% | PASS |
| Contrast fill | ≥ 50% | 60% | PASS |
| Affordability-context fill | ≥ 70% | 95% | PASS |
| Geographic-wildcard fill (where possible) | ≥ 70% | 90% | PASS |
| Reason references resolve to loaded evidence¹ | 100% | 100% | PASS |

¹ Spike-level check: every emitted reason reference must resolve to loaded
evidence for that school (qualifying award counts for academic reasons, a live
matcher signal for preference reasons). Full `RecommendationReason` validation
(templates, coverage records, limitation versions, fail-closed rendering) is a
`discovery_policy_v1` deliverable, not something this spike measures.

Eligibility funnel from the 6,322-row directory: 3,398 out of scope, 811 not
predominantly bachelor's, 312 excluded control types, 906 in-scope bachelor's
institutions with **no** recent-award evidence in the family → 895 eligible.

## Load-bearing findings

1. **The §8 diversity-relaxation rule is not optional.** The first simulation
   run failed `rounds_min4` (17/20) — not from data scarcity but because the
   ≤2-per-state cap starves radius-bounded scenarios whose eligible pool is
   nearly all one state (Fresno + 400 mi ⇒ almost all CA). Implementing the
   PRD's relax-control-then-state rule fixed all three: `mt-rural--strict-max`
   fills 4/4 candidates at relaxation level 2 (Montana schools for a Montana
   kid — correct behavior), the two Fresno scenarios reach 4 at levels 1–2.
   `discovery_policy_v1` must treat relaxation as a first-class stage with its
   level recorded in round diagnostics, exactly as the PRD specifies.

2. **E.117 "Undergraduate Research" is a CDS Section E1 checklist item**
   (added in the 2022-23 schema —
   `schemas/cds_schema_2021_22-to-2022_23.diff.md`). The PRD assumed research
   access was unmeasurable (reflection-only), but **245 schools have E.117
   extracted for 2024-25**. The `early-research` card is upgraded to `data`
   (card v2, library note records the amendment). The offered-≠-popular
   limitation still applies.

3. **Identity-join membership and geography are clean — with stated limits.**
   All 938 family UNITIDs in the completions file appear in
   `institution_directory.ipeds_id` (0 unmatched), and 0 of the 895 pool
   schools lack coordinates. This is a membership check only: `ipeds_id` is
   the directory's primary key, so within-dump ambiguity cannot occur by
   construction, and the PRD §6 audit of branch campuses, multi-campus
   systems, closures, consolidations, and one-to-many joins remains **open
   work** before production evidence tables ship (the directory's
   `main_campus`/`branch_count` fields exist but were not examined here).

4. **The family is direct-heavy.** 838 of 895 eligible schools have a direct
   edge. The adjacent tier (57 schools) passes its ≥40 threshold, but adjacency
   does little candidate-pool work for *this* lake; its real value is path
   display and the flexible-path slot. Narrower future lakes will exercise
   adjacency harder.

5. **CDS-backed card coverage is real but partial (2024-25):** 346 of the 895
   pool schools have at least one tracked E1/F1 field. Per field: study abroad
   280, double major 270, independent study 266, internships 260,
   residential % 246, undergrad research 245, teacher cert 240, honors 231,
   Greek life 213–216, out-of-state % 287–317, accelerated 185,
   cross-registration 165. Until extraction coverage grows, CDS-backed
   matchers must return `0` (unknown) for the ~60% of the pool without the
   field — absence never means mismatch — and coverage per card should be
   re-measured after each drain. (Machine-readable:
   `scratch/discovery-spike/cds-card-coverage.json`.)

## Caveats (spike-only simplifications)

- Evidence matchers are prototypes with placeholder thresholds; only
  directory/scorecard-backed keys were wired. CDS-backed keys deliberately
  contributed zero, exercising the supported-preference rule.
- Origins carry coordinates directly; the ZIP-centroid source (PRD Q5)
  remains unselected.
- `MAJORNUM=1` only (first majors); second-major counts excluded to avoid
  double-counting people.
- Completions release is provisional; the production loader must record
  release type and manifest checksums per the PRD evidence envelope.

## Recommended next steps

1. Formalize `discovery_policy_v1` (real matchers + thresholds, relaxation
   stage, diagnostics manifest, full `RecommendationReason` validation) — the
   spike's prototype is the skeleton. (Opening-deck selection is done:
   `data/discovery/decks/opening-v1.json`.)
2. Production evidence tables (`ProgramEvidenceFact`/summary projections) via
   the existing IPEDS pipeline, from fresh `main` per migration policy —
   including the PRD §6 identity audit (branches, systems, closures) deferred
   by this spike, and the IPEDS IC load that backs the faith-life and
   big-game-days cards.
3. Prioritize E1/F1 extraction coverage in future drains — every point of
   coverage directly widens the evidence-backed card set.
