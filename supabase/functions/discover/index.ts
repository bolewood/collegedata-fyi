// discover — HTTP dev entry for the archive pipeline's resolver.
//
// This function is the operator's tight edit-run loop for the landing-page
// resolver. It is NOT on the cron. It does NOT write to the database or
// Storage. It takes a list of school ids and returns the resolved document
// URL + cds_year (or the classified failure mode) for each one as JSON.
//
// Production traffic goes through archive-enqueue (monthly seeder) and
// archive-process (30s queue consumer). Those will be PRs 3 and 4. Real
// writes happen only via archive-process, which has no public HTTP surface
// — it is invoked by pg_cron with the service-role key and by direct
// operator action via psql or a queue-row insert.
//
// Why no ?archive=1 here: codex review flagged that verify_jwt=true only
// validates that a JWT is valid, not that it belongs to an operator. Any
// authenticated user of the project could have triggered service-role
// writes through this function. Rather than add an operator-token gate
// (another secret to manage, same attack surface if it leaks), discover
// stays a pure dry-run dev entry with no write path. Operator backfill is
// documented in PR 3 as "insert a row into archive_queue with a unique
// run_id and let the 30s cron pick it up."
//
// Usage:
//   GET  .../functions/v1/discover?schools=yale,mit,fairfield
//     → returns a JSON report for each requested school:
//       { mode: 'dry_run', count: N, results: [
//           { school_id, school_name, cds_url_hint, result }
//       ]}
//     where `result` is the ResolveResult discriminated union from
//     _shared/resolve.ts (kind: resolved | upstream_gone | transient |
//     no_cds_found | unsupported_content | blocked_url).
//
// History: this file used to be the M1a dry-run prototype with 8 pilot
// schools embedded inline. The parsing/resolver logic moved to
// _shared/resolve.ts so archive-process can reuse it. The pilot list is
// replaced by a schools.yaml fetch via _shared/schools.ts so new schools
// land without a redeploy.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

import { resolveCdsForSchool } from "../_shared/resolve.ts";
import { fetchSchoolsYaml, filterArchivable } from "../_shared/schools.ts";

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);
  const schoolFilter = url.searchParams.get("schools")?.split(",").map((s) =>
    s.trim()
  ).filter(Boolean);

  if (!schoolFilter || schoolFilter.length === 0) {
    return json({
      error:
        "discover is the resolver dev entry. Supply ?schools=id1,id2 (comma-separated school ids from schools.yaml).",
    }, 400);
  }

  // Cap the fan-out so an operator passing a long list doesn't burn through
  // GitHub rate limits on schools.yaml and doesn't run the fetch concurrency
  // up into edge-function memory pressure. 10 is well under the 25-subpage
  // cap per school the resolver already enforces.
  if (schoolFilter.length > 10) {
    return json({
      error: "discover dry-run is capped at 10 schools per request",
      supplied: schoolFilter.length,
    }, 400);
  }

  const { entries: allSchools } = await fetchSchoolsYaml();
  const targets = filterArchivable(allSchools).filter((s) =>
    schoolFilter.includes(s.id)
  );

  if (targets.length === 0) {
    return json({
      error: `no matching active schools in schools.yaml for ids: ${
        schoolFilter.join(",")
      }`,
      hint:
        "Schools with sub_institutions (e.g. columbia) are intentionally excluded in V1.",
    }, 404);
  }

  // Serialize the resolver calls. Parallelism here isn't worth the memory
  // pressure or the risk of burying an error in a Promise.all rejection
  // shape. The resolver itself still parallelizes the two-hop subpage walk
  // per school via Promise.all inside resolveCdsForSchool.
  const results: unknown[] = [];
  for (const s of targets) {
    try {
      const result = await resolveCdsForSchool(s.cds_url_hint);
      results.push({
        school_id: s.id,
        school_name: s.name,
        cds_url_hint: s.cds_url_hint,
        result,
      });
    } catch (e) {
      results.push({
        school_id: s.id,
        school_name: s.name,
        cds_url_hint: s.cds_url_hint,
        error: (e as Error).message,
      });
    }
  }

  return json({ mode: "dry_run", count: results.length, results });
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}
