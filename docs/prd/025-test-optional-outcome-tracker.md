# PRD 025: Test-optional observability and outcome tracker

**Status:** Draft
**Created:** 2026-06-03
**Author:** Anthony + Codex
**Related:** [PRD 010](010-queryable-data-browser.md), [PRD 016](016-academic-positioning-card.md), [PRD 019](019-cds-change-intelligence.md), [PRD 021](021-ipeds-coverage-layer.md), [Admission visualization upgrades](023-admission-visualization-upgrades.md)

---

## Executive summary

National education coverage has moved from "some elite schools are reinstating
the SAT" to a broader claim: test-optional and test-blind admissions may have
reduced student preparedness, especially in quantitative fields.

CollegeData.fyi should respond by doing what the product is built to do:
publish source-linked data that lets readers pressure-test the claim without
turning the site into an SAT advocacy project.

PRD 025 creates a public **Test-Optional Observability and Outcome Tracker**: a
reusable recipe and dataset that shows what testing-policy changes made visible
or invisible in public CDS data, then keeps a careful watchlist of coarse
downstream outcome signals.

The defensible launch headline is not "flat retention proves the preparedness
concern is wrong." It is:

> Test-optional and test-blind policies changed what the public can observe.
> Institution-level outcomes are worth watching, but the available public
> measures are coarse, lagged, and confounded.

The first launch is intentionally narrow:

1. Start with the University of California system and a small elite-reinstater
   panel because they are the current public-news focus.
2. Show observable score-reporting signals from CDS where available:
   SAT submit rate, ACT submit rate, and reported SAT/ACT bands.
3. Show coarse outcome-watchlist signals from federal data:
   first-year retention, six-year graduation, transfer-out, and selected
   Scorecard context.
4. Make the conclusion format explicit: "observability changed," "no obvious
   institution-level retention shock," "too lagged to judge," or "signal worth
   investigating," not "SAT good" or "SAT bad."

The launch artifact should be linkable every time another SAT reinstatement
article appears. It should read like a data essay with a reproducible table, not
like a generic dashboard.

## News context

The June 2026 WSJ coverage makes four claims that are product-relevant:

- Most schools remain test-optional, but many students still submit scores.
- SAT benchmark attainment and mean scores have fallen in recent years.
- High-school GPA inflation makes GPA less useful as a college-readiness signal.
- Elite schools and UC faculty are revisiting test requirements because they
  believe preparedness has weakened.

CollegeData.fyi cannot verify every upstream claim from College Board, ACT,
FairTest, or campus faculty anecdotes. The page should name provenance:
FairTest is an anti-test advocacy organization; College Board and ACT are test
vendors. Those sources can define the news context, but they are not neutral
CollegeData.fyi source layers.

CollegeData.fyi can add two public-data checks:

1. **Observability check:** after policy changes, what admissions/testing
   signals are still visible in school-published CDS data?
2. **Outcome watchlist:** are coarse institution-level public outcomes showing
   obvious stress yet?

The product stance should be sober:

- A retention collapse would be noteworthy.
- Flat retention is not proof that the concern is wrong.
- Retention at selective schools often sits near a ceiling, so it is a weak
  instrument for detecting subtle preparedness changes.
- Graduation, transfer-out, and earnings are lagged and may not fully reflect
  post-2020 cohorts yet.
- The pandemic and test-blind/test-optional changes overlap in time, so this
  data cannot isolate policy effects from pandemic disruption.
- Major-specific STEM preparedness may not be visible in institution-level
  public data.

## Problem

The public SAT debate is dominated by inputs:

- test-required, test-optional, test-flexible, test-blind;
- submitted scores;
- average SAT scores;
- GPA inflation;
- faculty anecdotes about classroom readiness.

Those inputs matter, but CollegeData.fyi should not pretend that UC retention
alone tests a national applicant-pool claim. UC enrolls a highly selected slice
of students, and national SAT benchmark trends need not appear in UC outcomes.

The practical questions for students, parents, counselors, and journalists are
more precise:

