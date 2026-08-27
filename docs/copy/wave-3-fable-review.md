# Wave 3 Fable review

Verdict: **ship with patches**

Patches applied to `wave-3-recipes.md` 2026-08-27 (must-fixes 1–7 and
should-fixes 1–8; nits 1–4 came along because they were already in the
replacement strings). Independently checked against live TSX: Harvey
Mudd / Notre Dame / William & Mary are 2025-26; Fig. 1 still says
“2024-25 cycle, 18 schools”; “§ Scale to all 697 schools” is still the
API header; `/recipes` Not-yet-built has the four IR items only; the
extraction-audit line is README-only. No TSX in this change.

The audience pivot is right and most of the surgery lands. But the deck has one
false premise about the live site, two source-conflation errors an IR director
will catch on first read, one year claim that is factually wrong for a school
in the seed, and it walks past the single most dishonest denominator on any of
these pages. Fix the strings; the structure survives.

Read as: IR director, then analyst hitting the API, then counselor off a
More-menu link. Locks honored — no parent gloss demanded, no C2/yield/Carnegie
dings unless dishonest, no TSX.

---

## Must-fix

### 1. Index card, acceptance "For" line — you printed the persona ranking

Quoted: "IR comparing peer yield; analysts extending C1 via the API.
Counselors second."

Failure: "Counselors second." is deck-internal audience triage leaking onto
the page. The lock says counselors are welcome and not the H1 — that is
guidance for the writer, not copy to publish. A counselor who followed the
More-menu link reads a sentence telling them they rank. It fails your own
counselor read-aloud ("the page isn't talking to a family" — it also shouldn't
be talking *about* the visitor). Bonus sloppiness: you don't "extend C1" — C1
is a CDS section; you extend the seed.

Replacement:

> IR comparing peer yield; analysts pulling every complete C1 row from the
> API; counselors calibrating reach/match/safety.

### 2. Index card, test-optional "For" line — C9 is not a policy

Quoted: "IR and policy analysts tracking effective C9 policy, not the
brochure."

Failure: "Effective C9 policy" conflates the sections this recipe exists to
keep apart. C9 is the submission count; C8 is the written policy; the recipe's
whole method is reading effective policy *from* C9 because C8 alone doesn't
tell you. The one audience this page is for will notice the deck itself can't
keep C8 and C9 straight. This is exactly the "C9 submission rate is not the
written C8 policy" fact the deck was warned about.

Replacement:

> IR and policy analysts reading effective policy from C9 submission rates;
> C8 is the written version.

### 3. "Written disclosures lie" — the recipe's own method note says otherwise

Quoted (deck, taglines): keep "submission rate as a proxy… written
disclosures lie, enrollment numbers don't." And later: "'Written disclosures
lie' can stay in the method note — it's the point of the proxy."

Failure: three problems, any one of which kills it. (a) The recipe's own
write-up, caveat 3: a school can be formally test-optional and effectively
test-required — "The two measures are complementary, not contradictory."
The tagline calls the same measure a lie. That is an internal contradiction
between the hook and the method the hook advertises. (b) C8 and C9 come from
the *same school-authored filing*. If written disclosures lie, an analyst has
no reason to trust the C9 counts either — the line saws off the branch the
chart sits on. (c) Site posture is "as the school published it," never
implying we verified or falsified the school's claims. Accusing every C8
disclosure of lying is the inverse violation. The proxy's point is that
written policy underdetermines practice — say that.

Replacement (index tagline, final clause):

> Uses the submission rate as an honest proxy for effective test-optional
> policy — C8 states the rule; C9 counts what enrolled first-years did.

Replacement (method note, if the thought stays):

> Written policy underdetermines practice; the submission rate is the outcome
> measure.

