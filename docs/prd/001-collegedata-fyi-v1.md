# PRD 001: collegedata.fyi V1

**Status:** Draft
**Author:** Anthony S.
**Date:** 2026-04-13
**Scope tag:** weekend side project
**Supersedes:** none (first PRD)
**Related:** [`docs/v1-plan.md`](../v1-plan.md) (detailed engineering plan), [`docs/decisions/`](../decisions/) (ADRs 0001-0005), [`docs/backlog.md`](../backlog.md)

---

## TL;DR

collegedata.fyi is an open-source archive and queryable manifest of US college Common Data Set documents. V1 discovers each school's CDS, **preserves the source file immediately**, extracts it into the CDS Initiative's own canonical schema, and exposes the result through a free public Postgres-over-HTTP API. The preservation angle is urgent because public universities are actively removing historical CDS PDFs from their websites in 2025-2026 to limit ADA/WCAG legal exposure, and nobody else is archiving them at scale. The build effort is deliberately scoped as a weekend project on a single vendor (Supabase) with MIT licensing and no UI.

## Problem

The Common Data Set is the most granular public dataset about American undergraduate admissions. It contains C7 admissions-factor weighting, C9 test-score distributions, C11 GPA breakdowns, C21 demonstrated-interest tracking, B2 race/ethnicity enrollment, H-section financial aid details, and J-section degree discipline breakdowns that no other public dataset captures at comparable depth. Every year, approximately 2,000-2,200 US colleges and universities populate this standardized form and publish it on their institutional research websites.

Four structural problems make the CDS hostile to the people who could most benefit from it:

1. **Decentralized hosting.** Every school publishes to its own URL. There is no central index, no registry, no API. commondataset.org itself does not aggregate anything.
2. **Layout-hostile format.** Most schools publish the CDS as a flattened PDF that breaks every automated parser that isn't specifically tuned for each school's quirks. Even good parsers (Docling, OCR stacks) produce silently wrong numbers when misaligned tables and merged headers slip past. We hit this personally during initial research on Harvey Mudd 2025-26.
3. **Active removal crisis.** The April 2024 DOJ ruling on ADA Title II requires public universities to make hosted PDFs WCAG 2.1 AA compliant. The CDS template is structurally hostile to screen readers and extremely difficult to remediate. Risk-averse schools are removing historical CDS documents from their websites rather than retrofit them. **Documents that existed last year are disappearing now, and there is no systematic archive that captures them before they vanish.**
4. **Strategic opacity.** Elite schools sometimes refuse to publish at all (University of Chicago), publish but omit specific sections (Dartmouth's GPA distributions), or publish multiple variant files in the same year to control how their numbers are read (Columbia's two-CDS approach). Consumers cannot tell "we haven't found it" from "they deliberately refuse" without a per-school context layer.

The people most affected by these problems are the ones least equipped to build their own scraper: high school guidance counselors comparing schools for students, prospective applicants triangulating admissions chances, IR professionals benchmarking against peer institutions without a third-party data pipeline, investigative journalists trying to verify ranking-inflation claims after the Columbia 2022 scandal, and researchers studying admissions equity against historical data that is literally being deleted from the web in real time.

## Users

V1's primary users are **developers and data-adjacent researchers** who can consume a public JSON API, not end consumers. Three concrete personas:

**Persona 1: "The counselor-tool builder."** An engineer building a college-search tool, college-fit calculator, or guidance-counselor platform. Wants a cross-school, queryable source of admissions and aid data that doesn't require scraping 2,000 institutional research websites. Currently they either buy commercial data from Peterson's or College Board (expensive, licensed, locked behind contracts) or they give up and use IPEDS (federal data that lacks the admissions granularity consumers care about).

**Persona 2: "The IR professional benchmarking peers."** An institutional researcher at a mid-sized private college whose job involves comparing their school against a peer group. Currently they scrape each peer's CDS individually, which is slow, fragile, and yields inconsistent data quality. They would rather hit a single API that returns comparable values across the peer group in one query.

**Persona 3: "The journalist or researcher verifying claims."** A reporter covering higher-ed, or an academic studying admissions equity. Currently they rely on archived PDFs that are actively vanishing, they hand-transcribe numbers, or they rely on whatever the CDS Initiative happens to have hosted. They want a trustworthy historical archive with provenance linking every value back to the source document.

