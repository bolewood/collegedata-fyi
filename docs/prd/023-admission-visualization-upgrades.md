# PRD 023: Admission visualization upgrades

**Status:** Draft
**Created:** 2026-05-11
**Author:** Anthony + Codex
**Related:** [PRD 016B](016B-admission-strategy-card.md), [PRD 020](020-accessible-cds-table-view.md), [PRD 021](021-ipeds-coverage-layer.md), [PRD 022](022-mcp-cli-readiness.md), [Admission strategy methodology](../../web/src/app/methodology/admission-strategy/page.tsx)

---

## Executive summary

The current Admission Strategy card explains a school one year at a time:
overall applicants, admits, enrolled students, Early Decision counts, residual
non-ED estimates, yield, and wait-list activity.

That is already more honest than a single headline admit rate, but the next
version should make the admissions funnel easier to see.

PRD 023 upgrades the school-page admission visuals with four layers:

1. **Adjusted admission-flow view:** show how applicants become admits and how
   the class is likely assembled, while keeping real counts in the labels. This
   is Sankey-inspired, but the UI should not call it a Sankey unless widths are
   globally proportional.
2. **Wait-list view:** show wait-list offers, students accepting a spot, and
   students admitted from the wait list as a small attrition visual.
3. **Trend view:** when multi-year extracted data is available, show whether ED
   share, residual admit rate, yield, and wait-list outcomes are changing.
4. **Peer context:** compare each school against simple peer buckets, not a
   hand-curated "peer list," so users can tell whether a metric is typical or
   unusual for schools in the same rough admissions market.

The first user-facing goal is clarity. A student or family should be able to
look at Duke, Vanderbilt, or Goshen and understand the shape of admissions in
under a minute: how much of the class is assembled early, how selective the
remaining pool looks, whether the wait list is meaningful, and whether those
signals are unusual relative to similar schools.

## Product stance

Move fast, keep the math visible, and let sparse data degrade cleanly.

The current-year chart should ship first because the data already exists for
schools where PRD 016B is populated. Trend and peer modules should appear only
when the underlying data is strong enough to avoid false precision. The product
should never promise a five-year trend when we only have one extracted year.

This is not a prediction product. It is a public-data browser for understanding
how a school builds a class.

## Problem

### 1. The current numbers are correct but cognitively expensive

The Admission Strategy card now includes real counts and derived rates, but the
reader still has to mentally convert those numbers into a model:

- How many applicants were in ED versus all other rounds?
- How much of the class was effectively committed through ED?
- How different is the ED admit rate from the rest of the pool?
- How much room was left after early admits?
- Is the wait list a real path or mostly a hedge?

A visual should do that work.

### 2. Literal proportional charts become unreadable

Admissions data often spans very different orders of magnitude:

- tens of thousands of applicants;
- thousands of admits;
- hundreds or low thousands of enrolled students;
- sometimes single-digit wait-list admits.

A purely proportional Sankey can collapse the important paths into hairlines.
The chart needs to be visually adjusted while being explicit that labels carry
the exact counts.

### 3. One-year data can overstate certainty

ED share, yield, and wait-list admits can move year to year. A single year is
still useful, but users should know whether a number is a pattern or a spike.

The product should use trends when we have them and remain a current-year view
when we do not.

### 4. "High" needs context

"ED fills 60% of the class" means something different at a highly selective
private university than at a broad-access regional public institution. We do not
need elaborate peer modeling in V1, but we do need simple context:

- similar selectivity;
- similar control type;
- similar enrollment size;
- same data year when possible.

## Goals

1. Replace the current admissions-round visual with an adjusted flow view that
   keeps ED and all-other-round paths easy to compare without implying false
   proportionality.
2. Add a wait-list visual showing offers, accepted wait-list spots, and admits
   from the wait list.
3. Add trend visuals when at least three comparable years are available.
4. Add peer-bucket context for the most important derived metrics.
5. Preserve accessible tables for every charted value.
6. Keep caveats concrete and close to the affected metric.
7. Avoid hiding missing data behind decorative empty states.

## Non-goals

- No personalized admissions advice.
- No probability prediction for an individual applicant.
- No exact Regular Decision admit rate. We still publish the non-early residual
  because CDS does not isolate RD.
- No Early Action admit rate unless a future non-CDS source reliably supplies
  the underlying counts.
- No named peer-picker UI in V1.
- No claim that a trend exists unless multiple comparable years are extracted.
- No heavy dashboard surface on the school page.

