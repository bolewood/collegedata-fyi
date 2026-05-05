# PRD 019: CDS change intelligence and reporting gaps

**Status:** Draft, candidate next strategic PRD.
**Created:** 2026-05-05
**Author:** Anthony + Codex
**Related:** [PRD 014](014-cross-year-canonical-schema.md), [PRD 016B](016B-admission-strategy-card.md), [PRD 017](017-match-list-builder.md), [PRD 018](018-open-college-fit-data.md), [Queryable browser backend](../queryable-browser-backend.md)

---

## Context

The strongest next narrative for collegedata.fyi is not "we archived more PDFs."
It is: **we can see what American colleges changed, stopped reporting, and started
emphasizing before families, counselors, and journalists can track it manually.**

This matters because the 2025-26 and 2026-27 admissions cycles sit at the
intersection of several external pressures:

- The U.S. high-school graduate count is projected to peak around 2025 and then
  decline through 2041. WICHE's 2024 _Knocking at the College Door_ release
  reports 3.9 million high-school graduates in 2025, falling to 3.4 million by
  2041, a 13% decline. The Census Bureau separately notes that U.S. births have
  declined every year since 2008 except 2014, giving the post-Great-Recession
  demographic cliff its underlying cohort shape.
- International-student demand is now a live policy variable, not background
  noise. IIE's Fall 2025 Snapshot reports new international enrollments down
  17% year over year, while NAFSA's fall 2025 outlook modeled up to 150,000
  fewer international students under visa-processing and travel-restriction
  pressure.
- Many college responses to pressure will show up first in CDS deltas: admit
  rates, early-round behavior, test-score reporting, international enrollment,
  aid allocation, yield, retention, class-size distribution, and reporting gaps.

The aspirational editorial goal is concrete: **generate enough fresh,
source-backed insight that Anthony could credibly pitch an op-ed or data essay
to a national outlet.** The implementation goal is a data product that makes that
essay repeatable every year.

## Pre-PRD spike — prove the editorial signal exists

Before Phase 0 begins, run a two-day spike. The goal is not infrastructure; the
goal is to answer whether the data contains enough surprising signal to justify
the full change-intelligence build.

Scope:

- Pick the 50-100 schools that already have both 2024-25 and 2025-26 primary CDS
  rows.
- Compare only five highest-leverage fields:
  - admit rate
  - yield rate
  - ED admit rate or ED volume, where available
  - SAT/ACT submit rate
  - C9 SAT/ACT range reporting, especially newly missing 25th/50th/75th
    percentile values
- Export a CSV with `school_id`, `field_key`, prior-year value, latest-year
  value, absolute delta, and source URLs.
- Manually inspect the top 50 deltas.

Decision gate:

- If at least five deltas are real, source-backed, and editorially interesting,
  proceed to Phase 0.
- If not, demote the annual-report/op-ed framing and re-scope v1 as a small
  school-page "What Changed" card.

## External sources to cite in product/editorial work

These are not product dependencies, but they define the macro frame. Keep them
out of the extraction pipeline; cite them in methodology/reporting pages.

- WICHE, _Knocking at the College Door_, 11th edition release:
  https://www.wiche.edu/resources/report-u-s-high-school-graduates-will-peak-next-year-then-most-states-will-see-steady-declines-through-2041/
- WICHE PDF, _Projections of High School Graduates_, December 2024:
  https://www.wiche.edu/wp-content/uploads/2024/12/2024-Knocking-at-the-College-Door-final.pdf
- Census Bureau, "U.S. Births Declined During the Pandemic" (contains the
  post-2008 birth-decline summary):
  https://www.census.gov/library/stories/2021/09/united-states-births-declined-during-pandemic.html
- IIE, Fall 2025 Snapshot on International Student Enrollment:
  https://www.iie.org/publications/fall-2025-snapshot-on-international-student-enrollment/
- IIE, "Four Things To Know About the Fall 2025 Snapshot":
  https://www.iie.org/blog/four-things-to-know-about-the-fall-2025-snapshot/