V1 does **not** try to serve non-technical end consumers (applicants, parents, counselors). That audience is a V2 concern and would need a UI, a search interface, and hand-curated explanations, none of which the weekend scope supports.

## Why now

The honest answer is less about external urgency and more about the build cost falling. Two technical facts that were not obvious a year ago make this project a weekend's worth of effort instead of a multi-month one.

**1. The CDS Initiative publishes a canonical machine-readable schema in the official Excel template.** The "Answer Sheet" tab of the 2025-26 template lists every canonical CDS field with stable question numbers (`A.001`, `B.101`, `C.101`, ...), US News PDF tags, and structural metadata — 1,105 fields in total. We do not have to design or maintain a schema; we extract theirs programmatically in about fifty lines of Python. A year ago this would have been a hand-authored mapping exercise.

**2. A non-trivial minority of school CDS PDFs are unflattened fillable forms.** Harvey Mudd's 2025-26 CDS, which we spent an audit trying to parse with layout-extraction tools, turned out to have 1,026 named AcroForm fields that `pypdf.get_fields()` reads deterministically. For those schools, extraction is a 20-line script rather than a rasterize-parse-clean pipeline. A full regression test against HMC's hand-verified ground truth ([`tools/extraction-validator/score_tier2.py`](../../tools/extraction-validator/score_tier2.py)) shows **31 of 31 fields match exactly (100%), including all 8 critical C1/C2 admissions fields** that the original Docling audit had reported as corrupted. Our sample is too small (N=3) to call the format distribution across the wider corpus, but Tier 2 is not theoretical and is verified end-to-end on at least one school.

Combine those two facts and the engineering cost of building an open CDS library drops by roughly an order of magnitude compared to the "run Docling on a PDF, clean up the mess per school" approach that was the default a year ago. Nobody has built this yet, and the build cost just became trivial. That is the real answer to "why now."

A secondary consideration, not a primary one: the ADA Title II compliance window (April 2026 for large entities, April 2027 for smaller ones) creates some risk that individual schools will remove historical CDS files rather than retrofit them for WCAG compliance. We have observed this in at least one concrete case — MIT removed every historical CDS URL during a domain migration between 2023 and 2026, with no successor content at the new `ir.mit.edu` subdomain. How widespread this becomes during the 2026-2027 compliance window is unknown, and an informal probe of ten elite schools found the aggregate removal rate so far to be well under 10%. V1 archives source files on first discovery anyway, so when individual schools do remove their CDS we have a copy. This is an incidental archival benefit, not the headline framing.

The CDS Initiative's 2025-26 Word template includes a note suggesting schools use "Large Language Models, VBA macros, or Python scripts" to help convert legacy CDS PDFs to machine-readable CSVs. We read this as "compatible with the direction the standards body is moving," not as an endorsement. The project's framing does not depend on it.

## Goals

V1 promises, in priority order:

1. **Preservation.** Every CDS document we discover is archived in Supabase Storage on first sight, before any extraction work runs. The archive is immutable and survives even if the school removes the live source.
2. **Discovery.** A queryable index of where each school's CDS lives, what we have on file, and when we last verified the source URL.
3. **Canonical-schema extraction.** Every archived document is extracted into a single schema derived from the commondataset.org Excel template's Answer Sheet (1,105 canonical fields for 2025-26, keyed by question number). Cross-school queries work against stable field IDs from day one.
4. **Honesty about quality.** Each extracted artifact is tagged with its producer and the year's schema. Consumers can filter by producer quality and see exactly which extraction path produced which value. Per-school known-issues documentation flags fields that should not be trusted without verification against the source.
5. **Free public API.** Read-only access via PostgREST at `api.collegedata.fyi`. No authentication, no rate limiting beyond Supabase's default, no commercial terms.

## Non-goals (V1)

V1 deliberately does **not** try to be:

- **A cleaned, normalized, decision-ready dataset.** Extraction quality varies by source format and school. V1 publishes what we extracted and how we extracted it. Cleanup is a separate, community-contributable layer, not a V1 promise.
- **A consumer-facing website or UI.** No React app, no search page, no school profile pages. If you want a UI, write one against our API.
- **A replacement for IPEDS.** IPEDS is mandatory, federal, and captures regulatory compliance data. The CDS is voluntary and captures commercial/admissions data. They complement each other. V1 ships the admissions side. Joining them is a V2 idea.
- **An authoring tool for schools filing the CDS.** That is the CDS Initiative's job.
- **A ranking or comparison site.** Ranking is editorial. V1 is data infrastructure.
- **A real-time system.** The underlying data changes roughly annually. Discovery runs daily at most, extraction runs when triggered, and consumers should treat the data as "most recent as of the `discovered_at` timestamp."

