# ADR 0009: Derived dataset licensed CC BY 4.0

**Date:** 2026-11-23
**Status:** Accepted
**Supersedes:** none
**Extends:** [ADR 0003 — MIT License](0003-mit-license.md)

## Context

ADR 0003 chose MIT for the repository. Until now the site and API also
described the structured dataset as MIT-licensed. MIT is a software license.
It says nothing about credit in a form that researchers, journalists, dataset
indexes or AI agents recognize, and data reusers rarely know how to apply it.

Some of what we serve isn't ours to license at all: the schools' Common Data
Set documents, the CDS Initiative template text in `schemas/`, and the federal
IPEDS, College Scorecard and FSA figures.

## Decision

1. The code stays MIT (ADR 0003, unchanged).
2. The structured CDS extracts we author, our field documentation and
   methodology notes, and our derived-metric definitions are licensed
   **CC BY 4.0** from the effective date in [`DATA_LICENSE.md`](../../DATA_LICENSE.md).
3. The license names what it doesn't cover: school documents, CDS template
   material, federal data, names and trademarks, and content that already has
   its own license (`data/discovery/` and `data/scholarships/` CC BY-SA 4.0,
   community write-ups CC BY-SA 4.0, usage statistics CC0).
4. There is one canonical credit line, kept in `web/src/lib/data-license.ts`
   and pinned by a test to `DATA_LICENSE.md`. API envelopes, the OpenAPI spec,
   MCP, snapshot manifests, spreadsheets, the CLI, `llms.txt` and the site all
   read it from there.

## Why

- **CC BY rather than MIT for data:** it's the license dataset users, Google
  Dataset Search and citation tooling already recognize, and its attribution
  terms (credit, license link, note changes) fit data reuse.
- **CC BY rather than CC BY-SA:** share-alike has real force on copyrightable
  prose, which is why the scholarship and discovery writing keeps it. On numeric
  tables it mostly adds friction for the reusers we want.
- **Honest about what it does:** facts aren't copyrightable, and our
  compilation follows the CDS template's own arrangement, so the license
  protects little. Its value is clear terms and consistent credit from people
  who follow licenses. It doesn't stop anyone from restating facts, and CC BY
  allows commercial reuse.

## Trade-offs accepted

- Data published before the effective date stays reusable under MIT, including
  everything in git history. A later license can't take back an earlier grant.
- Dated snapshot paths serve live data, so they can't mark the cutoff.
  `DATA_LICENSE.md` says to use the effective date instead.
- The PostgREST views don't carry `license`/`attribution` columns yet. That's a
  follow-up; the friendly API, MCP, snapshots and downloads carry them now.
