-- Daily corpus audit (ops-corpus-audit.yml, tools/data_quality/corpus_audit.py).
-- Read-only check of the published tables for wrong-school files, identical
-- admissions numbers across schools, and CDS applicants far from the IPEDS
-- count. Heartbeats use station_id corpus_audit. Apply from main after merge;
-- do not push from a branch.

insert into public.pipeline_stations (
  station_id, display_name, cadence_label, class, source_kind, on_board, sort_order,
  required_keys, allowed_keys
) values (
  'corpus_audit',
  'Data audit',
  'daily · SLA 36h',
  'daily_sla',
  'gha',
  true,
  85,
  array['new_findings', 'accepted_findings', 'federal_rows_compared'],
  array[
    'new_findings', 'accepted_findings', 'federal_rows_compared',
    'values_withheld', 'parse_errors', 'run_url'
  ]
);

insert into public.pipeline_heartbeats (station_id)
values ('corpus_audit');
