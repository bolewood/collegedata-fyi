# collegedata.fyi — Voice

Editorial source of truth for public copy. Visual rules stay in
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md). If they conflict, this file wins
for *what we say*; the design system wins for *how it looks*.

Locked 2026-08-26 after Anthony’s Wave 1 decisions.

---

## Site promise

School-published college facts, kept public and current, with the original
file one click away — plus federal context you can tell apart.

That sentence is the product. Every public page should make it usable, not
explain how the archive is built.

---

## Personas (primary)

Journalists and developers are welcome. They are not a fourth homepage
audience. Point them at `/api`, GitHub, and methodology.

### Parents and students

They may never have heard “Common Data Set.” They want accurate, current
numbers they can act on: is this school in range, what does it cost, can I
compare without a paywall or a student-data profile.

Say “the report the college publishes” once, then use the numbers. Link the
original file. Do not teach the template.

### College counselors

They know the CDS. Don’t teach sections A–J unless the page is the CDS
explainer. Help them stay current, share a year URL instead of a 47-page PDF,
and see coverage gaps and year-over-year shifts.

### Researchers and IR

They want peer files, definitions, bulk access, a way to contribute a missing
year, and data they can take elsewhere. They care about sourcing, schema, and
the API — not extractor war stories on the explainer page.

---

## Three voice layers

Keep plumbing visible to people who want it. Don’t put it on the front door.

| Layer | Audience | Lives on | Says |
|---|---|---|---|
| **Product** | Parents/students first; counselors second | `/`, `/about`, school pages, `/browse`, `/match`, `/recipes`, `/coverage`, cards, empty states, metadata | Benefit, then action, then one plain-English source line |
| **Professional** | IR, researchers, counselors who want the trail | `/methodology/*`, `/api`, rewritten source-story pages | Sourcing, definitions, portability, school-authored vs federal — still English |
| **Operator** | Maintainers and OSS contributors | `/pipeline-observation`, `docs/`, `docs/known-issues/`, GitHub | Extractors, Docling vs AcroForm, Harvey Mudd C1, drains, heartbeats |

**Harvey Mudd / Docling C1 shift** stays in `docs/known-issues/` and may
appear in a methodology appendix. It does not belong on
`/about/common-data-set`.

**Three sources** is a product *behavior* (labels on numbers), not a lecture.
Methodology gets one sentence: so a federal outcome is not mistaken for a
school-published aid figure.

---

## Chrome

- **Footer:** keep Pipeline, like a status link. Fine.
- **More menu:** do not treat Pipeline as a product destination. Wave 1
  should drop it from secondary nav and leave it in the footer.
- Primary nav stays Match / Schools / API.

---

## Page protocol

1. Name the primary persona (and secondary, if any).
2. Outline: **benefit → what to do on this page → what the number is → one
   source line → link for people who want the trail.**
3. Never start a product lede with process (extractors, field IDs, “print
   form,” “canonical,” “drain”).
4. Update title, description, and JSON-LD in the same change as the prose.
5. Read-aloud test: would a parent, a counselor, and an IR director each
   know what to do in 20 seconds?

Design-system rule **never hide a source** still holds. Added rule: **never
make the pipeline the story on a product page.**

---

## Glossary

Product copy prefers the right-hand column. Operator docs may use the left.

| Avoid on product pages | Prefer |
|---|---|
| extracted / extractor / Docling / AcroForm / Tier 4 | read from the school’s file |
| canonical year | 2025–26 (the actual year) |
| drain, manifest, projection, browser row | recently added files; schools you can compare |
| “we keep three sources separate” | labeled school-published vs federal |
| CDS field IDs in a lede (`C.101`, `AP_RECD_1ST_MEN_N`) | the fact in English, ID only in tables or API docs |
| “a 47-page PDF is not a database” as the hook | what a family or counselor can *do* with the report |

Keep saying **Common Data Set** on the explainer and in SEO. Define it in
the first sentence, then talk about the numbers.

---

## Differentiation (say this, not rankings)

Versus commercial college-search products: no account required, we don’t
build or sell a student profile, the original school file is linked, this is
not a ranking product.

Versus a raw CDS PDF: a shareable year page, comparable fields, coverage you
can see, historical files the school may have taken down.

Versus IPEDS Data Center / Scorecard sitewide: school-authored current
figures when the school publishes them; federal context kept labeled.

---

## Shipping copy

1. Draft in a copy deck (`docs/copy/`), not in a 400-line React diff.
2. Anthony reads as a reader.
3. Then implement in `web/`.
4. Small PRs per wave. Wave 1 is the front door: homepage, About, CDS
   explainer, metadata, nav chrome.

Waves 2–4 (school pages, methodology, API) wait until Wave 1’s dialect is
stable.
