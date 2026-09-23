# Wave 6 copy deck — per-school acceptance-rate pages (PRD 031 M2)

Read this as a parent, then as a counselor, then as IR. **Not signed yet.**
Revision 3 (after the round 2 editorial review).

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

**Title** (≤ 65 characters before " | collegedata.fyi"):
`{school} Acceptance Rate: {rate} for Fall {latest}`; names too long for
that fall back to `{school} Acceptance Rate by Year`.

**Meta description** (≤ 155 characters; whole sentences dropped, never part
of a number): "{answer sentence without comparison}" + "Figures for each
year since fall {first}, with source files." (no gaps) or "Figures back to
fall {first}, with source files." (gaps). Fallbacks: "…With source
files."; the answer alone; the answer without counts.

**Breadcrumb:** SCHOOLS / {SCHOOL} / ACCEPTANCE RATE · **Kicker:** First-year
admissions · **H1:** {school} *acceptance rate*. No date strip on the plate
(the section heading carries the span).

**Lead** (deterministic; `acceptance-rate-copy.ts`):

1. **Answer.** "{school} admitted {rate} of first-year applicants for fall
   {latest} ({admitted} of {applied})"
   - no turning point: ", down from / up from / the same as {first rate}
     for fall {first}."
   - turning point in the year just before the latest: ", up from {rate}
     for fall {year}, the lowest in the {n} years shown." (or "down from …
     the highest …").
2. **Turning point** (interior year below both ends = low, above both =
   high, compared at one decimal; if both, the one farther from the latest
   rate): "That is up from a low of {rate} for fall {year} and down from
   {first rate} for fall {first}." Adds "(the lowest in the years shown)"
   when the history has gaps.
3. **Dominant year** (four or more years, no turning point, one
   consecutive-year step ≥ 60% of the span's rate change, same direction):
   "Most of the drop came in one year, from {rate} for fall {a} to {rate}
   for fall {b}: admits fell from {x} to {y}, while applications rose {z}%."
   Factual only; never "because", "after", "as a result".
4. **Applications.** Four or more years: if an interior year is the true
   maximum (peak) or minimum (low) above/below both ends, the most recent
   such year: "Applications peaked at {n} for fall {year}[ in the years
   shown] and fell {x}% for fall {latest}, to {n}." When the latest change
   moves back toward the peak/low: "…and were {n} for fall {latest}, up {x}%
   from fall {prev}." When the peak/low is the previous year, only the
   latest change: "Applications fell {x}% for fall {latest}, to {n}." No
   peak/low: "Applications rose from {first} to {latest} over that span."
   Fewer than four years: only the latest change.
5. **Missing years:** "Usable figures for fall {year}[, …, and fall
   {year}] are not in our archive."

**Section heading:** four or more years: "{school}’s acceptance rate, fall
{first}–{latest}"; fewer (no chart): "{school} first-year admissions, fall
{first}–{latest}".

**Chart** (four or more years): full width, 180px, one ink colour, bars
from zero, 13px values. Caption: "Share of first-year applicants admitted,
by fall entering class." + " — = not available." when a year is missing.

**Table:** Year 24% · Acceptance rate 14% · Applied 13% · Admitted 13% ·
Enrolled 13% · Yield 11% · Source 12% (right-aligned). Figures in the sans
with tabular lining numerals (JetBrains Mono's zero has an inner mark that
`"zero" 0` cannot remove; scoped to this page). Gap rows: one dash across
the data columns; the source cell reads "Report on file; counts not usable"
or "No report in our archive". Below 640px the label sits under the year
and the dash is hidden.

**Note**, **related links** (stacked on mobile), **hub link**: as in
revision 2.

---

## Filled examples (production data, 2026-09-23)

**Northeastern University** — *Northeastern University Acceptance Rate:
5.2% for Fall 2024*

> Northeastern University admitted 5.2% of first-year applicants for fall
> 2024 (5,133 of 98,425), down from 20.5% for fall 2020. Most of the drop
> came in one year, from 18.4% for fall 2021 to 6.8% for fall 2022: admits
> fell from 13,829 to 6,191, while applications rose 20.9%. Applications
> rose from 64,459 to 98,425 over that span.

**Brown University** — *Brown University Acceptance Rate: 6.3% for Fall 2025*

> Brown University admitted 6.3% of first-year applicants for fall 2025
> (2,710 of 42,774). That is up from a low of 5.1% for fall 2022 and down
> from 7.7% for fall 2018. Applications peaked at 51,316 for fall 2023 and
> fell 12.5% for fall 2025, to 42,774.

Meta: "Brown University admitted 6.3% of first-year applicants for fall 2025
(2,710 of 42,774). Figures for each year since fall 2018, with source
files." (146 characters)

**Haverford College**

> Haverford College admitted 13.3% of first-year applicants for fall 2025
> (896 of 6,730), up from 12.4% for fall 2024, the lowest in the eight years
> shown. Applications fell 8.3% for fall 2025, to 6,730.

**Duke University**

> Duke University admitted 5.7% of first-year applicants for fall 2024
> (2,957 of 51,795), down from 8.9% for fall 2018. Applications rose from
> 35,767 to 51,795 over that span. Usable figures for fall 2021 and fall
> 2022 are not in our archive.

**Virginia Tech** (3 years; heading "Virginia Tech first-year admissions,
fall 2023–2025", no chart)

> Virginia Tech admitted 54.6% of first-year applicants for fall 2025
> (31,515 of 57,755), down from 57.0% for fall 2023. Applications rose 10.4%
> for fall 2025, to 57,755.

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