> What did schools stop showing, keep showing, or newly show after testing
> policy changed?

> Are the coarse outcome signals available in public data showing obvious
> institution-level stress yet?

CollegeData.fyi already has the ingredients to test part of that question, but
they are spread across multiple surfaces:

- CDS extraction exposes current admissions, test-score, and test-submit
  metrics through `school_browser_rows`.
- Historical IPEDS facts expose retention and completion-adjacent time series
  through `ipeds_facts`.
- Scorecard exposes current outcomes, including six-year graduation,
  transfer-out, and retention through `scorecard_summary`.

Without a purpose-built public artifact, each new article forces another manual
analysis. PRD 025 turns the analysis into a durable product surface while
keeping the limits of the instrument visible.

## Goals

1. Publish a public data essay / recipe page that responds to the
   SAT-reinstatement news cycle with source-linked CollegeData.fyi data.
2. Lead with observable CDS testing signals: SAT submit rate, ACT submit rate,
   score-band presence, and score-band values where available.
3. Provide a reproducible UC outcome-watchlist table showing first-year
   retention by year since 2019, explicitly labeled as a coarse and
   ceiling-limited signal.
4. Show graduation and transfer-out only as lagged baseline / watchlist data,
   not as evidence about post-2020 test-blind cohorts.
5. Expose the same data through a lightweight JSON endpoint or static dataset
   so journalists, counselors, and other agents can reuse it.
6. Make uncertainty explicit. The page should distinguish "observability
   changed," "flat observed retention," and "the preparedness claim is false."
7. Use the tracker as a repeatable response surface for future SAT/test-optional
   coverage.

## Non-goals

- No causal claim that test-optional policies caused any observed outcome.
- No endorsement or rejection of SAT/ACT requirements.
- No student-level inference.
- No race, income, disability, or demographic subgroup analysis in V1 unless the
  source and methodology are reviewed separately.
- No major-level STEM preparedness claim in V1; institution-level public data is
  too coarse.
- No ranking of schools by "test policy quality."
- No attempt to infer a school's formal test policy solely from submit rates.
- No private or scraped admissions-office policy database in V1.
- No annual report PDF before the web recipe proves the signal and framing.
- No "statistically unchanged" language in V1 unless a formal model is shipped.
- No claim that UC outcomes represent the national applicant pool.

## Users and jobs

### Journalist or columnist

"I need a public, source-linked dataset that shows what testing-policy changes
made visible or invisible, and what coarse public outcomes show so far."

### Counselor

"I want to explain to families what test-optional means in practice: scores may
be optional, but many students still submit them, and outcomes data is lagged."

### Parent or student

"I want to know what the public data can and cannot tell me about schools that
changed testing policies."

### CollegeData.fyi maintainer

"I want a repeatable link to share when national coverage makes a strong claim
about admissions policy."

## V1 launch surface

### Route

Create a recipe page:

```text
/recipes/test-optional-outcome-tracker
```

This is preferable to a school-page module for V1 because the first job is
editorial response and cross-school comparison, not per-school discovery.

### Page structure

1. **Headline**
   - "Test-Optional Observability and Outcome Tracker"
   - Subhead: "A source-linked check on what testing-policy changes made
     visible, and what coarse outcome data shows so far."

2. **Context panel**
   - Briefly summarize the public question without quoting paywalled article
     text.
   - Link to the public sources when available:
     - College Board SAT reports for score/benchmark trends.
     - ACT research for GPA inflation if cited.
     - CollegeData.fyi API/methodology pages for our data.

3. **Testing observability table**
   - Rows: UC campuses and news-comparison schools where CDS coverage exists.
   - Columns:
     - formal policy label, if manually sourced and linked;
     - latest CDS year;
     - SAT submit rate;
     - ACT submit rate;
     - SAT p25/p50/p75;
     - ACT p25/p50/p75;
     - score-band reporting status.
   - Source: `school_browser_rows` plus manual policy notes where included.
   - Label submit rates as "reported by CDS," not formal policy.
   - For UC campuses, expect many SAT/ACT fields to be null under test-blind
     reporting; that missingness is itself an observability signal.

