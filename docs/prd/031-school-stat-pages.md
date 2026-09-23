# PRD 031: Per-school stat pages (acceptance rate, early decision, test scores, waitlist)

**Status:** Draft for review (2026-09-23). Not approved to build.
**Author:** Anthony Showalter (with Claude)
**Related:** [PRD 028](028-organic-search-cds-queries.md) (organic search; M4 gate this PRD asks to open), [GSC CDS memo](028-gsc-cds-queries-2026-08.md), [PRD 002](002-frontend.md), [PRD 019](019-cds-change-intelligence.md), [PRD 021](021-ipeds-coverage-layer.md), [`web/VOICE.md`](../../web/VOICE.md), [`web/DESIGN_SYSTEM.md`](../../web/DESIGN_SYSTEM.md), copy deck [wave 5](../copy/wave-5-school-page-numbers.md)

---

## Reviewer brief

You are reviewing a plan, not code. Please answer the **Open questions** at
the bottom and challenge anything in **Scope**, **Eligibility**, and
**Risks**. The author's bias is toward shipping; the house rules in PRD 028
(protect Virginia Tech, no manufactured essays, no parallel URL trees) are
binding unless you argue them down explicitly.

## Summary

Add four school-level pages that answer the most-searched CDS questions with
a multi-year table from the school's own reports:

| URL | Answers |
|-----|---------|
| `/schools/{id}/acceptance-rate` | `{school} acceptance rate`, `… acceptance rate history`, `… by year` |
| `/schools/{id}/early-decision` | `{school} early decision acceptance rate`, `ED vs RD` |
| `/schools/{id}/test-scores` | `{school} SAT scores`, `middle 50% SAT`, `test optional submit rate` |
| `/schools/{id}/waitlist` | `{school} waitlist acceptance rate`, `waitlist odds` |

One page per school per metric, never per year. A page exists only when the
school reported that metric in at least two usable years.

## Why (evidence)

1. **Demand we already see but cannot serve.** The August GSC export
   classified ~2,700 impressions as "Not CDS" noise: acceptance-rate,
   tuition, enrollment, and "is duke test-optional" queries hitting
   school/year pages that don't answer them (memo, "Noise to ignore"). That
   is the demand slice PRD 028 M4 said to wait for.
2. **The SERP is thin, federal-only, and beatable.** Checked 2026-09-23:
   - `northeastern acceptance rate history` → admitstats, preptodone,
     prepmaven, Ivy Coach. All IPEDS-derived tables or blog posts; none
     links the school's own file.
   - `duke early decision acceptance rate common data set` → Duke's PDFs,
     then College Transitions "Inside the Numbers" built from CDS C1 + C21.
     That article is this page, hand-written, for one school.
   - IPEDS has no early decision, waitlist, or test-submission-by-cohort
     detail. CDS does (C2, C21, C9). Competitors using IPEDS cannot show it.
3. **The data already exists.** `school_browser_rows` holds per-year
   `applied`, `admitted`, `enrolled_first_year`, SAT/ACT 25th/50th/75th,
   submit rates, `ed_applicants`, `ed_admitted`, `wait_list_offered`,
   `wait_list_accepted`, `wait_list_admitted`. The wave-5 school summary
   (branch `fix/seo-school-pages`) already renders these as sentences with
   sanity checks in `web/src/lib/school-summary.ts`.

## Scope

### In

- Four static-segment routes under `web/src/app/schools/[school_id]/`:
  `acceptance-rate/page.tsx`, `early-decision/page.tsx`,
  `test-scores/page.tsx`, `waitlist/page.tsx`. Static segments win over the
  `[year]` dynamic segment in the App Router; add a test that proves it.
- Same identity handling as school pages: `fetchCanonicalSchoolId` →
  `permanentRedirect` for aliases; data via the alias-aware fetchers
  (`fetchSchoolYearFacts`, which merges live alias slugs).
- Sitemap entries for eligible pages only, `lastModified` from the newest
  contributing document.
