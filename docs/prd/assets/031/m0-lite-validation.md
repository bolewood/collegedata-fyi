# PRD 031 M0-lite — acceptance history validation

Operator doc. 2026-09-23, production data (read-only, anon key). Code:
`web/src/lib/acceptance-history.ts`, `web/src/lib/c1-headline-totals.ts`
(`readC1Totals`). Measurement: `web/src/lib/acceptance-history.measure.test.ts`
(opt-in, `ACCEPTANCE_MEASURE=live|survey`). Source check:
`scratch/prd-031/verify_sources.py` (gitignored; downloads each original file
from public storage and compares C1 lines).

## What the page reads

For a canonical school id: `fetchSchoolDocuments` rows that are extracted,
whole-institution, canonical academic year, **2018-19 or later**, and not
`wrong_file` / `blank_template` / `low_coverage`. Each row's extract goes
through `readC1Totals`. **The school's printed C1 counts (the validated
extract reading) are the source of truth.** From 2024-25 on, a sane
`school_browser_rows` row is used only when the extract can't be read, and
fills an enrolled count the extract lacks.

### Extract vs projection disagreements (all 20 pilot schools, 2024-25+)

| School-year | Printed (shown) | Projection | Note |
|---|---:|---:|---|
| Amherst 2024-25 applicants | 13,743 | 13,742 | The file prints a 13,743 total; its sex rows add to 13,742. The page shows the printed total; the hub sentence (projection) still says 13,742. |

No other applied, admitted, or enrolled value differs across the 20
schools. (Outside the pilot: Stanford, UCLA, UW-Madison, and Wake Forest
2024-25 also differ; see the fixture test.)

A year is usable when applied > 0, 0 < admitted ≤ applied, and enrolled
(if shown) ≤ admitted. Enrolled that fails its own checks is shown as "—"
rather than dropping the year.

## Mapping findings (the PRD 014 risk was real)

The artifact's `schema_version` plus producer decides the C1 numbering.
Corpus survey of 5,074 extracted whole-institution documents:

| Producer / schema_version | Docs | Numbering actually used | Decision |
|---|---:|---|---|
| tier4_docling, **none** | 2,903 | 2025-26 ids (Tier 4 label map is hard-coded) | read as 2025-26 |
| tier4_docling, 2025-26 (pre-2024 years) | 974 | 2025-26 | read as 2025-26 |
| tier4_docling / tier1 / tier2, 2024-25 | 472 | 2024-25 | read as 2024-25 |
| tier4_docling / tier1 / tier2, 2023-24 | 88 | 2023-24 (2024-25 minus unknown-gender rows) | **new spec** |
| tier1_xlsx, 2025-26, year < 2024 | 320 | 2025-26 *cell map* on an older layout: garbage | **excluded** |
| tier2_acroform, 2025-26, year < 2024 | 50 | coherent (totals = sums) | read as 2025-26 |
| tier6_html, none | 3 | 2025-26 | read as 2025-26 |

Bugs found and fixed (all also affected live year pages, which now read
through the same `readC1Totals`):

1. **Men-only counts on older year pages.** With no `schema_version`, the old
   default spec treated C.101 (men) as the total; whenever men ≥ women it
   returned men only. 305 of 2,584 older Tier 4 docs showed wrong applicant
   or admit counts (Colorado School of Mines 2018-19: 8,726 shown, 12,661 in
   the file).
2. **Older XLSX files** (e.g. Virginia Tech 2012-13 to 2022-23, NYU 2021-22,
   Northeastern 2018-20) were read with the 2025-26 cell map; values like VT
   2021-22 "12.6%" (real: ~57%) passed the bounds. Excluded; year pages no
   longer show C1 stats for them.
3. **Third sex category dropped.** The label map misses "of another gender"
   and "other/unknown", so men + women sums undercount (UCLA 2022-23: 144,233
   applicants shown vs 149,815 in the file; rate 8.7% vs 8.4%). Now recovered
   from the extract's markdown C1 rows; without markdown, a sum with no
   third-category cell is not shown (AcroForm `NON_BINARY` fields, e.g. Wake
   Forest and UW-Madison 2024-25).
4. **Part-time first-years dropped** on templates that print only full-time
   and part-time enrolled rows (C.107/C.108 hold full-time). Part-time is now
   added back; when the markdown lost one part-time row (Georgetown 2018-19,
   NYU 2019-20), enrolled is withheld.
5. **In-state row read as the total** (UC Riverside 2023-24: 48,180 in-state
   vs 55,750 total). Fixed in `preferCoherentTotal`.
6. **One sex missing / one column read twice** (UT Austin 2018-19 showed
   75.9%; Wellesley 2019-20 and 2021-22 doubled). Such sums are dropped.

