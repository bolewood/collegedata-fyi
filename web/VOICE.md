# collegedata.fyi — Voice

Editorial source of truth for public copy. Visual rules stay in
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md). If they conflict, this file wins
for *what we say*; the design system wins for *how it looks*.

Locked 2026-08-26 after Anthony’s Wave 1 decisions. Promise revised the
same day: completeness over “tell the sources apart.” Persona-read the
same evening: homepage says the gloss first; named sources stay on About.
Follow-up calls: keep the punchier comprehensiveness claim; do not advertise
takedowns; `/browse` is Compare; homepage title keeps “free.” Signed with
API in the header (researchers and parents using LLMs); GitHub off the hero.

---

## Site promise

The most comprehensive free college data we know of — each school’s Common
Data Set, plus IPEDS and College Scorecard, in one public place.

That sentence is the product. The benefit is *everything in one place, for
free.* Naming the three sources is how we say what “everything” is, not a
lecture on keeping them apart. Use this named-sources form on About and in
PR copy.

**Homepage lede** is the same promise in English first. Source names appear
lower on the page, or as the labeled links they already are:

The most comprehensive free college data we know of — the report each
college publishes about itself, plus the government’s own numbers, in one
public place.

Counselors and IR still recognize the product from “the report each college
publishes.” Do not open the homepage with three proper nouns.

Labels on numbers stay as product behavior; they are not the homepage claim.

Every public page should make the promise usable, not explain how the
archive is built.

---

## Personas (primary)

Journalists and developers are welcome. They are not a fourth homepage
audience. Point them at `/api` (already in the header), GitHub, and
methodology.

### Parents and students

They may never have heard “Common Data Set.” They want accurate, current
numbers they can act on: is this school in range, what does it cost, can I
compare without a paywall or a student-data profile.

Say “the report the college publishes” once, then use the numbers. Link the
original file. Do not teach the template. The homepage follows this rule
in the lede; it does not lead with Common Data Set, IPEDS, and Scorecard.

### College counselors

They know the CDS. Don’t teach sections A–J unless the page is the CDS
explainer. Help them stay current, share a year URL instead of a 47-page PDF,
and see coverage gaps and year-over-year shifts.

### Researchers and IR

They want peer files, definitions, bulk access, a way to contribute a missing
year, and data they can take elsewhere. They care about sourcing, schema, and
the API — not extractor war stories.

**Recipes (`/recipes`)** are this persona first, data analysts with them.
Counselors and journalists are welcome; they are not the H1. Analytical
jargon is fine when it names the method (yield, C2, Carnegie class, draw
rate, submission rate as a proxy). Field IDs belong in chips, captions, and
the method note — not as the hook. Still no extractor war stories
(Docling, AcroForm, drain, “extracted,” how we parsed the PDF).

---

## Three voice layers

Keep plumbing visible to people who want it. Don’t put it on the front door.

| Layer | Audience | Lives on | Says |
|---|---|---|---|
| **Product** | Parents/students first; counselors second | `/`, `/about`, school pages, `/browse`, `/match`, `/coverage`, cards, empty states, metadata | Benefit, then action, then one plain-English source line |
| **Professional** | IR, researchers, analysts; counselors who want the trail | `/recipes`, `/methodology/*`, `/api`, rewritten source-story pages | The question, the method, the number, the source — jargon is fine when it earns the point. Still no extractor war stories |
| **Operator** | Maintainers and OSS contributors | `/pipeline-observation`, `docs/`, `docs/known-issues/`, GitHub | Extractors, Docling vs AcroForm, Harvey Mudd C1, drains, heartbeats |

**Harvey Mudd / Docling C1 shift** stays in `docs/known-issues/` and may
appear in a methodology appendix. It does not belong on
`/about/common-data-set`.

**Three sources** belong in the named-sources promise (school CDS, IPEDS,
College Scorecard) used on About and in PR copy. The homepage lede uses
the gloss (“the report each college publishes,” “the government’s own
numbers”). On every page, keep labels so a federal outcome is not mistaken
for the school’s own report. Methodology may say that in one sentence.
Homepage ledes do not name the three systems.