- NAFSA, Fall 2025 International Student Enrollment Outlook and Economic Impact:
  https://www.nafsa.org/fall-2025-international-student-enrollment-outlook-and-economic-impact

## Strategic thesis

CDS transparency is voluntary, uneven, and changing. A school communicates not
only through the numbers it reports, but also through what it stops reporting.

The product should therefore track three classes of signal:

1. **Material changes** — values that moved enough to matter.
2. **Reporting gaps / silences** — fields that were previously reported but are
   now missing, suppressed, or no longer machine-extractable from a newer CDS.
3. **Recovered signals** — fields that were absent and then reappear. These are
   first-class editorial signals, not cleanup trivia: the return of data can
   reflect internal reporting changes, compliance pressure, or a strategic
   decision to make a metric visible again.

This is not a claim that every silence is suspicious. The UI and editorial copy
must stay neutral: "newly missing from the reported CDS" is a fact; "the school
is hiding this" is an interpretation that should almost never ship.

## Launch scope

### School panel

Start with an operator-curated **Top 200 Watchlist**, not the full corpus.

The watchlist should combine:

- Highly recognizable national universities and liberal arts colleges.
- Flagship publics.
- Schools with strong counselor/family search demand.
- Schools where 2025-26 CDS publication is likely or already detected.

Seed the launch watchlist without proprietary rankings:

- Top 100 schools by latest available CDS C1 application volume.
- 50 flagship state universities.
- 50 high-endowment or high-recognition liberal arts colleges, sourced from
  non-proprietary public data where possible and operator-reviewed for launch.

The Top 200 Watchlist is **operator-only until the first report ships**. Public
launch can expose aggregate coverage and selected findings, but not the full
watchlist membership before there is enough evidence to defend inclusion and
exclusion decisions.

The launch gate is:

> For at least 80% of the Top 200 Watchlist schools with an available 2025-26 CDS,
> collegedata.fyi can show a year-over-year change report comparing the latest
> primary CDS against the prior primary CDS, with material deltas, disappeared
> fields, recovered fields, and source-backed evidence.

### Launch field families

Do not attempt all 1,105 CDS fields in v1. Do not even attempt the full 50-80
field candidate set in the first projector. Launch with a tight 15-20 field
set, then expand only after the calibration subset is clean.

**Admissions pressure**

- C1 applicants, admits, enrolled first-years.
- Admit rate and yield rate derived from C1.
- C2/C21/C22 early decision, early action, wait-list, and deferral fields where
  available.
- C7 application-factor importance changes for a small initial subset only:
  academic GPA, standardized test scores, class rank, and first-generation
  status if reliably mapped.
- C9/C10/C11/C12 test-score and GPA reporting.
- Test-submit rates and score-range disappearance/reappearance.

**International pressure**

- B1/B2/B3 enrollment fields that expose nonresident-alien / international
  student counts and shares where available.
- C1 applicant/admit/enroll fields only if international-specific counts are
  present in school-specific variants. This is not universal; flag as
  school-specific evidence only.
- J / study-abroad fields are Phase 4+, not launch blocking.

**Affordability and aid pressure**

- H2A institutional grant recipients and dollars.
- H1/H2/H5/H6/H7/H8 average aid package, need grant, non-need grant, and
  institutional grant values.
- Percent receiving institutional grant aid.
- Net-price/outcome fields from Scorecard may contextualize, but CDS change
  events should remain CDS-sourced unless explicitly labeled.

**Student experience / institutional health**

- Retention and graduation fields, class-size distribution, student/faculty
  ratio, housing, and Greek participation are Phase 4+. They are valuable but
  too broad for the first deterministic projector.

## What ships

### `cds_field_observations`

Ship as a **view only** in v1. Do not create a new materialized write path unless
query-time measurements later require it. The view records one normalized
observation per school, primary CDS year, canonical field, and selected document:

- `school_id`
- `document_id`
- `canonical_year`
- `year_start`
- `field_key`
- `value_numeric`
- `value_text`
- `normalized_value`
- `unit`
- `source_producer`
- `source_producer_version`
- `source_page` / `source_locator` if available
- `archive_url`
- `observed_at`
- `quality_flag`

