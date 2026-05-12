# Recipe: Wait-list odds

**Who this is for:** students deciding whether to stay on a wait list, parents trying to set expectations after May 1, counselors explaining why a "maybe" can still be a long-shot, and reporters who want a corpus baseline instead of one-school anecdotes.

**Inspiration:** Roshan Fernandez's May 10, 2026 Wall Street Journal story, ["The Only Thing Harder Than Getting Into College Is Getting Off the Wait List"](https://www.wsj.com/us-news/education/college-waitlists-national-decision-day-4cb7b5d8), described wait lists that have grown into thousands of students while some schools admit few or none from the pool. This recipe uses that question as the prompt, then recomputes the answer from collegedata.fyi's Common Data Set corpus.

**CDS sections used:** C2 wait-list counts (`C.201`-`C.204`), C1 application/admission/enrollment totals, plus College Scorecard context for size/control/Carnegie buckets.

---

## The demo

Open [`/recipes/waitlist-odds`](https://www.collegedata.fyi/recipes/waitlist-odds) for the interactive chart.

The recipe reads the current `school_browser_rows` projection and keeps every school-year row that exposes wait-list data. A row is counted in the rate analysis only when it has all three C2 counts and the math is internally valid:

- applicants offered a wait-list spot
- applicants accepting a wait-list spot
- wait-listed applicants admitted

The key rate is:

```text
wait-list success rate = wait-listed students admitted / students accepting a wait-list spot
```

That is the applicant-facing number. "Admitted divided by offered a spot" is also useful for understanding how much a school over-offers the list, but students usually make the decision after they have already accepted a spot.

High-volume rows that report near-total wait-list admission are treated as data-quality caveats rather than odds estimates. Rows with at least 100 students accepting a wait-list spot and a reported success rate of at least 95% are preserved in the recipe but excluded from medians, bucket summaries, and the main chart. Some of these values appear verbatim in school PDFs; at least one inspected PDF leaves the accepted-count row blank and was over-filled by Tier 4 extraction. Exact duplicate school-year rows are collapsed before analysis, and the extremes table shows at most one row per school.

## What it shows

The current generated dataset contains 191 complete school-year rows across 148 schools, plus 61 partial rows where the CDS projection reports only some wait-list values. After collapsing duplicate school-year rows, six high-volume near-total rows are flagged as reported anomalies, leaving 180 school-year rows across 144 schools in the rate analysis. Across those analysis rows:

- median success rate among accepted wait-list spots: 13.16%
- weighted success rate: 21.51%
- median "admitted / offered a spot" rate: 5.51%
- rows under 2% success: 23

The median is not the lesson by itself. The split matters:

- highly selective schools cluster near low single digits
- broad-admit schools produce many of the high-success rows
- public flagships can swing dramatically year to year because small enrollment-model misses create huge wait-list movement
- very large wait lists are often option value for the institution, not a promise to the applicant

The practical answer is: hope is allowed, but planning on a wait-list admit is usually bad strategy. Treat it as an upside option while getting excited about the school that actually admitted you.

The Berkeley history panel, inspired by a chart idea from [@neetu_arnold](https://x.com/neetu_arnold), is a hand-audited example from the nine Berkeley CDS files currently in the archive. The browser projection only exposes the two newest Berkeley wait-list rows, so the older values were read directly from archived source files:

| CDS year | Offered | Accepted | Admitted | Success |
| --- | ---: | ---: | ---: | ---: |
| 2015-16 | 3,760 | 2,445 | 1,340 | 54.8% |
| 2018-19 | 7,824 | 4,127 | 1,536 | 37.2% |
| 2019-20 | 7,531 | 3,975 | 1,098 | 27.6% |
| 2020-21 | 8,753 | 5,043 | 1,651 | 32.7% |
| 2021-22 | 11,725 | 6,871 | 359 | 5.2% |
| 2022-23 | 8,456 | 4,655 | 44 | 0.9% |
| 2023-24 | 7,001 | 4,820 | 1,191 | 24.7% |
| 2024-25 | 10,894 | 7,853 | 26 | 0.3% |
| 2025-26 | 9,102 | 6,479 | 1 | 0.02% |

## How to reproduce

The page is generated from public-facing browser rows:

```bash
curl 'https://api.collegedata.fyi/rest/v1/school_browser_rows?select=school_id,school_name,canonical_year,acceptance_rate,wait_list_policy,wait_list_offered,wait_list_accepted,wait_list_admitted&wait_list_offered=not.is.null'
```

For the page's bucket analysis, join by `ipeds_id` to:

- `institution_directory` for control and undergraduate enrollment
- `scorecard_summary` for Carnegie basic classification and Scorecard enrollment fallback

Then filter to complete rows where:

```text
wait_list_offered >= wait_list_accepted >= wait_list_admitted >= 0
```

## Caveats

1. **This is CDS-reported, not counselor-rumor-reported.** When schools publish conflicting press figures or later updates, this recipe follows the Common Data Set projection.
2. **Partial C2 rows are not rate rows.** Some PDFs expose offered and accepted counts but not admitted counts in the current projection. Those rows remain visible as caveats but do not enter medians.
3. **Near-total high-volume admits are suspicious.** A school may publish them that way, but rows like IU Bloomington and UC Irvine can dominate the right edge of the chart while saying more about reporting quality than applicant odds.
4. **One-year wait-list rates are volatile.** A school can admit hundreds one year and almost none the next. The chart is best read by bucket and by multi-year pattern, not as a guarantee for a single future class.
5. **The accepted-wait-list denominator is applicant behavior.** Schools control how many spots they offer; students control whether they accept one. Both denominators are shown because they answer different questions.

## What else to try

- Plot a single school's wait-list success rate by year once more 2025-26 CDS files land.
- Compare wait-list success to Early Decision share to see which schools fill the class before regular decision has room to move.
- Flag schools whose wait-list accepted pool is larger than their entire admitted class.
- Build a "soft no" detector: very large accepted wait-list pool plus under-2% success in consecutive years.
