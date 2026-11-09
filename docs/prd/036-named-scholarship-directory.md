# PRD 036: Named Scholarship Directory

**Status:** Draft
**Created:** 2026-11-08
**Author:** Anthony + Claude (research: two GPT-6.1-Sol Orca workers)
**Related:** [PRD 018](018-open-college-fit-data.md) (merit profile from CDS H2A/H14), [PRD 026](026-guided-college-discovery.md) (CC BY-SA content layer), [PRD 035](035-calibrated-information-density.md)

---

## Executive summary

Families ask two different questions about merit aid:
- **How generous is this school with merit aid overall?** The CDS already answers this. H2A and H14 power `school_merit_profile`.
- **What named awards can my kid actually go for, and how?** For example, Boston College's Gabelli Presidential Scholars, or Tulsa's National Merit Semifinalist package. Nobody answers this in the open.

The existing directories have three problems:
- **They're proprietary.** College Transitions, MeritPlaybook, Fastweb and Niche all restrict republication.
- **They go stale.** College Transitions' National Merit table is dated June 2020, and it still describes USC, Florida, Tulsa and Alabama terms that have since changed.
- **They rarely say which year's terms they describe.**

PRD 036 adds an open, CC BY-SA directory of named, institution-tied merit programs:
- one record per program, with a version per entering class;
- every important fact traced to the school's official page;
- a visible "terms for fall 2027 entry · checked <date>" line;
- an annual re-verification (by an agent, with the owner spot-checking), plus automatic change monitoring during application season.

It sits next to the CDS merit profile on each school page. CDS gives the aggregate picture, the directory gives the specific awards, and the page never blends the two.

## Problem

1. **No open, sourced, dated list of named merit programs.** We counted the main sources:
   - College Transitions' selective list: 64 rows, updated October 2025.
   - College Transitions' National Merit list: 68 schools, dated June 2020.
   - MeritScholarships.org: about 169 profiles, with no date.
   - MeritPlaybook: 1,311 automatic tiers.

   All of them restrict reuse, so they can serve only as leads. The only open dataset we found is Open Scholarships: CC BY 4.0, 104 records, Nevada only.
2. **Third-party lists drift from current terms.** Verified examples:
   - USC cut its National Merit award from half tuition to a fixed $20,000 a year, starting fall 2025.
   - Vanderbilt retired its Chancellor's Scholarship for fall 2027 applicants.
   - Tulane's Stamps program changed from about 5 recipients to about 10, and its application process changed.
   - Florida ended nonresident Benacquisto awards in 2022-23.
   - Boston College's Gabelli program lists 18 recipients on its current page and 15 in an older brochure.
3. **Program terms don't reduce to a "full ride" flag.** Examples from official pages:
   - Tulsa's package is selective. It requires a visit and an interview, and it can't be combined with other Tulsa awards.
   - Oklahoma's page says outright that its package is not full cost.
   - Texas A&M's package includes a nonresident tuition waiver, which is not a scholarship.
   - Duke's Karsh program requires financial need.
   - UCF publishes conflicting renewal GPAs (3.0 and 3.2) on the same page.
4. **The merit profile can't name programs, and has a labeling bug.**
   - H2A covers only students with no financial need. Zero H2A recipients does not mean the school has no merit programs.
   - The live `institutional_aid_academics` flag (`20260627133000_materialize_public_serving_paths.sql:77`) ORs H.1401 (non-need) with H.1411 (need-based). The site can therefore claim a school uses academic merit criteria when the school only checked the need-based box.

## Goals

- **G1:** Publish 75 to 100 verified programs at launch, chosen from the 76-program research seed plus Stamps partners. Each record needs official-source evidence, an entering-year label and a review date.
- **G2:** Keep the record format accurate about selection, coverage, amounts, deadlines, renewal and stacking. No false flags like "full ride", "guaranteed" or "stackable".
- **G3:** Show the directory on school pages next to the CDS merit profile, and on a filterable `/scholarships` index.
- **G4:** Serve it through the public API (PostgREST view) and as a versioned CC BY-SA data download.
- **G5:** Keep it fresh: a full agent re-verification once a year with owner spot-checks, automatic change detection weekly from July to January, and stale terms shown as stale.
- **G6:** Fix the H14 conflation (M0).

