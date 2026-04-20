-- PRD 008: XSS mitigation for archived HTML.
--
-- Discovery: the sources bucket is public-read. A public object is served
-- with the content-type the uploader declared at .upload() time. To keep
-- browsers from executing <script> embedded in archived HTML bytes, the
-- Tier 6 storage layer uploads archived HTML with declared content-type
-- 'text/plain; charset=utf-8' (see normalizedContentType('html') in
-- supabase/functions/_shared/storage.ts). Supabase validates that
-- declared type against this allowlist, so 'text/plain' must also be
-- present — without it, the upload fails with "mime type text/plain;
-- charset=utf-8 is not supported" before any storage object is written.
--
-- 'text/html' stays in the allowlist as well for upstream flexibility;
-- no current code path uploads with that declared type.
--
-- Idempotent: the UPDATE replaces the allowlist array wholesale.
update storage.buckets
set allowed_mime_types = array[
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/html',
  'text/plain'
]
where id = 'sources';
