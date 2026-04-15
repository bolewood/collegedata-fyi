# ADR 0007: Year authority moves from discovery to extraction

**Date:** 2026-04-15
**Status:** Accepted
**Supersedes:** none
**Extends:** [ADR 0006 — Tiered extraction strategy](0006-tiered-extraction-strategy.md)

## Context

The discovery pipeline assigns each archived document a `cds_year`
value derived from the source URL and surrounding anchor text. The
logic lives in [`_shared/year.ts`](../../supabase/functions/_shared/year.ts)
and is called from [`_shared/resolve.ts`](../../supabase/functions/_shared/resolve.ts)
during the two-hop landing-page walk. A document is only archived if
the resolver can extract a valid academic span — `CDS2024-2025.pdf`
passes, `cds_all.pdf` fails. The span is validated by the
`y2 = y1 + 1` rule so Drupal upload paths like `2020-04` cannot be
misread as academic years.

This design was correct for M1, when extraction did not exist. The
URL was the only place we could see a year. After the first full
production drain (2026-04-14/15, 837 schools archived) and the spot
checks that followed, three findings make it wrong for M2.

**1. Year parsing is the single biggest source of archive failures.**
Of 302 `failed_permanent` rows in the April drain:

| Count | Bucket |
|---|---|
| 204 | resolver "no year-bearing anchors / no parseable year" |
| 51  | download HTTP 404 (stale hints) |
| ~20 | transient 403/timeout, exhausted 3 attempts |
| ~11 | content-type / magic-byte misses |

**2. The 204-row bucket decomposes into three distinct problems, and
URL-based year parsing is causing most of them.** A 25-school spot
check:

- ~36% are direct-doc hints already pointing at the correct CDS
  document, rejected because the filename format is unparseable
  (`kenyon-cds-202425-march-2025.pdf`, `CDS20162017.pdf`,
  `CDS22.pdf`, `common-data-set.pdf`, UCLA's `/file/<uuid>`).
- ~44% are JavaScript-rendered, iframe, SharePoint, or Box-embedded
  pages where our static HTML parser sees nothing useful anyway
  (unrelated to year authority — tracked separately).
- ~6% are real multi-year archive pages the resolver can see but
  cannot rank.

So 58% of the failure bucket (~120 schools) is recoverable if year
detection moves to a later stage.

**3. The resolver is throwing away multi-year historical depth on
every successful school.** A 20-school spot check of the `done`
bucket: the 25% of schools with HTML landing pages have an average
of **16.8 CDS-ish anchors and 14.2 distinct years per page**.
Northern Michigan University has 25 years on one page. Allegheny has
24. Lafayette has 20. The resolver walks these pages, identifies the
candidates, ranks them by year, and discards every year except the
winner. Projected across the 535-school successful pool, the current
architecture is throwing away on the order of **~1,900 archivable
documents** (≈14 extra years × 25% landing-page share × 535 schools)
that are already sitting on pages we crawl.

The common root: year parsing is content classification at the
metadata layer. The resolver is trying to answer "which document, in
which year?" from URLs and anchor text — a metadata representation
of a content question. The ground truth lives on page 1 of the
document, printed in canonical form by the CDS Initiative's
template. Extraction did not exist when discovery was designed; now
it does (M2 skeleton landed in `db520e6`), and the authority for
year assignment can move to where the truth is.

## Decision

**Content-derived year is authoritative.** The extraction pipeline
owns the academic year of each archived document, deriving it from
page content via a strict prefix-anchored regex ladder with
`y2 = y1 + 1` span validation. The discovery pipeline stops
requiring a year in the URL as a precondition for archiving.

The migration is staged across three PRs so each step is
independently revertable.

### Stage A — content detection, observation only (this PR)

Add `detect_year_from_pdf_bytes()` to the extraction worker. Call it
from `extract_one()` as a log-only side channel — no database
writes. Ship a `--detect-year-only` CLI harness that runs the
detector against every archived document regardless of
`extraction_status` and reports `confirmed` / `mismatch` /
`undetected` counts against the real corpus.

The detector uses two patterns, in order:

```python
r"Common\s+Data\s+Set\s*[,:]?\s*(20\d{2})\s*[-–—/]\s*(20\d{2}|\d{2})"
r"\bCDS\s*[,:]?\s*(20\d{2})\s*[-–—/]\s*(20\d{2}|\d{2})\b"
```

Both require an adjacent "Common Data Set" or "CDS" prefix. A bare
`(20\d{2})[-–—/](20\d{2})` fallback was evaluated and rejected:
American University's 47-page flattened CDS PDF has exactly one
valid year span anywhere in its extractable text — `2006-07` on
page 20, a section J reference year — and enabling the bare
fallback would have silently mis-dated the school by 18 years.
Missing a document is strictly preferable to corrupting one, per the
project directive on filter strictness.

Detection scans pages 1-10, not just the title page. The window is
bounded insurance for schools whose CDS title span appears after
page 1 (wrapped covers, front matter, or templates that bury the
"Common Data Set YYYY-YYYY" header behind a respondent-information
front page). It is **not** sufficient to recover every such school:
Ashland University is archived with a `2023-24` span on page 8 that
the strict prefix-anchored regex does not match (the year on page 8
is a bare `2023-2024` without a "Common Data Set" or "CDS" prefix
within the same extracted-text run), and Ashland remains in the
`undetected` bucket under the Stage A harness. The 10-page window
catches the cases where the prefix *does* carry past page 1, which
is the deliberately strict subset the project directive prefers.

No schema changes. No behavior changes for any other pipeline. The
observation wiring exists to collect evidence for Stage B.

### Stage B — load-bearing, resolver drops the year requirement (next PR)

**Gate: cleared by the 2026-04-15 Stage A harness run.** Full-corpus
detection against all 518 archived documents, using the final
shipped `detect_year_from_pdf_bytes()` (strict prefix-anchored
regex, collect-all-spans across pages 1-10, return only if exactly
one unique valid span exists), produced:

- 373 confirmed (matched the stored `cds_year`)
- 7 mismatches — all manually classified, **0 detection errors**.
  Every mismatch is a case where content detection caught a
  pre-existing resolver/archive bug the project did not know it
  had. Mismatch classification in order: misnamed filenames (CSU
  Long Beach, CUNY Queens), URL-stable re-uploads (Dominican U),
  misfiled folder structures (Samford), content-out-of-sync
  renames (TCNJ), and shared-file duplicates across schools (U
  Maine System + USM, which both point at the same Google Drive
  file — a separate archive bug surfaced by this run).
- 96 undetected (flat PDFs without a single unique CDS-prefix span
  across pages 1-10, or PDFs with multiple distinct valid spans
  where the collect-all-unique rule conservatively returns None to
  preserve the safety invariant)
- 42 non-PDF (xlsx/docx, out of scope for Stage A)

On the 380 PDFs where detection fired, **precision is 100%** —
detection has never produced a wrong span, only corrections.
Recall on PDFs is 80% (373 confirmed + 7 correct mismatches) ÷
(373 + 7 + 96).

An earlier iteration used a `for pattern in patterns: for page in
pages: return first valid` loop that scored a higher nominal
recall (86.5%) but carried a latent reference-trap: a page-1
footer like "Common Data Set 2015-16 data for comparison" would
beat a real title on a later page, and the `y2 = y1 + 1`
validation does nothing to prevent that (2015-16 is a structurally
valid span). That rule was tightened mid-review to the current
collect-all-unique form after two independent reviewers flagged
the exposure. The re-run against the shipped tightened code moved
31 previously-confirmed schools into the undetected bucket —
these are documents whose first-match answer happened to match
the stored year, but which also contained other distinct valid
spans in pages 1-10 and were therefore one unlucky ordering away
from corruption under the old rule. The 7 mismatches are
bit-identical between the two runs, which means the tightening
cost ~6.5% recall for a much harder safety invariant: "the
function returns a year only when the document's first 10 pages
agree on a single CDS-prefixed year."

The invariant "strict may miss but must never corrupt" now holds
structurally, not just empirically. Stage B can proceed.

One implication the Stage A evidence adds to the original decision:
when the extraction worker flips from observe to write, it will
**correct** the 7 pre-existing mismatched `cds_year` values in
place. Each correction is a row-level state transition that the
Stage B unique-constraint approach has to handle cleanly (e.g., a
row moving from `(dominican, 2021-22)` to `(dominican, 2024-25)`
must not collide with any pre-existing Dominican 2024-25 row). The
Stage B migration design needs to account for year corrections, not
just first-time year assignments.

A second, trickier implication: source-file Storage paths are
**year-encoded**. The `sources` bucket uses the convention
`{school_id}/{cds_year}/{sha256}.{ext}`, and `cds_manifest` exposes
the resolved path to consumers. If Stage B corrects a row from
`2021-22` to `2024-25` by updating the row in place, the DB year
and the artifact path diverge: the row says `cds_year = 2024-25`
but the Storage object still lives under `.../2021-22/<sha>.pdf`.
Consumers following `cds_manifest.source_storage_path` will
download a file whose path does not match the year in the row they
queried, and provenance gets split across two year prefixes if the
school ever republishes.

Stage B has to resolve this. Three sub-options:

- **Rekey on correction:** re-copy (or rename via the Storage API)
  the source blob to the new year prefix at the same sha. Costs a
  Storage round-trip per correction but keeps paths and years in
  lockstep.
- **Dual-write at archive time:** always write the blob under the
  SHA-only path (no year prefix) and use a DB-level
  `source_storage_path` column that can be updated in place. The
  year prefix becomes a presentation concern, not a storage key.
  Cleaner but requires a migration to `cds_artifacts` and an
  update to every consumer that constructs paths from
  `(school_id, cds_year, sha)`.
- **Freeze the original path:** accept that the archive path
  reflects the resolver-assigned year at archive time and treat it
  as historical metadata; add a new column `authoritative_cds_year`
  set by extraction; `cds_manifest` exposes both. Honest about the
  two-source-of-truth problem but adds a column.

Option B (SHA-only path) is probably right long-term but is a
larger migration than Stage B wants to take on. Option A (rekey)
is the minimum viable change. This ADR does not pick — the Stage B
PR drafts the migration and decides with the rekey cost in hand.

Changes in Stage B:

- `_shared/resolve.ts` returns every CDS-ish anchor from a landing
  page instead of picking the highest-year winner. An anchor is
  "CDS-ish" if its href matches `\.(pdf|xlsx?|docx?)` and either the
  href or the link text matches `cds|common[\s\-_]*data[\s\-_]*set`.
  Strict by design.
- `_shared/archive.ts` loops over all candidates instead of
  archiving one per school. The SHA-addressed Storage path model
  already handles collision-free multi-document writes.
- Direct-doc hints (URLs that return a document on first fetch)
  bypass year parsing and archive regardless of filename format.
  This alone recovers ~75 of the 204-row failure bucket.
- Extraction worker flips year detection from observe to write.
- One of three unique-constraint approaches is implemented (see
  trade-offs).

### Stage C — cleanup (follow-up)

Delete URL year parsing from `_shared/year.ts`. Update
[`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) §Overview (line 13) and
§Discovery flowbox (lines 80-83) to remove "year-labeled" and
"Normalize year span," and add a "Detect document year from page
content" step to the Extraction flowbox. Update
[`docs/archive-pipeline.md`](../archive-pipeline.md) failure
taxonomy. Re-run the April drain against the new pipeline.

## Why

**The year belongs at the content layer because that is where it
is.** The CDS Initiative publishes a template that prints the
academic year in a known location. Every school fills the template
without erasing that label. URLs are a derivative representation a
school's webmaster chose, often do not carry the year at all, and
are the wrong place to look for it. This is the same argument ADR
0006 made for format detection, applied to a different piece of
metadata on the same file.

**The failure modes are not fixable at the resolver layer without
layering heuristics on the wrong representation.** Each of the 204
failures could in principle be patched with a more permissive
regex, a smarter anchor ranker, or per-school overrides. Every such
patch increases resolver surface area without delivering historical
depth on the 535 working schools. Dumb code that fails in fewer
ways is a feature.

**The historical-depth gain is ~1,900 additional documents that
already sit on pages we crawl.** We pay the discovery cost today,
walk the pages, identify the candidates, and then discard everything
except the winner. Returning the full candidate list is strictly
cheaper than what the resolver already does. The only reason we
picked a winner was because downstream could not handle multiple
documents per school per year — and after M2, it can.

## Trade-offs accepted

**Content detection will miss some PDFs.** The full-corpus Stage A
harness (post-tightening) measured ~20% of PDFs as undetectable
(96 of 476): flattened image-derived documents without extractable
page text, PDFs without a "Common Data Set" or "CDS" prefix
anywhere in the first 10 pages, pathological layouts like American
University's 47-page PDF where the only valid year span in all
extractable text is a section J reference year on page 20, and
documents whose first 10 pages contain multiple distinct valid
spans (the collect-all-unique rule conservatively returns None on
ambiguity). Undetected documents remain archived — they just lack
an authoritative year until Stage B decides how to represent that
state.

**The unique-constraint approach is deferred to Stage B.** The
current schema has `UNIQUE NULLS NOT DISTINCT (school_id,
sub_institutional, cds_year)` with `cds_year text NOT NULL`. Moving
year authority to extraction breaks the not-null assumption because
archive happens first. Three candidate approaches:

1. **Make `cds_year` nullable.** Unique constraint still holds
   under NULLS NOT DISTINCT — but *that is precisely the problem*.
   Stage B's archiver will emit multiple CDS-ish anchors per school
   before extraction assigns years. With NULLS NOT DISTINCT, two
   pending rows with `(school_id, NULL, NULL)` collide on the
   unique key, and the second insert fails. This is not a
   theoretical race — it is the design intent (multi-candidate
   archiving) running straight into the existing constraint. Option
   1 requires either dropping `sub_institutional` from the
   constraint (breaks sub-institutional uniqueness), temporarily
   assigning a synthetic per-candidate placeholder, or switching
   the constraint to `NULLS DISTINCT`. Each has follow-on costs.
   **Likely not viable as specified.**
2. **Add a `detected_year` column, keep `cds_year` as discovery's
   best-effort guess.** Operationally simplest; introduces two
   sources of truth, which this ADR just argued against. But given
   option 1's structural problem and option 3's stringiness,
   "two-column with a precedence rule" may be the pragmatic winner.
3. **Introduce a sentinel (`"pending"` / `"unknown"`) in
   `cds_year`.** Avoids the null-handling question; bakes a state
   machine into a text column. The sentinel itself must be unique
   per-candidate to satisfy the unique constraint (e.g.
   `"pending:<archive_run_id>:<artifact_sha>"`), which is ugly but
   tractable.

Each has follow-on effects in `cds_manifest`, `archive.ts`, and
`archive_queue` claim logic. The Stage B PR will draft the
migration and decide with the full change in hand.

**Discovery and extraction become loosely coupled on the year
dimension.** Today they are in lock-step. After Stage B, a row can
exist in `cds_documents` without an authoritative year until
extraction processes it. `extraction_status` already tracks the
state so consumers have a signal to filter on, but the visible
"archived but not yet year-attributed" state is new. This is a
feature — it makes extraction progress observable in the query
layer.

**Non-PDF formats inherit a gap.** Year detection is PDF-only in
Stage A. Roughly 25% of the current 515-doc backlog is
`PK\x03\x04`-headed (xlsx/docx). Those documents will need
openpyxl / python-docx detection paths wired alongside the Tier 1
and Tier 3 extractors when they ship.

## Relationship to existing ADRs

- **ADR 0001 (Supabase-only architecture).** Unchanged. Detection
  runs inside the Python worker which ADR 0001 already places
  outside the edge function layer.
- **ADR 0002 (Publish raw over clean).** Unchanged. Year detection
  is a property of the source document, not a normalization of raw
  output.
- **ADR 0006 (Tiered extraction strategy).** Extended. The tier
  ladder is unchanged; year detection sits alongside format
  detection as a content-layer operation the Python worker
  performs before routing to a tier extractor. Same argument,
  different metadata, same file.

## Open items

- Unique-constraint approach. Decided in Stage B.
- Year detection for XLSX and DOCX. Wired alongside Tier 1 / 3.
- `cds_manifest` view update. Whichever schema approach is chosen,
  the `latest_canonical_artifact_id` subquery will need to handle
  un-dated rows.
- Stage A success threshold for the detection rate. To be set after
  the first full-corpus harness run surfaces real numbers.
- Bucket B (~90 JS-rendered failing schools) is unaffected by this
  ADR and tracked separately. Year authority is the wrong lens on
  that problem.
