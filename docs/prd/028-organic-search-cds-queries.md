# PRD 028: Organic search for school CDS queries

**Status:** M0–M2 implemented (2026-08-17). GSC URL inspect is green on all four canaries. Query × page readout is in [028-gsc-cds-queries-2026-08.md](028-gsc-cds-queries-2026-08.md). M3 is off-page.
**Created:** 2026-08-17
**Author:** Anthony Showalter (with Claude)
**Related:** [PRD 002](002-frontend.md) (frontend SEO primitives), [PRD 009](009-last-mile-ci-and-preservation.md) (distribution push), [PRD 015](015-institution-directory-and-cds-coverage.md) (school identity pages), [PRD 019](019-cds-change-intelligence.md) (year-over-year deltas), [PRD 021](021-ipeds-coverage-layer.md) (IPEDS baseline), [PRD 024](024-share-button.md) (share / unfurls), [ADR 0004](../decisions/0004-canonical-domain-collegedata-fyi.md) (naming / CollegeData.com collision), [CDS vs Scorecard research](../research/cds-vs-college-scorecard.md), [GSC CDS memo (2026-08-17)](028-gsc-cds-queries-2026-08.md)

---

## Executive summary

The head query `[school] Common Data Set` is winnable. Google Search
Console for 16 May–14 Aug 2026 shows Virginia Tech variants as the
site's actual organic business: `#2` for `virginia tech common data set`
at ~38% CTR, and the top four queries are all VT. Harvey Mudd, with
the same templates, titles, sitemap, and JSON-LD, does not appear in
the first ten pages for the same query shape.

The difference is not on-page SEO. It is **whether the official `.edu`
is a usable answer**.

- Harvey Mudd's IR page lists recent PDFs by year, titled "Common Data
  Set", on `hmc.edu`. Google's correct result is that page.
- Virginia Tech's IR page
  (`aie.vt.edu/analytics-and-ai/common-data-set.html`) explains what a
  CDS is, then says files are "**available via request to
  aiesupport@vt.edu**." The PDFs exist in a DAM path Google can
  sometimes find; the landing page is a dead end. We are the first
  public HTML answer that actually hands over the extracted file.

Rev 1 of this PRD treated Harvey Mudd as the canary and told us not to
chase the head term. GSC falsifies that as a universal rule. The
canary is **Virginia Tech**: protect that ranking, then find other
high-demand schools whose official CDS is gated, thin, JS-only, or
email-only. Harvey Mudd remains the hard case because IR publishes a
real year-by-year HTML index, not because a PDF exists.

An indexed `.edu` PDF is Google's navigational answer for "the file
the school published." It is not a usable session. collegedata.fyi
still wins the *use* of that file: accessible HTML, extracted tables,
prior years in one place, and comparison. Cite the official link
above the fold; do not treat "PDF is indexed" as "we cannot rank."
Haverford already converts against a public PDF (see the
[August 2026 GSC memo](028-gsc-cds-queries-2026-08.md)).

The other GSC number that matters: **236K impressions, 0.7% CTR,
average position 12.2**. Almost all impressions are page-two-or-worse
queries. VT proves what happens when one school-query moves to
position 2. The work is to repeat VT, not to beat HMC.

Vercel Analytics for the same window (17 May–16 Aug 2026) shows the
demand side of that: **17.5K visitors, 30.7K pageviews**, a July 5
spike to ~1,000 visitors/day, then a new baseline of roughly 250–500
visitors/day and another lift in early August. Google is the largest
referrer (2.7K), but Bing (1.4K), DuckDuckGo (581), Yahoo (491),
cn.bing (220), and ChatGPT (188) are already in the room. Discovery
is working. **`/about` is not in the top pages.** People land on a
year page or the homepage, take the file or bounce (77%), and never
hear why the archive exists. The story pages are how we convert an
already-rising crawl into a library people stay in — and how Bing,
DDG, and ChatGPT, which do not share GSC, still get a document they
can cite.

A second, smaller ranking surface is **source literacy**. `/about`
already publishes the Uncommon Data Set framing, but it glosses CDS,
Scorecard, and IPEDS in three paragraphs. CollegeVine owns
`what is a Common Data Set`; `collegescorecard.ed.gov` owns the
navigational Scorecard query. Three deep `/about/…` pages will not
displace those official/navigational results. They can rank for the
comparison and explainer queries the About page currently cannot
support (`common data set vs college scorecard`, `what is IPEDS`,
`IPEDS vs CDS`), and they give every school page a unique prose hub
to link to. That is the SEO side-effect, not the reason to write
them. The reason to write them is that the product story is currently
too thin for the rigor of the archive.

## What we have today (measured)

Checked 2026-08-17 against live pages, Google results, a Search
Console Performance screenshot (16 May–14 Aug 2026), and a Vercel
Analytics screenshot (17 May–16 Aug 2026).

### Search Console (site-wide, last 3 months)

| Metric | Value |
|--------|--------|
| Clicks | 1.6K |
| Impressions | 236K |
| Average CTR | 0.7% |
| Average position | 12.2 |

Clicks were flat (under ~20/day) through mid-July, then rose sharply
and peaked near ~90/day in early August. Impressions ran ~2.5–5K/day
with an upward drift from late July.

Top queries in that export (all Virginia Tech):

| Query | Clicks | Impressions | CTR (approx.) |
|-------|--------|-------------|---------------|
| `virginia tech common data set` | 277 | 721 | 38% |
| `virginia tech cds` | 72 | 168 | 43% |
| `common data set virginia tech` | 58 | 161 | 36% |
| `virginia tech common data set 2024` | 33 | 65 | 51% |

Those four queries are ~440 clicks, roughly **a quarter of all organic
clicks**, from ~0.5% of impressions. Harvey Mudd does not appear in
the top-query list.

Search Console is verified. M0's "is GSC set up?" question is closed.

