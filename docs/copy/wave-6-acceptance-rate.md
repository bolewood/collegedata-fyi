# Wave 6 copy deck — per-school acceptance-rate pages (PRD 031 M2)

Read this as a parent, then as a counselor, then as IR. **Not signed yet.**
Revision 2 (after the round 1 editorial review).

Route: `/schools/{id}/acceptance-rate`. Pilot only: 20 allowlisted schools,
`noindex`, not in the sitemap until the M1 slug decision
(`ACCEPTANCE_PILOT_INDEXABLE` in `web/src/lib/acceptance-pilot.ts`).

**Persona.** Primary: parents and students who searched
`{school} acceptance rate`. Secondary: counselors who want the trend in one
shareable URL.

**Rules.** Product layer (VOICE.md). Answer first, then the history. No field
IDs in the lead, no process words, no advice, no prestige adjectives, no
"odds"/"chances", **no causal language** (no "because", "due to", "driven
by"). Every sentence is generated from years that passed the checks
(`web/src/lib/acceptance-rate-copy.ts`, tested in
`acceptance-rate-copy.test.ts`).

**Precision.** One decimal for every rate on this page: lead, chart, table,
title, meta (5.7%, 20.5%, 57.0%). The hub and year pages keep the site
style (one decimal under 10%, whole numbers otherwise).

**Year labels.** The CDS report for 2024–25 counts the class that entered
in **fall 2024** (checked in the files: C1 says "applied … in Fall 2024").
Primary label everywhere is the fall: "Fall 2024". Secondary, in the table
only, 11px: "2024–25 report" (links to the year page). Chart axis: "’18 …
’24". En dashes in all spans.

---

## Templates

**Title** (≤ 65 characters before " | collegedata.fyi"; falls back in order):

1. `{school} Acceptance Rate: {rate} for Fall {latest} ({first}–{latest} History)`
2. `{school} Acceptance Rate: {rate} for Fall {latest} ({first}–{latest})`
3. `{school} Acceptance Rate: {rate} for Fall {latest}`
4. `{school} Acceptance Rate by Year`

**Meta description:** answer sentence [+ turning-point sentence] +
"Year-by-year figures from {school}’s Common Data Set, with source files."

**Breadcrumb:** SCHOOLS / {SCHOOL} / ACCEPTANCE RATE
**Kicker:** First-year admissions
**H1:** {school} *acceptance rate*
**Header strip:** Fall {first}–fall {latest}

**Lead** (deterministic):

1. **Answer.** "{school} admitted {rate} of first-year applicants for fall
   {latest} ({admitted} of {applied})" + ", down from / up from / the same
   as {first rate} for fall {first}." when there is no turning point.
2. **Turning point** (only when an interior year is below both ends — a
   low — or above both — a high — at one decimal; if both, the one farther
   from the latest rate): "That is up from a low of {rate} for fall {year}
   and down from {first rate} for fall {first}." / "That is down from a high
   of …".
3. **Applications.** Four or more years: "Applications rose from {first} to
   {latest} over that span." — plus ", but fell {x}% for fall {latest}
   ({prev} to {latest})" when the latest consecutive change runs the other
   way (≥ 1%). Fewer than four years: only the latest change,
   "Applications rose {x}% for fall {latest} ({prev} to {latest})."
4. **Missing years:** "Figures for fall {year}[, fall {year}, and fall
   {year}] are not available."

**Section heading:** {school}’s acceptance rate, fall {first}–{latest}

**Chart** (four or more usable years only): full width, 180px, one ink
colour, bars from zero, 13px mono values. Caption: "Share of first-year
applicants admitted, by fall entering class. Bars start at zero." + " — =
not available." when a year is missing.

**Table** (newest first): Year · Acceptance rate · Applied · Admitted ·
Enrolled · Yield · Source. Sticky year column. At 390px, Year, Acceptance
rate, and Applied fit without scrolling; a hint reads "Scroll for enrolled,
yield, and source →".

Missing year rows: one "—" across the five data columns, and the source
cell says which case it is (checked against the archive's documents):

- **Report on file; counts not usable** — the school's report for that
  year is in the archive, but its admissions counts did not pass the
  checks. The "{year} report" link goes to the year page.
- **No report in our archive** — no report for that year is on file. We
  do not say the school never published one; we have not verified that.

**Note** (one 13px style):

> Source: Common Data Set reports published by {school}, section C1
> (first-time, first-year, degree-seeking students). Note: Acceptance rate is
> admitted ÷ applied; yield is enrolled ÷ admitted. Each year is the class
> entering that fall; the 2024–25 report covers fall 2024. — = not reported
> or not usable.

**Related:** {school} overview · {school}’s {latest report} Common Data Set

**Hub link.** In the hub sentence "…an acceptance rate of 8.4%.", the words
*acceptance rate* link here only when this page is served.

---

## Filled examples (production data, 2026-09-23)

**Brown University** — *Brown University Acceptance Rate: 6.3% for Fall
2025 (2018–2025)*

> Brown University admitted 6.3% of first-year applicants for fall 2025
> (2,710 of 42,774). That is up from a low of 5.1% for fall 2022 and down
> from 7.7% for fall 2018. Applications rose from 35,437 to 42,774 over that
> span, but fell 12.5% for fall 2025 (48,904 to 42,774).

**Duke University** — *Duke University Acceptance Rate: 5.7% for Fall 2024
(2018–2024)*

> Duke University admitted 5.7% of first-year applicants for fall 2024
> (2,957 of 51,795), down from 8.9% for fall 2018. Applications rose from
> 35,767 to 51,795 over that span. Figures for fall 2021 and fall 2022 are
> not available.

Table rows: Fall 2022 — "No report in our archive"; Fall 2021 (2021–22
report) — "Report on file; counts not usable".

**Virginia Tech** (3 years, no chart) — *Virginia Tech Acceptance Rate:
54.6% for Fall 2025 (2023–2025)*

> Virginia Tech admitted 54.6% of first-year applicants for fall 2025
> (31,515 of 57,755), down from 57.0% for fall 2023. Applications rose 10.4%
> for fall 2025 (52,296 to 57,755).

## Checked, no footnote

- Brown lists 1,719 enrolled for both fall 2024 and fall 2025. Both are in
  the files: 855 + 863 + 1 (total printed 1,719) and 844 + 875 + 0.
- Northeastern admits fell from 13,829 (fall 2021) to 6,191 (fall 2022).
  Both totals are printed in the school's C1 tables; neither report
  describes a change in who is counted, so the page adds no footnote.

## Open for Anthony

1. "No report in our archive" is accurate but reads a little internal;
   "No report on file" is the shorter alternative.
2. The page uses the hub's display name ("Duke University"). The reviewer's
   examples used "Duke"; short names would need a curated list.
