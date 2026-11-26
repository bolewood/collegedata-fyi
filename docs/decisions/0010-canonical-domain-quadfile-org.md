# ADR 0010: Canonical domain is quadfile.org

**Date:** 2026-11-26
**Status:** Accepted
**Supersedes:** [ADR 0004 — Canonical domain is collegedata.fyi](0004-canonical-domain-collegedata-fyi.md)

## Decision

1. The site name is Quadfile. The canonical origin is `https://www.quadfile.org`.
2. The apex `quadfile.org` redirects to `www.quadfile.org` with a 301 (`web/src/lib/apex-redirect.ts`).
3. The public PostgREST API is served at `https://api.quadfile.org`. Runtime
   callers read their API origin from environment (`SUPABASE_URL` /
   `NEXT_PUBLIC_SUPABASE_URL`) and default to the project origin, so a
   credentialed request never depends on a redirect from the custom API host.
4. The old hosts stay up for 12 months after cutover, then are retired:
   - `collegedata.fyi` and `www.collegedata.fyi`: `/api/*` answers 308 and every
     other path answers 301, both to the same path on `https://www.quadfile.org`
     (`web/src/lib/old-site-redirect.ts`, placed first in `redirects()`). A
     retired school alias on an old host reaches its final page in at most two
     hops.
   - `api.collegedata.fyi`: handled by `web/src/lib/old-api-host.ts` (public
     storage objects redirect to `api.quadfile.org`; other requests are proxied
     to the project origin).
5. Compatibility accepted for the sunset period: the `X-CollegeData-Client`
   header family, `COLLEGEDATA_API_BASE` / `COLLEGEDATA_SNAPSHOT_DATE`, and the
   `collegedata-*` client identities and User-Agents. New code sends the
   `X-Quadfile-Client` header, `QUADFILE_*` variables and `quadfile-*` identities.
6. Package names: `@quadfile/cli` and `quadfile-mcp`. The MCP server reports the
   name `quadfile`.
7. The owner of record is Bolewood Group, LLC. The footer carries a plain-text
   note that the site was formerly collegedata.fyi.

## Consequences

- Canonical URLs, Open Graph URLs, JSON-LD, sitemaps and API envelopes use the
  new origin; no page head carries the old name.
- Historical PRDs, postmortems, plans, the changelog and applied migrations keep
  the old name as written.
