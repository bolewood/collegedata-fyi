# Wave 4 copy deck — Methodology and API

Read this as a counselor who clicked METHOD on a school card, then as IR,
then as someone pointing an LLM at `/api`. Do not review it as a React
diff. Waves 1–3 are on `main`. This wave wraps the public-voice project.

**Audience.** Methodology and `/api` are the professional layer: counselors
who want the trail, IR, researchers, developers. Parents using an LLM are
welcome on `/api`; they are not the methodology H1. Jargon is fine when it
names the method (ED residual, H2A, C.9 submitter-only). Extractor war
stories are not (Docling, AcroForm, drain, “extracted,” Tier 4, how we
parsed the PDF). Field IDs and table names belong here.

Locked from Waves 1–3 (do not reopen): gloss-first homepage; `/browse` is
Compare; API in the header; no takedown advertising; “as the school
published it”; Common Data Set in school/year SEO; Recipes are IR-first;
Harvey Mudd / Docling stays in `docs/known-issues/` (and may appear in a
methodology *appendix*, not in card-method prose).

Fable review 2026-08-27: **ship with patches.** Must-fixes and should-fixes
are applied below. Full write-up:
[`wave-4-fable-review.md`](wave-4-fable-review.md). Anthony asked to wrap
the voice project; this deck is the implementable source.

Logged for a later card-copy pass (not this wave): `PositioningCard`
caption “% OF ADMITS SUBMITTED SAT SCORES” — C.9 is enrolled first-years,
not admits.

**Not in this deck:** Discover (soft-launch, unindexed). School-card
redesign. Chart redesign. Changing curl examples except where the heading
or surrounding sentence is dishonest. API query parameters
(`extraction_status=eq.extracted`) are code and stay. Do not invent a new
docs layout.

---

## What these pages are

Methodology: the trail behind three school-page cards. One question per
page — what the card uses, what it does not, what the number is not.

API: two public surfaces (no-auth JSON for agents; PostgREST for bulk).
Same archive the site uses. Cite the source next to the number.

Ban in prose: extracted, extractor, Docling, AcroForm, drain, projection
(the pipeline kind), Browser, “website browser,” runbook, “now exposes,”
PRD numbers, “v1.”

Keep: field IDs, table names, anon key, PostgREST, `ipeds_id`, release
type, provisional vs final, H2A, ED residual, submitter-only.

---

## Methodology index (`/methodology`)

**Primary:** counselors off a METHOD link. Secondary: IR.

### Now

- Title: Methodology
- Description: “How collegedata.fyi turns Common Data Set source documents
  into academic profile, admission strategy, and merit profile cards.”
- H1: How the cards are built.
- Lede: source fields, derivations, caveats; starts from archived CDS.
- Cards: Academic profile / Admission rounds / Merit and need aid
- Detail H1s do not match the cards (Academic *positioning* vs Academic
  *profile*)

### Proposed

**Meta**

- Title: Methodology
- Description: How the school-page cards read Common Data Set filings —
  academic profile, admission rounds, merit and need aid. What they use,
  what they skip, what they do not predict.

**H1:** How the cards are *built.* (keep the sentence; italic the verb)

**Lede** (italic serif, 18/1.55):

> The trail behind the school-page cards. Each note names the CDS fields,
> the derivation, and the caveat. Nothing here predicts an admissions
> decision or a financial-aid package.

**Cards** — titles stay (they match the school-page `.meta` kickers).
Bodies name the method, not the pipeline:

| Card | Body |
|---|---|
| Academic profile | Where a student’s SAT or ACT lands in the score bands the school published for enrolled first-years. Not a chance-me. |
| Admission rounds | ED, EA, wait-list, and yield from Section C — including what CDS will not let you compute. |
| Merit and need aid | What the school reported in Section H, plus federal net-price and outcome context. Not a package estimate. |

---

## Academic profile (`/methodology/positioning`)

**Primary:** counselor who clicked METHOD on Academic profile.

### Now

- Title: Academic Positioning Methodology
- H1: Academic positioning
- Lede: “This page shows where your scores would land…”
- Field notes say “v1 does not score rank”
- Sources: `school_browser_rows`; “PRD 016 does not add a new API resource”

The H1 does not match the card the counselor left. “Your scores” addresses
a parent; this page is the trail. “v1” and “PRD 016” are operator.

### Proposed

**Title:** Academic profile methodology

**Description:** How collegedata.fyi compares a student’s scores to a
school’s published Common Data Set score bands for enrolled first-years.
Not a chance-me.

**H1:** Academic *profile.*

**Lede:**

> Where a student’s SAT or ACT would land in the numbers the school
> published for its enrolled first-years — the entering class, not the
> admitted pool. It is not a chance-me, and it does not predict an
> admissions decision.

