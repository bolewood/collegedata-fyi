import { authWallOutcome, type ProbeOutcome } from "./probe_outcome.ts";

function htmlPreview(bytes: Uint8Array): string {
  return new TextDecoder("utf-8", { fatal: false })
    .decode(bytes.slice(0, 64 * 1024))
    .toLowerCase();
}

function hasAny(value: string, needles: string[]): boolean {
  return needles.some((needle) => value.includes(needle));
}

export function rejectableHtmlSourceOutcome(
  bytes: Uint8Array,
  finalUrl: string,
): ProbeOutcome | null {
  const finalUrlOutcome = authWallOutcome(finalUrl);
  if (finalUrlOutcome) return finalUrlOutcome;

  let host = "";
  try {
    host = new URL(finalUrl).hostname.toLowerCase();
  } catch {
    // Continue with body classification.
  }

  const text = htmlPreview(bytes);
  const haystack = `${host}\n${text}`;

  if (
    hasAny(haystack, [
      "login.microsoftonline.com",
      "sign in to your account",
      "aadcdn",
      "samlrequest",
      "microsoft corporation. all rights reserved",
    ])
  ) {
    return "auth_walled_microsoft";
  }

  if (
    hasAny(haystack, [
      "accounts.google.com",
      "service_login",
      "google accounts",
      "google sign in",
      "identifierid",
    ])
  ) {
    return "auth_walled_google";
  }

  if (host.endsWith(".okta.com") || hasAny(haystack, ["okta sign in", "okta-signin"])) {
    return "auth_walled_okta";
  }

  if (
    hasAny(haystack, [
      "cloudflare",
      "just a moment",
      "cf-mitigated",
      "cf-chl-",
      "__cf_chl_",
      "captcha",
      "incapsula incident",
      "imperva",
      "perfdrive",
      "validate.perfdrive.com",
      "access denied",
      "request unsuccessful",
    ])
  ) {
    return "bot_challenge";
  }

  const cdsLike = hasAny(text, [
    "common data set",
    "common dataset",
    "cds",
    "b1 men women another gender",
    "first-time, first-year",
    "degree-seeking undergraduate",
  ]);
  const hasTableMarkup = text.includes("<table") && (
    text.includes("<td") || text.includes("<th")
  );

  if (
    hasAny(text, [
      "404 not found",
      "404 error",
      "page not found",
      "file not found",
      "the page you requested could not be found",
      "server error",
      "temporarily unavailable",
      "please sign in",
      "single sign-on",
      "single sign on",
    ])
  ) {
    return "wrong_content_type";
  }

  if (cdsLike && !hasTableMarkup) {
    return "wrong_content_type";
  }

  return null;
}
