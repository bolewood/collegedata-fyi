# Wave 2 copy deck — product surfaces

Read this as a parent, then as a counselor, then as IR. Do not review it as
a React diff. Wave 1 is on `main`. This wave is the pages that still talk
like the pipeline: Compare, the schools directory, school and year pages,
Match, and Coverage.

Locked from Wave 1 (do not reopen): gloss-first homepage; named sources on
About; `/browse` is **Compare**; API in the header; GitHub off the hero; no
takedown advertising; when claiming current or accurate, say “as the school
published it.”

**School pages are a Google door.** People search “Virginia Tech Common Data
Set.” Title and first sentence keep those words. The H1 can stay the school
name. The lead then talks like a parent.

- **H1 vs title.** Title and description carry the search query
  (`{name} Common Data Set`). H1 is the school name — that’s what
  the human is looking at. A `.meta` kicker can say Common Data Set
  once so the page isn’t a mystery. After the first sentence, say
  “report” and “the numbers,” not CDS every paragraph.
- **Year pages** keep `{name} Common Data Set {year}` in the title —
  that’s the long-tail (“Virginia Tech Common Data Set 2024-2025”).
- `VOICE.md` already allows this: Common Data Set on the explainer
  **and in SEO**.

Fable review 2026-08-27: **ship with patches.** Must-fixes and the
should-fixes that survived a code check are applied below. Full write-up:
[`wave-2-fable-review.md`](wave-2-fable-review.md).

**Not in this deck:** live TSX. Sign the prose, then we implement.

---

## Compare (`/browse`)

**Primary:** counselors and parents building a side-by-side list. IR
secondary (CSV / filters).

### Now (operator)

- Title: Queryable School Browser
- Kicker: § BROWSER / 2024-25+ / PRIMARY ROWS
- H1: Queryable school *browser.*
- Lede: “Filter the curated 2024-25+ browser rows without losing the source
  trail. The default view chooses the latest primary row per school…”
- Stats: Schools in scope / Primary rows / Queryable fields / Data refreshed
- Error: “Browser query failed”
- Caption: “Latest primary school-year rows, 2024-25+.”

### Proposed

**Meta**

- Title: Compare schools
- Description: Compare admissions, cost, and aid across schools. Each row is
  the latest school report we can compare, as the school published it. The
  original file is one click away.

**Chrome**

- Kicker: § Compare
- Sub: 2024-25+

**H1:** Compare schools, *side by side.*

**Lede** (Newsreader italic, 18 / 1.55):

> Filter admissions, cost, and aid. Each row is the latest school report
> we can compare, as the school published it. Open the original file from
> the same row.

**Hero stats** (short labels — `.meta` uppercases them):

The “Rows” count is every primary row from 2024-25 on, not latest-year-
per-school (`site_stats.browser_primary_row_count`). Label it as what it
is.

| Now | Label | Note |
|---|---|---|
| Schools in scope | Schools | In this table |
| Primary rows | Reports | 2024-25 and newer |
| Queryable fields | Facts | From the latest reports |
| Data refreshed | Refreshed | {date} |

**Filter-band stats** (the live dashboard under the filters — write it so
the implementer does not invent “Browser rows” again):

| Now | Label |
|---|---|
| Schools in scope | Schools |
| Matching filters | Match your filters |
| With required fields | Have every number |
| Missing fields | Missing a number |

**In-table caption:** Latest reports, 2024-25+. Schools missing a number
your filters need are counted above. Building a list? Use Match.

**Error:** label `Couldn’t load` (`.meta` will shout a full sentence).
Body: Try again in a moment.

Ban on this page: browser, browser rows, primary row, queryable.

---

## Schools directory (`/schools`)

**Primary:** parents hunting a name. Counselors second.

### Now

- Tailwind `text-2xl font-bold text-gray-900` — not the type system
- “School Directory”
- “N schools with archived Common Data Set documents.”

### Proposed

- Title: Schools
- Description: Every college with a Common Data Set on file. Open the
  reports each school published.
- H1 (serif, display): Schools
- Lede (italic serif): Every school we have a report from. Don’t see
  yours? Check [Coverage](/coverage) — schools without a report still get
  a page with the federal numbers.
- Caption: {n} schools
- Empty (on-page search, no matches): No reports on file match “{query}.”
  Try the site search — schools without a report still have a page with
  the federal numbers.

This table is only schools with a CDS on file. The header search and
Coverage are how a parent reaches the common case (no CDS, federal
numbers). Write the empty state; the live copy dead-ends (“No schools
found matching…”).

Keep the table. Restyle onto paper/ink/serif in the same change as the
prose — the gray heading is the design-system debt on this page.

---

## School page (`/schools/{id}`)

**Primary:** all three. Parents want current numbers and the file.
Counselors want a URL to send. IR wants the year list and a way to
contribute.

### Now (operator)

- Title: `{name} Common Data Set (CDS) Archive`
- Description: “Browse extracted admissions…”
- Lead: “This page archives N documents… Latest extracted year is…
  This page is the archive and extract.”
- JSON-LD: “extracted by collegedata.fyi”
- Directory-only stub exists (good) but does not say you still get federal
  numbers

### Proposed meta (SEO + readable)

People type `{name} Common Data Set`. Match that. Drop “Archive” and the
parenthetical “(CDS)” — both are extra syllables that aren’t the query.

- Title: `{name} Common Data Set`
  (template → `Virginia Tech Common Data Set | collegedata.fyi`)
- Description: `{name} Common Data Set — the yearly report the college
  publishes on admissions, cost, and aid, plus federal numbers. Years on
  file: {range}. Download the original file.`

H1 stays the school name (serif, institutional suffix italic). A `.meta`
kicker above it can read `Common Data Set` so the phrase is on the page
twice without stuffing the headline.

