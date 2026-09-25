# Wave 7 copy deck — per-school early-decision pages (PRD 031 M3)

Route: `/schools/{id}/early-decision`. Allowlist = sitemap. Indexed
(`EARLY_DECISION_INDEXABLE` in `web/src/lib/early-decision-pilot.ts`).

**Persona.** Someone who searched `{school} early decision acceptance rate`.
The overall first-year rate stays on `/acceptance-rate`.

**Rules.** Product layer (VOICE.md). Answer first, then the history. No
"odds"/"chances", no early action (CDS C22 has no counts), no advice. Every
sentence is generated from usable C21 years (`early-decision-copy.ts`).

**Precision.** One decimal, same as the acceptance-rate page.

**Year labels.** Fall of the entering class. Chart axis: "’18 … ’25".

---

## Allowlist (first three)

Distinctive names first. Harvard, Princeton, Yale, and Stanford are
REA/SCEA — skipped. Dartmouth (2 C21 years), Vanderbilt (0), and Cornell
(1) do not yet meet the three-year bar plus a school-written C21 details
note.

| School | Years | Latest | Own note |
| --- | --- | --- | --- |
| Bowdoin | 2025-26, 2024-25, 2022-23, 2021-22, 2020-21 | 14.9% fall 2025 | Binding-plan paragraph, 2023–24 report |
| Rice | 2024-25, 2023-24, 2022-23, 2021-22, 2018-19 | 16.8% fall 2024 | Binding-plan paragraph, 2019–20 report |
| Lafayette | 2025-26, 2024-25, 2023-24, 2018-19 | 38.0% fall 2025 | ED deadline note, 2024–25 report |

Older C21 counts that the cleaner left unmapped are read from the extract
markdown next to the printed labels. Date parts (month/day) are never
treated as counts. Stock / URL-only / question-stem "notes" are not shown
and do not admit a school to the allowlist.

---

## Templates

**Title** (≤ 65): `{school} Early Decision Rate: {rate} for Fall {latest}`;
names too long fall back to `{school} Early Decision by Year`.

**Meta description** (≤ 155): "{school} admitted {rate} of early-decision
applicants for fall {latest}." plus how far back the figures go.

**Breadcrumb:** SCHOOLS / {SCHOOL} / EARLY DECISION · **Kicker:** Early
decision · **H1:** {school} *early decision acceptance rate*.

**Lead.** Same machinery as acceptance-rate, with "early-decision
applicants" in place of "first-year applicants". At most five sentences,
none over 35 words, 75 words in all. The overall first-year rate is not
on this page.

**Chart** (four or more ED years): one ink colour. Caption: "Share of
early-decision applicants admitted, by fall entering class."

**Table:** year, rate, applied, admitted, source. Gaps named. The school's
own C21 details note sits under the table, attributed to the year it came
from.

**Related:** hub, acceptance-rate, latest year page.

---

## Open for Anthony

Dartmouth, Vanderbilt, and Cornell stay off until they have three usable
C21 years and a school-written details note. Brown, Northwestern, Bates,
and Davidson have the years but not a real note.
