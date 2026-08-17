# GSC memo: `[school] Common Data Set` queries (PRD 028)

**Date:** 2026-08-17
**Property:** Search Console, collegedata.fyi (www canonical)
**Window:** last 3 months (chart 2026-05-18 → 2026-08-15), Search type = Web
**Related:** [PRD 028](028-organic-search-cds-queries.md)

This memo freezes the operator exports that PRD 028 M0 asked for, plus
the reading of them. Raw CSVs live in gitignored `scratch/seo/` on the
machine that pulled them. The numbers that should survive a laptop are
here.

---

## What was checked

URL Inspection, 2026-08-17 — all four canaries **URL is on Google**:

- `https://www.collegedata.fyi/schools/virginia-tech`
- `https://www.collegedata.fyi/schools/virginia-tech/2025-26`
- `https://www.collegedata.fyi/schools/harvey-mudd`
- `https://www.collegedata.fyi/schools/harvey-mudd/2025-26`

Indexing is not the failure. Harvey Mudd’s absence from the head-term
SERP is competition, not a crawl bug.

Exports (same session, same date filter):

| Tab | What it gave us |
|-----|-----------------|
| Queries | 1,000 rows: query, clicks, impressions, CTR, average position |
| Pages | 505 rows: URL, impressions (no clicks/position in this dump) |
| Chart | Daily impressions only |
| Countries / Devices | Impression mix for the filtered slice |

The Pages and Queries totals do not match each other (GSC tables and
charts often disagree). Treat them as two views of one slice, not a
reconciliation.

---

## The slice, not the whole site

PRD 028’s site-wide screenshot was **236K impressions / 1.6K clicks /
0.7% CTR / position 12.2**. This export is the CDS neighborhood, not
that report.

| View | Impressions | Notes |
|------|-------------:|-------|
| Chart | 1,720 | 90 days |
| Pages table | 1,767 | 505 URLs |
| Queries, CDS-shaped only | ~14.3K | after dropping brand-collision, quoted IPEDS, snapshot URLs |
| Queries, CDS-shaped clicks | 668 | see school rollup below |

Daily impressions sit near zero through May, move in June, jump in
early July, and hold a higher August baseline (peak 83 on 2026-08-11).
Same shape as the PRD, smaller because this is the CDS filter.

**Countries (this slice):** United States 1,406 (~82%). Singapore is 5.
The site-wide 21% Singapore share is not CDS searchers. Keep writing
for U.S. college search.

**Devices (this slice):** Desktop 1,051 / mobile 644 / tablet 25.
More mobile than the site-wide 89% desktop mix. Still design the
About-tree as desktop reading; don’t break phones.

---

## Finding 1 — Virginia Tech is still the business

CDS-shaped query rollup for Virginia Tech:

| Query | Clicks | Impr | CTR | Pos |
|-------|-------:|-----:|----:|----:|
| virginia tech common data set | 277 | 721 | 38.4% | 3.58 |
| virginia tech cds | 72 | 168 | 42.9% | 3.84 |
| common data set virginia tech | 58 | 161 | 36.0% | 3.91 |
| virginia tech common data set 2026 | 33 | 65 | 50.8% | 2.60 |
| virginia tech common data set 2025 | 23 | 51 | 45.1% | 4.00 |
| va tech common data set | 19 | 40 | 47.5% | 5.20 |
| vt cds | 12 | 39 | 30.8% | 3.10 |
| vt common data set | 7 | 34 | 20.6% | 3.47 |
| virginia tech common data set pdf | 7 | 30 | 23.3% | 4.27 |
| vtech common data set | 7 | 16 | 43.8% | 6.88 |
| *(plus a few 2024–25 PDF variants with 0 clicks)* | | | | |

**517 clicks / 1,367 impressions / 37.8% CTR / position ~3.8** on the
school as a whole. That is ~77% of CDS-query clicks in this export.

People searching `… 2026` mean academic year 2025-26. We are at
position 2.6 with 51% CTR on that query. Do not change VT titles,
H1s, or year slugs to chase a calendar year.

Pages tab agrees on the landing URL: `/schools/virginia-tech/2025-26`
(116) then the hub (83). Year page first. PRD 002 was right.

Official source, re-fetched 2026-08-17: still the email gate at
`aie.vt.edu/analytics-and-ai/common-data-set.html`. Protect this ranking.

---

## Finding 2 — VT is no longer the only school that pays

PRD 028’s 90-day success line was “VT is no longer the only school in
the top-10 query report.” It isn’t. CDS-shaped clicks outside VT:

