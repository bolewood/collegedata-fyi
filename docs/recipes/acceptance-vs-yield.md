# College Pricing Power

**Question:** How much pricing power does a college appear to have, and what
financial outcomes do its students experience afterward?

“Pricing power” is a shorthand for a cluster of related questions. It is not a
number this page computes. The charts do not estimate how enrollment would
change if a college changed its price.

Open [`/recipes/acceptance-vs-yield`](https://www.collegedata.fyi/recipes/acceptance-vs-yield)
for two interactive scatters. Panel A plots IPEDS fall 2024 acceptance rate
against yield for 1,417 schools with entering classes of at least 100 students.
Panel B keeps yield and adds College Scorecard
federal-loan burden for 1,386 of those schools. Dividers are this sample’s
medians, not 50% lines. Each school is drawn at the same size; average net
price is in the tooltip. Hover any dot, or search, to see the underlying
counts. Many schools overlap.

**Who this is for:** IR and enrollment managers comparing peer yield and
federal-loan burden; analysts joining IPEDS ADM counts to College Scorecard.

**Sources:** IPEDS ADM2024 (fall 2024) raw applicant / admitted / enrolled
counts; College Scorecard 2022–23 debt, payments, earnings, net price, and
instructional spending; CDS 2024–25 C1 acceptance and yield as a tooltip
cross-check only (356 of 1,417 Panel A schools). Plotted positions always use
IPEDS.

The XLSX starter
([`acceptance-vs-yield-starter.xlsx`](../../web/public/recipes/acceptance-vs-yield-starter.xlsx))
is the same dataset in workbook form. Regenerate it with
`python3 tools/ipeds/build_pricing_power_starter_xlsx.py` after rebuilding the
checked-in TypeScript file.

## What the recipe computes

Acceptance rate and yield are computed from IPEDS ADM raw counts, not from the
integer-rounded DRVADM derived-rate fields (`admit_rate_total`,
`yield_rate_total`). Those derived rates are never plotted.

```text
acceptance = admissions_total / applicants_total
yield      = enrolled_total / admissions_total
```

Rates are exact `Decimal` ratios from the counts and are rounded only at
serialization (four decimal places in `[0, 1]`).

Debt **burden** is annual estimated federal loan service as a share of median
10-year earnings:

```text
burden = median_debt_monthly_payment × 12 / earnings_10yr_median
```

A $3,000 annual payment against $60,000 of earnings is a 5% burden. The monthly
payment is a Scorecard estimate derived from median federal debt among
completers, not the amount a typical alumnus is observed to send a servicer.
Earnings are for federally aided students working and not enrolled, including
people who did not complete. Debt and earnings are therefore not the same
population.

**Instruction / net-price** is instructional expenditure per FTE divided by
average net price. It is not the share of a college’s budget spent on teaching.
The denominator is College Scorecard average net price for Title IV aid
recipients, not total spending. The ratio lives in tooltips only; it is not a
plotted channel.

Average net price tells us what undergraduates who received Title IV federal
aid paid, on average, after grant and scholarship aid. It is not the bill for a
full-pay family, and full-pay students are not in the average.

## Join

Panel A starts from `school_facts_unified`, which is long-format: one row per
`field_key` per school. The builder requests the three ADM2024 count fields
separately (`applicants_total`, `admissions_total`, `enrolled_total` with
`source_table=eq.ADM2024`), pivots on `ipeds_id`, and computes rates from those
counts.

Guards, required:

1. Drop institutions that are out of directory scope (`in_scope` is not true).
   This build: **195**.
2. Drop missing or non-positive applicant, admitted, or enrolled counts.
   This build: **17**.
3. Drop `admitted > applied`. This build: **0**.
4. Drop `enrolled > admitted`. This build: **0**.
5. Drop entering classes under **100** students. This build: **327**. In
   IPEDS filings from very small direct-matriculation institutions (seminaries,
   yeshivas, small trade schools), the admitted count often equals the enrolled
   count, which reads as 100% yield but reflects record-keeping rather than a
   market signal — and the recipe’s audience applies to larger schools.

Result: **1,417** schools. Median acceptance **76.78%**. Median yield
**19.31%**. Quadrant counts against those medians: 397 / 312 / 311 / 397
(lower acceptance · higher yield / higher acceptance · higher yield / lower
acceptance · lower yield / higher acceptance · lower yield).

Panel B joins Panel A to `scorecard_summary` on `ipeds_id` and keeps rows where
earnings, monthly payment, completer debt, average net price, and instructional
expenditure per FTE are all present and positive. This build dropped **31**
schools for missing or non-positive Scorecard fields. Directory and Scorecard
join misses were **0**.

Result: **1,386** schools. Median yield **19.13%** — not the 19.31% used in
Figure 1. Median burden **5.20%**. Quadrant counts: 322 / 375 / 371 / 318
(higher yield · higher burden / lower yield · higher burden / higher yield ·
lower burden / lower yield · lower burden).
A school can sit on different sides of “higher yield” in the two charts.

CDS 2024–25 C1 is attached last, from `school_browser_rows` with
`canonical_year=eq.2024-25`, `sub_institutional=is.null`, and non-null
`acceptance_rate` and `yield_rate`. This build found **371** complete C1 rows
and attached **356** of them to a Panel A school. Syracuse has no CDS C1 row
in the serving data. Those rates appear only as a labeled tooltip cross-check.

Rebuild:

```bash
python3 tools/ipeds/build_pricing_power_recipe.py
python3 tools/ipeds/build_pricing_power_starter_xlsx.py
```

The first command writes `web/src/lib/pricing-power-recipe-data.ts`. The second
reads that file and writes the public XLSX. Dataset generated 2026-08-31.

After a regen, also refresh the counts, medians, quadrant tallies, and
exclusion figures quoted in this write-up — the web page derives them from
`PRICING_POWER_META` and updates itself, but this document does not.

## How to read the panels

Dividers are this sample’s medians, not 50% lines. A 50% × 50% grid would put
most of Panel A in one corner: 84% of these schools accept at least half of
applicants, and the median school admits about 77%. “Below-median acceptance”
still includes many colleges that admit 60% or 70% of applicants.

**Fig. 1 · Acceptance rate vs. yield.** Horizontal axis: acceptance. Vertical
axis: yield. Dividers: 76.8% acceptance and 19.3% yield among 1,417 schools.

- **I. Lower acceptance · higher yield** — These schools admit a smaller share
  of applicants than the sample median and enroll a larger share of those they
  accept than the sample median. That combination can reflect student
  preference, binding Early Decision, geography, aid, athletics, or a
  self-selected applicant pool. The chart does not tell us which.
- **II. Higher acceptance · higher yield** — These schools admit a larger share
  of applicants while still enrolling a relatively large share of those they
  accept. That can happen at public flagships, regional institutions,
  specialized colleges, or schools whose applicants are especially likely to
  enroll if admitted.
- **III. Lower acceptance · lower yield** — These schools admit a smaller share
  of applicants than this sample’s median (76.8%) but enroll a smaller share of
  admits than the median (19.3%). In this file, “below-median acceptance” still
  includes many colleges that admit 60% or 70% of applicants. Many of these
  schools compete for students who have several attractive alternatives. A
  below-median yield should not be read as evidence that the school is
  undesirable.
- **IV. Higher acceptance · lower yield** — These schools admit a larger share
  of applicants and enroll a smaller share of those admitted. For enrollment
  teams, this combination can make class size harder to predict because more
  offers may be required to fill each seat.

Yield is conversion, not a second selectivity score. A high yield can reflect
strong student demand, binding Early Decision, geography, price, financial aid,
athletics, a specialized mission, or simply an applicant pool that already
knows the school well. A low yield can reflect intense competition for students
rather than weak academic quality.

**Fig. 2 · Yield vs. graduate debt burden.** Horizontal axis: yield. Vertical
axis: debt burden. Dividers: 19.1% yield and 5.20% debt burden among 1,386
schools. Each school is drawn at the same size. Average net price is in the
tooltip. It is the College Scorecard average for Title IV aid recipients, not
the price a full-pay family pays.

Acceptance and yield describe how a college fills a class: how many applicants
it admits, and how many of those admits enroll. They do not tell us what
happens financially to students who enroll. Burden answers a narrower question:
how large are median federal loan payments, as estimated from completer debt,
relative to median earnings of federally aided students about 10 years after
they first enrolled?

This is not a measure of total college cost. It covers federal student debt,
and many families pay for college with savings, current income, grants, parent
borrowing, private loans, or other resources.

- **I. Higher yield · higher debt burden** — Higher yield means a larger share
  of admits enrolled. That is not the same thing as students preferring the
  school over every alternative. The debt measure asks a separate question
  about federal borrowing among federally aided students afterward.
- **II. Lower yield · higher debt burden** — A smaller share of admits
  enrolled, and federal loan payments are also above the sample median relative
  to later earnings. It does not tell us why either condition exists —
  competition, aid design, applicant mix, earnings, or borrowing can each
  produce the same pair of numbers.
- **III. Higher yield · lower debt burden** — Both of these measures sit on the
  better-looking side of this sample’s medians. That says nothing by itself
  about academic quality, access, family wealth, or the experience of students
  who do not borrow.
- **IV. Lower yield · lower debt burden** — A below-median yield in one
  admissions cycle does not mean a college produces poor federal-loan outcomes
  for the federally aided students in the Scorecard file.

## Syracuse: high published price, ordinary federal-loan burden

Syracuse University (`syracuse-university`, IPEDS 196413) is in both panels.
Fall 2024 ADM2024: 44,480 applied, 20,427 admitted, 3,835 enrolled →
acceptance **45.92%**, yield **18.77%**. Scorecard 2022–23: median completer
debt $26,000; monthly payment $275.64 (annual $3,308); median 10-year earnings
$79,164; burden **4.18%** (below the 5.20% Panel B median); Title IV average
net price **$38,793**.

The admissions figures on this page are from the fall 2024 entering class, the
most recent IPEDS ADM release. The Wall Street Journal’s August 2026 account
describes a 1.5% budget shortfall for the academic year that began in August
2026, late merit-aid offers for the fall 2025 class, and a published cost of
attendance of $98,544. The charts do not depict the shortfall year, and the
Scorecard debt and earnings figures describe earlier cohorts still.

A published cost of attendance near $100,000 does not, in this federal-loan
measure, come with unusually heavy payments relative to later earnings. The
fall 2024 admissions file shows a high average net price for Title IV
recipients and a yield near the middle of this sample. It does not show a
federal-debt-burden outlier, and it does not depict the fall 2025 recruiting
scramble or the fall 2026 shortfall described by the Journal.

Syracuse is not the only college in this part of the chart. Fordham University
(9.7% yield, 3.61% burden, $44,338 net price), American University (15.6%,
3.74%, $41,943), and Southern Methodist University (17.8%, 3.17%, $40,892)
also sit below both Panel B medians on yield and burden while posting
above-median Title IV net prices. Northeastern, Boston University, and NYU —
the Journal’s full-pay comparison set — do not: each has a much higher fall
2024 yield.

Federal data for 2023–24, as reported by The Wall Street Journal, show 21% of
Syracuse undergraduates paying full sticker price, compared with 40% at
Northeastern, 49% at Boston University, and 58% at NYU. Those three schools
are not yield peers in this file: each converted a much larger share of its
fall 2024 admits than Syracuse did.

Sticker price is important, but it is not the College Scorecard net-price
figure. That figure averages what Title IV aid recipients paid after grant
aid; it is not what a full-pay family is billed.

Syracuse’s chancellor told the Journal that in April 2026 the university could
have pulled from its wait list and largely decided not to, in order to
maintain academic standards, and that the shortfall was not due to a lack of
demand.

The Journal describes several forces that can lower enrollment without showing
up as a federal-loan burden, and this page does not separate them:
international enrollment, geography, competition from cheaper public flagships,
sports visibility, admissions execution and late merit-aid offers, the April
2026 wait-list choice, housing, and a falling number of 18- to 24-year-olds.

## What we mean by pricing power

“Pricing power” is a shorthand for a cluster of related questions. It is not a
number this page computes.

We are putting several published measures about the same college on one page:
how broadly it admits, how often admits enroll, what Title IV recipients pay
after grant aid, and how large federal loan payments are relative to later
earnings.

High yield is sometimes treated as a sign that a school could raise price
without losing students. This page does not test that. It does not estimate
elasticity, markups, or the price at which a class would fail to fill. A
school can post a high yield because of binding Early Decision, generous aid,
geography, athletics, a specialized mission, or an applicant pool that already
planned to enroll.

Low yield does not prove a school needs to lower its price, and it does not
measure how many students wanted to attend.

## What is being joined

The two charts join different years. Acceptance and yield are IPEDS ADM2024
(first-time students entering fall 2024). Average net price, federal debt,
estimated monthly payments, 10-year earnings, and instructional spending per
FTE come from the College Scorecard 2022–23 file. Scorecard earnings describe
federally aided students from a much earlier entering cohort, measured about
10 years after they first enrolled. Average net price is also from 2022–23,
not from the fall 2024 class. The join is by institution, not by one class of
students moving through college.

Where a school also has a complete Common Data Set C1 row for 2024–25, the
tooltip shows that acceptance and yield as a cross-check. In this build that
is 356 of 1,417 schools. Plotted positions always use IPEDS ADM2024.

## Limitations

1. **Yield is not pure demand.** Early Decision, geography, price, aid,
   athletics, a specialized mission, and a self-selected applicant pool can
   all produce the same conversion rate. A low yield can be competition rather
   than weak academic quality. At most schools, yield has fallen by about half
   over two decades as students apply to about three times as many schools
   (federal data, as reported by the Journal). Schools with an entering class
   under 100 are excluded: in IPEDS filings from very small
   direct-matriculation institutions, the admitted count often equals the
   enrolled count, which reads as 100% yield but reflects record-keeping
   rather than a market signal. A few larger schools with near-100% reported
   yield remain and are kept as reported. Quadrants use medians so that tail
   does not set the middle of the chart.

2. **Average net price is not sticker price, and it is Title IV-only.** The
   College Scorecard figure averages what undergraduates who received Title IV
   federal aid paid after grant aid. Full-pay students are not in that
   average, so the number is not what a typical full-pay family pays and is
   not an enrollment-weighted average of the whole undergraduate body.

3. **Debt burden is federal only, and the payment is modeled.** It does not
   include parent PLUS, private loans, or cash tuition. The monthly payment is
   a Scorecard estimate from median completer debt, not an observed typical
   bill. Median federal completer debt clusters at common federal loan limits.
   In this sample, 159 schools report exactly $27,000. A lower debt burden at
   a high-price college can be high later earnings, not a smaller bill.
   Syracuse at $26,000 sits in that pile.

4. **Three clocks, not one cohort.** This page combines institutional data
   from different systems and different years. The numbers should not be read
   as if they describe one group of students moving through college at the
   same time. Earnings are from federally aided students who enrolled about a
   decade before the Scorecard 2022–23 file. Fall 2024 admits are not those
   earners, and they are not the fall 2026 class in the Journal article.
   Figure 2 uses a smaller sample (1,386 schools) because it requires
   Scorecard debt, earnings, net price, and instructional spending. Its yield
   median is 19.1%, not the 19.3% used in Figure 1.

5. **Instruction / net-price is not a budget share.** Never treat the
   remainder as administration. Instructional expenditure per FTE and Title IV
   net price come from different systems and describe different populations.
   The ratio is a tooltip field, not a plotted dimension.

6. **Correlation is not causation.** The page does not estimate elasticity,
   markups, or a recommended price. Some branch campuses inherit a parent
   College Scorecard record, so debt, earnings, and burden can repeat across
   related institutions. Those repeats are kept as reported. They do not
   include Syracuse. “1,386 schools” is not 1,386 independent outcome draws.

## How to reproduce it

`school_facts_unified` is long-format (one row per field per school) and
PostgREST `max-rows` is 1,000. `limit=5000` and `Range: 0-4999` both return
HTTP 206 with `Content-Range: 0-999/…` and no error body. Page with
`limit=1000&offset=0`, then `offset=1000`, then `offset=2000` until a page is
short. Repeat the ADM count query for each of the three field keys. The
anonymous API key is on [`/api`](https://www.collegedata.fyi/api).

```bash
# ADM2024 applicant counts. Repeat for admissions_total and enrolled_total.
# Do not plot admit_rate_total or yield_rate_total (integer-rounded DRVADM).
curl 'https://api.collegedata.fyi/rest/v1/school_facts_unified?select=school_id,school_name,ipeds_id,in_scope,field_key,value_numeric,source_table,data_year,quality_flag&field_key=eq.applicants_total&source_table=eq.ADM2024&order=ipeds_id.asc&limit=1000&offset=0' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'
curl 'https://api.collegedata.fyi/rest/v1/school_facts_unified?select=school_id,school_name,ipeds_id,in_scope,field_key,value_numeric,source_table,data_year,quality_flag&field_key=eq.applicants_total&source_table=eq.ADM2024&order=ipeds_id.asc&limit=1000&offset=1000' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'
curl 'https://api.collegedata.fyi/rest/v1/school_facts_unified?select=school_id,school_name,ipeds_id,in_scope,field_key,value_numeric,source_table,data_year,quality_flag&field_key=eq.applicants_total&source_table=eq.ADM2024&order=ipeds_id.asc&limit=1000&offset=2000' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'

# Directory scope (paginate the same way)
curl 'https://api.collegedata.fyi/rest/v1/institution_directory?select=ipeds_id,school_id,school_name,in_scope&order=ipeds_id.asc&limit=1000&offset=0' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'

# Scorecard 2022-23 join fields
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,scorecard_data_year,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,instructional_expenditure_fte&order=ipeds_id.asc&limit=1000&offset=0' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,scorecard_data_year,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,instructional_expenditure_fte&order=ipeds_id.asc&limit=1000&offset=1000' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,scorecard_data_year,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,instructional_expenditure_fte&order=ipeds_id.asc&limit=1000&offset=2000' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'

# CDS 2024-25 C1 cross-check only (do not mix into plotted series)
curl 'https://api.collegedata.fyi/rest/v1/school_browser_rows?select=school_id,ipeds_id,canonical_year,sub_institutional,acceptance_rate,yield_rate,updated_at&canonical_year=eq.2024-25&sub_institutional=is.null&acceptance_rate=not.is.null&yield_rate=not.is.null&order=updated_at.desc&limit=1000&offset=0' \
  -H 'apikey: <anon key>' \
  -H 'Authorization: Bearer <anon key>'
```

From those rows: keep in-scope schools with complete positive ADM counts,
`admitted ≤ applied`, `enrolled ≤ admitted`, and an entering class of at least
100 students; compute acceptance and yield from
the counts; inner-join Scorecard on `ipeds_id` where all five outcome fields
are positive; compute `burden = monthly × 12 ÷ earnings` and
`instruction / net-price = instruction_fte ÷ avg_net_price`; attach CDS rates
as tooltip extras only. The generator source
(`tools/ipeds/build_pricing_power_recipe.py`) contains the exact pagination,
exclusion, median, and rounding logic.
