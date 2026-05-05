-- Archive observability: bot-challenge ProbeOutcome category + source-file metadata.
--
-- Two related concerns bundled:
--
--  1. Bot-challenge classification. Cloudflare/Imperva WAFs return either
--     200 OK with a JS challenge body, or 403 with a verification page,
--     or 503. Today these all collapse into wrong_content_type / transient
--     because archive.ts inspects bytes-magic only, not response headers.
--     Williams College (28 archived years) and Johns Hopkins 2025-26 are
--     the live cases: school-direct fetches consistently fail; mirror
--     fallbacks succeed where they exist. Surfacing bot_challenge as its
--     own category lets the cooldown policy throttle correctly and lets
--     a notification path target only the documents that need manual
--     download.
--
--  2. Source-file metadata. Embedded creation/modification dates from the
--     archived PDF/XLSX are the only reliable signal for "is this file
--     genuinely fresh, or has it been on the school's site for months?"
--     Captured at archive time (HTTP Last-Modified) and at extraction
--     time (PDF /CreationDate, /ModDate, /Producer; XLSX dcterms:created,
--     dcterms:modified). Powers freshness audits and seeds PRD 019's
--     change-intelligence layer with cross-school template-version
--     signal (e.g., the 2025-26 CDS Initiative XLSX template is dated
--     2025-09-26; schools that inherit it show that date as dcterms:created).

-- ─── 1. Extend ProbeOutcome constraint with bot_challenge ──────────────────

alter table public.archive_queue
  drop constraint if exists archive_queue_last_outcome_valid;

alter table public.archive_queue
  add constraint archive_queue_last_outcome_valid
  check (
    last_outcome is null
    or last_outcome in (
      -- ArchiveAction values (success outcomes from archiveOneSchool)
      'inserted',
      'refreshed',
      'unchanged_verified',
      'unchanged_repaired',
      'marked_removed',
      -- Failure outcomes (from PermanentError.category / TransientError.category)
      'dead_url',
      'auth_walled_microsoft',
      'auth_walled_okta',
      'auth_walled_google',
      'no_pdfs_found',
      'wrong_content_type',
      'file_too_large',
      'blocked_url',
      'transient',
      'permanent_other',
      -- Bot-challenge: WAF returned a challenge response. Distinct from
      -- wrong_content_type (school link returns generic HTML) and
      -- auth_walled_* (school requires SSO). Manual upload is the
      -- expected mitigation; see bot_challenged_documents view below.
      'bot_challenge'
    )
  );

-- ─── 2. Source-file metadata columns on cds_documents ──────────────────────

alter table public.cds_documents
  add column if not exists source_http_last_modified timestamptz,
  add column if not exists source_creation_date timestamptz,
  add column if not exists source_modification_date timestamptz,
  add column if not exists source_producer text;

comment on column public.cds_documents.source_http_last_modified is
  'HTTP Last-Modified header at the time the source bytes were fetched. '
  'Captured by supabase/functions/_shared/archive.ts. NULL for rows '
  'archived before this column existed and for sources whose host does '
  'not emit Last-Modified.';

comment on column public.cds_documents.source_creation_date is
  'Embedded creation timestamp from the source file (PDF /CreationDate or '
  'XLSX dcterms:created). Indicates when the school authored the file. '
  'Captured by tools/extraction_worker/source_metadata.py.';

comment on column public.cds_documents.source_modification_date is
  'Embedded modification timestamp from the source file (PDF /ModDate or '
  'XLSX dcterms:modified). Usually a closer freshness signal than '
  'source_creation_date because it reflects the last edit, not the '
  'template-derived creation date.';

comment on column public.cds_documents.source_producer is
  'Embedded /Producer (PDF) or /creator (XLSX) string. Useful for '
  'detecting which template a school used (e.g., CDS Initiative XLSX '
  'template vs. school-rolled-from-scratch).';

-- ─── 3. bot_challenged_documents view ──────────────────────────────────────
--
-- Single source of truth for "what's currently blocked behind a WAF and
-- needs manual download." The notification path in
-- .github/workflows/ops-extraction-worker.yml polls this view to mint
-- GitHub issues; a future operator dashboard can render it directly.

create or replace view public.bot_challenged_documents as
select
  d.id as document_id,
  d.school_id,
  d.school_name,
  d.cds_year,
  d.source_url,
  d.source_format,
  d.source_provenance,
  d.last_verified_at,
  d.updated_at as document_updated_at,
  q.last_outcome,
  q.last_attempted_at as last_challenge_at,
  q.last_error
from public.cds_documents d
left join public.archive_queue q
  on q.school_id = d.school_id
where d.extraction_status = 'failed'
  and d.source_sha256 is null
  and (
    q.last_outcome = 'bot_challenge'
    -- Defensive: include legacy rows whose error string matches the
    -- bot-challenge pattern but predates the typed category. The
    -- categoriseLegacyError() upgrade path will fix these on next attempt.
    or (q.last_outcome is null and q.last_error ilike '%cloudflare%')
    or (q.last_outcome is null and q.last_error ilike '%just a moment%')
  )
order by d.school_id, d.cds_year desc;

comment on view public.bot_challenged_documents is
  'PRD: archive observability. Documents whose source could not be '
  'archived because a WAF (Cloudflare, Imperva, etc.) returned a '
  'bot-challenge response. Source bytes never made it to Storage '
  '(source_sha256 is null), so manual download is required. The '
  'workflow at .github/workflows/ops-extraction-worker.yml polls '
  'this view daily and creates a GitHub issue per (school_id, '
  'cds_year), deduped by issue title.';

grant select on public.bot_challenged_documents to anon, authenticated;
