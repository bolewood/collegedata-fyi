# PRD 016B Phase 0 Findings

Generated: `2026-05-02T16:32:09.225693+00:00`

## Summary

- Rows audited: `476`
- ED-count answerability: `90` / `476` (`18.9%`)
- ED-offered answerability: `58` / `69` (`84.1%`)
- EA-offered rows: `31`
- ED-or-EA-offered rows: `90`; ED-count answerable for `58` (`64.4%`)
- Top-200-by-applicants answerability: `57` / `200` (`28.5%`)
- Top-200 ED-offered answerability: `38` / `45` (`84.4%`)
- Top-200 EA-offered rows: `19`
- Top-200 ED-or-EA-offered rows: `58`; ED-count answerable for `38` (`65.5%`)
- ED second-deadline signal: `19` rows (`4.0%`)
- ED share of admitted distribution: `{'count': 85, 'p25': 0.0257, 'p50': 0.0969, 'p75': 0.2046, 'p90': 0.2941}`
- Verifier rejections: `{'ed_admitted_gt_ed_applicants': 4}`

## Producer Answerability

| Producer | Answerable | Total | Pct |
|---|---:|---:|---:|
| tier1_xlsx | 6 | 53 | 11.3% |
| tier2_acroform | 32 | 85 | 37.6% |
| tier4_docling | 52 | 337 | 15.4% |
| tier6_html | 0 | 1 | 0.0% |

## Threshold Decisions

- Card eligibility floor: **cleared for migration**. Current answerability clears the draft 70% top-200 ED-offered gate.
- Class-composition emphasis threshold: use the measured p75 ED-share value as the candidate loud-emphasis threshold once answerability clears.
- Verifier policy: suppress the affected block, not the document; rejection examples need spot audit before migration.
