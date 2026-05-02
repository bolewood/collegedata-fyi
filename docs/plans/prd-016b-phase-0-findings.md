# PRD 016B Phase 0 Findings

Generated: `2026-05-02T20:54:23.425796+00:00`

## Summary

- Rows audited: `469`
- ED-count answerability: `104` / `469` (`22.2%`)
- ED-offered answerability: `104` / `145` (`71.7%`)
- EA-offered rows: `114`
- ED-or-EA-offered rows: `190`; ED-count answerable for `104` (`54.7%`)
- Top-200-by-applicants answerability: `68` / `200` (`34.0%`)
- Top-200 ED-offered answerability: `68` / `97` (`70.1%`)
- Top-200 EA-offered rows: `82`
- Top-200 ED-or-EA-offered rows: `128`; ED-count answerable for `68` (`53.1%`)
- ED second-deadline signal: `67` rows (`14.3%`)
- ED share of admitted distribution: `{'count': 96, 'p25': 0.0325, 'p50': 0.1002, 'p75': 0.2432, 'p90': 0.3057}`
- Verifier rejections: `{'ed_admitted_gt_ed_applicants': 6}`

## Producer Answerability

| Producer | Answerable | Total | Pct |
|---|---:|---:|---:|
| tier1_xlsx | 4 | 48 | 8.3% |
| tier2_acroform | 32 | 81 | 39.5% |
| tier4_docling | 68 | 339 | 20.1% |
| tier6_html | 0 | 1 | 0.0% |

## Threshold Decisions

- Card eligibility floor: **cleared for migration**. Current answerability clears the draft 70% top-200 ED-offered gate.
- Class-composition emphasis threshold: use the measured p75 ED-share value as the candidate loud-emphasis threshold once answerability clears.
- Verifier policy: suppress the affected block, not the document; rejection examples need spot audit before migration.