## Scope

V1 is split into three independently useful pieces. Each is shippable on its own, and the project should publicly claim only what has actually shipped.

### V1a — CDS Finder

A scraper that takes a school slug and returns the canonical URL of its most recent CDS document, plus enough metadata to archive it. Seed corpus comes from the pbworks College Lists Wiki (~80 institutions) plus a fallback ladder of known URL path patterns and Google dorks. `schools.yaml` holds per-school overrides; contributors PR new entries as coverage expands. Output is a `cds_documents` row with source URL, format (fillable PDF / flat PDF / scanned), sha256, page count, discovery timestamp, and participation status.

The finder is runnable on its own and produces value even if extraction never happens: a cross-institutional index of where every school's CDS lives is itself a useful public artifact.

### V1b — Tiered Extraction Pipeline

Each archived source is routed to the appropriate extractor based on its format. The tier ladder (documented in detail in `docs/v1-plan.md`):

| Tier | Input | Extractor | Status |
|---|---|---|---|
| 1 | Filled XLSX | `openpyxl` → Answer Sheet | Deferred (no schools observed publishing this) |
| 2 | Unflattened fillable PDF | `tools/tier2_extractor/` via `pypdf.get_fields()` | **Built**, verified on HMC 2025-26 |
| 3 | Filled DOCX | `python-docx` → Word tags | Deferred (not observed) |
| 4 | Flattened PDF | Layout extractor (Docling or Reducto) + schema-targeting cleaner | Partial — reference extracts exist, cleaner not written |
| 5 | Image-only scan | OCR + cleaner | Not started, V1 best-effort only |

Every tier targets the same canonical schema (`schemas/cds_schema_{year}.json`), which is extracted programmatically from the commondataset.org Excel template via `tools/schema_builder/`. Cross-tier, cross-school queries work because the field IDs are identical.

The scraper probes every incoming document with `pypdf.get_fields()` before routing, so fillable PDFs go to Tier 2 deterministically and never enter the expensive Tier 4 path.

### V1c — Public Manifest API

A Supabase-hosted Postgres schema exposed read-only through PostgREST at `api.collegedata.fyi` via Supabase custom domain. Consumers query `https://api.collegedata.fyi/rest/v1/cds_documents?school_id=eq.yale` and get JSON back. No custom backend, no bespoke web server, no auth. The tables exposed (`cds_documents`, `cds_artifacts`, `cleaners`) are fully described in `docs/v1-plan.md`'s data model section.

Using the custom domain from day one matters: the URL ends up in every example `curl` command and every piece of documentation, and migrating it later would invalidate every link.

## Success criteria

V1 ships when these are all true:

1. **`api.collegedata.fyi` responds with a PostgREST JSON payload** for `cds_documents` and `cds_artifacts` queries. Running `curl 'https://api.collegedata.fyi/rest/v1/cds_documents?limit=10'` from any machine on the internet returns structured data.
2. **At least 20 schools have populated `cds_documents` rows**, representing a realistic mix of fillable (Tier 2) and flattened (Tier 4) formats. The target mix includes Yale, Harvey Mudd, Harvard, and ~15 others selected from the pbworks seed list to stress-test the finder's URL resolution logic.
3. **At least 5 of those 20 schools have at least one canonical artifact** (a structured extract keyed to canonical question numbers) available for download via signed or public Storage URLs.
4. **The source files for all 20 schools are archived in Supabase Storage.** Even if extraction fails for a given school, the raw source is recoverable.
5. **The README documents the project clearly enough that a developer unfamiliar with the CDS can run three `curl` commands and understand what they are looking at.** "Explain it to a developer who has never heard of the Common Data Set" is the copy-quality bar.
6. **The tier architecture and the canonical schema are each captured in a single ADR** so a new contributor can understand *why* the project looks the way it does without reading the whole git history.
7. **At least one external person has read the project** — either via an HN Show, a targeted Slack share in an IR-professional community, or an email to someone like Fairfield's Digital Commons team. "Built it for yourself and nobody else" is a failure state even for a weekend project.

