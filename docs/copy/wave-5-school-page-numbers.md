# Wave 5 copy deck — the numbers on school and year pages

Read this as a parent, then as a counselor, then as IR. **Not signed yet.**

Why: school and year pages said what a Common Data Set is and where the file
lives, but not what the school reported. People reach these pages from
searches like `{school} acceptance rate` and `{school} common data set 2026`.
The first screen should answer with the school's own numbers, as the school
published them.

Rules carried from `web/VOICE.md`: product layer, benefit first, numbers in
English, no field IDs, no process words, no advice, no prestige adjectives.
Every sentence is generated from the school's reported values; a sentence is
dropped when its numbers are missing or impossible (admits > applicants,
SAT 25th > 75th, flagged files). Nothing is estimated.

---

## School hub lead — new second paragraph

After “The {school} Common Data Set is the yearly report…” (illustrative
numbers; the early decision and year-over-year figures are not Cornell’s):

> In its 2025-26 report, Cornell University says 72,523 first-year students
> applied and 6,077 were admitted, an acceptance rate of 8.4%. 3,827 admitted
> students enrolled (63% yield). Enrolled students who sent scores had a
> middle-50% SAT of 1490–1550 and ACT of 33–35. Early decision: 2,000 of
> 10,000 applicants admitted (20%). Waitlist: 9,720 offered a spot, 6,598
> accepted one, and 254 admitted from it. Compared with 2024-25, applications
> rose 11% (65,612 to 72,523) and the acceptance rate went from 9.2% to 8.4%.

Sentence order: acceptance, yield, test scores, early decision, waitlist,
year-over-year. The year-over-year sentence only appears when the prior year
is the immediately preceding one.

Percent style: one decimal under 10%, whole numbers otherwise (8.4%, 55%).

## Year page lead — new second paragraph

Same sentences for that year, plus “Compared with {prior year}, …” when the
prior year exists.

## School hub — “All years” line

Under the three-report ledger, a small meta line so every year is one click
away (and crawlable):

> ALL YEARS: 2025-26 · 2024-25 · 2023-24 · …

Only shown when the school has more than three years.

## Meta descriptions

School hub, when numbers exist:

> {school} Common Data Set, 2012–2025. 2025-26 report: 55% acceptance rate,
> 57,755 applicants. Download the original file.

Year page, when numbers exist (both year forms, because the template prints
“2025-2026” and people search it):

> {school} Common Data Set 2025-26 (2025-2026): 8.4% acceptance rate, 72,523
> applicants, SAT 1490–1550. The school’s own report, plus the original file
> to download.

Without numbers, the previous descriptions stay (with the long year form on
year pages).

## Not changed

Titles and H1s. PRD 028 protects Virginia Tech’s ranking; titles stay
`{school} Common Data Set` and `{school} Common Data Set {year}`.
