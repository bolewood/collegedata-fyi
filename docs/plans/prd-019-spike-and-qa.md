# PRD 019 spike and QA findings

**Date:** 2026-05-05
**Related PRD:** [`docs/prd/019-cds-change-intelligence.md`](../prd/019-cds-change-intelligence.md)
**Implementation runbook:** [`tools/change_intelligence/README.md`](../../tools/change_intelligence/README.md)

This file preserves the point-in-time spike and QA results that justified moving
PRD 019 from strategy into implementation.

## What the spike tested

The spike asked whether the existing 2024-25 and 2025-26 CDS extracts contained
enough real year-over-year signal to justify a change-intelligence product and,
eventually, a publication-grade annual report.

It compared only high-leverage admissions/reporting fields already available in
`school_browser_rows`:

- Admit rate.
- Yield rate.
- Early Decision volume where available.
- SAT/ACT submit rates.
- C9 SAT/ACT range reporting, especially newly missing or newly reported ranges.

It deliberately did not test all 1,105 CDS fields. The goal was editorial signal
discovery plus extraction-noise diagnosis, not full diff coverage.

## Spike result

Report artifact: `.context/reports/prd019_admissions_reporting_spike.md`
CSV artifact: `.context/reports/prd019_admissions_reporting_spike.csv`

Summary:

- Source rows fetched: 478.
- Schools with primary 2024-25 and 2025-26 rows: 85.
- Candidate events written: 392.
- Clean comparable events: 282.
- Noisy/provenance/quality-gated events: 110.
- Reporting-status candidate events requiring human review: 31.

The spike passed the decision gate. It found enough source-backed movement to
justify the deterministic projector, but it also showed why public claims need a
hard comparability and human-review gate. Large apparent deltas can come from
producer changes, source-format changes, or low-quality source rows.

## Examples of signal

The clean comparable table surfaced:

- ED volume changes at Texas Christian, Bates, Tulane, William & Mary,
  Davidson, Lafayette, Bowdoin, and Harvey Mudd.
- SAT/ACT range movement at schools including Bates, Hollins, Harvey Mudd,
  SMU, Tulane, William & Mary, and several publics.
- Submit-rate movement, including a large Purdue SAT/ACT submit-rate shift and
  a Yale SAT submit-rate increase.

These examples are candidate insights only. They should not be used in public
copy until source PDFs are reviewed and the event survives the PRD 019 rules.

## QA lessons from the spike

The spike identified the core false-positive risks that shaped the shipped
projector:

- Producer changes can fabricate missing fields or deltas. Example class:
  `tier4_docling` to `tier2_acroform` or `tier1_xlsx`.
- Source-format changes can make a value look newly missing even when the school
  still reported it.
- Low-quality or partial extraction rows can create fake reporting-status
  changes.
- Duplicate/crosswalk issues can double-count schools unless the selected
  primary row and canonical school identity are used.

Resulting implementation decisions:

- `newly_missing` requires compatible producer family/version unless a human
  confirms the source-side silence.
- Source-provenance crossings cap severity.
- `quality_regression`, `producer_changed`, and `format_changed` are explicit
  event types, not silent caveats.
- Public visibility is opt-in through `public_visible=true`.
- Major events and report-bound `newly_missing` events require human review.

## First calibration dry-run

Command shape:

```bash
python tools/change_intelligence/project_change_events.py \
  --env /path/to/.env \
  --watchlist data/watchlists/change_intelligence_calibration.yaml \
  --csv .context/reports/prd019-change-events-calibration.csv \
  --report .context/reports/prd019-change-events-calibration.md \
  --summary-json .context/reports/prd019-change-events-calibration-summary.json
```

Dry-run summary:

- Watchlist schools: 30.
- Schools with prior-year primary CDS rows: 18.
- Schools with latest-year primary CDS rows: 4.
- Pairable schools for this comparison: 4 (13%).
- Events: 36.
- Major: 2.
- Notable: 11.
- Watch: 23.
- Human-review candidates: 4.

The low pairable percentage is the main QA finding. The pipeline can generate
events, but the report/product surface needs more fresh 2025-26 extraction
coverage across the watchlist before it can support the 80% Top 200 launch goal.

## Current shipped boundary

Shipped:

- `cds_field_observations` view.
- `cds_field_change_events` generated table.
- `cds_field_change_event_reviews` human-review table.
- Calibration and Top 200 watchlist seed files.
- Deterministic projector with CSV, Markdown, summary JSON, and optional
  Supabase persistence.
- Annual-report seed sections.
- Review/publish CLI.
- Public school-page `WhatChangedCard`, gated by RLS and `public_visible`.
- Operator-only `/changes` digest, disabled unless
  `CHANGE_INTELLIGENCE_DIGEST_ENABLED=true`.

Not shipped:

- Public `/changes` launch.
- Publication-grade annual report.
- Human-reviewed editorial claims.
- Full Top 200 freshness target.
- Expansion beyond the first admissions/test-focused field set into aid,
  international enrollment, retention, and student-experience families.

## Remaining gates before public reporting

- Re-drain or otherwise refresh enough of the Top 200 watchlist that latest/prior
  pairability is credible.
- Review every `major` and report-bound `newly_missing` event against raw source
  PDFs.
- Mark verified public events with `review_change_event.py --verdict confirmed
  --publish`.
- Keep macro context from WICHE, Census, IIE, and NAFSA in report/methodology
  copy, not in `cds_field_change_events`.
- Separate supported facts from interpretation in every public artifact.