The view is derived from `cds_fields` plus `cds_manifest` / selected-primary
document logic. If this ever becomes materialized, it must be refreshed by the
same projection flow that refreshes `cds_fields`, not independently.

### `cds_field_change_events`

A generated table of year-over-year events. One row per meaningful event:

- `school_id`
- `field_key`
- `field_family`
- `from_document_id`
- `to_document_id`
- `from_year`
- `to_year`
- `event_type`
- `severity`
- `from_value`
- `to_value`
- `absolute_delta`
- `relative_delta`
- `threshold_rule`
- `summary`
- `from_producer`
- `to_producer`
- `from_producer_version`
- `to_producer_version`
- `from_source_provenance`
- `to_source_provenance`
- `evidence_json`
- `created_at`

Event types:

- `material_delta`
- `newly_missing`
- `newly_reported`
- `reappeared`
- `format_changed`
- `producer_changed`
- `quality_regression`
- `quality_recovered`
- `card_quality_changed`

Severity levels:

- `watch` — visible on school page but not report-worthy.
- `notable` — included in watchlist digest.
- `major` — candidate for editorial/reporting surface.

### Producer, schema, and provenance comparability

The hardest credibility risk is false change events caused by extraction drift,
not school behavior. The projector must classify comparability before computing
events.

Hard rules:

- `field_key` must be resolved through PRD 014's canonical equivalence tables
  before any comparison. Raw schema-version-specific IDs are not allowed in
  change rules.
- A schema rename must not emit `newly_missing` or `newly_reported`.
- `newly_missing` requires same producer family and compatible producer version
  between prior and latest observations. If the producer family or material
  version changed, emit `producer_changed` or `quality_regression` instead.
- Producer downgrades, such as `tier1_xlsx` -> `tier4_docling`, are editorially
  neutral until a human confirms the field is truly absent from the newer source
  document.
- Producer upgrades, such as a Tier 4 cleaner redrain that recovers fields, are
  `quality_recovered` unless the school-side source also changed in a way that
  justifies `newly_reported`.
- Source provenance crossings, such as `school_direct` -> `mirror`, must be
  tagged. A `material_delta` across provenance can be visible, but its severity
  is capped at `watch` unless human-reviewed.
- The prior year's value determines the selectivity band for threshold rules,
  even if the latest year crosses a band boundary.

Required tests:

- A field renamed across CDS schema versions does not fire `newly_missing`.
- `tier1_xlsx` -> `tier4_docling` missing fields produce `producer_changed`, not
  `newly_missing`.
- A prior admit rate of 19% and latest admit rate of 24% uses the prior-year
  `high_selectivity` band.

### Evidence schema

`evidence_json` must have a typed shape. It is not a generic notes bucket.

```ts
type ChangeEventEvidence = {
  from_value: { num?: number; text?: string; status: "reported" | "missing" };
  to_value: { num?: number; text?: string; status: "reported" | "missing" };
  from_producer: string;
  to_producer: string;
  from_source_provenance: string | null;
  to_source_provenance: string | null;
  threshold_rule_fired: string;
  computed_delta: {
    absolute?: number;
    percentage_points?: number;
    relative_pct?: number;
  };
  comparability: {
    same_canonical_field: boolean;
    same_producer_family: boolean;
    compatible_producer_version: boolean;
    same_source_provenance: boolean;
  };
  caveats: string[];
};
```

### Field-specific threshold rules

Thresholds must be field-aware and institution-aware. A four-point yield move
does not mean the same thing at a school with a 5% admit rate as it does at a
regional public with a 75% admit rate. Rules should support baseline bands:

- `high_selectivity`: prior admit rate < 20%.
- `selective`: prior admit rate >= 20% and < 50%.
- `broad_access`: prior admit rate >= 50%.
- `unknown_selectivity`: no reliable prior admit rate.

Delta semantics:

- Probability/rate/share fields use percentage-point deltas as the primary
  metric. Do not use `(new - old) / old` as a default report trigger for admit
  rate, yield, submit rates, or enrollment shares.
