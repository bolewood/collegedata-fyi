# Wave 6 copy deck — per-school acceptance-rate pages (PRD 031 M2)

Read this as a parent, then as a counselor, then as IR. **Not signed yet.**
Revision 8 (after the round 7 editorial review).

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

**Lead** (deterministic; `acceptance-rate-copy.ts`). At most five
sentences, none over 35 words, 75 words in all (tested). When the
dominant-year sentence runs, a percent-change applications sentence is
dropped (the dominant sentence carries the applications that matter); a
plain span sentence stays. Every claim is re-derived from the table by an independent audit
(`acceptance-lead-audit.ts`) over all 20 pilot schools and synthetic
series; it fails on the round-5 Bates, Amherst, and Northwestern leads.

Display precision rules (one decimal): directions compare printed values
("unchanged from X%" when equal); "lowest/highest" claims must hold at full
precision and every year tied at display is named ("7.2% for fall 2023 and
fall 2022, the lowest…"). "the N years shown" only for unbroken series;
with gaps, "the N years with figures".

1. **Answer.** "{school} admitted {rate} of first-year applicants for fall
   {latest} ({admitted} of {applied})" +
   - *record* (nothing prints below/above the latest): ", the lowest in
     {N years}[, tied with fall X], down from {rate} for fall {first}" when
     monotone, else "…, down from {prev rate} for fall {prev}".
   - otherwise compare with the previous year, then the recent turn
     (`rateShape`): in the previous year it folds in ("up from {rate} for
     {falls}, the lowest in {N years}" when it is the series low); older,
     "and from a low of {rate} for {falls}" when it is the series low, else
     "and from {rate} for fall {E}, the lowest since fall {X} ({rate})" where
     X is the most recent earlier year that printed lower.
   - *far extreme*: moving down but not the series low → its own sentence,
     "The low was {rate}, for {falls}." (mirror: "The high was …");
     skipped when the first year ties it or it was already named.
2. **Start:** "It was {first rate} for fall {first}." — dropped when the
   answer already named the first year (monotone series, or the first year
   is the turn or far extreme).
3. **Applications:** "Applications fell {x}% for fall {latest}, to {n} from
   {prev}[; the most (fewest) in the years shown/with figures was {n}, for
   fall {year}]." No peak/low: "…rose from {a} to {b} over that span."
4. **Dominant year** (four or more years, monotone or record, one
   consecutive step ≥ 60% and ≤ 100% of the span's change, not the latest
   step of a non-monotone series): "Most of the drop came in one year, from
   {rate} for fall {a} to {rate} for fall {b}, when applications rose from
   {x} to {y} and admits fell/went from {p} to {q}."
5. **Missing years** (always last), in the table's terms: "No report for
   fall {year} is in our archive." / "Usable figures for fall {year} are not
   in our archive." / both: "Our archive has no report for fall 2022 and no
   usable figures for fall 2021."

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

- Virginia Tech admitted 54.6% of first-year applicants for fall 2025 (31,515 of 57,755), the lowest in the three years shown, down from 57.0% for fall 2023. Applications rose 10.4% for fall 2025, to 57,755 from 52,296.
- Haverford College admitted 13.3% of first-year applicants for fall 2025 (896 of 6,730), up from 12.4% for fall 2024, the lowest in the eight years shown. It was 18.8% for fall 2018. Applications fell 8.3% for fall 2025, to 6,730 from 7,341.
- Brown University admitted 6.3% of first-year applicants for fall 2025 (2,710 of 42,774), up from 5.4% for fall 2024 and from a low of 5.1% for fall 2022. It was 7.7% for fall 2018. Applications fell 12.5% for fall 2025, to 42,774 from 48,904; the most in the years shown was 51,316, for fall 2023.
- Northeastern University admitted 5.2% of first-year applicants for fall 2024 (5,133 of 98,425), the lowest in the five years shown, down from 20.5% for fall 2020. Applications rose from 64,459 to 98,425 over that span. Most of the drop came in one year, from 18.4% for fall 2021 to 6.8% for fall 2022, when applications rose from 75,244 to 91,000 and admits fell from 13,829 to 6,191.
- Duke University admitted 5.7% of first-year applicants for fall 2024 (2,957 of 51,795), the lowest in the five years with figures, down from 6.8% for fall 2023. It was 8.9% for fall 2018. Applications rose from 35,767 to 51,795 over that span. Our archive has no report for fall 2022 and no usable figures for fall 2021.
- University of Pennsylvania admitted 5.4% of first-year applicants for fall 2024 (3,523 of 65,236), the lowest in the seven years shown, down from 5.9% for fall 2023. It was 8.4% for fall 2018. Applications rose 9.7% for fall 2024, to 65,236 from 59,465; the fewest in the years shown was 42,205, for fall 2020.
- Harvard University admitted 4.2% of first-year applicants for fall 2025 (2,003 of 47,893), up from 3.6% for fall 2024 and from a low of 3.2% for fall 2022. It was 4.7% for fall 2018. Applications fell 11.3% for fall 2025, to 47,893 from 54,008; the most in the years with figures was 61,221, for fall 2022. Usable figures for fall 2020 are not in our archive.
- Princeton University admitted 4.4% of first-year applicants for fall 2025 (1,868 of 42,303), the lowest in the five years with figures, down from 4.6% for fall 2024. It was 5.5% for fall 2018. Applications rose from 35,370 to 42,303 over that span. Usable figures for fall 2019, fall 2020, and fall 2021 are not in our archive.
- Johns Hopkins University admitted 6.1% of first-year applicants for fall 2025 (3,072 of 50,259), the lowest in the five years shown, down from 6.4% for fall 2024. It was 7.5% for fall 2021. Most of the drop came in one year, from 7.5% for fall 2023 to 6.4% for fall 2024, when applications rose from 38,893 to 45,895 and admits went from 2,923 to 2,954.
- Northwestern University admitted 7.7% of first-year applicants for fall 2024 (3,806 of 49,474), up from 7.2% for fall 2023 and fall 2022, the lowest in the six years with figures. The high was 9.3%, for fall 2020. It was 8.5% for fall 2018. Applications fell 4.4% for fall 2024, to 49,474 from 51,769. Usable figures for fall 2021 are not in our archive.
- Emory University admitted 10.3% of first-year applicants for fall 2024 (3,562 of 34,614), the lowest in the six years with figures, down from 18.5% for fall 2018. Applications rose from 27,559 to 34,614 over that span. Usable figures for fall 2020 are not in our archive.
- Rice University admitted 8.0% of first-year applicants for fall 2024 (2,597 of 32,473), up from 7.9% for fall 2023, the lowest in the six years with figures. It was 11.1% for fall 2018. Applications rose from 20,923 to 32,473 over that span. Usable figures for fall 2020 are not in our archive.
- University of Notre Dame admitted 9.4% of first-year applicants for fall 2025 (3,320 of 35,401), the lowest in the seven years with figures, down from 11.3% for fall 2024. It was 17.7% for fall 2018. Applications rose from 20,371 to 35,401 over that span. Usable figures for fall 2021 are not in our archive.
- Georgetown University admitted 13.5% of first-year applicants for fall 2025 (3,618 of 26,822), up from 12.9% for fall 2024 and from a low of 12.0% for fall 2021. The high was 16.8%, for fall 2020. It was 14.5% for fall 2018. Applications rose 2.6% for fall 2025, to 26,822 from 26,131; the most in the years shown was 27,506, for fall 2021.
- New York University admitted 9.1% of first-year applicants for fall 2025 (10,340 of 114,125), the lowest in the six years with figures, down from 9.2% for fall 2024. It was 20.0% for fall 2018. Applications rose from 71,834 to 114,125 over that span. Usable figures for fall 2021 and fall 2023 are not in our archive.
- Bowdoin College admitted 6.8% of first-year applicants for fall 2025 (957 of 14,045), the lowest in the six years shown, down from 7.1% for fall 2024. It was 9.2% for fall 2020. Applications rose 5.9% for fall 2025, to 14,045 from 13,265; the fewest in the years shown was 9,325, for fall 2021.
- Amherst College admitted 9.0% of first-year applicants for fall 2024 (1,238 of 13,743), down from 9.8% for fall 2023. The low was 7.3%, for fall 2022. It was 11.3% for fall 2019. Applications rose 8.0% for fall 2024, to 13,743 from 12,727; the most in the years with figures was 14,864, for fall 2022. No report for fall 2020 is in our archive.
- Hamilton College admitted 13.6% of first-year applicants for fall 2024 (1,162 of 8,531), up from 11.8% for fall 2023 and fall 2022, the lowest in the six years shown. The high was 18.4%, for fall 2020. It was 16.4% for fall 2019. Applications fell 11.5% for fall 2024, to 8,531 from 9,643; the most in the years shown was 9,899, for fall 2022.
- University of Richmond admitted 22.2% of first-year applicants for fall 2024 (3,585 of 16,152), the lowest in the seven years shown, down from 23.3% for fall 2023. It was 30.2% for fall 2018. Applications rose from 11,882 to 16,152 over that span.
- Bates College admitted 14.8% of first-year applicants for fall 2025 (1,433 of 9,660), up from 13.3% for fall 2024 and from 13.0% for fall 2023, the lowest since fall 2019 (12.1%). It was 17.8% for fall 2018. Applications fell 3.7% for fall 2025, to 9,660 from 10,027.

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
