# Wave 1 copy deck — front door

Read this as a parent, then as a counselor, then as IR. Do not review it as
a React diff. Locked decisions: three primary personas, the site promise
(named sources on About; gloss first on the homepage), Harvey Mudd Docling
off the CDS explainer, Pipeline stays in the footer.

Persona-read 2026-08-26 applied **1, 2, 5, 8, 9** below. **3, 4, 6, 7** are
open questions at the end of this deck.

**Not in this deck:** live TSX. Sign the prose, then we implement.

---

## Chrome

**Keep in footer (status-style):** Pipeline, plus Coverage, API, About, GitHub.

**Drop from the More menu:** Pipeline. More stays Browser, Coverage, Recipes,
About, GitHub until question 6 is called (Compare vs Browser for `/browse`).

Primary nav unchanged: Match, Schools, API.

---

## Homepage (`/`)

**Primary persona:** parents and students. Counselors and IR should still
see a path (Match / Browse / API) without being the lede.

### Meta

- Title: collegedata.fyi — College facts from the schools
  *(question 7 — alternative title parked below)*
- Description: The most comprehensive free college data we know of — the
  report each college publishes, plus the government’s own numbers, in one
  public place.

### Hero

Keep the headline: **College data,** *straight from the source.*

Replace the current lede with the gloss. Do not name Common Data Set, IPEDS,
or College Scorecard in this paragraph — those links already live on the
page:

> The most comprehensive free college data we know of — the report each
> college publishes about itself, plus the government’s own numbers, in one
> public place.
>
> Search a school. Compare admissions, cost, and aid. Open the original
> file. No account.

Marginalia can stay (OPEN DATA / SOURCE LINKS / PUBLIC API on the left;
ADMISSIONS / AFFORDABILITY / OUTCOMES on the right). Those are catalog
chrome, not operator jargon.

CTAs: Search is the door. **No “Find a school” button** — search is already
the dominant element, and inventing a fourth destination forces the
implementer to improvise. Button row stays Match / Compare / Schools as
today:

- **Build match list** → `/match`
- **Compare schools** → `/browse` *(label vs nav “Browser” is question 6)*
- **Browse all schools** → `/schools`

Ghost: **API** and **GitHub** (IR/builders, not the parent path).

### Stat band

Keep live counts. Relabel the operator notes:

| Now | Proposed label | Proposed note |
|---|---|---|
| Schools in archive / N extracted | Schools | Latest reports we have on file |
| Source documents / year span | Documents | School files, 1998–2025 (live span) |
| Queryable fields / field schema | Facts you can compare | From current school reports |
| Browser rows / N schools | Schools you can compare | side by side · refreshed {date} |

Exact note wording can use the live stats. Ban “extracted,” “schema,”
“browser rows,” and “comparer” on this band.

### Recently added (today: “§ Latest drain”)

Heading: **Recently added**
Caption: New school reports in the archive. Each row opens the school and
the original file.

Keep the live feed. Drop “drain” from the public heading.

---

## About (`/about`)

**Primary:** all three personas, parents first.
Keep the title **The *Uncommon* Data Set** — it’s brand, not jargon.

### Meta

- Title: About
- Description: The most comprehensive free college data we know of. School
  Common Data Set reports, IPEDS, and College Scorecard, in one public place.
  No account.

### Proposed body

**Lede.** Choosing a college should not mean a dozen tabs, a paid search
product, and a PDF you can’t compare. This is the most comprehensive free
college data we know of: each school’s Common Data Set, plus IPEDS and
College Scorecard, in one public place.

**What you can do.**

- Search a school and open the latest report it published.
- If a school hasn’t published its own report, you still get the federal
  numbers.
- Download the original file the school posted.
- Compare admissions, enrollment, test scores, cost, and aid across schools.
- Build a match list on your device. We don’t store a student profile.
- If you’re in IR or research: use the same data through a public API.

The federal-fallback line is load-bearing. Roughly 507 schools have a
current CDS, 189 are stale, and ~1,473 in-scope schools have never published
one we could find. Without it, “search a school and see current numbers”
fails for the majority of schools, and the comprehensiveness claim weakens.

**How this is different.** Commercial college-search tools can be useful.
They often want an account, hide where a number came from, or build a student
profile along the way. We don’t. The school’s own report sits next to the
federal numbers, the original file is one click away, and you don’t have to
pay or log in.

**The reports, in one line each.** (Links, not a seminar.)

- [Common Data Set](/about/common-data-set) — the yearly report the college
  writes.
- [College Scorecard](/about/college-scorecard) — federal outcomes and net
  price.
- [IPEDS](/about/ipeds) — the federal statistical baseline.

