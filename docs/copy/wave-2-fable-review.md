# Wave 2 Fable review

Verdict: **ship with patches**

Patches applied to `wave-2-product-surfaces.md` 2026-08-27 (must-fixes 1–6
and should-fixes 1–8, with one honesty tweak on #4: “no Scorecard row”
is not the same as “no federal numbers” — IPEDS baseline can still
render. The deck now splits on any federal data vs neither). Nits left
for Anthony except the Compare error shout and “side by side” on the
sub-kicker.

The deck's direction is right on every surface — the ban lists are the correct
bans, the locks are respected, and the worst live copy dies ("Queryable school
browser," "archive and extract," "filter the corpus," "the resolver has not
scanned it"). But six lines fail a persona read-aloud, contradict the deck
itself, or promise something some pages cannot deliver. All six are patchable
without reopening anything.

## Must-fix

### 1. Compare — the "Rows" stat mislabels its own number

> | Primary rows | Rows | Latest year per school |

The number behind this stat counts **every** primary row from 2024-25 on —
including two rows for a school that has both 2024-25 and 2025-26 on file
(`site_stats`: `count(*) filter (where sub_institutional is null)` over
`school_browser_rows`, `year_start >= 2024`). "Latest year per school"
describes the table's default view, not this count. IR reads "Schools: 700"
next to "Rows: 900 — latest year per school," sees that the caption and the
arithmetic can't both be true, and stops trusting the band. It's the caption.

Replacement:

> | Primary rows | Reports | 2024-25 and newer |

### 2. Schools directory — hides the common case and dead-ends the parent

> Lede (italic serif): Every school we have a report for. Search by name.

Accurate, and useless to the majority. Most in-scope schools have no archived
CDS — that is the product's central fact, not an edge. A parent hunting one of
those ~1,473 names types it into the on-page search and gets the live table's
dead end ("No schools found matching …") with no exit. The load-bearing
federal fallback is unreachable from this page. The lede needs the pointer,
and the empty state needs to carry it too — the on-page search only filters
this table; the header search is the one that finds every school.

Replacement lede:

> Every school we have a report from. Don't see yours? Check
> [Coverage](/coverage) — schools without a report still get a page with the
> federal numbers.

Replacement empty state (table, no matches):

> No reports on file match "{query}." Try the site search — schools without a
> report still have a page with the federal numbers.

### 3. School page — "This is the {name} Common Data Set" claims to be the document

> This is the {name} Common Data Set — the yearly report the college
> publishes. {n} reports, {range}.

Two failures in eleven words. First, the page is not the Common Data Set; it
is our copy of {n} of them next to the federal numbers. The deck's own
publisher line ("The school's own page is the publisher") corrects this — but
that line only renders when we know the school's page. When we don't, the
claim stands uncorrected, and a counselor forwarding the URL has just told a
family this page *is* the school's document. That is the school-authored /
our-copy blur the locks exist to prevent. Second, "This is the [singular]"
collides with "{n} reports" in the next breath.

Replacement (keeps `{name} Common Data Set` in sentence one — lock intact):

> The {name} Common Data Set is the yearly report the college publishes about
> itself. {n} reports on file, {range}; the latest is {year}. Downloads
> include {formats}.

### 4. Directory-only page — garden-path grammar and a promise some pages break

> We don't have a Common Data Set this school published. You still get the
> federal numbers.

Read sentence one aloud as a parent: the relative clause arrives with no
warning and the sentence parses on the second try. And sentence two is false
on some of these pages: when a school has no Scorecard row, the live page
renders "FEDERAL OUTCOMES DATA NOT AVAILABLE FOR THIS INSTITUTION" directly
under the promise. The common-case page cannot ship copy its own body
contradicts.

Replacement, two states:

With federal data:

> We haven't found a Common Data Set from this school. The federal numbers
> are below.

Without:

> We haven't found a Common Data Set from this school, and federal outcome
> data isn't available for it either.

### 5. Year page — title collides with the site template

> Title: `{name} Common Data Set {year} | collegedata.fyi`

The layout template is `%s | collegedata.fyi` (`web/src/app/layout.tsx`). Set
the title to this literal string and every year page renders "…Common Data
Set 2024-2025 | collegedata.fyi | collegedata.fyi." The deck knows this: the
school-page section writes its title bare with a "(template → …)" note, and
the Coverage section drops "— collegedata.fyi" for exactly this reason. The
year-page section forgot its own rule.

Replacement:

> Title: `{name} Common Data Set {year}`
> (template appends `| collegedata.fyi`)

### 6. Coverage — "Title-IV" in the lede, to a parent

> Every undergraduate Title-IV school, with whether we have a public report
> on file.

The deck names "parents who searched a missing school" as an audience for
this page, then opens with a federal statute citation. No parent knows what
Title-IV is, and the ones who land here just failed to find their kid's
school. Say it in English; keep Title-IV in Methodology, where IR reads.

Replacement:

> Every U.S. college that takes federal student aid, and whether we have a
> public report on file. Publishing is voluntary. Some schools post the file,
> some bury it, some don't publish one we could find.

## Should-fix

### 1. Compare description overclaims "latest published"

> Each row is the latest report the school published that we can put side by
> side.

"The latest report the school published" asserts our discovery is complete.
It isn't — a school can post 2025-26 tomorrow and this sentence is wrong
until we find it. The deck's own lede has the honest form eight lines later
("the latest school report we can compare"). Use it; it's shorter too.

Replacement description:

> Compare admissions, cost, and aid across schools. Each row is the latest
> school report we can compare, as the school published it. The original file
> is one click away.

### 2. Compare — "From current reports" claims currency the rows don't have

> | Queryable fields | Facts | From current reports |

A 2024-25 row read in 2026 is not "current"; it is the latest on file. The
lock says current/accurate claims anchor to "as the school published it" —
the lede carries that anchor, this note doesn't, and the note is the one
sitting next to a number. (This is the Compare band, not the signed Wave 1
homepage band. The homepage stays.)

Replacement note: `From the latest reports`

### 3. Compare — the second stat band is unwritten and the caption points at nothing

The live dashboard has its own band the deck never touches: "Schools in scope
/ Matching filters / With required fields / Missing fields," plus "Fields
needed for the current filters: …". The deck bans "queryable" and "primary
row" but gives the implementer nothing for this chrome — they will improvise,
which is how "Browser rows" happened the first time. And the proposed
in-table caption says missing schools "are counted separately" — separately
*where*? The reader can't find the count from that word.

Replacement band labels: `Schools` / `Match your filters` / `Have every
number` / `Missing a number`

Replacement caption:

> Latest reports, 2024-25+. Schools missing a number your filters need are
> counted above. Building a list? Use Match.

### 4. Schools directory description drops "Common Data Set" from the whole surface

> Description: Find a college and open the reports it published.

The live description carries "Common Data Set"; the proposal removes the
phrase from `/schools` entirely — title, description, H1, lede, caption. The
lock keeps the query in SEO, and this is the page Google would surface for
"college common data set list." One mention, no stuffing. Also "Find a
college" promises any college; the table only holds the ones with reports.

Replacement:

> Every college with a Common Data Set on file. Open the reports each school
> published.

### 5. Coverage description — "which we've never found" and "stale"

> Which schools have a current report, which are stale, and which we've never
> found. Filter by state and size.

"Which we've never found" reads as schools we never found — the object went
missing mid-sentence. "Stale" is our pipeline word for the middle state; a
counselor guesses right, a parent doesn't. And this surface also loses
"Common Data Set" (the live description has it).

Replacement:

> Which schools have a current Common Data Set, which have only older years,
> and which have none we could find. Filter by state and size.

### 6. Match lede — "profile" does double duty and trips the parent

> Enter a profile on this device. … We don't store a student profile.

Sentence one tells the parent to enter a profile; sentence four says no
profile is stored. That is the exact shape of a contradiction, aimed at the
reader we most need to reassure — and the anxiety word is ours, twice. Say
what they actually enter; save the claim word for the claim.

Replacement:

> Enter scores and GPA — they stay on this device. Filter by fit and admit
> rate. Export a list with the year and the original file. We don't store a
> student profile.

### 7. Year page — lead and empty state assume the file link rendered

> [Download the original file](url). — and — The original file is above.

`source_storage_path` is nullable and the live lead renders the download link
conditionally. When there is no stored file, the deck's empty card opens with
a claim about a file that isn't on the page. One deck note fixes it:

> Empty state, no downloadable file: "The numbers from this report aren't on
> the page yet."

(One line replacing both live empty variants — "No structured field values
available" and "Structured data coming soon" both die — is right. Keep that.)

### 8. Year page — "the school's own page" is ambiguous as a bare link

> See the [school's own page](url).

On the school page this phrase has the publisher sentence around it. Here it
is naked, and a parent reads it as the school's homepage. Say what the link
is without re-saying CDS.

Replacement: `See the [school's page for these reports](url).`

## Nit

1. **Compare — "side by side" three times.** H1 ("Compare schools, side by
   side."), sub kicker ("2024-25+ · side by side"), description ("put side by
   side"). Should-fix 1 removes it from the description; cut it from the sub
   too: `§ Compare / 2024-25+`. The H1 earns it once.
2. **Dash drift.** The deck writes "2024–25+" (en dash) in Compare chrome and
   "2024-25+" (hyphen) elsewhere; the data layer prints hyphens. Pick the
   hyphen and stop.
3. **Fact-list order drifts by surface.** School page: "admissions, cost, and
   aid." Year page: "admissions, cost, aid, and enrollment." Compare:
   "admissions, enrollment, cost, and aid." Pick one order (Wave 1's hero is
   "admissions, cost, and aid") and reuse it.
4. **JSON-LD cleanup stops one string early.** The deck kills "extracted by,"
   but the live DataCatalog description still says "keyed to the canonical
   1,105-field schema" — "canonical" is glossary-banned and it's a
   field-count lecture in a string Google can show. Replacement: "Every
   Common Data Set year we have for {name}, as the school published it."
5. **Kicker chrome is inconsistent across the deck.** Compare gets
   "§ Compare," Match gets bare "Match," school pages get a bare "Common Data
   Set" kicker, directory-only keeps "§ Institution directory." Pick the §
   convention for all top-level kickers and say so, or the implementer
   decides per page.
6. **Compare error shouts.** "Couldn't load these schools." replaces a `.meta`
   label, so it uppercases to a full shouted sentence, and it gives no
   action. Keep the label short and put the sentence in the body: label
   `Couldn't load`, body "Try again in a moment."
7. **"(CDS)" leaves the school-page title with no counterweight.** Dropping
   it from the title is right — it isn't the query. But counselors genuinely
   search "{name} CDS." Cheap insurance: let the description carry the
   abbreviation once ("…the yearly report (CDS) the college publishes…") if
   it fits. Not worth more than that.

## What holds

- The ban lists are the right lists, and the worst live copy dies with them.
- The Compare caption killing "Looking for fit ranking?" — we don't rank; the
  live link copy implied we do. "Use Match" survives without the claim.
- "The numbers, as published" as the fields heading is the best line in the
  deck.
- Coverage catching the doubled "— collegedata.fyi" title, replacing "the
  resolver has not scanned it," and cutting the tell-the-sources-apart
  lecture to one line.
- "don't publish one we could find" fixing the live lede's "don't publish at
  all" overclaim.
- The email-gate line: "The original is here." Four words, does the whole job.
- Match description staccato: "On this device. No account. No student profile
  stored."

## Do not reopen

Survived this pass, intact in the deck:

- Compare is the public name everywhere; "Browser" appears only in ban lists.
- School and year titles and first sentences keep `{name} Common Data Set`;
  H1 stays the school name; year titles keep the year query.
- Directory-only pages keep the school-page title and tell the truth
  (Must-fix 4 patches the wording, not the truth).
- No takedown language anywhere in the deck.
- "As the school published it" anchors the Compare lede and year-page lead.
- Federal fallback stated on directory-only, and reachable from `/schools`
  once Must-fix 2 lands.
- API in the header, GitHub off the hero — untouched.
- No TSX. The deck is prose.