- Dollar fields may use both absolute-dollar deltas and relative percentage
  deltas, with inflation adjustment where practical.
- Count fields use absolute deltas and relative percentage deltas, but rules
  must define minimum denominator floors to avoid noisy small-N swings.

Examples:

- Admit rate: major if absolute change >= 3 percentage points; stricter review
  for `high_selectivity` schools.
- Yield rate: notable if absolute change >= 4 percentage points, but major
  thresholds vary by baseline band and historical volatility.
- International enrollment share: notable if absolute change >= 2 percentage
  points; major if >= 5 percentage points.
- Institutional grant recipient share: notable if absolute change >= 5
  percentage points.
- Average institutional/non-need grant dollars: notable if inflation-adjusted
  delta >= 10%; major if >= 20%.
- C9 SAT/ACT range: newly missing is notable if the school reported the field
  in at least two prior primary CDS years.
- Test-submit rate: notable if absolute change >= 5 percentage points.
- C7 importance factor: notable if a factor moves across a semantic boundary
  (`not considered` -> `considered`, `considered` -> `important`,
  `important` -> `very important`).

Thresholds live in config, not code paths scattered through the app:

```
tools/change_intelligence/rules.yaml
```

The rules engine must also compute historical volatility where enough prior years
exist. A small raw movement can be major if it is far outside the school's own
recent pattern; a larger movement can remain `watch` if the field has always
been volatile.

### Human verification gate

Any event with `severity = major`, and any `newly_missing` event that is eligible
for public/reporting output, must pass a human verification step before it can be
included in the annual report artifact or public digest.

Verification records:

- `event_id`
- `reviewer`
- `reviewed_at`
- `verdict`: `confirmed`, `extractor_noise`, `ambiguous`, `not_reportable`
- `notes`
- `source_pages_checked`

The pipeline may generate candidate silences. It may not publish them as
reportable silences until a human has inspected the newer source document and,
where needed, the prior document. This is the credibility gate for the whole
feature.

Phase 0 must estimate verification capacity in operator hours. If the projected
annual review queue is greater than 40 hours, v1 must reduce the watchlist,
tighten thresholds, or both.

### Section quality gate

A field can only become `newly_missing` when the newer document is otherwise
high-quality for the relevant section/subsection. This should reuse existing
quality signals before inventing new ones:

- `data_quality_flag`
- `admission_strategy_card_quality`
- `merit_profile_quality`
- section/subsection answerability from the Phase 0 audit
- producer compatibility from the comparability rules above

Phase 0 must define initial section-quality thresholds. Sketch:

- section/subsection answerability >= 70% for the relevant launch field family,
  or an existing card-quality flag indicating the section is usable.
- no `wrong_file`, `blank_template`, or `low_coverage` document flag.
- no producer downgrade unless human-reviewed.

### School-page "What Changed" module

Add a compact school-page section:

- Latest CDS year compared with prior primary year.
- 3-5 highest-salience changes.
- Explicit "newly missing" / "newly reported" labels.
- Source links to both PDFs.
- Caveat line: "A missing field can mean the school omitted it, changed format,
  or our extractor could not recover it. We flag extractor-quality regressions
  separately where detected."

### Watchlist digest

Add an operator-facing or public `/changes` surface:

- Top 200 Watchlist completion status.
- Newly published CDS files.
- Biggest admissions changes.
- Biggest aid changes.
- International-enrollment movement.
- Newly missing test-score or aid fields.
- Schools with extraction-quality regressions that block a clean comparison.

Public launch can start as a static page generated from the latest change-event
projection. Do not overbuild filters before the first editorial report is written.

For v1, `/changes` is operator-only. Public launch happens after threshold
calibration and editorial review.

### Annual report seed

Generate a Markdown report artifact:

```
.context/reports/cds-change-intelligence-2025-26.md
```

Sections:

- Freshness / coverage status for the Top 200 Watchlist.
- Biggest admissions-pressure signals.
- International-student signals visible in CDS.
- Aid and affordability shifts.
- Reporting gaps / silences worth asking about.
- Methodology and caveats.
- Query appendix with source links.