Keep the C.7–C.12 / C.1 / C.2 field notes. They *are* the method.

C.8 (patched): whether score bands describe all enrolled first-years or
only the subset who submitted scores.

C.11: “This card does not score rank…”

C.12:

> The card displays the school average beside the student’s entered GPA;
> GPA never contributes to academic fit because weighted and unweighted
> scales are not consistently documented.

**Why this isn’t a chance-me** (patched):

> A position compares a student’s numbers with the bands the school
> published for enrolled first-years.

and

> That means the range describes submitters, not the full entering class.

Stale-data (drop roadmap voice):

> If the newest archived CDS for a school is more than three years old,
> the card carries a stale-data caveat.

**Sources:**

> Every card links the archived CDS for that school year. The serving
> table is `school_browser_rows`, documented on the API page.

---

## Admission rounds (`/methodology/admission-strategy`)

**Primary:** same counselor, plus IR checking ED math.

### Now

- Title: Admission Strategy Methodology
- H1: Admission strategy (card kicker is Admission rounds)
- Lede is already professional. Keep the spine.
- “PRD 016B adds columns”; “Phase 0 measurement results are preserved in
  the repository’s PRD findings note”

### Proposed

**Title:** Admission rounds methodology

**Description:** How collegedata.fyi reads Early Decision, Early Action,
yield, wait-list, and admission-factor context from Common Data Set
Section C — and which rates CDS will not support.

**H1:** Admission *rounds.*

**Lede:** keep, one tightness pass:

> The headline admit rate in most college guides averages across rounds.
> This note says what Section C actually publishes, what we derive, and
> what those numbers do not prove.

Keep: C.1 / C.21 / C.22 / C.2 / C.7 / C.13; “Why non-early residual”;
“Read ED rates carefully” with no “v1”:

> We do not estimate a general-pool ED rate because CDS does not
> separate those applicant groups.

NBER as methodological context (not school-level data); wait-list
year-to-year noise; “we take no legal position on ED.”

**Sources:**

> Every school card links the archived CDS for the displayed year. The
> serving table is `school_browser_rows`, documented on the API page.

The D’Amico docket can stay as a pointer for readers who want legal
context. Do not write it as a finding. If it crowds the method, move it
below Sources.

---

## Merit and need aid (`/methodology/merit-profile`)

**Primary:** counselor plus IR. Federal numbers stay labeled federal.

### Now

- Title: Merit Profile Methodology
- H1: Merit profile (card kicker is Merit and need aid)
- Lede is already the right claim: what the school awarded, not a package.
- Missing-data paragraph: “After the May 3, 2026 Tier 4 redrain, direct
  H.2A02 answerability was 244 of 365 latest primary 2024+ schools
  (66.8%)…”

That coverage count is useful. The redrain is a pipeline story. VOICE
allows Harvey Mudd / Docling in a methodology *appendix*, not in the
card-method body.

### Proposed

**Title:** Merit and need aid methodology

**Description:** How collegedata.fyi reads merit-aid and need-aid from
Common Data Set Section H, with federal College Scorecard net-price and
outcome context. Not a personalized price estimate.

**H1:** Merit and need *aid.*

**Lede:** keep.

Keep H.2 / H.2A / H.6 / H.14 / Scorecard notes. Keep “What H2A does and
does not mean” (understates mixed packages). Keep “Missing data policy”:
missing stays missing; no imputation from peers or marketing copy.

**Coverage sentence** (drop the redrain and the effective-answerability
stat). Date the live-API count (2026-08-27: 335 of 488, 69%). Do not
restate the H.2A01/H.201 share-blank rule — it already lives in “What
H2A does and does not mean.”

> The average no-need grant (H.2A02) is currently reported for 335 of 488
> schools in the merit view (69%).

**Sources** — keep `school_merit_profile` and the curl. Scorecard is
federal context joined by IPEDS UNITID; say that once.

---

## API (`/api`)

**Primary:** researchers, IR, developers. Secondary: parents pointing an
LLM at a public endpoint (why API stays in the header).

### Now

- Title: API
- Description: “Public REST API for the collegedata.fyi Common Data Set
  archive and source-labeled NCES/IPEDS federal baseline facts.”
  (Scorecard is used; the description names two of three sources.)
- H1: API, `font-bold text-gray-900` — leftover SaaS chrome
- Lede: “CollegeData.FYI now exposes two public surfaces…”
- H2: Runbook (smoke-test, CLI, MCP, snapshots, troubleshoot)
- Troubleshoot: “the projected value failed a sanity check”
- Example: “Search the curated school browser”
- Example: “Fetch extracted field values for a document” plus “For Tier 4
  Docling extracts, the LLM fallback cleaned row…”
