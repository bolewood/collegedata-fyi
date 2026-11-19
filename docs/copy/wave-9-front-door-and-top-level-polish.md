# Wave 9 copy deck — front door and top-level voice polish

**Status:** Signed 2026-11-19 by Anthony and implemented in `web/`.

Read this deck straight through as a parent first, then as a counselor, then as
an institutional researcher. Waves 1–4 stripped operator jargon and caught
factual errors. This pass fixes the second-order habits that crept in along the
way: clipped staccato fragments, identical two-beat italic headings on every
route, defensive disclaimers in sentence one, heavy em-dash reliance, and two
older `/about/*` pages plus one recipe that still read like internal memos.

**Honesty locks kept intact:**
- Homepage opens in plain English, not with three proper nouns.
- Named sources (`Common Data Set`, `IPEDS`, `College Scorecard`) live on About.
- Accuracy is anchored to what the school published, with the original file
  linked; federal figures stay labeled as federal.
- No account, no student profile, not a ranking, no takedown advertising.
- `/browse` stays **Compare**; API stays in the header; GitHub stays off the
  hero.
- No extractor jargon (`Docling`, `AcroForm`, `Tier 4`, `drain`, `browser row`,
  `queryable`).

---

## 1. Homepage (`/`)

**Primary:** parents and students. Counselors and IR see their doors immediately
without steering the hero copy.

### Meta
- **Title:** `collegedata.fyi — Free college data, straight from the source` *(keep)*
- **Description:** `Admissions, test scores, financial aid, and graduate outcomes for U.S. colleges, from each school’s annual report and federal records, with the original file linked.`

### Hero chrome (deduplicated)
Right now the left marginalia (`OPEN DATA / SOURCE LINKS / PUBLIC API`) and the
center kicker (`Free data · source links · federal numbers · public API`) repeat
the same phrases inches apart. Keep the side marginalia and drop the redundant
center kicker so the H1 has room to breathe:

- **Left marginalia:** `§ OPEN DATA` / `SOURCE LINKS` / `PUBLIC API` *(keep)*
- **Right marginalia:** `ADMISSIONS` / `AFFORDABILITY` / `OUTCOMES` *(keep)*
- **Center kicker:** *(remove)*

### Hero H1 + lede
Keep the H1; it is genuinely good and earns the one italic turn on the front
door.

- **H1:** `College data,` *`straight from the source.`* *(keep)*
- **Lede (Newsreader italic):**
  > Admissions, test scores, financial aid, and graduate outcomes for U.S.
  > colleges, pulled from each school’s own annual report and federal records.
  > Every page links directly to the original file.
- **Sub-line (sans):**
  > Search any school, compare numbers side by side, or download the source
  > files for free, with no account required.