### Vercel Analytics (17 May–16 Aug 2026)

GSC is Google-only. Vercel is what actually arrived.

| Metric | Value |
|--------|--------|
| Visitors | 17,474 (+5.1K% vs prior period — prior was near-zero) |
| Page views | 30,696 (+2.2K%) |
| Bounce rate | 77% (up 20 points) |
| Pages / visitor | ~1.75 |

Daily visitors sat near zero through June, spiked around **5 July**
(~1,000), then held a much higher baseline (~250–500) with another
rise in early August. That lines up with GSC clicks leaving the
sub-20/day floor in mid-July.

Top pages (visitors):

| Path | Visitors |
|------|----------|
| `/schools/virginia-tech/2025-26` | 1,000 |
| `/` | 959 |
| `/schools/stanford` | 357 |
| `/schools` | 339 |
| `/schools/stanford/2017-18` | 333 |
| `/schools/texas-a-and-m-university-college-station/2023-24` | 294 |
| `/api` | 291 |

`/about` does not appear. The year page is the working SEO unit (PRD
002 was right). Historical years already convert: Stanford **2017-18**
is a top-five URL. Texas A&M 2023-24 is a second large-public year
page in the same list. Repeat-VT is not a theory.

Top referrers:

| Referrer | Visitors |
|----------|----------|
| google.com | 2.7K |
| bing.com | 1.4K |
| duckduckgo.com | 581 |
| search.yahoo.com | 491 |
| cn.bing.com | 220 |
| chatgpt.com | 188 |
| ecosia.org | 44 |

Google is not the only crawler that matters. Bing + Yahoo + DDG
together are in the same order of magnitude as Google. ChatGPT is
already a referrer; PRD 009's "LLM citability" is not hypothetical.
Story pages, `/llms.txt`, and Dataset JSON-LD have to be written for
that set, not for GSC alone.

Other notes, not to over-read:

- **89% desktop.** These are research sessions. Long-form About-tree
  pages should be designed as desktop reading (the design system
  already is). Do not ship a marketing-mobile layout. Still don't
  break 11% mobile.
- **US 58% / Singapore 21% / China 7%.** Singapore-at-21% is
  unexplained (VPN, crawlers, international students — do not treat
  it as a product-market signal until it is checked). US remaining
  majority is enough to keep writing for U.S. college search.
- **77% bounce / 1.75 pages per visitor.** Consistent with "landed,
  grabbed the PDF, left." Telling the source story is also an
  engagement bet: a year-page lead plus an About-tree link should
  raise pages/visitor. Do not chase bounce rate with popups or
  related-school carousels.

### Virginia Tech vs Harvey Mudd (the ranking experiment)

Same product, same metadata template, opposite SERPs.

| | Virginia Tech | Harvey Mudd |
|---|---|---|
| Our hub | `/schools/virginia-tech` | `/schools/harvey-mudd` |
| Our title | `{name} Common Data Set (CDS) Archive` | same template |
| Our latest year | 2025-26 (Excel, extracted) | 2025-26 (fillable PDF, extracted) |
| Docs on our hub | 14 | 16 |
| Head-query rank | **#2** (operator + GSC CTR) | **not in first 10 pages** |
| Official IR page | [aie.vt.edu/.../common-data-set.html](https://aie.vt.edu/analytics-and-ai/common-data-set.html) — CDS definition, then **email to request files** | [hmc.edu/.../common-data-set/](https://www.hmc.edu/institutional-research/institutional-statistics/common-data-set/) — year-by-year **linked** PDFs through 2025-26; a 2026-27 heading exists without an href |
| Applicant-scale (our 2025-26 extract) | 57,755 applied | 5,217 applied |
| Other HTML competitors | GradGPT visualized CDS page already ranks | CollegeVine "how to get in" essay |

Official VT copy, verbatim: "Current and historical CDS files for
Virginia Tech are available via request to aiesupport@vt.edu."

That is the product. For VT, we are not a third copy of a public PDF
index. We are the public index. For HMC, we are a third copy of a
well-published `.edu` PDF index. Latest **linked** year on both sides
is 2025-26 (checked 2026-08-17). HMC's page also has an unlinked
"2026-2027" heading; there is no PDF. That is not an archive lag.

Demand also differs: a large public flagship generates more
`[school] common data set` searches than a 900-student college. Even a
#2 Harvey Mudd rank would be small traffic. VT is both **winnable**
and **worth winning**.

### Indexing is not the failure

| Check | Result |
|-------|--------|
| Live school URL | `https://www.collegedata.fyi/schools/harvey-mudd` |
| Live year URL | `https://www.collegedata.fyi/schools/harvey-mudd/2025-26` |
| `<title>` (school) | `Harvey Mudd College Common Data Set (CDS) Archive \| collegedata.fyi` |
| `<title>` (year) | `Harvey Mudd College Common Data Set 2025-26 \| collegedata.fyi` |
| Canonical | `https://www.collegedata.fyi/schools/harvey-mudd` (www host) |
| `robots.txt` | `Allow: /`, sitemap pointer |
| Sitemap | School hub + extracted year pages included (`web/src/app/sitemap.ts`) |
| Rendering | Next.js App Router SSR / ISR (`revalidate = 3600`) |
| JSON-LD | `CollegeOrUniversity` + `DataCatalog` on school; `Dataset` + `BreadcrumbList` on year |
| `site:collegedata.fyi Harvey Mudd Common Data Set` | Returns the year page as result 1 |

PRD 002 already shipped the technical SEO primitives: unique titles,
descriptions, canonicals, OG images, sitemap, robots, Dataset markup. Those
are doing their job. Google can fetch both school pages. It ranks VT
because the official alternative fails the click; it skips HMC because
the official alternative is a better click.

### What Google ranks instead

For `Harvey Mudd Common Data Set`, page one is owned by:

1. Harvey Mudd IR: `/institutional-research/institutional-statistics/common-data-set/`
2. Harvey Mudd IR parent page and Fast Facts PDFs
3. Direct `hmc.edu` CDS PDF URLs (Google indexes the PDFs themselves)
4. Long-form admissions explainers that *cite* the CDS (CollegeVine's
   "How to Get Into Harvey Mudd") rather than hosting it

This is the expected SERP for a named institutional document. The official
`.edu` is the publisher. The PDFs contain the query phrase on every page
header. CollegeVine wins leftover intent with unique editorial. A new
archive of the same PDFs is, to Google, a third copy.

### Unique value Google cannot currently see

HMC's public IR page lists four **linked** recent years (2022-23
through 2025-26), plus an unlinked 2026-27 heading with no PDF, and
says older files are "archived in OIRE, and available on request."
collegedata.fyi currently shows **16 CDS documents** for Harvey Mudd,
latest **2025-26** — the same latest linked year as HMC. The gap that
matters is historical files the school no longer lists, plus extracted
fields / XLSX / CSV / API. It is not stated as crawlable unique prose
on the school page. The H1 is `Harvey Mudd College`. The visible page
is product cards and tables. The "16 documents, 2009–2025, including
years the school no longer publishes" sentence does not exist as a
first-screen paragraph.