- Links in: school hub summary sentences link the metric phrase ("acceptance
  rate", "early decision", "middle-50% SAT", "Waitlist") to the page when it
  exists; year pages link the same phrases. Links out: each table row links
  the year page and the original file.

### Out (v1)

- Cost / net price pages (Section G + Scorecard mixing needs its own labeling
  design).
- Ranked cross-school lists ("lowest acceptance rates"). That is a separate
  project (hub pages); it will reuse these pages as link targets.
- Comparison pages (`/compare/a-vs-b`).
- Any per-year metric URL (`/2025-26/waitlist`). Rejected: multiplies near-
  duplicate pages by ~8x for no new answer.
- FAQ / HowTo structured data. Google restricted FAQ rich results in 2023;
  it is spam-prone at scale (PRD 028 M4 note).
- LLM-written prose of any kind.

## Page anatomy (all four)

Follow `web/DESIGN_SYSTEM.md` (paper, ink, one forest accent, tabular mono
numbers, `cd-card`) and `web/VOICE.md` (product layer). Reuse existing
components where they fit (`Sparkline`, school header plates, `ArchiveLead`
typesetting). Example numbers below are illustrative, not checked
against our extracts.

1. **Breadcrumb:** Schools / {school} / Acceptance rate.
2. **H1:** `{school} acceptance rate` (per page type). The school name
   stays in the H1 because that is the query.
3. **Answer sentence (first paragraph, server-rendered):** the latest year in
   plain English, reusing `yearSummarySentences` wording. Example:
   "In its 2025-26 report, Northeastern University says 98,373 first-year
   students applied and 5,115 were admitted, an acceptance rate of 5.2%."
4. **Trend line:** one sentence across the span, e.g. "Across 9 reports
   (2017-18 to 2025-26) the acceptance rate went from 27% to 5.2%." Only
   from reported years; gaps are named ("no report for 2019-20").
5. **Table:** one row per year, newest first. Columns per page type:
   - Acceptance: year, applicants, admitted, acceptance rate, enrolled, yield, source.
   - Early decision: year, ED applicants, ED admitted, ED rate, overall rate, ED share of admits, source.
   - Test scores: year, SAT 25/50/75, ACT 25/50/75, % submitting SAT, % submitting ACT, source.
   - Waitlist: year, offered, accepted a spot, admitted, admit rate from waitlist, source.
   "Source" links to the year page and the original file.
6. **Chart:** a small trend chart of the headline rate. Tabular numbers are
   the primary content; the chart is optional polish.
7. **Definition note (meta style):** what the CDS item counts, in English,
   with the section ID in the note only (e.g. "From the school's report,
   section C1."). Early decision page must note that schools define ED admit
   counts differently (Duke's includes QuestBridge and deferred-then-admitted
   students) and show the school's own C21 note text when present.
8. **Federal comparison (labeled):** when IPEDS has the same concept
   (`ADM*` admissions and test fields), one labeled row block "Federal
   (IPEDS) figure for {year}" with its source table, per PRD 021 labeling.
   Never blended into the CDS row. Omit on early decision and waitlist.
9. **Related:** links to the other metric pages for this school, the school
   hub, and the latest year page.

### Titles and descriptions

- Title: `{school} Acceptance Rate by Year (2017–2025) | collegedata.fyi`
  (span from data). Variants: `Early Decision Acceptance Rate`,
  `SAT & ACT Scores`, `Waitlist Acceptance Rate`.
- Description: answer fragment + span, e.g. "Northeastern's acceptance rate
  was 5.2% in 2025-26 (5,115 of 98,373). Every year from the school's own
  Common Data Set since 2017-18, with the original files."
- Canonical: the page itself. Never canonicalize to the school hub.

### Structured data

- `BreadcrumbList`.
- `Dataset` with `name` "{school} acceptance rate, 2017–2025",
  `variableMeasured` (e.g. "Acceptance rate", "Applicants", "Admitted"),
  `temporalCoverage` "2017/2026", `creator` the school, `provider`
  collegedata.fyi, `isBasedOn` the year-page URLs. No FAQ schema.

## Eligibility (the anti-thin-content gate)

A metric page is **indexable and in the sitemap** only if all hold:

1. At least **2 usable years** for that metric (usable = not
   `wrong_file`/`blank_template`/`low_coverage`, passes the sanity checks in
   `school-summary.ts`: admitted ≤ applied, 25th ≤ 75th, scores in range).
2. The **latest usable year is 2022-23 or newer** (stale pages rank badly
   and mislead).
3. For early decision: `ed_applicants > 0` in ≥ 2 years. For waitlist:
   `wait_list_offered > 0` in ≥ 2 years. For test scores: SAT or ACT range in
   ≥ 2 years.

Otherwise the route returns 404 (preferred over thin noindex pages; no
internal links point at it). Estimate eligible counts before building:

```sql
-- per-metric eligible schools (run read-only against production)
select
  count(*) filter (where acc >= 2 and latest >= 2022) as acceptance,
  count(*) filter (where ed  >= 2 and latest >= 2022) as early_decision,
  count(*) filter (where sat >= 2 and latest >= 2022) as test_scores,
  count(*) filter (where wl  >= 2 and latest >= 2022) as waitlist
from (
  select school_id, max(year_start) as latest,
    count(*) filter (where applied > 0 and admitted between 0 and applied) as acc,
    count(*) filter (where ed_applicants > 0 and ed_admitted between 0 and ed_applicants) as ed,
    count(*) filter (where sat_composite_p25 between 400 and sat_composite_p75 and sat_composite_p75 <= 1600) as sat,
    count(*) filter (where wait_list_offered > 0 and wait_list_admitted >= 0) as wl
  from school_browser_rows
  where sub_institutional is null
    and coalesce(data_quality_flag, '') not in ('wrong_file','blank_template','low_coverage')
  group by school_id
) t;
```

Note: the query groups by raw `school_id`; alias slugs (e.g. `virginia-tech`)
must be folded into their canonical slug first (see
`canonicalizeSchoolRows` in `web/src/lib/school-alias.ts`). Expected order
of magnitude: ~500–700 acceptance pages, fewer for the others. If
`school_browser_rows` only holds recent years for most schools, this PRD's
value drops sharply; confirm year depth first (open question 1).

## Rollout

1. **Pilot:** acceptance-rate and early-decision pages for the ~50 schools
   with the most GSC impressions on school/year pages (from the next GSC
   export), plus Virginia Tech, Haverford, Brown, Northeastern, Duke.
2. **Measure 6 weeks:** GSC impressions/clicks for queries containing
   `acceptance rate`, `early decision`, `sat`, `waitlist` landing on the new
   URLs; indexing status ("Crawled – currently not indexed" is the kill
   signal); no drop on the Virginia Tech head term.
3. **Expand** to all eligible schools and add test-scores and waitlist pages
   if the pilot pages are indexed and earning impressions. If more than a
   third of pilot pages sit in "crawled, not indexed" after 6 weeks, stop and
   rework the template before expanding.

## Success metrics (90 days after full rollout)

- New query class: ≥ 5,000 monthly impressions and ≥ 1% CTR on
  `{school} acceptance rate|early decision|sat|waitlist` queries.
- ≥ 70% of sitemap-listed stat pages indexed.
- Virginia Tech `common data set` head term stays top 3 (PRD 028 guardrail).
- Pages/visitor up from ~1.75 (stat pages link to year pages and files).

## Risks

| Risk | Mitigation |
|------|-----------|
| Scaled-content demotion | Eligibility gate; every page carries a school-specific multi-year table with sourced numbers; no templated prose beyond generated sentences; pilot before scale; kill signal defined. |
| Cannibalizing the school hub or year pages | Distinct intent: hub/year pages target `{school} common data set`; stat pages target the metric. Hub keeps its title. Watch GSC for URL flipping on the same query. |
| Wrong numbers (bad extraction) published as "the acceptance rate" | Sanity checks + quality flags; show source link per row; year-over-year jumps > 3x flagged for review before first publish (reuse PRD 019 change-intelligence events). |
| ED definitions differ by school | Definition note + school's own C21 note; never compute "RD rate" unless the school reports it (the Duke CDS/announcement mismatch is the canonical example). |
| Mixing federal and CDS numbers | Separate labeled block, PRD 021 labels; never in the same row. |
| Alias slugs split data (the Aug 25 regression) | Pages use alias-aware fetchers; add a Virginia Tech fixture test that 2025-26 appears. |
| Voice drift toward admissions advice | Copy deck first (VOICE.md "Shipping copy"); banned-words test extended to these pages. |

## Implementation notes for the builder

- Data: extend `fetchSchoolYearFacts` (or add a sibling) with the extra
  columns: `yield_rate`, `sat_composite_p50`, `act_composite_p50`,
  `sat_submit_rate`, `act_submit_rate`, `ed_offered`. Keep sanity rules in
  `school-summary.ts` so hub, year, and stat pages cannot disagree.
- Eligibility: one pure function `statPageEligibility(rows)` returning which
  of the four pages exist, used by the route (404), the sitemap, and the
  internal links. Unit-test it with Virginia Tech (alias merge), a school
  with one year, and a flagged file.
- Sitemap: add stat URLs from the same eligibility function; keep
  `lastModified`.
- Tests: route precedence (`acceptance-rate` vs `[year]`), canonical tags,
  alias redirect, VT fixture, banned copy, 404 for ineligible.
- Performance: pages are ISR (`revalidate = 3600`) like school pages; one
  `school_browser_rows` query per render.

## Open questions for the reviewer

1. **Year depth:** does `school_browser_rows` contain pre-2024 years for most
   schools, or mostly the latest? (School pages filter `gte("year_start",
   2024)` for cards, which suggests the table is deeper, but confirm.) If
   shallow, is backfilling the projection for historical extracts in scope?
2. **PRD 028 M4 gate:** M4 said field-level pages wait until VT holds top 3
   and two more gated-official schools earn clicks. The August memo shows VT
   at ~3.8 and Haverford, Brown, UCSB, WashU, UW with clicks. Is the gate
   met, or should this wait for the next GSC export?
3. **404 vs noindex** for ineligible metric URLs. The author prefers 404
   (no thin URLs exist at all). Any reason to keep a noindex stub?
4. **URL shape:** `/schools/{id}/acceptance-rate` vs
   `/schools/{id}/admissions` with all four sections on one page. One page
   is less risky for thin content but weaker for query targeting. Which?
5. **Canonical slug for Virginia Tech.** The Aug 25 crosswalk rows made the
   long federal slug canonical and `virginia-tech` a redirect. This PRD's
   pages will inherit that. Should the canonical flip back to
   `virginia-tech` before stat pages launch, so there is only one URL move?
6. **Federal comparison rows:** include IPEDS on acceptance and test-score
   pages in v1, or defer to keep the first version single-source?
