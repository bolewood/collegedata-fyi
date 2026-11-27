# Quadfile — Voice

Editorial source of truth for public copy. Visual rules stay in
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md). If they conflict, this file wins
for *what we say*; the design system wins for *how it looks*.

Originally locked 2026-08-26 (Waves 1–4). Updated 2026-11-19 to add
natural-prose rules, separate invariant tests from prose, and retire
hedged front-door phrasing.

---

## Site promise

Every public page should make the product useful, not explain how the
archive is built.

- **About / PR form (named sources):**
  Each college’s annual Common Data Set alongside federal IPEDS and
  College Scorecard records, linked to the original files, free with no
  account.
- **Homepage form (plain English first):**
  Admissions, test scores, financial aid, and graduate outcomes for U.S.
  colleges, pulled from published school reports and federal records.
  Every school report links directly to the original file.

Do not open the homepage with three proper nouns (`Common Data Set`,
`IPEDS`, `College Scorecard`). Say what the reader actually gets in
everyday terms, then let the labeled data and `/about/*` guides carry
the formal names.

Avoid hedged superlatives like *"the most comprehensive free college
data we know of."* Specific facts carry more weight than qualified
boasts.

---

## Natural prose (anti-slop)

Banning operator jargon is only half the job. When writers (human or AI)
draft under a long list of negative rules, they default to **faux-editorial
minimalism**: breathy three-word sentences, defensive caveats up top,
em dashes in every paragraph, and identical two-beat headlines on every
page.

Write like a knowledgeable, calm human explaining a useful tool to a
parent or counselor across a table.

### Five rules

1. **Vary sentence length.** Never stack more than two short or fragment
   sentences in a row.
   - *Avoid:* "Search a school. Compare admissions, cost, and aid. Open
     the original file. No account."
   - *Prefer:* "Search any school, compare numbers side by side, or
     download the source files for free, with no account required."

2. **Lead with value, put caveats second.** Honesty is non-negotiable,
   but opening a page with what it *isn’t* or *doesn’t have* makes the
   product sound apologetic.
   - *Avoid:* "This is a partial, hand-built list. A school that is not
     here has not been documented yet, which is different from having no
     named scholarships."
   - *Prefer:* "Award amounts, eligibility rules, and deadlines for
     named merit scholarships, each linked directly to the college’s own
     page. We’re building this index by hand, so a missing school simply
     hasn’t been added yet."

3. **Don’t repeat one headline gimmick across the site.** Save split
   italic turns (`College data,` *`straight from the source.`*) for the
   homepage and brand moments. Utility pages (`/match`, `/browse`,
   `/coverage`, `/scholarships`, `/methodology`) should use plain,
   direct headings.

4. **No internal spec or SEO talk in public prose.** Never publish
   phrases written for PRDs, architecture docs, or search-engine strategy:
   *"navigational query"*, *"non-goals"*, *"coverage layer"*, *"that
   pairing is the product"*, *"start there, not on this page"*, *"this
   page is not trying to replace…"*.

5. **Cut throat-clearing and essay filler.** On recipes and methodology
   pages, lead with the finding or question rather than *"College
   affordability data lives in several different places."* Cut transitions
   like *"That is an important distinction"*, *"In other words"*, and
   *"That does not mean X. It does show Y."*

### Em dashes
Default to commas, colons, parentheses, or a clean period instead of em
dashes. Never use more than one em dash on a page, and never pin one in
a test.

---

## Personas (primary)

Journalists and developers are welcome. They are not a fourth homepage
audience; point them at `/api` (in the header), GitHub, and methodology.

### Parents and students
They may never have heard "Common Data Set." They want reliable, current
numbers they can act on: is this school in range, what does it cost, and
can I compare schools without a paywall or a student-data profile?

Name what they get (admissions, test scores, financial aid, outcomes),
link the original school file, and don’t lecture them on the template.

### College counselors
They already know the CDS. Don’t explain sections A–J unless they are on
the CDS explainer. Help them check the latest year, share a clean year
URL instead of a 47-page PDF, and spot coverage gaps or year-over-year
shifts.