*Why this works better than before:* drops the hedged superlative (*"The most
comprehensive free college data we know of"*), replaces the vague phrase
*"the government’s own numbers"* with concrete facts a parent recognizes, and
replaces four choppy fragments (*"Search a school. Compare admissions, cost, and
aid. Open the original file. No account."*) with normal, breathing English.

### Search placeholder + buttons
- **Search placeholder** (`SchoolSearch.tsx`): `Search any U.S. college by name or city…` *(drops `alias`, which is an internal database term)*
- **Buttons:** `Build match list` · `Compare schools` · `Browse all schools` · `API` *(keep)*

### Stat band
All four numbers come from `site_stats` (already fetched on `/`). Rename the
labels so every label is a noun that matches what the number actually counts,
and surface `scorecard_institution_count` in the first note so the homepage
stops quietly underselling federal coverage.

| Field in `site_stats` | Now | Proposed label | Proposed note |
|---|---|---|---|
| `total_schools` | `Schools` / *Latest reports we have on file* | `School reports` | `Colleges with archived reports (plus {scorecard_institution_count} with federal data)` |
| `total_documents` | `Documents` / *School files, 1998–2025* | `Source files` | `Original school reports, {yearRangeValue}` |
| `queryable_field_count` | `Facts` / *You can compare · from current school reports* | `Data points` | `Admissions, cost, and aid fields per report` |
| `browser_primary_row_count` | `Compare` / *Side by side · refreshed {date}* | `Recent reports` | `2024–25 and newer · updated {date}` |

*(Exact live-stat check: `total_schools` = distinct schools with archived CDS
documents; `total_documents` = archived CDS documents; `queryable_field_count` =
comparable CDS fields; `browser_primary_row_count` = primary 2024–25+ reports in
Compare. Every label now matches its underlying query.)*

### Recently added (below the fold)
- **Heading:** `§ Recently added` *(keep)*
- **Caption:** `The latest annual reports added to the archive. Select any school to view the numbers alongside its original file.`

*(Optional layout note for a later pass: consider adding 3–4 clickable example
schools under the search box, such as a flagship public, a selective private,
and a regional university, so first-time parents can see what a school page
looks like in one click instead of facing an empty search box.)*

---

## 2. About (`/about`)

**Primary:** all three audiences, starting with families and counselors.

### Meta
- **Title:** `About` *(keep)*
- **Description:** `We collect colleges’ annual Common Data Set reports alongside federal IPEDS and College Scorecard data, linked to the original files and free with no account.`

### Body
- **H1:** `The` *`Uncommon`* `Data Set` *(keep — brand play, works well here)*
- **Lede:**
  > Most U.S. colleges publish a detailed annual report called the Common Data
  > Set, then tuck it away as a PDF somewhere on their website. We collect
  > those reports alongside federal IPEDS and College Scorecard data so
  > families, counselors, and researchers can look up real numbers in one free,
  > public place.

**What you can do**
- Look up any college and read its latest published report, or its federal data
  when the school hasn’t published a Common Data Set.
- Download the original PDF or spreadsheet the college posted.
- Compare admissions, test scores, tuition, and financial aid across schools.
- Build a college match list in your browser without creating an account or
  saving a student profile on our servers.
- Pull the same underlying dataset for research, journalism, or LLM tools
  through the [public API](/api).

**How this is different**
> Commercial college-search sites can be helpful, though many require an
> account, hide where a figure came from, or build a student profile along the
> way. Here, each school’s own report sits next to federal data, every figure
> links back to its source, and nothing sits behind a login or paywall.

**The three data sources**
- [Common Data Set](/about/common-data-set): the annual report colleges
  publish on admissions, enrollment, cost, and financial aid.
- [College Scorecard](/about/college-scorecard): federal figures on net price,
  student debt, and post-college earnings.
- [IPEDS](/about/ipeds): the federal statistical baseline filed each year by
  U.S. colleges that receive federal student aid.

**Open source**
> Our code, schema, and archived files are open source under the MIT license on
> [GitHub](https://github.com/bolewood/collegedata-fyi), and the full dataset is
> available through the [public API](/api). If you’re curious how files are
> parsed or want to check known data quirks, GitHub is the best place to look.
> *(Keep conditional `/usage` link: `You can also see how the archive is used on the [usage page](/usage).`)*

**Credits** & **Project Sponsors** — keep as-is.
**Closing italic line** (*"Better college decisions start with better access to the facts."*): **delete.** The page ends cleaner without a tagline.

---

## 3. Common Data Set explainer (`/about/common-data-set`)

Mostly strong already; just smooth out the staccato spots.

### Meta
- **Title:** `What is the Common Data Set` *(keep)*
- **Description:** `The Common Data Set is the annual report U.S. colleges publish on admissions, enrollment, cost, and financial aid. Here is what it covers and how to use it.`

### Lede
> Every year, hundreds of U.S. colleges publish a standardized report covering
> admissions, enrollment, costs, and financial aid. It’s called the Common Data
> Set. We archive those files and turn them into searchable pages you can
> compare and share.

### Body edits (light touch)
- **What it is** (last three sentences):
  - *Now:* `Filling it out is voluntary. There is no central filing cabinet. Each school posts a file, or doesn't.`
  - *Proposed:* `Filling it out is voluntary, and there is no central federal repository. Each college decides whether and where to post its own file.`
- **How to use it here** (first bullet):
  - *Now:* `Search a school, open a year, read the facts, download the original file.`
  - *Proposed:* `Families and students: search a school to see its latest admissions, test-score, and aid numbers, with the college’s original file linked on the same page.`
  - *(Keep the Counselors and IR/researchers bullets with one small tweak: change `"the extract uses the template’s field IDs"` to `"the dataset preserves the template’s official field IDs"` so `"extract"` doesn’t slip back into product-adjacent copy.)*
- **Last section heading + paragraph:**
  - *Heading:* `How it relates to federal data` *(warmer and clearer than `"We don't replace the school, or the feds"`)*
  - *Body:* `Every Common Data Set number on this site comes directly from the college, as the school published it. We display it alongside federal data from [IPEDS](/about/ipeds) and [College Scorecard](/about/college-scorecard), which run on different calendars and definitions, and we keep each source clearly labeled.`

---

## 4. College Scorecard explainer (`/about/college-scorecard`)

Full rewrite off internal SEO/architecture-memo voice. Removes *"navigational
result"*, *"This page is not trying to replace that"*, *"That pairing is the
product"*, and *"a map of the join this site actually cites"*. Keeps every
table, diagram, and Harvey Mudd / Virginia Tech worked example.

### Meta
- **Title:** `College Scorecard, and how it differs from the Common Data Set`
- **Description:** `College Scorecard reports federal net price, student debt, and post-college earnings across roughly 6,000 schools. Here is what it covers and why its dates lag a college’s Common Data Set.`

### Hero
- **Kicker:** `College Scorecard`
- **H1:** `College Scorecard, and how it differs from the Common Data Set`
- **Lede:**
  > College Scorecard answers questions the Common Data Set never asks, such as
  > what graduates actually borrow and earn years later. Because it draws from
  > federal records rather than this year’s admissions office, we show it next
  > to a school’s report instead of blending the two together.

### Body

**Where it comes from**
> Launched by the U.S. Department of Education, [College Scorecard](https://collegescorecard.ed.gov/)
> is a public consumer database built from existing federal records rather than
> a survey colleges fill out each fall. Because the government compiles it from
> administrative data, it covers nearly every U.S. college that participates in
> federal financial aid, including thousands of schools that never publish a
> Common Data Set.

**What goes into it**
> Each institution’s Scorecard record combines several federal systems: IPEDS
> institutional surveys, federal student-aid records (NSLDS), Treasury/IRS
> earnings data, Federal Student Aid operating flags, and Census/OPE reference
> fields. We document the field-level comparison in
> [CDS vs College Scorecard](https://github.com/bolewood/collegedata-fyi/blob/main/docs/research/cds-vs-college-scorecard.md).

- **Figure 1 caption:** `How College Scorecard combines five federal data sources into one institutional record.` *(link: `See how it appears on Harvey Mudd`)*
- **Table** (`What Scorecard is good at, what CDS is good at, and what neither covers`): keep structure; tighten row 3 middle cell from *"School-authored PDF/XLSX you can archive and cite"* to *"Original school-published PDF or spreadsheet you can download and cite"*, and row 2 right cell to *"A single blended number that hides which year it came from"*.

**Why Scorecard covers more schools than the Common Data Set**
> Federal reporting through IPEDS is mandatory for colleges that accept federal
> student aid, while publishing a Common Data Set is voluntary. That is why a
> college with no public Common Data Set still has a page here with federal cost
> and outcome figures rather than a dead end. Both
> [Harvey Mudd](/schools/harvey-mudd) and [Virginia Tech](/schools/virginia-tech)
> publish Common Data Sets, so they serve as useful side-by-side examples across
> our [Common Data Set](/about/common-data-set) and [IPEDS](/about/ipeds)
> guides.

- **Figure 2 caption:** `Mandatory federal reporting covers roughly 6,000 colleges, while voluntary Common Data Set publishing covers only a subset.`

**Why Scorecard dates lag a school’s own report**
> On pages like [Harvey Mudd](/schools/harvey-mudd) and
> [Virginia Tech](/schools/virginia-tech), admissions and test-score cards come
> from the college’s latest archived Common Data Set, while federal outcomes
> sit in their own section with a vintage note. Earnings and repayment figures
> naturally reflect earlier cohorts (often students who enrolled a decade
> earlier), so they will never match the current admissions cycle year for year.

- **Figure 3 caption:** `On Harvey Mudd’s school page, the 2025–26 Common Data Set sits alongside federal Scorecard outcomes with their cohort dates clearly noted.`

**How we use it alongside the Common Data Set**
> Families need both kinds of information: this year’s admissions and merit-aid
> picture from the college, and long-term net price, debt, and earnings from
> federal records. Showing both on one page, with each section labeled by source
> and year, lets you read them together without mistaking one for the other. For
> school-specific details like waitlists or test policies, open a year page such
> as [Virginia Tech 2025–26](/schools/virginia-tech/2025-26).

**When to use the official Scorecard site**
> If you want earnings broken down by individual major (CIP code), the federal
> comparison tool, or the full data dictionary, go straight to
> [collegescorecard.ed.gov](https://collegescorecard.ed.gov/). We bring
> Scorecard’s institutional metrics onto each school page so you can read them
> alongside a college’s Common Data Set and [IPEDS baseline](/about/ipeds)
> without juggling three different sites.

---

## 5. IPEDS explainer (`/about/ipeds`)

Full rewrite off internal spec/SEO voice. Removes *"The navigational query
'IPEDS' belongs to..."*, *"In public language, the coverage layer's non-goals
are:"*, *"Directory-scale coverage"*, and *"Source labels are the product."*

### Meta
- **Title:** `What IPEDS is, and what it cannot replace` *(keep — strong title)*
- **Description:** `IPEDS is the federal statistical database filed each year by roughly 6,400 U.S. colleges. Here is what it covers, how we use it on school pages, and why it cannot replace a Common Data Set.`

### Hero
- **Kicker:** `IPEDS`
- **H1:** `What IPEDS is, and what it cannot replace`
- **Lede:**
  > The federal government already maintains a comprehensive statistical record
  > of U.S. colleges through IPEDS. It is essential for long-term trends,
  > institutional finances, and broad coverage, but it moves on a slower federal
  > schedule and leaves out key admissions details colleges publish in their
  > Common Data Sets.

### Body

**The federal baseline (and UNITID)**
> Run by the [National Center for Education Statistics](https://nces.ed.gov/),
> [IPEDS](https://nces.ed.gov/ipeds) (the Integrated Postsecondary Education
> Data System) collects annual survey data from roughly 6,400 U.S. institutions
> that participate in federal financial aid. Every institution has a permanent
> numeric identifier called a `UNITID` (for example, `115409` for Harvey Mudd
> and `233921` for Virginia Tech), which is how we reliably match federal
> records to each school’s published reports.
>
> For official definitions and raw downloads, go to `nces.ed.gov/ipeds`. This
> guide explains how those federal tables appear on collegedata.fyi and where
> they differ from a college’s Common Data Set.

**How IPEDS data is structured**
> Instead of one annual document, IPEDS is organized into separate survey
> components: directory information (`HD`), institutional characteristics (`IC`),
> admissions (`ADM`), fall enrollment (`EF`), graduation rates (`GR`), student
> financial aid (`SFA`), and finance (`F`). NCES publishes provisional files first
> (after quality checks and imputations for missing responses), followed later
> by revised final files distributed as Microsoft Access databases and
> codebooks.

- **Figure 1 caption:** `IPEDS survey components are released first as provisional files and later as final datasets, keyed by each school’s UNITID.`

**How IPEDS appears on a school page**
> On every school page, the federal baseline table lists the exact IPEDS table,
> variable name, release status (`provisional` or `final`), and how closely the
> federal definition aligns with the Common Data Set:

- **Table** (`Example IPEDS facts and how they align to CDS`): keep the 3 rows, lightly smoothing row 1 (*"ADM totals track C1 closely, though definitions of student population, gender reporting, and release timing can differ."*) and row 3 (*"HD locale is a federal geographic classification rather than a Common Data Set field."*).
- **Figure 2 caption:** `Virginia Tech’s federal baseline table, showing the IPEDS table, variable name, and release status for each figure.`

**What IPEDS cannot replace**
> IPEDS is not a substitute for a college’s Common Data Set. It does not report
> current-year waitlist numbers, Early Decision vs. Regular Decision outcomes,
> non-need merit aid counts (Section H2A), or the school’s own published PDF.
> Common Data Sets also tend to appear months before the corresponding IPEDS
> release. For those school-reported details, open a year page such as
> [Virginia Tech 2025–26](/schools/virginia-tech/2025-26) or
> [Harvey Mudd 2025–26](/schools/harvey-mudd/2025-26).

**Why we include it anyway**
- **Broader coverage:** When a college doesn’t publish a Common Data Set, IPEDS
  still gives you reliable enrollment, cost, and admissions context.
- **Longer history:** Federal series remain consistent over time even when a
  college reorganizes its website or removes older PDFs.
- **Institutional finance:** IPEDS Finance filings include endowment and
  spending figures that the Common Data Set doesn’t cover (see our
  [endowment draw-rate analysis](/recipes/endowment-draw-rate)).

**Telling the three sources apart on a school page**
> Each school page keeps its sources visually separate. Common Data Set figures
> live in the main school-year view alongside the downloadable original file.
> IPEDS figures appear in the federal baseline table with their `UNITID`, table,
> and variable names. College Scorecard outcomes sit in their own section with
> cohort vintage notes.

- **Figure 3 caption:** `Virginia Tech’s school page, keeping school-published Common Data Set figures separate from the federal IPEDS baseline.`

---

## 6. Match (`/match`)

**Primary:** parents, students, and counselors building a college list.

### Meta
- **Title:** `Match` *(keep)*
- **Description:** `Build a college list from each school’s published admissions and test-score data. Runs locally in your browser with no account and no stored student profile.`

### Hero
- **Kicker:** `Match`
- **H1:** `Build your college list from published numbers` *(breaks up the repeated `Clause, *italic clause.*` pattern)*
- **Lede:**
  > Enter your test scores and GPA to filter schools by selectivity, size, cost,
  > and fit, then export your list with links to each school’s original report.
  > Everything stays in your browser; we never save a student profile.

---

## 7. Compare (`/browse`)

**Primary:** counselors and parents comparing schools side by side; IR
secondary.

### Meta
- **Title:** `Compare schools` *(keep)*
- **Description:** `Compare admissions, test scores, cost, and financial aid across U.S. colleges using each school’s latest published report, with the original file one click away.`

### Hero
- **Kicker:** `§ Compare` / `2024–25+` *(en dash rather than hyphen)*
- **H1:** `Compare schools side by side` *(plain, direct — drops the comma + italic cliché)*
- **Lede:**
  > Filter and sort admissions, test scores, cost, and financial aid across
  > colleges. Each row reflects the latest comparable report as the school
  > published it, with the original file linked right alongside the numbers.

### Hero stats
| Label | Note |
|---|---|
| `Schools` | `In this table` *(keep)* |
| `Reports` | `2024–25 and newer` *(keep, en dash)* |
| `Metrics` | `Comparable fields per report` *(replaces `Facts / From the latest reports`)* |
| `Updated` | *(date — replaces `Refreshed`)* |

---

## 8. Schools directory (`/schools`)

**Primary:** parents, counselors, and researchers looking up a specific college.

### Meta
- **Title:** `Schools` *(keep)*
- **Description:** `Browse every U.S. college with an archived Common Data Set on file, and open the original reports each school published.`

### Hero
- **H1:** `Schools` *(keep)*
- **Lede:**
  > Every college with an archived annual report on file. Don’t see a school
  > listed? Use the search bar above or check [Coverage](/coverage). Colleges
  > without a published Common Data Set still have pages with federal data.

---

## 9. Coverage (`/coverage`)

**Primary:** counselors, IR staff, and parents checking whether a school has a
report on file.

### Meta
- **Title:** `Coverage` *(keep)*
- **Description:** `See which U.S. colleges have a current Common Data Set on file, which have older years, and which have federal data only. Filter by state and size.`

### Hero
- **Kicker:** `§ Coverage`
- **H1:** `Archive coverage` *(clean and scannable; avoids another two-beat italic slogan)*
- **Lede:**
  > Every U.S. college that participates in federal student aid, and whether we
  > have a public Common Data Set on file. Publishing is voluntary: some schools
  > post their report openly, some tuck it away, and many never publish one at
  > all.

### Methodology note (lines 89–115 of `coverage/page.tsx`)
Small tighten only:
- Paragraph 1: change *"active Title-IV institutions that serve undergraduates"* to *"active U.S. colleges that serve undergraduates and accept federal student aid"* (removes the `Title-IV` leak that Wave 2 flagged for the lede but left in the section below).
- Paragraph 4: *"Know where a missing report is posted? Open the school’s page and [send us the link](/feedback) so we can archive it and update this table."* *(Points to `/feedback` instead of `/about`, which has no submission link.)*

---

## 10. Scholarships (`/scholarships`)

**Primary:** families, students, and counselors researching named merit awards.

### Meta
- **Title:** `Scholarship programs` *(keep)*
- **Description:** `Named merit scholarships at U.S. colleges: award amounts, eligibility, and deadlines, each linked to the school’s own page and dated. Not a ranking or an award estimate.`

### Hero
- **Kicker:** `§ Scholarships`
- **H1:** `Named merit scholarships` *(clear, scannable — drops the comma + italic formula)*
- **Lede:**
  > Award amounts, eligibility rules, and deadlines for named merit
  > scholarships, each linked directly to the college’s own page. We’re
  > building this index by hand, so a school missing from this list simply
  > hasn’t been added yet.

### Fine print
- Line 87 currently uses British spelling (`licence`); change to `license` for
  consistency with the rest of the site (`MIT License` in Footer).

---

## 11. Methodology index (`/methodology`)

**Primary:** counselors, IR staff, and curious parents checking how school-page
cards work.

### Meta
- **Title:** `Methodology` *(keep)*
- **Description:** `How the cards on each school page read Common Data Set filings and federal data, covering academic profiles, admission rounds, financial aid, and scholarships.`

### Hero
- **Kicker:** `§ Methodology`
- **H1:** `How the school-page cards work`
- **Lede:**
  > Each guide below documents the exact Common Data Set fields, formulas, and
  > limits behind the cards on a school page. These summaries show what
  > colleges reported; they do not predict admission decisions or financial-aid
  > offers.

### Cards (removing the triple `"Not a ..."` fragment tic)
1. **Academic profile:** `How a student’s SAT or ACT score compares with the middle ranges each school published for enrolled first-years.`
2. **Admission rounds:** `Early Decision, Early Action, waitlists, and yield from Section C, including what the Common Data Set does and does not let you calculate.`
3. **Merit and need aid:** `Need-based and non-need aid from Section H, paired with federal net-price and graduate outcome data.`
4. **Scholarship programs:** `How we document named merit scholarships at selected schools, with source URLs and review dates for every term.`

*(The single disclaimer in the lede already covers non-prediction cleanly without repeating `"Not a ..."` at the end of every card.)*

---

## 12. Recipes index (`/recipes`)

**Primary:** institutional researchers, analysts, and education journalists.

### Meta
- **Title:** `Recipes` *(keep)*
- **Description:** `Worked analyses built from Common Data Set filings and federal data, each with its method, interactive chart, and underlying public API query.`

### Hero
- **Kicker:** `§ Recipes`
- **H1:** `Data analyses & recipes` *(or keep `Worked examples` without the stray italic + period)*
- **Lede:**
  > Interactive analyses built from Common Data Set filings and federal data,
  > with the method, caveats, and public API query right beside each chart.
  > Written primarily for institutional researchers, analysts, and education
  > reporters.

---

## 13. Alignment gap (`/recipes/alignment-gap`)

**Primary:** IR staff, college-finance reporters, analysts, and engaged
parents.

PRD 034 went straight to `main` with no review. The math and data-limits
sections are solid; the opening paragraphs and region/quadrant cards need a
tight editorial edit to cut throat-clearing and LLM hedging.

### Opening narrative (replaces lines 192–234)
- **H1:** `Debt burden, merit aid, and financial resources` *(plain, direct)*
- **Lede (italic serif):**
  > At **{covers} of {positiveGap} colleges ({coversPct}%)** with above-median
  > graduate debt burden, the freshman non-need merit aid budget alone is larger
  > than the school’s entire annual alignment gap.
- **Body (3 tight paragraphs instead of 6):**
  > Many colleges whose graduates leave with heavy federal student debt also
  > spend thousands of dollars per freshman on non-need “merit” discounts to
  > recruit students who do not have financial need. Putting federal debt and
  > earnings data next to school-reported merit aid lets us ask a concrete
  > question: how big are those merit budgets compared with the debt burden
  > graduates carry?
  >
  > To measure that consistently across schools, we start with **debt burden**:
  > the share of median post-college earnings required to cover annual federal
  > loan payments (from College Scorecard). A school’s **alignment gap** is
  > roughly how much less debt its graduates would need to borrow, expressed
  > per year of college, to match the {corpusMedianBurden} median debt burden
  > across this group.
  >
  > The gap is a yardstick, not a tuition prescription. Cutting sticker price or
  > redirecting merit grants wouldn’t reduce student borrowing dollar for
  > dollar. What it shows is scale: how a college’s debt burden stacks up
  > against its non-need merit spending (Common Data Set H2A) and its endowment
  > (IPEDS).

### Region cards (tightening the hedging)
- **A · Merit aid is larger than the gap:**
  > Among the {positiveGap} schools with above-median debt burden, {covers}
  > ({coversPct}%) report average non-need merit aid per first-year student
  > larger than their annual alignment gap. Quincy University is a stark
  > example: it reports non-need merit aid for every full-time freshman,
  > averaging {quincy.avgMeritGrant}, alongside an average net price of
  > {quincy.avgNetPrice} and an alignment gap of {quincy.gap} a year. A college
  > can’t simply shift budget lines dollar for dollar, but the comparison shows
  > how large existing merit discounting is next to graduate debt.
- **B · Merit aid is smaller than the gap:**
  > These schools also carry above-median debt burden, but their reported
  > non-need merit aid per freshman is smaller than the gap, and some award
  > almost none at all. The University of the Incarnate Word, for instance,
  > reports $0 in CDS non-need merit aid while still showing a positive gap. At
  > these schools, overall pricing, need-based aid, borrowing habits, and
  > graduate earnings drive the picture far more than merit discounting.
- **C · Debt burden is at or below the median:**
  > These schools have no positive alignment gap here because their graduate
  > debt burden is already at or below the {medianBurden} benchmark. They stay
  > on the chart so you can see the full sample at once.

### Quadrant cards (cutting *"That is an important distinction"* / *"In other words"* filler)
- **I · Higher debt burden · higher endowment:**
  > Above-median debt burden paired with above-median endowment per
  > undergraduate. Endowment rules and restricted gifts limit what any college
  > can spend on aid, so this doesn’t prescribe a budget. It simply flags
  > institutions with deeper financial reserves whose graduates still carry
  > heavier federal debt. Hollins University sits near the outer edge, with a
  > {hollins.burden} debt burden and roughly {hollinsEndowmentUsd} in endowment
  > per undergraduate.
- **II · Higher debt burden · lower endowment:**
  > Above-median debt burden with below-median endowment per undergraduate. Two
  > colleges can leave graduates with similar debt while operating with very
  > different financial cushions. Bennington College illustrates the tighter
  > side: a relatively high debt burden, a modest endowment per student, and
  > instructional spending equal to about {benningtonInstructionPct}% of its
  > average net price.
- **III · Lower debt burden · higher endowment:**
  > Debt burden at or below the median alongside above-median endowment per
  > undergraduate, a group that includes Grinnell, Princeton, Stanford, and
  > Wellesley. At many heavily endowed colleges, instructional spending per
  > student exceeds average net price because endowment income subsidizes a
  > large share of the education.
- **IV · Lower debt burden · lower endowment:**
  > Debt burden at or below the median without a large endowment per student.
  > Stronger post-college earnings often do the heavy lifting here (earnings
  > sit in the denominator of debt burden), alongside lower borrowing. Bentley,
  > Babson, and Santa Clara all land in this quadrant.

---

## 14. Open factual bug to fix in the same pass

- [`web/src/components/PositioningCard.tsx`](../../web/src/components/PositioningCard.tsx) line 26:
  - *Now:* `${formatPercent(submitRate)} OF ADMITS SUBMITTED ${testName} SCORES`
  - *Fix:* `${formatPercent(submitRate)} OF ENROLLED FIRST-YEARS SUBMITTED ${testName} SCORES`
  - *(Matches the Wave 4 correction: CDS Section C.9 reports enrolled first-years, not admits.)*

---

## 15. Copy-test cleanup when implementing

Several existing tests hard-pin exact prose strings from Waves 2–4 and PRD 034,
which turns normal editing into CI failures:
- `web/src/lib/wave-2-product-copy.test.ts`: keep the **banned-jargon**
  assertions (`Queryable`, `PRIMARY ROWS`, `§ BROWSER`, `extracted by`,
  `Title-IV institution in the`, `resolver has not scanned`) and route/SEO
  invariants (`${name} Common Data Set`, `href="/coverage"`, `directoryOnlyLead`),
  and remove brittle exact-phrase pins (`"side by side"`, `"Every school we
  have a report from"`, `"Enter scores and GPA"`).
- `web/src/lib/wave-4-copy.test.ts`: keep factual invariants (no
  `admitted-class`, no `Tier 4`, no `Docling`, no `PRD 016`, rate-limit
  numbers, valid MCP config paths) and drop exact editorial wording pins like
  `"The trail behind the school-page cards"` and `"enrolled first-years — the
  entering class, not the"`.
- `web/src/lib/alignment-gap-copy.test.ts`: update to check computed claim
  invariants (the live 65% headline, no stale Bard/Grinnell numbers, non-causal
  caveat present) rather than frozen opening sentences.
