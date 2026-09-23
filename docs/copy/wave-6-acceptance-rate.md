# Wave 6 copy deck — per-school acceptance-rate pages (PRD 031 M2)

Read this as a parent, then as a counselor, then as IR. **Not signed yet.**

Route: `/schools/{id}/acceptance-rate`. Pilot only: 20 allowlisted schools,
`noindex`, not in the sitemap until the M1 slug decision
(`ACCEPTANCE_PILOT_INDEXABLE` in `web/src/lib/acceptance-pilot.ts`).

**Persona.** Primary: parents and students who searched
`{school} acceptance rate`. Secondary: counselors who want the trend in one
shareable URL instead of five PDFs.

**Protocol (VOICE.md).** Benefit → what's on the page → what the number is →
one source line → the trail. Product layer: no field IDs in the lead, no
process words (extracted, parsed, projection), no advice, no prestige
adjectives, no "odds" or "chances" anywhere. Every sentence is generated
from years whose numbers passed the checks; a year that fails is left out
and named. Nothing is estimated.

Percent style matches the site: one decimal under 10%, whole numbers
otherwise (5.7%, 55%).

---

## Templates

**Title (`<title>`)**

> {school} Acceptance Rate by Year, {first year start}–{last year start}

The span is the first and last *usable* year, never the archive's range.
A school with usable years 2021-22 to 2025-26 reads "2021–2025".

**Meta description**

> {span sentence} In {latest year}, {admitted} of {applied} applicants were
> admitted ({rate}), with the original files.

**Breadcrumb:** SCHOOLS / {SCHOOL} / ACCEPTANCE RATE

**Eyebrow (meta):** § C1 · First-year admissions

**H1:** {school} *acceptance rate* (second clause italic, per the design
system's serif-with-italic-accent headline).

**Lead** (up to three generated sentences, one paragraph):

1. Span: "{school}’s reports from {first year} to {last year} show the
   acceptance rate going from {first rate} to {last rate}."
   If both round to the same share: "…show an acceptance rate of {rate} in
   both years."
2. Applications: "Over the same years, first-year applications went from
   {first applied} to {last applied}."
3. Gaps (only when a year between the first and last is missing): "There is
   no usable report for {year}[, {year}, or {year}], so that year is / those
   years are left out."

The hub keeps its single-year sentence; this page leads with the span so the
two URLs don't say the same thing.

**Chart** (small column chart, decoration for the table, `aria-hidden`
bars with a visible caption):

> Acceptance rate by report year. Bars start at zero.

Missing years render as an empty slot labeled "no data".

**Table caption (visually hidden, read by screen readers):**

> {school} first-year applicants, admits, acceptance rate, enrolled, and
> yield by report year, newest first.

Columns: Report year (with "fall {yyyy}" beneath) · Applied · Admitted ·
Acceptance rate · Enrolled · Yield · Original file.

- Report year links to the year page.
- Original file links to the school's file: "PDF", "XLSX".
- Missing years get a row: "—" in each number cell and, in the file cell,
  "Report on file" (linked to the year page) or "No report on file".
- On phones the table scrolls sideways; the scroll region is labeled
  "{school} acceptance rate table, scrolls sideways".

**Definition note (meta style, under the table):**

> From each year’s Common Data Set, section C1: first-time, first-year,
> degree-seeking applicants and admits.

**Method lines (small, under the note):**

- Acceptance rate is admitted ÷ applied. Yield is enrolled ÷ admitted.
- Each report covers the class that entered that fall: the 2024-25 report
  counts students who applied to start in fall 2024.
- Numbers are as the school reported them. A dash means that count isn’t
  shown for the year because it could not be read in full from the report.

**Related:**

> More on {school}: [the school page](/schools/{id}) · [the {latest year}
> report](/schools/{id}/{latest year})

**Hub link.** In the hub's existing sentence "…an acceptance rate of 8.4%."
the words *acceptance rate* link here, only when this page is served. The
sentence is otherwise unchanged.

**Degraded state** (a URL that was submitted in a sitemap and later lost a
year; never a silent 404):

> Some years that used to appear here are no longer shown. The table lists
> the years we can still stand behind.

---

## Filled examples (production data, 2026-09-23)

### Virginia Tech

- **Title:** Virginia Tech Acceptance Rate by Year, 2023–2025
- **Description:** Virginia Tech’s reports from 2023-24 to 2025-26 show the
  acceptance rate going from 57% to 55%. In 2025-26, 31,515 of 57,755
  applicants were admitted (55%), with the original files.
- **H1:** Virginia Tech *acceptance rate*
- **Lead:** Virginia Tech’s reports from 2023-24 to 2025-26 show the
  acceptance rate going from 57% to 55%. Over the same years, first-year
  applications went from 47,207 to 57,755.

| Report year | Applied | Admitted | Rate | Enrolled | Yield |
|---|---:|---:|---:|---:|---:|
| 2025-26 (fall 2025) | 57,755 | 31,515 | 55% | 7,133 | 23% |
| 2024-25 (fall 2024) | 52,296 | 28,758 | 55% | 7,289 | 25% |
| 2023-24 (fall 2023) | 47,207 | 26,923 | 57% | 7,196 | 27% |

Virginia Tech has XLSX reports back to 2012-13, but their admissions
table can't be read reliably yet, so the page starts at 2023-24 (see the
validation note). Three years is the eligibility floor.