## User stories

1. A student can open a school page and immediately see how much of the class is
   shaped by Early Decision versus all other rounds.
2. A parent can understand why the headline admit rate is not the same thing as
   the likely non-ED pool.
3. A counselor can see whether the wait list admitted many students, a few
   students, or none at all.
4. A journalist can cite the exact underlying counts from an accessible table.
5. A developer can retrieve the same derived data through the public API once
   the MCP/CLI layer grows to include admission strategy facts.

## Product principles

1. **Real counts first.** Every visual label uses the exact available count or a
   clearly named derived estimate.
2. **Adjusted visuals are allowed when labeled.** If the chart compresses scale
   to remain readable, say so in chart copy and keep the table exact. Do not
   use "Sankey" as the user-facing label unless one global scale is used.
3. **Denominators must be visible.** "10%" is not enough; show "600 of 6,000"
   where space allows.
4. **Single-school first, context second.** The primary job is explaining this
   school. Trends and peers should support that story, not become a separate
   analytics product.
5. **Sparse data should be honest.** Missing trend, peer, or wait-list data
   should hide that module or show a small factual missing-data note.
6. **Accessible by default.** Every chart has a semantic table equivalent and
   does not rely on color alone.

## V1 surface

### 1. Adjusted admission-flow view

Replace the current "Applicant paths" treatment with a two-lane flow:

- **Early Decision**
  - ED applicants
  - ED admits
  - likely ED class seats, using the assumption below
- **All other rounds**
  - remaining applicants
  - remaining admits
  - seats left after ED admits, using the assumption below

The committed V1 shape is a **stage-normalized flow / Marimekko small-multiple**:

- applicant widths compare ED applicants to non-ED applicants;
- admit widths compare ED admits to non-ED admits;
- class-seat widths compare likely ED seats to remaining seats.

Each stage is internally proportional, but widths are not globally proportional
from applicant stage to admit stage to class-seat stage. This avoids the
hairline problem without pretending to be a true Sankey.

Labels carry the real counts. A small note should say: "Each column is scaled
within that stage. Labels show exact counts."

Future option: a true Sankey can be explored later only if it uses one global
scale, or a global square-root/log transform with an explicit caption. That is
not the V1 implementation.

#### ED class-seat assumption

CDS does not report how many ED admits actually enrolled. Because ED is a
binding admission plan, V1 uses this assumption:

```text
likely_ed_class_seats = min(ed_admitted, enrolled_first_year)
seats_left_after_ed = enrolled_first_year - likely_ed_class_seats
```

The chart must name this assumption near the class-seat stage:
"Class-seat estimate assumes ED admits enroll."

This is good enough to explain class assembly, but it is still an estimate. Peer
context should use "likely ED class share," not "ED class share," when this
assumption is involved.

#### Required metrics

| Metric | Formula | Notes |
|---|---:|---|
| ED applicants | `ed_applicants` | CDS C.21 |
| ED admits | `ed_admitted` | CDS C.21 |
| ED admit rate | `ed_admitted / ed_applicants` | Hidden if denominator missing or zero |
| All-other applicants | `c1_applicants - ed_applicants` | Labeled as residual, not RD |
| All-other admits | `c1_admitted - ed_admitted` | Labeled as residual, not RD |
| All-other residual admit rate | all-other admits / all-other applicants | Hidden if invalid |
| ED share of admits | `ed_admitted / c1_admitted` | Exact from admits |
| Likely ED class seats | `min(ed_admitted, enrolled_first_year)` | Assumes ED admits enroll |
| Likely ED share of class | likely ED class seats / `enrolled_first_year` | Labeled as an estimate |
| Seats left after ED | `enrolled_first_year - likely_ed_class_seats` | Labeled as an estimate |

#### Design requirements

- Put "Early Decision" and "All other rounds" outside the flow boxes so the
  numeric columns align vertically.
- Use the same column order in both lanes: applicants, admits, enrolled.
- Keep exact counts in bold only where they are the main comparison.
- Use the site palette. Suggested semantic pairing: early path = forest
  `#3f5b3a`; other rounds = graphite or a tinted neutral. Do not introduce blue.
- On mobile, stack the two lanes but keep the three stages in the same order.
- For no-ED or open-admissions schools, collapse to a single "All applicants"
  flow instead of rendering an empty ED lane.
- Provide a table immediately below or via the existing accessible-table pattern
  with all displayed values.

### 2. Wait-list attrition view

