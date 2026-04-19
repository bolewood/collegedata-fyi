-- school_hosting_observations: append-only log of what the resolver
-- (or other observation sources) learned about a school's hosting
-- environment on each probe. Plus latest_school_hosting view that
-- exposes the most-recent observation per school for downstream
-- consumers that don't want history.
--
-- This is PR 3 of the URL hint refactor plan
-- (docs/plans/url-hint-refactor-and-hosting-jsonb.md). PR 4 wires the
-- resolver to write to this table; this PR is schema only.
--
-- Append-only by deliberate choice. Per the plan's review:
--   "Add a school_hosting_history table (or raw jsonb event log) so
--    hosting fact stability can be measured — this validates P2.
--    Without this, you cannot answer 'how stable are these facts?'"
--
-- The append-only model lets us answer "when did Adelphi flip from
-- public to auth-walled?" with a row-level event log instead of
-- losing prior state on every overwrite. The view handles the common
-- "what's the latest" query without callers needing a window function.
--
-- Storage cost: ~851 active schools × 1 observation/cron × monthly
-- cadence ≈ 10K rows/year. JSONB redirect_chain at p95 maybe 1KB →
-- ~10 MB/year. Trivial. A 5-year retention window is unbounded;
-- pruning policy can wait until the table actually grows.

create table public.school_hosting_observations (
  id                     bigserial primary key,
  school_id              text not null,
  observed_at            timestamptz not null default now(),

  -- Where the observation came from. Differentiates "resolver wrote
  -- this on a real probe" vs "operator hand-curated this fact" so
  -- consumers can filter on trustworthiness. Three sources today;
  -- additions are a code change (probe_outcome.ts may eventually
  -- need a parallel enum).
  observation_source     text not null
    check (observation_source in ('resolver', 'playwright', 'manual')),

  -- The seed URL the probe started from. Lets us reconstruct what
  -- happened: "this observation was made probing the cds_url_hint
  -- that pointed at intranet.adelphi.edu/wp-content/.../CDS.pdf and
  -- got redirected to login.microsoftonline.com." Without this,
  -- redirect_chain is harder to interpret.
  seed_url               text,

  -- The school's primary domain at observation time, captured from
  -- schools.yaml. Used by inferHosting() (PR 4) to compare against
  -- final_url_host for the same_origin vs third-party file_storage
  -- classification. Recorded here as well so historical observations
  -- remain interpretable if a school changes domains.
  origin_domain          text,

  -- The host the redirect chain settled on. For Adelphi this is
  -- login.microsoftonline.com; for a healthy Brown probe it's
  -- oir.brown.edu. Distinct from origin_domain — they only match
  -- when the school hosts on its own infrastructure.
  final_url_host         text,

  -- ─── Inferred dimensions (each nullable) ───────────────────────
  -- The resolver populates whatever it can determine from the probe.
  -- "unknown" is a deliberately-distinct value from NULL: NULL means
  -- "we didn't have enough signal to tell," "unknown" means "we
  -- looked and the signal was indeterminate." Both are common enough
  -- to be worth distinguishing.

  -- Content management system. Headers + URL patterns + body sniffs.
  cms                    text
    check (cms is null or cms in (
      'drupal', 'wordpress', 'sharepoint', 'static', 'custom', 'unknown'
    )),

  -- Where the actual CDS files are hosted. Detected by comparing the
  -- file-link hosts to origin_domain.
  file_storage           text
    check (file_storage is null or file_storage in (
      'same_origin', 'box', 'google_drive', 'sharepoint', 'dropbox',
      'intranet', 'mixed', 'unknown'
    )),

  -- Auth wall detected via final-URL host (login.microsoftonline.com,
  -- *.okta.com, accounts.google.com, etc.). Mirrors the values from
  -- ProbeOutcome's auth-walled categories minus the "auth_walled_"
  -- prefix.
  auth_required          text
    check (auth_required is null or auth_required in (
      'none', 'microsoft_sso', 'okta', 'google_sso', 'basic', 'unknown'
    )),

  -- Static HTML vs JavaScript-rendered. Heuristic: zero CDS-ish
  -- anchors AND small/SPA-shaped body suggests js_required.
  -- Conservative — defaults to 'unknown' rather than guessing.
  rendering              text
    check (rendering is null or rendering in (
      'static_html', 'js_required', 'unknown'
    )),

  -- WAF / CDN fingerprint from response headers (cf-ray, server,
  -- x-amz-cf-id, etc.).
  waf                    text
    check (waf is null or waf in (
      'none', 'cloudflare', 'akamai', 'imperva', 'aws_cloudfront',
      'fastly', 'unknown'
    )),

  -- ─── Outcome of THIS specific probe ────────────────────────────
  -- Mirrors archive_queue.last_outcome but per-observation rather than
  -- per-queue-row. Lets us correlate hosting facts with what
  -- happened: e.g., "Adelphi was auth_walled_microsoft on every
  -- observation in 2026-04 and then started returning unchanged_verified
  -- in 2026-07 — they un-walled."
  outcome                text
    check (outcome is null or outcome in (
      'inserted', 'refreshed', 'unchanged_verified', 'unchanged_repaired',
      'marked_removed', 'dead_url', 'auth_walled_microsoft',
      'auth_walled_okta', 'auth_walled_google', 'no_pdfs_found',
      'wrong_content_type', 'file_too_large', 'blocked_url',
      'transient', 'permanent_other'
    )),

  -- Free-text tail of the error message (truncated by the writer to
  -- ~200 chars) for diagnostics. The structured `outcome` is the
  -- queryable signal; this is the human-readable companion.
  outcome_reason         text,

  -- Per-hop redirect chain captured by the upgraded fetchText (PR 4).
  -- Shape: [{ from: url, to: url, status: int }, ...]. Null for
  -- observations recorded before PR 4 ships, and for observation
  -- sources (manual, playwright) that don't carry a chain.
  redirect_chain         jsonb,

  -- Operator-supplied freeform commentary. Used primarily on
  -- observation_source='manual' rows when a human is recording a
  -- hosting fact the resolver can't infer (e.g., "Box folder is
  -- public-read but unlisted; URL was provided by IR contact").
  notes                  text
);