One related content gap (the other was a false freshness alarm):

- **`/about` is live** ([The Uncommon Data Set](https://www.collegedata.fyi/about)).
  Rev 1 of this PRD wrongly called the essay unpublished. What is
  still missing is depth: About summarizes CDS, Scorecard, and IPEDS
  in one section each and then moves on. There is no annotated walk
  through a real CDS PDF, no Scorecard history, no IPEDS survey-component
  explainer. `/methodology` is the wrong tree — it documents how the
  product *cards* are built, not what the underlying federal and
  school-authored sources are. The Show HN draft
  (`docs/blog/show-hn-draft.md`) remains unposted.

### Authority and brand (off-page)

- Domain registered / first commit: **2026-04-11**. Four months old as of
  this PRD. Google treats new domains conservatively for competitive
  queries.
- TLD is `.fyi`. Honest per ADR 0004; it does not inherit `.edu` trust.
- ADR 0004 already recorded the **CollegeData.com** collision: a
  decades-old commercial college-search brand owns the generic "college
  data" query class. Unbranded searches for college data do not accrue to
  us.
- Inbound links are thin. PRD 009 already named this: "Archive usefulness
  ∝ discoverability" and scoped a Show HN / GSC distribution push. The
  Show HN draft is still unposted.
- No public author byline on school/year pages. E-E-A-T for a data archive
  is "who extracted this, from which file, when" — we have provenance in
  the product, but the first screen does not say it in English.

### On-page specifics that make the loss worse (not the root cause)

These would not beat `hmc.edu` by themselves. They do make it harder to
rank for adjacent queries and for Google to understand the unique offer.

1. **H1 does not contain "Common Data Set."** School H1 is the institution
   name; year H1 is the institution name with "Common Data Set {year}" as
   a `<p>`, not an H1. Titles are good; headings are not aligned.
2. **No unique intro copy.** Every school page is the same widget stack.
   Near-duplicate templates at corpus scale look like a scraper, not a
   library.
3. **URL does not contain the query phrase.** `/schools/harvey-mudd` is
   correct identity design (PRD 015). It is a weaker exact-match URL than
   HMC's `/common-data-set/`. Do not rename school slugs to chase this.
4. **Apex → www is a 307.** `layout.tsx` documents it. For SEO this should
   be a 301. Minor, but free.
5. **Sitemap gaps.** `/browse` and some recipes (`waitlist-odds`,
   `endowment-draw-rate`) are indexable but omitted from `sitemap.ts`.
6. **Internal links are nav, not topical.** Recipes mention Harvey Mudd
   (acceptance-vs-yield) but do not systematically point at the year page
   with descriptive anchors. No "Common Data Set" concept hub. No Claremont
   Colleges cluster.
7. **Root layout sets `alternates.canonical: "/"`.** Child
   `generateMetadata` overrides it today (verified live). Keep that
   contract tested; a merge bug here would canonicalize every school to
   the homepage.

## Problem

Parents, counselors, journalists, and IR staff search `[school] Common Data
Set` when they want the document.

When the school publishes it well, they get the `.edu` and never see us
(Harvey Mudd). When the school gates the file behind email, a JS app, or
a DAM path with no indexable landing page, Google will rank a public
HTML archive **second** — and people click it (Virginia Tech, ~38% CTR).

Today almost all of that second case is accidental. One school produces
a quarter of clicks. 236K impressions at average position 12.2 are
sitting on page two. We do not yet know which of those impressions are
VT-shaped (gated official source + real search demand) versus HMC-shaped
(excellent official source we should not fight).

## Goals

1. **Protect Virginia Tech.** Do not regress `/schools/virginia-tech`
   or its year pages. It is the existence proof and the current
   organic business.
2. **Repeat VT.** Find high-demand schools whose official CDS is
   gated, email-only, JS-only, or otherwise a poor Google result, and
   make our hub the obvious public HTML answer — still citing the
   official page.
3. Put a crawlable, source-linked explanation of *what this page is* on
   every school hub and year page: years archived, extract/download
   formats, link to the official IR source, and (when true) that the
   school currently asks the public to email for the file.
4. Branch `/about` into three long, source-rigorous pages — Common Data
   Set, College Scorecard, IPEDS — that show the silo problem with
   annotated real documents rather than glossing it. Rank for the
   explainer/comparison queries those pages honestly answer. Do not
   treat them as a blog.
5. Use Search Console as the operator loop: query × page × position,
   starting with `common data set` / `cds` filters, not a marketing
   suite.

## Non-goals

- **Do not try to outrank a well-published official `.edu` PDF index**
  (Harvey Mudd, Penn State, UVA, and similar). Cite and link those.
  Do **compete** when the official page is an email gate or otherwise
  fails the searcher.
- **Do not rename the domain, drop `.fyi`, or collide with CollegeData.com
  trademarks.** ADR 0004 stands. Brand-query work is "collegedata.fyi",
  not "college data".
- **Do not manufacture per-school SEO essays** or spun "How to get into X"
  content. That is CollegeVine's game and it fights the source-linked
  posture.
- **Do not add `/common-data-set/[school]` duplicates** of existing school
  URLs. Identity stays `/schools/{school_id}`. Optional redirects from
  well-known aliases are fine; a second canonical is not.
- **Do not buy links, guest-post networks, or directory spam.**
- **Do not noindex year pages** to "consolidate" onto the school hub.
  Year pages are the SEO answer pages (PRD 002).
- **Do not wait on LLM-citation work as a substitute.** `/llms.txt` and
  facts endpoints remain useful; they do not fix this Google SERP.
- **Do not outrank `collegescorecard.ed.gov` or `nces.ed.gov/ipeds`**
  for the navigational queries `college scorecard` and `IPEDS`. Cite
  them. Compete for `what is the common data set`, `CDS vs Scorecard`,
  `IPEDS vs CDS`, and similar literacy queries.
- **Do not put the source-story pages under `/methodology`.** That
  index is "how the cards are built." Source literacy hangs off
  `/about`.
- **Do not ship a blog index, CMS, or authoring workflow.** Three
  static App Router pages plus About as the hub.
- **Not a Search Console product.** Use the existing Google Search Console
  property as an operator tool; do not build a GSC clone.

## Users and jobs

### Parent or student

"I searched Harvey Mudd Common Data Set because someone told me that's
where the real numbers live. I want the latest admit rate, SAT band, and
a file I can download — and I would stay if the page also showed last
year and a spreadsheet."

### Counselor

"I want one URL I can send a family that has the extracted tables, not a
47-page PDF, and that still links to the official source so I am not
the one vouching for a scrape."

### Journalist or researcher

"I need the 2015 CDS and the school no longer lists it. Search should
find the archive year page, not a 'contact IR' note. If I am writing
about the data system itself, I want one durable URL that explains
CDS vs Scorecard vs IPEDS with examples, not a vendor blog."

### IR professional

"If this archive ranks, it must not impersonate my office. Link to my
page, label the extract, show the archived original."

## Product principles

1. **Cite the official source above the fold.** Every school hub and year
   page that has a known IR URL must link it. We are an archive and
   extract, not the publisher.
2. **Unique copy must be true of this school, generated from data we
   already have.** Counts, year spans, "school currently lists N years;
   we archive M", format list, last-verified date. No invented narrative.
3. **Gated official pages are the wedge, then historical files.** When
   the school tells Google "email us," we should be result two (or one).
   When the school lists fewer years than we archive, say so. Both are
   true unique value; VT shows the first one already converts.
4. **Freshness is a ranking feature when a newer file actually exists.**
   If the school has published a newer CDS than we have extracted, the
   page should say that rather than imply we are current. Do not treat
   an IR heading without an href as a published year. HMC's 2026-27
   heading (checked 2026-08-17) is that case: no PDF, archive current.
5. **No prestige copy.** Do not write "elite STEM college" filler to pick
   up CollegeVine-style queries.
6. **Do not impersonate IR.** Ranking for VT because they hide the file
   is complementary. Copy must still say the numbers are the school's,
   with a link to `aie.vt.edu` (or whoever), not "the official Virginia
   Tech Common Data Set hosted here."

## Query taxonomy (what we will and will not chase)

Split by **official-source quality**, not by school prestige.

| Query class | Example | Should we win? | Why |
|-------------|---------|----------------|-----|
| Head term, gated official page | `virginia tech common data set` | **Yes — already #2. Protect and repeat.** | Official result fails the searcher |
| Head term, excellent official page | `Harvey Mudd Common Data Set` | No (cite them) | `.edu` PDF index is correct |
| Current-year file, gated official | `virginia tech cds 2025-26` | Yes | We host XLSX/PDF they make you email for |
| Historical year | `Harvey Mudd Common Data Set 2015` / `virginia tech common data set 2024` | Yes | VT 2024 already converts in GSC (33 clicks). Stanford `/2017-18` is a top Vercel URL (333 visitors). |
| Extract / spreadsheet | `{school} CDS excel` | Yes | Official pages are usually PDF-only or email-only |
| Specific fact + CDS | `{school} waitlist CDS` | Yes, over time | Year page headings |
| Comparison | `{school} vs {school} CDS` | Yes, later | No official page does this |
| Concept, CDS | `what is the common data set` | Yes — `/about/common-data-set` | CollegeVine owns a thin explainer; we can be the rigorous one |
| Concept, Scorecard | `college scorecard vs common data set` | Yes — `/about/college-scorecard` | Do not chase navigational `college scorecard` (ed.gov) |
| Concept, IPEDS | `what is IPEDS` / `IPEDS vs CDS` | Yes — `/about/ipeds` | Do not chase navigational `IPEDS` (nces.ed.gov) |
| Brand | `collegedata.fyi …` | Yes, already | |

M1 on-page copy still ships for every school. **Prioritization of
attention and internal links** follows VT-shaped schools (gated or
thin official source × search demand), not Harvey Mudd.

## What ships

### M0 — Operator baseline (no product UI)

1. Search Console is verified (screenshot 2026-08-17). Remaining:
   URL inspect `/schools/virginia-tech`, `/schools/virginia-tech/2025-26`,
   `/schools/harvey-mudd`, `/schools/harvey-mudd/2025-26`. Export
   queries matching `common data set|cds` for 3 months, sorted by
   impressions, with page and average position. That export is the
   VT-shaped opportunity list.
2. Change apex → www from **307 to 301** (Vercel / DNS / middleware —
   wherever the 307 is currently issued).
3. Add missing indexable URLs to `sitemap.ts`: `/browse`,
   `/recipes/waitlist-odds`, `/recipes/endowment-draw-rate`, and any
   other public recipe already routed. M2 pages join the sitemap when
   they ship (`/about/common-data-set`, `/about/college-scorecard`,
   `/about/ipeds`).
4. Add a regression test that school and year `generateMetadata`
   emit a path-specific canonical, so the root `canonical: "/"` cannot
   leak. Include `virginia-tech` in that fixture.

### M1 — Make the unique offer crawlable (the actual ranking work)

**School hub** (`/schools/[school_id]`):

- Keep the school name as the visual headline if design requires it.
  Add a visible H1 or H1-equivalent that includes "Common Data Set"
  without becoming keyword soup. Preferred pattern: H1 remains
  `{name}`; an immediately following `h2` or lead sentence is
  `{name} Common Data Set archive, {first}–{latest} ({n} documents).`
  Implementation should follow `web/DESIGN_SYSTEM.md`; this PRD does
  not restyle the page.
- Add a short **source-linked lead** (2–4 sentences, data-generated,
  no editorial flourish) covering: years archived, latest extracted
  year, download formats (PDF / XLSX / CSV), and a link labeled as
  the school's own CDS page when `discovery_seed_url` (or equivalent)
  is known.
- When we can detect it cheaply, mention that the school currently
  lists fewer public years than we archive. Do not scrape HMC's IR
  page on every request; a static comparison is not required in M1
  if we can only truthfully say "n archived years, {range}."
- If a newer **linked** official file is known-missing, show
  coverage-honest copy ("latest archived year is {year}") rather
  than implying currency. An unlinked year heading is not a miss
  (HMC 2026-27 as of 2026-08-17).
- For VT-shaped schools, the lead may say the school's own page
  currently asks the public to request the file, and that this page
  is the archived source plus extract. Only if that is true of the
  seed URL we link. Do not guess.

**Year page** (`/schools/[school_id]/[year]`):

- Promote "Common Data Set {year}" into the heading structure so the
  H1 or a single H1+subtitle pairing contains both the school name
  and the phrase. Do not ship two H1s.
- Add one lead sentence: this is the archived source file plus the
  extracted field tables, with a download link and a link back to the
  official IR page.
- Add in-page headings for the high-demand CDS slices already
  rendered (admissions, testing, waitlist, aid) so queries like
  `Harvey Mudd waitlist CDS` have a fragment to rank. Reuse existing
  section labels; do not invent new analysis.

**Copy rules:** every sentence must be generable from manifest /
coverage / document rows. If a fact is missing, omit the sentence.
No "prestigious," no "top STEM," no admissions advice.

### M2 — Three source-story pages off `/about`

`/about` stays the product narrative ([live](https://www.collegedata.fyi/about)).
It currently spends one paragraph each on CDS, Scorecard, and IPEDS,
then pivots to "what you can do now." That gloss is the problem. Branch
three long static App Router pages from it. `/methodology` is
untouched: those URLs stay "how the cards are built."

| URL | Title pattern | Primary queries |
|-----|---------------|-----------------|
| `/about/common-data-set` | What is the Common Data Set | `what is the common data set`, `common data set explained` |
| `/about/college-scorecard` | College Scorecard, and why it is not a CDS | `college scorecard vs common data set`, `college scorecard vs IPEDS` |
| `/about/ipeds` | What IPEDS is, and what it cannot replace | `what is IPEDS`, `IPEDS vs CDS`, `IPEDS vs college scorecard` |

Writing standard: the rigor of [PRD 021](021-ipeds-coverage-layer.md)
and the original Uncommon Data Set essay
(`docs/blog/the-uncommon-data-set.md`), not marketing. Measured claims,
named schools, named field IDs, named federal tables. Every screenshot
captions the archived source file it came from and links to the live
year page. No prestige adjectives. No "chance me."

**About becomes the hub.** Replace the three gloss paragraphs with a
short "three sources" block that links to these pages. Keep the rest of
About (what you can do, what makes it different, open source, credits).
Do not paste the long pages back into About.

#### a) `/about/common-data-set`

Job: make a reader *feel* why a 47-page PDF on a random IR URL is not
a data system, then show the canonical template and what this archive
does with it.

Must include:

1. What the CDS Initiative is (College Board, Peterson's, U.S. News;
   link `commondataset.org`). Sections A–J in one table, in English.
2. **Annotated screenshots of real archived PDFs**, not stock. Minimum
   set, all from files we host:
   - A fillable AcroForm page (Harvey Mudd 2025-26 is the documented
     ground-truth case — named fields, deterministic extract).
   - The same *kind* of table after flattening / scan / kerned year
     numerals, so the reader sees why Docling-on-the-wrong-file
     corrupts C1. Use `docs/known-issues/harvey-mudd-2025-26.md` as
     the caption source; do not re-litigate it as if the live extract
     is still wrong.
   - A school that publishes XLSX (Virginia Tech 2025-26) next to a
     school that hides the file behind email (same school's IR page).
   - A page-header that repeats "Common Data Set 2025-2026" five times
     so the silo is visible: the document is a print form, not a
     database.
3. The publishing mess, with real examples we already have in the
   essay draft: fillable PDF, flattened PDF, scan, XLSX, DOCX, HTML,
   Box/SharePoint, year-in-the-URL lies, section-only files. This is
   the pain. Show it; do not summarize it.
4. What "extracted" means here: canonical field IDs (C.101, H.2A),
   provenance back to the archived bytes, spreadsheet download. Link
   VT and HMC year pages with descriptive anchors.
5. What we are not: not the publisher, not IPEDS, not Scorecard.

Figures live in-repo (`web/public/about/` or `docs/prd/assets/028/`),
cropped to the relevant table, alt text that states school / year /
section. Do not screenshot third-party commercial UIs.

#### b) `/about/college-scorecard`

Job: history and current shape of the federal consumer tool, then an
honest join story — why Scorecard earnings/debt/net-price exist, why
they lag the CDS year on the school page, why we never blend them into
one unlabeled number.

Must include:

1. Origin: Obama-era College Scorecard as a consumer-information
   product, not a guidebook survey. Link `collegescorecard.ed.gov`.
2. What it actually is now: a join of IPEDS + NSLDS + Treasury/IRS
   earnings + FSA, per
   [docs/research/cds-vs-college-scorecard.md](../research/cds-vs-college-scorecard.md).
   One table of "Scorecard is good at / CDS is good at / neither."
3. Coverage vs CDS: Title IV mandate vs voluntary school PDF. This is
   why a school with no public CDS still has a Scorecard row.
4. Lag, with a worked example on a live school page (Harvey Mudd or
   Virginia Tech): the CDS year on the admissions card vs the Scorecard
   vintage note already rendered in the UI. Screenshot that pairing
   and caption the vintages. Do not imply Scorecard is "the latest
   CDS."
5. Why it belongs next to CDS on this site: outcomes and net price
   families ask for, labeled as federal, never silently mixed into
   §C or §H.
6. What the official Scorecard site does better (program-level CIP
   earnings, the .gov tool) and what we do instead (source-linked
   school page + API). Cite ed.gov; do not impersonate it.

#### c) `/about/ipeds`

Job: make IPEDS legible to a counselor who has heard the acronym, and
to a journalist who is about to download the wrong Access file.

Must include:

1. NCES and IPEDS as the statistical system of record for U.S.
   postsecondary institutions. Link `nces.ed.gov/ipeds`. UNITID as
   the join key we actually use.
2. How data gets in: survey components (HD, IC, ADM, EF, GR, SFA, F),
   provisional vs final, the Access-database reality for recent
   releases. This is the silo on the federal side — not a PDF, a
   stack of tables with dictionaries.
3. Worked examples from the live federal baseline table (PRD 021):
   pick 3–4 facts on Virginia Tech or Harvey Mudd (admit rate Near
   CDS, endowment Not CDS-equivalent, locale Direct). Screenshot the
   school-page table with source column visible. Caption
   `source_table` / `source_variable` / release type.
4. What IPEDS cannot replace: current-year wait-list, ED vs other
   rounds, H2A merit counts, the school-authored PDF as
   accountability. Quote PRD 021's non-goals in public language.
5. Why we load it: directory-scale coverage when no public CDS
   exists; historical series; finance (PRD 027) that CDS never had.
6. How to tell CDS from IPEDS on a school page. One annotated
   screenshot of a page that shows both, with the source labels
   circled.

**Shared page chrome (all three):**

- Serif H1, `max-w-2xl` or `max-w-3xl` reading column, same tokens as
  About. Read `web/DESIGN_SYSTEM.md`. Figures may go slightly wider
  than the text column. Captions in the meta/mono style.
- Unique `<title>` and meta description. Canonical under `/about/…`.
- `Article` JSON-LD (`headline`, `datePublished`, `author` as the
  project / Bolewood, `about` pointing at the official source org).
- Breadcrumb: About / {page}. Footer and About hub link all three.
- In-body links to 3–5 school or year URLs. **Virginia Tech must
  appear on the CDS page** (email-gate example). Harvey Mudd appears
  as the fillable-PDF / extraction example. Scorecard and IPEDS pages
  use the same two schools so a reader can cross the three stories
  on one institution.
- Last-reviewed date in the header (these pages will rot when NCES
  ships a new Scorecard dictionary or CDS template year).

**SEO expectation (honest):** the crawl is already compounding
(17.5K visitors in three months, multi-engine). These pages will not
move the Harvey Mudd head term and will not replace repeating VT.
They are how we turn year-page landings into a library: unique
indexable prose, internal links, something Bing/DDG/ChatGPT can cite
besides a stats widget, and a reason not to bounce at 77%. Measure
in GSC by landing page `/about/*` **and** in Vercel as `/about`
entering the top-pages list plus pages/visitor moving off 1.75.
Do not hope they steal VT clicks.

Optional later, not M2: a Harvey Mudd year-over-year note only if
PRD 019 public events already support it. Still no hand-authored
"how to get into X" article.

### M2.5 — VT-shaped school inventory (operator + light data)

Not a new page type. A ranked worklist:

1. From the GSC query export: school-name CDS queries with impressions
   and average position 5–20 (page-two-ish, already in the index).
2. For each, fetch the official IR URL we already store. Classify:
   public PDF index / email-or-request gate / JS-only / 404 / unknown.
3. Cross with demand proxies we already have (applicants, enrollment,
   browser-row existence). Prefer large publics with gated pages.
4. First 10 on that list get a manual SERP check and, if our coverage
   is stale, a finder/archive pass **before** copy tweaks. Freshness
   beat HMC; it must not lose VT. Stanford and Texas A&M year pages
   are already in Vercel's top pages — include them in the first
   SERP checks even if GSC is Google-only.

GradGPT already ships visualized per-school CDS URLs (they appear on
the VT SERP). Speed matters more than heading tags for this slice.

### M3 — Off-page, the work PRD 009 already named

Technical on-page work will not create domain authority. M3 is
distribution, not HTML:

1. Post the Show HN (draft already at `docs/blog/show-hn-draft.md`).
2. Add the site to the obvious citation surfaces that accept primary
   sources: Wikipedia *Common Data Set* page (if a reliable secondary
   source exists first — do not cite ourselves as the RS), IR
   community lists, relevant GitHub / academic README mentions.
3. Ask journalists / researchers who already use the API to link the
   school page they used, not only the homepage.
4. Keep linking official IR pages; some of those offices will link
   back if the archive is clearly complementary (historical +
   extract) rather than competitive.

M3 is operator work with a checklist, not an engineering milestone
that "ships" in a PR. Record outcomes in CHANGELOG / this PRD's
status line when something lands.

### M4 — Later, only if M1–M3 hold VT and move two more schools

Do not build these until VT stays #1–#3 for the head query **and** at
least two more gated-official schools show GSC clicks, *or* a
historical-year HMC query reaches the first 3 pages:

- Comparison URLs (`/compare/harvey-mudd/caltech`) as indexable
  pages, not only the API.
- Peer-cluster pages (Claremont Colleges CDS).
- Field-level year pages (`.../2025-26/waitlist`) only if year-page
  headings plus Search Console query data show a real demand slice.
- Programmatic FAQ / speakable schema. Easy to spam; skip until
  unique copy exists.

## What does NOT ship

- Rank-tracking SaaS, Ahrefs/Semrush subscriptions as a product
  dependency (operator may use them; the PRD does not require them).
- Per-school LLM-generated "insights" paragraphs.
- Changing `school_id` slugs or adding a parallel `/cds/` tree.
- noindex on directory-only schools is already correct (PRD 015);
  leave it.
- Discover (`/discover`) stays noindex.
- A blog, CMS, or `/methodology/common-data-set` alias of the About
  tree. Three static pages. About remains the hub.

## Implementation notes

- Lead copy belongs in the school/year server components so it is in
  the first HTML. Do not hide it behind a client island.
- Prefer one shared `archiveLead(school)` helper over per-page string
  soup, and snapshot-test **Virginia Tech** (gated official), Harvey
  Mudd (excellent official), one thin school, and one directory-only
  school (noindex, no lead claiming an archive).
- Official IR link: use the curated discovery seed / IR URL already
  in `schools.yaml` (`https://www.hmc.edu/institutional-research/common-data-set/`
  for Harvey Mudd — note the live IR page is currently
  `/institutional-research/institutional-statistics/common-data-set/`;
  do not ship a 404). Resolve URL accuracy as part of M1, not as a
  crawler. The seed 301s to the live path today; either URL is fine
  as a link target.
- Freshness: HMC is not behind. Latest linked year on both sides is
  2025-26; the IR "2026-27" line has no href. When a real newer file
  appears, the weekly archive probe should pick it up. School-page
  copy should only disclose an actual archive lag, not a CMS stub.
- Design: read `web/DESIGN_SYSTEM.md` before adding the lead or the
  About-tree pages. School-page leads are typesetting. The three
  source pages are long-form with figures — still paper, ink, and
  one quiet green. No blue, no marketing cards.
- Annotated screenshots: capture from files we archive or from our
  own school-page UI. Store under `web/public/about/` (or
  `docs/prd/assets/028/`) with a filename that includes school-id,
  year, and section. Alt text is a sentence, not "screenshot".
- After M2 ships, school-page leads may link "What is a Common Data
  Set" to `/about/common-data-set`. Do not inline the essay on every
  school page.

## Verification

Canaries:

- **Protect:** Virginia Tech (`virginia-tech`) — head term already ranks.
- **Hard case:** Harvey Mudd (`harvey-mudd`, IPEDS `115409`) — excellent
  official page; do not use as the go/no-go for head-term ranking.
- **Repeat:** first school from the M2.5 gated-official list.

### M0

- [ ] Search Console URL inspection: VT hub, VT 2025-26, HMC hub, HMC
      2025-26 — "URL is on Google" or documented exclusion.
- [ ] Query export (`common data set|cds`, 3 months) saved under
      `scratch/` or `.context/` with position and landing page.
- [ ] `curl -I https://collegedata.fyi/schools/virginia-tech` → **301**
      to the www equivalent.
- [ ] `/sitemap.xml` contains `/browse` and the missing recipes.
- [ ] Automated test: year page metadata canonical is path-specific
      for both `virginia-tech/2025-26` and `harvey-mudd/2025-26`.

### M1

- [ ] View-source on the school hub contains the phrase
      "Common Data Set" in a heading or the first visible paragraph,
      plus a document count and year span.
- [ ] Official IR link present and non-404.
- [ ] Year page heading structure contains both school name and
      "Common Data Set {year}".
- [ ] Still links to archived PDF and spreadsheet downloads.
- [ ] No new invented adjectives in the lead (manual read of Harvey
      Mudd, Harvard, and one small school).

### M2

- [ ] `/about` links to all three source pages; the gloss paragraphs
      no longer pretend to be the full story.
- [ ] Each page has a unique title, canonical, and at least three
      annotated figures with captions that name school, year, and
      archived source.
- [ ] CDS page includes Harvey Mudd (fillable) and Virginia Tech
      (email gate and/or XLSX).
- [ ] Scorecard page shows a vintage lag example from a live school
      page; does not claim Scorecard is current-year CDS.
- [ ] IPEDS page shows `source_table` / `source_variable` on a live
      federal baseline screenshot; states what IPEDS cannot replace.
- [ ] Sitemap includes the three URLs.
- [ ] No `/methodology/common-data-set` duplicate.

### Success metrics (90 days after M1+M2, not a launch gate)

Directional. Do not treat as engineering pass/fail.

1. **No VT regression.** `virginia tech common data set` stays in the
   top 3 with CTR in the 30%+ range. Year-page and hub titles still
   contain "Common Data Set".
2. **Repeat.** At least two more school head queries (gated-official
   class) produce GSC clicks. Target: VT is no longer the only school
   in the top-10 query report.
3. Site-wide CTR moves up from 0.7% as more queries leave position
   ~12. Average position moving from 12 toward 8 is the leading
   indicator; click count is the lagging one.
4. Harvey Mudd: `site:` still returns our page. A historical-year or
   spreadsheet query in the first 3 pages is a bonus, not the bar.
   Head-term page-10 absence is accepted.
5. **Literacy pages.** GSC shows impressions for at least one of
   `what is the common data set`, `IPEDS vs CDS`, or
   `college scorecard vs common data set`, landing on `/about/…`.
   Vercel: `/about` or an `/about/…` child enters the top-pages
   list; pages/visitor moves up from ~1.75. Zero GSC impressions
   after 90 days means inspect indexing before rewriting into
   listicles.
6. **Do not lose the non-Google crawl.** Bing/DDG/Yahoo/ChatGPT
   referrers stay in the mix. A Google-only title tweak that
   wrecks the year page for Bing is a regression.

## Failure modes

| Failure | Why it happens | Mitigation |
|---------|----------------|------------|
| VT ranking dies after a copy/heading change | We touched the only page that converts | Snapshot tests; SERP check before merge; protect VT in QA |
| We "optimize" HMC H1, still invisible on page 10 | Excellent `.edu` competitor | Do not use HMC head-term rank as go/no-go |
| Duplicate-content filter across 4,000 school pages | Leads are identical except for names | Generate from real per-school facts |
| Google treats us as a scraper | We host their file and extract it | Always link the official page; JSON-LD `creator` is the school |
| VT IR objects to ranking #2 | We made their gated file public | Principle 1 + 6; ADR 0008; the file was already on a DAM URL |
| GradGPT (or similar) takes the VT slot | Visualized CDS pages on the same SERP | Freshness + spreadsheet download + source link; do not wait on a blog |
| Literacy pages become listicles | SEO temptation on `what is IPEDS` | Keep PRD 021 rigor; if GSC is zero, inspect indexing before rewriting |
| Unlinked IR heading looks like we are stale | HMC's 2026-27 block is a paragraph, not a PDF | Do not write "we're behind"; wait for an href. Optional later: detect heading-without-link as coverage signal |
| CollegeData.com confusion | ADR 0004 known cost | Brand as collegedata.fyi in titles |

## Open questions

1. **Closed: Search Console is verified.** Remaining: the query ×
   position export for `cds` / `common data set`.
2. **Should year pages use H1 = `{name} Common Data Set {year}`** and
   demote the visual school name, or keep the design-system school
   name as H1 with a strong H2? Design consultation before merging.
   A/B this on a non-VT school first.
3. **Do we have a durable official-IR URL field** that is accurate
   enough to render, or only a discovery seed that can drift (HMC's
   seed vs. the live `/institutional-statistics/common-data-set/`
   path; VT's public page vs. DAM PDFs)? If seeds 404, M1 must not
   link them.
4. **How many schools are VT-shaped?** Need the M2.5 classification
   against our seed URLs. Do not guess a percentage in this PRD.
5. **Closed: HMC 2026-27 is not a pipeline miss.** IR heading with no
   `<a href>`; guessed upload URLs 404; archive last verified 2026-08-15
   on the linked 2025-26 file. Next weekly probe should catch the PDF
   when they attach one.
6. **Wikipedia / Wikidata**: only with a reliable secondary source.

## Recommendation

Do not treat Harvey Mudd as the SEO canary. Treat **Virginia Tech as
the ranking we already have** and **gated official pages as the
repeatable pattern**.

Ship M0 (GSC export + 301 + sitemap) and M1 copy on all school/year
pages, with VT in the test fixtures so we cannot regress the only
query that pays. Run M2.5 next — that list, not H1 tweaks, is where
the next 277-click query comes from.

Write the three `/about/…` source pages as M2, in parallel with that
list, not instead of it. The visitor curve is already up. `/about` is
already the essay and is not being read. These pages are the depth
it currently skips, and the thing a 77% bounce session never sees.
They are how a compounding crawl becomes a library — a trust bet
that should also show up in Bing, DDG, and ChatGPT, not only GSC.

Still do not promise page one for Harvey Mudd. That `.edu` is doing
its job. The 236K impressions at position 12 are the queue of schools
where the `.edu` is not. Stanford 2017-18 and Texas A&M 2023-24 are
proof that queue already pays when we are the usable HTML.

## References

- GSC Performance, last 3 months (16 May–14 Aug 2026), screenshot in
  `.context/attachments/` (2026-08-17)
- Vercel Analytics, ~17 May–16 Aug 2026 (17.5K visitors, 77% bounce,
  multi-engine referrers, VT/Stanford/Texas A&M year pages), screenshot
  in `.context/attachments/` (2026-08-17)
- Live **protect** canary: [Virginia Tech hub](https://www.collegedata.fyi/schools/virginia-tech),
  [2025-26](https://www.collegedata.fyi/schools/virginia-tech/2025-26)
- Official VT page (email gate): [aie.vt.edu common-data-set](https://aie.vt.edu/analytics-and-ai/common-data-set.html)
- Live **hard** canary: [Harvey Mudd hub](https://www.collegedata.fyi/schools/harvey-mudd),
  [2025-26](https://www.collegedata.fyi/schools/harvey-mudd/2025-26)
- Official HMC publisher: [HMC Common Data Set](https://www.hmc.edu/institutional-research/institutional-statistics/common-data-set/)
- SERP competitor already on VT: [GradGPT Virginia Tech CDS](https://www.gradgpt.com/common-data-set/virginia-tech)
- [PRD 021 IPEDS coverage](021-ipeds-coverage-layer.md)
- [CDS vs College Scorecard research](../research/cds-vs-college-scorecard.md)
- Live About (the published Uncommon Data Set framing):
  https://www.collegedata.fyi/about
- Draft long essay (source for CDS-page examples, not a second URL):
  `docs/blog/the-uncommon-data-set.md`
- Show HN draft (still unposted): `docs/blog/show-hn-draft.md`