Note: `school_browser_rows` disagrees with the extract for Stanford 2024-25
(projection empty), UW-Madison and Wake Forest 2024-25 (projection zeros),
UCLA 2024-25 (no enrolled), Amherst 2024-25 (13,742 vs the school's printed
13,743). These are projection issues for PRD 014 follow-up; the page uses
the projection when sane, else the extract.

## Source-file check

168 school-years (the 20 pilot schools plus 9 candidates) were compared
with the school's own file: 154 matched automatically (the number printed,
or the exact sum of the sex rows), and the other 14 were reconciled by hand:
decimal residency tables (Emory, Amherst, UW-Madison 2023-24), fillable
forms with no text layer (read via form fields), and multi-column layouts
(NYU 2022-23).

Known source inconsistency: Virginia Tech 2023-24 prints 47,207 in its
residency table while its sex rows add to 47,208. The page shows the
school's printed total.

The 2024-25+ comparison is checked in as a fixture
(`web/src/lib/__fixtures__/acceptance-2024-plus.json`): 42 of 45 extract
readings equal `school_browser_rows` exactly; the three differences are the
documented ones above.

## Allowlist and usable years

Named five, plus 15 high-profile schools with ≥ 4 usable, source-checked
years. Split-slug pairs waiting on M1 (Georgia Tech, Tulane, UChicago,
Caltech, Rutgers, Texas A&M, UVA, UW) are left out. Wellesley and Dartmouth
fall to 3 usable years; Stanford (4, with 2020-21 to 2023-24 missing),
UT Austin, UW-Madison, and Lafayette are alternates.

| School | Canonical id | Usable | Span | Gaps named | Auto-matched | Enrolled "—" |
|---|---|---:|---|---|---:|---:|
| Virginia Tech | `virginia-polytechnic-institute-and-state-university` | 3 | 2023-24–2025-26 | — | 2/3 | 0 |
| Haverford College | `haverford-college` | 8 | 2018-19–2025-26 | — | 8/8 | 3 |
| Brown University | `brown` | 8 | 2018-19–2025-26 | — | 8/8 | 0 |
| Northeastern University | `northeastern` | 5 | 2020-21–2024-25 | — | 5/5 | 1 |
| Duke University | `duke` | 5 | 2018-19–2024-25 | 2021-22, 2022-23 | 5/5 | 1 |
| University of Pennsylvania | `upenn` | 7 | 2018-19–2024-25 | — | 7/7 | 0 |
| Harvard University | `harvard` | 7 | 2018-19–2025-26 | 2020-21 | 6/7 | 4 |
| Princeton University | `princeton` | 5 | 2018-19–2025-26 | 2019-20 to 2021-22 | 5/5 | 0 |
| Johns Hopkins University | `johns-hopkins` | 5 | 2021-22–2025-26 | — | 5/5 | 0 |
| Northwestern University | `northwestern` | 6 | 2018-19–2024-25 | 2021-22 | 6/6 | 0 |
| Emory University | `emory` | 6 | 2018-19–2024-25 | 2020-21 | 5/6 | 1 |
| Rice University | `rice` | 6 | 2018-19–2024-25 | 2020-21 | 6/6 | 0 |
| University of Notre Dame | `university-of-notre-dame` | 7 | 2018-19–2025-26 | 2021-22 | 7/7 | 0 |
| Georgetown University | `georgetown` | 8 | 2018-19–2025-26 | — | 7/8 | 1 |
| New York University | `nyu` | 6 | 2018-19–2025-26 | 2021-22, 2023-24 | 6/6 | 1 |
| Bowdoin College | `bowdoin` | 6 | 2020-21–2025-26 | — | 6/6 | 0 |
| Amherst College | `amherst` | 5 | 2019-20–2024-25 | 2020-21 | 4/5 | 2 |
| Hamilton College | `hamilton` | 6 | 2019-20–2024-25 | — | 6/6 | 2 |
| University of Richmond | `university-of-richmond` | 7 | 2018-19–2024-25 | — | 4/7 | 2 |
| Bates College | `bates` | 8 | 2018-19–2025-26 | — | 8/8 | 2 |

"Auto-matched" below the year count means the rest were reconciled by hand
(see above). Every published applicant and admit count matches its file.

