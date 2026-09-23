# Wave 6 copy deck — per-school acceptance-rate pages (PRD 031 M2)

Read this as a parent, then as a counselor, then as IR. **Not signed yet.**
Revision 5 (after the round 4 editorial review).

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

**Lead** (deterministic; `acceptance-rate-copy.ts`). Every percent change
names its base-year count; tested across all 20 pilot schools, arithmetic
to one decimal. No causal verbs.

**Rate shape** (`rateShape`, compared at one decimal). Direction = latest
year vs the previous year.

- *Monotone* (never reverses) or too short: compare with the first year.
- *Flat* (latest = previous): compare with the first year.
- *Record* (no earlier year at or beyond the latest rate): the latest is
  the lowest/highest of the years shown.
- *Turn*: rising latest → find the most recent earlier year at or above the
  latest rate; the turn is the lowest year after it (the low the series has
  since moved away from). Falling is the mirror. If the turn is also the
  low/high of every year shown it is "a low/high"; otherwise "the lowest
  since fall {that earlier year}". **Ties go to the most recent tied
  year** (the one the series left last).

Sentences:

1. **Answer.** "{school} admitted {rate} of first-year applicants for fall
   {latest} ({admitted} of {applied})" +
   - monotone/flat: ", down from {first rate} for fall {first}." (with the
     dominant year: ", while applications rose from {a} to {b}.")
   - record: ", the lowest in the {n} years shown, down from {prev rate}
     for fall {prev}."
   - turn in the previous year: ", up from {rate} for fall {prev}[, the
     lowest in the {n} years shown]."
   - older turn: ", up from {prev rate} for fall {prev} and from a low of
     {rate} for fall {year}."
2. **Start** (record or turn): "It was {first rate} for fall {first}."
3. **Applications** (skipped when the dominant year runs): "Applications
   fell {x}% for fall {latest}, to {n} from {prev}[; they peaked at {n} for
   fall {year}[ in the years shown]]." or "…rose from {a} to {b} over that
   span." Fewer than four years: the latest change only.