Add a compact visual for CDS C.2 wait-list data. This should be visually
separate from the ED flow because wait-list dynamics are a different question:
"Did the school actually use the wait list?"

The recommended V1 visual is a three-stage attrition bar:

1. students offered a place on the wait list;
2. students accepting a wait-list spot;
3. students admitted from the wait list.

This is inspired by the recent wait-list coverage pattern that compares a large
wait-list offer pool against a much smaller admitted-off-waitlist count. The
CollegeData version should focus on the school currently being viewed, with
peer context added nearby when available.

#### Required metrics

| Metric | Formula | User-facing label |
|---|---:|---|
| Wait-list offered | `wait_list_offered` | Offered a wait-list spot |
| Wait-list accepted | `wait_list_accepted` | Accepted a wait-list spot |
| Wait-list admitted | `wait_list_admitted` | Admitted from wait list |
| Wait-list opt-in rate | `wait_list_accepted / wait_list_offered` | Joined the wait list |
| Wait-list admit rate | `wait_list_admitted / wait_list_accepted` | Admitted after joining |
| Wait-list offer rate | `wait_list_offered / c1_applicants` | Applicants offered wait list |
| Wait-list admitted vs class size | `wait_list_admitted` alongside `enrolled_first_year` | Context, not the primary rate |

#### Display rules

- If the school reports a wait-list policy but no counts, show a small
  "policy reported, counts unavailable" state.
- If `wait_list_accepted > 0` and `wait_list_admitted = 0`, show the zero
  explicitly. Do not hide the module.
- If `wait_list_offered`, `wait_list_accepted`, or `wait_list_admitted` violate
  basic monotonicity, show the values with a visible data-quality badge and link
  to the source PDF. Suppress the visual only when the extraction is clearly
  invalid, such as a hallucinated value, impossible order of magnitude, or source
  mismatch.
- Add an internal review flag for wait-list anomalies so these pages do not
  become invisible repair work.
- Always include a caution that wait-list outcomes are volatile year to year.

### 3. Trend view, when we have it

Add a trend strip below the current-year visual when at least three comparable
years are available for a school. If only one or two comparable years exist,
hide the trend strip for now.

"Comparable" means:

- same `school_id`;
- same canonical field family populated for the metric being charted;
- same template-family interpretation for the relevant fields;
- no known schema-year change that alters the metric's meaning.

The preferred trend view is:

- a 100% stacked bar or area chart for estimated class composition:
  ED seats versus all-other seats;
- a small line chart for ED admit rate versus all-other residual admit rate;
- a small line or dot chart for wait-list admit rate, when wait-list data is
  available in the same years.

#### Trend metrics

| Metric | Minimum years | Chart |
|---|---:|---|
| Likely ED share of class | 3 | 100% stacked bar/area |
| ED admit rate | 3 | Line |
| All-other residual admit rate | 3 | Line |
| Overall yield | 3 | Line or small stat trend |
| Wait-list admit rate | 3 | Line or dots |
| Wait-list admitted count | 3 | Bars |

#### Data notes

Trend data should use the same canonical schema mapping as current-year data.
For V1, it is acceptable if trends are available only for schools with multiple
clean modern CDS extractions. As older years become normalized, the same
component can expand to five-year histories.

If historical ED counts are missing but historical C.1 totals exist, do not
render a partial ED trend. A broken trend is worse than no trend.

### 4. Peer-bucket context

Add simple comparative context for the school, using broad buckets rather than
custom peers.

V1 buckets:

- `admit_rate_bucket`: under 5%, 5-10%, 10-20%, 20-40%, 40%+
- `control`: public, private nonprofit, private for-profit when present
- `undergrad_size_bucket`: under 2k, 2k-7k, 7k-15k, 15k+
- `year_start`: same CDS year when possible, latest available otherwise

Peer context should display as short contextual labels:

- "High for private schools with 5-10% admit rates"
- "Typical for schools in this selectivity band"
- "Very low wait-list admit rate among similar schools"

For V1, use percentiles and medians rather than ranking tables.

#### Peer metrics

| Metric | Peer statistic |
|---|---|
| Likely ED share of class | percentile and bucket median |
| ED admit-rate multiple | percentile and bucket median |
| All-other residual admit rate | percentile and bucket median |
| Overall yield | percentile and bucket median |
| Wait-list opt-in rate | percentile and bucket median |
| Wait-list admit rate | percentile and bucket median |
| Wait-list admitted count relative to class size | percentile and bucket median |

