// Tests for probe_outcome.ts. Pure functions; no DB or network.

import { assertEquals } from "jsr:@std/assert";
import {
  authWallOutcome,
  categoriseLegacyError,
  DEFAULT_COOLDOWN_DAYS,
  PROBE_OUTCOME_VALUES,
  type ProbeOutcome,
} from "./probe_outcome.ts";

// ─── authWallOutcome ────────────────────────────────────────────────────────

Deno.test("authWallOutcome: Microsoft SAML host detected", () => {
  assertEquals(
    authWallOutcome(
      "https://login.microsoftonline.com/712a36c7-3e2d-4f6f-87d0-3192d156f77d/saml2",
    ),
    "auth_walled_microsoft",
  );
});

Deno.test("authWallOutcome: Microsoft tenant subdomain detected", () => {
  assertEquals(
    authWallOutcome("https://tenant.login.microsoftonline.com/saml"),
    "auth_walled_microsoft",
  );
});

Deno.test("authWallOutcome: Okta tenant subdomain detected", () => {
  assertEquals(
    authWallOutcome("https://acme.okta.com/login/login.htm"),
    "auth_walled_okta",
  );
});

Deno.test("authWallOutcome: bare okta.com detected", () => {
  assertEquals(
    authWallOutcome("https://okta.com/saml"),
    "auth_walled_okta",
  );
});

Deno.test("authWallOutcome: Google accounts host detected", () => {
  assertEquals(
    authWallOutcome("https://accounts.google.com/o/saml2/initsso"),
    "auth_walled_google",
  );
});

Deno.test("authWallOutcome: non-auth host returns null", () => {
  assertEquals(authWallOutcome("https://oir.brown.edu/foo.pdf"), null);
});

Deno.test("authWallOutcome: malformed URL returns null", () => {
  assertEquals(authWallOutcome("not a url"), null);
});

Deno.test("authWallOutcome: hostname matching is case-insensitive", () => {
  assertEquals(
    authWallOutcome("https://LOGIN.MICROSOFTONLINE.COM/saml"),
    "auth_walled_microsoft",
  );
});

// ─── categoriseLegacyError ──────────────────────────────────────────────────

Deno.test("categoriseLegacyError: Microsoft SAML in error string", () => {
  assertEquals(
    categoriseLegacyError(
      "PermanentError: unknown content type for https://login.microsoftonline.com/.../saml2?...",
    ),
    "auth_walled_microsoft",
  );
});

Deno.test("categoriseLegacyError: HTTP 404 → dead_url", () => {
  assertEquals(
    categoriseLegacyError("PermanentError: download HTTP 404 at https://x.edu/cds.pdf"),
    "dead_url",
  );
});

Deno.test("categoriseLegacyError: HTTP 410 → dead_url", () => {
  assertEquals(
    categoriseLegacyError("download HTTP 410 at https://x.edu/cds.pdf"),
    "dead_url",
  );
});

Deno.test("categoriseLegacyError: HTTP 503 → transient", () => {
  assertEquals(
    categoriseLegacyError("download HTTP 503 at https://x.edu/cds.pdf"),
    "transient",
  );
});

Deno.test("categoriseLegacyError: timeout → transient", () => {
  assertEquals(
    categoriseLegacyError("download fetch failed: connection timeout"),
    "transient",
  );
});

Deno.test("categoriseLegacyError: 'no cds found' → no_pdfs_found", () => {
  assertEquals(
    categoriseLegacyError(
      "PermanentError: resolve no cds found: landing parsed, no CDS-ish document anchors and no subpages",
    ),
    "no_pdfs_found",
  );
});

Deno.test("categoriseLegacyError: 'magic' bytes → wrong_content_type", () => {
  assertEquals(
    categoriseLegacyError(
      "unknown content type for https://x.edu/cds.pdf: text/html, bytes do not match PDF/XLSX/DOCX magic",
    ),
    "wrong_content_type",
  );
});

Deno.test("categoriseLegacyError: 'blocked unsafe URL' → blocked_url", () => {
  assertEquals(
    categoriseLegacyError("download blocked unsafe URL: http://10.0.0.1/x.pdf"),
    "blocked_url",
  );
});

Deno.test("categoriseLegacyError: file-too-large → file_too_large", () => {
  assertEquals(
    categoriseLegacyError(
      "file exceeds 52428800 bytes (Content-Length 60000000) at https://x.edu/big.pdf",
    ),
    "file_too_large",
  );
});

Deno.test("categoriseLegacyError: aggregated multi-candidate auth-wall", () => {
  // Real shape from the 2026-04-18 Adelphi force-resolve output:
  // multiple candidates all redirected to login.microsoftonline.com.
  // Aggregator concatenates the per-candidate errors with "; ".
  assertEquals(
    categoriseLegacyError(
      "all 6 candidate(s) failed permanently: " +
        "https://intranet.adelphi.edu/wp-content/uploads/2023/03/2022-2023-Common-Data-Set.pdf: " +
        "unknown content type for https://login.microsoftonline.com/.../saml2: text/html",
    ),
    "auth_walled_microsoft",
  );
});

Deno.test("categoriseLegacyError: unknown shape → permanent_other", () => {
  assertEquals(
    categoriseLegacyError("something completely unrecognized"),
    "permanent_other",
  );
});

Deno.test("categoriseLegacyError: empty string → null", () => {
  assertEquals(categoriseLegacyError(""), null);
});

// ─── DEFAULT_COOLDOWN_DAYS ──────────────────────────────────────────────────

Deno.test("DEFAULT_COOLDOWN_DAYS: every ProbeOutcome has a window", () => {
  for (const outcome of PROBE_OUTCOME_VALUES) {
    const days = DEFAULT_COOLDOWN_DAYS[outcome];
    if (typeof days !== "number" || days < 0) {
      throw new Error(`outcome ${outcome} has invalid cooldown: ${days}`);
    }
  }
});

Deno.test("DEFAULT_COOLDOWN_DAYS: success outcomes that did real work have no cooldown", () => {
  // inserted/refreshed/unchanged_repaired produced new artifacts; we
  // don't want to throttle re-checks of recently-changing schools.
  assertEquals(DEFAULT_COOLDOWN_DAYS["inserted"], 0);
  assertEquals(DEFAULT_COOLDOWN_DAYS["refreshed"], 0);
  assertEquals(DEFAULT_COOLDOWN_DAYS["unchanged_repaired"], 0);
});

Deno.test("DEFAULT_COOLDOWN_DAYS: transient retries next cron (zero cooldown)", () => {
  // TransientError is supposed to retry — applying a cooldown would
  // contradict design intent.
  assertEquals(DEFAULT_COOLDOWN_DAYS["transient"], 0);
});

Deno.test("DEFAULT_COOLDOWN_DAYS: auth-walled outcomes share the longest cooldown", () => {
  // Schools rarely un-wall their archives; quarterly re-check is
  // generous enough to catch policy changes without burning cron.
  assertEquals(DEFAULT_COOLDOWN_DAYS["auth_walled_microsoft"], 90);
  assertEquals(DEFAULT_COOLDOWN_DAYS["auth_walled_okta"], 90);
  assertEquals(DEFAULT_COOLDOWN_DAYS["auth_walled_google"], 90);
});

Deno.test("DEFAULT_COOLDOWN_DAYS: unchanged_verified gets its 30d window", () => {
  // The cost signal that motivated PR 1 — schools whose CDS file
  // changes maybe annually should be re-checked monthly, not weekly.
  assertEquals(DEFAULT_COOLDOWN_DAYS["unchanged_verified"], 30);
});
