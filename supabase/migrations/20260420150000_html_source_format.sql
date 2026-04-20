-- PRD 008: Tier 6 HTML extraction.
--
-- Extends cds_documents.source_format CHECK to allow 'html' and the
-- sources bucket MIME allowlist to accept 'text/html' uploads. Archived
-- HTML is served as text/plain; charset=utf-8 via storage.ts'
-- normalizedContentType('html') → XSS mitigation for the public-read
-- bucket (the extractor reads bytes direct from Storage; browsers
-- reading the public URL never get 'text/html' so embedded <script>
-- never executes).
--
-- Idempotent: the constraint drop/add pattern is safe to re-run, and the
-- bucket UPDATE replaces the allowlist array wholesale.

alter table public.cds_documents
  drop constraint if exists cds_documents_source_format_valid;

alter table public.cds_documents
  add constraint cds_documents_source_format_valid
  check (source_format is null or source_format in (
    'pdf_fillable',
    'pdf_flat',
    'pdf_scanned',
    'xlsx',
    'docx',
    'html',
    'other'
  ));

comment on column public.cds_documents.source_format is
  'Source file format detected on discovery. pdf_fillable = unflattened '
  'PDF with AcroForm fields (Tier 2). pdf_flat = flattened PDF (Tier 4). '
  'pdf_scanned = image-only PDF + OCR (Tier 5). xlsx = filled Excel '
  'template (Tier 1). docx = filled Word template (Tier 3). html = '
  'structured HTML normalized to markdown and passed through the Tier 4 '
  'cleaner (PRD 008; producer=tier6_html). other = unhandled format.';

-- Extend the sources bucket MIME allowlist to include HTML. Upload
-- validation accepts text/html; stored objects are served as text/plain
-- via normalizedContentType('html') in supabase/functions/_shared/storage.ts.
update storage.buckets
set allowed_mime_types = array[
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/html'
]
where id = 'sources';
