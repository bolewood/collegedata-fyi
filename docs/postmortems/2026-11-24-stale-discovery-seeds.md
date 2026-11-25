# Postmortem: why the archive silently missed 2025-26 files for about 150 schools

**Date found:** 2026-11-24
**Status:** Partly fixed. 117 of the 151 missed schools are archived; 34 are
found but not archived, and 43 searched schools have no answer yet.
Prevention work is open (see [Actions](#actions)).
**Tracking issue:** #452
**Fix PRs:** #453, #454, #455, #456, #457, #459
**Reviewed by:** Gemini 4 Neon (high) and Fable, 2026-11-24

## Summary

The site exists to collect each school's Common Data Set (CDS) every year.
For months it stopped doing that for a large share of schools, and nothing
that anyone read reported it.

On the morning of 2026-11-24, 476 schools had a 2024-25 document in the
archive. Only 236 of them, half, also had a 2025-26 one. By late November,
about 88% of a year's files have been produced (see
[When schools post](#when-schools-post)), so half was far too low.

We searched by hand the 273 schools whose newest year was 2023-24 or
2024-25. 151 of them had posted 2025-26 on their own site:

- 117 now have it in the archive.
- 34 have a file we found but could not archive yet: it sits behind
  SharePoint or a viewer, is posted as separate section files, or the
  school's site blocks our fetcher.

79 had not posted 2025-26, and 43 gave no answer after two search rounds.

After the fixes, 364 of 479 schools with a 2024-25 document also had a
2025-26 one (76%). 417 schools had a 2025-26 document, up from 278.

The monthly job built to catch this failed loudly four times, and each
failure was handled. Then, in November, it reported `ok` while its own summary said
71 of its 78 schools were still stuck. An issue had been collecting that
count every month since August, and no one acted on it.

## Terms used here

- **Seed:** the URL the archive starts from for a school, kept in
  `tools/finder/schools.yaml`. A good seed is the school's CDS listing page,
  which shows every year. A weak seed is the URL of one file.
- **Weekly refresh:** the archive job that revisits every seed and archives
  anything new it finds.
- **Monthly re-probe:** the job that looks for schools with weak seeds and
  searches the web (Brave Search) for a better one.
- **College Transitions mirror:** a third-party collection of CDS files we
  imported. It ends at 2024-25.
- **Filed year:** the CDS year the archive files a document under: the year
  read from the file, or the seed's year when the file can't be read
  (`canonical_year` in `cds_manifest`).

## How we found it

Not through monitoring. The same day, the extraction scoreboard used to
draft the public data quality page (PRD 040) counted live documents by year:
280 for 2025-26 against 503 for 2024-25. #452 opens with those two numbers
and investigates the gap.

## Impact

- **Missing current data.** For about 150 schools, the school's page showed
  an older year as the latest, with no sign that a newer one existed. 34 of
  them still do.
- **Wrong-year data.** 22 real 2025-26 documents were filed as 2024-25. Their
  admissions figures were compared with federal figures for the wrong fall.
  Re-filing them lifted the 2024-25 federal admissions match from 86.2% to
  89.9% (#431).
- **Missing older years.** The new listing pages turned up about 500 older
  documents we had never archived. They are being extracted.
- **Still unknown.** The 156 schools whose newest year is 2022-23 or older
  were not searched, so the true miss count is higher than 151.

## What went wrong

### 1. A one-file seed finds a new year only if the file is in one of two places

When a school's seed is one file, the resolver
(`supabase/functions/_shared/resolve.ts:1509-1555`) archives that file, then
walks its parent folders for sibling files. Only if that walk finds nothing
does it try the standard CDS paths on the school's site, such as
`/common-data-set`.

So a new year is found only when a parent folder's page links to it, or
when the school uses a standard path and the parent walk found nothing. A
school whose new file is linked only from a page the resolver never reads,
such as an office page elsewhere on the site, is missed. If the parent walk
finds older siblings, the standard paths are not tried at all. Either way,
weekly refresh re-verified the old file and recorded success.

### 2. We found this problem in August and fixed its shape, not its mechanism

On 2026-08-21 we hit the same failure at the University of Oklahoma (#133)
and Ohio University (#135). We fixed those two schools. Then an agent wrote
a monthly job, `tools/finder/stuck_pdf_seeds.py` (#134), to find every other
school in the same state.

The job described the Oklahoma case by its surface: "a direct-document seed
plus fewer than a few archived years." The real test was simpler: a
one-file seed whose newest filed year is behind the current cycle, however
many years we hold. Describing the shape instead of the mechanism produced
two bugs:

- **A cap on archived years.** The job skipped any school with more than two
  archived years. Many schools held several years from the College
  Transitions mirror behind a seed that was one old file. The cap excluded
  90 of them.
- **"unknown" sorted as the newest year.** The archive files a document it
  cannot date under the year `unknown`. As a string, that sorts above every
  real year, so a school holding one undated document never looked stale.
  That excluded 25 more.

The job flagged 75 schools on 2026-11-24 when the correct number was 190
(39%). No one compared its count with the number of schools behind on the
current year, which the archive showed the whole time.

The `unknown` bug had already been fixed once. A migration on 2026-08-23
(`20260823220000_coverage_ignore_unknown_years.sql`) fixed it in the
coverage view's SQL. The same comparison in the Python job lived on for
three more months. We fixed the instance, not the mechanism: a text year
column that sorts `unknown` above real years.

### 3. The re-probe's results swung, and November's status didn't show it

For the schools it flagged, the monthly re-probe searched the web for a
better seed. Its results varied a lot from month to month:

| Run | Result |
|---|---|
| 2026-09-02 | 110 stuck, 0 re-probed: a shell heredoc bug stopped the step |
| 2026-09-11 (rerun) | 112 re-probed, 6 still stuck; many seeds moved to listing pages (#175) |
| 2026-11-02 | 78 re-probed, 7 replaced, 71 still stuck; status `ok` |

In November, search returned a result for 57 of the 78 schools, but 46 of
those were again a single file, many of them years old (a 2016-17 PDF at
Hillsdale, a 2015-16 PDF at Florida SouthWestern). The status meant "the
step finished." A step that leaves 91% of its schools where they started has
failed at its job, and the number that said so was stored with the status.

### 4. An alarm existed, and it wasn't one anyone acted on

Issue #136, open since 2026-08-21, gets a comment from the monthly job with
the stuck list. Its counts were 70, 78 and 71. Three things made it easy to
ignore:

- **It was the wrong number.** It counted what the capped job flagged, so it
  looked steady while the real problem was growing.
- **A steady number on a standing issue reads as "known and handled."** Each
  comment looked like the last one. Nothing changed state: no new issue, no
  assignee, no deadline.
- **It reported a count, not a gap.** "71 stuck" says nothing about how far
  behind the archive is. "Half the schools with last year's CDS have this
  year's" would have.

### 5. The 2025-26 form prints last year's title

The official 2025-26 PDF form prints "Common Data Set 2024-2025" in its page
header. Our year reader trusted the title, so 22 real 2025-26 documents were
filed as 2024-25 (#455). For 21 of them it was the school's second 2024-25
document, which no check looked for. A check for two live documents of one
school in the same year would have caught all 21.

### 6. Fetch failures had no owner

Some schools' listing pages were known, but the fetch failed: blocked
responses, dead links on the school's page, files behind SharePoint or Box,
and relative links resolved without the page's `<base href>` (#457). Each
failed quietly as a single school's archive result. Six blocked listings now
go to the headless archive (#456). 34 schools are still unarchived because of
fetch problems like these.

### 7. The tests checked the code's choices, not the goal

`test_stuck_pdf_seeds.py` had a test named
`test_many_years_not_stuck_even_if_pdf`. It asserted the cap: a school with
three years and a one-file seed is not stuck. That is the bug, written down
as expected behavior. The goal was never written as a test: every school
behind the current cycle gets looked at again.

### 8. The pipeline page measures whether jobs run, not what they achieve

`/pipeline-observation` describes itself as "when it last ran on schedule,
and what it found." The "Stuck PDFs" station had a 40-day schedule check, so
it stayed green in November while it found 39% of its schools and fixed 7 of
the 78 it found. The heartbeat table keeps only each station's latest run,
so earlier months can't be read back.

Loud failures were handled. The monthly workflow ended in failure on
2026-08-21, 09-02, 09-11 and 10-02, mostly at the step that opens the
seed-update PR, and its results were landed by hand (#172, #175, #222). The
quiet failure, a job that succeeded at the wrong thing, is the one that
lasted.

### 9. The coverage page showed the symptom one school at a time

`/coverage` labels each school "Older CDS available" when its newest year is
behind. The label was right for every affected school. But it was a label on
a row, with no total, no trend and no alert.

### 10. The project's goals never named this outcome

PRD 001 asks the finder to return each school's most recent CDS. Its success
criteria are all about things existing: the API responds, 20 schools have
rows, 5 have extracts. Its non-goals note that the data "changes roughly
annually." No document says "each year, the new CDS should arrive for the
schools that post one", with a number and a date.

Our planning wrote goals as things to build, and our reviews checked that
those things were built. No step asked what would show the site failing at
its main job, so later PRDs, tests and dashboards were built around what the
PRDs named. The project's agent rules (`CLAUDE.md`) say to "search the corpus
for other documents with the same failure shape" and to add a durable finder
hint after a discovery fix. Neither rule has a step that counts what a
corpus-wide fix missed.

## When schools post

The posting season matters for the alarm floor and the hand check. For the
348 of 489 2024-25 files with a usable production date in the file:

| Produced by end of | Share |
|---|---:|
| December 2024 | 3% |
| February 2025 | 18% |
| April 2025 | 46% |
| June 2025 | 68% |
| August 2025 | 81% |
| November 2025 | 88% |

Most files appear between March and August of the year after the fall they
describe. By November of that year, 88% exist. So "this year" in November
2026 is 2025-26, which matches the project's freshness floor
(`cds_freshness_floor()` in SQL, `default_min_fresh_year` in Python).

That floor moves to a new year each September, when about 81% of that year's
files already exist. An alarm floor must be read off the curve by months since
the CDS year's fall, not by calendar month: from September the current year
should be at 81% or more. The early part of the curve applies to the next
year (the floor year plus one), which is how a break in the newest year can be
caught before the September switch.

## What the fixes changed, including side effects

Fixed on 2026-11-24:

- 95 seeds now point at the school's CDS listing page instead of one file
  (#453, #459).
- The monthly re-probe no longer caps archived years, and it ignores undated
  documents when finding a school's newest year (#454). It now flags 190
  schools.
- The year reader uses the form's own reference date when the printed title
  is last year's (#455).
- Six listings that block our fetcher go to the headless archive (#456).
- The resolver honours `<base href>` (#457).

Side effects, listed in #452:

- From some new listing pages the archive picked the wrong file: DePaul's
  change sheet, Richmond's Section A alone, single section files at
  Tennessee State and Reed, and a definitions sheet at DePauw (since
  replaced).
- Auburn University at Montgomery's 2025-26 file is filed as 2026-27 because
  the school's page header says so.
- University of Mary Washington has two documents held by a guard after its
  files changed; the earlier extractions are still served.

## The headline number

One definition, used by the alarm, the pipeline page, PRD 040 and
`CLAUDE.md`:

> **Current-year renewal:** of the schools with a live document whose filed
> year is the previous CDS year, the share that also have one whose filed
> year is the current CDS year. The current CDS year is
> `cds_freshness_floor()`. Undated (`unknown`) documents don't count.

On 2026-11-24 that was 236 of 476 (50%) in the morning and 364 of 479 (76%)
after the fixes. A ratio of the two years' counts (278 against 476) is not
the same number, because it counts schools that have only the current year.

## Actions

Owner means who does the work; "agent" work still needs the owner's review.

| # | Action | Targets | Owner | Issue |
|---|---|---|---|---|
| 1 | **Alarm on current-year renewal.** A scheduled workflow computes [the headline number](#the-headline-number) and compares it with a floor read off [when schools post](#when-schools-post) by months since that CDS year's fall, less a margin (81% or more from September). It also tracks the next CDS year against the early curve (18% by February, 46% by April), so a break in the newest year shows before September. Below the floor, it opens a new issue assigned to the owner and closes it only when the number recovers. It never comments on a standing issue, which is how #136 was ignored. | 4, 8, 9, 10 | agent | #460 |
| 2 | **Measure the miss rate from outside the pipeline.** Every month, a workflow opens an issue listing 20 random schools with links to their sites. Someone checks each by hand and records whether the school had a newer CDS than the archive. Year-round, because files appear from March to November. | 1, 2, 3, 6 | owner, with agent help | #461 |
| 3 | **Date every seed by the last new year it produced.** A seed that has not produced a new year within one cycle is suspect, whatever kind of URL it is. | 1, 6 | agent | #462 |
| 4 | **A sweep's status reflects its result.** The re-probe counts a school as fixed when the new seed reaches a newer year than the archive holds, or is a listing page whose newest year matches ours (the school hasn't posted). A single file older than the current year is not a fix. The station warns when most of its schools are still stuck, and keeps a history of summaries. | 3, 8 | agent | #463 |
| 5 | **Make every sweep account for every school.** A job that filters schools reports how many it checked, flagged and skipped, and why. A test asserts `flagged + fresh + skipped == total` and covers many mirror years, an `unknown` year and a stale listing page. | 2, 7 | agent | #464 |
| 6 | **Add a denominator check to the agent rules.** Add to the "Data quality loop" rules in `CLAUDE.md`: count a fix's reach, fix the mechanism and every copy of it, and check the headline number a month after a discovery fix. | 2, 10 | agent (done) | this PR |
| 7 | **Search the rest.** Search the 156 schools whose newest year is 2022-23 or older, so the headline number starts from a clean baseline. | impact | agent | #465 |
| 8 | **Flag two live documents of one school in one filed year.** Report them on the pipeline page and in the scoreboard; each is a misfiled year or a duplicate. | 5 | agent | #467 |
| 9 | **Give fetch failures a list and an owner.** Group schools whose listing is known but whose files we can't fetch by cause (blocked, viewer, section files, dead link), and work the list monthly. | 6 | agent | #468 |

## Lessons

- **Define the main job as a number with a date, and alarm on it.** "Each
  year, the new CDS arrives for the schools that post one" was the site's
  purpose and was never measured. The same holds downstream: for extraction,
  the share of archived documents whose key fields read; for scoring, how many
  schools each filter drops.
- **An alarm is something that changes state.** A count added to a standing
  issue every month is a log, not an alarm. Open a new issue, assign it, and
  close it only when the number recovers.
- **A green light on a job means it ran, not that it worked.** Any job that
  exists to catch a failure needs a check on its result, not only its
  schedule. Loud failures get fixed; quiet ones need a number that moves.
- **Fix the mechanism, and every copy of it.** The August job copied the
  Oklahoma case ("few archived years") instead of the cause. And the
  `unknown` sort was fixed in SQL while the same comparison lived on in
  Python. When fixing a bug, search for the other places that make the same
  comparison.
- **Treat exclusions in a safety net as wrong until numbers show otherwise.**
  Every skip rule in a job meant to catch failures should come with a count of
  what it skips, checked against the size of the problem.