### Duke University

- **Title:** Duke University Acceptance Rate by Year, 2018–2024
- **Description:** Duke University’s reports from 2018-19 to 2024-25 show
  the acceptance rate going from 8.9% to 5.7%. In 2024-25, 2,957 of 51,795
  applicants were admitted (5.7%), with the original files.
- **Lead:** Duke University’s reports from 2018-19 to 2024-25 show the
  acceptance rate going from 8.9% to 5.7%. Over the same years, first-year
  applications went from 35,767 to 51,795. There is no usable report for
  2021-22 or 2022-23, so those years are left out.

| Report year | Applied | Admitted | Rate | Enrolled | Yield |
|---|---:|---:|---:|---:|---:|
| 2024-25 | 51,795 | 2,957 | 5.7% | 1,740 | 59% |
| 2023-24 | 46,366 | 3,145 | 6.8% | — | — |
| 2022-23 | — | — | — | — | — (no report on file) |
| 2021-22 | — | — | — | — | — (report on file) |
| 2020-21 | 39,603 | 3,085 | 7.8% | 1,584 | 51% |
| 2019-20 | 41,471 | 3,190 | 7.7% | 1,730 | 54% |
| 2018-19 | 35,767 | 3,189 | 8.9% | 1,745 | 55% |

### Brown University

- **Title:** Brown University Acceptance Rate by Year, 2018–2025
- **Description:** Brown University’s reports from 2018-19 to 2025-26 show
  the acceptance rate going from 7.7% to 6.3%. In 2025-26, 2,710 of 42,774
  applicants were admitted (6.3%), with the original files.
- **Lead:** Brown University’s reports from 2018-19 to 2025-26 show the
  acceptance rate going from 7.7% to 6.3%. Over the same years, first-year
  applications went from 35,437 to 42,774.

| Report year | Applied | Admitted | Rate | Enrolled | Yield |
|---|---:|---:|---:|---:|---:|
| 2025-26 | 42,774 | 2,710 | 6.3% | 1,719 | 63% |
| 2024-25 | 48,904 | 2,638 | 5.4% | 1,719 | 65% |
| 2023-24 | 51,316 | 2,686 | 5.2% | 1,695 | 63% |
| 2022-23 | 50,649 | 2,562 | 5.1% | 1,717 | 67% |
| 2021-22 | 46,568 | 2,568 | 5.5% | 1,705 | 66% |
| 2020-21 | 36,793 | 2,822 | 7.7% | 1,751 | 62% |
| 2019-20 | 38,674 | 2,733 | 7.1% | 1,662 | 61% |
| 2018-19 | 35,437 | 2,718 | 7.7% | 1,652 | 61% |

(Brown's 2024-25 and 2025-26 reports both list 1,719 enrolled; each matches
its own file.)

---

## Words we don't use here

odds, chances, admit odds, "chance me", "how to get in", prestigious, elite,
selective / most selective, top, best, easy / hard to get into, extracted,
parsed, projection. Tested in `acceptance-rate-copy.test.ts` against the
shared `BANNED_LEAD_WORDS` plus this page's additions.

## Open for Anthony

1. The applications sentence is new relative to the PRD's lead (which was
   the span alone). It explains why a rate falls; drop it if it reads as
   editorializing.
2. "There is no usable report for…" is the PRD's phrase. "Usable" is honest
   but a little internal; alternative: "We don't have numbers we can check
   for…".
3. Chart: the PRD said no chart in the pilot. This one is small, starts at
   zero, and repeats the table. Keep or cut.