comment on table public.school_hosting_observations is
  'Append-only log of what was observed about each school''s hosting environment on each probe. Resolver writes one row per archiveOneSchool call (PR 4). Consumers wanting current state should query latest_school_hosting view, not this table directly. Append-only model preserves history so we can answer how-stable-is-this-fact questions; pruning policy deferred until table size warrants.';

comment on column public.school_hosting_observations.observation_source is
  'resolver = automated probe via archiveOneSchool. playwright = automated probe via Playwright collector (for JS-rendered IR pages). manual = operator-supplied via tooling.';

comment on column public.school_hosting_observations.cms is
  'Detected content management system. drupal/wordpress/sharepoint inferred from URL patterns and headers; static for plain HTML hosts; custom for in-house systems; unknown when signal is indeterminate. NULL means we did not look or could not capture; differs from "unknown" which means we looked and could not tell.';

comment on column public.school_hosting_observations.file_storage is
  'Where the CDS files actually live. same_origin = on the school''s own infrastructure; box/google_drive/sharepoint/dropbox = third-party share. intranet = same domain but auth-walled. mixed = some files on origin, some on third-party.';

comment on column public.school_hosting_observations.auth_required is
  'Whether reaching the CDS files requires authentication. Inferred from redirect-chain final-URL host. Adelphi-style schools that put their archive behind Microsoft 365 SSO show as microsoft_sso.';

comment on column public.school_hosting_observations.rendering is
  'static_html = the resolver''s static HTML parser sees the CDS anchors. js_required = the page returns a small/SPA-shaped body and zero anchors, suggesting client-side rendering. The js_required classification is conservative; ambiguous cases stay "unknown".';

comment on column public.school_hosting_observations.outcome is
  'The ProbeOutcome category produced by this probe. Mirrors the same enum as archive_queue.last_outcome (kept in sync via supabase/functions/_shared/probe_outcome.ts).';

-- Index supporting the view (most-recent per school) and per-school
-- timeline queries ("show me Adelphi's last 12 observations").
create index school_hosting_observations_school_observed_idx
  on public.school_hosting_observations (school_id, observed_at desc);

-- ─── latest_school_hosting view ─────────────────────────────────────────
-- DISTINCT ON (school_id) ORDER BY observed_at DESC returns the most
-- recent observation per school. Postgres-specific but cheap given
-- the supporting index. Consumers query this view for "what do we
-- currently believe about this school?" without writing the
-- partitioned-window-function boilerplate themselves.
create view public.latest_school_hosting as
  select distinct on (school_id)
    school_id,
    observed_at,
    observation_source,
    seed_url,
    origin_domain,
    final_url_host,
    cms,
    file_storage,
    auth_required,
    rendering,
    waf,
    outcome,
    outcome_reason,
    redirect_chain,
    notes
  from public.school_hosting_observations
  order by school_id, observed_at desc;

comment on view public.latest_school_hosting is
  'Most-recent school_hosting_observations row per school. Use this for "what do we currently believe?" queries; query the underlying table for history. View is read-only by Postgres semantics — write via INSERT into school_hosting_observations.';

-- RLS off for now: this table is service-role-only (resolver writes,
-- internal tooling reads). When/if a public read API is added,
-- enable RLS and grant SELECT on latest_school_hosting to anon.
alter table public.school_hosting_observations enable row level security;

-- Service-role bypasses RLS by default; no policy needed for the
-- writer. Ad-hoc SELECT via the SQL editor uses service-role too.
-- Public read access is intentionally deferred to a future PR that
-- decides what dimensions to expose (notes/manual entries may
-- contain operator commentary not meant for public consumption).