Explicitly **not** a success criterion for V1: high extraction-quality scores for Tier 4 schools, a community cleaner actually running in CI, or any consumer-facing UI.

## Architecture summary

Single vendor: **Supabase**. Supabase Postgres holds the manifest and provenance tables. Supabase Storage holds archived source files and extracted artifacts. Supabase Edge Functions on a daily cron run the discovery scraper. A local Python worker polls the `extraction_pending` flag and runs the actual extraction (Tier 2 for fillable PDFs is deterministic and fast; Tier 4 falls through to Docling or Reducto for flattened PDFs). PostgREST exposes the manifest as a free public API.

The rationale for this stack is captured in ADR 0001 (Supabase-only). The rationale for publishing raw over clean is ADR 0002. The licensing choice is ADR 0003 (MIT). The domain choice is ADR 0004. The repo location is ADR 0005. The tiered extraction strategy will be captured in ADR 0006 (on the backlog as a P1 item).

Full data model, milestone breakdown, and vendor rationale live in `docs/v1-plan.md`. This PRD stays at the product level and does not duplicate that detail.

## Milestones (weekend-project realistic)

Rough timeline for shipping V1. Assumes CC-assisted development, evening-and-weekend effort, and no blockers from external services (Supabase provisioning, domain DNS propagation).

| Milestone | Scope | Realistic effort |
|---|---|---|
| **M0: Scaffolding** | Register `collegedata.fyi`, provision Supabase project, apply Postgres schema migration, create Storage bucket, configure custom domain, confirm PostgREST returns empty-but-valid JSON via curl | Saturday morning |
| **M1: CDS Finder V1** | Edge function cron running against `schools.yaml` with 10-20 seed institutions from the pbworks list, producing `cds_documents` rows with `participation_status` populated, failure cases logged for hand-debugging | Saturday afternoon + Sunday morning |
| **M2: Tier 2 extraction integration** | Wire `tools/tier2_extractor/` to the `extraction_pending` queue so fillable PDFs produce canonical artifacts automatically. Verify end-to-end with HMC. | Sunday afternoon |
| **M3: Public API + README + announce** | Finalize PostgREST exposure, polish README with preservation framing and three curl examples, post Show HN and send targeted DMs to IR/CDS communities | Following evening |
| **M4+: First community cleaner** | Publish `cds_schema_v1` as versioned contract, ship a reference cleaner for the easy flat-PDF normalizations, wire into GitHub Actions | Deferred indefinitely; depends on V1 attracting interest |

"Weekend project" in this PRD means the M0-M3 block is scoped to roughly one long weekend of focused work, not that every line of code ships in 48 hours. M4 is explicitly post-launch and community-dependent.

## Open questions

Real uncertainties that the PRD cannot answer on its own. Each needs a small experiment, a conversation with someone, or a deliberate decision before V1 ships.

