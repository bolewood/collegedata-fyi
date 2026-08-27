# Wave 2 copy deck — product surfaces

Read this as a parent, then as a counselor, then as IR. Do not review it as
a React diff. Wave 1 is on `main`. This wave is the pages that still talk
like the pipeline: Compare, the schools directory, school and year pages,
Match, and Coverage.

Locked from Wave 1 (do not reopen): gloss-first homepage; named sources on
About; `/browse` is **Compare**; API in the header; GitHub off the hero; no
takedown advertising; when claiming current or accurate, say “as the school
published it.”

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
  the latest report the school published that we can put side by side. The
  original file is one click away.

**Chrome**

- Kicker: § Compare
- Sub: 2024–25+ · side by side

**H1:** Compare schools, *side by side.*

**Lede** (Newsreader italic, 18 / 1.55):

> Filter admissions, enrollment, cost, and aid. Each row is the latest
> school report we can compare, as the school published it. Open the
> original file from the same row.

**Stats** (short labels — `.meta` uppercases them):

| Now | Label | Note |
|---|---|---|
| Schools in scope | Schools | In this table |
| Primary rows | Rows | Latest year per school |
| Queryable fields | Facts | From current reports |
| Data refreshed | Refreshed | {date} |

**In-table caption:** Latest reports, 2024–25+. Schools missing a number
needed for your filters are counted separately. Looking for a match list?
Use Match.

**Error:** Couldn’t load these schools.

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
- Description: Find a college and open the reports it published.
- H1 (serif, display): Schools
- Lede (italic serif): Every school we have a report for. Search by name.
- Caption: {n} schools

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

### Proposed meta

- Title: `{name}`
- Description: `{name} — the report the college publishes, plus federal
  numbers, in one place. Open the original file.`

### Proposed archive lead

Heading can stay the school name (already the H1). Body:

> This page has {n} reports from {range}. Latest year is {year}.
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

Keep the stub. Add the Wave 1 fallback in product voice:

> We don’t have a report this school published. You still get the federal
> numbers.

Contribute remains on this page (IR path).

### JSON-LD

Same facts, no “extracted by.” Dataset description: admissions, enrollment,
cost, and aid as the school published them.

---

## Year page (`/schools/{id}/{year}`)

**Primary:** counselors (the URL they send). Parents opening a year.

### Now

- Description: “official source download plus extracted admissions…”
- Lead: “archived source file … plus the extracted field tables”
- Heading: “All extracted fields”
- Empty: “Structured data coming soon”

### Proposed meta

- Title: `{name}, {year}`
- Description: `{name} {year} — the report the college published, as it
  published it. Download the original file.`

### Proposed lead

> This is {name}’s {year} report, as the school published it.
> [Download the original file](url). See the [school’s own page](url).
> Subscribe via [RSS](feed).

### Fields heading

**The numbers, as published** — not “All extracted fields.”

Empty (file on disk, numbers not on the page yet):

> The original file is above. The numbers from this report aren’t on the
> page yet.

Ban: extracted field tables, structured data coming soon (too product-y
without saying what to do).

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

> Enter a profile on this device. Filter by scores, fit, and admit rate.
> Export a list with the year and the original file. We don’t store a
> student profile.

“Corpus” and “source-backed” leave the page. The file link stays — that’s
the counselor proof.

---

## Coverage (`/coverage`)

**Primary:** counselors and IR. Parents who searched a missing school.

The H1 already works: What we have, *and what we don’t.*

### Tighten

- Title: Coverage (drop “— collegedata.fyi”; the template adds it)
- Description: Which schools have a current report, which are stale, and
  which we’ve never found. Filter by state and size.
- Lede can stay, minus “resolver”:

> Every undergraduate Title-IV school, with whether we have a public
> report on file. Publishing is voluntary. Some schools post the file,
> some bury it, some don’t publish one we could find.

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
