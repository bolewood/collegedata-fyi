<!-- /autoplan restore point: PRD 009 did not exist prior to /autoplan; delete this file to revert. -->

# PRD 009: ADR 0008 + Distribution Push

**Status:** Reviewed (autoplan 2026-04-20) — approved reframe from 3-item bundle to "takedown policy + discoverability sprint"
**Created:** 2026-04-20

---

## Context

The project sits at 697 schools indexed, 3,924 documents archived, 98%
extracted, sitemap submitted to Google. The operator is entering "done
for now" mode.

This PRD started as a bundle of three last-mile operational items
(preservation re-check cron, CI with Tier 4 regression gate, ADR 0008
takedown process). Both CEO voices and both Eng voices converged on the
same reshape during /autoplan review:

- **ADR 0008 is cheap, durable insurance.** 30 min pure-docs work, zero
  maintenance cost, solves a real low-frequency / high-stakes problem
  (first takedown request). Ship it.
- **Preservation re-check is premature.** `docs/v1-plan.md` describes the
  archive as "an open data library first and an incidental archive
  second." Informal probe found removals "well under 10%." Cron is
  defensible only if the archive narrative is being actively leaned into
  as a product claim. Right now, it isn't.
- **CI with the Tier 4 regression gate is worse than no gate.** Pins
  every future PR to pre-1.0 Docling output determinism. Baseline
  regeneration becomes the recurring chore. CEO premise ("silent Tier 4
  regression is the most likely future pain") is hypothetical, not
  measured — zero historical regression incidents exist.
- **The highest-EV use of 4 hours is distribution.** GSC sitemap crawl
  will bring visitors over weeks; a good Show HN drives 10-100× that in
  a day. Archive value is unrealized until people find it.

## Premises

1. **Archive usefulness ∝ discoverability.** The project is
   technically complete enough to be useful. What's missing is anyone
   knowing it exists. A "Show HN: I archived every U.S. college's Common
   Data Set" post with the preservation-archive angle has a plausible
   front-page shot; even page-2 drives 100+ visitors + 5-10 inbound
   backlinks that meaningfully accelerate organic discovery.
2. **LLM citability matters more than SEO.** People ask ChatGPT/Claude
   "what's Harvard's acceptance rate?" more than they search Google for
   CDS PDFs. `Dataset` JSON-LD (partially done — per-year pages have
   it) + a machine-friendly `/api/facts/{school_id}` endpoint make the
   corpus something an LLM tool call can cite.
3. **Takedown policy is pure insurance.** First request may never
   arrive. Writing it costs 30 min. Not writing it and responding
   ad-hoc under pressure costs hours and leaves no paper trail.
4. **Preservation cron + CI are deferrable without regret** if the
   archive narrative isn't the lead product claim AND future code
   changes are expected to be rare. Current state meets both. If either
   changes — a school notably removes their CDS, or a second contributor
   lands an extraction PR — revisit PRD 009's deferred items as PRD 010.

## What to build

### 1. ADR 0008: Takedown process

**New file:** `docs/decisions/0008-takedown-process.md` (~120 lines
modeled on ADR 0007).

**Structure:**

- **Context:** archive preserves publicly-published documents. Schools
  may request removal. Right-to-archive defense is strong (public
  educational use, MIT-licensed extracts). Need documented protocol
  before the first request lands.
- **Decision:** three-step protocol
  1. **Verify:** request must come from a `.edu` address matching the
     school's official domain + specific document reference
     (school_id, cds_year). Cross-check against the school's public
     IR office listing. Reject unaffiliated parties.
  2. **Apply:** `UPDATE cds_documents SET participation_status =
     'withdrawn', removed_at = now() WHERE school_id = $1 AND cds_year
     = $2`. Leave Storage bytes in place for now (see "Non-goals"
     below — moving to a separate bucket would break
     `cds_artifacts.storage_path` and the frontend's hardcoded public
     URL pattern; that's a separate PRD).
  3. **Transparency log:** append a line to `docs/takedowns.md` (new
     scaffolding file, populated on first takedown): date, school_id,
     cds_year, reason category (FERPA-adjacent / attribution
     dispute / other), outcome. No requester PII.
- **Required companion change:** `web/src/lib/queries.ts` must filter
  `participation_status NOT IN ('withdrawn', 'verified_absent')` in
  every `cds_manifest` select so withdrawn documents disappear from
  the frontend. Without this, the takedown is cosmetic. 5-line change.
  Verify by manually flipping a test row to `withdrawn` + confirming
  the school page no longer lists it.
- **Status:** Accepted.
- **Consequences:** clarity when the first request arrives, paper trail,
  transparency that argues for good-faith posture in any dispute.
- **Cross-references:** ADR 0003 (MIT license), ADR 0006 (tiered
  extraction), CONTRIBUTING.md's new "Takedown requests" section.

**CONTRIBUTING.md update:** new section "### If you represent a school
and need a document removed" with the `.edu` verification instructions +
contact. 5 lines.

### 2. Schema.org Dataset JSON-LD + LLM-friendly API

Per-year pages (`/schools/[school_id]/[year]`) already emit `Dataset`
JSON-LD (shipped in PRD 008 SEO work). Two small completions:

- **School detail page enrichment.** `/schools/[school_id]` currently
  emits `CollegeOrUniversity` + `BreadcrumbList`. Add a `DataCatalog`
  schema listing every year's Dataset entity for the school. Gives
  search engines (and LLMs) a one-stop view of "what's in the archive
  for this school."
- **`/api/facts/{school_id}` endpoint.** A small Next.js route that
  returns plain JSON (no schema wrapper) with the most-queried fields
  from the most recent year: school name, year, applied / admitted /
  enrolled totals, acceptance rate, yield, retention, 4-year grad
  rate. Shape chosen for one-shot LLM consumption. Target ChatGPT
  tool-use format: flat object, stable key names, no nesting.

**New files:**
- `web/src/app/api/facts/[school_id]/route.ts` (~30 lines)
- Schema.org `DataCatalog` block added to
  `web/src/app/schools/[school_id]/page.tsx`

### 3. Show HN draft + companion blog post

**New file:** `docs/blog/show-hn-draft.md` (committed; not published
until operator decides to launch).

**Angle:** "I archived every US college's Common Data Set so the data
doesn't get memory-holed." Real-life example: a school that silently
moved or deleted their CDS. Open data, MIT license, extracted to
canonical schema, queryable via public API, 697 schools and growing.

**Post structure:**
- One-sentence hook
- The gap: no free public API for CDS, every school a different URL
- The solution: automated discovery + tiered extraction (1 XLSX, 2
  AcroForm, 4 Docling + cleaner, 5 force-OCR, 6 HTML), all targeting
  a canonical 1,105-field schema from the CDS Initiative itself
- The archive angle: downloads the source file on first discovery so
  it stays public even if the school removes it later
- The ask: schools publish CDS as a legal expectation of US News /
  Common App compliance; this is preservation of a public-accountability
  document, not scraping private data
- Live link: `collegedata.fyi`
- GitHub link: `github.com/bolewood/collegedata-fyi`

**Supporting materials:**
- Screenshot of a school page (MIT is the HTML archetype — works nicely
  visually)
- One real number that surprises people (Tier 4 cleaner 94% GT scorer
  on audited schools; 38 → 159 field improvement on MIT 2023-24 after
  Tier 6 HTML drop-in)

## Files modified

| File | Change |
|---|---|
| `docs/decisions/0008-takedown-process.md` | **New.** Takedown ADR. |
| `docs/takedowns.md` | **New (empty scaffold).** Transparency log header only. |
| `web/src/lib/queries.ts` | Add `participation_status NOT IN ('withdrawn','verified_absent')` filter to every `cds_manifest` select. |
| `CONTRIBUTING.md` | Add takedown-request section pointing at ADR 0008. |
| `web/src/app/schools/[school_id]/page.tsx` | Add `DataCatalog` JSON-LD enumerating per-year Datasets. |
| `web/src/app/api/facts/[school_id]/route.ts` | **New.** Flat-JSON facts endpoint for LLM consumption. |
| `docs/blog/show-hn-draft.md` | **New.** Committed but unpublished. |
| `docs/backlog.md` | Resolve "ADR 0008" entry. Explicitly defer "Periodic re-check job" and "Test framework + CI" with a link to this PRD's review for the reasoning. |

## Verification plan

### Acceptance criteria

1. **ADR 0008 lands as complete docs.** File exists, linked from
   CONTRIBUTING.md, transparency log scaffold at `docs/takedowns.md`.
2. **Withdrawn filter works end-to-end.** Manually flip a test
   `cds_documents` row to `participation_status='withdrawn'`. Confirm
   that school's year dropdown on the frontend no longer lists that
   year. Revert the test row.
3. **`DataCatalog` JSON-LD renders.** Rich Results Test on
   `https://www.collegedata.fyi/schools/mit` detects `CollegeOrUniversity`
   + `BreadcrumbList` + `DataCatalog`.
4. **`/api/facts/{school_id}` returns valid flat JSON.** `curl
   https://www.collegedata.fyi/api/facts/mit` returns a single object
   with at least: `school_id`, `school_name`, `latest_year`, `applied`,
   `admitted`, `enrolled`, `acceptance_rate`, `yield_rate`. Shape
   stable enough for tool-use.
5. **Show HN draft is ready to post.** Operator reviews + edits, but
   the commit lands the draft structurally complete.

## Risks

| Risk | Mitigation |
|---|---|
| Show HN draft sits in the repo unpublished forever. | Committed as a reminder, not a commitment. If it never ships, cost is zero. If ops bandwidth opens up next month, draft is ready. |
| Withdrawn filter breaks an edge case in the admin path. | There is no admin path. The filter is a consumer-side SELECT only; no writes affected. Test case: manual toggle flip + revert. |
| `DataCatalog` JSON-LD adds page weight. | Small — it enumerates ~10-20 years per school max, ~2 KB per page. Inline in the SSR'd HTML. No impact. |
| `/api/facts` endpoint becomes a scraping target. | PostgREST is already public and exposes more data. This endpoint is strictly a denormalized subset for LLM convenience. No new attack surface. |
| Show HN triggers a takedown request before ADR 0008 is written. | ADR 0008 ships first in this PRD. Minimum-viable-process exists before the spotlight arrives. |
| We later decide we do want the preservation cron + CI. | See "Deferred to PRD 010." Not a risk, a planned follow-up gate. |

## Non-goals

- **Preservation re-check cron.** Deferred to PRD 010 if needed.
  Trigger criteria: a user reports a school removed their CDS and
  nothing in the manifest reflects it, OR the archive narrative becomes
  the lead product claim.
- **Test framework + CI.** Deferred to PRD 010 if needed. Trigger
  criteria: a second contributor lands an extraction PR, OR a silent
  regression is observed post-merge.
- **Moving withdrawn documents to a separate Storage bucket.** The
  current PRD leaves bytes in place with `participation_status='withdrawn'`
  and a frontend filter. If a takedown request specifically demands
  bytes removal, that's a PRD 010-scope migration (create bucket, flip
  `cds_artifacts.storage_path`, update frontend URL construction).
- **HN launch itself.** The draft is committed. Actually posting is an
  operator decision, not this PRD's deliverable.

## Cross-references

- [ARCHITECTURE.md](../ARCHITECTURE.md) — architecture stays unchanged.
- [ADR 0002](../decisions/0002-publish-raw-over-clean.md) — publish-raw
  posture makes takedown policy discoverable.
- [ADR 0003](../decisions/0003-mit-license.md) — MIT license covers
  code; schools own their data.
- [PRD 008](008-html-extraction.md) — prior last-mile work.
- [docs/backlog.md](../backlog.md) — "ADR 0008" entry resolved here;
  "Periodic re-check job" + "Test framework" explicitly deferred.

---

## /autoplan Review Report

Reviewed 2026-04-20 on branch `main`. CEO + Eng phases only (Design + DX
skipped per scope).

### Phase 1: CEO Review — Dual Voices

| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Right problem to solve? | No — discoverability > durability | No — distribution > maintenance | **DISAGREE with original PRD** |
| 2. Premises valid? | No — asserted, not measured | No — own v1-plan says removals <10% | **DISAGREE** |
| 3. Scope calibration correct? | No — 3 items wrongly bundled | No — "durability theme" is post-hoc | **DISAGREE** |
| 4. Alternatives sufficiently explored? | No — CI-skip + distribution never named | No — "ADR 0008 only" path missing | **DISAGREE** |
| 5. 6-month trajectory sound? | No — HN didn't happen, CI drift chore | No — installed machinery in low-change mode | **DISAGREE** |

### Phase 3: Eng Review — Dual Voices

Critical findings on the original bundle (all resolved by the reframe):
1. `contains(github.event.pull_request.changed_files, ...)` is invalid
   GHA syntax. Original Tier 4 gate would never run. **Resolved by
   dropping CI from scope.**
2. ADR 0008's "move to sources-withdrawn bucket" breaks storage
   addressing. **Resolved by downscoping ADR to participation_status
   + frontend filter only; bytes stay in place.**
3. Frontend didn't filter withdrawn docs. **Resolved by adding the
   filter to `queries.ts` as an explicit deliverable.**
4. Preservation cron raced discovery. **Resolved by dropping
   preservation from scope.**

### User Challenges (resolved)

- **Challenge 1: Split the bundle.** Accepted. ADR 0008 ships; preservation
  + CI deferred to PRD 010.
- **Challenge 2: Drop the Tier 4 regression gate.** Accepted (gate not
  shipping; CI deferred entirely).
- **Challenge 3: Consider distribution.** Accepted. Schema.org
  enrichment + `/api/facts` + Show HN draft replace the deferred ops
  work.

### Verdict

**APPROVED** as reframed. Ship ADR 0008 + withdrawn filter + DataCatalog
JSON-LD + `/api/facts/{school_id}` + Show HN draft. Est. 2-3 hours CC.
