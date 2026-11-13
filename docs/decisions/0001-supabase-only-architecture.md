# ADR 0001: Supabase-only architecture for V1

**Date:** 2026-04-11
**Status:** Accepted

## Context

V1 needs somewhere to host the manifest (Postgres), the raw PDF + Docling JSON blobs (object storage), the discovery scraper (cron + HTTP fetching), and optionally a public read API. Options considered included Railway, AWS (S3 + Lambda/Fargate), Google Cloud (Cloud Run + GCS), Vercel, and Supabase. All were already paid for by the maintainer.

## Decision

Use Supabase for everything in V1:

- **Supabase Postgres** for the manifest (`cds_documents`, `cds_artifacts`, `cleaners`)
- **Supabase Storage** for raw PDFs and Docling JSON blobs
- **Supabase Edge Functions on cron** for the discovery scraper (Deno, fits lightweight HTTP work)
- **PostgREST** (built into Supabase) as the public read API, served under `api.collegedata.fyi` via custom domain

Docling extraction is the one exception — it's Python, memory-hungry, and can't run inside an edge function. For V1 it runs as a local script on demand (triggered by an "extraction_pending" flag in Postgres). When it grows, the same script moves to a GitHub Actions cron workflow with no architectural change.

## Why

V1's workload is batch jobs and static blob serving, not a live server. Nothing needs autoscaling, nothing needs to be up 24/7, and the hot path is "someone downloads a file" — the cheapest primitive on the internet. Under this shape, Supabase's Postgres + Storage + Edge Functions combination provides every needed primitive in one vendor, with no operational overhead. PostgREST eliminates the need to write a backend at all.

Alternatives were rejected because they either required more ops (AWS), were optimized for always-on workloads (Railway), or would have added a second vendor without removing the first (Vercel for static hosting while Supabase still held data).

## Trade-offs accepted

- Coupling to one vendor. Mitigated by the fact that Postgres, S3-compatible Storage, and Deno edge functions are all portable primitives; migration off Supabase is possible if ever needed.
- Supabase free-tier Storage limits will bite eventually (rough estimate: 500 schools × 5 years × 5MB ≈ 12GB). This is a "nice problem to have" — handled by moving to a paid plan when it matters.
- Docling extraction can't live in the same vendor. Accepted as a pluggable worker contract instead.

## Addendum (2026-11-09): frontend hosting and extraction runtime

This ADR was written before the web frontend existed and does not mention it. Its "Why" section lists Vercel as a rejected alternative for hosting static files while Supabase held the data. Since launch, the Next.js frontend at `collegedata.fyi` has been hosted on Vercel. It reads the public PostgREST API and Edge Functions like any other client and stores no data of its own; Postgres, Storage, the scheduled archive functions, and the public read API remain on Supabase. No ADR has revisited the original rejection, so this addendum records the fact and does not decide the question. The frontend design is in [PRD 002](../prd/002-frontend.md) and [`docs/frontend.md`](../frontend.md).

The Docling exception also moved as the paragraph above predicted: the extraction worker now runs on a daily GitHub Actions cron (`.github/workflows/ops-extraction-worker.yml`), with larger drains run by operators from a lock-file-pinned local environment. See [`docs/data-extraction-pipeline.md`](../data-extraction-pipeline.md).

The original text above is left as written.
