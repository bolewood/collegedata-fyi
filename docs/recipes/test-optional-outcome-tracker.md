# Test-optional outcome tracker

This recipe responds to SAT-reinstatement coverage by separating three
questions that often get collapsed together:

1. What testing data is still visible in school-published Common Data Set rows?
2. Do UC first-year retention outcomes show an obvious institution-level shock?
3. What completion or transfer-out outcomes should stay on the watchlist?

The public page is:

```text
https://www.collegedata.fyi/recipes/test-optional-outcome-tracker
```

The reusable export is:

```text
https://www.collegedata.fyi/api/recipes/test-optional-outcome-tracker
https://www.collegedata.fyi/api/recipes/test-optional-outcome-tracker?format=csv
```

## Data sources

- `school_browser_rows` for latest CDS testing observability:
  SAT submit rate, ACT submit rate, and SAT/ACT composite score bands.
- `ipeds_facts` for UC historical outcomes:
  `retention_rate_full_time`, `bachelor_6yr_grad_rate`, and
  `transfer_out_rate_total`.
- `scorecard_summary` for current Scorecard context:
  `retention_rate_ft`, `graduation_rate_6yr`, and `transfer_out_rate`.

## Interpretation

This is not a causal test of the SAT. The primary signal is observability: when
schools stop requiring or collecting scores, public score reporting gets
thinner. UC first-year retention does not show an obvious institution-level
collapse, but retention is coarse, ceiling-limited, and confounded by the
pandemic era. Completion and transfer-out remain useful watchlist measures, but
they are too lagged to fully evaluate post-2020 cohorts.

## Caveats

- Formal test-policy labels are not inferred from CDS submit rates.
- UC is a highly selected public system, not the national applicant pool.
- IPEDS retention is not course-level math readiness, DFW rates, GPA, or STEM
  persistence.
- COVID disruption and test-policy changes overlap, so the analysis is
  descriptive, not causal.