## Non-goals

- Personalized award estimates, eligibility calculators or "your chances" odds.
- Outside or portable scholarships (Jack Kent Cooke, Daniels, Fastweb-style awards). They may appear later, clearly tagged.
- Consortium and access programs (QuestBridge, Posse, Bonner). QuestBridge is need-based; Posse is a nomination-based full-tuition leadership award. They are excluded from v1; tagging them is a later phase (see open decisions).
- Athletic scholarships by sport, which need EADA data and NCAA rules and get their own PRD.
- Graduate awards.
- Rankings. This is not a ranking product (VOICE.md). Sorting is factual (deadline, coverage); there is no "best scholarships" list.
- Exhaustive grids of every automatic award tier. MeritPlaybook owns that space. MVP includes only named National Merit packages and named flagship tiers.
- Copying third-party directory text or their selection of programs.

## Product principles

1. **The school's page is the authority.** Third-party lists are leads; every published fact comes from an official page. Programs administered by a foundation tied to the school, such as UVA's Jefferson Scholars, use the foundation's official page and say so.
2. **Every record names its year.** Each record carries the entering class its terms apply to. Undated recurring deadlines stay marked recurring and are never rolled forward into a dated deadline.
3. **Unknown is not no.** A blank field never means "false", "zero" or "unrestricted". A conflicting source shows as a conflict, not as a confident value.
4. **Being considered is not winning.** "Automatically considered" and "guaranteed to everyone who qualifies" are different fields.
5. **No made-up totals.** We never add up components, multiply an annual amount by four, or present "up to" as a promise. Totals the school itself advertises are quoted with their scope.
6. **CDS and named programs stay separate.** Each keeps its own year label and source. A named award never "explains" the H2A average.
7. **The source is one click away.** VOICE.md applies: the page says "as the school published it", keeps the pipeline out of product copy, and shows the source line.

## Detailed design

### M0: Prerequisites

- **Fix the H14 flag.** Expose `merit_criteria_academics` (H.1401) and `need_criteria_academics` (H.1411) separately in `school_merit_profile_cache`.
  - The original definition is in `supabase/migrations/20260503120000_school_merit_profile.sql`. The cache is in `20260627133000_materialize_public_serving_paths.sql`.
  - Keep the old column for compatibility and mark it deprecated in the API docs.
  - Update `MeritProfileCard.tsx` and `web/src/lib/public-data.ts`.
  - The conflation is confirmed in both the original view (line 64) and the live cache (line 77).
- **Commit the research reports** to `docs/research/` (see "What happens on approval").

### M1: Record format, authoring files and validator

**Where records live.** Hand-reviewed YAML under `data/scholarships/`, one file per program, holding every entering-year version:
- `data/scholarships/programs/<school_id>/<program_slug>.yaml`
- `data/scholarships/LICENSE`: CC BY-SA 4.0, adapted from `data/discovery/LICENSE`. It must state plainly what is excluded: third-party text, quoted excerpts, trademarks and source PDFs.
- `data/scholarships/README.md`: the contribution gate (same agreement as `data/discovery/`), sourcing rules, a field guide and an attribution example.
- `data/scholarships/schema/program.schema.json`: JSON Schema.

Records are edited through pull requests rather than an admin UI. That gives every edit a review, a diff and an audit trail, and matches the reviewed-change practice used elsewhere in the repo. Published versions can't be edited; a correction adds a new version with `supersedes`.

**Record structure.** It follows the research taxonomy, trimmed for the MVP.

*Program (stable across years)*
- `program_id` (slug, stable across renames), `school_id`, `ipeds_id`, `applicable_campuses`
- `official_name`, `aliases`, `program_family` (stamps | national_merit | presidential | honors | other)
- `awarding_authority` (institution | affiliated_foundation | cofunded | unknown)
- `related_programs`: a list of {program_id, relation}, where relation is component_of | includes | replaces | mutually_exclusive_with | successor_to. Examples: Robertson is one program at both Duke and UNC; UGA's Stamps sits inside its Foundation Fellowship; Oxford and Atlanta Woodruff.
- `status`: active | paused | closed_to_new_entrants | merged | discontinued | unknown