The live meta description repeats the phrase ("Written disclosures lie;
enrollment numbers don't.") — it dies in the same change. Replacement meta:

> C9 SAT submission rate, year by year, for seven well-documented schools.
> Effective test-optional policy, read from what enrolled first-years did —
> C8 is the written version.

### 4. Acceptance lede — "a complete 2024-25 row" is false for the seed

Quoted: "Acceptance rate (C1) against yield, for eighteen schools with a
complete 2024-25 row."

Failure: the method note says the seed is three hand-checked ground-truth
anchors plus fifteen API rows, and — its own caveat 3 — Harvey Mudd, one of
the three anchors, is on a **2025-26** cycle. So at least one of the eighteen
does not have a 2024-25 row, and the anchors aren't API rows at all. The
analyst persona will run the page's own query with `canonical_year=eq.2024-25`
and get a set that doesn't match the chart. The old lede was vague; the new
one is vague *and* wrong, which is worse.

Replacement:

> Acceptance rate (C1) against yield, for an eighteen-school seed — three
> hand-checked anchors plus fifteen rows from the public API, most on the
> 2024-25 cycle. Four quadrants: selective-and-desired, loved-despite-
> openness, selective-but-second-choice, accessible-and-optional. The XLSX
> starter and API query extend it past the seed.

### 5. Deck silence on "§ Scale to all 697 schools" — the lying denominator

Quoted (live page, unaddressed by the deck): "§ Scale to all 697 schools"

Failure: the query under that header filters
`acceptance_rate=not.is.null&yield_rate=not.is.null`. Per the recipe's own
coverage caveat, C1 completeness runs 50–60% on Tier 4 documents — the query
returns roughly 400–500 rows, not 697. This is the exact "analyst hits the
API and notices a lying denominator" failure, on the page the deck rewrites,
in a section header — which is chrome the deck declared in scope ("only the
chrome and the sentences around them"). The deck says "Keep the quadrant
copy. Keep CDS C1 · B1 · B22 chips" and never looks at the biggest overclaim
on the page.

Replacement:

> § Scale to every school with a complete 2024-25 C1 row

### 6. Not-yet-built — the item you're replacing isn't on the page, and the replacement is a pipeline demo

Quoted (deck, "Now"): "Not-yet-built includes 'Audit your own school's
extraction'". Quoted (deck, "Proposed"): "Replace 'Audit your own school's
extraction' with: Audit your own school's published numbers against the
original file."

Failure: the live `/recipes` Not-yet-built box has four items — H2A/H4,
C9/C11, F × J, longitudinal — and no extraction item. The string lives in
`docs/recipes/README.md` (operator layer, where it's legal). So the proposed
"replace" is actually an *addition* to the product page — and the added item
is "audit the extract" with the banned word sanded off. It fails the deck's
own definition of a recipe ("one analytical question… not a pipeline demo"):
its subject is whether our pipeline copied the PDF correctly. That is
operator QA, not an IR question.

Replacement: cut the item from the `/recipes` proposal entirely; the four
live items are all real IR questions. If the deck also intends to clean the
README (it commits write-ups to drop war stories in the same change), the
README line becomes:

> **Audit your school's numbers.** An IR-staff-facing recipe: pull your
> school's values from the public API, compare them against the source PDF,
> and flag discrepancies for correction.

### 7. Detail-page metadata left on the old copy

Quoted (live acceptance meta, unaddressed): "Two numbers, eighteen schools
worth of context: how selective a school looks on paper (acceptance rate)
against how selective it actually is (yield)."

Failure: VOICE page protocol #4 — title, description, and JSON-LD update in
the same change as the prose. The deck replaces the acceptance lede and the
test-optional H1/lede but proposes no meta for either page, leaving the
acceptance description on the exact sentence the deck just deleted from the
lede, and the test-optional description on the parent wink plus "disclosures
lie" (fixed in must-fix 3). Search snippets are where IR first meets these
pages.

Replacement (acceptance meta description):

> Acceptance rate (C1) against yield for an eighteen-school seed, with the
> API query and XLSX starter that extend it to every school with a complete
> C1 row.

Wait-list and endowment metas already match their proposed prose; leave them.

---

## Should-fix

### 1. Index meta — two sources named, three used

Quoted: "Worked examples from Common Data Set and IPEDS filings — method,
chart, and a public API query. Built for institutional research and
analysts."

Failure: the wait-list recipe buckets on College Scorecard context and wears
a Scorecard chip on its own page. The index description claims CDS + IPEDS
only. Also "institutional research and analysts" yokes a function to a
person.

Replacement:

> Worked examples from Common Data Set filings and federal data — method,
> chart, and the public API query behind each. Built for institutional
> researchers and analysts.

### 2. Index lede — "a chart you can run"

Quoted: "One question, the method in sight, a chart you can run, and the API
query behind it."

Failure: you run the query; you read the chart. The deck's own definition
says "a chart or table you can operate."

Replacement:

> One question, the method in sight, a chart you can operate, and the API
> query behind it. Written for IR and analysts. Counselors are welcome.

### 3. Test-optional lede — "seven schools with a long series"

Quoted: "for seven schools with a long series."

Failure: the write-up documents long series for Yale (2009-10 → 2024-25) and
Caltech (2002-03 → 2020-21) only; MIT is quoted from 2021-22. Asserting "a
long series" for all seven overdescribes the universe, and the analyst who
pulls the data sees it. The shipped phrase was already honest.

Replacement:

> for seven well-documented schools.

### 4. Test-optional lede — bands stated against the wrong series

Quoted: "≥85% behaves like test-required; 10–85% is genuinely optional; under
10% behaves like test-blind."

Failure: per the method note, the bands classify **combined SAT + ACT**
submission capped at 100%; the chart lines are SAT-only. The lede attaches
the thresholds to the SAT line with no caveat, so any ACT-leaning school an
analyst adds reads as test-blind when it isn't. Twenty-second read-aloud
currently delivers the question and the universe but not this caveat, and
it's the recipe's biggest one.

Replacement (append to lede):

> Bands score combined SAT + ACT submission, capped at 100%; the lines plot
> SAT only.

### 5. Wait-list H1 — ruled: it reads as a field-ID lede

Quoted: "Wait-list outcomes, *from C2.*"

Failure: the brief asked for a judgment; here it is. It passes the lock's
letter — "wait-list outcomes" is English, "from C2" is a source. But the
italic lands on the field ID, making C2 the typographic hook, which is the
thing the lock keeps out of hooks; and "outcomes" does no work the page name
("Wait-list odds") doesn't already do. It's a caption wearing an H1's font
size. There's a real IR headline available in the C2 triplet itself.

Replacement:

> Offered, accepted, *admitted.*

Fallback if Anthony wants the noun-plus-source shape: keep the words, move
the italics off the field ID — "Wait-list *outcomes*, from C2."

### 6. Wait-list lede — federal buckets pass as CDS

Quoted: "Offer, accept, and admit counts from CDS C2, across every complete
row we can query, bucketed by selectivity, control, size, and Carnegie
class."

Failure: control, size, and Carnegie class come from the directory and
Scorecard joins, not from C2. The sentence opens "from CDS C2" and never
hands off, so the whole method reads school-authored. The Scorecard chip
mitigates; a method-forward lede should still label the federal half —
"federal numbers stay labeled federal" is a Wave 1 lock.

Replacement:

> Offer, accept, and admit counts from CDS C2, across every complete row in
> the corpus, bucketed by C1 selectivity and by federal control, size, and
> Carnegie class.

### 7. Endowment stat relabel — cramped value, and the deck missed the rot

Quoted: "Rows | {n} school-years, {k} schools"

Failure: the ledger's grammar is one big number in the strong slot, detail in
the small line — the neighbors ("Latest median", "Above 7%") all follow it.
Stuffing "{n} school-years, {k} schools" into the value slot breaks the row.
And the deck leaves the live small line's hardcoded "across five years"
untouched; the page already computes the fiscal-year span, and the string
goes stale the day FY2025 lands.

Replacement: label "Rows"; value "{n}"; small line "{k} schools,
FY{min}–FY{max}".

### 8. Write-up cleanup has no worklist

Quoted: "GitHub write-ups in `docs/recipes/` may keep SQL; they still drop
extractor war stories in the same change as the pages."

Failure: "in the same change" with no named lines is how it doesn't happen.
These pages link "Read the full write-up →", so IR lands directly on Tier 4
lore. Name the cuts: acceptance-vs-yield caveats ¶1 ("Tier 4 flattened
PDFs… the cleaner or an LLM fallback"), test-optional caveat 1
("extraction-noise outlier… Tier 4 (flattened-PDF) extraction"), wait-list
caveat sentence ("over-filled by Tier 4 extraction"). API parameters
(`extraction_status=eq.extracted`) are code and stay.

Replacement: add that enumerated list to the deck's "Not in this deck"
paragraph so the change is checkable.

---

## Nit

### 1. Bare surname on first reference

Quoted: "Inspired by Fernandez's May 2026 WSJ story."

Failure: first reference to a working reporter gets a first name; the live
page has it right.

Replacement: "Inspired by Roshan Fernandez's May 2026 WSJ story."

### 2. Mixed comparators in the band sentence

Quoted: "≥85% … 10–85% … under 10%"

Failure: symbol, range, then a word. Pick one register.

Replacement: "≥85% behaves like test-required; 10–85% is genuinely optional;
<10% behaves like test-blind."

### 3. "Starter workbook" vs. the artifact's name

Quoted: "The starter workbook and API query extend it past the seed."

Failure: every link on the page says "XLSX starter." One artifact, one name.
(Already applied in the must-fix 4 replacement.)

Replacement: "The XLSX starter and API query extend it past the seed."

### 4. "Every complete row we can query"

Quoted: "across every complete row we can query"

Failure: "we can query" is a shrug. The deck legalized "corpus" on these
pages for exactly this job. (Already applied in the should-fix 6 replacement.)

Replacement: "across every complete row in the corpus"

---

## What holds

- The pivot itself: IR-first "For" lines, killing "students deciding whether
  test-optional is real" and "stay emotionally invested," dropping "PRs
  welcome" from the lede while keeping the contribute path in the footer.
- Test-optional H1 "SAT submission as *effective policy.*" — names the
  method, kills the parent wink, and is not a field-ID hook.
- Wait-list lede's spine: "flagged as data-quality caveats, not dropped
  silently" and "the numbers here are from the filings, not the article" are
  exactly the professional register.
- Endowment page: H1, the "reason to look closer, not proof of trouble"
  caution, and IPEDS F2 · Part H · provisional-vs-final all stand.
- Keeping "eighteen schools" in sight as a coverage caveat — right instinct;
  only the year claim needed surgery.

## Do not reopen

- Gloss-first homepage; named sources on About.
- `/browse` is Compare; API stays in the header.
- No takedown advertising.
- "As the school published it"; we never imply we verified the school's math.
- Federal numbers stay labeled federal.
- Common Data Set in school/year SEO.
- Wave 3 audience lock: Recipes are IR and data analysts first; counselors
  and journalists welcome, not the H1.
- Analytical jargon that earns the point (yield, C2, Carnegie class, draw
  rate, submission rate as proxy) stays; extractor war stories stay banned.
- "Corpus" allowed on Recipes; still banned on parent-first product pages.
- Field IDs in chips, captions, and method lines — not as hooks.
- No rankings.
- No TSX until Anthony signs.