1. **What fraction of schools publish fillable PDFs (Tier 2) vs flattened (Tier 4)?** Current sample: 1 of 3 real schools (HMC fillable, Yale and Harvard flattened). A 20-30 school probe is the cheapest way to calibrate this before investing heavily in Tier 4 cleaners. If Tier 2 is 80% of the corpus, Tier 4 becomes a minor path. If it is 20%, Tier 4 is the main path and Reducto pricing becomes a real budget question.
2. **Are Supabase free-tier limits going to bite before V1 attracts any attention?** Storage is the only realistic pressure point. Back-of-envelope: 500 schools × 5 years × ~5 MB = ~12 GB, above free tier but within the cheapest paid plan. This is a "nice problem to have" risk but worth measuring during M1.
3. **Storage URL exposure: public or signed?** Public is simpler and matches the open-data framing. Signed means we can rotate blob visibility if a school requests removal. The preservation mission argues for public (once archived, stays archived). The legal surface argues for signed (a school's counsel can send a takedown request, and having short-lived URLs gives us flexibility). Lean toward public with a documented takedown process, but this is a real judgment call.
4. **How do we measure cross-year comparability when the 2025-26 schema introduces breaking changes?** Gender categories collapsed from four to three, B4-B21 disaggregates by Pell, B22 requires explicit numerator/denominator. Cross-year queries silently lose or mis-merge data at the 2024-25 → 2025-26 boundary without tooling. The backlog has a schema year-diff script as a P1; the open question is whether that diff tooling ships as part of V1 or V1.1.
5. **Reducto pricing.** We have not yet looked at per-page cost. Only matters if Tier 4 is a meaningful fraction of the corpus. Worth 10 minutes of research before M0 starts so the architecture decision in ADR 0006 can reference a real number.
6. **How do we handle strategic non-publishers in the manifest?** University of Chicago, Reed. The `verified_absent` participation status exists in the data model, but the sourcing process for that status (how do we know a school "refuses to publish" vs "we haven't found it yet") needs a documented protocol.

## Risks

Things that could kill the project or invalidate its value.

**Risk: The scraper can't handle the long tail.** Some schools render their pages via JS before exposing the PDF, some put the CDS behind a portal login, some publish image-only scans that need OCR. Each failure mode is a long tail of one-off engineering work. **Mitigation:** every finder failure writes a row with a reason, `schools.yaml` accepts per-school overrides, and the README explicitly documents "not yet found" as a first-class state rather than pretending we have complete coverage.

**Risk: Tier 4 extraction quality is worse than we can credibly ship.** For flattened PDFs that don't have AcroForm, the layout-extraction path (Docling, Reducto, OCR) produces silently wrong numbers some of the time. **Mitigation:** publish per-school known-issues files, tag each artifact with its producer, and let consumers filter by quality. Never pretend a Tier 4 extract is as trustworthy as a Tier 2 extract.

**Risk: Supabase free-tier storage fills up.** Noted under open questions. **Mitigation:** measure during M1, move to a paid tier if needed.

**Risk: The project launches and nobody cares.** A real weekend-project failure mode. **Mitigation:** the preservation framing is specifically designed to land with IR professionals, journalists, and IPEDS-adjacent researchers, three audiences more likely than the general public to share it. Launch outreach targets those audiences explicitly, not /r/college or /r/ApplyingToCollege.

**Risk: A school's legal counsel sends a takedown request for an archived document.** The counter-argument is that every CDS is already public data published on the school's own website, that the school owns the data per commondataset.org's stated terms (none), and that fair-use archival precedent is well-established. But the first takedown-request email will still be uncomfortable. **Mitigation:** document a takedown process in the README from day one. Respond within 48 hours, verify the claim, and apply takedowns in a documented way (`participation_status = withdrawn`, archive remains in cold storage) rather than silently deleting. The archive copy never leaves storage, even if it stops being served publicly.

**Risk: The CDS Initiative itself objects or asks the project to stop.** Unlikely given the 2025-26 template's explicit endorsement of machine-readable extraction, but possible. **Mitigation:** reach out to Peterson's Research (the operational maintainer of the templates) proactively before or at launch to introduce the project. If they object, we adjust. If they endorse, we cite them.

## Out of scope / parked for V2+

Captured so these ideas don't get lost. Details live in `docs/backlog.md`'s Strategic Context section.

- **Join CDS with College Scorecard via IPEDS unit ID.** Massive upside; clean technical problem. Park for V2.
- **Cross-year time series as a first-class query.** Needs schema year-diff tooling as a prerequisite.
- **Web UI for non-technical users.** Not happening in V1. Maybe V3.
- **Community cleaner CI integration.** Designed for in V1's artifact model but deferred past M4 until someone actually wants to ship a cleaner.
- **Commercial tier or paid API.** Not planned. MIT-licensed, free public API, donations-only if donations happen at all.

## Decision log

This PRD consolidates decisions already captured as ADRs:

- **ADR 0001:** Single vendor (Supabase)
- **ADR 0002:** Publish raw over clean (extended to canonical-schema extraction; ADR 0006 will formalize the extension)
- **ADR 0003:** MIT license
- **ADR 0004:** `collegedata.fyi` canonical domain
- **ADR 0005:** Repo lives on `bolewood` GitHub org

Future ADRs expected to come out of V1:

- **ADR 0006 (P1, not yet written):** Tiered extraction strategy, detection logic, and data model columns
- **ADR 0007 (future):** Takedown process for archived documents
- **ADR 0008 (future):** Cross-year schema compatibility policy

## Changelog

- **2026-04-13:** First draft. Consolidated from `docs/v1-plan.md`, ADRs 0001-0005, `docs/known-issues/`, `docs/backlog.md`, and the Gemini ecosystem research findings.
