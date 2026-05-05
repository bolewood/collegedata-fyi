# Backlog

Tactical work items for collegedata.fyi. Higher-level milestones (M0 scaffolding, M1 finder, M2 extraction pipeline, M3 public API, M4 first contributor integration) live in [`v1-plan.md`](v1-plan.md). Frontend design and review decisions live in [`docs/prd/002-frontend.md`](prd/002-frontend.md). Frontend architecture is documented in [`docs/frontend.md`](frontend.md). This file tracks the smaller, between-milestone work that surfaces as we build.

Effort hints are rough estimates of CC-assisted time, not hand-coded human time.

Sections are ordered **Open → Resolved → Strategic context**. Every open item is above every resolved one so the file is scannable.

---

## Open

### Near-term operational polish

- **Ground-truth Tier 4 native-table candidates before LLM repair.** New
  `tier4_docling` artifacts preserve compact Docling native table cells and use
  the no-orphan-clusters layout tuning. Before running the LLM repair broadly,
  spot-check the 53 config-only fields from the tuning sample and the 103
  native-JSON-only candidates surfaced by the native table adapter. Promote
  section-specific native parsers only after deterministic validation.

- **Re-run Tier 4 LLM fallback for v0.3-compatible artifacts.**
  The selected-result contract now ignores stale fallbacks unless they match the
  selected Tier 4 base artifact by `base_artifact_id` or legacy
  `markdown_sha256 + cleaner_version`. The remaining work is operational:
  re-run `llm_fallback_worker.py` for the v0.3 Tier 4 corpus so compatible
  fallback values are available again where the deterministic cleaner still has
  gaps, then refresh `cds_fields` / `school_browser_rows`. Until then, stale
  fallback rows are preserved but excluded from public selected results.

- **Cross-table inconsistency notes.** Some schools' CDS files are internally inconsistent (Yale's C1 says women=772 enrolled, B1 says 769 enrolled; HMC's C1 enrollees-by-gender doesn't match the by-status sub-block). Decide whether to record these in `docs/known-issues/{school}.md`, in a per-extract `_notes` field, or both. They are not extraction bugs.

- **Header / metadata field fallback.** HMC's AcroForm has no value for `NAME` (school name, A.101) or respondent address fields, even though the visible PDF shows them. The Tier 2 extractor should probably mark these as "prefer external" so the manifest's `cds_documents.school_name` column is the canonical source for school identity.

- **Surface `unmapped_fields` from Tier 2 as a worker failure signal.** The Tier 2 extractor returns an `unmapped_fields` array for any populated AcroForm field whose `pdf_tag` has no entry in the canonical schema (e.g., a school using a modified or legacy template with renamed tags silently drops those fields). The stat is in the JSON output but the worker (`tools/extraction_worker/worker.py`) doesn't surface it. Add: (a) a log warning when `stats.unmapped_acroform_fields > 0`, (b) record the count in `cds_artifacts.notes.unmapped_count`, (c) optionally flip `extraction_status = extracted_with_gaps` (new enum value, requires migration) for consumers who want to filter on "complete extractions only." Raised by the pre-merge review of PR #1 as a medium-severity data-corruption risk.

- **`probe_urls.py` destroys schools.yaml formatting when it writes back.** It uses `yaml.dump()` with `sort_keys=False`, which preserves in-memory dict order but discards the section headers, comments, and section grouping that `build_school_list.py` produces. The idempotent fix is either (a) extract `build_school_list.py`'s `write_yaml()` into a shared helper both scripts import, or (b) have `probe_urls.py` write results to a side file like `tools/finder/probe_results.yaml` keyed by IPEDS ID, which `build_school_list.py` then reads during its next run. Option (b) is cleaner because it makes `probe_urls.py` purely additive and leaves `schools.yaml` generated-only from `build_school_list.py`.

- **`probe_urls.py` does GET where HEAD would be faster.** The probe loop issues a GET with `read_bytes=5000` for every pattern attempt, even though most attempts will 404. A HEAD-first strategy (check status + content-type from headers, only GET-sniff the HTML body when the HEAD returns 200 text/html) would cut probe time roughly in half. Minor optimization, matters more if we run against the full 2,400-school corpus.

- **Fix slugify state-suffix disambiguation.** Surfaced 2026-04-19 by the new `assert_no_duplicates()` guard in `tools/finder/build_school_list.py`: 12 inactive-cohort slug pairs collide because two real institutions share a name but our slugify drops state info. Examples: Anderson University (IN + SC), Bethany College (KS + WV), Bethel University (IN, MN, TN), Columbia College (MO + SC), Marian University (IN + WI), Union College (KY + NE), University of St Thomas (MN + TX), Westminster College (MO + PA + UT), and several more. The 11 active-school duplicates we just cleaned up (`tools/finder/dedup_audit.py` + `tools/finder/dedup_migrate.py`, 2026-04-19) were a different bug — wrong IPEDS IDs in old hand-curated entries — but this slugify gap will produce the same collision pattern any time a state's IPEDS cohort grows. **Fix shape:** in `tools/finder/build_school_list.py`'s `slugify()` (or wherever the school ID is minted), detect when two IPEDS rows would produce the same slug and append `-{state}` (lowercased STABBR) to disambiguate. Preserve any existing canonical slug a hand-curated entry already uses — only mint new disambiguated forms for the second-and-later collisions. **Why it matters:** today these schools all live in the inactive cohort so the active-corpus invariant holds, but as soon as we promote one to active without a state suffix it'll collide with its sibling and silently overwrite or fail to ingest. The build-time guard now flags this loudly (warning, not error, for inactive); make it an error once the slugify fix lands. Lincoln University (`lincoln-university-mo` + `lincoln-university-pa`) is the existing reference pattern. **Effort:** ~1 hour for the slugify change + a re-build of schools.yaml + verifying no active-school IDs change.

- **Two schools pointing at the same archived file (U Maine System Central Office + U Southern Maine) — production DB cleanup pending.** schools.yaml side fixed 2026-04-15 in commit `59982f7` (flipped `university-of-maine-system-central-office` to `scrape_policy: verified_absent`). **Still pending: production DB cleanup.** The stale `cds_documents` row (id `6d0ef326-ce81-4f11-8214-125e29c1cd4f`, cds_year `2025-26`, status `extraction_pending`) and its `archive_queue` entry are still live. Operator action: either `UPDATE public.cds_documents SET participation_status = 'verified_absent', extraction_status = 'not_applicable' WHERE id = '6d0ef326-ce81-4f11-8214-125e29c1cd4f';` (preserves history) or `DELETE` outright; plus `DELETE FROM public.archive_queue WHERE school_id = 'university-of-maine-system-central-office';`. Broader class: `schools.yaml` entries populated via `last_method: brave` with `search_fallback_tried: true` should have their hint URLs cross-validated against the school's own domain before being accepted — a separate follow-up.