4. **UC first-year retention watchlist**
   - Rows: UC campuses.
   - Columns: data years 2019 through latest loaded IPEDS data year.
   - Values: `retention_rate_full_time` from `ipeds_facts`.
   - Include simple per-campus delta from 2019 to latest.
   - Include system-level median and range.
   - Caption: "Retention is a coarse, ceiling-limited institutional signal, not
     a direct measure of classroom preparedness."

5. **Completion and transfer-out baseline table**
   - Rows: same UC campuses.
   - Columns:
     - six-year graduation rate by available data year;
     - transfer-out rate by available data year;
     - notes about cohort lag.
   - Prefer IPEDS historical fields where loaded:
     - `bachelor_6yr_grad_rate`
     - `transfer_out_rate_total`
   - Use Scorecard only for current context if historical IPEDS coverage is
     insufficient.
   - Caption: "Completion outcomes are too lagged to evaluate post-2020
     entering cohorts in June 2026. Treat this table as baseline context."

6. **Interpretation box**
   - Use plain-language findings:
     - "Testing-policy changes changed what the public can observe."
     - "UC retention is not showing an obvious institution-level collapse."
     - "Retention is a weak instrument for subtle preparedness shifts at
       high-retention schools."
     - "Completion data is too lagged to fully judge post-2020 cohorts."
   - Avoid causal language.

7. **Reproducibility**
   - Include API links or a downloadable JSON/CSV.
   - Include the exact field keys and source tables.

## Initial school panels

### UC outcome-watchlist panel

The first panel should include the nine undergraduate UC campuses:

- UC Berkeley
- UC Davis
- UC Irvine
- UCLA
- UC Merced
- UC Riverside
- UC San Diego
- UC Santa Barbara
- UC Santa Cruz

Rationale: UC is test-blind, current WSJ coverage references UC faculty
pressure, and the system is large enough to inspect manually. The UC panel is
not a national applicant-pool test; it is a high-profile system watchlist.

### News-comparison observability panel

Use a small editorial comparison set, not a ranked peer model. Every row must
carry a formal policy label with source URL and verification date if the row is
used to discuss policy rather than just CDS reporting.

- MIT
- Dartmouth
- Yale
- Harvard
- Brown
- Caltech
- University of Chicago, only if explicitly labeled as a long-running
  test-optional contrast rather than a reinstater

Rationale: several elite institutions have changed or revisited testing rules,
and their CDS submit rates / score bands are likely to be closely watched.

The comparison panel should be labeled "news-comparison schools," not peers.
If V1 cannot source policy labels, omit formal policy language and publish only
the observable CDS submit-rate / score-band table.

## Data contracts

### Historical IPEDS facts

Source table:

```text
ipeds_facts
```

Query shape:

```text
ipeds_id = eq.<six digit UNITID>
field_key = in.(retention_rate_full_time,bachelor_6yr_grad_rate,transfer_out_rate_total)
data_year = gte.2019
data_year = lte.<latest loaded data year>
```

Use `ipeds_id`, `field_key`, and bounded `data_year` to stay on the intended
serving indexes. Do not filter by raw `unitid` in public examples.

Required fields:

| Field | Meaning | Source notes |
|---|---|---|
| `retention_rate_full_time` | First-year full-time retention rate | IPEDS Fall Enrollment |
| `bachelor_6yr_grad_rate` | Six-year graduation/completion rate | IPEDS Graduation Rates / derived tables |
| `transfer_out_rate_total` | Transfer-out rate | IPEDS Graduation Rates / derived tables |

All values should keep:

- `collection_year`
- `data_year`
- `release_type`
- `source_table`
- `source_variable`
- `quality_flag`
- `definition_alignment`

### Scorecard summary

Source table:

```text
scorecard_summary
```

Use Scorecard for current context, not as the primary historical tracker in V1:

- `graduation_rate_6yr`
- `transfer_out_rate`
- `retention_rate_ft`
- `scorecard_data_year`

