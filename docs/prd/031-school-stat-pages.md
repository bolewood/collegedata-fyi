# PRD 031: Per-school stat pages (acceptance rate first)

**Status:** Rev 2 (2026-09-23), after red-team review. M1 is decided: public URLs use the name people search (`/schools/virginia-tech`). Acceptance-rate pages are indexable.
**Author:** Anthony Showalter (with Claude)
**Related:** [PRD 028](028-organic-search-cds-queries.md), [GSC CDS memo](028-gsc-cds-queries-2026-08.md), [PRD 014](014-cross-year-canonical-schema.md) (cross-year schema; M0 dependency), [PRD 019](019-cds-change-intelligence.md), [`web/VOICE.md`](../../web/VOICE.md), [`web/DESIGN_SYSTEM.md`](../../web/DESIGN_SYSTEM.md), copy deck [wave 5](../copy/wave-5-school-page-numbers.md)

---

## What changed from rev 1

Rev 1 proposed four stat templates at corpus scale, justified by a "rate by
year" story. A red-team review and a production count (below) showed that
story is not in the data yet. Rev 2:

- **Measures year depth instead of guessing.** The source rev 1 allowed has
  no history at all (see "Measured depth"). A projection backfill is now M0
  and gates everything else.
- **One URL, not four.** Pilot `/schools/{id}/acceptance-rate` only. Early
  decision is second, after a real C21 note is on the page. Waitlist and test
  scores wait for the first URL to be indexed.
- **PRD 028 M4 stays closed.** Virginia Tech was position ~3.8 in August,
  which is page one but not top 3, and M4 described a field-level year URL
  that this PRD rejects. This pilot stands on its own evidence and a sitemap
  cap. It does not cite M4.
- **Freezes the canonical slug first** (M1). Decided: `/schools/virginia-tech`
  is the public URL; the legal-name slug stays a live alias and 308s here.
- **Drops** the 3× human-review gate, Dataset JSON-LD, the IPEDS comparison
  row, and all "odds" wording.
- **Fixes the eligibility query** (per-metric latest year, ACT counted,
  waitlist bounds, alias folding, served documents only).
- **Adds a de-eligibility rule:** an indexed URL never silently 404s.
- **Cannibalization:** the stat page leads with the multi-year span; the hub
  keeps the single-year sentence and links the stat page.