---

## Chrome

- **Footer:** keep Pipeline, like a status link. Fine. GitHub belongs here
  and in More, not in the header or the homepage hero.
- **More menu:** do not treat Pipeline as a product destination. Wave 1
  drops it from secondary nav and leaves it in the footer. More is Compare,
  Coverage, Recipes, About, GitHub.
- Public name for `/browse` is **Compare** — nav, buttons, later browse
  chrome. Do not say “Browser” on product pages.
- **Primary nav stays Match / Schools / API.** API is load-bearing in the
  header: researchers, and parents who will point an LLM at a public
  endpoint to build a college list. Do not demote it into More.

---

## Page protocol

1. Name the primary persona (and secondary, if any).
2. Outline: **benefit → what to do on this page → what the number is → one
   source line → link for people who want the trail.**
3. Never start a product lede with process (extractors, field IDs, “print
   form,” “canonical,” “drain”). Recipes may name section IDs (C2, Part H)
   in the method line; they still do not open on extractors.
4. Update title, description, and JSON-LD in the same change as the prose.
5. Read-aloud test: would a parent, a counselor, and an IR director each
   know what to do in 20 seconds?
6. Homepage ledes use the gloss, not three proper nouns. When claiming
   current or accurate, say “as the school published it.”

Design-system rule **never hide a source** still holds. Added rule: **never
make the pipeline the story on a product page.**

---

## Glossary

Product copy prefers the right-hand column. Operator docs may use the left.

| Avoid on product pages | Prefer |
|---|---|
| extracted / extractor / Docling / AcroForm / Tier 4 | read from the school’s file |
| canonical year | 2025–26 (the actual year) |
| drain, manifest, projection, browser row, comparer, Browser | recently added files; schools you can compare; Compare |
| “files a school has since taken down” | historical years; the original file (do not advertise takedowns) |
| “we keep three sources separate” / “federal context you can tell apart” | the three public sources, in one place |
| CDS field IDs in a product lede (`C.101`, `AP_RECD_1ST_MEN_N`) | the fact in English; IDs in tables, recipe chips, or API docs |
| “a 47-page PDF is not a database” as the hook | what a family or counselor can *do* with the report |

Keep saying **Common Data Set** on the explainer and in SEO. School and
year pages are a Google door: people search `{name} Common Data Set`.
Put that phrase in the title, description, and first sentence. H1 can
be the school name. Define the term once, then talk about the numbers.

When claiming **current** or **accurate**, anchor to “as the school
published it.” Never imply we verified the school’s math. Parents want
accurate numbers; our honest posture is the school’s own report, labeled,
with the original file one click away. Federal figures stay labeled as
federal.

---

## Differentiation (say this, not rankings)

Versus commercial college-search products: no account required, we don’t
build or sell a student profile, the original school file is linked, this is
not a ranking product.

Versus a raw CDS PDF: a shareable year page, comparable fields, coverage you
can see. Do not say “files a school has since taken down” on product pages.

Versus IPEDS Data Center or Scorecard alone: those are one federal system
each. We put the school’s own report next to them, in public, without a
paywall. If a school hasn’t published its own report, you still get the
federal numbers. That fallback is load-bearing: most in-scope schools have
no archived CDS, so “search a school and see current numbers” is only true
because of it.

---

## Shipping copy

1. Draft in a copy deck (`docs/copy/`), not in a 400-line React diff.
2. Anthony reads as a reader.
3. Then implement in `web/`.
4. Small PRs per wave. Wave 1 (front door) shipped 2026-08-27. Wave 2
   product surfaces shipped 2026-08-27. Wave 3 Recipes (IR and data
   analysts first) copy is locked in
   [`docs/copy/wave-3-recipes.md`](../docs/copy/wave-3-recipes.md).

Wave 4 (methodology, API) waits until Wave 3 lands.