Scorecard outcomes are already surfaced on school pages. The tracker should
make the vintage explicit because Scorecard data lags and is not a direct
measure of 2024+ entering cohorts.

### Verified production availability

As of 2026-06-03, production has 21 loaded IPEDS releases and Berkeley
`retention_rate_full_time` rows from 2004 through 2024. Phase 0 still must
re-check the full UC campus panel before launch, because the public artifact
should report missingness explicitly rather than assume every field is complete.

### CDS testing signals

Source table:

```text
school_browser_rows
```

Fields:

- `canonical_year`
- `year_start`
- `sat_submit_rate`
- `act_submit_rate`
- `sat_composite_p25`
- `sat_composite_p50`
- `sat_composite_p75`
- `act_composite_p25`
- `act_composite_p50`
- `act_composite_p75`
- `archive_url`
- `data_quality_flag`

Important limitation:

Submit rates and score bands are not a formal test-policy database. They are
observable CDS reporting signals. A school can be test-optional while still
receiving many submitted scores.

## Derived metrics

### Retention delta

```text
latest_retention_delta = latest_retention_rate_full_time - 2019_retention_rate_full_time
```

Display as percentage points.

### System median retention

For each data year:

```text
median(retention_rate_full_time across included UC campuses)
```

Display with campus count, e.g. `median across 9 campuses`.

### Flatness language

Do not use "statistically unchanged" unless a statistical test is implemented.
For V1, use descriptive language:

- "basically flat"
- "no obvious decline"
- "within a narrow range"
- "not a smoking gun"

If a formal method is added later, use:

- campus fixed-effects linear trend for system-wide direction;
- Mann-Kendall trend as a non-parametric sensitivity check;
- bootstrap confidence interval for median year-over-year change.

The page should explain that with nine campuses and a short time window, the
analysis is descriptive, not a definitive causal model. It should also say why
retention is a weak instrument here:

- UC campuses are high-retention institutions, so there is limited room for a
  visible decline.
- Institution-level retention cannot see course DFW rates, first-term GPA,
  STEM-major persistence, or instructor remediation burden.
- A flat retention line is weak evidence either way.

## Methodology copy

The page should include a compact methodology section:

1. We selected UC because it is test-blind and currently central to the public
   debate.
2. We used public federal IPEDS retention/completion data and source-linked CDS
   test-reporting data.
3. We use 2019 as a descriptive pre-policy reference year, not as a clean causal
   baseline. The pandemic and test-blind/test-optional policy changes overlap
   in time, so post-2020 movements cannot be attributed to testing policy.
4. We did not attempt to measure classroom preparedness directly.
5. We did not infer STEM-specific readiness.
6. We did not infer causality from institutional aggregates.
7. We did not treat UC as representative of the national applicant pool.
8. We flagged lagged outcomes where the relevant entering cohorts have not yet
   reached the measurement window.

## UX requirements

The surface should feel like a compact research artifact, not a marketing page.

- Use dense tables with sticky first column on mobile if needed.
- Prefer line charts only where at least four comparable years exist.
- Put source labels close to each table.
- Use small badges for data source:
  - `IPEDS`
  - `Scorecard`
  - `CDS`
- Include a "Copy API query" control for each table.
- Include a "Download CSV" control for the assembled tracker dataset.
- Include a "Last updated" timestamp.
- Avoid a hero layout; this is a recipe/data page.

## API and export

V1 can be implemented without a new database table by assembling data in the
Next.js route from existing public tables. However, the page should expose a
stable export:

```text
/api/recipes/test-optional-outcome-tracker
```

Response shape:

