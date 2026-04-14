# ADR 0002: Publish raw Docling output, not cleaned data, in V1

**Date:** 2026-04-11
**Status:** Accepted

## Context

Docling extraction quality varies dramatically across schools' CDS PDFs. Sanity-checking against Yale 2024-25 and Harvey Mudd 2025-26 showed the gap clearly: Yale came out essentially clean, while HMC had real data corruption — the C1 applicants/admits table had values shifted by one row so a naive consumer would silently read wrong numbers for every applicant count. See [`docs/known-issues/`](../known-issues/) for details.

Any V1 that promised "clean, normalized CDS data" would either lie about corrupted fields or block indefinitely on the long tail of extraction bugs.

## Decision

V1 publishes **raw Docling JSON output** alongside the source PDF, with no cleanup, normalization, or schema. The only promise is "this is what Docling saw in the PDF on this date, produced by this version of Docling."

Cleanup lives as a separate, versionable, contributable layer above the raw output. The data model explicitly supports multiple cleaners coexisting as different `cds_artifacts` rows tagged with `(producer, producer_version)`. A future `cds_schema_v1` will define a target shape that cleaners can normalize toward, but that's a post-V1 concern.

## Why

Two reasons, both about honesty.

First, publishing raw output is a promise we can keep today. "Here is the ground truth Docling produced, here is the source PDF, verify for yourself" is a contract with no hidden corruption. A consumer who reads a raw artifact and gets burned by an extraction bug can see exactly what happened and fix it themselves.

Second, it unblocks contributors. If V1 tried to ship cleaned data, any cleanup improvement would require us to be the bottleneck. By publishing raw and treating cleaners as pluggable artifacts, anyone can write a cleaner, publish its output alongside ours, and let consumers pick. This is the same pattern Hugging Face datasets and Common Crawl use and it scales well.

## Trade-offs accepted

- Non-technical users cannot consume V1 directly. They need a cleaner in between. This is fine because V1's audience is developers and researchers; non-technical users are a V2 concern.
- Raw artifacts contain real, known bugs (e.g., HMC C1 corruption). We document them loudly in per-school `known_issues.md` files rather than try to hide them.
- Consumers who naively read raw Docling JSON will still get wrong numbers in some schools. The README must make this unambiguous.