4. **Dominant year** (four or more years, monotone or record, one
   consecutive step ≥ 60% of the span's rate change): "Most of the drop came
   in one year, from {rate} for fall {a} to {rate} for fall {b}, when
   applications rose from {x} to {y} and admits fell from {p} to {q}." Both
   counts, both years. Admits "fell/rose" when they moved with the rate,
   otherwise "went from".
5. **Missing years** (always last): "Usable figures for fall {year}[, …]
   are not in our archive."

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

## Filled examples — all 20 pilot schools (production data, 2026-09-23)

- Virginia Tech admitted 54.6% of first-year applicants for fall 2025 (31,515 of 57,755), down from 57.0% for fall 2023. Applications rose 10.4% for fall 2025, to 57,755 from 52,296.
- Haverford College admitted 13.3% of first-year applicants for fall 2025 (896 of 6,730), up from 12.4% for fall 2024, the lowest in the eight years shown. It was 18.8% for fall 2018. Applications fell 8.3% for fall 2025, to 6,730 from 7,341.
- Brown University admitted 6.3% of first-year applicants for fall 2025 (2,710 of 42,774), up from 5.4% for fall 2024 and from a low of 5.1% for fall 2022. It was 7.7% for fall 2018. Applications fell 12.5% for fall 2025, to 42,774 from 48,904; they peaked at 51,316 for fall 2023.
- Northeastern University admitted 5.2% of first-year applicants for fall 2024 (5,133 of 98,425), down from 20.5% for fall 2020, while applications rose from 64,459 to 98,425. Most of the drop came in one year, from 18.4% for fall 2021 to 6.8% for fall 2022, when applications rose from 75,244 to 91,000 and admits fell from 13,829 to 6,191.
- Duke University admitted 5.7% of first-year applicants for fall 2024 (2,957 of 51,795), the lowest in the five years shown, down from 6.8% for fall 2023. It was 8.9% for fall 2018. Applications rose from 35,767 to 51,795 over that span. Usable figures for fall 2021 and fall 2022 are not in our archive.
- University of Pennsylvania admitted 5.4% of first-year applicants for fall 2024 (3,523 of 65,236), the lowest in the seven years shown, down from 5.9% for fall 2023. It was 8.4% for fall 2018. Most of the drop came in one year, from 9.0% for fall 2020 to 5.9% for fall 2021, when applications rose from 42,205 to 56,332 and admits fell from 3,789 to 3,304.
- Harvard University admitted 4.2% of first-year applicants for fall 2025 (2,003 of 47,893), up from 3.6% for fall 2024 and from a low of 3.2% for fall 2022. It was 4.7% for fall 2018. Applications fell 11.3% for fall 2025, to 47,893 from 54,008; they peaked at 61,221 for fall 2022 in the years shown. Usable figures for fall 2020 are not in our archive.
- Princeton University admitted 4.4% of first-year applicants for fall 2025 (1,868 of 42,303), the lowest in the five years shown, down from 4.6% for fall 2024. It was 5.5% for fall 2018. Most of the drop came in one year, from 5.7% for fall 2022 to 4.5% for fall 2023, when applications rose from 38,019 to 39,644 and admits fell from 2,167 to 1,782. Usable figures for fall 2019, fall 2020, and fall 2021 are not in our archive.
- Johns Hopkins University admitted 6.1% of first-year applicants for fall 2025 (3,072 of 50,259), the lowest in the five years shown, down from 6.4% for fall 2024. It was 7.5% for fall 2021. Most of the drop came in one year, from 7.5% for fall 2023 to 6.4% for fall 2024, when applications rose from 38,893 to 45,895 and admits went from 2,923 to 2,954.
- Northwestern University admitted 7.7% of first-year applicants for fall 2024 (3,806 of 49,474), up from 7.2% for fall 2023, the lowest in the six years shown. It was 8.5% for fall 2018. Applications fell 4.4% for fall 2024, to 49,474 from 51,769. Usable figures for fall 2021 are not in our archive.
- Emory University admitted 10.3% of first-year applicants for fall 2024 (3,562 of 34,614), down from 18.5% for fall 2018. Applications rose from 27,559 to 34,614 over that span. Usable figures for fall 2020 are not in our archive.
- Rice University admitted 8.0% of first-year applicants for fall 2024 (2,597 of 32,473), up from 7.9% for fall 2023, the lowest in the six years shown. It was 11.1% for fall 2018. Applications rose from 20,923 to 32,473 over that span. Usable figures for fall 2020 are not in our archive.
- University of Notre Dame admitted 9.4% of first-year applicants for fall 2025 (3,320 of 35,401), the lowest in the seven years shown, down from 11.3% for fall 2024. It was 17.7% for fall 2018. Applications rose from 20,371 to 35,401 over that span. Usable figures for fall 2021 are not in our archive.
- Georgetown University admitted 13.5% of first-year applicants for fall 2025 (3,618 of 26,822), up from 12.9% for fall 2024 and from a low of 12.0% for fall 2021. It was 14.5% for fall 2018. Applications rose 2.6% for fall 2025, to 26,822 from 26,131; they peaked at 27,506 for fall 2021.
- New York University admitted 9.1% of first-year applicants for fall 2025 (10,340 of 114,125), the lowest in the six years shown, down from 9.2% for fall 2024. It was 20.0% for fall 2018. Applications rose from 71,834 to 114,125 over that span. Usable figures for fall 2021 and fall 2023 are not in our archive.
- Bowdoin College admitted 6.8% of first-year applicants for fall 2025 (957 of 14,045), the lowest in the six years shown, down from 7.1% for fall 2024. It was 9.2% for fall 2020. Applications rose 5.9% for fall 2025, to 14,045 from 13,265; they were lowest at 9,325 for fall 2021.
- Amherst College admitted 9.0% of first-year applicants for fall 2024 (1,238 of 13,742), down from 9.8% for fall 2023. It was 11.3% for fall 2019. Applications rose 8.0% for fall 2024, to 13,742 from 12,727; they peaked at 14,864 for fall 2022 in the years shown. Usable figures for fall 2020 are not in our archive.
- Hamilton College admitted 13.6% of first-year applicants for fall 2024 (1,162 of 8,531), up from 11.8% for fall 2023, the lowest in the six years shown. It was 16.4% for fall 2019. Applications fell 11.5% for fall 2024, to 8,531 from 9,643; they peaked at 9,899 for fall 2022.
- University of Richmond admitted 22.2% of first-year applicants for fall 2024 (3,585 of 16,152), the lowest in the seven years shown, down from 23.3% for fall 2023. It was 30.2% for fall 2018. Applications rose from 11,882 to 16,152 over that span.
- Bates College admitted 14.8% of first-year applicants for fall 2025 (1,433 of 9,660), up from 13.3% for fall 2024 and from 13.0% for fall 2023, the lowest since fall 2021. It was 17.8% for fall 2018. Applications fell 3.7% for fall 2025, to 9,660 from 10,027.

Johns Hopkins: the archive holds five reports (2021-22 to 2025-26); earlier years are not on file (a discovery gap, not unusable counts).

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
