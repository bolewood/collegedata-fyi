# FSA institutional nonpayment

Loads the public Federal Student Aid school-level nonpayment workbook into
`fsa_releases` and `fsa_nonpayment_facts`, and stamps `school_id` at load
time. The serving view is `fsa_nonpayment_current`.

This is **not** the official cohort default rate. Homepage and About still
name CDS, IPEDS, and College Scorecard.

## Source

- Listing: https://studentaid.gov/data-center/student/portfolio (in-page search: `nonpayment`)
- File: https://studentaid.gov/sites/default/files/fsawg/datacenter/library/nonpayment-rates.xlsx
- Design: [`docs/designs/fsa-institutional-nonpayment.md`](../../docs/designs/fsa-institutional-nonpayment.md)
- M0 join report: [`docs/designs/fsa-m0-join-report.md`](../../docs/designs/fsa-m0-join-report.md)

Downloads belong in `scratch/fsa/<as-of>/`, not in `tools/`.

## Apply (after the migration is on main)

```bash
python tools/fsa/report_m0.py \
  --xlsx scratch/fsa/2026-05/nonpayment-rates.xlsx \
  --csv path/to/Most-Recent-Cohorts-Institution.csv

python tools/fsa/load.py \
  --xlsx scratch/fsa/2026-05/nonpayment-rates.xlsx \
  --csv path/to/Most-Recent-Cohorts-Institution.csv

python tools/fsa/load.py \
  --xlsx scratch/fsa/2026-05/nonpayment-rates.xlsx \
  --csv path/to/Most-Recent-Cohorts-Institution.csv \
  --hd path/to/HD2024.zip \
  --apply
```

`--apply` surgically fills `institution_directory.opeid` from the Scorecard
CSV (no slug rewrite) and upserts the workbook on `source_sha256`. Reloading
the same file is idempotent.

## Tests

```bash
python -m unittest discover -s tools/fsa -p "test_*.py"
python -m unittest tools.scorecard.test_load_directory
```