### Researchers and IR
They want peer files, definitions, bulk access, a way to flag a missing
year, and clean exports. Analytical terminology (`yield`, `C2`,
`Carnegie class`, `draw rate`) belongs on `/recipes`, `/methodology/*`,
and `/api`. Still no extractor war stories (`Docling`, `AcroForm`,
`drain`, how we parsed the PDF).

---

## Three voice layers

Keep plumbing visible to people who want it. Don’t put it on the front
door.

| Layer | Audience | Lives on | Tone |
|---|---|---|---|
| **Product** | Parents/students first; counselors second | `/`, `/about`, `/about/*`, school & year pages, `/browse`, `/match`, `/coverage`, `/scholarships`, cards, empty states, metadata | Clear, calm, everyday English. Benefit first, honest scope second, original file one click away. |
| **Professional** | IR, researchers, analysts, reporters | `/recipes`, `/methodology/*`, `/api` | Lead with the question or finding, state the method and caveats plainly, show the query. Jargon is fine when it earns its keep. |
| **Operator** | Maintainers and OSS contributors | `/pipeline-observation`, `docs/`, `docs/known-issues/`, GitHub | Extractors, Docling vs AcroForm, Harvey Mudd C1, drains, heartbeats. |

---

## Chrome

- **Primary nav:** Match / Schools / API. API stays in the header (for
  researchers, and for families pointing LLMs at a public endpoint).
- **More menu:** Compare, Archive status, Recipes, About, GitHub. Do not put
  Pipeline in More.
- **Footer:** Pipeline stays here like a status link; GitHub lives here
  and in More, not on the homepage hero.
- **Public name for `/browse`:** always **Compare**, never "Browser."

---

## Glossary

Product copy prefers the right-hand column. Operator docs may use the
left.

| Avoid on product pages | Prefer |
|---|---|
| extracted / extractor / Docling / AcroForm / Tier 4 | read from the school’s file / published by the school |
| canonical year | 2025–26 (the actual academic year) |
| drain, manifest, projection, browser row, comparer, Browser, alias | recently added reports; comparable reports; Compare |
| Title-IV (on parent ledes) | colleges that accept federal student aid |
| "files a school has since taken down" | historical years; the original file (do not advertise takedowns) |
| "the government’s own numbers" | federal tuition, debt, and earnings data (or federal records) |
| CDS field IDs in a product lede (`C.101`, `AP_RECD_1ST_MEN_N`) | the fact in English; IDs in tables, recipe chips, or API docs |
| "admitted-class bands" / "% of admits submitted" for C.9 | enrolled first-years (the entering class) |

Keep **Common Data Set** on the explainer and in school/year SEO
(`{name} Common Data Set` in title, description, and first sentence; H1
stays the school name).

When claiming **current** or **accurate**, anchor to *"as the school
published it."* Never imply we audited the school’s math. Federal
figures stay labeled as federal.

---

## Shipping & testing copy

1. **Draft major pages in `docs/copy/`** so Anthony can read the prose
   aloud without wading through JSX. For small UI labels or single-card
   tweaks, review directly in the PR.
2. **Run two distinct checks before merging:**
   - *Factual & consistency audit* (AI persona review is great at this):
     do captions match underlying SQL counts? Do empty states contradict
     promises? Are C.9 enrolled vs. admits and source vintages accurate?
   - *De-AI read-aloud pass*: strip stacked fragments, excess em dashes,
     repeated headline templates, defensive first sentences, and spec
     language.
3. **Test invariants, not prose.** Automated tests in `web/src/lib/`
   should enforce:
   - Live data accuracy (`acceptance-lead-audit.ts`, computed headlines)
   - Banned jargon and factual traps (`Docling`, `Tier 4`, `admitted-class`,
     `Title-IV` on parent ledes)
   - Structural/SEO requirements (length caps, `{name} Common Data Set`
     in school metadata, license attribution)
   Do **not** pin exact editorial phrasing with `expect(src).toContain(...)`.
   That freezes mediocre copy and punishes future editing.