### Proposed archive lead

Name the term once, then use “report” and the numbers. Do not say the
page *is* the Common Data Set — it is our copy of {n} of them, next to
the federal numbers. The publisher line only renders when we know the
school’s page, so the lead has to stand on its own.

> The {name} Common Data Set is the yearly report the college publishes
> about itself. {n} reports on file, {range}; the latest is {year}.
> Downloads include {formats}.

If the school’s own page is public:

> The [school’s own page](url) is the publisher. This page is the public
> copy, with the numbers next to the file.

If the school’s page asks you to email:

> The [school’s own page](url) currently asks you to request the file.
> The original is here.

Then: What is a [Common Data Set](/about/common-data-set)? Subscribe to
new reports via [RSS](feed).

Do **not** say extract, extracted, archive and extract, or that a school
took a file down.

### Directory-only (no CDS on file)

Keep the stub. Title still `{name} Common Data Set` — that’s the query
that got them here. Then tell the truth. Do not promise federal numbers
on pages that have neither Scorecard nor an IPEDS baseline table
(live copy: “FEDERAL OUTCOMES DATA NOT AVAILABLE FOR THIS INSTITUTION”).

With any federal data on the page:

> We haven’t found a Common Data Set from this school. The federal
> numbers are below.

With neither:

> We haven’t found a Common Data Set from this school, and we don’t have
> federal numbers for it either.

Contribute remains on this page (IR path).

### JSON-LD

Same facts, no “extracted by.” Kill “keyed to the canonical 1,105-field
schema” too — “canonical” is glossary-banned.

Dataset description: Every Common Data Set year we have for {name}, as
the school published it.

---

## Year page (`/schools/{id}/{year}`)

**Primary:** counselors (the URL they send). Parents opening a year.

### Now

- Title: `{name} Common Data Set {year}` (keep this — it’s the query)
- Description: “official source download plus extracted admissions…”
- Lead: “archived source file … plus the extracted field tables”
- Heading: “All extracted fields”
- Empty: “Structured data coming soon”

### Proposed meta

- Title: `{name} Common Data Set {year}`
  (template appends `| collegedata.fyi` — do not write the suffix into
  the title or it doubles. Keep the query; “Virginia Tech Common Data
  Set 2024-2025” is a real search. Don’t add “Archive.”)
- Description: `{name} {year}: the school’s Common Data Set —
  admissions, cost, and aid — plus the original file to download.`
  (keep “Common Data Set” once; drop “extracted”)

### Proposed lead

Name Common Data Set once, then “this year’s report.” The download link
is conditional (`source_storage_path` can be null). The publisher link
is the school’s reports page, not its homepage.

> The {year} Common Data Set for {name} — admissions, cost, and aid, as
> the school published them. [Download the original file](url) (omit if
> none). See the [school’s page for these reports](url). Subscribe via
> [RSS](feed).

After that sentence, “the numbers” and “this year’s report” are
enough. Don’t keep saying Common Data Set.

### Fields heading

**The numbers, as published** — not “All extracted fields.”

Empty (file on disk, numbers not on the page yet):

> The original file is above. The numbers from this report aren’t on the
> page yet.

Empty, no downloadable file:

> The numbers from this report aren’t on the page yet.

Ban: extracted field tables, structured data coming soon, “No structured
field values available.”

---

## Match (`/match`)

**Primary:** parents and students. Counselors second (export).

### Now

- Title: Match List Builder
- Kicker: Match list builder
- H1: Build a school list from source-backed admissions data.
- Lede: “Enter one profile, filter the corpus, and export a
  counselor-friendly list with academic fit… CDS year, and source PDF.”

### Proposed

- Title: Match
- Description: Build a college list from the numbers schools publish. On
  this device. No account. No student profile stored.

**Kicker:** Match

**H1:** Build a list from the *school’s own numbers.*

**Lede** (italic serif):

> Enter scores and GPA — they stay on this device. Filter by fit and
> admit rate. Export a list with the year and the original file. We
> don’t store a student profile.

“Corpus” and “source-backed” leave the page. The file link stays — that’s
the counselor proof.

---

## Coverage (`/coverage`)

**Primary:** counselors and IR. Parents who searched a missing school.

The H1 already works: What we have, *and what we don’t.*

### Tighten

- Title: Coverage (drop “— collegedata.fyi”; the template adds it)
- Description: Which schools have a current Common Data Set, which have
  only older years, and which have none we could find. Filter by state
  and size.
- Lede, minus “resolver” and minus “Title-IV” (parents land here after a
  failed school search; keep the statute in Methodology):

> Every U.S. college that takes federal student aid, and whether we have
> a public report on file. Publishing is voluntary. Some schools post
> the file, some bury it, some don’t publish one we could find.

**Methodology** (on this page, still English):

- Keep: we look on school sites and known public archives; last-checked
  date; *No public CDS found* ≠ never publishes; contribute from the
  school page.
- Replace “the resolver has not scanned it” with “we haven’t checked this
  school yet.”
- Drop the “labeled separately so readers can tell” lecture. One line:
  federal numbers stay labeled as federal.

---

## Read-aloud checks

- Parent on a school page: “I can see current numbers — the school’s
  report if they published one, federal if they didn’t — and download the
  file.”
- Counselor on a year page: “I can send this URL. The official file is on
  it.”
- IR on Compare: “I can filter and export without being taught what a
  primary row is.”

If any of those fail, the page isn’t done.

---

## Out of Wave 2

Recipes, methodology, API docs — Wave 3/4. Cards on school pages
(positioning, merit, admission strategy) keep their numbers; only
operator chrome around them moves if it uses banned words. Do not
redesign those cards in this wave.