#### Peer display rules

- Require at least 30 schools with a non-null value for the specific metric. The
  threshold is for statistical stability, not privacy.
- Compute peer N per metric, not per bucket. A bucket with 30 schools but only
  18 ED reporters should not show an ED peer label.
- Use metric-family fallback rules:
  - ED metrics: keep control type longer than size; broaden size first, then
    control, then use admit-rate bucket only.
  - Wait-list metrics: keep size longer than control; broaden control first,
    then size, then use admit-rate bucket only.
  - Yield and overall admit-rate metrics: broaden size first, then control.
- If the broadened metric-specific bucket still has fewer than 30 schools, hide
  peer labels for that metric.
- Do not show precise percentile labels like "73rd percentile" on the primary
  card. Use plain language: low, typical, high, unusually high.
- The accessible table can expose the median, percentile, peer count, and bucket
  definition.

## Data model

The current `school_browser_rows` surface already carries the current-year
admission strategy fields. This PRD needs two additional derived surfaces:

### `school_admission_strategy_years`

One row per school per canonical year for charting trends.

Suggested fields:

| Field | Notes |
|---|---|
| `school_id` | canonical school slug |
| `canonical_year` | e.g. `2024-25` |
| `year_start` | numeric sort key |
| `template_family` | schema/template compatibility key for trends |
| `school_name` | display label |
| `source_url` | CDS source URL |
| `archive_url` | CollegeData archived document URL |
| `applied` | C.1 applicants |
| `admitted` | C.1 admitted |
| `enrolled_first_year` | C.1 enrolled |
| `yield_rate` | C.1 derived |
| `ed_offered` | C.21 |
| `ed_applicants` | C.21 |
| `ed_admitted` | C.21 |
| `wait_list_policy` | C.2 |
| `wait_list_offered` | C.2 |
| `wait_list_accepted` | C.2 |
| `wait_list_admitted` | C.2 |
| `wait_list_quality` | `ok`, `non_monotonic_reported`, `extraction_suspect`, `missing_counts` |
| `admission_strategy_quality` | projection quality flag |

### `admission_strategy_peer_buckets`

Precomputed or queryable peer stats for current-year and latest-year views.

Suggested fields:

| Field | Notes |
|---|---|
| `year_start` | same-year when available |
| `admit_rate_bucket` | broad selectivity band |
| `control` | ownership/control type |
| `undergrad_size_bucket` | size band |
| `metric_key` | e.g. `likely_ed_share_of_class` |
| `school_count` | comparison N for this metric, after null filtering |
| `median_value` | bucket median |
| `p25_value` | bucket p25 |
| `p75_value` | bucket p75 |
| `p90_value` | bucket p90 |

The peer layer can start as an in-app derived query if that is faster. If the
query becomes expensive, promote it to a materialized view.

## API and MCP readiness

PRD 022 introduces friendly school facts APIs, MCP tools, and CLI commands.
Admission strategy visuals should use the same derived payload shape so the
visual, API, MCP, and CLI surfaces do not drift.

Future response shape:

```json
{
  "category": "admissions",
  "key": "admission_strategy",
  "source": {
    "layer": "cds",
    "canonical_year": "2024-25",
    "archive_url": "https://www.collegedata.fyi/schools/duke/2024-25"
  },
  "current_year": {
    "ed": {
      "applicants": 6201,
      "admitted": 849,
      "admit_rate": {
        "value": 0.1369,
        "display_value": "13.7%"
      },
      "likely_class_seats": {
        "value": 849,
        "display_value": "849"
      }
    },
    "all_other_rounds": {
      "applicants": 48232,
      "admitted": 1901,
      "residual_admit_rate": {
        "value": 0.0394,
        "display_value": "3.9%"
      }
    },
    "wait_list": {
      "offered": 3990,
      "accepted": 2070,
      "admitted": 86,
      "wait_list_admit_rate_among_accepted": {
        "value": 0.0415,
        "display_value": "4.2%"
      }
    }
  },
  "trend": [],
  "peer_context": []
}
```

The first implementation can keep this internal to the frontend. Once PRD 022
friendly endpoints exist, the same object should be exposed there.

Precision rule: API payloads carry raw numeric values in `value`; UI and CLI
surfaces use `display_value`. Percent displays round to one decimal place unless
the value is below 1%, in which case two decimals are allowed.

## UX placement

On `/schools/[school_id]`, this belongs inside the existing Academic Profile /
Admissions area near the current Admission Strategy card.

