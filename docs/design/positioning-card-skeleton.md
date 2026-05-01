# Per-school positioning card + methodology page — UX skeleton

**Status:** Skeleton, awaiting design pass with Claude Design.
**Created:** 2026-05-01 (autoplan)
**Implements:** [PRD 016 — Academic positioning card](../prd/016-academic-positioning-card.md)
**Voice/tokens:** [`web/DESIGN_SYSTEM.md`](../../web/DESIGN_SYSTEM.md), [`web/src/app/tokens.css`](../../web/src/app/tokens.css)

> **Audience for this doc:** a senior designer about to wireframe. The
> heaviest constraint is honesty about uncertainty: every visual element
> on the card has to be defensible against the reviewers' charge that
> *any* positioning UI risks looking more precise than CDS C.9/C.11
> support. Lead with the caveats; let the geometry serve them.
>
> **Two questions are deliberately left open** for the design pass —
> see §8. The rest of the doc has enough structure that the design
> conversation can productively riff on exactly those two open
> questions without renegotiating the rest.

The page this lives on (`web/src/app/schools/[school_id]/page.tsx`) is
already an editorial archive — serif headline, mono call-numbers,
ledger of archived CDS docs, federal Scorecard outcomes. The brand
voice is "paper, ink, and one quiet green," which is exactly the right
voice for a positioning card that is supposed to read as a footnote on
public data, not a verdict. We are *adding a margin annotation* to a
catalog card, not bolting a SaaS widget onto a library page.

---

## 1. Per-school positioning card — anatomy and states

### Placement on `/schools/[school_id]`

Current section order on a school page with archived CDS:

1. Header (school name, IPEDS, Carnegie, archive count + sparkline)
2. Documents ledger (`rule-2` divider, then per-year `DocumentCard`s)
3. `OutcomesSection` (federal Scorecard)
4. `ScorecardVintageNote`

The positioning card slots in **between the documents ledger and the
OutcomesSection**, under a `rule-2` divider that mirrors the ledger
divider above it. Rationale:

- The ledger establishes provenance ("we have this school's CDS for
  these years"). The positioning card *reads from* that ledger and
  should sit immediately downstream of it so the visual chain is:
  *here are the source PDFs → here is what they say about your fit →
  here is the federal outcomes baseline.*
- Putting it above the ledger would make positioning feel like the
  primary product of the page; the existing PRD positions it as
  feature #2 to the archive, not the headline. The archive is the
  credibility moat.
- Putting it below `OutcomesSection` would bury it; visitors arriving
  from a "[School] common data set" SEO query stop reading after the
  Scorecard.

So: ledger → **positioning card** → outcomes → vintage note.

### Empty state (no profile entered)

This is the default state for nearly every page view, and it has to
stand on its own as a useful "here's what this school's published
academic profile looks like" panel — even if the user never enters
anything. Components inside the card:

- A mono caption above the card: `§ ACADEMIC PROFILE` (matches the
  ledger and outcomes voice).
- A serif sub-head: *"Where you'd land in this school's admitted
  class."* Italic on the second clause per voice convention.
- A horizontal SAT range strip showing 25th / 50th / 75th anchors with
  the school's actual numbers labeled in tabular mono — e.g. for
  Bowdoin's 2024 CDS: `1430 — 1500 — 1540`. The strip is ink-on-paper
  with hairline rules at the anchor points. No score plotted.
- A GPA bucket distribution rendered as a vertical bar mini-chart, ink
  bars on `--paper-2` ground, with the bucket labels in mono on the
  x-axis (`4.0`, `3.75–3.99`, `3.50–3.74`, …).
- A single-line stat row: `ADMIT RATE 9% · TEST POLICY OPTIONAL · % SUBMITTING SAT 47%`.
  All forest, mono, uppercase, tracked.
- A primary CTA button (`.cd-btn`) — *"Add your scores to see where you fit"* —
  that opens the profile form (see §2).

The empty state is intentionally **almost as informative as the filled
state**. If the user never enters a profile, they still leave with
"Bowdoin's middle-50% is 1430–1540 and only ~half their admits even
submitted scores" — which is the most defensible sentence the data
supports anyway.

### Filled state (profile entered)

Same anatomy, with three additions:

- A small ink tick mark plotted on the SAT strip at the student's
  composite score, labeled below in mono (`YOU 1480`). The tick is a
  vertical hairline, not a dot or pin — pins look like a precise GPS
  coordinate, ticks look like a margin annotation. Brick (`--brick`)
  if below 25th, ink if inside 25–75, forest if above 75th. **Use
  hue sparingly** — the tick itself stays ink; the *label color* is
  what shifts.
- A bucket highlight on the GPA chart: the user's bucket bar gets the
  forest fill, all others stay ink at 60% opacity. Above the chart in
  mono: `YOUR GPA 3.7 → 3.50–3.74 BUCKET (24% OF ADMITS)`.
- A positioning sentence rendered in body serif, not as a label badge.
  The sentence form is load-bearing — a sentence reads as
  interpretation, a badge reads as verdict. Examples:
  - "Your SAT is **above the 75th percentile** of admitted students who
    submitted scores. Your GPA falls in the modal admit bucket. This
    school admits 9% of applicants."
  - "Your SAT is **within the middle 50%** of submitting admits."
  - "Your SAT is **below the 25th percentile** of submitting admits."

The reach/target/safety label appears as a *secondary* mono caption
beneath the sentence, in the form `§ TIER · TARGET (RATIONALE: SAT in mid-50%, admit rate 9%)` —
not as a hero badge. See §3 for when the tier line is suppressed
entirely.

### Loading state

Skeleton on the card outline at the same height the filled card will
occupy (prevents layout shift when the user lands from search). Use
`--paper-2` blocks where bars/numbers will go. No spinner — the rest
of the page already loads progressively.

### Error state

If `school_academic_profile` returns 5xx or malformed: render the
empty-state shell with a mono note in `--ink-3`: `§ PROFILE DATA TEMPORARILY UNAVAILABLE — TRY AGAIN OR VIEW THE SOURCE CDS BELOW`.
Link "view the source CDS" to the latest doc in the ledger above. Do
*not* render an empty range bar; partial geometry implies precision we
don't have.

### "This school has no current CDS" state

Reuse the existing `CoverageBadge` pattern. The card collapses to a
single sentence: *"We don't have a current Common Data Set for this
school. Federal outcomes below give a partial picture."* Linked
"federal outcomes below" anchor-jumps to `OutcomesSection`. No range
bar, no tier label, no CTA to enter a profile. (Entering a profile on
a no-CDS school produces nothing useful, so we don't invite it.)

### Test-optional disclosure

When `test_policy = optional` AND the student has *not* entered a SAT
or has explicitly checked "not submitting":

- The SAT strip renders at 30% opacity (`--ink-4` text, ink-at-30%
  bars) with a diagonal hatch overlay at low opacity. Not grayed to
  the point of unreadable — the school's published numbers stay
  legible — but visibly demoted.
- Above the strip, mono caption in ochre (`--ochre`): `§ TEST-OPTIONAL · BAND REFLECTS SUBMITTING ADMITS ONLY (47%)`.
  Ochre is "rare emphasis"; this is exactly the case it's reserved for.
- The positioning sentence drops the SAT clause: "Your GPA falls in the
  modal admit bucket. This school is test-optional; without test
  scores, position is GPA-only."

### "X% of admits submitted" caveat

This is the headline caveat from the legal/research review and it must
be **inline with the SAT strip**, not buried in a footnote. Two surfaces:

1. A mono caption directly under the strip: `§ FROM THE 47% OF ADMITS WHO SUBMITTED SCORES · 2024–25 CDS`.
2. The methodology link sits at the end of that caption: `· METHOD →`,
   anchoring to the methodology page section on test-optional drift.

This caption is present in **every state** of the card except "no
current CDS" and the loading skeleton.

### Source-link footer

Bottom of the card, hairline rule above it (`.rule`), mono only:

```
§ SOURCE: COMMON DATA SET 2024–25 · §C.7 §C.9 §C.11 · ARCHIVED PDF →
```

The "ARCHIVED PDF" link points to the actual `cds_artifacts` document
on Supabase storage — the same URL the `DocumentCard` above already
exposes. The §-prefixed question numbers cite which CDS cells the card
read.

### Mobile vs desktop

Desktop (≥ 768px): two-column layout inside the card. Left column =
SAT strip + GPA chart stacked. Right column = stat row + positioning
sentence + tier caption. Card max-width inherits `max-w-5xl` from the
page wrapper.

Mobile: single column, stacked in this order — caption, sub-head, SAT
strip, test-optional caption (when applicable), GPA chart, stat row,
positioning sentence, tier caption, source footer. CTA button
full-width at the bottom of the empty state. The SAT strip stays
full-bleed inside the card; the GPA bars resize but keep the same
bucket labels — no responsive label-hiding (numeric labels are the
point of the chart).

The existing page already wraps at `max-w-5xl px-4 sm:px-6` — match
that and the card will breathe correctly at all widths.

---

## 2. Profile entry UI

**Inline mini-form on the card itself**, not a modal, not a sidebar. A
modal interrupts the reading flow on a page that's primarily about
reading; a sidebar competes with the document ledger. The form lives
inside the same card, replacing the CTA button when invoked.

Anatomy:

- Three labeled inputs in a row on desktop, stacked on mobile:
  - **GPA** (number, 0.00–5.00, one decimal of precision shown as a
    suggestion; freeform underneath). Required.
  - **SAT composite** (number, 400–1600, optional). Helper text:
    *"Leave blank if you're not submitting scores."*
  - **ACT composite** (number, 1–36, optional). Helper text: *"We'll
    convert to SAT-equivalent for the range bar."*
- A subtle "not submitting scores" checkbox below the test inputs,
  pre-checked when both test fields are blank.
- A submit button (`.cd-btn`) reading *"Show my position"*. Submission
  is client-side only — the form just writes to localStorage and
  re-renders the card.
- A ghost "Cancel" button (`.cd-btn--ghost`) reverts to the empty
  state.

**Deferred to v1 by design:** state, intended major, residency,
rigor multiplier. The reviewers explicitly flagged these as scope
that would look foolish in 6 months given CDS doesn't publish
state- or major-stratified percentiles. The form must be obviously
short — three fields — so the absence of those knobs reads as
*deliberate restraint*, not a missing feature.

### Persistence

- localStorage key `cdfyi_profile_v1`, JSON-encoded, no PII beyond GPA
  / SAT / ACT / submitting-flag. Set TTL (1 year) and surface a "this
  was saved 3 weeks ago" note above the card when re-rendered.
- Shareable URL parameters: `?gpa=3.7&sat=1480` (and `?act=33`) on the
  school URL itself. Reading from URL params *overrides* localStorage
  for that pageview but does not persist them — share-link recipients
  see the position the sender saw without overwriting their own
  saved profile. This is how a counselor sends a student a specific
  view in a v1 world without saved profiles.
- "Clear my profile" affordance: small mono link in the source footer
  area: `§ CLEAR SAVED PROFILE`. Confirmation inline (button morphs
  to "Are you sure? · Yes / Cancel"), not a system dialog.

### Persistence across schools

Once entered on one school page, the profile auto-fills on every other
school page in the same browser. No cross-school list view in v1;
that's the v2 list builder. But a small mono row at the top of the
card, when a saved profile is present, reads:

```
§ USING YOUR SAVED PROFILE · GPA 3.7 · SAT 1480 · EDIT · CLEAR
```

`EDIT` opens the inline form pre-filled.

---

## 3. Tier label semantics and caveat hierarchy

The reviewers' concern is real: hard reach/target/safety labels on a
9%-admit school whose admit decisions are 70% holistic factors *over*-
state the data. The skeleton answer is a two-tier semantic where the
*sentence* form leads and the *label* form is secondary and
suppressible.

### Primary: positional sentence

Always rendered when a profile exists. Three forms:

- **Above the 75th percentile of submitting admits** ("you'd be a
  high scorer in this admit class")
- **Within the middle 50% range of submitting admits** ("your scores
  are typical for admits")
- **Below the 25th percentile of submitting admits** ("you'd be a
  low scorer in this admit class")

Combined with a one-line GPA clause (above/within/below modal bucket)
and an admit-rate clause. This is the durable, defensible artifact.
It maps directly onto cells in CDS C.9 and C.11; anyone can audit it
against the source PDF.

### Secondary: tier label, with rationale

A small mono caption beneath the sentence:
`§ TIER · TARGET · BASIS: SAT IN MID-50%, ADMIT RATE 9%`.

Tier mapping (publishable rubric, not opaque ML):

- **Likely** — admit rate ≥ 50% AND scores at-or-above mid-50%.
- **Strong fit** — admit rate ≥ 25% AND scores in or above mid-50%.
- **Possible** — scores in mid-50% range, admit rate 10–25%.
- **Unlikely** — scores below mid-50% OR admit rate < 10%.
- **Long shot** — scores below 25th *and* admit rate < 25%, or admit
  rate < 10% regardless of scores.

We use "Likely / Strong fit / Possible / Unlikely / Long shot" instead
of "safety / target / reach / hard reach" because the latter family
implies a counselor-style decision, while the former describes
probability bands. This keeps the labels useful for the data-curious
audience without overpromising counselor-grade calibration.

### When the tier label is suppressed

The tier caption is **not rendered** when:

- The school's admit rate is below 15% AND the student's scores are
  inside the mid-50%. Rationale: at 15-and-under admit rates, the
  numerical position barely moves the outcome; rendering "Possible"
  vs "Unlikely" implies a precision the data can't support. Render
  the positional sentence + admit-rate sentence, then a mono caption:
  `§ AT THIS SELECTIVITY, NUMERICAL POSITION IS A SMALL FACTOR · METHOD →`.
- C.9 SAT/ACT data is missing or stale (older than 3 years). Render
  the GPA-only positional sentence and a `§ SAT/ACT FIGURES UNAVAILABLE FOR THIS SCHOOL`
  caption.
- Test-optional school + non-submitting student + no GPA distribution
  in the latest CDS. Render only the admit-rate sentence and skip
  the tier caption entirely.

The empty state never renders tier labels at all (there's no profile
to position against).

### Caveat hierarchy, top to bottom

1. Test-optional submitter-only caveat (under the SAT strip, **always**
   when applicable).
2. Selectivity caveat (under the tier caption, **always** for sub-15%
   admit-rate schools).
3. CDS year + source link (in the footer, **always**).
4. "This is positioning, not a prediction" — single line in the
   methodology link footer (**always**).

---

## 4. Methodology page — anatomy

Route: `/methodology/positioning` (not `/positioning/methodology` — the
parent `/methodology/` route gives us a place for future sibling docs:
extraction, scorecard mapping, etc.).

### Top: one-line explainer

Serif lede paragraph, italic accent on the second half:

> *"This page shows where your scores would land in a school's
> admitted-class numbers. It is not a chance-me, and it does not
> predict admissions decisions."*

Below, a mono caption: `§ LAST UPDATED 2026-05-01 · OPEN-SOURCE METHOD`.

### "What we use" section

Subsections, each tied to a CDS question number:

- **§C.9 — SAT/ACT 25th/50th/75th percentiles.** We linearly interpolate
  between the published anchors to estimate where any single score
  falls. Worked example: Bowdoin 2024 published 1430 / 1500 / 1540.
  A 1480 sits between the 25th and 50th — specifically, ~42nd
  percentile by linear interpolation. Show the math inline: `(1480 − 1430) / (1500 − 1430) × 25 + 25 = 42.9`.
  Disclose the assumption ("scores are uniformly distributed between
  anchors, which is approximately but not exactly true").
- **§C.11 — GPA bucket distribution.** Direct lookup, no
  interpolation. Worked example: Bowdoin's 2024 C.11 shows 24% of
  admits in the 3.50–3.74 bucket. A student with a 3.7 GPA falls in
  that bucket.
- **§C.12 — mean GPA, % submitting GPA.** Used for the "modal admit
  bucket" determination and the "% submitting GPA" caveat.
- **§C.7 — admission factor importance.** When a school marks GPA or
  test scores as "considered" rather than "very important," we surface
  that as a one-line note ("This school marks test scores as
  *considered*, not *very important*"). We do not numerically
  re-weight the position score on this — too easy to overreach.
- **§C.8 — test policy.** Drives the test-optional disclosure.
- **§C.1/§C.2 — admit rate.** Drives the tier rubric and the
  selectivity-based suppression rule.

Each subsection has a "see this in Bowdoin's PDF" link to the actual
archived source.

### "What we don't use" section

Bulleted, unapologetic. Each bullet is a one-liner with rationale:

- **Legacy / donor / institutional priorities** — not in CDS.
- **Athletic recruitment** — not in CDS at the granularity that would
  matter.
- **Geographic balance** — schools may publish enrollment-by-state in
  CDS but not admit-by-state; positioning at that granularity is not
  defensible.
- **Demonstrated interest** — captured in §C.7 as a yes/no factor
  weight, but not numerically positionable.
- **Intended major** — institution-wide CDS only; major-level
  admit profiles are tribal.
- **In/out-of-state for publics** — CDS does not publish state-stratified
  admit percentiles. We do not estimate.
- **Essays, recommendations, interview** — qualitative, not in the
  position calculation.
- **Application timing (ED/EA)** — known to shift outcomes
  significantly; not in v1.

### "Why this isn't a chance-me" section

Three-paragraph plain-English explanation:

1. A *position* says where you sit on a published distribution. A
   *prediction* says how the school will decide. Those are different
   questions and the data on this site can only answer the first.
2. Even at the median scores, holistic schools admit 9% of applicants
   — meaning 91% of applicants who looked numerically identical to
   admits did not get in. Numbers describe the bar, not the verdict.
3. We publish the rubric so you can audit it. If you disagree with the
   tier mapping, you can read the source PDFs above and form your own
   read. That's the point.

### "Sources and audit trail"

Every claim links to a CDS question number. The page itself ends with
a link to the worked-example school's PDF in the archive.

---

## 5. Information hierarchy on `/schools/[school_id]`

After the card lands, the section order a visitor reads top-to-bottom:

1. **Header** — school name, IPEDS / Carnegie / archive count.
   Provenance and identity.
2. **Documents ledger** — the catalog of archived CDS years. The
   archive is the moat; lead with it.
3. **Positioning card** — empty by default, becomes useful with a
   profile. Reads downstream of the ledger so the source chain is
   visible.
4. **OutcomesSection** — federal Scorecard, completion rates, post-grad
   earnings. Different question (outcomes), still useful.
5. **ScorecardVintageNote** — provenance footer.

The directory-only stub (no archived CDS) keeps its current order and
**does not** render the positioning card. Empty positioning on a
no-data school is worse than no positioning at all.

---

## 6. States and edge-cases inventory

| State | Card behavior |
|---|---|
| Loading | Skeleton at filled-card height. |
| Empty (no profile) | Published 25/50/75 + GPA dist + admit rate + CTA. |
| Filled, complete profile, normal school | Full card with sentence + tier caption. |
| Filled, complete profile, sub-15% admit | Sentence shown, tier caption suppressed, selectivity caveat. |
| Filled, GPA only (no SAT/ACT) | GPA bucket + modal-bucket sentence; no SAT strip plot, just school's published range. |
| Filled, SAT only (no GPA) | SAT strip plotted; GPA chart shows distribution unhighlighted; sentence drops GPA clause. |
| Test-optional + not submitting | SAT strip demoted; sentence is GPA-only. |
| No current CDS | Single-sentence collapsed card, no inputs, link to outcomes. |
| Stale CDS (> 3 years old) | Render with a `§ DATA FROM 2021–22 · MAY BE OUT OF DATE` mono caption above the source footer. |
| C.9 missing for this school | SAT strip absent, mono note. GPA + admit-rate sentence still possible. |
| C.11 missing for this school | GPA chart absent, mono note. SAT + admit-rate sentence still possible. |
| Both missing | Empty-state shell with a "we have a CDS but couldn't extract academic profile fields" coverage note. |
| School removed by takedown | Whole school page already 404s under the existing takedown flow; positioning card never renders. |
| Very high admit rate (≥ 80%) | Tier rubric maps almost everyone to "Likely"; that's accurate. Render normally. |
| Very low admit rate (< 5%) | Tier suppressed always; sentence + selectivity caveat only. |
| Profile entered but invalid (GPA > 5.0, SAT < 400) | Form rejects with inline mono error: `§ ENTER A GPA BETWEEN 0.0 AND 5.0`. |
| URL params override saved profile | Mono caption: `§ VIEWING WITH PROFILE FROM SHARED LINK · USE YOURS INSTEAD?`. |

---

## 7. Accessibility skeleton

- **Range bar.** Render as a `<div role="img">` with an `aria-label`
  that reads, e.g., "SAT range: 25th percentile 1430, median 1500,
  75th percentile 1540. Your score 1480 falls between the 25th and
  50th percentile." A visually-hidden `<p>` sibling carries the same
  text for screen readers in case `role="img"` is suppressed.
- **GPA chart.** A `<table>` with `aria-hidden="false"` carrying the
  bucket / percent rows beneath the visual chart. Visual chart marked
  `aria-hidden="true"`. The table is visually hidden but readable by
  AT — uses `.sr-only` style.
- **Form.** Each input has a `<label>` with `for=`, plus inline helper
  text via `aria-describedby`. Errors via `aria-invalid` and
  `aria-errormessage`.
- **Focus order.** Header → ledger documents → "Add your scores" CTA
  (when empty) → form fields in DOM order → submit → outcomes. The
  card's interactive surface is one logical group; tab through it
  before tabbing into outcomes.
- **Keyboard.** All interactive elements (CTA, form fields, edit/clear
  links, source PDF link, methodology link) reachable by Tab. No
  custom keyboard handlers — native form semantics only.
- **Touch targets.** Buttons and links inside the card are ≥ 44 px
  tap-targets on mobile. Inline mono links (`EDIT`, `CLEAR`,
  `METHOD →`) get padded hit-areas via `padding: 8px 4px` even though
  visually they sit on the baseline.
- **Contrast.** `--ink` on `--paper` exceeds WCAG AA. `--ink-3` on
  `--paper` for mono captions hits AA at 12px+ but **not** AAA — that's
  fine for mono captions, not for primary content. Brick (`--brick`)
  on `--paper` for the "below 25th" label clears AA. Ochre
  (`--ochre`) on `--paper` for the test-optional caveat clears AA at
  12px+.
- **Reduced motion.** No motion in v1. The card has no animations to
  honor `prefers-reduced-motion` against.
- **Screen reader announcement on submit.** When the form submits and
  the card re-renders, a `role="status"` live region inside the card
  announces the positioning sentence.

---

## 8. Two open design questions

**Q1: What is the visual treatment for the SAT range strip?** The
honest geometry options are: (a) a horizontal hairline with three tick
marks at 25/50/75 and a fourth tick for the user's score, all the same
weight; (b) a thin filled bar between 25 and 75 with hairline anchors
at 25/50/75 and a separate user-score tick above or below; (c) a
distribution sketch that hints at the implied curve without committing
to one (a faint bell-ish shadow). Each carries a different precision
implication. (a) reads most as marginalia and least as "chart", which
matches the brand voice; (c) is the most informative but risks looking
like we know the underlying distribution shape, which we don't. The
designer should pick this with full awareness of the precision
trade-off.

**Q2: Where does the test-optional submitter-only caveat physically
sit, and how loud is it?** Options: (a) tightly bound to the SAT
strip, ochre-cased mono caption directly under it, always present
when applicable. (b) Promoted to a card-level banner above the
positioning sentence when test-optional + non-submitting, demoted to
inline when test-optional + submitting. (c) A sticky footer line on
the card that follows scroll. The reviewers were specific that this
caveat must be visible, not buried — but "visible" is a wide range.
The designer should call the loudness level given that almost half of
the Top 200 are test-optional now and over-loud caveats start reading
as boilerplate the user banner-blinds past.

---

## Notes for implementation handoff

- The card itself should be one component (`web/src/components/PositioningCard.tsx`)
  that accepts `(profile, schoolAcademicProfile)` and a render mode.
  The scoring lives in `web/src/lib/positioning.ts` and is called
  client-side; the card receives the school profile from the page's
  server-side fetch but does the score computation in the browser
  to keep student profile data off the server (consistent with the
  PRD's "no profile data leaves the browser by default" stance).
- Reuse `.cd-card`, `.rule-2`, `.cd-btn`, `.cd-btn--ghost`,
  `.mono`, `.serif`, `.nums`. Do not introduce new tokens for v1.
- The positioning sentence is the load-bearing artifact. Every other
  visual element exists to support it. If a designer is in doubt
  about a treatment, they should ask: *does this make the sentence
  more honest or less honest?*
