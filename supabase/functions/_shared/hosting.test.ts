// Tests for hosting.ts inference logic. Pure functions; no I/O.
//
// The cases here mirror the plan's "golden fixtures" requirement —
// schools whose hosting facts we already learned the hard way and
// want to lock in as regression coverage. Adding a new school's
// fingerprint here is the right way to encode hosting knowledge.

import { assertEquals } from "jsr:@std/assert";
import {
  eTldPlus1,
  inferAuthRequired,
  inferCms,
  inferFileStorage,
  inferHosting,
  inferRendering,
  inferWaf,
} from "./hosting.ts";

// ─── eTldPlus1 ──────────────────────────────────────────────────────────────

Deno.test("eTldPlus1: simple .edu", () => {
  assertEquals(eTldPlus1("brown.edu"), "brown.edu");
});

Deno.test("eTldPlus1: subdomain collapses to org", () => {
  assertEquals(eTldPlus1("oir.brown.edu"), "brown.edu");
});

Deno.test("eTldPlus1: deep subdomain", () => {
  assertEquals(eTldPlus1("a.b.c.brown.edu"), "brown.edu");
});

Deno.test("eTldPlus1: case-insensitive input", () => {
  assertEquals(eTldPlus1("OIR.Brown.Edu"), "brown.edu");
});

Deno.test("eTldPlus1: IP literal returns verbatim", () => {
  assertEquals(eTldPlus1("10.0.0.1"), "10.0.0.1");
});

Deno.test("eTldPlus1: single-label returns null", () => {
  assertEquals(eTldPlus1("localhost"), null);
});

Deno.test("eTldPlus1: empty returns null", () => {
  assertEquals(eTldPlus1(""), null);
});

// ─── inferAuthRequired ──────────────────────────────────────────────────────

Deno.test("inferAuthRequired: Microsoft SSO redirect target", () => {
  assertEquals(
    inferAuthRequired(
      "https://login.microsoftonline.com/712a36c7-3e2d-4f6f-87d0-3192d156f77d/saml2",
    ),
    "microsoft_sso",
  );
});

Deno.test("inferAuthRequired: Okta", () => {
  assertEquals(
    inferAuthRequired("https://acme.okta.com/login/login.htm"),
    "okta",
  );
});

Deno.test("inferAuthRequired: Google SSO", () => {
  assertEquals(
    inferAuthRequired("https://accounts.google.com/o/saml2/initsso"),
    "google_sso",
  );
});

Deno.test("inferAuthRequired: normal IR landing → none", () => {
  assertEquals(
    inferAuthRequired("https://oir.brown.edu/institutional-data/common-data-set"),
    "none",
  );
});

Deno.test("inferAuthRequired: undefined → unknown", () => {
  assertEquals(inferAuthRequired(undefined), "unknown");
});

// ─── inferCms ───────────────────────────────────────────────────────────────

Deno.test("inferCms: Drupal via X-Generator", () => {
  assertEquals(
    inferCms({ "x-generator": "Drupal 9 (https://www.drupal.org)" }, undefined),
    "drupal",
  );
});

Deno.test("inferCms: WordPress via X-Powered-By", () => {
  assertEquals(
    inferCms({ "x-powered-by": "WordPress" }, undefined),
    "wordpress",
  );
});

Deno.test("inferCms: WordPress via /wp-content/ in URL", () => {
  assertEquals(
    inferCms({}, "https://oira.jhu.edu/wp-content/uploads/CDS_2021-2022.pdf"),
    "wordpress",
  );
});

Deno.test("inferCms: Drupal via /sites/default/files/", () => {
  assertEquals(
    inferCms({}, "https://www.bucknell.edu/sites/default/files/x.pdf"),
    "drupal",
  );
});

Deno.test("inferCms: SharePoint via _layouts path", () => {
  assertEquals(
    inferCms({}, "https://x.sharepoint.com/_layouts/15/x.aspx"),
    "sharepoint",
  );
});

Deno.test("inferCms: no signal → unknown", () => {
  assertEquals(inferCms({ server: "nginx" }, "https://x.edu/foo"), "unknown");
});

// ─── inferWaf ───────────────────────────────────────────────────────────────

Deno.test("inferWaf: Cloudflare via cf-ray header", () => {
  assertEquals(inferWaf({ "cf-ray": "9abc123-IAD" }), "cloudflare");
});

Deno.test("inferWaf: Cloudflare via Server header", () => {
  assertEquals(inferWaf({ "server": "cloudflare" }), "cloudflare");
});

