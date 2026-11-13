#!/bin/zsh
# PRD 038 M3: Tier 4 (and fillable-twin) values for the shadow report. PRODUCTION SELECT ONLY.
# usage: fetch_tier4.sh PSQL_WRAPPER SHAS_FILE OUT.json
#   PSQL_WRAPPER  a script that runs psql read-only against production (it must set default_transaction_read_only=on)
#   SHAS_FILE     comma-separated full source sha256 values (the cohort)
#   OUT.json      {sha256: {document_id, school_id, canonical_year, artifact_id, producer_version, recorded_sha,
#                           values, twin: {producer, document_id, values} | null}}
set -e
PSQL="$1"; SHAS="$2"; OUT="$3"
LIST=$(tr ',' '\n' < "$SHAS" | sed "s/.*/('&')/" | paste -sd, -)
SQL=$(cat <<EOF
with shas(sha) as (values $LIST),
src as (
  select distinct on (s.sha) s.sha, a.document_id
  from shas s join public.cds_artifacts a on a.sha256 = s.sha and a.kind = 'source'
  order by s.sha, a.created_at desc
),
t4 as (
  select distinct on (src.sha) src.sha, src.document_id, a.id as artifact_id, a.producer_version, a.schema_version,
         coalesce(a.notes->>'source_sha256', a.notes->'source_artifact'->>'sha256') as recorded_sha, a.notes->'values' as vals
  from src join public.cds_artifacts a on a.document_id = src.document_id and a.kind = 'canonical' and a.producer = 'tier4_docling'
  order by src.sha, a.created_at desc, a.id desc
),
twin as (
  -- a fillable twin: a tier2_acroform artifact on another document of the same school and year, or an older one on this document
  select distinct on (c.sha) c.sha, c.twin_doc, c.vals
  from (
    select t4.sha, m2.document_id as twin_doc, a.notes->'values' as vals, a.created_at, a.id
    from t4
    join public.cds_manifest m1 on m1.document_id = t4.document_id
    join public.cds_manifest m2 on m2.school_id = m1.school_id and m2.canonical_year = m1.canonical_year and m2.document_id <> m1.document_id
    join public.cds_artifacts a on a.document_id = m2.document_id and a.kind = 'canonical' and a.producer = 'tier2_acroform'
    union all
    select t4.sha, t4.document_id, a.notes->'values', a.created_at, a.id
    from t4 join public.cds_artifacts a on a.document_id = t4.document_id and a.kind = 'canonical' and a.producer = 'tier2_acroform'
  ) c
  order by c.sha, c.created_at desc, c.id desc
)
select json_object_agg(t4.sha, json_build_object(
  'document_id', t4.document_id, 'school_id', m.school_id, 'canonical_year', m.canonical_year,
  'artifact_id', t4.artifact_id, 'producer_version', t4.producer_version, 'schema_version', t4.schema_version, 'recorded_sha', t4.recorded_sha,
  'values', (select coalesce(json_object_agg(e.key, json_build_object('value', e.value->>'value', 'value_decoded', e.value->>'value_decoded')), '{}'::json)
             from jsonb_each(t4.vals) e),
  'canonical_artifacts', (select coalesce(json_agg(json_build_object('id', c.id, 'producer', c.producer, 'created_at', c.created_at)), '[]'::json) from public.cds_artifacts c where c.document_id = t4.document_id and c.kind = 'canonical'),
  'twin', (select case when tw.twin_doc is null then null else json_build_object('producer', 'tier2_acroform', 'document_id', tw.twin_doc,
             'values', (select coalesce(json_object_agg(e.key, json_build_object('value', e.value->>'value', 'value_decoded', e.value->>'value_decoded')), '{}'::json) from jsonb_each(tw.vals) e)) end
           from twin tw where tw.sha = t4.sha)
)) from t4 left join public.cds_manifest m on m.document_id = t4.document_id;
EOF
)
"$PSQL" -At -c "$SQL" > "$OUT"
python3 -c "import json,sys; d=json.load(open('$OUT')); print(len(d), 'documents with a Tier 4 base')"
