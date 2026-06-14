-- Resolve Supabase Advisor "Security Definer View" findings.
--
-- Postgres views default to definer privileges, which can bypass RLS on
-- underlying tables. These public-schema views should execute with the
-- caller's privileges instead. The two serving views below remain public
-- because their base tables already have public SELECT policies:
--   - cds_manifest
--   - cds_field_observations
--
-- The two operator/internal views are made invoker-safe and are not exposed
-- to anon/authenticated roles:
--   - bot_challenged_documents
--   - latest_school_hosting
begin;

alter view public.bot_challenged_documents set (security_invoker = true);
alter view public.cds_field_observations set (security_invoker = true);
alter view public.latest_school_hosting set (security_invoker = true);
alter view public.cds_manifest set (security_invoker = true);

revoke select on public.bot_challenged_documents from anon, authenticated;
revoke select on public.latest_school_hosting from anon, authenticated;

comment on view public.bot_challenged_documents is
  'Operator-only archive observability view. SECURITY INVOKER so callers cannot bypass RLS on underlying tables.';

comment on view public.cds_field_observations is
  'PRD 019 source view: one normalized observed field per selected primary document and canonical field key. SECURITY INVOKER so RLS applies to underlying public serving tables.';

comment on view public.latest_school_hosting is
  'Operator-only most-recent school_hosting_observations row per school. SECURITY INVOKER; public read access remains intentionally deferred.';

comment on view public.cds_manifest is
  'Convenience view joining cds_documents to their most recent canonical artifact and archived source file. SECURITY INVOKER so public reads honor underlying RLS policies.';

commit;