```json
{
  "generated_at": "2026-06-03T00:00:00.000Z",
  "methodology": {
    "baseline_data_year": 2019,
    "latest_ipeds_data_year": 2024,
    "panel": "uc-system"
  },
  "schools": [
    {
      "school_id": "uc-berkeley",
      "school_name": "University of California-Berkeley",
      "ipeds_id": "110635",
      "outcomes": [
        {
          "data_year": 2019,
          "field_key": "retention_rate_full_time",
          "value": 97,
          "unit": "percent",
          "source_table": "EF2019D",
          "source_variable": "RET_PCF"
        }
      ],
      "testing_signal": {
        "canonical_year": "2025-26",
        "sat_submit_rate": null,
        "act_submit_rate": null,
        "archive_url": "https://www.collegedata.fyi/schools/uc-berkeley/2025-26"
      }
    }
  ]
}
```

The API should be read-only, unauthenticated, and derived entirely from already
public data.

## Editorial launch plan

### First post

Use the tracker to publish a short CollegeData.fyi post:

> WSJ is covering a real SAT policy debate. The harder question is what became
> more or less observable when schools changed testing policy. We checked the
> public data CollegeData.fyi already tracks: CDS testing signals, UC first-year
> retention since 2019, and completion/transfer-out baselines. The early read:
> testing-policy changes clearly changed score visibility; UC retention does not
> show an obvious institution-level collapse, but retention is a coarse,
> ceiling-limited measure and graduation outcomes remain too lagged for
> post-2020 cohorts.

### LinkedIn frame

The LinkedIn post should use:

- one screenshot of the testing observability table;
- one screenshot or crop of the UC retention watchlist;
- one sentence on why observability changed when testing policy changed;
- one sentence on why retention is only a coarse first watchlist signal;
- a link to the recipe.

Do not lead with "WSJ is wrong." Lead with "the public data can clarify what is
visible now and what remains too early to call."

### Future article response

Every future SAT/test-optional article can be answered with one of four updates:

1. Add a school/system panel.
2. Refresh the outcome data when new IPEDS/Scorecard vintages land.
3. Add or update a policy-status source note where formal policy matters.
4. Add a short interpretation note if the data changes.

## Implementation plan

### Phase 0: Data validation

- Confirm the UC panel maps to correct `school_id` and `ipeds_id` values.
- Query `ipeds_facts` for `retention_rate_full_time`,
  `bachelor_6yr_grad_rate`, and `transfer_out_rate_total` from 2019 through the
  latest loaded data year.
- Query `school_browser_rows` for latest CDS test-submit and score-band fields.
- Query `scorecard_summary` for current outcomes/vintage.
- Export a scratch CSV for manual inspection.

Exit criteria:

- Every UC campus has at least one retention row for 2019 and latest loaded year,
  or the missingness is explicitly documented.
- No row uses a parent-campus federal value for a sub-institutional CDS variant.
- Production availability is re-checked before launch even if local validation
  passes.

### Phase 1: Public recipe page

- Add `/recipes/test-optional-outcome-tracker`.
- Render testing observability table.
- Render UC retention watchlist table.
- Render completion/transfer baseline table with lag caveats.
- Add methodology and source labels.
- Add CSV download from the assembled in-memory dataset.

Exit criteria:

- Page is linkable and comprehensible without reading the WSJ article.
- Data source labels are visible above every table.
- Mobile table layout is usable.

### Phase 2: Public API export

- Add `/api/recipes/test-optional-outcome-tracker`.
- Return the same dataset used by the page.
- Include generated timestamp, field keys, source tables/variables, and notes.

Exit criteria:

- API response can reproduce every visible table.
- API route has smoke coverage.

### Phase 3: Comparison panels

- Add the news-comparison observability panel.
- Add a small "policy status" note only where manually sourced, linked, and
  verification-dated.
- Keep CDS submit rates separate from formal policy.
- If formal policy labels are not ready, publish CDS observability values only.

Exit criteria:

- The comparison panel does not imply causal peer analysis.
- Every manually sourced policy note has a URL and date.

### Phase 4: Tracker refresh workflow

- Add a lightweight script or documented command that regenerates the tracker
  export after IPEDS/Scorecard/CDS refreshes.
- Add a freshness note to the page.

Exit criteria:

- Maintainer can refresh and verify the artifact in under 15 minutes.

## Data quality and caveats

