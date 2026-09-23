# Wave 6 copy deck — per-school acceptance-rate pages (PRD 031 M2)

Read this as a parent, then as a counselor, then as IR. **Not signed yet.**
Revision 4 (after the round 3 editorial review).

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

**Lead** (deterministic; `acceptance-rate-copy.ts`). Rule for every
sentence: **each percent change names its base-year count** ("fell 12.5%
for fall 2025, to 42,774 from 48,904"); tested across all 20 pilot schools,
arithmetic checked to one decimal.

1. **Answer.** "{school} admitted {rate} of first-year applicants for fall
   {latest} ({admitted} of {applied})"
   - no turning point: ", down from / up from / the same as {first rate}
     for fall {first}." When the dominant-year sentence runs, the
     applications span rides here: "…, while applications rose from {a} to
     {b}."
   - turning point in the year just before the latest: ", up from {rate}
     for fall {year}, the lowest in the {n} years shown." followed by "It
     was {first rate} for fall {first}."
2. **Turning point** (interior low/high beyond both ends at one decimal):
   "That is up from a low of {rate} for fall {year} and down from {first
   rate} for fall {first}." + "(the lowest in the years shown)" with gaps.
3. **Applications** (skipped when the dominant-year sentence runs).
   Latest change first, with its base: "Applications fell {x}% for fall
   {latest}, to {n} from {prev}" + "; they peaked at {n} for fall {year}[
   in the years shown]." when an interior year is the true max (or "were
   lowest at" for the true min) and isn't the base year. No peak/low: "…
   rose from {first} to {latest} over that span[, but fell {x}% for fall
   {latest}, to {n} from {prev}]." Fewer than four years: the latest change
   only.
4. **Dominant year** (four or more years, no turning point, one
   consecutive-year step ≥ 60% of the span's rate change): the last
   narrative sentence, never mentions applications, temporal not causal:
   "Most of the drop came in one year, from {rate} for fall {a} to {rate}
   for fall {b}, when admits fell from {x} to {y}."
5. **Missing years** (always last): "Usable figures for fall {year}[, …,
   and fall {year}] are not in our archive."

**Section heading:** four or more years: "{school}’s acceptance rate, fall
{first}–{latest}"; fewer (no chart): "{school} first-year admissions, fall
{first}–{latest}".

**Chart** (four or more years): full width, 180px, one ink colour, bars
from zero, 13px values. Caption: "Share of first-year applicants admitted,
by fall entering class." + " — = not reported or not usable." when a year
is missing (same wording as the note).

**Table:** `table-layout: fixed; width: 100%`. Desktop: Year 18% ·
Acceptance rate 20% · Applied 13% · Admitted 13% · Enrolled 13% · Yield 11%
· Source 12% (right-aligned). Gap rows: "—" in the rate column and one
left-aligned cell spanning Applied→Source (14px sans, muted, wraps) with
"Report on file; counts not usable" or "No report in our archive". Below
640px: header "Rate"; Year/Rate/Applied fill the screen exactly (38/28/34%)
so the scroll cut lands on a column edge; gap labels move under the year.
Figures in the sans with tabular lining numerals (the mono zero is marked).
Layout guard: `web/tests/acceptance-rate-layout.spec.ts` fails if any
pilot table is wider than its column at 1440 or 1024px.

**Note**, **related links** (stacked on mobile), **hub link**: as in
revision 2.

---

## Filled examples (production data, 2026-09-23)

**Northeastern University** — *Northeastern University Acceptance Rate:
5.2% for Fall 2024*

> Northeastern University admitted 5.2% of first-year applicants for fall
> 2024 (5,133 of 98,425), down from 20.5% for fall 2020, while applications
> rose from 64,459 to 98,425. Most of the drop came in one year, from 18.4%
> for fall 2021 to 6.8% for fall 2022, when admits fell from 13,829 to
> 6,191.

**Brown University** — *Brown University Acceptance Rate: 6.3% for Fall 2025*

> Brown University admitted 6.3% of first-year applicants for fall 2025
> (2,710 of 42,774). That is up from a low of 5.1% for fall 2022 and down
> from 7.7% for fall 2018. Applications fell 12.5% for fall 2025, to 42,774
> from 48,904; they peaked at 51,316 for fall 2023.

Meta: "Brown University admitted 6.3% of first-year applicants for fall 2025
(2,710 of 42,774). Figures for each year since fall 2018, with source
files."

**Haverford College**

> Haverford College admitted 13.3% of first-year applicants for fall 2025
> (896 of 6,730), up from 12.4% for fall 2024, the lowest in the eight years
> shown. It was 18.8% for fall 2018. Applications fell 8.3% for fall 2025,
> to 6,730 from 7,341.

**Georgetown University**

> Georgetown University admitted 13.5% of first-year applicants for fall
> 2025 (3,618 of 26,822). That is down from a high of 16.8% for fall 2020
> and down from 14.5% for fall 2018. Applications rose 2.6% for fall 2025,
> to 26,822 from 26,131; they peaked at 27,506 for fall 2021.

**Duke University**

> Duke University admitted 5.7% of first-year applicants for fall 2024
> (2,957 of 51,795), down from 8.9% for fall 2018. Applications rose from
> 35,767 to 51,795 over that span. Usable figures for fall 2021 and fall
> 2022 are not in our archive.

**Virginia Tech** (3 years; heading "Virginia Tech first-year admissions,
fall 2023–2025", no chart)

> Virginia Tech admitted 54.6% of first-year applicants for fall 2025
> (31,515 of 57,755), down from 57.0% for fall 2023. Applications rose 10.4%
> for fall 2025, to 57,755 from 52,296.

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
