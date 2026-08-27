# Wave 4 Fable review

Verdict: **ship with patches**

Patches applied to `wave-4-methodology-api.md` 2026-08-27 (must-fixes 1–7
and should-fixes 1–8; nits 1–4 applied because they were one-line).
Independently checked against live TSX and the public API: Bowdoin 2025-26
SAT 1470/1510/1540, 34.76% submit; `school_merit_profile` 335 of 488 with
H.2A02 (68.6%) vs the deck’s May 2026 244 of 365; three live “v1”s, not
one; `/api` leftover chrome is gray, not blue. No school-card TSX this
wave. The PositioningCard caption “% OF ADMITS SUBMITTED” is logged for a
later card-copy pass.

Independently checked against live TSX and the live API (2026-08-27). The
deck's premise holds: the three school-card `.meta` kickers are
"§ Academic profile," "§ Admission rounds," "§ Merit and need aid," the
index card titles already match them, and the live detail H1s are still
"Academic positioning" / "Admission strategy" / "Merit profile" — the
realignment is real work, correctly aimed. Every "Now" line I checked is
accurate except two ("blue" on `/api`, and the deck sees only one of the
three live "v1"s). Live-API checks: Bowdoin 2025-26 verifies exactly
(SAT 1470/1510/1540, 34.76% submit); `school_browser_rows` has 697 rows;
`school_merit_profile` has 488 rows with H.2A02 present on 335 (68.6%) —
verified against the API, not the paragraph. The deck's 244 of 365
(66.8%) matches only the May 3, 2026 audit note in
`docs/plans/prd-018-section-h-audit.md`. No TSX in this review.

The structure survives: kickers become H1s, changelog and pipeline lore
die, metadata moves with the prose. But the deck ships the wrong
population for C.9 three times on the page whose only job is the trail,
hardcodes a coverage fraction that is stale on arrival — against its own
written instruction — welds that fraction to a share rule computed from
different fields, and, one wave after being burned for it, again leaves
writer guidance inside a replacement string. Fix the strings; the
architecture is right.

Read as: counselor off a METHOD link, then IR, then an analyst pointing
an LLM at `/api`. Locks honored — no parent gloss demanded, no card or
chart redesign, no new docs layout, API parameters kept as code.

---

## Must-fix

### 1. "Admitted-class bands" — C.9 describes the enrolled class, and the page knows it

Quoted (deck, three separate strings): index card body "Where a student's
SAT or ACT lands in the published admitted-class bands."; positioning
description "…a school's published Common Data Set admitted-class bands.";
positioning lede "Where a student's SAT or ACT would land in the
admitted-class numbers the school published."