### Main caveats

- Retention is institution-level, not course-level or major-level preparedness.
- UC campuses have high baseline retention rates, so retention has limited room
  to reveal subtle preparedness changes.
- UC is a highly selected public system and should not be treated as a proxy for
  the national applicant pool.
- COVID disruption and test-policy changes overlap, so post-2020 movements
  cannot be attributed to testing policy alone.
- Six-year graduation lags entering-cohort changes by years.
- As of June 2026, six-year graduation mostly reflects cohorts admitted before
  or during the initial policy transition, not mature post-2020 cohorts.
- Transfer-out can be positive or negative depending on context.
- CDS submit rates reflect submitted-score reporting, not formal policy alone.
- UC test-blind campuses may not report SAT/ACT score bands in the same way as
  test-optional institutions.
- Formal policy labels require separate sourced URLs and verification dates.
- Public federal data may revise between provisional and final releases.

### Required caveat copy

Use this near the conclusion:

> This is not a causal test of the SAT. The primary signal is observability:
> when schools stop requiring or collecting scores, public score reporting gets
> thinner. UC first-year retention does not show an obvious institution-level
> collapse, but retention is coarse, ceiling-limited, and confounded by the
> pandemic era. Completion and transfer-out remain useful watchlist measures,
> but they are too lagged to fully evaluate post-2020 cohorts.

## Acceptance criteria

- A public recipe page exists at `/recipes/test-optional-outcome-tracker`.
- The page leads with a testing observability table using CDS submit-rate and
  score-band availability where available.
- The UC retention watchlist covers every available data year from 2019 through
  the latest loaded IPEDS year.
- The page includes at least one completion or transfer-out baseline signal
  beyond retention.
- Formal policy labels appear only when a source URL and verification date are
  attached.
- Every visible value has a source family and, where possible, source
  table/variable metadata.
- The page includes methodology and caveat copy covering retention ceiling
  effects, pandemic overlap, outcome lag, and UC generalizability limits.
- The page does not use "statistically unchanged" or equivalent language unless
  a formal model is implemented.
- The page can export CSV or JSON.
- The page passes mobile and desktop smoke tests.
- The route can be linked in a LinkedIn post without additional explanation.

## Open questions

1. Should the first launch include only UC, or UC plus the news-comparison
   observability panel?
2. Should manually sourced formal test-policy labels be included in V1, or
   should V1 only use observable CDS submit-rate signals?
3. Should the tracker live under `/recipes/` permanently, or graduate into a
   broader `/research/` or `/trackers/` section after the first launch?
4. Should we add a static saved dataset per refresh, or recompute live from
   public tables at request time?
5. What evidence would justify moving from "observability changed" to "public
   outcomes show stress"?

## Risks

### Risk: The page is read as anti-SAT or pro-SAT advocacy

Mitigation: keep the conclusion as a pressure test, not a policy claim. Use
neutral labels and caveats.

### Risk: Outcome data is too lagged

Mitigation: make lag the point. The page should say exactly which outcomes are
early watchlist indicators and which are still too lagged for post-2020 cohorts.

### Risk: The page overstates a weak null signal

Mitigation: lead with observability, label retention as a coarse watchlist, and
avoid claiming that flat retention disproves classroom-level preparedness
problems.

### Risk: Users confuse submit rates with policy

Mitigation: label CDS fields as "reported submit rate" and keep formal policy
notes separate.

### Risk: Time-series queries become slow

Mitigation: use the documented `ipeds_id` + `field_key` + bounded `data_year`
query shape and avoid unbounded PostgREST reads.

### Risk: UC-specific conclusions are overgeneralized

Mitigation: call the first panel "UC outcome watchlist" and avoid generalizing
to all test-optional schools or the national applicant pool until broader panels
ship.

## Product thesis

The best response to repeated SAT coverage is not another opinion. It is a
repeatable artifact:

> The debate is real. The claims are testable. Here is what the public outcomes
> and observability data can show so far, with sources attached.

That is the CollegeData.fyi wedge.