### Trigger-on-volume

- **PRD 015 M7 — first-party CDS source submission backend.** Replace
  Formspree on the school detail + coverage pages with first-party
  intake: an `archive-submit` edge function that writes into a new
  `source_submissions` table (school_id, url, note, submitter_email,
  ip, submitted_at, status), plus an operator review surface (probably
  `/operator/submissions` behind service-role auth) to triage
  accepted/rejected and feed accepted URLs into the resolver as hints.
  **Why deferred:** Formspree handles low-volume submissions fine and
  every submission already routes to `anthony+collegedata@bolewood.com`.
  Build this when inbox volume makes the manual workflow expensive —
  rough trigger is ~10+ submissions per week, or when the first abuse
  pattern appears (spam / off-topic / non-CDS URLs requiring filter).
  **Shape:** ~1 day of work — table + RLS + edge function + minimal
  operator page + swap the SubmissionForm endpoint via env var. The
  M5 SubmissionForm component already accepts an env-driven endpoint,
  so the frontend swap is one config change.

### Frontend polish

- **Academic positioning v1.1 follow-ups from pre-merge review.** Confirm
  whether the range strip should plot the student's score as a tick or whether
  the v1 right-column score display is the intended design decision; add focused
  component tests for empty, loaded, ACT-null, test-optional, stale-CDS, and
  wrong-file states; broaden scoring fixtures beyond the current spread variants;
  surface GPA submit rate (`C.1202`) and the user's selected GPA scale in the
  card; consider route-mocked Playwright fixtures so live Bowdoin/MIT extraction
  changes cannot make the e2e flaky. **Effort:** ~0.5-1 day.

- **Queryable browser CSV export pagination.** The `/browse` MVP exports the current browser result set through one Edge Function call capped at `page_size=500`. That is fine for current launch filters, but a broad export should page through all results or move export server-side before result sets grow. **Effort:** ~1 hour.

- **OG images.** Per-school social cards with school name + key stats. Would improve link previews on Twitter/Slack/Discord. **Effort:** ~1 hour using Next.js OG image generation.

- **Server-side stats RPC.** The landing page fetches public count/table data to compute stats. At 10K+ docs this becomes wasteful. Fix: Postgres function or view that returns pre-computed stats. **When:** when the corpus exceeds ~5,000 documents. Not urgent now.

- **Singleton Supabase client per-request.** The current `supabase.ts` creates one module-level client shared across all requests. This works for the anon key (stateless) but doesn't follow the `@supabase/ssr` pattern recommended for Next.js server components. Low risk for a read-only app with no auth, but worth cleaning up if auth is ever added. **Effort:** ~15 minutes.