- Resource blurbs: “extraction results,” “website browser”
- Page is gray-50 / gray-900 / gray-800. Design system: no blue; cards
  are paper, not Tailwind white/gray.

Code samples and the resource catalog stay. This wave is the sentences
around them, plus restyle onto tokens.

### Proposed

**Title:** API

**Description:** Public API for Common Data Set filings and federal data —
no-auth JSON for agents, and the full PostgREST archive. Same sources the
site uses.

**H1:** The *public* API.

**Lede** (italic serif, 18/1.55):

> Two ways in: simple no-auth JSON for agents and scripts, and the full
> [PostgREST](https://postgrest.org/) archive at `api.collegedata.fyi`
> for bulk work. Every page on this site is built from the endpoints
> below. Keep the source label next to the number.

Drop “now exposes.” This is not a changelog.

Simple-endpoints intro (avoid a second “Start here”):

> The friendly surface for MCP tools, CLIs, notebooks, and quick
> integrations.

**H2 Runbook → Start here**

Keep the five steps. Relabel:

| Now | Proposed |
|---|---|
| Runbook | Start here |
| 1. Smoke-test the API | 1. Try search, facts, and compare |
| 2. Run the CLI | 2. Run the CLI |
| 3. Connect an MCP client | 3. Connect an MCP client |
| 4. Use snapshots for local work | 4. Pin a snapshot |
| 5. Troubleshoot source gaps | 5. When a value is missing |

Under “Pin a snapshot,” keep the `latest` curls and add one pinned line
(`<snapshot-id>` is in the manifest):

`curl 'https://www.collegedata.fyi/snapshots/<snapshot-id>/schools.jsonl'`

**Missing-value sentence:**

> A missing value is usually one of four things: the school has no public
> CDS, the school’s filing leaves the field blank, the field is not in
> the friendly dictionary, or the row failed a sanity check and was
> withheld. The sources endpoint shows the document and the federal
> release behind the page.

**Resource blurbs** (prose only; keep live interpolated counts; field
lists stay, including `extracted_at` / `extraction_status`):

- `cds_manifest`: One row per archived CDS document — school, year,
  source URL, format, `extraction_status`. Carries `ipeds_id` so federal
  joins are one query.
- `cds_artifacts`: Raw artifacts keyed by document. Prefer `cds_fields`
  for field-level queries.
- `cds_fields`: `{count} normalized field rows from 2024-25 and newer
  filings. Derived metrics such as acceptance_rate live on
  school_browser_rows.`
- `school_browser_rows`: `{n} primary 2024-25+ rows across {k} schools,
  refreshed {date}. The curated serving layer behind Compare, CSV export,
  and the academic-profile and admission-rounds cards.`

**Examples to retitle**

- “Search the curated school browser” → “Search latest-per-school rows
  (Compare)”

  Body:

  > Compare’s latest-per-school ranking runs through an Edge Function so
  > it can account for required fields and null answerability. Percent
  > and rate values are stored as fractions from 0 to 1.

- “Fetch extracted field values for a document” → “Fetch the canonical
  artifact for a document”

  Body:

  > Prefer `cds_fields` for field-level queries. If you need the
  > underlying artifact, fetch `kind=eq.canonical` on `cds_artifacts` —
  > the canonical artifact is the one the site serves.

Keep the JavaScript example’s `.eq("extraction_status", "extracted")` —
that is the published filter name.

Keep: anon-key auth, endowment draw-rate example (already honest),
federal-baseline example, schema/licensing, GitHub issue footer.

**Restyle:** leftover chrome is gray (`text-gray-900`, `bg-gray-50`), not
blue — forest links already. Page wrapper, H1, lede, H2, code blocks,
resource cards onto `--paper` / `--ink` / `--serif` / `--mono`. No
`text-gray-900`. Do not redesign the catalog.

---

## Read-aloud checks

- Counselor on methodology: “I know which CDS fields built the card, and
  that it is not a prediction.”
- IR on merit: “H2A understates mixed packages; missing stays missing;
  Scorecard is federal.”
- Analyst on `/api`: “Two surfaces, copy-paste queries, no pipeline
  lore, table names I can use.”

If the lede could be a changelog (“now exposes”) or a pipeline note
(“Tier 4 redrain”), it isn’t done.

---

## Out of Wave 4

Discover. School cards (including the PositioningCard admit-submit
caption). Pipeline observation (operator). GitHub README. Do not add a
fourth methodology page for extractors — `docs/known-issues/` already
holds Harvey Mudd / Docling. Slugs stay `/methodology/positioning` and
`/methodology/admission-strategy`.
