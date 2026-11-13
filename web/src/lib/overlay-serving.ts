// PRD 038 A2/A3/A13: which `tier2_template_overlay` values the web may serve. Pure (no Supabase, no Next):
// the rules mirror tools/browser_backend/overlay_serving.py and supabase/pending/038_overlay_serving.sql, and
// all three are pinned by tools/browser_backend/fixtures/overlay_parity.json.
//
// The served-class set comes from the server-only env var OVERLAY_SERVE_CLASSES (never NEXT_PUBLIC_). It is read on
// each fetchExtract call from the server runtime's environment, and Vercel fixes a deployment's environment at build
// time, so changing it needs a redeploy. Default: empty = nothing served.

import type { ArtifactRow, FieldValue } from "./types";

export const OVERLAY_PRODUCER = "tier2_template_overlay";
export const OVERLAY_BASE_PRODUCER = "tier4_docling";
export const OVERLAY_ENV_VAR = "OVERLAY_SERVE_CLASSES";

export const KNOWN_OVERLAY_CLASSES: ReadonlySet<string> = new Set([
  "numeric",
  "choice",
  "checkbox_box",
  "checkbox_boxless",
  "free_text",
  "ocr_numeric",
]);

/** Comma-separated class names -> the served set. Empty or missing -> empty. Unknown name -> empty (fail closed). */
export function parseOverlayServeClasses(raw: string | null | undefined): ReadonlySet<string> {
  if (raw == null) return new Set();
  const names = raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  if (names.length === 0 || names.some((name) => !KNOWN_OVERLAY_CLASSES.has(name))) return new Set();
  return new Set(names);
}

export function overlayServeClassesFromEnv(
  env: Record<string, string | undefined> = process.env,
): ReadonlySet<string> {
  return parseOverlayServeClasses(env[OVERLAY_ENV_VAR]);
}

/** A stable string for the served set: part of the `unstable_cache` key, so a redeploy with a new set never reads old entries. */
export function overlayServeKey(classes: ReadonlySet<string>): string {
  return classes.size === 0 ? "off" : `on:${Array.from(classes).sort().join("+")}`;
}

type OverlayNotes = {
  source_sha256?: string | null;
  source_artifact?: { sha256?: string | null } | null;
  held?: unknown;
  values?: unknown;
};

function notesOf(row: ArtifactRow | null | undefined): OverlayNotes {
  const notes = row?.notes;
  return notes && typeof notes === "object" && !Array.isArray(notes) ? (notes as OverlayNotes) : {};
}

export function recordedSourceSha(row: ArtifactRow | null | undefined): string | null {
  const notes = notesOf(row);
  const sha = notes.source_sha256 || notes.source_artifact?.sha256;
  return sha ? String(sha) : null;
}

/** Held unless `notes.held` is exactly false: an artifact without the mark is not served. */
export function overlayIsHeld(row: ArtifactRow): boolean {
  return notesOf(row).held !== false;
}

export function overlayMatchesBase(base: ArtifactRow | null, overlay: ArtifactRow): boolean {
  if (!base || overlay.kind !== "cleaned" || overlay.producer !== OVERLAY_PRODUCER) return false;
  if (base.producer !== OVERLAY_BASE_PRODUCER) return false;
  // Both schema versions non-null and equal: the overlay's ids follow its template year; a Tier 4 artifact without a
  // schema version carries 2025-26 ids whatever the template (A13).
  if (!base.schema_version || !overlay.schema_version || base.schema_version !== overlay.schema_version) return false;
  const baseSha = recordedSourceSha(base);
  const overlaySha = notesOf(overlay).source_sha256;
  if (!baseSha || !overlaySha || String(overlaySha) !== baseSha) return false;
  return !overlayIsHeld(overlay);
}