**Open source.** Code, schema, pipeline, and archived files are public
(MIT). [GitHub](https://github.com/bolewood/collegedata-fyi). [API](/api).
Developers who want extractors and known issues start there, not on this
page.

**Credits / sponsors.** Keep Bolewood and the data-source links. Move
Docling and Reducto off this page (GitHub README / methodology appendix).
Parents don’t need the PDF parser list to trust the product.

Keep the closing line if it still earns it: *Better college decisions start
with better access to the facts.*

---

## What is the Common Data Set (`/about/common-data-set`)

**Primary:** parents who don’t know the term; counselors who will share the
URL. IR is secondary (they already know).

### Meta

- Title: What is the Common Data Set
- Description: The Common Data Set is the yearly report a college publishes
  on admissions, enrollment, cost, and aid. We archive those reports and
  make the numbers easy to use.

### Lede (replace the current “47-page PDF is not a data system”)

> Colleges publish a yearly report of admissions, cost, and financial aid.
> It’s called the Common Data Set. We keep those reports public — including
> files a school has since taken down — and turn them into pages you can
> search, compare, and share.

Keep the takedown claim (true; Stanford 2017–18). Don’t escalate it on
school-page copy in Wave 2. Quiet link to the takedown policy is question 4.

### Body outline

**What it is.** In the late 1990s, schools and guidebook publishers agreed
on one form so every college wasn’t answering the same questions fifteen
ways. The [Common Data Set Initiative](https://commondataset.org/) still
publishes that template. Filling it out is voluntary. There is no central
filing cabinet. Each school posts a file, or doesn’t.

**What’s in it.** Keep the A–J table in English. That’s useful for
counselors and curious parents. Don’t lead with field counts (1,105) unless
IR asks; a short “about a thousand comparable facts” is enough.

**How to use it here.**

- Search a school, open a year, read the facts, download the original file.
- Counselors: send the year page, not a 47-page PDF. The official file is
  on the same page, so you aren’t asking a family to trust a scrape.
- IR / researchers: the extract uses the template’s field IDs; the API and
  GitHub repo are the portable copy. Contribute a missing year from the
  school page.

**We don’t replace the school, or the feds.** The numbers are the college’s.
We aren’t [IPEDS](/about/ipeds) and we aren’t [College Scorecard](/about/college-scorecard).
Those are different systems with different calendars. On this site they
stay labeled.

### What leaves this page

All of the extractor narrative, including:

- “Point the wrong extractor at that file and C1 shifts”
- Docling collapsing Harvey Mudd C1, kerned years, running headers
- `docs/known-issues/harvey-mudd-2025-26.md` cited in public prose
- AcroForm / `pypdf.get_fields()` / `AP_RECD_1ST_MEN_N`
- The Docling-shift and repeating-header figures

**Relocate to:** `docs/known-issues/harvey-mudd-2025-26.md` (already there)
and, if we want a public professional pointer, a methodology appendix or
GitHub known-issues index. Not this URL.

**Optional keep, rewritten:** Harvey Mudd as a *positive* example — a school
that publishes a fillable 2025–26 file, [open the year page](/schools/harvey-mudd/2025-26)
— without teaching the parser. Virginia Tech as a *coverage* example: the
school’s landing page asks you to email; the file is public here. One
sentence each, or cut both from Wave 1 and save them for methodology.

---

## Read-aloud checks

- Parent: “I can search a school and see current numbers — the school’s
  report if they published one, federal numbers if they didn’t — plus the
  original file when we have it.”
- Counselor: “I can share a year URL and I know it’s the school’s report.”
- IR: “I know where the API and GitHub are, and that plumbing lives there.”

If any of those fail, the page isn’t done.

---

## Open questions (Anthony’s call)

Persona-read applied 1, 2, 5, 8, and 9. These four stay parked:

**3. “Collection of.”** “Most comprehensive free college data” can be read
as a swipe at IPEDS itself — which is free and covers ~6,000 institutions.
Safer: “the most comprehensive free *collection of* college data we know of.”
Slightly less punchy; meaningfully harder to rebut. Flagged, not blocking.
Deck currently keeps the punchier line.

**4. Takedown claim.** “Including files a school has since taken down” stays
in the CDS explainer lede. Wave 2 school-page copy should not escalate it.
Do we add a quiet link from the CDS explainer to the takedown policy
([ADR 0008](../decisions/0008-takedown-process.md), or wherever the public
policy will live)?

**6. Compare vs Browser.** Homepage button says “Compare schools”; More menu
says “Browser.” Two names for `/browse` in the same viewport. Pick
**Compare** for both (More item becomes “Compare”), or keep **Browser**
everywhere. This deck does not choose.

**7. Homepage title tag.** Current proposal: `collegedata.fyi — College
facts from the schools`. Alternative that keeps “free”: `collegedata.fyi —
Free college data, straight from the source`.
