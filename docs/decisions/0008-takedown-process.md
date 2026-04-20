# ADR 0008: Takedown Process for Archived Documents

**Date:** 2026-04-20
**Status:** Accepted
**Supersedes:** none
**Extends:** [ADR 0002 — Publish raw over clean](0002-publish-raw-over-clean.md), [ADR 0003 — MIT License](0003-mit-license.md)

## Context

The archive preserves publicly-published Common Data Set documents. Every
document in the corpus was published by a school's Institutional Research
office on a public URL as a matter of ordinary US News / Common App
compliance. The right-to-archive posture is strong:

- CDS documents are public-accountability records, not private data.
- Extracted canonical values are keyed to the CDS Initiative's own
  schema; the schema ships publicly, no reverse engineering involved.
- The repository is MIT-licensed per [ADR 0003](0003-mit-license.md);
  schools own their data but not the archive's method of preservation.
- Source PDFs are stored byte-for-byte as published, with provenance
  tags linking back to the originating URL and discovery timestamp.

Even with all of that, a school's IR office or legal counsel may request
removal. Reasons could range from legitimate (a document was accidentally
publicly posted and contains FERPA-protected data; a school disputes the
version we archived) to courtesy-only (an IR director would like their
name off an old CDS). A response protocol should exist before the first
request arrives so we can act quickly, transparently, and consistently.

Previously this was referenced as a future ADR in [ADR 0006](0006-tiered-extraction-strategy.md)
and as a 30-minute pure-docs task in [backlog.md](../backlog.md). This
ADR is that document.

## Decision

A three-step protocol governs every takedown request. Execute in order;
each step is fully revertible if a later step reveals the request was
invalid.

### Step 1: Verify

1. The request must arrive via email to the contact link on
   [collegedata.fyi](https://collegedata.fyi) or as a GitHub issue on
   the [bolewood/collegedata-fyi](https://github.com/bolewood/collegedata-fyi)
   repository.
2. The requesting email must originate from a `.edu` address matching
   the school's official domain (cross-check against the school's
   public IR office listing, not a free webmail account).
3. The request must specify the document precisely: `school_id`,
   `cds_year`, and optionally `sub_institutional` if relevant.
4. If any of the above is missing, reply asking for the missing piece.
   Do not act until the verification is complete.

If the requester is a credentialed member of the school's IR, communications,
or general counsel office, no further verification is required. If the
requester is an unaffiliated party claiming to represent the school,
ask them to CC someone at the school's IR office to confirm. If that
confirmation doesn't arrive, treat the request as unverified and do not
act.

### Step 2: Apply

The takedown marks the document as withdrawn from the public catalog.
Bytes stay in place for the current implementation (see "Consequences"
below for the bytes-move follow-up path).

```sql
UPDATE cds_documents
SET participation_status = 'withdrawn',
    removed_at = now(),
    updated_at = now()
WHERE school_id = $1
  AND cds_year = $2
  AND (sub_institutional = $3 OR (sub_institutional IS NULL AND $3 IS NULL));
```

The frontend's `cds_manifest` selects in [`web/src/lib/queries.ts`](../../web/src/lib/queries.ts)
filter out rows with `participation_status IN ('withdrawn', 'verified_absent')`,
so the withdrawn document:

- No longer appears in the school's year list
- No longer appears in the schools directory
- No longer appears in sitemap.xml
- Returns 404 if the URL is hit directly (the year page's
  `fetchDocumentsBySchoolAndYear` returns zero rows, `notFound()` fires)

The PostgREST API at `api.collegedata.fyi` still exposes the row because
it's a direct table query. Consumers who query the raw API get the row
with `participation_status='withdrawn'` and can choose whether to filter.
This is intentional: transparency about what was withdrawn is part of
the archive's good-faith posture (see Step 3).

**If the request specifically demands bytes-removal** (not just
public-catalog removal):

1. Move the Storage object via `supabase.storage.from('sources').move(...)`
   into a private `sources-withdrawn` bucket. This bucket does not
   exist in the current schema; creating it + updating
   `cds_artifacts.storage_path` + rewriting the frontend's public URL
   pattern is a separate PRD scope triggered by the first such request.
2. Until that bucket exists, record the bytes-removal request in the
   transparency log and let the requester know that catalog removal
   is immediate but bytes removal is on a ~1-week timeline.
3. Operator judgment: if the requester is a school's general counsel
   or equivalent and cites FERPA or a legal-exposure reason, prioritize
   the bytes move over standard queue order.

### Step 3: Transparency log

Every takedown gets one line appended to `docs/takedowns.md` (the
scaffolding for this file ships with this ADR). Format:

```
- YYYY-MM-DD | school_id | cds_year | reason_category | outcome
```

Where `reason_category` is one of:

- `ferpa_adjacent` — document contains data the school considers
  FERPA-sensitive
- `accidental_publish` — document was never intended to be public
- `version_dispute` — school disputes the version we archived
- `attribution_dispute` — requester objects to the archive itself
- `other` — doesn't fit the above

And `outcome` is one of:

- `catalog_removed` — participation_status flipped, bytes in place
- `catalog_and_bytes_removed` — bytes also moved to sources-withdrawn
- `declined` — verification failed, no action taken
- `restored` — previously withdrawn document was un-withdrawn at
  school's request

The log does NOT include requester PII (name, email, phone, internal
correspondence). Only the aggregate fact that the document was
withdrawn and why-in-a-category.

## Consequences

**Positive:**

- A documented process exists before the first request arrives. Time
  from request-received to document-withdrawn is under 1 hour instead
  of "whenever I figure it out under pressure."
- The transparency log creates a public paper trail that argues for the
  archive's good-faith posture if any future dispute arises.
- Verification steps filter out bad-faith or misdirected requests
  without operator emotional labor.

**Negative / tradeoffs:**

- Current implementation leaves bytes in Storage. If a request is
  bytes-removal-or-else-lawsuit, we have a ~1-week gap to stand up
  the `sources-withdrawn` bucket. This is a judgment call: for a
  low-frequency event (zero requests to date), the cheap
  catalog-only implementation is right. A higher-frequency future
  (e.g., if the HN launch surfaces ten takedowns in a week) triggers
  the bucket-move PRD.
- `cds_artifacts.storage_path` references remain valid after a
  catalog-only takedown, so programmatic consumers (not the
  frontend) can still fetch the archived bytes. This is a feature,
  not a bug: researchers who need the underlying data still have it.
  If a school's lawyer points at this and says "we want it gone,"
  that's when we move bytes.
- The `declined` outcome means we'll occasionally tell a requester
  "no." The verification rules are intentionally strict to protect
  against bad-faith requests.

**Operational:**

- Add `docs/takedowns.md` to the repo now (empty scaffolding,
  populated on first real takedown).
- Link ADR 0008 from `CONTRIBUTING.md` under a new "If you represent
  a school and need a document removed" section.
- The existing `participation_status` CHECK constraint in
  [`supabase/migrations/20260413201910_initial_schema.sql`](../../supabase/migrations/20260413201910_initial_schema.sql)
  already allows `'withdrawn'` as a value. No migration required for
  the catalog-only path.

**Cross-references:**

- [ADR 0002](0002-publish-raw-over-clean.md) — publish-raw posture
  makes the takedown-needed case rare but nonzero (raw data gets
  richer scrutiny).
- [ADR 0003](0003-mit-license.md) — MIT license covers the code;
  schools own their data.
- [ADR 0006](0006-tiered-extraction-strategy.md) — referenced this
  ADR as a future document.
- [`docs/takedowns.md`](../takedowns.md) — transparency log.
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — contact instructions
  for takedown requests.
