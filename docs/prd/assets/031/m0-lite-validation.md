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

### One number everywhere (site-wide resolver)

The hub summary and meta description, the year page summary, and the
year page's key stats now read the latest year's C1 counts through the same
printed-total resolver as the acceptance-rate page (`withPrintedTotals` in
`web/src/lib/acceptance-history-data.ts`; cached, at most one extra
artifact read per hub render). `web/tests/acceptance-rate-consistency.spec.ts`
checks all 20 pilot schools: applied, admitted, and rate match on the hub
summary, hub meta, year page, and stat page. (Rice's hub picks its 2025-26
report, which has no usable counts, so the hub states no acceptance figure;
the stat page ends at 2024-25.)

Corpus-wide estimate: of 469 schools' latest projected rows, 47
hub summaries change (17 of them had no projected counts at all). This is a
lower bound: the survey lacks the markdown the reader uses to confirm
sums. Only the pilot rows are source-checked; non-pilot readings where
applied equals admitted (Lake Superior State, Front Range CC) deserve a
look before indexing anything built on them.

| School | Year | Projection (applied / admitted) | Printed |
|---|---|---:|---:|
| southern-connecticut-state-university | 2025-26 | 8,120 / 7,224 | 9,958 / 8,701 |
| front-range-community-college | 2024-25 | — / 6,820 | 6,506 / 6,506 |
| wichita-state-university | 2025-26 | 4,784 / 3,361 | 8,736 / 6,311 |
| university-of-houston | 2025-26 | 28,115 / 21,788 | 34,728 / 26,312 |
| saint-marys-college-of-california | 2024-25 | 4,309 / 3,816 | 4,310 / 3,816 |
| university-of-wisconsin-green-bay | 2025-26 | 7,755 / 5,914 | 8,984 / 6,716 |
| brigham-young-university | 2025-26 | 751 / 8,331 | 12,141 / 8,331 |
| university-of-south-dakota | 2024-25 | — / — | 5,965 / 5,892 |
| university-of-arkansas | 2024-25 | 30,549 / 22,701 | 28,873 / 22,701 |
| pratt-institute-main | 2025-26 | 1,890 / 1,375 | 7,579 / 6,547 |
| the-evergreen-state-college | 2024-25 | — / — | 1,300 / 1,253 |
| west-virginia-university | 2024-25 | — / — | 20,150 / 15,570 |
| louisiana-tech-university | 2025-26 | 2,343 / 1,292 | 6,299 / 4,496 |
| augustana-university | 2025-26 | 776 / 719 | 3,294 / 2,401 |
| loyola-university-chicago | 2025-26 | 362 / 33,009 | 43,954 / 33,009 |
| pacific-university | 2025-26 | 1,028 / 932 | 2,909 / 2,614 |
| samford-university | 2024-25 | 159 / 39 | 7,842 / 6,696 |
| lake-superior-state-university | 2024-25 | 2,146 / 2,106 | 2,106 / 2,106 |
| trinity-college | 2024-25 | — / — | 6,396 / 2,144 |
| rhodes-college | 2025-26 | 936 / 637 | 5,682 / 2,927 |
| university-of-rochester | 2024-25 | 21,384 / 8,569 | 21,384 / 8,570 |
| central-connecticut-state-university | 2025-26 | 8,577 / 7,164 | 10,176 / 8,070 |
| baldwin-wallace-university | 2025-26 | 23 / 7 | 4,406 / 3,410 |
| washington-university-in-st-louis | 2025-26 | 7,830 / 575 | 35,316 / 4,359 |
| hobart-william-smith-colleges | 2024-25 | — / — | 5,904 / 3,778 |
| university-at-buffalo | 2024-25 | 40,856 / 30,308 | 40,855 / 30,307 |
| mount-holyoke-college | 2024-25 | — / — | 5,226 / 1,883 |
| franklin-and-marshall-college | 2024-25 | 9,881 / 2,789 | 9,881 / 2,785 |
| millersville-university-of-pennsylvania | 2024-25 | — / — | 7,662 / 6,604 |
| missouri-university-of-science-and-technology | 2025-26 | 2,966 / 2,585 | 8,330 / 6,550 |
| university-of-north-carolina-at-charlotte | 2025-26 | 18,398 / 15,202 | 27,218 / 21,170 |
| texas-state-university | 2024-25 | — / — | 33,907 / 30,498 |
| saginaw-valley-state-university | 2025-26 | 9,532 / 7,650 | 11,586 / 9,087 |
| washington-college | 2024-25 | — / — | 4,048 / 2,303 |
| gettysburg-college | 2024-25 | — / — | 8,366 / 3,254 |
| southwestern-university | 2024-25 | — / — | 6,313 / 2,718 |
| rose-hulman-institute-of-technology | 2024-25 | — / — | 955 / 658 |
| allegheny-college | 2025-26 | 1,435 / 1,184 | 6,151 / 3,615 |
| rollins-college | 2024-25 | 8,860 / 4,212 | 8,860 / 4,213 |
| troy-university | 2024-25 | — / — | 9,474 / 9,099 |
| university-of-houston-system-administration | 2025-26 | 28,115 / 21,788 | 34,728 / 26,312 |
| amherst | 2024-25 | 13,742 / 1,238 | 13,743 / 1,238 |
| florida-international-university | 2024-25 | — / — | 32,855 / 17,957 |
| scripps-college | 2024-25 | — / — | 3,199 / 1,225 |
| fitchburg-state-university | 2024-25 | 4,582 / 3,983 | 3,831 / 3,404 |
| virginia-commonwealth-university | 2024-25 | — / — | 24,804 / 20,769 |
| north-carolina-central-university | 2024-25 | 18,363 / 15,971 | 18,368 / 15,972 |

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