Deno.test("inferWaf: AWS CloudFront via x-amz-cf-id", () => {
  assertEquals(inferWaf({ "x-amz-cf-id": "abc123" }), "aws_cloudfront");
});

Deno.test("inferWaf: Akamai via x-akamai-transformed", () => {
  assertEquals(inferWaf({ "x-akamai-transformed": "9 ...; ..." }), "akamai");
});

Deno.test("inferWaf: Fastly via x-fastly-request-id", () => {
  assertEquals(inferWaf({ "x-fastly-request-id": "abc" }), "fastly");
});

Deno.test("inferWaf: no signal → unknown", () => {
  assertEquals(inferWaf({}), "unknown");
});

// ─── inferRendering ─────────────────────────────────────────────────────────

Deno.test("inferRendering: anchors found → static_html", () => {
  assertEquals(inferRendering(50_000, 5), "static_html");
});

Deno.test("inferRendering: tiny body, no anchors → js_required", () => {
  // SPA-shaped page with empty static HTML
  assertEquals(inferRendering(2_000, 0), "js_required");
});

Deno.test("inferRendering: large body, no anchors → unknown (don't guess)", () => {
  // Probably a normal HTML page that just doesn't have CDS anchors
  assertEquals(inferRendering(100_000, 0), "unknown");
});

Deno.test("inferRendering: missing inputs → unknown", () => {
  assertEquals(inferRendering(undefined, undefined), "unknown");
  assertEquals(inferRendering(50_000, undefined), "unknown");
});

// ─── inferFileStorage ───────────────────────────────────────────────────────

Deno.test("inferFileStorage: all docs on school's eTLD+1 → same_origin", () => {
  assertEquals(
    inferFileStorage("https://oir.brown.edu/cds", [
      { url: "https://oir.brown.edu/files/CDS_2024.pdf" },
      { url: "https://www.brown.edu/sites/files/CDS_2023.pdf" },
    ]),
    "same_origin",
  );
});

Deno.test("inferFileStorage: all docs on Box → box", () => {
  assertEquals(
    inferFileStorage("https://rpi.box.com/v/CDS", [
      { url: "https://rpi.box.com/shared/static/abc.pdf" },
      { url: "https://rpi.box.com/shared/static/def.pdf" },
    ]),
    "box",
  );
});

Deno.test("inferFileStorage: Google Drive", () => {
  assertEquals(
    inferFileStorage("https://drive.google.com/drive/folders/abc", [
      { url: "https://drive.google.com/uc?id=xyz&export=download" },
    ]),
    "google_drive",
  );
});

Deno.test("inferFileStorage: SharePoint", () => {
  assertEquals(
    inferFileStorage("https://x.sharepoint.com/sites/IR/CDS.aspx", [
      { url: "https://x.sharepoint.com/sites/IR/Shared%20Documents/CDS.pdf" },
    ]),
    "sharepoint",
  );
});

Deno.test("inferFileStorage: same_origin + Box → mixed", () => {
  assertEquals(
    inferFileStorage("https://oir.brown.edu/cds", [
      { url: "https://oir.brown.edu/files/CDS_2024.pdf" },
      { url: "https://brown.box.com/shared/static/old-CDS.pdf" },
    ]),
    "mixed",
  );
});

Deno.test("inferFileStorage: empty docs → unknown", () => {
  assertEquals(inferFileStorage("https://x.edu/cds", []), "unknown");
});

Deno.test("inferFileStorage: undefined docs → unknown", () => {
  assertEquals(inferFileStorage("https://x.edu/cds", undefined), "unknown");
});

// ─── inferHosting (top-level orchestration) ─────────────────────────────────

Deno.test("inferHosting golden: Adelphi (intranet behind Microsoft SSO)", () => {
  // Adelphi's hint points at intranet.adelphi.edu. Resolver fetches
  // it; download follows redirect; final URL is login.microsoftonline.com.
  // The intranet domain IS adelphi.edu (same eTLD+1) so file_storage
  // would naively read same_origin — but auth_required != none should
  // promote it to "intranet".
  const inference = inferHosting({
    hintUrl:
      "https://intranet.adelphi.edu/wp-content/uploads/2023/03/2022-2023-Common-Data-Set.pdf",
    finalUrl:
      "https://login.microsoftonline.com/712a36c7-3e2d-4f6f-87d0-3192d156f77d/saml2",
    headers: {},
    resolvedDocs: [
      {
        url:
          "https://intranet.adelphi.edu/wp-content/uploads/2023/03/2022-2023-Common-Data-Set.pdf",
      },
    ],
  });
  assertEquals(inference.auth_required, "microsoft_sso");
  assertEquals(inference.file_storage, "intranet");
  assertEquals(inference.origin_domain, "adelphi.edu");
  assertEquals(inference.final_url_host, "login.microsoftonline.com");
});

