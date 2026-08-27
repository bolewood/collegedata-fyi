# Wave 3 copy deck — Recipes

Read this as IR, then as a data analyst, then as a counselor who followed
a link. Do not review it as a React diff. Wave 1 and Wave 2 are on `main`.

**Locked 2026-08-27 (Anthony):** Recipes are IR and data analysts first.
Analytical jargon is fine when it conveys the point of the recipe (yield,
C2, Carnegie class, draw rate, SAT submission rate as a proxy). Extractor
war stories are not (Docling, AcroForm, drain, “extracted,” how we parsed
the PDF). Counselors and journalists are welcome; they are not the H1.

Locked from Waves 1–2 (do not reopen): gloss-first homepage; `/browse` is
Compare; API in the header; no takedown advertising; “as the school
published it”; Common Data Set in school/year SEO.

Fable review 2026-08-27: **ship with patches.** Must-fixes and the
should-fixes that survived a code check are applied below. Full write-up:
[`wave-3-fable-review.md`](wave-3-fable-review.md).

**Not in this deck:** live TSX. Sign the prose, then we implement.
Methodology and API docs wait for Wave 4. Discover waits (soft-launch,
unindexed). GitHub write-ups in `docs/recipes/` may keep SQL; they drop
extractor war stories in the same change as the pages. Named cuts:

- `acceptance-vs-yield.md` caveats ¶1: “Tier 4 flattened PDFs… the cleaner
  or an LLM fallback”
- `test-optional-tracker.md` caveat 1: “extraction-noise outlier… Tier 4
  (flattened-PDF) extraction”
- `waitlist-odds.md`: “over-filled by Tier 4 extraction”

API parameters (`extraction_status=eq.extracted`) are code and stay.

---

## What a recipe is

A worked example: one analytical question, a chart or table you can
operate, the method in sight, a copy-paste API query. It is not a
counselor explainer and not a pipeline demo.

Ban on these pages: extracted, extractor, Docling, AcroForm, drain,
projection (the pipeline kind), “audit the extract.”

Keep when they earn the point: yield, wait-list offer / accept / admit,
Carnegie class, control, SAT submission rate, draw rate, Part H,
provisional vs final, C1 / C2 / C8 / C9, F2. “Corpus” is allowed here —
it means every school with that field on file, not a convenience sample.

---

## Recipes index (`/recipes`)

**Primary:** IR and analysts. Secondary: counselors, reporters.

### Now

- Title: Recipes
- Description: “Worked examples of what you can do with the collegedata.fyi
  CDS and federal-data archive…”
- H1: Worked *examples.*
- Lede: “What you can do with the archive… If you want to contribute one,
  PRs welcome.”
- Card “For” lines still lead with students and parents (except endowment)
- Wait-list tagline: “corpus-wide” is fine; audience is not
- Not-yet-built (live `/recipes`): four IR items (H2A/H4, C9/C11, F × J,
  longitudinal). “Audit your own school's extraction” is in
  `docs/recipes/README.md` only — do not add it to the product page.

### Proposed

**Meta**

- Title: Recipes
- Description: Worked examples from Common Data Set filings and federal
  data — method, chart, and the public API query behind each. Built for
  institutional researchers and analysts.

**H1:** Worked *examples.* (keep)

**Lede** (italic serif):

> One question, the method in sight, a chart you can operate, and the API
> query behind it. Written for IR and analysts. Counselors are welcome.

Drop “PRs welcome” from the lede. Keep the GitHub contribute link in the
not-yet-built footer, where people who want to add a recipe actually look.

**Card “For” lines** — IR first. Do not print “Counselors second.”

| Recipe | For |
|---|---|
| Acceptance rate vs. yield | IR comparing peer yield; analysts pulling every complete C1 row from the API; counselors calibrating reach/match/safety. |
| Test-optional tracker | IR and policy analysts reading effective policy from C9 submission rates; C8 is the written version. |
| Wait-list odds | Enrollment managers and IR. C2 offer / accept / admit, bucketed. |
| Endowment draw-rate | IR, college-finance reporters, trustees. IPEDS F2 Part H estimate. |

**Taglines** — keep the analytical ones. Cut parent therapy.

- Acceptance: keep the four-quadrant scatter. Fine.
- Test-optional: drop “written disclosures lie.” Replacement:

> Uses the submission rate as an honest proxy for effective test-optional
> policy — C8 states the rule; C9 counts what enrolled first-years did.

- Wait-list: keep C2, selectivity, control, size, Carnegie class. Drop
  “stay emotionally invested.”
- Endowment: keep. Already IR-first.

**Not yet built**

The live box has four IR questions (H2A/H4, C9/C11, F × J, longitudinal).
Keep those. Do **not** add “audit your own school’s extraction” — that
string lives in `docs/recipes/README.md`, not on `/recipes`. If the README
is cleaned in the same change:

> **Audit your school’s numbers.** Pull your school’s values from the
> public API, compare them against the source PDF, and flag discrepancies.

---

## Acceptance rate vs. yield

**Primary:** IR comparing peers. Analysts who will hit the API.

### Now

- H1: Acceptance rate *vs.* yield
- Lede: “Two numbers, eighteen schools worth of context. A collegedata.fyi
  recipe.”