| School | Clicks | Impr | CTR | Pos | Official source (yaml / fetch) |
|--------|-------:|-----:|----:|----:|--------------------------------|
| Haverford | 23 | 240 | 9.6% | 4.7 | Direct PDF (`CDS_2023-2034.pdf`) |
| Brown | 20 | 461 | 4.3% | 8.8 | HTML CDS URL, 0 PDF hrefs in static source |
| UC Santa Barbara | 12 | 248 | 4.8% | 4.8 | IR research page, not a year index |
| WashU | 9 | 645 | 1.4% | 7.8 | CDS buried on a consumer-info page |
| UW Seattle | 9 | 422 | 2.1% | 6.9 | Public PDF index |
| Florida | 6 | 419 | 1.4% | 6.7 | Direct PDF seed |
| Bowdoin | 5 | 305 | 1.6% | 5.7 | IR home, not a CDS index |
| Elon | 5 | 197 | 2.5% | 6.0 | Direct upload-path seed |
| UW–Madison | 4 | 296 | 1.4% | 8.0 | HTML page, 0 PDF hrefs in static source |
| UC Merced | 4 | 18 | 22.2% | 4.3 | Small volume, already page-ish one |
| Stony Brook | 3 | 216 | 1.4% | 7.8 | Fact-book CDS directory |
| CU Boulder | 3 | 168 | 1.8% | 5.9 | Reports listing |
| Davidson | 3 | 141 | 2.1% | 4.4 | Dedicated CDS page |
| Skidmore | 3 | 126 | 2.4% | 4.8 | `facts/common/` listing |
| Gonzaga | 3 | 13 | 23.1% | 3.9 | Tiny volume, high CTR |
| Notre Dame | 2 | 224 | 0.9% | 7.5 | Seed PDF **403s** |
| Alabama | 2 | 281 | 0.7% | 8.2 | Direct PDF seed |
| Penn State | 2 | 153 | 1.3% | 6.9 | Excellent public PDF index (100+ files) |
| Howard | 1 | 290 | 0.3% | 6.8 | Public PDF index |
| Wellesley | 1 | 137 | 0.7% | 6.4 | Direct PDF seed |

Harvey Mudd does not appear as a real query. One page impression on
the hub. Indexed, not the business, not a go/no-go.

**Haverford is the second school.** Head query `haverford college
common data set`: 14 clicks, 20.6% CTR, position 4. The official file
is a PDF (mis-dated filename). Google is already treating our year
page as a usable HTML answer, and people click it. That is the VT
pattern at smaller scale.

**Brown is demand we have not converted.** Current-year queries
(`… common data set 2026`) do better (position ~6.3, ~10% CTR) than
the un-yeared head term (position ~9–10, near-zero CTR). The official
CDS URL is HTML that does not link files in the static source.

---

## Finding 3 — An indexed `.edu` PDF is not a good product

PRD 028 split schools by official-source quality: compete when the
`.edu` is an email gate; cite and do not fight when it is a
well-published PDF index (Harvey Mudd, Penn State, UVA). That split
is still the right way to **prioritize** (VT-shaped gates first). It
is the wrong way to **underrate our offer**.

A public PDF on `school.edu` is often Google’s correct *navigational*
result for “the document the school published.” It is a poor
*session*. The searcher gets a 47-page print form, no extracted
tables, no prior years in one place, no comparison, and usually no
accessible HTML. collegedata.fyi’s year page is the opposite of that:
source-linked extract, spreadsheet, archived years, and the rest of
the library one click away.

Haverford is the measured version of that argument. Their `.edu` PDF
exists and is fetchable. We still get position 4 and 20% CTR on the
head query, because the HTML archive is the better click for anyone
who wants to *use* the file rather than prove it exists.

So:

- **Do not impersonate IR.** Keep the official link above the fold.
  Copy must not say we host “the official” CDS.
- **Do not treat “PDF is indexed” as “we cannot win.”** We can win
  historical years, spreadsheet intent, comparison, and a share of
  the head term when the PDF is a bad reading experience.
- **Do not spend H1 experiments on Penn State / Howard** while VT is
  the only 38% CTR query. Freshness and the archive lead are the
  lever. GradGPT is already on the VT SERP; speed still matters more
  than heading tags for that slice.
- **Do not use Harvey Mudd head-term rank as go/no-go.** Their IR
  page is a real year-by-year HTML index. That is a different object
  from “a PDF exists at some DAM path.”

Notre Dame is the other pole: the yaml seed PDF **403s**. There is no
usable official HTML. That is a second VT if we keep the year page
fresh.