Deno.test("inferHosting golden: RPI (Box-hosted CDS)", () => {
  const inference = inferHosting({
    hintUrl: "https://rpi.box.com/v/CDS",
    finalUrl: "https://rpi.box.com/v/CDS",
    headers: {},
    resolvedDocs: [
      { url: "https://rpi.box.com/shared/static/2023.pdf" },
      { url: "https://rpi.box.com/shared/static/2024.pdf" },
    ],
  });
  assertEquals(inference.file_storage, "box");
  assertEquals(inference.auth_required, "none");
});

Deno.test("inferHosting golden: WordPress IR (JHU pattern)", () => {
  const inference = inferHosting({
    hintUrl: "https://oira.jhu.edu/common-data-set/",
    finalUrl: "https://oira.jhu.edu/common-data-set/",
    headers: { "x-powered-by": "WordPress" },
    bodyLength: 80_000,
    anchorCount: 7,
    resolvedDocs: [
      { url: "https://oira.jhu.edu/wp-content/uploads/CDS_2021-2022.pdf" },
    ],
  });
  assertEquals(inference.cms, "wordpress");
  assertEquals(inference.file_storage, "same_origin");
  assertEquals(inference.rendering, "static_html");
});

Deno.test("inferHosting golden: Drupal IR (Bucknell pattern)", () => {
  const inference = inferHosting({
    hintUrl: "https://www.bucknell.edu/commondataset/",
    finalUrl: "https://www.bucknell.edu/commondataset/",
    headers: { "x-generator": "Drupal 10" },
    bodyLength: 120_000,
    anchorCount: 15,
    resolvedDocs: [
      { url: "https://www.bucknell.edu/sites/default/files/cds_2024.pdf" },
    ],
  });
  assertEquals(inference.cms, "drupal");
  assertEquals(inference.file_storage, "same_origin");
});

Deno.test("inferHosting golden: Cloudflare-fronted school", () => {
  const inference = inferHosting({
    hintUrl: "https://example-school.edu/ir/cds",
    finalUrl: "https://example-school.edu/ir/cds",
    headers: { "cf-ray": "9abc-IAD", "server": "cloudflare" },
    bodyLength: 50_000,
    anchorCount: 5,
    resolvedDocs: [
      { url: "https://example-school.edu/files/cds_2024.pdf" },
    ],
  });
  assertEquals(inference.waf, "cloudflare");
});

Deno.test("inferHosting golden: dmi.illinois.edu (custom CMS, search-engine-blind)", () => {
  // The infamous "Brave can't see this subdomain" school. Hosting-
  // wise unremarkable: no Drupal/WP signals, no WAF in headers.
  // Everything reads as same_origin static. The notable fact about
  // this school is in the operator's `notes` field (manual-source
  // observation), not the inferred dimensions.
  const inference = inferHosting({
    hintUrl:
      "https://www.dmi.illinois.edu/stuenr/misc/cds_2024_2025.xlsx",
    headers: {},
    resolvedDocs: [
      { url: "https://www.dmi.illinois.edu/stuenr/misc/cds_2024_2025.xlsx" },
    ],
  });
  assertEquals(inference.cms, "unknown");
  assertEquals(inference.waf, "unknown");
  assertEquals(inference.file_storage, "same_origin");
  assertEquals(inference.origin_domain, "illinois.edu");
});

Deno.test("inferHosting: minimal probe data still returns valid shape", () => {
  // For Case A (direct doc) probes the resolver may not have any
  // probe data. We still want a structured row in the observation
  // log — just with most dimensions as "unknown".
  const inference = inferHosting({
    hintUrl: "https://oir.yale.edu/cds.pdf",
    resolvedDocs: [{ url: "https://oir.yale.edu/cds.pdf" }],
  });
  assertEquals(inference.cms, "unknown");
  assertEquals(inference.waf, "unknown");
  assertEquals(inference.auth_required, "unknown");
  assertEquals(inference.rendering, "unknown");
  assertEquals(inference.file_storage, "same_origin");
  assertEquals(inference.origin_domain, "yale.edu");
  assertEquals(inference.final_url_host, null);
});
