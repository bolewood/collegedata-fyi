-- PRD 029: append-only publish-event log + extracted_at.
--
-- cds_documents is a mutable state table: refresh updates a row in place
-- and unchanged_verified re-touches last_verified_at. An RSS feed cannot
-- be built from that table without missing refreshes or firing on
-- re-verification. cds_publish_events is the immutable log.
--
-- Pattern follows school_hosting_observations (append-only, school_id
-- keyed, RLS on). Public SELECT is limited to school_direct rows so a
-- feed can claim "this school published" without leaking mirror or
-- operator-manual ingest.

begin;

create table public.cds_publish_events (
  id                bigserial primary key,
  school_id         text not null,
  document_id       uuid not null references public.cds_documents(id),
  cds_year          text not null,
  event_type        text not null
                    check (event_type in ('inserted', 'refreshed')),
  source_provenance text not null,
  source_sha256     text not null,
  occurred_at       timestamptz not null default now()
);

comment on table public.cds_publish_events is
  'Append-only log of inserted and refreshed archive outcomes. RSS/Atom '
  'feeds read school_direct rows only. Mirror and operator_manual rows '
  'stay for audit and must not generate a "school published" alert. '
  'unchanged_verified is deliberately not recorded.';

comment on column public.cds_publish_events.event_type is
  'inserted = new cds_documents row. refreshed = existing row updated in '
  'place with new bytes (refreshDocumentWithNewSha).';

comment on column public.cds_publish_events.source_provenance is
  'Copied from the write that produced the event. Feed filters to '
  'school_direct so a third-party mirror catch-up cannot look like a '
  'school publish.';

create index cds_publish_events_school_occurred_idx
  on public.cds_publish_events (school_id, occurred_at desc);

alter table public.cds_publish_events enable row level security;

create policy cds_publish_events_public_school_direct
  on public.cds_publish_events
  for select
  to anon, authenticated
  using (source_provenance = 'school_direct');

grant select on public.cds_publish_events to anon, authenticated;

alter table public.cds_documents
  add column if not exists extracted_at timestamptz;

comment on column public.cds_documents.extracted_at is
  'Set once when extraction_status first becomes extracted. Written by '
  'tools/extraction_worker/worker.py mark_extraction_status. Later edits '
  'to the row must not rewrite this timestamp.';

-- Recreate cds_manifest to expose extracted_at and the freshness columns
-- already on cds_documents (HTTP Last-Modified, embedded PDF/XLSX dates).
-- cds_scorecard depends on cds_manifest, so drop it first.
drop view if exists public.cds_scorecard;
drop view if exists public.cds_manifest;

create view public.cds_manifest
with (security_invoker = true) as
  select
    d.id                   as document_id,
    d.school_id,
    d.school_name,
    d.ipeds_id,
    d.sub_institutional,
    d.cds_year,
    d.source_url,
    d.source_format,
    d.participation_status,
    d.discovered_at,
    d.last_verified_at,
    d.removed_at,
    d.extraction_status,
    d.extracted_at,
    d.source_http_last_modified,
    d.source_creation_date,
    d.source_modification_date,
    (
      select a.id
      from public.cds_artifacts a
      where a.document_id = d.id and a.kind = 'canonical'
      order by a.created_at desc
      limit 1
    ) as latest_canonical_artifact_id,
    (
      select a.storage_path
      from public.cds_artifacts a
      where a.document_id = d.id and a.kind = 'source'
      order by a.created_at desc
      limit 1
    ) as source_storage_path,
    d.detected_year,
    coalesce(d.detected_year, d.cds_year) as canonical_year,
    d.data_quality_flag
  from public.cds_documents d;

grant select on public.cds_manifest to anon, authenticated;

comment on view public.cds_manifest is
  'Convenience view joining cds_documents to their most recent canonical '
  'artifact and archived source file. SECURITY INVOKER so public reads '
  'honor underlying RLS. extracted_at and source_* date columns are the '
  'PRD 029 freshness signals.';

