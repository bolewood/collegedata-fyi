# Change Intelligence

PRD 019 deterministic event projection.

For the spike/QA results that justified this pipeline, see
[`docs/plans/prd-019-spike-and-qa.md`](../../docs/plans/prd-019-spike-and-qa.md).

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

The Markdown report is an annual-report seed, not publish-ready copy. It
groups generated events into freshness, admissions pressure,
international-student signals, aid shifts, reporting gaps, and
extraction-quality blockers. Treat every `major` event and every
`newly_missing` event as requiring source-PDF review before public reporting.

Record human review and optionally publish a confirmed event:

```bash
python tools/change_intelligence/review_change_event.py \
  --env /path/to/.env \
  --event-id EVENT_ID \
  --reviewer "Anthony" \
  --verdict confirmed \
  --source-page "2025 p. 12" \
  --source-page "2024 p. 11" \
  --notes "Checked the C9 table in both archived PDFs." \
  --publish
```

Use `--publish` only after a confirmed verdict. Non-confirmed verdicts update
`verification_status` and keep `public_visible = false`.

The web `/changes` digest is disabled unless the server environment includes:

```bash
CHANGE_INTELLIGENCE_DIGEST_ENABLED=true
SUPABASE_SERVICE_ROLE_KEY=...
```

The route is intended for operator review only and is not linked from public
navigation.