/** The newest overlay artifact that may merge onto `base` (ties by id, like the other joins). */
export function pickOverlay(base: ArtifactRow | null, artifacts: ArtifactRow[]): ArtifactRow | null {
  const matching = artifacts.filter((row) => overlayMatchesBase(base, row));
  if (matching.length === 0) return null;
  matching.sort((a, b) => {
    const left = `${a.created_at ?? ""}`;
    const right = `${b.created_at ?? ""}`;
    if (left !== right) return left < right ? 1 : -1;
    return `${a.id}` < `${b.id}` ? 1 : -1;
  });
  return matching[0];
}

function isTwo(x: unknown): boolean {
  // 2, 2.0 and "2" (also "2.0", surrounding spaces) are the number two; booleans and everything else are not.
  if (typeof x === "number") return x === 2;
  if (typeof x === "string" && /^\s*[0-9]+(\.[0-9]+)?\s*$/.test(x)) return Number(x) === 2;
  return false;
}

function hasLane2Evidence(record: Record<string, unknown>): boolean {
  const derived = record.derived_lanes;
  return isTwo(record.lane) || (Array.isArray(derived) && derived.some(isTwo));
}

/** `value_decoded` when it is non-blank, else `value`; trimmed; null when both are blank (mirrors overlay_serving._record_text). */
export function recordText(record: unknown): string | null {
  if (!record || typeof record !== "object") return null;
  const r = record as Record<string, unknown>;
  for (const raw of [r.value_decoded, r.value]) {
    if (raw === null || raw === undefined) continue;
    const text = String(raw).trim();
    if (text) return text;
  }
  return null;
}

/** The overlay values a consumer may serve. `classes` is required: never the producer's own default set. A blank value is
 *  not merged (it never overwrites a populated Tier 4 value) and a `values` that is not a plain object serves nothing. */
export function serveOverlayValues(
  values: unknown,
  classes: ReadonlySet<string>,
): Record<string, FieldValue> {
  const out: Record<string, FieldValue> = {};
  if (classes.size === 0 || !values || typeof values !== "object" || Array.isArray(values)) return out;
  for (const [key, record] of Object.entries(values as Record<string, unknown>)) {
    if (!record || typeof record !== "object" || Array.isArray(record)) continue;
    const r = record as Record<string, unknown>;
    if (!classes.has(String(r.emission_class)) || hasLane2Evidence(r) || recordText(r) === null) continue;
    out[key] = record as FieldValue;
  }
  return out;
}

export type OverlayMergeInput = {
  /** The newest canonical artifact (what `fetchExtract` shows today). */
  canonical: ArtifactRow | null;
  /** Fallback values already filtered for compatibility with `canonical`. */
  fallbackValues: Record<string, FieldValue>;
  /** Every `producer = tier2_template_overlay` artifact for the document. */
  overlayCandidates: ArtifactRow[];
  classes: ReadonlySet<string>;
};

export type OverlayMergeResult = {
  mergedValues: Record<string, FieldValue>;
  overlay: ArtifactRow | null;
  overlayFields: string[];
};

/** `fallback || tier4 base || overlay`: the overlay wins. With an empty set this is the old merge and touches no overlay row. */
export function mergeWithOverlay({
  canonical,
  fallbackValues,
  overlayCandidates,
  classes,
}: OverlayMergeInput): OverlayMergeResult {
  const canonicalValues = (notesOf(canonical).values ?? {}) as Record<string, FieldValue>;
  const mergedValues: Record<string, FieldValue> = { ...fallbackValues, ...canonicalValues };
  if (classes.size === 0) return { mergedValues, overlay: null, overlayFields: [] };
  const overlay = pickOverlay(canonical, overlayCandidates);
  if (!overlay) return { mergedValues, overlay: null, overlayFields: [] };
  const served = serveOverlayValues(notesOf(overlay).values, classes);
  const fields = Object.keys(served);
  if (fields.length === 0) return { mergedValues, overlay: null, overlayFields: [] };
  for (const key of fields) mergedValues[key] = served[key];
  return { mergedValues, overlay, overlayFields: fields };
}