Corrections to the review: `web/src/lib/school-summary.ts` shipped to `main`
in [#184](https://github.com/bolewood/collegedata-fyi/pull/184) (v0.6.6.0),
so the sentence and sanity-check dependency is merged, not on a branch. The
waitlist bound the review flagged also applied to the live hub sentence; it
is fixed in the same change as this revision (2 of 211 live waitlist
sentences had contradictory counts and are now omitted).

## Measured depth (production, 2026-09-23)

Queries are checked in under `scratch/seo/` on the operator machine and
reproduced in the appendix. All counts fold live alias slugs into their
canonical slug and exclude removed, withdrawn, and quality-flagged rows.

| Measure | Value |
|---|---:|
| `school_browser_rows` whole-institution rows | 736 |
| …of those before 2024-25 | **0** |
| `cds_fields` rows before 2024-25 | **0** |
| Schools with a usable acceptance year | 411 |
| …with exactly 1 usable year | 263 |
| …with 2 usable years (the maximum possible) | 148 |
| Median usable acceptance years | 1 |
| Eligible today under rev 1 rules: acceptance / ED / tests / waitlist | 148 / 27 / 157 / 44 |
| Extracted public reports before 2024-25 (all schools) | 4,309 |
| Schools with any extracted pre-2024 report | 632 |
| Schools with ≥ 5 extracted years since 2018-19 | 408 |

Why: the browser projection hard-codes `MIN_YEAR_START = 2024`
(`tools/browser_backend/project_browser_data.py`) and its field map only
covers the 2024-25 and 2025-26 templates. Older year pages show numbers
because they read the extract artifact directly; those values never reach
the tables a stat page would query.

So today every "history" would be two years at most, and the eligibility
rule would correctly produce a short list of 148 two-row tables. That is not
worth a new URL. The files for a real history exist (4,309 extracted older
reports); whether their admissions fields are sane is unknown until they are
projected. The reviewer's examples show it varies by school: Duke 2018-19
yields a rate, Northeastern 2018-19 does not, Virginia Tech 2016-17 is not
extracted.

## Milestones

### M0 — History backfill (prerequisite, its own PR)

1. Extend the projection below 2024-25 for the admissions fields this page
   needs: C1 applied/admitted/enrolled totals (gender-split on older
   templates), C21 ED counts, C2 waitlist counts, C9 SAT/ACT percentiles.
   Map each older template's field IDs explicitly; do not guess.
   **Dependency:** [PRD 014](014-cross-year-canonical-schema.md) found that
   documents were extracted against the current template's field IDs, and
   older templates move and split fields. Pre-2024 extracts may hold C1
   values under the wrong IDs, which would explain the school-by-school
   variation (Duke 2018-19 yields a rate; Northeastern 2018-19 does not).
   Confirm PRD 014's year-aware mapping covers the pre-2024 templates, or
   re-extract, before trusting any backfilled number.
2. Write the projected rows to a history table (or `school_browser_rows`
   with a `history` flag). Do not change which rows existing browse/match
   cards read; those stay `year_start >= 2024`.
3. Re-run the appendix query and **record the per-metric yield in this PRD**:
   how many schools reach ≥ 3 and ≥ 5 usable acceptance years.
4. Go/no-go for M2: at least **150 schools with ≥ 4 usable acceptance years**
   ending 2023-24 or later. Below that, stop: the product is a short list and
   the hub's year-over-year line already covers it.

M0 is useful even if M2 never ships: year pages and the hub summary gain
sanity-checked numbers for older years.

### M1 — Freeze the canonical slug (decision, then data change)

Decide whether `virginia-tech` or
`virginia-polytechnic-institute-and-state-university` is canonical, and the
same for the other split pairs (Rutgers, Texas A&M, UVA, Georgia Tech,
Caltech, Tulane, UChicago, UW). Apply it through the crosswalk from `main`,
update PRD 028's "protect" canary to the frozen URL, and wait for GSC to
show the frozen URL as the ranking page. No stat URL enters a sitemap before
this.

### M2 — Pilot: `/schools/{id}/acceptance-rate`

Only after M0's go and M1.

- **Allowlist is the sitemap.** Named schools only: Virginia Tech, Haverford,
  Brown, Northeastern, Duke, plus up to 45 more by GSC impressions on their
  school/year pages. The route 404s for any school not on the allowlist,
  even if eligible. Expansion is a code change to the allowlist, reviewed
  against the pilot readout.
- **Measure 6 weeks** (see Success metrics). Kill signal: more than a third
  of pilot URLs "Crawled – currently not indexed," or any drop in the Virginia
  Tech head term.

### M3 — Early decision page

After M2 is indexed and earning impressions, and only for schools whose own
C21 "significant details" note is present in the extract and shown on the
page (not a stock disclaimer). This is the stronger long-term wedge (IPEDS
cannot answer it) and the easier page to get wrong.

### Later (not scheduled)

Waitlist and test-score pages, after M3. IPEDS comparison block, as a
separate project with cohort-year alignment. Ranked cross-school lists.

## The acceptance-rate page

Follow `web/DESIGN_SYSTEM.md` and `web/VOICE.md` (product layer). Draft the
copy in `docs/copy/` before code.

1. **Breadcrumb:** Schools / {school} / Acceptance rate.
2. **H1:** `{school} acceptance rate`.
3. **Lead: the span, not the single year.** Generated only from usable
   years: "{school}'s reports from 2018-19 to 2025-26 show the acceptance rate
   going from X% to Y%." Missing years are named ("no usable report for
   2020-21"). The hub keeps its single-year sentence and links "acceptance
   rate" here, so the two URLs do not repeat each other.
4. **Table**, newest first: year, applied, admitted, acceptance rate,
   enrolled, yield, link to the year page and the original file.
5. **Definition note (meta style):** "From each year's Common Data Set,
   section C1: first-time, first-year, degree-seeking applicants and admits."
6. **Related:** hub, latest year page.

No chart in the pilot. No federal numbers on the page. No prose beyond
generated sentences.

### Title, description, structured data

- **Title:** `{school} Acceptance Rate by Year, {first}–{last}`. The span is
  taken from **usable** years only. A school with usable years 2021-22 to
  2025-26 is titled "2021–2025", never the archive's full span.
- **Description:** span sentence + latest rate + "with the original files."
- **Canonical:** the page itself.
- **Structured data:** `BreadcrumbList` only. No `Dataset`: the school
  published a Common Data Set, we published a derivative table, and a
  `creator` of the school would say otherwise.

### Wording rules

- No "odds," "chances," or "admit odds" anywhere: route, title, headings,
  alt text.
- Rates are "acceptance rate" (admitted ÷ applied), never "admission odds."
- When waitlist pages come later: the rate is admitted from the waitlist ÷
  **accepted a spot**, shown with offered a spot beside it, labeled
  "admitted from the waitlist." Never "odds."
- When test-score pages come later: keep "enrolled students who sent
  scores" in the H1 and lead. The page does not answer "is {school}
  test-optional" (that is C8 policy, not C9 scores) and must not claim to.

## Eligibility (acceptance rate)

A pilot school's page is served only if all hold:

1. On the allowlist.
2. At least **3 usable years** (usable = extracted, public, not
   `wrong_file`/`blank_template`/`low_coverage`, `applied > 0`,
   `0 ≤ admitted ≤ applied`).
3. The latest **usable acceptance** year is 2023-24 or newer (per metric,
   not the school's latest row of any kind).

Otherwise 404, and nothing links to it.

### Once a URL has been in the sitemap

It never silently 404s. If it later fails eligibility (a quality flag flips,
a year is withdrawn):

- Serve the last good table with a meta note naming the withdrawn year, and
  keep it in the sitemap, **or**
- Return **410** deliberately after a human decision, and drop it from the
  sitemap in the same change.

Implementation: store the set of URLs ever submitted (a checked-in list for
the pilot is enough) and test that each still returns 200 or an explicit 410.

### Adjacent-year check (replaces rev 1's 3× gate)

Real selectivity shifts and bad extracts look alike across a span (a 27% →
5% drop is real for Northeastern). So nothing blocks publication of a
sourced table. Instead: when an adjacent-year change in applied, admitted,
or rate exceeds 2×, emit a PRD 019 change-intelligence candidate for that
document pair. The existing verification queue owns it. A confirmed
extractor error flags the document, which removes the year from the table
under the rules above.

## Success metrics (pilot, 6 weeks after sitemap submission)

- ≥ 2/3 of pilot URLs indexed.
- Impressions for `{school} acceptance rate` queries landing on the stat URL,
  not the hub. If Google keeps showing the hub for those queries, that is
  cannibalization; revisit the lead before expanding.
- No drop in the Virginia Tech head term (PRD 028 guardrail) or in hub CTR
  for pilot schools.

## Risks

| Risk | Mitigation |
|------|-----------|
| No real history after backfill | M0 go/no-go with a measured threshold |
| Scaled-content classification | One template, ≤ 50 URLs, allowlist = sitemap, kill signal |
| Hub/stat cannibalization | Span lead on stat page; hub keeps single year and links it |
| Title span overstates data | Span from usable years only; tested |
| Bad extract published as "the rate" | Sanity bounds + flags + adjacent-year candidates into the PRD 019 queue |
| Slug move on the ranking term | M1 before any stat URL is submitted |
| Indexed URL disappears overnight | Never-silent-404 rule and test |

## Appendix: eligibility / depth query

```sql
-- Read-only. Folds live aliases; per-metric latest year; served docs only.
with alias_map as (
  select c.alias, min(c.school_id) as canonical
  from institution_slug_crosswalk c
  where c.alias <> c.school_id
    and c.alias <> 'tufts-university'            -- retired aliases never fold
    and not exists (select 1 from institution_slug_crosswalk p
                    where p.alias = c.alias and p.is_primary and p.school_id = c.alias)
  group by c.alias
  having count(distinct c.school_id) = 1
),
rows as (
  select coalesce(a.canonical, r.school_id) as school, r.year_start,
    (r.applied > 0 and r.admitted between 0 and r.applied) as acc_ok,
    (r.ed_applicants > 0 and r.ed_admitted between 0 and r.ed_applicants) as ed_ok,
    ((r.sat_composite_p25 between 400 and 1600 and r.sat_composite_p75 between r.sat_composite_p25 and 1600)
      or (r.act_composite_p25 between 1 and 36 and r.act_composite_p75 between r.act_composite_p25 and 36)) as test_ok,
    (r.wait_list_offered > 0 and r.wait_list_admitted between 0 and r.wait_list_offered
      and (r.wait_list_accepted is null
           or r.wait_list_accepted between r.wait_list_admitted and r.wait_list_offered)) as wl_ok
  from school_browser_rows r
  join cds_manifest m on m.document_id = r.document_id
  left join alias_map a on a.alias = r.school_id
  where r.sub_institutional is null
    and m.removed_at is null
    and coalesce(m.participation_status, '') not in ('withdrawn', 'verified_absent')
    and coalesce(r.data_quality_flag, '') not in ('wrong_file', 'blank_template', 'low_coverage')
),
per_school as (
  select school,
    count(distinct year_start) filter (where acc_ok)  as acc_years,
    max(year_start)            filter (where acc_ok)  as acc_latest,
    count(distinct year_start) filter (where ed_ok)   as ed_years,
    max(year_start)            filter (where ed_ok)   as ed_latest,
    count(distinct year_start) filter (where test_ok) as test_years,
    max(year_start)            filter (where test_ok) as test_latest,
    count(distinct year_start) filter (where wl_ok)   as wl_years,
    max(year_start)            filter (where wl_ok)   as wl_latest
  from rows group by school
)
select
  count(*) filter (where acc_years >= 3 and acc_latest >= 2023) as eligible_acceptance,
  count(*) filter (where acc_years >= 4 and acc_latest >= 2023) as m0_go_threshold,
  count(*) filter (where ed_years >= 3 and ed_latest >= 2023)   as eligible_early_decision,
  count(*) filter (where test_years >= 3 and test_latest >= 2023) as eligible_test_scores,
  count(*) filter (where wl_years >= 3 and wl_latest >= 2023)   as eligible_waitlist
from per_school;
```

After M0, point `rows` at the history projection instead of
`school_browser_rows`.

## Open questions

1. **M0 scope:** backfill all of section C for 2018-19 onward, or only the
   C1 totals the pilot needs? (Author leans C1 + C21 + C2 + C9, since the
   template mapping work is shared.)
2. **M1 direction:** decided — searchable public slug (`virginia-tech`,
   `caltech`, `tulane-university`). The legal-name slug remains a live alias.
3. **Allowlist size:** 50 URLs, or fewer? The review's position is one
   template for the named schools only.