*Version (one per entering class)*
- `entry_year`, `entry_terms`, `source_cohort_text` (the school's own wording)
- `verification_status`: verified | needs_review | conflicting | historical_only | unverified
- `last_checked_at`, `last_reviewed_at`, `reviewed_by` (agent run id or person), `owner_spot_checked` (bool), `next_reverify_at`

*Offers (variants within a version: resident, nonresident, a tier)*
- `variant_name`, `residency`
- `selection_mode`: automatic_guaranteed | competitive | hybrid | unknown. `automatic_guaranteed` requires an explicit official promise.
- `consideration_route`: admission_application | separate_application | honors_application | nomination | invitation | multiple
- `aid_basis`: merit_only | merit_and_need | unclear. `need_role`: required | considered | not_considered | top_up_only | unknown.
- `funds_limited`

*Eligibility*
- `national_merit_statuses`: semifinalist | finalist
- `first_choice_required`
- GPA: min, scale, basis (weighted, unweighted, recalculated by the school)
- `test_rules`: a list of {exam, min, scoring: single_sitting | superscore, official_required}
- `tests_policy_for_scholarship`, which is separate from the admission test policy
- `residency_eligible`, `citizenship_eligible`
- `majors_allowed`, `major_change_restrictions`, `honors_requirement`, `first_generation_rule`
- free-text `eligibility_notes`

The research proposes an expression tree for eligibility logic. It is deferred until v2: flat fields plus notes cover the seed set.

*Benefits (a list of components)*
- `category`: tuition | mandatory_fees | housing | meals | books | laptop | stipend | study_abroad | enrichment | health_insurance | other
- `instrument`: scholarship | tuition_waiver | cash_stipend | restricted_fund | earned_compensation
- `coverage`: full | partial | fixed_amount | variable
- `amount`: {qualifier: exact | range | up_to | at_least | approximate | not_published, value, min, max, period: semester | academic_year | one_time | total_program}
- `duration_terms`, `exclusions`, `scope_text`
- `advertised_coverage_label` (the school's own words)
- `normalized_coverage`: full_tuition | full_tuition_fees | tuition_housing_meals | full_school_coa | partial_or_fixed | other. There is no "full ride" value; the page derives a display label only when the components support it.

*Application and deadlines*
- `separate_application`: required | encouraged | not_required | invitation_only
- `milestones`: a list of {kind, requirement: required | priority | recommended | invitation_only, date or recurring month/day, precision, source_date_text}
- `interview_mode`, `finalist_event_required`

*Renewal and stacking*
- `renewal_rules`: GPA, credit load, evaluation timing, whether summer courses can fix a shortfall, `max_semesters`
- `stacking_rules`: a list of {other_aid_type, relation: allowed | not_allowed | replaces | counts_within_package}
- `award_counts`: a list of {metric: offers | new_recipients | target | share_of_class, qualifier, value, cohort_year, source}

*Evidence*
- `sources`: {url, authority: official_program | official_aid_policy | official_admissions | official_news | archived_official | foundation_official, retrieved_at, content_sha256, archive_url}
- `field_evidence`: {field_path, source_ref, locator, short_excerpt (≤25 words, optional), value_status: reported | not_published | conflicting}

**Validator.** `tools/scholarships/validate.py`, run by pytest in CI (`.github/workflows/ci.yml`). It checks:
- The record matches the JSON Schema.
- `school_id` and `ipeds_id` resolve together. Reuse the `tools/finder/identity_guard.py` helpers (`normalize_ipeds`) and the checked-in identity snapshot.
- Every source is on the school's domain (`normalize_domain`) or an allowlisted affiliated-foundation domain, and every source is marked as official.
- Publication-grade fields (amounts, selection mode, deadlines, separate application, NM status) have `field_evidence`.
- `automatic_guaranteed` has evidence.
- A `verified` version has `last_reviewed_at`, `reviewed_by`, and an `entry_year` or an explicit unconfirmed label.
- No milestone date falls outside the version's application cycle.
- `relation` targets exist.
- Published versions haven't changed. A git-diff check in CI enforces this.

### M2: Storage, public view and API

- **Migration** `supabase/migrations/<ts>_scholarship_directory.sql`:
  - `scholarship_programs`: program-level columns.
  - `scholarship_program_versions`: typed filter columns plus a `record jsonb` column holding the full version.
  - `scholarship_sources`.
  - A materialized `scholarship_directory_cache` with a thin `scholarship_directory` security_invoker view and a `refresh_scholarship_directory_cache()` function. This copies the `school_merit_profile` pattern from `20260627133000_materialize_public_serving_paths.sql`.
  - Grant SELECT to anon and authenticated.
  - The public view shows only the latest version per program that is verified or marked past-cycle, plus a `freshness_status`: current_cycle_verified | current_cycle_unconfirmed | past_cycle | conflicting.
- **Loader** `tools/scholarships/load.py`:
  - Reads the validated YAML and upserts by `program_id` and `entry_year` (idempotent), then refreshes the cache.
  - It runs from `main` after merge (`.github/workflows/scholarships-load.yml`), following the migrations-from-main rule.
- **Download:** `web/public/data/scholarships-v<N>.json`, a versioned snapshot with license and attribution metadata, built by the loader.
- **API docs** in `web/src/app/api/page.tsx`: a `scholarship_directory` table entry and curl examples (one school's programs; National Merit packages with housing), copying the `school_merit_profile` entries.

### M3: Web pages

- **`ScholarshipProgramsCard`** (`web/src/components/`), rendered on `web/src/app/schools/[school_id]/page.tsx` directly after `MeritProfileCard`. Each program shows:
  - name, a coverage summary from its components, how you're considered, the key deadline, and a renewal summary;
  - a freshness line, a new design-system pattern: "Terms for fall 2027 entry, as published on the school's page Nov 8, 2026 · official page ↗". VOICE.md forbids implying that collegedata.fyi checked the school's figures, so "verified" stays an internal status and never appears in product copy;
  - an amber note for past-cycle or conflicting records.

  When a school has no records yet, the card says "No named programs documented yet", which is different from "this school has none".
- **Separate panels.** The CDS merit card and the program card keep separate year labels and sources. Shared copy: "School-wide CDS figures describe <year>. The programs below are documented separately for <entry year> entry and are not an estimate of any student's award."
- **`/scholarships` index**, a filterable table. Filters:
  - coverage (full tuition / tuition plus housing and meals / fixed amount)
  - selection (competitive / guaranteed if eligible)
  - National Merit (semifinalist / finalist)
  - separate application
  - deadline month
  - residency
  - school

  Sorting is by deadline, school or coverage, never "best". Coverage by school type and region is published on the page so the selective-school skew is visible.
- **`/methodology/scholarships`**, modeled on `web/src/app/methodology/merit-profile/page.tsx`: sourcing rules, field definitions, freshness states, what not to infer, and how to report a correction.
- **Corrections:** a "Report an update" link to a GitHub issue template (`.github/ISSUE_TEMPLATE/scholarship-correction.yml`) that asks for the official URL. There are no accounts and no collected PII.
- **Copy:** draft first in `docs/copy/036-scholarships.md` for Anthony's read-through, then implement (VOICE.md process). Read `web/DESIGN_SYSTEM.md` and use the tokens.

### M4: Change monitoring

- **`tools/common/polite_fetch.py`** (new, shared). The repo currently has no robots.txt handling. This module adds:
  - robots.txt per RFC 9309, cached for 24 hours; an unreachable robots file blocks fetching;
  - Crawl-delay honored;
  - the existing `collegedata-fyi-*` User-Agent with contact URL;
  - at most one request at a time per host;
  - conditional GET (ETag and Last-Modified) and backoff that respects Retry-After;
  - no logins, CAPTCHAs or portals.
- **`tools/scholarships/monitor.py`:**
  - For each version, fetch its authority URLs and linked PDFs.
  - Hash the raw bytes, plus a hash of the normalized main text (versioned, so a parser change doesn't look like an award change).
  - On a change, run a deterministic diff on amounts, dates, selection words and years. Mark the version `needs_review` and open a GitHub issue with the diff and an Archive.org snapshot link. Never auto-publish.
  - Check for staleness: an entry-year heading older than the target class, a heading year that conflicts with body or deadline years, all deadlines past with no next-cycle signal, or a 404 (that alone never proves a program ended).
- **Workflow** `.github/workflows/scholarships-monitor.yml`: weekly from July to January, monthly from February to June. It also rechecks each required or priority milestone 30 days and 7 days before it.
- **Annual review, August to September.** Each program gets an agent re-verification for the next entering class, with the owner spot-checking each batch (same process as M5). A program still unconfirmed 30 days before its likely early deadline is shown as past-cycle; last year's dates are never carried forward.

### M5: Seeding and LLM-assisted drafting

- **Lead sources**, used only as leads:
  - the 76-program research seed
  - the Stamps partner directory, excluding partners not accepting applications
  - the NMSC college-sponsor leaflet, pinned to its edition
  - College Transitions and MeritScholarships.org for discovery only
- **Drafting:** `tools/scholarships/draft.py` fetches official pages through `polite_fetch`. It asks `tools/extraction_worker/llm_client.py` (Anthropic SDK, prompt caching) for a draft YAML with `field_evidence` locators, then runs the validator. Drafts go to `scratch/scholarships/` and never straight to `data/`.
- **How a record gets verified.** This matches how the owner works: agent-curated content is trusted when it comes with its reasoning and an audit trail.
  1. An agent re-checks every publication-grade field against the live official page and records a locator for each.
  2. For amounts and deadlines, it also saves a page screenshot to the PR as an artifact.
  3. The agent sets `verified` and `reviewed_by`.
  4. Anthony spot-checks a sample per batch PR: at least 5 programs, plus every `conflicting` or `automatic_guaranteed` record. That sets `owner_spot_checked`.
  5. The merge is the publication decision.
- **Launch order.** Each batch is a PR.
  1. 20 canary programs that exercise every edge case: Tulsa NMSF, Alabama NMF and tiers, Oklahoma nonresident, Texas A&M, UCF (conflict), Georgia Tech Stamps, W&L Johnson, Vanderbilt (CV plus retired Chancellor's), BC Gabelli, Duke Karsh (need required), Robertson (joint), UGA Foundation and Stamps (nested), USC NM (cut), Tuskegee, NC A&T Cheatham-White, Ole Miss tiers, Arizona, Ohio State Stamps (portal lead time), UMD Banneker/Key (tiers), Purdue (resident/nonresident).
  2. Expand to 75 to 100 programs.

  Coverage targets include HBCUs and regional publics, not just selective privates.

### ARCHITECTURE.md

Add a "Scholarship directory" pipeline, numbered 13 so the existing pipelines keep their numbers. Add `scholarship_directory` to the Consumer API's list of served views.

## Edge cases the record format must handle

Each comes from an official page:
- **Interview or visit required.** Tulsa NMSF is selective even though it's tied to National Merit status.
- **Waiver vs scholarship.** Texas A&M and Florida State include nonresident waivers. A waiver is never tuition coverage.
- **Coverage that doesn't track tuition.** USC National Merit is now a fixed $20,000. Ole Miss's top tier is fixed at first-year tuition.
- **Contradictions on one page.** UCF lists two renewal GPAs; Oklahoma's heading says Fall 2026 while its deadlines are 2026/2027.
- **A retired program with current recipients.** Vanderbilt Chancellor's.
- **Admission and scholarship deadlines that differ.** Ohio State Stamps has a separate deadline about five days after its portal opens.
- **Need required inside a merit program.** Duke Karsh, Duke University Scholars.
- **One shared, nested or merged program.** Robertson (Duke and UNC), UGA Foundation and Stamps, UGA Ramsey merged into Foundation.
- **Different counts for the same program.** W&L says "up to 44"; Georgia Tech targets 50 offers; Indiana Wells says about 14 in one place and about 18 in another.

## Success metrics

- Launch: 75 or more verified programs, 100% with official evidence and entering-year labels, and at least 15% outside the most selective tier (HBCUs, regional publics).
- Freshness: by October 1 each cycle, at least 90% of active programs are `current_cycle_verified`. The median time from a detected change to a published update is under 7 days during July to January.
- Accuracy: an audit sample of 20 programs per cycle has no material error in amount, selection mode or deadline. Corrections are logged publicly.
- Usage: school-page card views and `/scholarships` filter use, read from existing analytics. API calls to `scholarship_directory`.

## Risks

| Risk | Mitigation |
|---|---|
| A family reads a maximum or "full tuition" as a guaranteed full ride | Coverage built from typed components; the page never says "full ride" on its own; exclusions shown; the "considered vs guaranteed" wording |
| A stale deadline costs someone a deadline | Entering-year label; past-cycle shown in amber; checks 30 and 7 days before each milestone; "confirm on the official page" next to every date |
| Third-party compilation rights | Leads only; facts re-taken from official pages and paraphrased; a house policy of excerpts of 25 words or fewer (not a legal safe harbor); an explicit list of what the license excludes |
| The directory leans toward selective schools and full rides | Seeding quotas; coverage published by school type and region |
| Maintenance burden grows with the record count | The monitor only flags changes; the annual review is batched by deadline month; scope held at 100 until the freshness metric holds for one full cycle |
| Program counts read as odds | `award_counts` carries a metric and a denominator; no probability shown |
| CDS and named programs blended | Separate panels, years and sources; shared copy that says so; methodology section |

## Milestones and shipping order

| Milestone | Ships | Effort (human / CC) |
|---|---|---|
| M0 | H14 flag fix plus research docs | ~1 day / ~1 hr |
| M1 | Record format, LICENSE/README, validator, 20 canary programs | ~2 wks / ~1–2 days plus an owner spot-check |
| M2 | Migration, loader, cache and view, JSON download, API docs | ~1 wk / ~0.5 day |
| M3 | Card, `/scholarships`, methodology, corrections template, copy review | ~1.5 wks / ~1 day plus copy review |
| M4 | polite_fetch, monitor, workflows, annual review runbook | ~1 wk / ~0.5 day |
| M5 | Expand to 75–100 verified programs | ~3 wks / ~2–3 days plus owner spot-checks (about 1 hour per batch) |

M1 through M3 can ship with the 20 canaries before M5 adds the rest. The monitor (M4) must be running before the first July-to-January cycle after launch.

## Verification and acceptance

- CI: the validator rejects a fixture with each banned pattern:
  - `automatic_guaranteed` without evidence
  - a summed total
  - an off-domain source
  - an edited published version
  - a mismatched `school_id`/`ipeds_id`
- For the 20 canaries, the agent's evidence (locators and screenshots) is in the PR. Anthony spot-checks them, and the checks are recorded in the PR checklist.
- After the load from `main`: `scholarship_directory` returns the canaries, `freshness_status` is computed correctly for a past-cycle fixture, and an anon-key curl works.
- Web: the card renders for a school with programs and shows the honest empty state for one without; the index filters work; a Playwright check of `/schools/tulsa` and `/scholarships`.
- Monitor: a dry run against canary URLs; a fixture that changes an amount opens a `needs_review` issue; robots disallow and an unreachable robots file both block fetching.
- M0: the API returns separate academic merit and academic need flags; the merit card shows the corrected copy.

## Open decisions (recommendations included)

1. **Foundation-administered, school-tied programs** (Jefferson/Walentas, Morehead-Cain, Robertson). Recommend **include**, with `awarding_authority: affiliated_foundation`, because families think of them as the school's program.
2. **Automatic award tiers.** Recommend **named National Merit packages and named flagship tiers only** in v1; defer full grids.
3. **Contribution gate.** Recommend the **same agreement as `data/discovery/`**, so the maintainer keeps the right to relicense.
4. **Posse and similar nomination-based consortium awards.** Recommend **phase 2**, tagged `program_family: consortium`, because eligibility depends on a recruitment city rather than the school's admissions process.
5. **Open Scholarships (CC BY 4.0, Nevada)** as an import. Recommend **later**: it's out of scope (state and private aid) and would need attribution handling.
