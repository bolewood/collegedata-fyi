# ADR 0004: Canonical domain is collegedata.fyi

**Date:** 2026-04-11
**Status:** Accepted

## Context

The project needs a public-facing name and domain. Candidates considered: `collegedata.fyi`, `collegedata.live`, `opencds.io`, `cdslib.org`, and a few longer variants. All were available for $5-15/year.

## Decision

Register `collegedata.fyi` as the canonical domain. Serve the public API under `api.collegedata.fyi`. Consider registering `collegedata.live` defensively as a 301 redirect to `.fyi` to protect against typos and preserve future repositioning options.

## Why

Two framing decisions drove this:

**No CDS jargon in the name.** "CDS" is inside baseball for institutional research professionals. Everyone else reads it as a medical acronym or a music format. `opencds.io` would force every non-technical visitor to learn the term before they could evaluate the project, which is exactly the friction the name should avoid. `collegedata.*` is immediately legible to anyone — a guidance counselor, a parent, a journalist — without a glossary.

**`.fyi` is an honest promise.** The TLD matches V1's actual scope: "here's the reference, here's where to look it up." `.live` would overclaim freshness the project can't deliver yet (extraction lag, manual Docling runs). `.org` would overclaim institutional heft. `.io` would signal "dev tool" when we want the project to be legible to non-developers too. `.fyi` sits where the project actually is: a rough-but-useful reference that exists primarily so developers and researchers can build better things on top.

There is a `collegedata.com` (long-running college search site) with no trademark conflict on the descriptive name, but some traffic will arrive there by mistake. Accepted as a known cost; if it becomes a problem, the project can rename.

## How to apply

- README lead copy: "college facts pulled straight from each school's Common Data Set" — not "an open CDS library."
- Supabase custom domain configured to `api.collegedata.fyi` during M0 so example `curl` commands in docs never need to change.
- All public documentation refers to the project as "collegedata.fyi," not as "CDS library" or "Open CDS."