create view public.cds_scorecard
with (security_invoker = true) as
  select
    m.document_id,
    m.school_id,
    m.school_name,
    m.ipeds_id,
    m.canonical_year                    as cds_year,
    m.source_format,
    m.extraction_status,
    m.data_quality_flag,
    m.latest_canonical_artifact_id,
    m.source_storage_path,
    sc.scorecard_data_year,
    sc.earnings_10yr_median,
    sc.earnings_10yr_p25,
    sc.earnings_10yr_p75,
    sc.median_debt_completers,
    sc.median_debt_monthly_payment,
    sc.avg_net_price,
    sc.net_price_0_30k,
    sc.net_price_30k_48k,
    sc.net_price_48k_75k,
    sc.net_price_75k_110k,
    sc.net_price_110k_plus,
    sc.graduation_rate_6yr,
    sc.grad_rate_pell,
    sc.repayment_rate_3yr,
    sc.default_rate_3yr,
    sc.pell_grant_rate,
    sc.federal_loan_rate,
    sc.first_generation_share,
    sc.median_family_income,
    sc.retention_rate_ft,
    sc.endowment_end,
    sc.instructional_expenditure_fte
  from public.cds_manifest m
  left join public.scorecard_summary sc
    on sc.ipeds_id = m.ipeds_id;

grant select on public.cds_scorecard to anon, authenticated;

comment on view public.cds_scorecard is
  'CDS manifest left-joined with the curated College Scorecard subset. '
  'One row per CDS document. Recreated alongside cds_manifest in PRD 029.';

-- Demand-shaped top-N for daily archive escalation. Ranked from public
-- CDS C1 applicant volume already stored on school_browser_rows.applied
-- (2025-26 C.116 / 2024-25 C.101–C.104). Independently computed at
-- query time — not derived from, referenced against, or trimmed from
-- data/watchlists/top_200_change_intelligence.yaml.
create or replace function public.publish_alert_tier_schools(p_n integer default 50)
returns table(school_id text, applied integer, canonical_year text)
language sql
stable
security invoker
set search_path = public
as $$
  with latest as (
    select distinct on (sbr.school_id)
      sbr.school_id,
      sbr.applied,
      sbr.canonical_year
    from public.school_browser_rows sbr
    where sbr.sub_institutional is null
      and sbr.applied is not null
      and sbr.applied > 0
    order by sbr.school_id, sbr.year_start desc, sbr.document_id
  )
  select latest.school_id, latest.applied, latest.canonical_year
  from latest
  order by latest.applied desc, latest.school_id
  limit greatest(p_n, 0);
$$;

comment on function public.publish_alert_tier_schools(integer) is
  'PRD 029 M2: top-N school_ids by latest public C1 applicant volume. '
  'Must not be computed from the PRD 019 operator-only watchlist.';

revoke all on function public.publish_alert_tier_schools(integer) from public;
grant execute on function public.publish_alert_tier_schools(integer) to service_role;

-- 9-month freshness anchors for the ~50 tier schools. Dedicated read so
-- archive-enqueue does not stretch latest_archive_terminal_rows past its
-- ~95-day bound. Precedence: embedded modification date, embedded
-- creation date, HTTP Last-Modified, discovered_at.
create or replace function public.publish_alert_freshness_anchors(p_school_ids text[])
returns table(school_id text, freshness_at timestamptz)
language sql
stable
security invoker
set search_path = public
as $$
  select distinct on (d.school_id)
    d.school_id,
    coalesce(
      d.source_modification_date,
      d.source_creation_date,
      d.source_http_last_modified,
      d.discovered_at
    ) as freshness_at
  from public.cds_documents d
  where d.school_id = any(p_school_ids)
    and d.sub_institutional is null
    and d.removed_at is null
  order by
    d.school_id,
    coalesce(d.detected_year, d.cds_year) desc;
$$;

comment on function public.publish_alert_freshness_anchors(text[]) is
  'PRD 029 M2: per-school freshness timestamp for daily-escalation clock. '
  'Scoped to the demand-tier school_ids only.';

revoke all on function public.publish_alert_freshness_anchors(text[]) from public;
grant execute on function public.publish_alert_freshness_anchors(text[]) to service_role;

commit;