Adjacent-year changes > 2× (PRD 031's change-intelligence candidates):
Northeastern 2021-22 → 2022-23, admits 13,829 → 6,191 and rate 18% → 6.8%.
Both years match the files; this is the real drop the PRD cites. Not
written to the PRD 019 queue (no production writes in this change).

## Corpus-wide yield (for the M0 go/no-go)

Before the completeness guards and the 2018-19 floor, the survey found 348
schools with ≥ 3 usable years (latest ≥ 2023-24), 300 with ≥ 4, and 237
with ≥ 5 (raw slugs, aliases not folded). The final rules need each
document's markdown, which the survey did not pull, so the real count is
lower. Re-run `ACCEPTANCE_MEASURE=survey` against a markdown-aware survey
before the M0 go/no-go (threshold: 150 schools with ≥ 4).

### One number everywhere, gated for non-pilot hubs

Hub summary and meta, year-page summary and key stats, and the stat page
read one decision per school-year (`gatedYearFacts` →
`web/src/lib/c1-hub-gate.ts`). Pilot schools take the printed totals.
Elsewhere a changed number must be corroborated before it replaces what
production showed:

- Sanity (all): applied ≥ 50, 0 < admitted ≤ applied, enrolled ≤ admitted;
  applied = admitted only with IPEDS open admission.
- Tiny change (both counts within max(5, 0.1%)): accept.
- IPEDS for the same fall (ADM2024 = fall 2024 = 2024-25 reports): both
  counts within ±10%. IPEDS one fall older (2025-26 reports): rate within
  ±10 points and applied within ±35%. If both values pass, keep the one
  closer to IPEDS applicants (so a hub never moves away from the federal
  count it matched — Arkansas). Resolver fails, projection passes: keep the
  projection. Neither: suppress.
- No IPEDS: accept only if the projection is missing or broken (admitted >
  applied, or applied < 25% of the resolver's); keep a projection within
  2%; otherwise suppress. A sane projection is never replaced by a value
  more than 2% lower without IPEDS.
- IPEDS administrative units (system / central offices; checked-in list
  `web/src/data/ipeds-administrative-units.json` from the HD2024 snapshot,
  plus sector / degree-granting facts): no C1 figures on hub, year page,
  or stat page. University of Houston System Administration (229407) was
  showing UH's report.

Audit (463 non-pilot hubs, latest projected row; survey extract values, so
approximate; per-school report `scratch/prd-031/round-8/hub-gate-report.json`):

| Outcome | Hubs |
|---|---:|
| Keep the value production shows | 375 |
| New value, corroborated (or tiny change) | 32 |
| Suppressed, production showed a figure | 7 |
| Suppressed, production showed none already | 49 |

| Reason code | Hubs |
|---|---:|
| `unchanged` | 355 |
| `no_resolver_suppress` | 45 |
| `ipeds_accept_resolver` | 26 |
| `no_resolver_keep_projection` | 17 |
| `ipeds_suppress` | 9 |
| `tiny_adjustment` | 6 |
| `ipeds_keep_projection_closer` | 2 |
| `no_ipeds_suppress` | 1 |
| `administrative_unit` | 1 |
| `ipeds_keep_projection` | 1 |

Suppressed where production showed a figure (all fail IPEDS or identity):

| School | Year | Production (applied / admitted) | Reason | IPEDS fall: applied / admitted |
|---|---|---:|---|---|
| wichita-state-university | 2025-26 | 4,784 / 3,361 | ipeds_suppress | 2024: 9,916 / 9,316 |
| university-of-wisconsin-green-bay | 2025-26 | 7,755 / 5,914 | ipeds_suppress | 2024: 5,899 / 5,226 |
| pratt-institute-main | 2025-26 | 1,890 / 1,375 | ipeds_suppress | 2024: 8,457 / 6,195 |
| louisiana-tech-university | 2025-26 | 2,343 / 1,292 | ipeds_suppress | 2024: 8,491 / 7,336 |
| samford-university | 2024-25 | 159 / 39 | ipeds_suppress | 2024: 4,559 / 3,755 |
| lake-superior-state-university | 2024-25 | 2,146 / 2,106 | ipeds_suppress | 2023: 2,473 / 1,682 |
| university-of-houston-system-administration | 2025-26 | 28,115 / 21,788 | administrative_unit | —: — / — |

Tests: `c1-hub-gate.test.ts` (Lake Superior State suppressed, WashU
repaired, Fitchburg keeps its IPEDS-matching projection, Arkansas keeps the
projection closer to IPEDS, UH System Administration shows nothing);
`tests/acceptance-rate-consistency.spec.ts` (20 pilots across hub, meta,
year page, stat page; 7 gated non-pilot hubs against their year pages).

### Schools mirroring another school's counts (report only)

Same applied and admitted for the same year under different slugs. Alias
pairs awaiting M1 are expected; branch campuses and unrelated pairs need an
identity decision (not changed here):

- 2024-25: worcester-polytechnic-institute, whitman-college (7,243 / 2,763)
- 2024-25: barnard, bard-college (11,836 / 1,046)
- 2024-25: california-institute-of-technology, caltech (13,856 / 356)
- 2024-25: fairleigh-dickinson-university-metropolitan-campus, fairleigh-dickinson-university-florham-campus (11,478 / 10,665)
- 2025-26: old-dominion-university, eastern-virginia-medical-school (15,024 / 13,725)
- 2025-26: georgia-institute-of-technology-main-campus, georgia-tech (66,881 / 8,921)
- 2025-26: university-of-washington-bothell-campus, uw, university-of-washington-tacoma-campus (72,933 / 30,446)
- 2024-25: tulane-university-of-louisiana, tulane-university (32,609 / 4,559)
- 2024-25: university-of-south-carolina-columbia, university-of-south-carolina-aiken (52,703 / 31,701)
- 2024-25: miami-university-oxford, miami-university-middletown, miami-university-hamilton (39,580 / 29,843)
- 2024-25: springfield-college, springfield-college-regional-online-and-continuing-education (3,284 / 2,361)
- 2024-25: uchicago, university-of-chicago (43,612 / 1,955)
- 2024-25: virginia-polytechnic-institute-and-state-university, virginia-tech (52,296 / 28,758)
- 2024-25: georgia-tech, georgia-institute-of-technology-main-campus (59,789 / 8,413)
- 2024-25: uw, university-of-washington-bothell-campus (69,166 / 27,076)
- 2025-26: tulane-university, tulane-university-of-louisiana (32,942 / 4,763)
- 2024-25: northeastern, northeastern-university-professional-programs (98,425 / 5,133)
- 2024-25: university-of-washington-tacoma-campus, university-of-washington-seattle-campus (4,068 / 3,357)
- 2025-26: texas-a-and-m-university-college-station, texas-am (62,967 / 32,531)
- 2025-26: university-of-houston, university-of-houston-system-administration (28,115 / 21,788)

## Johns Hopkins before 2021-22

The hub serves five Johns Hopkins reports (2021-22 to 2025-26); earlier
years are not in the archive, so this is a discovery gap, not unusable
counts. (Withdrawn/removed manifest rows were not queried.) Worth a finder
pass before the page is indexed.

## Not done here

- The durable fix is in the Tier 4 cleaner's label map ("of another
  gender", "other/unknown", part-time rows) plus a re-drain, then the
  Python projection below 2024-25 (PRD 031 M0 proper). This TypeScript
  layer is the read-side stopgap.
- Years before 2018-19 are not shown; their templates were not checked.

## Wave 2 (#191) — 2026-09-24

Live measurement (`ACCEPTANCE_MEASURE=live ACCEPTANCE_ONLY_EXTRA=1`) against
production. Bar unchanged: ≥ 3 usable C1 years, latest 2023-24 or newer.

Shipped (searchable ids): `uw-madison`, `uf`, `uc-santa-barbara`,
`stanford`, `ucla`, `unc`, `usc`, plus backups `ut-austin`,
`wellesley-college`, `lafayette-college`.

Dropped (fewer than 3 usable years): WashU (`washington-university-in-st-louis`,
2), UW (`uw`, 2), UMich (`umich`, 2). UW also still mirrors
Bothell/Tacoma counts in some years (identity follow-up, not this page).

Stanford, UW-Madison, UCLA, UT Austin, Wellesley, and Lafayette were in the
M0-lite 168-year source check (Stanford/UCLA 2024-25 extract-vs-projection
disagreements remain as documented above). UF, UCSB, UNC, and USC years
were checked against the public source files (pdftotext of the archived
PDF). Applicant and admit counts match the printed total or the exact sum
of the sex rows, except:

- UCSB 2021-22 prints degree-seeking totals 105,647 / 30,823 and
  men+women rows 45,516 / 57,658 applied and 11,709 / 18,330 admitted
  (103,174 / 30,039). The page shows the sex-row sum, same as the year
  page — the third-category rows are missing from the extract.
- UCLA 2024-25 has no text layer and no AcroForm fields; applied /
  admitted match `school_browser_rows` (146,276 / 13,114). Enrolled is
  the documented extract-vs-projection disagreement.

## Wave 3 (#189) — 2026-09-24

Live measurement against production. Same bar: ≥ 3 usable C1 years,
latest 2023-24 or newer.

Shipped: `georgia-tech`, `caltech`, `uchicago`,
`rutgers`, `texas-am`, plus leftover `yale`.

Dropped: UVA (`uva`, 2 years). Cornell, Columbia, and Vanderbilt also had
only 2 usable years; MIT had 3 (latest 2023-24) but the issue asked for
one leftover, and Yale was first in the preference order. Tulane has eight
usable extract years, but the hub still leads with 2024-25 (no
`school_browser_rows` for 2025-26), so it stays off until hub and stat
page agree.

Georgia Tech, Caltech, Tulane, UChicago, Rutgers, and Texas A&M were in
the M0-lite split-slug set waiting on M1. Latest-year applicant and admit
counts were checked against the public source files. Caltech 2024-25,
UChicago 2025-26, and Yale 2025-26 match as the sum of the sex rows
(no printed all-students total in the text layer).



