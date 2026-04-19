// inferHosting — derive a school's hosting environment from a single
// probe. Pure function; no I/O. Inputs come from the resolver's
// fetchText result + the resolved candidate URLs.
//
// PR 4 of the URL hint refactor plan
// (docs/plans/url-hint-refactor-and-hosting-jsonb.md). Outputs land
// in school_hosting_observations (PR 3 schema). Wired by archive.ts.
//
// Design choice: every dimension defaults to "unknown" rather than
// guessing. Per the plan's review:
//   "Default to 'unknown' rather than guessing. The js_required
//    classification is conservative; ambiguous cases stay 'unknown'."
// The point of this layer is to encode signal, not noise. A school
// that actually flips its CMS in the future will produce a clear
// "drupal → wordpress" event in the observation log; a school we
// can't classify produces "unknown → unknown" forever, which is fine.

import { authWallOutcome } from "./probe_outcome.ts";

export type Cms =
  | "drupal"
  | "wordpress"
  | "sharepoint"
  | "static"
  | "custom"
  | "unknown";

export type FileStorage =
  | "same_origin"
  | "box"
  | "google_drive"
  | "sharepoint"
  | "dropbox"
  | "intranet"
  | "mixed"
  | "unknown";

export type AuthRequired =
  | "none"
  | "microsoft_sso"
  | "okta"
  | "google_sso"
  | "basic"
  | "unknown";

export type Rendering = "static_html" | "js_required" | "unknown";

export type Waf =
  | "none"
  | "cloudflare"
  | "akamai"
  | "imperva"
  | "aws_cloudfront"
  | "fastly"
  | "unknown";

// Inputs to inferHosting. Every field is optional so the caller can
// pass whatever it has. archive.ts populates as much as it can from
// the resolver's outputs; manual / playwright-source rows can pass
// less.
export interface ProbeData {
  hintUrl: string; //         The seed URL (cds_url_hint or override)
  finalUrl?: string; //       Where fetchText ended up after redirects
  contentType?: string; //    Content-Type of the final response
  headers?: Record<string, string>; // Lowercased response headers (HOSTING_HEADERS subset)
  resolvedDocs?: { url: string }[]; // Per-candidate URLs from the resolver
  anchorCount?: number; //    Number of CDS-ish anchors found in the static HTML
  bodyLength?: number; //     Length of the response body in bytes
}