- Audience on the index: students and parents building a target list

### Proposed

H1 stays. The lede should say what the scatter is, not brand the page.
The seed is three hand-checked anchors plus fifteen API rows; Harvey Mudd,
Notre Dame, and William & Mary are on 2025-26, so do not claim all eighteen
are 2024-25.

**Description:**

> Acceptance rate (C1) against yield for an eighteen-school seed, with the
> API query and XLSX starter that extend it to every school with a complete
> C1 row.

**Lede:**

> Acceptance rate (C1) against yield, for an eighteen-school seed — three
> hand-checked anchors plus fifteen rows from the public API, most on the
> 2024-25 cycle. Four quadrants: selective-and-desired, loved-despite-
> openness, selective-but-second-choice, accessible-and-optional. The XLSX
> starter and API query extend it past the seed.

**Figure caption** (live: “Fig. 1 · 2024-25 cycle, 18 schools” — same
false year claim):

> Fig. 1 · 18-school seed, mostly 2024-25

**API block header** (live: “§ Scale to all 697 schools”). The query
filters to non-null acceptance and yield; C1 completeness is ~50–60%, so
the result is not 697. Do not hardcode a school count.

> § Scale to every school with a complete 2024-25 C1 row

Keep the quadrant copy. Keep CDS C1 · B1 · B22 chips. “Eighteen schools”
is a coverage caveat — leave it in sight (IR will ask).

---

## Test-optional tracker

**Primary:** IR and policy analysts.

### Now

- H1: Test-*optional*?
- Lede: “What share of enrolled first-years actually submitted SAT scores,
  year by year. A collegedata.fyi recipe.”
- Index audience: students deciding whether test-optional is real

The H1 is a parent wink. The chart is a policy instrument (C8/C9
submission rate as the effective-policy proxy). Write the H1 for the chart.

### Proposed

**H1:** SAT submission as *effective policy.*

**Description:**

> C9 SAT submission rate, year by year, for seven well-documented schools.
> Effective test-optional policy, read from what enrolled first-years did —
> C8 is the written version.

**Lede:**

> C9 SAT submission rate, year by year, for seven well-documented schools.
> ≥85% behaves like test-required; 10–85% is genuinely optional; <10%
> behaves like test-blind. Written policy is C8; this chart is what
> enrolled first-years actually did. Bands score combined SAT + ACT
> submission, capped at 100%; the lines plot SAT only.

Keep the three-band guide. Keep C8 · C9 chips.

Method note, if the thought stays:

> Written policy underdetermines practice; the submission rate is the
> outcome measure.

---

## Wait-list odds

**Primary:** enrollment management and IR.

### Now

- H1: Should you get your hopes up about a *wait list*?
- Lede: WSJ inspiration, then “every complete C2 wait-list row currently
  visible in the collegedata.fyi CDS corpus, with high-volume near-total
  admit rows treated as data-quality caveats.”
- Index audience: students staying emotionally invested

The H1 is a parent question. The page is a C2 tabulation. Keep the WSJ
citation (provenance); stop writing the headline for the applicant. Do not
italicize the field ID — C2 belongs in the method line, not the hook.

### Proposed

**H1:** Offered, accepted, *admitted.*

**Lede:**

> Offer, accept, and admit counts from CDS C2, across every complete row
> in the corpus, bucketed by C1 selectivity and by federal control, size,
> and Carnegie class. High-volume near-total admit rows are flagged as
> data-quality caveats, not dropped silently. Inspired by Roshan
> Fernandez’s May 2026 WSJ story; the numbers here are from the filings,
> not the article.

**Description:** keep the live string. Title/description/JSON-LD still
update in the same TSX change as the prose.

Keep “§ Reading the odds” if it still explains the success-rate
definition. Define the rate once. Don’t teach wait lists to a parent.

---

## Endowment draw-rate tracker

**Primary:** IR, finance reporters, trustees. Already closest to the lock.

### Now

- H1: How much of the endowment is being *spent*?
- Lede: estimate from federal filings; high draw rate is a reason to look
  closer, not proof of trouble. Good.
- Stat: “School-year rows”

### Proposed

H1 and caution stay. Relabel the stat to match the ledger grammar (one
big number, detail on the small line). Do not hardcode “across five years”
— the page already knows `FY{min}–FY{max}`.

> Label: Rows
> Value: {n}
> Small: {k} schools, FY{min}–FY{max}

Keep IPEDS F2 · Part H · provisional vs final — that *is* the method.

**Description:** keep the live string (it already interpolates the fiscal
year span). Title/description/JSON-LD still update in the same TSX change.

---

## Read-aloud checks

- IR on the index: “These are methods I can reuse, with the field IDs and
  an API query.”
- Analyst on wait-list: “I know the universe (complete C2 rows), the
  buckets, and the caveat.”
- Counselor who landed here: “I can still read the chart, but the page
  isn’t talking to a family.”

If the H1 could be a parent tweet, it isn’t done.

---

## Out of Wave 3

Methodology, API docs — Wave 4. Discover. School cards. Do not redesign
the charts in this wave; only the chrome and the sentences around them.