- **FieldsView Phase 2 — reconstructed CDS tables.** Phase 1 (PR #14) shipped the textbook gutter with per-subsection KV groups; the design's reference (`fields-c.jsx` / `fields-b.jsx` from the Claude Design handoff) goes further and renders each subsection as the actual CDS table it came from — Men/Women/Total columns on B1, importance-level dot matrix on C7, P25/P50/P75 on C9, income brackets on H2A. The schema already carries the pivot dimensions (`category`, `cohort`, `student_group`, `gender`, `residency`, `unit_load`) on every field; we just need to (1) thread those dimensions through `FieldValue` so the frontend can read them — today the `tier4_cleaner` populates `section`/`subsection` but not the others — and (2) write small per-subsection layout descriptors that say "rows = these dim values, cols = these dim values" for the top ~15 high-traffic subsections (B1, B2, C1, C7, C9, C11, H2A, H6, J1, etc.). Long-tail subsections continue to render as KV rows from Phase 1. **Also part of this work:** "— not provided" rendering for known-but-missing fields, gated on per-CDS-year schema awareness so older years don't show fields-that-didn't-exist as missing. **Effort:** ~1-2 days (~half day to thread dimensions, ~1 day for the 15 layout descriptors and the reconstruction loop).

### Queryable browser backend polish

- **PRD 019 Top 200 freshness and review gate.** Core change-intelligence
  substrate is shipped, but public reporting is blocked on enough pairable
  latest/prior CDS rows for the watchlist and human verification of every
  `major` and report-bound `newly_missing` event. First calibration dry-run:
  30 schools, 4 pairable latest/prior rows, 36 events, 2 major, 11 notable,
  4 review candidates. Next work: refresh/drain more 2025-26 watchlist rows,
  apply the projector intentionally, and review/publish only confirmed events
  with `tools/change_intelligence/review_change_event.py`. **Effort:** scoped
  operational drain + review pass.

- **PRD 019 public methodology/report layer.** The deterministic projector,
  annual-report seed, school-page card, review CLI, and operator-only `/changes`
  digest exist. Still open: public methodology page for change intelligence,
  publication-grade annual report, charts, and public `/changes` launch after
  calibration. Keep external macro context (WICHE, Census, IIE, NAFSA) out of
  `cds_field_change_events`; it belongs in report/editorial copy. **Effort:**
  depends on freshness and review queue size.

- **GPA scale-resolution sprint for academic positioning.** PRD 016 deliberately
  keeps GPA out of tier scoring because CDS C.12 does not consistently state
  whether average high-school GPA is weighted, unweighted, or on another local
  scale. Focused follow-up: extract scale evidence from source PDFs where
  available, define an `unknown_scale` fallback, manually audit 100 schools
  across selectivity tiers, and decide whether `school_browser_rows` can ever
  responsibly carry normalized GPA. Until then, the positioning card displays
  school average GPA beside the entered GPA only. **Effort:** focused sprint.

- **Audit Tier 1 XLSX academic-profile field mapping.** PRD 012 Phase 0 found SAT/ACT `cds_fields` parse errors in XLSX rows where C9 fields contain values such as "Very Important", "Important", "Considered", "Percent", or "Number". That points to schema/template alignment drift in the XLSX extractor for at least some 2024-25 workbooks. The PRD 012 browser projection now range-checks and nulls invalid score values, so these should not leak into `school_browser_rows`, but the underlying Tier 1 mapping still needs a focused audit before score fields are treated as launch-certified for XLSX publishers. **Effort:** ~2 hours.

- **Move `browser-search` ranking into SQL if it becomes hot.** The MVP Edge Function reads the materialized `school_browser_rows` table and applies the pure ranking contract in TypeScript. That kept the launch slice small and testable. If corpus size or traffic grows, port the same required-field and latest-per-school semantics into a Postgres RPC using window functions. **Effort:** ~2-3 hours.

### Larger features / future tiers

- **Tier 3 DOCX extractor (PRD 007).** Revised plan shipped 2026-04-29 in [PRD 007](prd/007-tier3-docx-extraction.md). Primary path is a deterministic OOXML SDT reader keyed by schema `word_tag` values, same lookup pattern as Tier 2. Fallback path is a measured Docling DOCX structural adapter that reuses Tier 4 cleaner/table logic for SDT-stripped Word files before considering any bespoke Word-table parser. Addressable corpus today is ~30-50 documents (Kent State's 14 SDT-preserving files are the largest family). The format sniffer now routes DOCX correctly; the remaining work is the extractor itself.

- **Tier 4 cleaner — continue resolver coverage beyond the core product surfaces.** [PRD 005](prd/005-full-schema-extraction.md)'s Phase 6 architecture shipped 2026-04-20 (commit `aecca9b`): the section-family resolver framework backed by a shared `SchemaIndex` took the cleaner from 72 -> ~380 fields (Harvard 382, Yale 390, Dartmouth 343). PRD 016B and PRD 018 added targeted C21/C22 and H1/H2/H2A coverage. Remaining work is continuing to add resolvers for thinner sections as specific schools surface gaps; the ceiling is 1,105 fields, but full-schema parity is not urgent.

- **Tier 4 cleaner — Docling flat-text table recovery.** Dartmouth's C10 and Harvard's Submitting SAT/ACT block are cases where Docling emitted a two-column table as two sequential paragraphs (all labels first, then all values in the same order) instead of interleaved table rows. Current cleaner has no recovery path for this shape — the `_INLINE_PATTERNS` fallback handles single-field cases but not these multi-row column-flattened ones. **Fix shape:** detect consecutive N-line blocks of label-like paragraphs (each starting with "Percent..." or matching the row-label pattern of a known table) followed by N value-like paragraphs (e.g. `\d+%`), and pair them positionally. Only worth building if corpus survey shows many schools hitting this pattern — currently it's a known miss for ~2 fields per affected school.

- **Retire `cds_year` as discovery output (ADR 0007 follow-up / "Stage D").** ADR 0007 Stage C landed as docs-only because `normalizeYear` turned out to be load-bearing inside `pickCandidates` — it's the partitioning signal that lets a multi-year landing page like Lafayette's 19-year archive fan out into 19 distinct `cds_documents` rows without colliding on `UNIQUE (school_id, sub_institutional, cds_year)`. Deleting `_shared/year.ts` cleanly requires first dropping `cds_year` from that unique constraint and rekeying on something URL-derived. **What to build:** (1) migration replacing `UNIQUE (school_id, sub_institutional, cds_year)` with `UNIQUE (school_id, sub_institutional, source_url_hash)` (or `source_sha256` if we're willing to couple uniqueness to the file contents rather than the source URL — tradeoff is whether a republished identical PDF at a new URL should be a new row); (2) rework `pickCandidates` in `supabase/functions/_shared/resolve.ts` to partition on URL uniqueness instead of `year`, with `chosen = dedupe-by-url(clean-set)` and no year-based branching; (3) delete `supabase/functions/_shared/year.ts` and `_shared/year.test.ts`; (4) remove the `cds_year` NOT NULL constraint or drop the column entirely depending on whether `cds_manifest` consumers still read it; (5) update `cds_manifest.canonical_year` expression to draw only from `detected_year` (falling back to NULL/"unknown" for undetected rows); (6) re-run the full-corpus drain and compare fan-out vs the pre-Stage-D baseline. **Why it matters:** closes the loop on ADR 0007. Today `cds_year` is a best-effort URL guess that Stage B already overrides via `detected_year`; keeping it as a NOT NULL unique-constraint participant means the resolver still has to produce plausible-looking year strings (or `UNKNOWN_YEAR_SENTINEL`) and the year module cannot be deleted. This is dead weight with an active footgun — any future resolver work has to reason about URL year parsing even though the result is purely decorative. **Effort:** ~3-4 hours including the migration, test updates, and a re-drain. Not urgent — `detected_year` already gives consumers the right answer via `cds_manifest.canonical_year`. Defer until the schema is otherwise due for a migration. **Cross-references:** [ADR 0007](decisions/0007-year-authority-moves-to-extraction.md) Shipped section; `supabase/functions/_shared/year.ts` header comment.

- **Public CDS upload form.** A web-accessible upload pathway at `collegedata.fyi/upload` (or similar) where any visitor can contribute a CDS file for a school + year we don't have. The operator-only precursor shipped 2026-04-19 as `supabase/functions/archive-upload` + `tools/upload/upload.py` — same edge function, same magic-byte validation, same provenance plumbing — just gated by service-role auth. The public version needs what the operator version deliberately skips:

  1. **Trust model.** Anonymous uploads invite abuse. Options: CAPTCHA + rate limit (minimum viable), emailed magic link (friction, but we know who), OAuth via GitHub/Google (better identity, still free). Start with CAPTCHA + IP rate limit; revisit if abuse actually happens.
  2. **Moderation queue.** Uploads land in a new `pending_uploads` table (not straight into `cds_documents`) with status=pending + uploader metadata. An admin view lists pending rows, previews the PDF, accept/reject with one click. On accept, the edge function runs the same archive path `archive-upload` uses today with `source_provenance='community_contribution'` (new CHECK value).
  3. **Content validation.** Magic-byte check (already written). Also: PDF content year detection via the existing `detect_year_from_pdf_bytes` — we can auto-verify the uploader's claimed year matches page 1. Mismatch → auto-reject (or flag for human review).
  4. **Duplicate-of-existing suppression.** If the uploaded sha256 matches what we already have, thank the uploader and no-op.
  5. **Public attribution.** Optionally credit contributors in a "Contributors" page. Controversial — some contributors may not want attribution; some schools might object to community-sourced archiving even if the file itself is already public. Defer.
  6. **Storage abuse.** 50 MB/file bucket limit already enforced. IP rate-limit (e.g., 5 uploads/hour) + per-file-size cap prevents anyone from burning storage as an attack surface. Add total-per-day-per-IP if needed.
  7. **Frontend surface.** A `/upload` page on the Next.js app. Drag-drop file, select school (search-autocomplete from the schools.yaml corpus), select year from dropdown, optionally paste the URL they got it from. Tiny terms-of-service checkbox ("I am the uploader or authorized to share this; this is a public educational document").

  **Effort estimate:** 1-3 days CC. Bulk of the work is the moderation view (Next.js page + minimal admin auth) and the trust model decision. The actual edge function is 70% done — `archive-upload` does the archiving; the public wrapper just adds the pending-queue detour + CAPTCHA.

  **When to build:** after the operator uploader has been used for at least a few weeks and the workflow pain is clearly "I wish someone else could do this for me" rather than "I need this for one school." Preservation-archive story (the strongest launch narrative — "help us archive the public-accountability documents of American higher education") is significantly stronger with a community-upload surface than without. Parks this alongside the HN launch planning (see Strategic context → "Launch the preservation archive story to IR professionals").

- **Score Reducto reference extracts against the HMC ground truth.** `tools/extraction-validator/score_tier2.py` already handles the join against `harvey-mudd-2025-26.yaml` via the committed id map. Adapting the scorer to read Reducto's free-form output (nested by section, not keyed by question_number) would produce the first real apples-to-apples Tier 2 vs Reducto vs Docling comparison. The HMC ground truth has 31 fields — a meaningful sample, not a spot check. Useful for the "when is Reducto worth paying for?" decision on Tier 4 coverage.

### Deferred (explicit trigger conditions to re-open)

- **[DEFERRED 2026-04-28 per PRD 014 closeout] Tier 4 schema-derived phrase matcher / M6.** PRD 014's M6 would replace the remaining 2025-26 hard-coded Tier 4 phrase mappings with schema-derived matching. Do not start this now: M4 finished as `modest_delta`, all value assertions passed after the narrow C1 fix, and the important browser-facing metrics are covered by the equivalence/projection layer. **Trigger conditions:** revisit when adding 2026-27 schema support, when a full Tier 4 corpus drain becomes operationally necessary, or when validation finds repeated year-specific phrase misses that the current resolver/fallback path cannot cover.

- **[PARTIALLY SHIPPED 2026-04-28] CI expansion beyond minimal checks.** Minimal GitHub Actions CI now runs Python projection/cleaner tests, Deno Supabase function tests, and a Next.js build. Deliberately still not included: full Docling corpus drains, Tier 4 fixture regeneration gates, deployment, or scheduled extraction work. Expand only when a concrete regression class appears or a second contributor needs stronger pre-merge guardrails.

- **[DEFERRED 2026-04-20 per PRD 009 /autoplan review] Periodic re-check job for preservation.** The `last_verified_at` / `removed_at` columns on `cds_documents` are useless without a scheduler that re-HEADs every known source URL on some cadence (weekly is probably fine) and flips `removed_at` when a URL starts 404ing. **Reason deferred:** both CEO voices during [PRD 009](prd/009-last-mile-ci-and-preservation.md) /autoplan review flagged that the archive narrative is "incidental" per v1-plan.md (removals "well under 10%"), so a preservation cron isn't load-bearing yet. **Trigger conditions:** revisit when (a) a user reports a school removed their CDS and the manifest doesn't reflect it, OR (b) the archive narrative becomes the lead product claim (e.g., post-HN launch framing). Design notes from the original PRD 009 review are preserved in that file — if this ships later, it needs: 2-consecutive-observation threshold, GET fallback for WAF'd hosts, `source_provenance='school_direct'` filter, compare-and-set to avoid races with discovery.

- **[DEFERRED 2026-04-20 per PRD 009] Protect service role key from CI logs.** Generic hygiene: when a Python cron job eventually runs in GitHub Actions, `SUPABASE_SERVICE_ROLE_KEY` lives in GitHub Secrets and should never end up in stdout, stderr, or error-report attachments. Recommendation at that time: (a) never `print()` the key, (b) use supabase-py's built-in masking, (c) rely on GHA's automatic `::add-mask::` for `${{ secrets.X }}` references, (d) audit error handlers for `SUPABASE_*` traceback leaks. The original plan had a grep-check workflow step that /autoplan's Eng review flagged as potentially leaking the secret into shell history (worse than the problem it was solving) — drop that design. Deferred alongside the test framework + CI item above; triggered when GHA workflows are added.

### Blocked on external (Reducto sponsorship)

- **Reducto schema-constrained extraction mode.** Not on the critical path now that Docling is the Tier 4 extractor. If Reducto sponsorship materializes, re-running with their schema parameter pinned to the canonical CDS schema would close the key-naming drift between schools. Reference extracts at `tools/extraction-validator/references/reducto/`.

- **Reducto citations enabled.** Per-field bbox + page + source-text provenance. Only relevant if Reducto sponsorship materializes.

- **Reducto pricing investigation.** Only relevant if sponsorship does not materialize and we need to self-fund.

---

## Resolved

Reverse chronological.

### 2026-05-05

- **[RESOLVED 2026-05-05] ~~PRD 019 change intelligence alpha.~~**
  Shipped the deterministic PRD 019 substrate: `cds_field_observations`,
  `cds_field_change_events`, `cds_field_change_event_reviews`, calibration and
  Top 200 watchlist seeds, `tools/change_intelligence/project_change_events.py`,
  `rules.yaml`, annual Markdown/CSV report seed output, review/publish CLI,
  public-gated `WhatChangedCard`, and the operator-only `/changes` digest. The
  pre-PRD spike passed with 85 pairable schools, 392 candidate events, 282 clean
  comparable events, and 31 reporting-status candidates. Public reporting remains
  gated by watchlist freshness and human verification; follow-ups stay open
  above.

### 2026-05-03

- **[RESOLVED 2026-05-03] ~~Source routing and fresh CDS extraction priority.~~**
  The extraction worker now orders pending/retry rows by recency before older
  backlog rows, and both the CLI and ops workflow expose `--min-year-start` for
  fresh-year drains. ZIP source sniffing is content-aware, so DOCX no longer
  routes as XLSX; headless/archiver downloads preserve document-like response
  bytes even when publisher headers are misleading. This cleared the 2025-26
  pending queue after the manual fresh-year drain: 101 extracted, 16 failed, 1
  not applicable, 0 pending.

- **[RESOLVED 2026-05-03] ~~PRD 018 merit profile data asset.~~**
  Shipped `school_merit_profile`, joining latest primary 2024-25+ CDS Section H
  merit/need-aid fields to selected Scorecard affordability/outcome fields.
  Targeted H1/H2/H2A cleaner work and redrains populate the school-page
  `MeritProfileCard` and the public API. The card copy explicitly treats H2A
  as school-reported institutional grant data, not a personalized estimate.

- **[RESOLVED 2026-05-03] ~~PRD 017 match list builder.~~**
  Shipped `/match` with `MatchListBuilder`, list ranking helpers, local-only
  save/share codes, directory/Scorecard enrichment, and school-page document
  ledger cleanup. The default sort puts stronger-fit schools first and long CDS
  histories now show the three most recent files before the expandable ledger.

- **[RESOLVED 2026-05-03] ~~PRD 016B admission strategy card and redrain.~~**
  Shipped `AdmissionStrategyCard`, `school_browser_rows` admission-strategy
  columns, C21/C22 Tier 4 cleaner coverage, effective ED/wait-list semantics,
  `admission_strategy_card_quality`, and the targeted Tier 4 redrain. The
  implementation uses ED and EA names directly rather than a vague "early plan"
  label in product copy.

### 2026-05-02

- **[RESOLVED 2026-05-02] ~~PRD 016 academic positioning card.~~**
  Shipped school-page academic positioning backed by `school_browser_rows`
  SAT/ACT bands, selectivity context, localStorage-only student profile state,
  methodology page copy, and unit tests for fit tiering. GPA remains caveated
  because CDS C.12 scale semantics are not consistently machine-resolvable.

### 2026-04-29

- **[RESOLVED 2026-04-29] ~~Coverage data-quality launch cleanup.~~**
  The PRD 015 audit found three launch-trust issues in the coverage layer:
  slug fragmentation between schools.yaml canonical slugs and Scorecard-style
  mirror slugs, Bucknell/Drexel missing from `/coverage`, and stale
  administrative system-office rows with CDS documents. Shipped
  `20260429190000_launch_coverage_data_quality.sql`: corrects Bucknell and
  Drexel IPEDS IDs in existing rows, repairs their `institution_directory`
  / `institution_slug_crosswalk` canonical slugs, canonicalizes
  non-conflicting `cds_documents` rows through the primary schools.yaml
  crosswalk, preserves remaining old aliases as redirects, marks the four
  system offices `verified_absent` / `not_applicable`, deletes their
  queue entries, and refreshes `institution_cds_coverage`. Also corrected
  `tools/finder/schools.yaml` so future loads preserve `bucknell` and
  `drexel`, with a regression test pinning their NCES UNITIDs.

- **[RESOLVED 2026-04-29] ~~Repo-native Playwright smoke tests.~~**
  Added `web/tests/smoke.spec.ts` and `web/playwright.config.ts` with
  smoke coverage for homepage institution search, `/coverage`, `/browse`
  live rows + source-link HTTP resolution, `/api/facts/mit` JSON, and
  mobile body-overflow checks. The web CI job now installs Chromium and
  runs `npm run test:smoke` against the production Next build.

- **[RESOLVED 2026-04-29] ~~API launch copy drift.~~** README curl examples
  now include the required public Supabase anon key headers, the Show HN
  draft no longer claims raw PostgREST is headerless, and the facts endpoint
  no longer links to a nonexistent `/api/facts/{school_id}/full` route.

### 2026-04-28

- **[RESOLVED 2026-04-28] ~~Scheduled/manual ops worker path.~~** Added `.github/workflows/ops-extraction-worker.yml`, separate from PR CI. It supports a daily small pending-row drain and manual dispatch with `limit`, `school`, `include_failed`, and low-field threshold inputs. GitHub-hosted runs are capped at 100 rows; full Docling corpus drains stay on a laptop or self-hosted runner. `worker.py` now writes `--summary-json` with processed count, failures, mean fields, low-field docs, extraction counts, and browser projection counts, and the workflow uploads that summary plus the worker log as an artifact.

- **[RESOLVED 2026-04-28] ~~Incremental browser projection refresh + minimal CI.~~** Extraction drains now refresh `cds_fields` and `school_browser_rows` per newly written canonical artifact, with `--skip-projection-refresh` available for isolation runs and `--seed-projection-metadata` available after schema/alias changes. Per-document replacement is atomic through `replace_browser_projection_for_document(...)`. Full projection rebuilds remain the operator path after migrations or projection logic changes. Added minimal GitHub Actions CI for Python unit tests, Supabase Deno tests, and a Next.js build.

- **[RESOLVED 2026-04-28] ~~Browser academic-profile backend expansion (PRD 012).~~** Shipped SAT/ACT submission-rate and percentile columns into `school_browser_rows`, added companion submit-rate metadata to `browser-search`, and refreshed production after the Tier 4 v0.3 drain. Public `cds_fields` moved from 113,836 to 217,910 rows (+104,074, +91.4%); mean projected field rows per processed `2024+` document moved from 224.5 to 433.2. `school_browser_rows` now has 469 rows after stale projection rows were cleared before rebuild. SAT/ACT fields are backend-queryable and exported, but not exposed as default visible filters until the UI can show submit-rate context. Follow-ups remain open above for the XLSX academic-profile mapping audit and future score-filter UI.

### 2026-04-27

- **[RESOLVED 2026-04-27] ~~Tier 4 v0.3 deterministic layout-overlay cleaner.~~** PRD 0111A's Docling improvement spike found a high-leverage path before LLM repair: keep the tuned Docling markdown/native-table pipeline, but pass embedded PDF layout text from `pypdf` into the cleaner as a supplemental, deterministic gap-fill overlay. The page-audit sequence covered Farmingdale, Kenyon, and Michigan State, then re-ran the same ten low-coverage 2024-25+ Tier 4 fixture PDFs. Total recovered canonical fields moved from 5,066 after the Farmingdale pass to 5,602 after the generalized v0.3 pass (+536), with Michigan State moving 336 -> 486. The overlay added coverage for A general information, B graduation grids, C admissions layouts, D transfer, E/F checkbox grids, G expenses, H aid, I faculty/class-size, and J disciplines while leaving ambiguous or visibly blank cells blank. Producer version bumped to `tier4_docling` `0.3.0` so the full corpus drain writes fresh artifacts. Follow-ups remain open above for stale LLM fallback invalidation and projection automation.

### 2026-04-26

- **[RESOLVED 2026-04-26] ~~Queryable school browser MVP (PRD 010).~~** Shipped backend + frontend. Backend surfaces: `cds_field_definitions`, `cds_metric_aliases`, `cds_selected_extraction_result`, `cds_fields`, `school_browser_rows`, and `browser-search`. Launch projection populated 113,836 field rows and 472 browser rows from 507 `2024-25+` documents. Frontend shipped at [`/browse`](https://www.collegedata.fyi/browse) with launch-certified filters, latest-per-school ranking, answerability counts, source links, pagination, and CSV export. Key semantics preserved: direct aliases only in `cds_fields`; derived `acceptance_rate` / `yield_rate` in the serving layer; `sub_institutional` preserved; rates stored fractionally; Tier 4 fallback cleaned overlay fills gaps only; `is blank` does not create a required field for answerability. Follow-ups remain open above for projection automation, SQL-side ranking, automated Playwright smoke tests, and export pagination.

### 2026-04-20

- **[RESOLVED 2026-04-20, commit `aecca9b`] ~~Tier 4 cleaner full-schema expansion — Phase 6 (PRD 005).~~** Took the cleaner from 72 to ~380 fields via 14 section-family resolvers backed by a `SchemaIndex` loaded from `cds_schema_2025_26.json`. Each resolver isolates a single CDS subsection so false-positive matches ("Total", "Other") can't leak across families. Hand-coded `_FIELD_MAP` stays as the regression-safe baseline; resolvers fire after it and only claim fields not yet populated. Per-school coverage delta: Harvard 72 → 382, Yale 70 → 390, Dartmouth 50 → 343. Ground-truth expansion: 133/133 Harvard, 49/51 Yale, 47/49 Dartmouth; all previously-passing fields preserved. Complementary to [PRD 006](prd/006-llm-fallback.md) — PRD 005 resolvers handle well-structured tables; PRD 006 LLM fallback handles the structural-failure tail. **Remaining follow-up** (Open section above): keep adding resolvers opportunistically for the thinner sections as specific schools surface gaps.

- **[RESOLVED 2026-04-20] ~~ADR 0008: Takedown process for archived documents.~~** Shipped as [`docs/decisions/0008-takedown-process.md`](decisions/0008-takedown-process.md) + transparency-log scaffold at [`docs/takedowns.md`](takedowns.md). Three-step protocol: verify via `.edu` email matching school domain, apply by flipping `participation_status='withdrawn'` + `removed_at=now()`, log each takedown in the public transparency file. The frontend's `cds_manifest` selects in `web/src/lib/queries.ts` filter out `participation_status IN ('withdrawn','verified_absent')` so withdrawn docs disappear from the school directory, school page, and sitemap; PostgREST API keeps the rows visible (transparency). Bytes-removal-to-separate-bucket is deferred per PRD 009 and triggered by the first request that demands it. Linked from `CONTRIBUTING.md` under a new "If you represent a school and need a document removed" section.

- **[RESOLVED 2026-04-20] ~~Tier 6 HTML extractor (PRD 008).~~** Shipped as `tools/extraction_worker/html_to_markdown.py` — an 80-line BS4+lxml normalizer that converts CDS-shaped HTML into the pipe-delimited markdown shape the Tier 4 cleaner already consumes. No bespoke parser — reuses `tier4_cleaner._parse_markdown_tables`, `_normalize_label`, `SchemaIndex.filter`. Worker adds `_run_tier6` + HTML sniff case + routing. MIT 2024-25 first drain: 152 schema fields populated across sections B, C, F, G, H, I. **XSS mitigation** (critical finding during /autoplan review): the `sources` bucket is public-read; adding `text/html` to the allowlist would mean archived HTML with `<script>` executes at the Supabase CDN URL. Fix: `normalizedContentType('html')` returns `'text/plain'`, and the bucket allowlist includes `text/plain` so the upload's declared content-type matches. Verified: public HEAD returns `content-type: text/plain` + `content-security-policy: default-src 'none'; sandbox`. Shipped files: `html_to_markdown.py`, `worker.py` (additive), migrations `20260420150000_html_source_format.sql` + `20260420160000_html_xss_mitigation_allow_plain.sql`, `storage.ts` (html recognition + text/plain override), `format.ts` (HTML badge). PRD reframed during /autoplan from bespoke Tier 6 extractor + alias table to cleaner reuse — both CEO voices and eng subagent converged on the reuse path. **Follow-ups:** (a) auto-discover HTML-native publishers at resolver time (currently operator-curated via `manual_urls.yaml` + `force_urls`); (b) archive MIT historical years (2021-22, 2022-23, 2023-24 HTML pages); (c) `web/src/components/DocumentCard.tsx:69` hardcodes "Download PDF" link text — cosmetic bug surfaces on any non-PDF format (also affects existing xlsx/docx archives).

- **[RESOLVED 2026-04-20] ~~Tier 4 LLM fallback (PRD 006).~~** Schema-aware LLM repair layer on top of the Tier 4 cleaner. Phase 0 (benchmark harness) + Phase 1 (production worker, cache table, merged view in the frontend) shipped in a single day. 244 2024-25 docs backfilled with mean 28.2 fields added per doc beyond the cleaner baseline, $14.08 total Anthropic spend (Claude Haiku 4.5 with prompt caching), zero regression on audited ground truth. Target subsections: H5-H8 (loans/aid), C13-C17 (deadlines/policies), D13-D16 (transfer credit), G5 (estimated expenses). Artifacts land in `cds_artifacts` with `producer='tier4_llm_fallback'`; `cds_llm_cache` keys on `(source_sha256, markdown_sha256, section_name, schema_version, model_name, prompt_version, strategy_version, cleaner_version, missing_fields_sha256)` so re-runs on unchanged inputs cost $0. Consumer merge via `web/src/lib/queries.ts:fetchExtract` (Mode B: cleaner wins, fallback fills gaps). See [`docs/tier4-llm-fallback.md`](tier4-llm-fallback.md) for operator runbook + [`docs/research/tier4-cleaner-learnings-for-llm-fallback.md`](research/tier4-cleaner-learnings-for-llm-fallback.md) for the measured gaps that informed subsection selection. **Next expansions:** backfill earlier years (2023-24, 2022-23, ...); expand target subsections as `corpus_survey_tier4.py --include-fallback` surfaces sections where the fallback pays for itself; batch thin subsections (C15, D15, D16) into shared calls to cut per-call overhead.

- **[RESOLVED 2026-04-20] ~~Tier 1 XLSX extractor.~~** Shipped as `tools/tier1_extractor/extract.py`. The CDS Excel template's Answer Sheet lookup formulas give a deterministic `{question_number: (sheet, cell_ref)}` map; applying that map to any filled XLSX reads all populated cells in one pass. 289 tier1_xlsx artifacts written across the first full drain (2026-04-20), median 307 fields/doc, max 782. Routed via `source_format='xlsx'` through the worker.

- **[RESOLVED 2026-04-20] ~~Tier 5 scanned-PDF extractor.~~** Shipped as a config flag on Tier 4: the worker passes `force_ocr=True` when `source_format='pdf_scanned'`, which makes `tier4_extractor.extract()` swap in `EasyOcrOptions(force_full_page_ocr=True)`. Verified end-to-end on Kennesaw State 2023-24 (0 fields under default lazy OCR → 172 fields under force-OCR on 31 scanned pages). No separate Tier 5 extractor — it's a one-parameter variant of Tier 4 with EasyOCR forced on every page. Requires `easyocr` in `tools/extraction_worker/requirements.txt`.

- **[RESOLVED 2026-04-20] ~~Use `api.collegedata.fyi` as the Supabase URL.~~** `NEXT_PUBLIC_SUPABASE_URL` flipped to `https://api.collegedata.fyi` in `web/.env.local` alongside the PRD 006 consumer rollout. Verified: the custom domain proxies both PostgREST (`/rest/v1/`) AND Storage (`/storage/v1/object/public/...`) — a source PDF fetch returns the same 499,277 bytes as the raw `supabase.co` URL with the same HTTP 200. `STORAGE_BASE_URL` in `web/src/lib/supabase.ts` derives from the same env var, so the flip covers both concerns with one change. Vercel env update is a separate operator step (Project Settings → Environment Variables → edit `NEXT_PUBLIC_SUPABASE_URL` → redeploy).

### 2026-04-18

- **[RESOLVED 2026-04-18, commits `3665abf` + `234b183`] ~~Manifest data-quality audit.~~** Shipped as `tools/data_quality/audit_manifest.py` + Supabase migration adding `data_quality_flag` column to `cds_documents` (exposed in `cds_manifest` view). Frontend shows amber "Publisher issue" badge on flagged docs. Post-drain audit flagged 217 docs (189 blank templates, 28 low coverage) out of 2,043 artifacts. Uses a separate `data_quality_flag` column rather than overloading `participation_status`.

- **[RESOLVED 2026-04-18, commit `7138a3e`] ~~Tier 4 cleaner — B1 gender-column table coverage.~~** Fixed by preferring headers containing "full" when multiple headers match a col_hint string (e.g., "Full-Time Men" preferred over "Part-Time Men" when col_hint="men"). GT scorer unchanged: Harvard 32/32, Dartmouth 25/27, Yale 26/29. Corpus-wide B.101/B.126 improvement will be visible after a re-run of corpus_survey_tier4.py.

- **[RESOLVED 2026-04-18, commit `8ea5567`] ~~`supabase gen types` for typed client.~~** Shipped. Generated `database.types.ts` from live schema, typed the Supabase client as `createClient<Database>(url, key)`. ManifestRow and ArtifactRow now derive from the generated types; app-level types (SchoolSummary, CorpusStats, FieldValue) kept in `types.ts`.

- **[RESOLVED 2026-04-18] ~~Schema-version-aware labels.~~** Investigation showed this is already handled: FieldsView uses `field.question` from the artifact data (the extraction pipeline writes the question text into each field value). `labels.ts` is only a fallback for the rare case where an artifact has values but no inline `question` text. Multi-version labels from structural schemas is a V1.1 belt-and-suspenders option, not blocking.

- **[LARGELY RESOLVED 2026-04-17/18] ~~Multi-year archive per school.~~** Multi-year archival is now working via two complementary paths: (1) the resolver's parent-ancestor walking (`39bf219`) follows `cds_url_hint` pointers that land on a single PDF up to the parent IR page to discover sibling years; (2) the `force_urls` endpoint (`5cc6718`) + Playwright URL collector (`1f70278`) + `manual_urls.yaml` allow hand-curated batch archival of historical PDFs for schools where the resolver can't reach them. Yale, Harvard, CMU, Lafayette, and dozens more now have multi-year archives in the database. **Remaining gap:** fully automated multi-year discovery for schools whose landing page exposes historical links that the static resolver can already see but the `archive-enqueue` cron only processes the most-recent candidate. This is a cron-side change (fan out all candidates instead of one) and is low urgency now that the manual path covers the top-100 schools.

### 2026-04-17

- **[RESOLVED 2026-04-17] ~~Cross-year schema diff tool~~** Shipped as `tools/schema_builder/diff.py` with 5 year-pair diffs committed to `schemas/`:

  | Transition | Unchanged | Added | Removed | Possibly renamed |
  |---|---:|---:|---:|---:|
  | 2019-20 → 2020-21 | 750 | 216 | 105 | 39 |
  | 2020-21 → 2021-22 | 988 | 13 | 10 | 7 |
  | 2021-22 → 2022-23 | 885 | 131 | 99 | 24 (major redesign — file size 135KB → 770KB) |
  | 2022-23 → 2023-24 | 886 | 124 | 120 | 34 |
  | 2023-24 → 2025-26 | 839 | 134 | 162 | 43 (freshmen→first-year, gender collapse, graduate restructure) |

  Each diff emits both a JSON file (machine-readable for cross-year consumers) and a Markdown file (human release-notes style). Rename detection uses SequenceMatcher similarity ≥ 0.55 on normalized row_labels within the same (subsection, column_header) group, which correctly catches cohort-year rolls (e.g. B3 "Fall 2013 Cohort" → "Fall 2014 Cohort") and admission-year rolls (C2 "Fall 2020 admissions" → "Fall 2021 admissions").

  Normalization built into the tool: freshmen→first-year, male/female→men/women, another-gender→unknown, nonresident-aliens→nonresidents. These prevent false-positive churn on known template-drift renames.

  Downstream: cross-year consumers read the diff files to reconcile fields across years. The B2 gender-column breaking change lives in `cds_schema_2023_24-to-2025_26.diff.json`; a "gender discontinuity" consumer filter can be built from that.

  **Follow-ups:** (a) generate canonical question-number overlays on older structural schemas by fuzzy-matching against the 2025-26 Answer Sheet; (b) the 2024-25 → 2025-26 diff remains incomplete because we don't have the 2024-25 XLSX.

- **[RESOLVED 2026-04-17] ~~Tier 4 schema-targeting cleaner.~~** Shipped across four commits. The initial cleaner (`00d4cd6`) parsed Docling markdown tables and wrote `notes.values` keyed by canonical question number. Phase 1 (`592254b`) fixed three correctness bugs — ACT Math/English q# inversion, punctuation-sensitive label matching, C9 Submitting SAT/ACT column mapping — and shipped `score_tier4.py` + id_maps for Harvard/Yale/Dartmouth. Phase 2a (`7a9a2f0`) added B2 race/ethnicity, C10 class rank, C13 app fee, a wrapped-label parser, and an `_INLINE_PATTERNS` fallback for non-table fields. Phase 4 (`6b7a065`, `5951379`) added a 443-doc corpus survey that surfaced two systemic gaps — pre-2020 CDS terminology (`freshmen`/`freshman` → `first-year`, `Nonresident aliens` → `Nonresidents`) and header-less "one-metric-per-row" tables where Docling eats the first data row as a header — and fixed both. Final state: GT scorer 94.3% (83/88), critical fields 100% (21/21); corpus C1 admissions coverage moved from 8–14% to 50–59%. See `tools/extraction-validator/corpus_survey_tier4.py` for the ongoing coverage gauge. Remaining gaps are either Docling-rendering limits (cell-boundary mangling, flat-text table emission) or corpus data quality (below), not cleaner bugs.

- **[RESOLVED 2026-04-17, commit `592254b`] ~~Hand-mapping from ground-truth IDs to canonical question numbers.~~** Shipped for all four audited schools: `tools/extraction-validator/id_maps/{harvey-mudd,harvard,yale,dartmouth}-YYYY-YY.yaml`. Used by both `score_tier2.py` (HMC) and `score_tier4.py` (the other three) as the join table between homegrown GT IDs and canonical question numbers.

- **[RESOLVED 2026-04-17] ~~`schemas/README.md`~~** Shipped. Documents canonical vs structural schemas, the per-year XLSX sources, the 2024-25 gap, and next steps including the cross-year diff tool.

- **[SUPERSEDED by PRD 004, 2026-04-17] ~~Resolver: Georgetown / MIT / Bepress.~~** These three JS-rendered / WAF-blocked resolver failures are now tracked under [PRD 004 (JS-rendered resolver)](prd/004-js-rendered-resolver.md). The approved approach is a hybrid: hand-curate URLs via `tools/finder/manual_urls.yaml` + `force_urls` endpoint for immediate coverage, spike-test Playwright for automation. New resolver capabilities shipped since the original items were written: well-known-paths fallback (`df574a4`), parent-ancestor walking (`39bf219`), Box share-URL rewriter (`ec3c03c`), `force_urls` batch archive endpoint (`5cc6718`), Playwright URL collector (`1f70278`), headless-browser download for WAF-blocked schools (`c6c26af`). Georgetown, MIT, and Fairfield PDFs have been hand-curated into `manual_urls.yaml` and archived via `force_urls`.

### 2026-04-16

- **[RESOLVED 2026-04-16] ~~Probe the actual Tier 2 / Tier 4 distribution.~~** Tier probe (commit `49729de`) measured 84% pdf_flat, 6% pdf_fillable on a 32-school sample. Tier 4 Docling extractor shipped in commit `37293ab`. Full-corpus distribution across 1,675 docs will surface as the extraction worker drains.

### 2026-04-15

- **[RESOLVED 2026-04-15, commit `db520e6`] ~~Python extraction worker skeleton (M2 scope).~~** Shipped as `tools/extraction_worker/worker.py`. Polls `extraction_pending`, routes to Tier 2 (fillable PDF) and Tier 4 (Docling) extractors. See [ARCHITECTURE.md](ARCHITECTURE.md) extraction pipeline section.

- **[RESOLVED 2026-04-15, commit `59982f7`] ~~Re-probe schools whose hint URL contains `test|draft|copy|backup`.~~** Resolver-side fix instead of a database sweep: `TEST_ARTIFACT_RE` in `supabase/functions/_shared/resolve.ts` flags filenames matching `test|draft|old|copy|backup|archive|bak|tmp|temp|staging|dev|preview`, and `findBestSourceAnchor` ranks test artifacts below clean siblings. Schools whose only archivable CDS is a staging upload (CSULB's case) still get archived — dropping would be worse — but a clean file always wins when one exists. Covered by 3 new tests in `resolve.test.ts`. Existing already-archived test-artifact rows stay as-is; they can be fixed with a `force_school` re-archive pass for the known case (CSULB) if someone wants to confirm the school hasn't since uploaded a cleaner file.

---

## Strategic context (V2 and V3 ideas worth not losing)

Ideas bigger than a single backlog item, captured here so they don't get dropped. These are not scheduled.

### [SHIPPED + LOADED 2026-04-20] Join CDS with College Scorecard via IPEDS unit ID

Live in production. `GET /rest/v1/cds_scorecard` returns CDS documents joined to federal earnings, debt, net-price-by-income, completion, and retention. Total row counts at first load:

- `scorecard_summary`: **6,322 rows** (every Title-IV institution in the March 2026 bundle, vintage `2022-23`).
- `cds_documents.ipeds_id`: **3,794 of 3,950 public manifest rows** populated. The remaining gap is from legacy slug variants and non-Title-IV / non-school rows where `cds_documents.school_id` doesn't match a current Scorecard directory row. See the runbook's "Slug rationalization" section for the cleanup path.
- `cds_scorecard` view: live, returning real joined data (MIT tops earnings at $143,372 / 96.4% grad rate / $20,111 net price; Harvard's net-price-by-income range is $2,091 → $53,337).

Shipped across four migrations + two Python scripts:

- `20260420170000_ipeds_id.sql` — adds `ipeds_id` to `cds_documents`, exposes it in the `cds_manifest` view, wires it through `SchoolInput`/`InsertFreshArgs` so new archives populate it automatically from `schools.yaml`.
- `20260420170100_scorecard_summary.sql` — initial 43-field curated subset of the College Scorecard Most-Recent-Institution data. One row per UNITID. RLS-gated public read.
- `20260420170200_cds_scorecard_view.sql` — `cds_scorecard` view that left-joins the CDS manifest with a curated Scorecard outcome slice. `WITH (security_invoker = true)` so the view honors querying-user RLS instead of the view owner's.
- `20260420180000_scorecard_pell_remap.sql` — adapts the table to the March 2026 Scorecard data dictionary. `GRAD_DEBT_MDN_PELL` was renamed (`PELL_DEBT_MDN`, remap-only); `GRAD_DEBT_MDN_NOPELL` and `C150_4_NONPELL` were removed entirely (columns dropped from `scorecard_summary` and the view). The schema-drift guard in `refresh_summary.py` caught these on first dry-run.
- `tools/scorecard/backfill_ipeds_ids.py` — one-shot SQL generator / supabase-py writer to populate `ipeds_id` on rows inserted before the migration. Validates UNITIDs, escapes defensively, has a generator self-check + a column-exists preflight.
- `tools/scorecard/refresh_summary.py` — annual CSV→upsert loader keyed on UNITID. Includes schema-drift abort, per-batch dedup, leading-zero normalization, and stable-order pagination for `--only-cds`.

Operator runs `refresh_summary.py` once a year after each Scorecard bulk release. Full runbook: [`tools/scorecard/README.md`](../tools/scorecard/README.md), including the running schema-drift event log.

**Research docs (still authoritative):**
- [CDS vs. College Scorecard schema comparison](research/cds-vs-college-scorecard.md) — domain-by-domain field mapping that informed the 43-column selection
- [Join recipe](research/scorecard-join-recipe.md) — manual-join curl/Python/SQL examples; primarily useful now for Scorecard columns beyond the curated subset (per-program earnings, full repayment breakdowns)
- [Scorecard summary table plan](research/scorecard-summary-table-v2-plan.md) — the design doc this shipped against (status flipped to "Shipped 2026-04-20")

### Cross-year time series as a first-class query

Once multiple years of data exist for each school, cross-year time series become the most interesting consumer query: "show me Yale's SAT 50th percentile from 2015 to 2025," "which schools' acceptance rates dropped fastest during the test-optional period." This requires the schema year-diff tooling (P1 #4 above) plus a data model extension that lets consumers ask for "the same field across years" in the face of known schema discontinuities. Park for V2.

### Launch the "preservation archive" story to IR professionals

The preservation angle is a stronger story than the data-library angle for at least three audiences: institutional research professionals (who are the ones getting blamed when schools manipulate numbers), investigative journalists covering higher ed (who are currently losing access to historical CDS files as WCAG-driven removals accelerate), and IPEDS-adjacent academics (who use historical CDS for admissions equity research). An HN launch post framed around "we're archiving the public-accountability documents of American higher education at the moment they're being deleted" will land much harder than a generic open-data announcement. The CDS Initiative's own endorsement of machine-readable formats is written cover; a launch post that quotes their 2025-26 Word template instructions directly is very hard to argue against.