This is the bridge from data product to op-ed/reporting.

Report generation must exclude unverified `major` and `newly_missing` events by
default. It may include an appendix of unverified candidates only if they are
clearly labeled as candidates and excluded from editorial claims.

Editorial review must explicitly check for adjacency-driven implied causation.
Macro context from WICHE, Census, IIE, and NAFSA should frame the report, but
school-specific change tables should not be positioned so close to macro-policy
claims that readers infer causation the data does not prove.

## What does NOT ship

- No claim that missing data proves intentional concealment.
- No automated accusation language.
- No full 1,105-field diff UI in v1.
- No use of proprietary rankings as a hard-coded public source unless licensing
  is reviewed. The Top 200 Watchlist is operator-curated for launch.
- No LLM-only change events. LLMs may summarize events after deterministic
  detection, but the event record must come from structured field comparisons.
- No policy-causation claims. CDS deltas can be discussed alongside WICHE, IIE,
  NAFSA, Census, and policy context, but the app should not infer causation.
- No unreviewed silences in publication-grade reports. Machine-generated
  `newly_missing` candidates are not reportable until verified.

## Architecture sketch

```
cds_documents / cds_manifest
        |
        v
cds_fields  + selected primary document logic
        |
        v
cds_field_observations
        |
        v
tools/change_intelligence/project_change_events.py
        |
        +--> cds_field_change_events
        |
        +--> .context/reports/cds-change-intelligence-2025-26.md
        |
        +--> school page What Changed module
        |
        +--> /changes watchlist digest
```

## Implementation phases

### Phase 0 — Field and watchlist scoping

- Create Top 200 Watchlist seed file:
  `data/watchlists/top_200_change_intelligence.yaml`.
- Create a ground-truth calibration subset:
  `data/watchlists/change_intelligence_calibration.yaml`.
- Select a tight 15-20 launch field list and map raw schema-version fields to
  canonical schema keys through PRD 014 equivalence tables.
- Write `rules.yaml` with threshold rules.
- Run an answerability audit for launch fields across 2024-25 and 2025-26
  documents already in the corpus.
- Estimate human-verification queue size in operator hours.

Exit gate: at least 70% of watchlist schools with both latest and prior primary
CDS have enough launch fields for a useful change report, and the estimated
verification queue is <= 40 operator hours.

### Calibration subset

Before applying thresholds to the whole watchlist, calibrate on an intentionally
mixed 30-school subset:

- 10 high-selectivity private universities and liberal arts colleges.
- 10 flagship or high-application public universities.
- 5 international-heavy universities.
- 5 broad-access or regional institutions with available multi-year CDS history.

The subset should include schools where the operator already has domain intuition
and schools where the pipeline is likely to struggle. It should deliberately
include Ivies/top privates, large publics, LACs, and schools with known extraction
edge cases.

Candidate seed, subject to document availability at implementation time:

- High-selectivity private / LAC: Harvard, Yale, Princeton, MIT, Stanford, Duke,
  Northwestern, Vanderbilt, Amherst, Bowdoin.
- Flagship / high-application public: UC Berkeley, UCLA, Michigan, Virginia,
  North Carolina, Georgia Tech, Texas A&M, Ohio State, Wisconsin, Florida.
- International-heavy universities: Columbia, NYU, Northeastern, USC, Boston
  University.
- Broad-access / regional / extraction-edge calibration: Arizona State,
  Cincinnati, George Mason, Kent State, UT Dallas.

Threshold rules are not considered launch-ready until every `major` and
`newly_missing` event in this subset has been manually reviewed and classified.

### Phase 1 — Observation and event projection

- Implement `cds_field_observations` as a view.
- Implement change-event projector.
- Persist events into Supabase.
- Add unit tests for threshold rules and event classification.
- Spot-check at least 20 schools, including Ivies, flagship publics, LACs, and
  international-heavy private universities.

Exit gate: projector produces deterministic, source-linked events with no known
false-positive major events in the 20-school spot check.