Failure: C.9 reports score bands and submit rates for **enrolled**
first-time, first-year students — the entering class, not the admitted
pool. Verified against the canonical schema (C.9 cohort: first-time,
first-year; "Percent Submitting SAT Scores") and against the page's own
worked example, which says "34.76% of **enrolled** first-year students
submitting SAT scores" three lines below a lede that says "admitted-class."
This is not a labeling nit: admitted-pool bands run higher than
enrolled-class bands because of yield melt, so the error changes what the
number means for the exact task the card performs — a student measuring a
score against a bar. The live page already has the disease ("admitted-class
numbers," C.8's "all admitted students," and the self-contradicting "only a
minority of enrolled students submitted… the range describes submitters,
not the full admitted class"). The deck retitles the page and walks past
it. Its own read-aloud check — "I know which CDS fields built the card" —
fails when the counselor learns the field and misreads its population. The
deck's audience note even names "C.9 submitter-only" as earned jargon; it
caught the submitter caveat and missed the bigger one standing next to it.

Replacements:

Index card body:

> Where a student's SAT or ACT lands in the score bands the school
> published for enrolled first-years. Not a chance-me.

Positioning description:

> How collegedata.fyi compares a student's scores to a school's published
> Common Data Set score bands for enrolled first-years. Not a chance-me.

Positioning lede:

> Where a student's SAT or ACT would land in the numbers the school
> published for its enrolled first-years — the entering class, not the
> admitted pool. It is not a chance-me, and it does not predict an
> admissions decision.

Kept C.8 note, patched in place: "whether score bands describe all
enrolled first-years or only the subset who submitted scores."

Kept "Why this isn't a chance-me," patched in place: "A position compares
a student's numbers with the bands the school published for enrolled
first-years." and "That means the range describes submitters, not the
full entering class."

Logged, out of this wave: the school-page `PositioningCard` caption reads
"% OF ADMITS SUBMITTED SAT SCORES" — the same error, on the card the
counselor came from. Cards are locked this wave; put the caption on the
next card-copy worklist. Do not ship a methodology page that canonizes
the caption's mistake in the meantime.

### 2. The merit coverage sentence — stale on arrival, and it counts one field while describing another

Quoted (deck, proposed): "H.2A02 is present for 244 of 365 latest 2024-25+
primary rows (66.8%). When either field is absent, or the denominator is
zero, the share is left blank."

Failure: three problems in two sentences. (a) **Stale.** 244 of 365 is
the May 3, 2026 audit figure. The live `school_merit_profile` view today
has 488 rows, 335 with H.2A02 present — 68.6% — verified against the
public API with an exact count, not against any paragraph. The deck's own
caveat says "If those counts have drifted, use the live view count…
do not hardcode a stale fraction without checking," and then hardcodes
May's fraction without checking. (b) **Conflation.** H.2A02 is the
*average dollar amount* of non-need aid; the blank-share rule the second
sentence describes is computed from H.2A01 (recipient count) divided by
H.201 (verified in the `school_merit_profile` migration). Welded into one
breath, "either field" grammatically points back at H.2A02, which is not
in the share formula. The one audience this page is for will notice.
(c) **Duplication.** The share-blank sentence already exists on the page,
verbatim and attached to the correct fields, in "What H2A does and does
not mean." Pasting the deck's replacement ships it twice.

Replacement (Missing data policy, final sentence):

> The average no-need grant (H.2A02) is currently reported for 335 of 488
> schools in the merit view (69%).

Prefer computing both counts live from the view — the API page already
interpolates its row counts from site stats; same pattern, and it is the
only durable fix for a number that has now gone stale once. If it must be
hardcoded, date it. Do not restate the share rule here; it already lives
in the H2A section.

### 3. The deck bans "v1" and then instructs the implementer to keep two of them

Quoted (deck, ban list): "Ban in prose: … 'v1.'" Quoted (deck,
positioning): "Replace 'v1 does not score' with 'This card does not
score.'" Quoted (deck, admission rounds): "Keep: … 'Read ED rates
carefully'".

Failure: the live pages contain three "v1"s and the deck sees one. The
positioning C.12 note says "v1 displays the school average beside your
entered GPA" — untouched by the deck's single replacement. The
admission-strategy "Read ED rates carefully" section — which the deck
says to keep — says "We do not estimate a general-pool ED rate in v1
because CDS does not separate those applicant groups." Both keep
instructions ship a banned token.

Replacement (C.12): "The card displays the school average beside the
student's entered GPA; GPA never contributes to academic fit because
weighted and unweighted scales are not consistently documented."

Replacement (admission rounds): "We do not estimate a general-pool ED
rate because CDS does not separate those applicant groups."

### 4. The retitled Compare example still opens with "The browser"

Quoted (deck): "'Search the curated school browser' → 'Search
latest-per-school rows (Compare)'". Quoted (live, unaddressed): "The
browser uses an Edge Function so latest-per-school ranking can account
for required fields and null answerability."

Failure: "Browser" is on the deck's own ban list and VOICE fixed the
public name as Compare. The deck sands the heading and leaves the banned
name as the first word of the first sentence underneath it. The analyst
reads the heading, then the sentence, and now has two names for one thing
— the exact confusion the rename exists to end.

Replacement:

> Compare's latest-per-school ranking runs through an Edge Function so it
> can account for required fields and null answerability. Percent and
> rate values are stored as fractions from 0 to 1.

### 5. "Fetch field values for a document" — the curl underneath fetches artifact notes

Quoted (deck): "'Fetch extracted field values for a document' → 'Fetch
field values for a document'" and the replacement paragraph ending
"Deterministic values win conflicts."

Failure: the example under that heading is
`cds_artifacts?document_id=eq.<uuid>&kind=eq.canonical&select=notes` — it
returns artifact notes, not field values. The old heading was dishonest
with the Docling context; the new one is dishonest without it. And once
the LLM-fallback sentence is cut, "Deterministic values win conflicts"
dangles — deterministic as opposed to *what*? The referent was amputated
in the same edit; what remains is pipeline lore the reader can no longer
decode. The deck declared heading-versus-example honesty in scope and
then created a fresh mismatch.

Replacement heading: "Fetch the canonical artifact for a document."

Replacement paragraph:

> Prefer `cds_fields` for field-level queries. If you need the underlying
> artifact, fetch `kind=eq.canonical` on `cds_artifacts` — the canonical
> artifact is the one the site serves.

### 6. Writer guidance inside a replacement string, again

Quoted (deck, resource blurbs): "`school_browser_rows`: Curated serving
layer for Compare, CSV, and the academic-profile / admission-rounds
cards. Do not say 'website browser.'"

Failure: "Do not say 'website browser.'" is an instruction to the writer
sitting inside copy an implementer will paste — the identical failure
shape as Wave 3 must-fix 1 ("Counselors second."). Every other bullet in
this list is pure page copy; this one ends in a style memo.

Replacement: end the blurb at "cards." Move the prohibition into the
deck's ban list where it belongs. (This blurb also silently deletes the
page's live counts — see Should-fix 4.)

### 7. The missing-value sentence enumerates three causes and omits the most common one

Quoted (deck, proposed): "A missing value is usually one of three things:
the school has no public CDS, the field is not in the friendly
dictionary, or the row failed a sanity check and was withheld."

Failure: the most common cause is none of the three — the school filed a
CDS and left the field blank. The merit methodology page documents this
at corpus scale: roughly a third of schools in the merit view have a
filing with no H.2A02 (335 of 488 report it; verified live). An analyst's
first null will usually be this fourth case, and a sentence that
enumerates three and hedges with "usually" teaches them to distrust the
enumeration — on the troubleshooting step, where trust is the product.

Replacement:

> A missing value is usually one of four things: the school has no public
> CDS, the school's filing leaves the field blank, the field is not in
> the friendly dictionary, or the row failed a sanity check and was
> withheld. The sources endpoint shows the document and the federal
> release behind the page.

---

## Should-fix

### 1. Second person survives the sections the deck keeps

Quoted (live, kept wholesale): "A position compares your numbers with
published admitted-class bands."

Failure: the deck's own rationale for rewriting the lede is "'Your
scores' addresses a parent; this page is the trail" — then it keeps "Why
this isn't a chance-me" untouched, with "your numbers" in the first line
(and "your entered GPA" in C.12, fixed en passant by must-fix 3). Half a
pronoun purge reads worse than none.

Replacement: covered by the must-fix 1 patch ("A position compares a
student's numbers with the bands the school published for enrolled
first-years.").

### 2. Admission-rounds Sources: "drop PRD 016B and Phase 0" with no replacement strings

Quoted (deck): "Sources — drop PRD 016B and Phase 0. Same serving table,
same curl."

Failure: the live section is two compound sentences where the condemned
clauses are structural halves ("…; PRD 016B adds columns to that
resource, not a new API endpoint." and "Phase 0 measurement results are
preserved in the repository's PRD findings note; the API page documents
the public columns exposed by this card."). "Drop X" with no strings is
how Wave 3 should-fix 8 happened — the implementer improvises and the
deck stops being checkable.

Replacement:

> Every school card links the archived CDS for the displayed year. The
> serving table is `school_browser_rows`, documented on the API page.

Both live sentences die; the "public columns" clause is covered by
"documented on the API page."

### 3. The proposed API lede loses the base URL and the PostgREST link

Quoted (deck, proposed lede): "Two ways in: simple no-auth JSON for
agents and scripts, and the full PostgREST archive for bulk work."

Failure: the live lede introduces `api.collegedata.fyi` in a code chip
and links the PostgREST docs. The proposal drops both; the base URL's
next appearance is buried inside resource-card URLs. For the analyst and
the LLM alike, the base URL is the single most load-bearing string on the
page — it belongs in sentence one.

Replacement: "…and the full PostgREST archive at `api.collegedata.fyi`
for bulk work." — keeping the PostgREST link on the word.

### 4. The blurb rewrites delete the page's live counts

Quoted (live `cds_fields` blurb): "{formatCount(stats.queryable_field_count)}
normalized field rows…" Quoted (live `school_browser_rows` blurb): "{n}
primary 2024-25+ rows across {k} schools, refreshed {date}."

Failure: the deck's replacement blurbs are static prose; the live ones
interpolate counts and a refresh date from site stats. Those
interpolations are the page's best honesty device — the exact anti-stale
mechanism must-fix 2 has to retrofit onto the merit page — and the deck
deletes them without comment.

Replacement (`cds_fields`): "{count} normalized field rows from 2024-25
and newer filings. Derived metrics such as `acceptance_rate` live on
`school_browser_rows`." Replacement (`school_browser_rows`): "{n} primary
2024-25+ rows across {k} schools, refreshed {date}. The curated serving
layer behind Compare, CSV export, and the academic-profile and
admission-rounds cards."

### 5. "Pin a snapshot" over three `latest` curls

Quoted (deck): "4. Use snapshots for local work → 4. Pin a snapshot"

Failure: every example under the new heading fetches the `latest` alias —
the heading commands the one thing no example shows. Curl changes are
explicitly legal where the heading is dishonest.

Replacement: keep the heading and add one pinned line to the block:
`curl 'https://www.collegedata.fyi/snapshots/<snapshot-id>/schools.jsonl'`
(the manifest names the id).

### 6. Two "start here"s

Quoted (live, kept): "Start here for MCP tools, CLIs, notebooks, and
quick integrations." Quoted (deck): "H2 Runbook → Start here"

Failure: the Simple-endpoints intro opens with "Start here…" and the H2
two sections later is now titled "Start here." A skimming reader is told
to start in two places.

Replacement (intro sentence): "The friendly surface for MCP tools, CLIs,
notebooks, and quick integrations."

### 7. The detail titles lose the word "methodology" entirely

Quoted (deck): "Title: Academic profile" (and "Admission rounds," "Merit
and need aid").

Failure: the root layout templates titles as `%s | collegedata.fyi`, so
the proposed strings render as "Academic profile | collegedata.fyi" — in
a search snippet, indistinguishable from the school-page card it
documents, and stripped of the one word professionals actually search.
The H1 is the kicker's job; the title tag can carry both.

Replacement titles: "Academic profile methodology," "Admission rounds
methodology," "Merit and need aid methodology."

### 8. Merit description drops the federal label

Quoted (deck, proposed): "…with College Scorecard net-price and outcome
context."

Failure: federal numbers stay labeled federal is a Wave 1 lock, and
metadata is where search meets the page. The on-page lede keeps "federal
College Scorecard"; the description should not be the one surface that
lets Scorecard pass unlabeled.

Replacement: "…with federal College Scorecard net-price and outcome
context."

---

## Nit

### 1. "If a future card uses" — roadmap voice in kept copy

Quoted (live, kept): "If a future card uses a CDS year more than three
years old, the scoring result carries a stale-data caveat."

Replacement: "If the newest archived CDS for a school is more than three
years old, the card carries a stale-data caveat."

### 2. There is no blue on `/api`

Quoted (deck): "restyle `/api` off gray/blue Tailwind onto paper/ink
tokens."

Failure: the live links already use `--forest`; the leftover chrome is
gray. The restyle work is real; the diagnosis should be accurate so the
implementer isn't hunting for blue that isn't there.

### 3. The second live stat dies silently

Quoted (live, unmentioned in the proposal): "effective first-year merit
answerability was 252 of 365 (69.0%)."

Failure: dropping it is a defensible simplification; not saying so reads
as oversight. One deck line: "The effective-answerability stat goes too."

### 4. The italic device lands on an acronym

Quoted (deck): "H1: The public *API.*"

Failure: every other Wave 4 H1 italicizes a lowercase noun ("built,"
"profile," "rounds," "aid"); italicizing a three-letter all-caps acronym
in the serif face is typographic noise, not emphasis.

Replacement: "The public API." — roman throughout, or italicize
"public."

---

## What holds

- The spine of the wave: all three H1-to-kicker realignments, verified
  against the live components. The counselor who leaves "§ Admission
  rounds" now lands on "Admission rounds." That was the brief, and it's
  right.
- Metadata proposed in the same change for every page whose prose changes
  — the Wave 3 must-fix 7 lesson, learned and applied.
- The API description fix: "Common Data Set filings and federal data" is
  the right-size umbrella for the two-of-three source conflation the
  deck correctly caught in the live meta.
- The kill list: "now exposes," "Runbook," "projected," "V1 friendly
  dictionary," "extraction results," the Docling paragraph, PRD 016 /
  016B / Phase 0. This is the layer discipline the wave exists for.
- Keeping the Bowdoin worked example — verified accurate against the live
  API (2025-26; 1470/1510/1540; 34.76% submitting). The one hardcoded
  worked example on these pages is the one that's still true.
- "Which rates CDS will not support" in the admission-rounds description;
  the C.22 EA honesty; "we take no legal position on ED"; NBER as
  methodological context and D'Amico as a pointer, not a finding.
- Merit lede kept, and "What H2A does and does not mean" kept — the
  understates-mixed-packages caveat is the most valuable sentence on the
  page.
- `.eq("extraction_status", "extracted")` and query parameters kept as
  code; field lists keep `extracted_at` / `extraction_status`.
- Restyle scope: tokens only, forest links, catalog untouched, no new
  docs layout.

## Do not reopen

- Gloss-first homepage; named sources on About.
- `/browse` is Compare; API stays in the header.
- No takedown advertising.
- "As the school published it"; we never imply we verified the school's
  math.
- Federal numbers stay labeled federal.
- Common Data Set in school/year SEO.
- Recipes are IR-first (Wave 3, shipped).
- Analytical jargon that earns the point stays; extractor war stories
  stay banned on these pages. Field IDs and table names are allowed at
  this layer; API parameters are code.
- Harvey Mudd / Docling: `docs/known-issues/` and a methodology
  *appendix* only. The `/api` Docling cut is correct — don't relitigate
  it into an appendix demand.
- No parent gloss on methodology or `/api`.
- School cards and charts ship as-is this wave. The `PositioningCard`
  caption ("% OF ADMITS SUBMITTED") is logged under must-fix 1 for a
  future card-copy pass, not smuggled into this one.
- URL slugs stay `/methodology/positioning` and
  `/methodology/admission-strategy` even though the H1s change; slug
  churn is not copy.
- Discover stays out.
