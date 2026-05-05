# Change Intelligence

PRD 019 deterministic event projection.

## Operator flow

Dry-run the calibration subset:

```bash
python tools/change_intelligence/project_change_events.py \
  --env /path/to/.env \
  --watchlist data/watchlists/change_intelligence_calibration.yaml \
  --csv .context/reports/prd019-change-events-calibration.csv \
  --report .context/reports/prd019-change-events-calibration.md \
  --summary-json .context/reports/prd019-change-events-calibration-summary.json
```

After migration `20260505180000_change_intelligence.sql` is applied, persist
generated events with `--apply`.

Rules live in `tools/change_intelligence/rules.yaml`. The first slice compares
the launch admissions/test fields already projected in `school_browser_rows`.
Raw-field follow-up work should use `cds_field_observations`.
