// collegedata.fyi — discovery scraper
//
// M0 stub. Deployed so we can verify the edge-function deployment path and
// have a live endpoint to POST against, but the real scraper logic arrives
// in M1. See docs/v1-plan.md and tools/finder/seed_urls.md for the design.
//
// When M1 lands, this function will:
//   1. Accept a POST body like { "school_id": "yale", "cds_year": "2024-25" }
//      or run in batch mode against every row in schools.yaml
//   2. Resolve the source URL via per-school overrides, the pbworks seed list,
//      and a ladder of URL-pattern probes + Google dorks
//   3. HEAD-check and download the source file
//   4. Detect format (pdf_fillable / pdf_flat / pdf_scanned / xlsx / docx)
//      via pypdf-style AcroForm probing
//   5. Upload the raw bytes to the `sources` Storage bucket with a
//      deterministic path: {school_id}/{cds_year}/source.{ext}
//   6. Upsert a cds_documents row with source_url, source_sha256,
//      source_format, discovered_at, last_verified_at, extraction_status
//   7. Return a JSON response summarizing the discovery outcome
//
// For now, respond with a stub payload that confirms the function is
// reachable and the environment variables are plumbed correctly.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const PROJECT_REF = Deno.env.get("SUPABASE_PROJECT_REF") ?? "unknown";
const VERSION = "0.0.1-stub";

Deno.serve((req: Request) => {
  const now = new Date().toISOString();
  return new Response(
    JSON.stringify(
      {
        status: "stub",
        function: "discover",
        version: VERSION,
        project_ref: PROJECT_REF,
        method: req.method,
        timestamp: now,
        message:
          "This is the M0 stub for the CDS discovery scraper. " +
          "Real scraper logic lands in M1. See docs/v1-plan.md.",
      },
      null,
      2,
    ),
    {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    },
  );
});