---

## Pages tab (where those queries land)

Year pages 1,308 impressions / hubs 376 / homepage 51 / `/about` 15 /
apex host 4.

Top landing URLs in the CDS slice:

| Impr | URL |
|-----:|-----|
| 116 | `/schools/virginia-tech/2025-26` |
| 109 | `/schools/penn-state/2025-26` |
| 83 | `/schools/virginia-tech` |
| 56 | `/schools/bowdoin/2025-26` |
| 51 | `/` |
| 47 | `/schools/university-of-notre-dame/2025-26` |
| 36 | `/schools/haverford-college/2025-26` |
| 36 | `/schools/uw/2025-26` |
| 35 | `/schools/washington-university-in-st-louis/2025-26` |
| 32 | `/schools/howard-university/2025-26` |
| 30 | `/schools/brown/2025-26` |
| 15 | `/about` |

Penn State’s year page is #2 by *impressions* and almost unused by
*clicks* (2 clicks, 1.3% CTR, position 6.9 on the query rollup). That
is leftover page-two inventory above a real `.edu` index, not a
second VT. Do not read the Pages tab without the Queries tab.

Homepage 51 CDS-query impressions: the query is a school CDS search
and Google showed `/`. The school/year lead copy is the fix.

`/about` already has 15 impressions in this slice. The three
`/about/…` source pages are not starting from zero.

Apex (`https://collegedata.fyi/…`) still has 4 leftover impressions.
The 301 pin in Next.js is correct; live `curl -I` already 301s.

Stanford and Texas A&M are thin in *this Google CDS-query slice*
(1–2 impressions per URL). They remain large in Vercel because Bing /
DDG / ChatGPT are in the mix. Do not let a Google-only title tweak
wreck those year pages.

---

## Noise to ignore in the 1,000-row query export

| Bucket | Approx. impressions | What it is |
|--------|--------------------:|------------|
| Not CDS | 2,699 | Acceptance-rate, tuition, enrollment, “is duke test-optional” |
| Quoted Ferris State / IPEDS | 1,500+ | Filename and field-dump searches |
| `college data` / `collegedata` | 510 | CollegeData.com collision (ADR 0004). 0 clicks, position 13–16 |
| Snapshot JSONL URLs | 332 | `collegedata.fyi/snapshots/latest/*.jsonl` at position ~1, 0 clicks. Crawlers |
| `"3,695" admitted 2020` | ~400 | People or tools searching a CDS cell value |

None of that is a school-page SEO program.

---

## Attention list (not an H1 backlog)

1. **Virginia Tech** — protect. 38% CTR, position ~3.8.
2. **Haverford** — already converting against a PDF official. Closest
   second VT. Freshness, then leave the copy honest.
3. **Brown** — demand at position 6–9; official HTML is thin/JS.
   Current-year query is the wedge.
4. **UCSB** — real CTR at position ~5. Smaller than Brown, healthier.
5. **Notre Dame** — official seed 403s. `… 2026` is closer (pos 4.8)
   than the un-yeared head term (pos 9).
6. **WashU / Florida / UW Seattle** — large impression piles, page-two
   CTR. UF `… 2026` is already position 3.8. Freshness before copy.
7. **Bowdoin / Elon / Davidson / Skidmore** — small but real clicks
   from position ~4–6.
8. **Alabama / Wellesley / Richmond / Duke / BC** — PDF-only or stale
   official files. Historical years + extract are the honest unique
   offer; the PDF may still own “download the form.”
9. **Penn State / Howard** — impressions without clicks, strong `.edu`
   indexes. Cite them. Still ship the archive lead: prior years and
   comparison are the product, not a war with `psu.edu`.
10. **Harvey Mudd** — ignore as go/no-go.

Operator next, not engineering: SERP check the first eight, archive
pass if our latest year is behind a *linked* official file, then stop.
M3 (Show HN, citations) is still off-page.

---

## What this does not change in the product

M0–M2 still ship for every school: path-specific canonicals, 301 apex
→ www, sitemap gaps, data-generated archive lead, year-page headings,
three `/about` source pages. Unique copy stays generated from
manifest facts. No prestige adjectives. No parallel `/cds/` tree.

The lead may say the school currently asks the public to request the
file **only when that is true of the URL we link** (Virginia Tech
today). For everyone else, the honest sentence is years archived,
formats, and a link labeled as the school’s own CDS page when we have
an HTML landing URL. Direct PDF seeds are not “the school’s own CDS
page.”