Suggested order:

1. headline admission facts;
2. adjusted admission-flow view;
3. wait-list attrition view;
4. trend strip, if available;
5. peer context labels;
6. source and methodology links;
7. accessible data table.

On the archived CDS page `/schools/[school_id]/[year]`, show the same chart
using only that year's source data. Do not show current-year peer labels or
trend modules on archived pages in V1; mixing years there creates more confusion
than context.

## Accessibility

Every visual must include:

- semantic table with the same values;
- chart title and short description;
- visible source year;
- no color-only encoding;
- keyboard-accessible tooltip or disclosure for methodology notes;
- mobile layout that does not require horizontal scrolling for the primary
  chart.
- at 390px width, all primary numeric labels are visible without truncation;
  secondary details can move into a disclosure.

Tooltips are acceptable for secondary details, but the primary takeaway must be
visible without hover.

## Copy guidelines

Use plain, non-insider language.

Preferred terms:

- "Early Decision"
- "All other rounds"
- "Likely share of the entering class"
- "Admitted from the wait list"
- "Schools in a similar selectivity band"

Avoid:

- "residual" as the primary label, except in methodology copy;
- "C.21" or "C.2" in user-facing chart headings;
- "peer normalization";
- "strategy score."

## Implementation plan

### Phase 1: Current-year adjusted flow

- Rework the existing admission round visual into the adjusted two-lane flow.
- Replace the current production visual in place. Do not run old and new charts
  side by side except behind a short-lived local/dev flag.
- Keep the current derived data contract where possible.
- Add the accessible table using the CDS table-view pattern from PRD 020.
- Verify on pinned `(school_id, canonical_year)` fixtures for Duke, Vanderbilt,
  Goshen, and at least one school with no ED so tests do not drift with future
  extraction updates.

### Phase 2: Wait-list attrition

- Add the three-stage wait-list visual.
- Handle zero-admitted states explicitly.
- Add the data-quality badge and internal review flag for non-monotonic
  wait-list values.
- Add derived wait-list rates to the frontend utility layer if not already
  centralized.
- Add source/methodology links back to CDS C.2 fields.

### Phase 3: Trend data

- Build or expose `school_admission_strategy_years`.
- Render trend strip only when at least three comparable years are present.
- Start with likely ED class share and wait-list admit rate; add yield and
  all-other residual after the core chart works.

### Phase 4: Peer buckets

- Add simple bucket assignment.
- Compute medians and percentiles for the core metrics.
- Render short context labels on the school page.
- Add detailed peer-bucket numbers to the accessible table, not the visual.

### Phase 5: API alignment

- Align the internal derived payload with PRD 022 school-facts output.
- Add admission-strategy facts to the friendly API once that layer exists.
- Document fields in public API docs.

## Acceptance criteria

1. Duke and Vanderbilt school pages make the ED versus all-other class model
   clear without requiring the user to read the methodology page first.
2. The adjusted flow labels use exact counts, include the stage-scaling note,
   and link to methodology.
3. Wait-list data shows all three counts and the wait-list admit rate among
   students who accepted a wait-list spot.
4. A school with `wait_list_admitted = 0` displays that zero clearly.
5. Trend charts do not render unless at least three comparable years are
   available.
6. Peer context does not render unless the metric-specific comparison bucket has
   at least 30 schools after fallback broadening.
7. All charted values are available in an accessible table.
8. Mobile layout remains readable at 390px width, with all primary numeric
   labels visible without truncation.
9. Playwright visual QA covers:
   - pinned school-year with ED and wait-list data;
   - pinned school-year with ED and no wait-list admits;
   - pinned school-year with no ED;
   - pinned school-year with missing historical data;
   - pinned school-year with peer bucket too small.

## Open questions

1. Is "likely class seats" the right public label for the ED enrollment
   assumption, or should the UI use "class seats if ED admits enroll"?
2. Should wait-list peer context compare all schools, or only schools that
   report a wait-list policy?
3. Should trend view use a compact inline strip on the school page and a larger
   version on a future compare page?
4. Which school-year fixtures should be pinned for each visual state once the
   first implementation data audit identifies stable examples?

## First build recommendation

Ship the current-year adjusted flow and wait-list attrition first. They solve
the immediate comprehension problem and reuse data already in the product.

Add trends as soon as `school_admission_strategy_years` has enough comparable
rows. Add peer buckets after the chart copy is stable, because peer labels will
amplify whatever terminology the primary visual uses.
