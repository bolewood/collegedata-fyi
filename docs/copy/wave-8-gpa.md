# Wave 8 copy deck — per-school GPA pages (PRD 031 M3 / #195)

Route: `/schools/{id}/gpa`. Allowlist = sitemap. Indexed
(`GPA_INDEXABLE` in `web/src/lib/gpa-pilot.ts`).

**Persona.** Someone who searched `{school} average gpa` or `{school} gpa
requirements`. The honest answer is the enrolled first-year distribution
from CDS C11, plus the C12 average when the school printed one. This is
not a cutoff.

**Rules.** Product layer (VOICE.md). Answer first, then the history. No
"cutoff," "minimum," or "odds." No advice about "the GPA you need." If the
school did not print an average, show the bands only. Every sentence is
generated from usable C11 years (`gpa-copy.ts`).

**Precision.** GPA averages to two decimals (3.86). Band shares one
decimal, same as the acceptance-rate page (74.2%).

**Year labels.** Fall of the entering class. Chart axis: "’18 … ’25".

---

## Allowlist (first three)

Distinctive names first. A year counts when C11 bands sum to about 100
(all-enrolled column when present; otherwise the single reported table).
C12 average is optional. ≥3 usable years, latest 2023–24 or newer.
Searchable public slug.

| School | Years | Latest | Average printed |
| --- | --- | --- | --- |
| Harvard | 2025-26, 2024-25, 2022-23, 2021-22, 2019-20 | 4.22 fall 2025; 74.7% at 4.0 | Yes |
| Princeton | 2025-26, 2024-25, 2023-24, 2022-23, 2021-22, 2020-21 | 3.96 fall 2025; 72.0% at 4.0 | Yes |
| Stanford | 2025-26, 2024-25, 2022-23, 2021-22, 2020-21, 2019-20 | 3.94 fall 2025; 73.0% at 4.0 | Yes |

Yale left C11 blank in every year we have. Dartmouth, Cornell, Duke, and
Brown have no usable C11 years yet. Vanderbilt has two. Northwestern's
three years have no printed average and a 0% 4.0 band — held for a
source-check, not this first three.

---

## Templates

**Title** (≤ 65): `{school} Average GPA: {avg} for Fall {latest}` when an
average is printed; otherwise `{school} GPA: {share} at 4.0 for Fall
{latest}`. Names too long fall back to `{school} First-Year GPA by Year`.

**Meta description** (≤ 155): answer sentence plus how far back the
figures go. Never "requirements," "cutoff," or "minimum."

**Breadcrumb:** SCHOOLS / {SCHOOL} / GPA · **Kicker:** High school GPA ·
**H1:** {school} *enrolled first-year GPA*.

**Lead.** At most five sentences, none over 35 words, 75 words in all.
The first sentence names C11: enrolled first-years who reported a GPA.
If an average is printed, lead with it. If not, lead with the 4.0 band
share. Never invent a cutoff.

**Chart** (four or more years): average GPA when the school printed one
in those years; otherwise the 4.0 band share. Caption names which.

**Table:** year, average, 4.0, 3.75–3.99, 3.50–3.74, reported, source.
Gaps named. Missing averages print as —.

**Related:** hub, acceptance-rate, latest year page.

**Hub.** Link the word "GPA" only when this page is served.

---

## Open for Anthony

Yale left C11 blank in every year we have. Dartmouth, Cornell, Duke, and
Brown have no usable C11 years yet. Vanderbilt has two. Northwestern's
three years have no printed average and a 0% 4.0 band — held for a
source-check, not this first three. SAT/ACT is #196. Do not advise what
GPA a student "needs."
