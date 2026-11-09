# Watchlists

Operator-curated YAML cohorts of canonical `school_id`s. They are working lists for pipeline tooling, not public rankings, and are not shown on the site.

| File | Used by | Purpose |
|---|---|---|
| `top_200_change_intelligence.yaml` | `tools/change_intelligence/` | PRD 019 Top 200 watchlist for change-event projection and the freshness audit. Each entry has a `segment`. |
| `change_intelligence_calibration.yaml` | `tools/change_intelligence/` | Smaller PRD 019 subset used to tune thresholds before generating report-bound change events. |
| `priority_coverage.yaml` | `tools/ops/top100_coverage.py` | Operator priority-100 cohort scored against the two-year byte bar (finder seed plus archived bytes for the current and prior CDS year). |
| `residential_allowlist.yaml` | `tools/ops/top100_coverage.py` | Sticky, operator-approved list of schools that may be fetched from the residential `spoke-ops` runner. Being blocked by a WAF is not enough to be added; each entry records the approval date and reason. |

Each file has `version`, `status` or `description`, and a `schools:` list keyed by `school_id`. Ids must match `tools/finder/schools.yaml`. Refresh a cohort by editing the file in a PR; do not scrape third-party ranking sites on a schedule.

See [`tools/change_intelligence/README.md`](../../tools/change_intelligence/README.md) and [`tools/ops/README.md`](../../tools/ops/README.md) for the commands that consume these files.