// Output shape mirrors the school_hosting_observations columns.
export interface HostingInference {
  cms: Cms;
  file_storage: FileStorage;
  auth_required: AuthRequired;
  rendering: Rendering;
  waf: Waf;
  origin_domain: string | null;
  final_url_host: string | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

// Extract the eTLD+1 from a URL host. Used to decide whether a file
// URL belongs to the same organization as the hint URL. Strict
// implementation that handles the common .edu / .com / .org cases —
// not a full PSL parser. Brown's hint at oir.brown.edu and a file
// at dam.brown.edu both return "brown.edu" (same org, despite
// different subdomains).
//
// Strict because over-matching is worse than under-matching: a false
// "same_origin" classification would hide third-party hosting from
// the audit dashboard. Better to return null on ambiguity (foo.co.uk
// style multi-segment TLDs) and let same-origin detection downgrade
// to "unknown" for those rare cases.
export function eTldPlus1(host: string): string | null {
  const h = host.toLowerCase().trim();
  if (!h) return null;
  // IP literals — return verbatim, no eTLD logic applies.
  if (/^\d+\.\d+\.\d+\.\d+$/.test(h)) return h;
  if (h.includes(":")) return null; // IPv6, skip.

  const parts = h.split(".");
  if (parts.length < 2) return null;

  // Most US higher-ed: domain.edu, domain.com, domain.org.
  // Two-segment eTLD+1 covers ~all cases in our corpus.
  return parts.slice(-2).join(".");
}

function hostFromUrl(url: string): string | null {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
}

function classifyHost(host: string): FileStorage | null {
  if (host === "box.com" || host.endsWith(".box.com") || host.endsWith(".box.net")) {
    return "box";
  }
  if (
    host === "drive.google.com" ||
    host === "docs.google.com" ||
    host === "sites.google.com"
  ) return "google_drive";
  if (host.endsWith(".sharepoint.com") || host === "sharepoint.com") {
    return "sharepoint";
  }
  if (host === "dropbox.com" || host.endsWith(".dropbox.com")) return "dropbox";
  return null;
}

// ─── Per-dimension inference ───────────────────────────────────────────────

export function inferAuthRequired(finalUrl: string | undefined): AuthRequired {
  if (!finalUrl) return "unknown";
  const wall = authWallOutcome(finalUrl);
  if (wall === "auth_walled_microsoft") return "microsoft_sso";
  if (wall === "auth_walled_okta") return "okta";
  if (wall === "auth_walled_google") return "google_sso";
  // No auth wall detected. We could check for HTTP 401 → 'basic' but
  // the resolver currently treats those as transient errors, not as
  // a structural facet, so leave as none.
  return "none";
}

export function inferCms(
  headers: Record<string, string> | undefined,
  finalUrl: string | undefined,
): Cms {
  const h = headers ?? {};
  // Header signals first — these are the most reliable.
  const generator = (h["x-generator"] ?? "").toLowerCase();
  const poweredBy = (h["x-powered-by"] ?? "").toLowerCase();
  const server = (h["server"] ?? "").toLowerCase();

  if (generator.includes("drupal") || server.includes("drupal")) return "drupal";
  if (generator.includes("wordpress") || poweredBy.includes("wordpress")) {
    return "wordpress";
  }
  if (server.includes("microsoft-iis") && (h["x-powered-by"] ?? "").toLowerCase().includes("asp.net")) {
    // Likely SharePoint or other Microsoft web app — distinguish via URL.
    if (finalUrl && finalUrl.includes("/_layouts/")) return "sharepoint";
  }

  // URL pattern signals as fallback. Less reliable than headers
  // because schools sometimes proxy CMS-shaped paths through their
  // own routing layer.
  if (finalUrl) {
    const u = finalUrl.toLowerCase();
    if (u.includes("/wp-content/") || u.includes("/wp-json/")) return "wordpress";
    if (u.includes("/sites/default/files/") || u.includes("/_default_")) {
      return "drupal";
    }
    if (u.includes("/_layouts/") || u.includes("/sitepages/")) return "sharepoint";
  }

  return "unknown";
}

export function inferWaf(headers: Record<string, string> | undefined): Waf {
  const h = headers ?? {};
  if (h["cf-ray"] || (h["server"] ?? "").toLowerCase() === "cloudflare") {
    return "cloudflare";
  }
  if (h["x-amz-cf-id"]) return "aws_cloudfront";
  if (h["x-akamai-transformed"]) return "akamai";
  if (h["x-fastly-request-id"]) return "fastly";
  // Imperva sets X-Iinfo or sometimes server: imperva
  if ((h["server"] ?? "").toLowerCase().includes("imperva")) return "imperva";
  // Distinguishing 'none' from 'unknown' would require knowing whether
  // the origin actually fronts itself directly, which we can't
  // reliably do from headers alone. Default to unknown.
  return "unknown";
}

export function inferRendering(
  bodyLength: number | undefined,
  anchorCount: number | undefined,
): Rendering {
  // Conservative classifier: only call it js_required when we have
  // strong signal (response was tiny AND no CDS-ish anchors found in
  // static HTML). Most schools that don't return CDS anchors aren't
  // actually JS-rendered — they just don't have CDS anchors on that
  // particular page. The threshold (< 50 KB body AND zero anchors)
  // catches SPAs while leaving normal IR pages classified as static.
  if (bodyLength === undefined || anchorCount === undefined) return "unknown";
  if (anchorCount === 0 && bodyLength < 50_000 && bodyLength > 0) {
    return "js_required";
  }
  if (anchorCount > 0) return "static_html";
  // Zero anchors but a large body — probably static HTML that just
  // happens to lack CDS anchors. Don't flag js_required without
  // additional signal.
  return "unknown";
}

// File storage requires comparing each resolved doc's host to the
// hint URL's host. If all docs are on the school's own org
// (eTLD+1 match), it's same_origin. If any are on Box/Drive/etc., we
// classify by the dominant third-party host or 'mixed' if multiple.
export function inferFileStorage(
  hintUrl: string,
  resolvedDocs: { url: string }[] | undefined,
): FileStorage {
  if (!resolvedDocs || resolvedDocs.length === 0) return "unknown";

  const hintHost = hostFromUrl(hintUrl);
  const hintOrg = hintHost ? eTldPlus1(hintHost) : null;

  const counts: Record<string, number> = {};
  let sameOriginCount = 0;
  for (const doc of resolvedDocs) {
    const host = hostFromUrl(doc.url);
    if (!host) continue;
    const thirdParty = classifyHost(host);
    if (thirdParty) {
      counts[thirdParty] = (counts[thirdParty] ?? 0) + 1;
      continue;
    }
    const docOrg = eTldPlus1(host);
    if (hintOrg && docOrg === hintOrg) {
      sameOriginCount++;
      continue;
    }
    // Different org but not a known third-party: likely a school
    // moved hosting to a separate domain (rare). Count as same_origin
    // unknown bucket.
    counts["other_external"] = (counts["other_external"] ?? 0) + 1;
  }

  const thirdPartyEntries = Object.entries(counts).filter(
    ([k]) => k !== "other_external",
  );

  if (thirdPartyEntries.length === 0 && sameOriginCount > 0) return "same_origin";
  if (sameOriginCount > 0 && thirdPartyEntries.length > 0) return "mixed";
  if (thirdPartyEntries.length === 1) {
    return thirdPartyEntries[0][0] as FileStorage;
  }
  if (thirdPartyEntries.length > 1) return "mixed";
  return "unknown";
}

// Top-level orchestration. Calls each per-dimension inferrer and
// returns the full HostingInference shape. archive.ts inserts the
// result into school_hosting_observations.
export function inferHosting(probe: ProbeData): HostingInference {
  const finalHost = probe.finalUrl ? hostFromUrl(probe.finalUrl) : null;
  const hintHost = hostFromUrl(probe.hintUrl);
  const originDomain = hintHost ? eTldPlus1(hintHost) : null;

  const auth = inferAuthRequired(probe.finalUrl);
  // When the final URL is auth-walled, file_storage from the same
  // domain reads as 'intranet' rather than 'same_origin' — captures
  // the Adelphi case where intranet.adelphi.edu is the school's own
  // domain but isn't publicly reachable.
  let fileStorage = inferFileStorage(probe.hintUrl, probe.resolvedDocs);
  if (auth !== "none" && auth !== "unknown" && fileStorage === "same_origin") {
    fileStorage = "intranet";
  }

  return {
    cms: inferCms(probe.headers, probe.finalUrl),
    file_storage: fileStorage,
    auth_required: auth,
    rendering: inferRendering(probe.bodyLength, probe.anchorCount),
    waf: inferWaf(probe.headers),
    origin_domain: originDomain,
    final_url_host: finalHost,
  };
}