### Phase 2 — School-page and digest UI

- Add `WhatChangedCard` to school pages.
- Add `/changes` digest page.
- Add methodology copy explaining material deltas, reporting gaps, and extractor
  quality.
- Ensure every visible event links back to source PDFs and years.

Exit gate: a counselor or journalist can understand the event without knowing
CDS field names.

### Phase 3 — Report generation

- Generate first annual Markdown report.
- Export CSV of all watchlist events.
- Add charts for a small number of high-confidence cross-school trends.
- Run human verification for every `major` and report-bound `newly_missing`
  event.
- Draft an editorial memo with claims separated into:
  `strongly supported`, `suggestive`, and `needs external corroboration`.

Exit gate: at least five publishable insights have source-backed evidence and
clear caveats.

## Verification

- Unit tests for field-specific threshold rules.
- Fixture tests for:
  - material numeric delta
  - newly missing after one prior year
  - newly missing severity raised after two-plus prior years
  - newly reported
  - reappeared
  - extraction quality regression
  - producer changed
  - schema rename with no event
  - source provenance crossing
  - categorical C7 movement
  - prior-year selectivity boundary
- Snapshot test for a known school with stable historic CDS rows.
- Manual spot-check of 20 watchlist schools against source PDFs.
- Human verification coverage: 100% of `major` and report-bound
  `newly_missing` events have `confirmed` or `not_reportable` decisions.
- Cross-check the annual report summary counts against raw `cds_field_change_events`.
- Confirm no public copy claims causation from demographic or immigration-policy
  context without external citation.

## Failure modes

- **Extractor miss misclassified as school silence.** Mitigation: event type
  `quality_regression` and public caveat. A field should only become
  `newly_missing` when the newer document is otherwise high-quality for that
  section.
- **Producer drift fabricates school behavior.** Mitigation: explicit producer
  comparability rules, `producer_changed` events, and no `newly_missing` events
  across producer downgrades without human review.
- **Schema drift fabricates field disappearance.** Mitigation: canonical
  equivalence mapping from PRD 014 before comparisons, plus rename fixture tests.
- **Top 200 freshness too low.** Mitigation: recency-first discovery/drain,
  targeted watchlist re-drain, and a public freshness denominator.
- **Thresholds generate noise.** Mitigation: start conservative and manually
  review every `major` event before it appears in the first report; use baseline
  selectivity bands and historical volatility where possible.
- **Year pairing is wrong.** Mitigation: compare selected primary documents only,
  never sub-institutional rows unless explicitly supported.
- **Editorial overreach.** Mitigation: separate "what changed in CDS" from "why
  it changed." External sources frame the macro context; CDS events are the
  evidence layer.

## Effort estimate

1-2 weeks for a first deterministic event projector and school-page card if the
field list stays tight and the watchlist is curated manually.

2-4 weeks for a publication-grade annual report with enough spot-checking,
charts, caveats, and top-200 freshness work to support a serious external pitch.

This estimate excludes the mandatory two-day pre-PRD editorial spike.

## Open questions

- Exact 30-school calibration subset.
- Whether every confirmed `newly_missing` event should appear on school pages,
  or only those above `notable`.
- How much of the human verification workflow belongs in Supabase tables vs.
  `.context` report-review artifacts for v1.
- Whether the first public launch should lead with `/changes`, an annual report,
  or a single flagship essay with `/changes` as supporting evidence.

## Decisions made from initial review

- Top 200 Watchlist is operator-only until the first report ships.
- Watchlist seed avoids proprietary rankings: C1 application volume, flagship
  publics, and public/operator-reviewed LAC recognition.
- One prior year is enough to flag a launch `newly_missing` event, but the label
  must say "vs. prior year." Two-plus prior years can raise severity.
- Phase 1 international-student pressure uses CDS-visible fields first. IIE,
  NAFSA, IPEDS, and Scorecard context belong in the report layer, not
  `cds_field_change_events`.
- `/changes` starts operator-only and becomes public after threshold calibration
  and the first editorial review.
