# Postmortem: why the archive silently missed 2025-26 files for over 100 schools

**Date found:** 2026-11-24
**Status:** Fixed for the schools searched. Prevention work is open (see [Actions](#actions)).
**Tracking issue:** #452
**Fix PRs:** #453, #454, #455, #456, #457, #459
**Reviewed by:** Gemini 4 Neon (high), 2026-11-24

## Summary

The site exists to collect each school's Common Data Set (CDS) every year.
For months it stopped doing that for a large share of schools, and nothing
told us.

On the morning of 2026-11-24, 278 schools had a 2025-26 document in the
archive, against 479 with a 2024-25 one. By late November, 2025-26 should be
close to complete. We searched by hand the 273 schools whose newest year was
2023-24 or 2024-25. 151 of them had posted 2025-26 on their own site:

- 117 now have it in the archive. A few had it already, filed under the
  wrong year.
- 34 have a file we found but could not archive yet: it sits behind
  SharePoint or a viewer, is posted as separate section files, or the
  school's site blocks our fetcher.

By the end of the day, 416 schools had a 2025-26 document, 138 more than
that morning. The routes overlap, so they don't sum: 109 files located by
search and archived, 22 documents re-filed from 2024-25 to 2025-26, and the
rest found by the archive once seeds pointed at listing pages.

Every job ran on schedule and every test passed. On the pipeline page the
station built to catch this reported `ok` while its own summary said 71 of
its 78 schools were still stuck.

## Terms used here

- **Seed:** the URL the archive starts from for a school, kept in
  `tools/finder/schools.yaml`. A good seed is the school's CDS listing page,
  which shows every year. A bad seed is the URL of one PDF.
- **Weekly refresh:** the archive job that revisits every seed and archives
  anything new it finds there.
- **Monthly re-probe:** the job that looks for schools with bad seeds and
  searches the web (Brave Search) for a better one.
- **College Transitions mirror:** a third-party collection of CDS files we
  imported. It ends at 2024-25.

## How we found it

Not through monitoring. The same day, the extraction scoreboard used to
draft the public data quality page (PRD 040) counted live documents by year:
280 for 2025-26 against 503 for 2024-25. #452 opens with those two numbers
and investigates the gap. No alert, test or dashboard raised it.

## Impact

- **Missing current data.** For about 150 schools, the school's page showed
  an older year as the latest, with no sign that a newer one existed. 34 of
  them still do.
- **Wrong-year data.** 22 documents were 2025-26 forms filed as 2024-25.
  Their admissions figures were compared with federal figures for the wrong
  fall.
- **Missing older years.** The new listing pages turned up about 500 older
  documents we had never archived.
- **Still unknown.** The 156 schools whose newest year is 2022-23 or older
  were not searched, so the true miss count is higher than 151.

Part of the gap is seasonal: schools post 2025-26 between fall and winter,
and 79 of the 273 searched have not posted it. The 151 are not seasonal.
Their files were already on their own sites.

## What went wrong

### 1. A seed that stopped working looked the same as one that worked

When a school's seed was one PDF, weekly refresh fetched that file, found it
unchanged, and recorded success. It could not see that the school had posted
a newer file somewhere else.

### 2. We found this exact problem in August and fixed its shape, not its mechanism

On 2026-08-21 we hit the same failure at the University of Oklahoma (#133)
and Ohio University (#135): one-year PDF seeds that weekly refresh kept
re-verifying. We fixed those two schools. Then an agent wrote a monthly job,
`tools/finder/stuck_pdf_seeds.py` (#134), to find every other school in the
same state.

The job described the Oklahoma case by its surface: "a direct-document seed
plus fewer than a few archived years." The mechanism was simpler. A seed
that is one file can never find a new year, however many years we already
hold. Describing the shape instead of the mechanism produced two bugs:

- **A cap on archived years.** The job skipped any school with more than two
  archived years. Many schools held several years from the College
  Transitions mirror behind a seed that was one old file. The cap excluded
  90 of them.
- **"unknown" sorted as the newest year.** The archive files a document it
  cannot date under the year `unknown`. As a string, that sorts above every
  real year, so a school holding one undated document never looked stale.
  That excluded 25 more.

The job flagged 75 to 110 schools a month. The correct number was 190. No
one compared the flagged count with the number of schools behind on the
current year, which the archive showed the whole time. Neither the owner nor
the agents checked a month later whether 2025-26 arrivals had risen.

### 3. The re-probe left most schools stuck and still reported success

For the schools it did flag, the monthly re-probe searched the web for a
better seed. On 2026-11-02 it re-probed all 78 and replaced 7 seeds. Its
summary, stored with the heartbeat, read `stuck 78, reprobed 78,
still_stuck 71`, and its status was `ok`. Search returned a result for 57 of
the 78, but 46 of those were again a single file, many of them years old (a
2016-17 PDF at Hillsdale, a 2015-16 PDF at Florida SouthWestern).

The status meant "the step finished." A step that leaves 91% of its schools
where they started had failed at its job, and the number that said so was
already on the page.

### 4. A second cause hid inside the gap: the 2025-26 form prints last year's title

The official 2025-26 PDF form prints "Common Data Set 2024-2025" in its page
header. Our year reader trusted the title, so 22 real 2025-26 documents were
filed as each school's second 2024-25 document (#455). The schools looked
behind even though we held their file.

### 5. The tests checked the code's choices, not the goal

`test_stuck_pdf_seeds.py` had a test named
`test_many_years_not_stuck_even_if_pdf`. It asserted the cap: a school with
three years and a one-file seed is not stuck. That is the bug, written down
as expected behavior. The goal was never written as a test: every school
behind the current cycle gets looked at again.

### 6. The pipeline page measures whether jobs run, not what they achieve

`/pipeline-observation` describes itself as "when it last ran on schedule,
and what it found." The "Stuck PDFs" station had a 40-day schedule check. It
ran every month, so it stayed green while finding a third of its schools and
fixing 7 of the 78 it found. (The heartbeat table keeps only each station's
latest run, so earlier months can't be checked.)
Nothing on the page answers the question that matters most: do we have this
year's CDS for the schools that post one?

Loud failures were handled. The monthly job's PR step failed outright in
August, September and October, and each time someone landed the results by
hand (#172, #175, #222, #240). The quiet failure, a job that succeeded at the
wrong thing, ran for three months.

### 7. The coverage page showed the symptom one school at a time

`/coverage` labels each school "Older CDS available" when its newest year is
behind. The label was right for every affected school. But it was a label on
a row, with no total, no trend and no alert. A page nobody is prompted to
open does not warn anyone.

### 8. The project's goals never named this outcome

PRD 001 asks the finder to return each school's most recent CDS. Its success
criteria are all about things existing: the API responds, 20 schools have
rows, 5 have extracts. Its non-goals note that the data "changes roughly
annually." No document says "each year, the new CDS should arrive for the
schools that post one", with a number and a date. Later PRDs, tests and
dashboards were built around what the PRDs named, and this was not named.

The owner and the agents share that gap. The owner set goals as things to
build. The agents built them and never asked what would show the site failing
at its main job. The project's agent rules (`CLAUDE.md`) already say to
"search the corpus for other documents with the same failure shape" and to
add a durable finder hint after a discovery fix. Neither rule has a step that
counts what a corpus-wide fix missed.

## Why it stayed silent

Every check asked either "did the step run?" or "is this one school's status
right?" None asked "is the archive keeping up with the schools?" The August
job made that worse: a job named for this exact problem, with a green light,
looked like coverage, so no one went looking.

## What we fixed on 2026-11-24

- 95 seeds now point at the school's CDS listing page instead of one file
  (#453, #459).
- The monthly re-probe no longer caps archived years, and it ignores undated
  documents when finding a school's newest year (#454). It now flags 190
  schools.
- The year reader uses the form's own reference date when the printed title
  is last year's (#455).
- Six listings that block our fetcher go to the headless archive (#456).
- The resolver honours `<base href>` when it reads relative links, which had
  turned three schools' links into 404s (#457).

## Actions

Owner means who does the work; "agent" work still needs the owner's review.

| # | Action | Targets | Owner | Issue |
|---|---|---|---|---|
| 1 | **Alarm on one freshness number.** Of the schools with a document for the previous CDS year, the share that also have one for the current year. Last year's curve can't be rebuilt (the archive began in April 2026), so the first year uses a fixed floor by month, replaced by the snapshot curve after a year. When the share falls below it, a scheduled workflow opens a GitHub issue. The pipeline page and the PRD 040 snapshot also show it, but the issue is the alarm. | 6, 7, 8 | agent | #460 |
| 2 | **Measure the miss rate from outside the pipeline.** From October to February, a monthly workflow opens an issue listing 20 random schools with links to their sites. Someone checks each by hand and records whether the school had a newer CDS than the archive. The pipeline cannot report what it never looks for. | 1, 2, 3 | owner, with agent help | #461 |
| 3 | **Date every seed by the last new year it produced.** A seed that has not produced a new year within one cycle is suspect, whatever kind of URL it is. This catches bad listing pages, blocked fetches and broken links, not only one-file seeds. | 1, 3 | agent | #462 |
| 4 | **A sweep's status reflects its result.** The re-probe counts a school as fixed only when the new seed reaches a newer year than the archive holds; a single file older than the current year is not a fix. The station shows a warning when most of its schools are still stuck, not `ok`. | 3, 6 | agent | #463 |
| 5 | **Make every sweep account for every school.** A job that filters schools reports how many it checked, flagged and skipped, and why. A test asserts `flagged + fresh + skipped == total`, and covers the edge cases: many mirror years, an `unknown` year, a stale listing page. | 2, 5 | agent | #464 |
| 6 | **Add a denominator check to the agent rules.** Add to the "Data quality loop" rules in `CLAUDE.md`: before calling a corpus-wide fix done, compare what it caught and what it excluded with the total that has the problem. Also: fix the mechanism, not the first case's shape, and check the main freshness number a month after a discovery fix. | 2, 8 | agent (done) | this PR |
| 7 | **Search the rest.** Search the 156 schools whose newest year is 2022-23 or older, so the freshness number starts from a clean baseline. | impact | agent | #465 |

## Lessons

- **Define the main job as a number with a date, and alarm on it.** "Each
  fall, the new CDS arrives for the schools that post one" was the site's
  purpose and was never measured. The same holds downstream: for extraction,
  the share of archived documents whose key fields read; for scoring, how many
  schools each filter drops.
- **A green light on a job means it ran, not that it worked.** Any job that
  exists to catch a failure needs a check on its result, not only its
  schedule. Loud failures get fixed; quiet ones need a number that moves.
- **Fix the mechanism, not the shape of the first case.** The August job
  copied the Oklahoma case ("few archived years") instead of the cause ("one
  file cannot find a new year"). Ask what makes the failure happen, then test
  for that.
- **Treat exclusions in a safety net as wrong until numbers show otherwise.**
  Every skip rule in a job meant to catch failures should come with a count of
  what it skips, checked against the size of the problem.
