# Wave 1 copy deck — front door

Read this as a parent, then as a counselor, then as IR. Do not review it as
a React diff. Locked decisions: three primary personas, the site promise,
Harvey Mudd Docling off the CDS explainer, Pipeline stays in the footer.

**Not in this deck:** live TSX. Sign the prose, then we implement.

---

## Chrome

**Keep in footer (status-style):** Pipeline, plus Coverage, API, About, GitHub.

**Drop from the More menu:** Pipeline. More stays Browser, Coverage, Recipes,
About, GitHub.

Primary nav unchanged: Match, Schools, API.

---

## Homepage (`/`)

**Primary persona:** parents and students. Counselors and IR should still
see a path (Match / Browse / API) without being the lede.

### Meta

- Title: collegedata.fyi — College facts from the schools
- Description: The most comprehensive free college data we know of — school
  Common Data Set reports, IPEDS, and College Scorecard, in one public place.

### Hero

Keep the headline: **College data,** *straight from the source.*

Replace the current lede with:

> The most comprehensive free college data we know of — each school’s
> Common Data Set, plus IPEDS and College Scorecard, in one public place.
>
> Search a school. Compare admissions, cost, and aid. Open the original
> file. No account.

Marginalia can stay (OPEN DATA / SOURCE LINKS / PUBLIC API on the left;
ADMISSIONS / AFFORDABILITY / OUTCOMES on the right). Those are catalog
chrome, not operator jargon.

CTAs: keep Search as the front door. Buttons: **Find a school** (→ `/schools`
or just rely on search), **Build a match list**, **Compare schools** (Browse).
Ghost: **API** and **GitHub** (IR/builders, not the parent path).

### Stat band

Keep live counts. Relabel the operator notes:

| Now | Proposed label | Proposed note |
|---|---|---|
| Schools in archive / N extracted | Schools | Latest reports we have on file |
| Source documents / year span | Documents | School files, 1998–2025 (live span) |
| Queryable fields / field schema | Facts you can compare | From current school reports |
| Browser rows / N schools | Schools in the comparer | Refreshed {date} |

Exact note wording can use the live stats. Ban “extracted,” “schema,”
“browser rows” on this band.

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
- Download the original file the school posted.
- Compare admissions, enrollment, test scores, cost, and aid across schools.
- Build a match list on your device. We don’t store a student profile.
- If you’re in IR or research: use the same data through a public API.

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

- Parent: “I can search a school and see current numbers plus the original
  file.”
- Counselor: “I can share a year URL and I know it’s the school’s report.”
- IR: “I know where the API and GitHub are, and that plumbing lives there.”

If any of those fail, the page isn’t done.
