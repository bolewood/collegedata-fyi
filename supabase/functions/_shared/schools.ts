// schools.yaml loader for edge functions. Fetches the committed file from
// GitHub raw at runtime so new schools land without a function redeploy.
// See the plan for rejected alternatives (embed-at-deploy, push-to-storage-
// on-commit).
//
// PR 5 of the URL hint refactor renamed the YAML field cds_url_hint →
// discovery_seed_url and added an optional browse_url. The loader accepts
// either field name during the migration window so existing schools.yaml
// rows continue to work even if the rename hasn't propagated to every
// row yet. Once the YAML is fully renamed, the back-compat fallback can
// be removed in a follow-up cleanup.

import { parse as parseYaml } from "jsr:@std/yaml";
import { USER_AGENT } from "./resolve.ts";

const SCHOOLS_YAML_URL =
  "https://raw.githubusercontent.com/bolewood/collegedata-fyi/main/tools/finder/schools.yaml";

// school_overrides.yaml is a separate committed file for hand-curated
// per-school data that cannot live in schools.yaml because the latter
// is regenerated from IPEDS by build_school_list.py and would lose any
// nested override structure on regeneration. PR 5 introduced the file
// (with a documented schema); PR 6 wires this loader to read and merge
// it. Operator-supplied browse_url, direct_archive_urls, and
// hosting_override entries land on top of the schools.yaml entry,
// keyed by school_id.
const SCHOOL_OVERRIDES_YAML_URL =
  "https://raw.githubusercontent.com/bolewood/collegedata-fyi/main/tools/finder/school_overrides.yaml";

// Hard cap on how long we wait for the raw YAML fetch. Without this, a
// hanging GitHub request could consume the whole edge function invocation
// and leave the queue un-seeded. 15s is well above typical GitHub response
// time (<1s) but short enough that a stuck request fails fast.
const SCHOOLS_YAML_FETCH_TIMEOUT_MS = 15_000;

interface SubInstitution {
  id: string;
  label: string;
}

// Mirrors the shape in tools/finder/schools.yaml. Only the fields the
// archiver needs are listed; YAML parse tolerates extras.
//
// `discovery_seed_url` is what the resolver fetches as the seed for its
// upgrade path (parent walk, well-known paths, multi-candidate fan-out).
// `browse_url` is the human-friendly URL surfaced by the kids worklist
// and any contributor-facing tool. They differ when a school's seed is
// a direct PDF (good for the resolver, useless for a kid trying to
// browse for new years).
//
// `cds_url_hint` is preserved for back-compat with un-renamed YAML rows
// during the PR 5 migration window.
export interface SchoolEntry {
  id: string;
  name: string;
  domain?: string;
  ipeds_id?: string;
  scrape_policy: "active" | "unknown" | "verified_absent";
  discovery_seed_url?: string | null;
  browse_url?: string | null;
  /** @deprecated use discovery_seed_url; kept as YAML back-compat */
  cds_url_hint?: string | null;
  sub_institutions?: SubInstitution[];
  notes?: string;
}

export interface ArchivableSchool {
  id: string;
  name: string;
  ipeds_id?: string;
  discovery_seed_url: string;
  browse_url?: string;
}

// Operator-supplied per-school overrides. See
// tools/finder/school_overrides.yaml for the source-of-truth schema
// and tools/finder/school_overrides.yaml comments for field semantics.
// Every field is optional; a missing field falls back to the
// schools.yaml entry. hosting_override carries the same enum domains
// as the school_hosting_observations columns of the same name.
export interface DirectArchiveUrl {
  url: string;
  year?: string;
}

export interface HostingOverride {
  cms?: string;
  file_storage?: string;
  auth_required?: string;
  rendering?: string;
  waf?: string;
  notes?: string;
}

export interface SchoolOverride {
  school_id: string;
  browse_url?: string;
  direct_archive_urls?: DirectArchiveUrl[];
  hosting_override?: HostingOverride;
}

function isValidSchoolOverride(raw: unknown): raw is SchoolOverride {
  if (!raw || typeof raw !== "object") return false;
  const o = raw as Record<string, unknown>;
  if (typeof o.school_id !== "string" || o.school_id.length === 0) return false;
  if (o.browse_url !== undefined && o.browse_url !== null && typeof o.browse_url !== "string") {
    return false;
  }
  if (o.direct_archive_urls !== undefined && !Array.isArray(o.direct_archive_urls)) {
    return false;
  }
  if (
    o.hosting_override !== undefined && o.hosting_override !== null &&
    typeof o.hosting_override !== "object"
  ) return false;
  return true;
}

// Validates a raw YAML node matches the minimum shape we rely on. Missing
// or malformed fields would otherwise surface as cryptic runtime errors
// inside the bulk insert (e.g. "null value in column ... violates not-null
// constraint"). Invalid entries are logged and dropped so a single bad row
// can't abort the whole monthly seeding run.
function isValidSchoolEntry(raw: unknown): raw is SchoolEntry {
  if (!raw || typeof raw !== "object") return false;
  const e = raw as Record<string, unknown>;
  if (typeof e.id !== "string" || e.id.length === 0) return false;
  if (typeof e.name !== "string" || e.name.length === 0) return false;
  if (
    e.scrape_policy !== "active" &&
    e.scrape_policy !== "unknown" &&
    e.scrape_policy !== "verified_absent"
  ) return false;
  // discovery_seed_url (new) or cds_url_hint (legacy) — either is OK.
  // Both must be string when present.
  for (const key of ["discovery_seed_url", "cds_url_hint", "browse_url"] as const) {
    const v = e[key];
    if (v !== undefined && v !== null && typeof v !== "string") return false;
  }
  // IPEDS UNITID: NCES-issued numeric identifier. Must be a digit string
  // when present. YAML parses unquoted 166027 as a number, which would
  // silently become numeric in downstream consumers (and could bypass
  // escaping in tools/scorecard/backfill_ipeds_ids.py). Reject non-string
  // or non-digit values so the trust boundary is enforced at the
  // schools.yaml parser, not at every call site.
  if (e.ipeds_id !== undefined && e.ipeds_id !== null) {
    if (typeof e.ipeds_id !== "string") return false;
    if (!/^\d{3,8}$/.test(e.ipeds_id)) return false;
  }
  return true;
}

export interface FetchSchoolsYamlResult {
  entries: SchoolEntry[];
  skipped_invalid: number;
  // Map from school_id → override. Populated from school_overrides.yaml.
  // Empty when the file is missing or empty. Callers that don't care
  // about overrides can ignore this field.
  overrides: Map<string, SchoolOverride>;
  skipped_invalid_overrides: number;
}

// Fetch school_overrides.yaml from GitHub raw. Best-effort: any failure
// (HTTP error, parse error, etc.) is logged and treated as "no
// overrides," so a missing/broken overrides file doesn't break the
// archive pipeline. The schools.yaml fetch is the load-bearing one.
async function fetchSchoolOverrides(): Promise<{
  overrides: Map<string, SchoolOverride>;
  skipped_invalid: number;
}> {
  const empty = { overrides: new Map<string, SchoolOverride>(), skipped_invalid: 0 };
  let resp: Response;
  try {
    resp = await fetch(SCHOOL_OVERRIDES_YAML_URL, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(SCHOOLS_YAML_FETCH_TIMEOUT_MS),
    });
  } catch (e) {
    console.log(JSON.stringify({
      ts: new Date().toISOString(),
      fn: "schools.ts",
      event: "school_overrides_fetch_failed",
      error: (e as Error).message,
    }));
    return empty;
  }
  if (!resp.ok) {
    // 404 is a normal state if the file hasn't been added yet.
    if (resp.status === 404) return empty;
    console.log(JSON.stringify({
      ts: new Date().toISOString(),
      fn: "schools.ts",
      event: "school_overrides_fetch_failed",
      status: resp.status,
    }));
    return empty;
  }
  let parsed: unknown;
  try {
    parsed = parseYaml(await resp.text());
  } catch (e) {
    console.log(JSON.stringify({
      ts: new Date().toISOString(),
      fn: "schools.ts",
      event: "school_overrides_parse_failed",
      error: (e as Error).message,
    }));
    return empty;
  }
  let rawOverrides: unknown[] = [];
  if (
    parsed && typeof parsed === "object" &&
    Array.isArray((parsed as { overrides?: unknown }).overrides)
  ) {
    rawOverrides = (parsed as { overrides: unknown[] }).overrides;
  }
  const out = new Map<string, SchoolOverride>();
  let skipped_invalid = 0;
  for (const raw of rawOverrides) {
    if (isValidSchoolOverride(raw)) {
      out.set(raw.school_id, raw);
    } else {
      skipped_invalid += 1;
    }
  }
  return { overrides: out, skipped_invalid };
}

export async function fetchSchoolsYaml(): Promise<FetchSchoolsYamlResult> {
  let resp: Response;
  try {
    resp = await fetch(SCHOOLS_YAML_URL, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(SCHOOLS_YAML_FETCH_TIMEOUT_MS),
    });
  } catch (e) {
    throw new Error(
      `schools.yaml fetch failed: ${(e as Error).message} (${SCHOOLS_YAML_URL})`,
    );
  }
  if (!resp.ok) {
    throw new Error(
      `schools.yaml fetch failed: HTTP ${resp.status} from ${SCHOOLS_YAML_URL}`,
    );
  }
  const text = await resp.text();
  const parsed = parseYaml(text);

  // schools.yaml's top-level shape is { schools: [...] }, not a bare
  // array. Accept both forms defensively so a future refactor that
  // flattens the top-level doesn't silently break this loader.
  let rawEntries: unknown[];
  if (Array.isArray(parsed)) {
    rawEntries = parsed;
  } else if (
    parsed &&
    typeof parsed === "object" &&
    Array.isArray((parsed as { schools?: unknown }).schools)
  ) {
    rawEntries = (parsed as { schools: unknown[] }).schools;
  } else {
    throw new Error(
      `schools.yaml parse failed: expected array at top level or object with 'schools' array, got ${typeof parsed}`,
    );
  }

  const entries: SchoolEntry[] = [];
  let skipped_invalid = 0;
  for (const raw of rawEntries) {
    if (isValidSchoolEntry(raw)) {
      entries.push(raw);
    } else {
      skipped_invalid += 1;
    }
  }

  // Fetch overrides in parallel with… well, actually we already
  // awaited the schools fetch. Sequential is fine — overrides is
  // tiny (4 rows today, probably never more than 50) and the round
  // trip dominates parsing cost.
  const { overrides, skipped_invalid: skipped_invalid_overrides } =
    await fetchSchoolOverrides();

  // Apply overrides on top of entries. Only browse_url is overlaid
  // back onto SchoolEntry today because that's what filterArchivable
  // and the kids tool consume; direct_archive_urls and hosting_override
  // are exposed via the returned map for callers that want them
  // (kids worklist queries hosting_override; archiveManualUrls feeds
  // on direct_archive_urls in a future PR).
  for (const e of entries) {
    const o = overrides.get(e.id);
    if (!o) continue;
    if (o.browse_url && !e.browse_url) {
      e.browse_url = o.browse_url;
    }
  }

  return {
    entries,
    skipped_invalid,
    overrides,
    skipped_invalid_overrides,
  };
}

// Error raised by resolveSchoolName when the caller passes a school_id
// that is not in schools.yaml and does not supply an explicit school_name.
// Callers (archive-process, archive-upload) turn this into a 400 response
// so the upstream tool can retry with either the canonical id or an
// explicit school_name.
//
// Backstory: before this guard, `schoolName = entry?.name ?? schoolId`
// was allowed to fall through to the raw slug, which stuffed ids like
// `university-of-florida` into cds_documents.school_name and created
// silent duplicates alongside the canonical `uf` entry (see
// docs/dedup-plan-20260420.md for the cleanup). This class is the
// fail-closed replacement.
export class UnknownSchoolError extends Error {
  code = "unknown_school";
  suggestion?: string;
  constructor(message: string, suggestion?: string) {
    super(message);
    this.name = "UnknownSchoolError";
    this.suggestion = suggestion;
  }
}

// Normalize a slug or display name to a comparable token string. Drops
// structural noise words ("university", "college", "institute", "of",
// "at", "the") and everything non-alphanumeric, so we can match
// `university-of-florida` against the `uf` entry's `University of Florida`
// name and surface `uf` as the suggestion.
export function normalizeSchoolToken(s: string): string {
  return s
    .toLowerCase()
    .replace(/[-_]/g, " ")
    .replace(/\bthe\b/g, "")
    .replace(/\buniversity\b/g, "")
    .replace(/\bcollege\b/g, "")
    .replace(/\binstitute\b/g, "")
    .replace(/\bof\b/g, "")
    .replace(/\bat\b/g, "")
    .replace(/[^a-z0-9]/g, "")
    .trim();
}

// Given an unknown school_id and the list of valid entries, return the
// canonical entry that best matches — or null if no normalized-token
// match is found. Matches either the entry's id or its name.
export function suggestCanonicalSchool(
  inputId: string,
  entries: SchoolEntry[],
): { id: string; name: string } | null {
  const needle = normalizeSchoolToken(inputId);
  if (!needle) return null;
  for (const e of entries) {
    if (normalizeSchoolToken(e.id) === needle) return { id: e.id, name: e.name };
    if (normalizeSchoolToken(e.name) === needle) return { id: e.id, name: e.name };
  }
  return null;
}

// Resolve the display name for a school_id. Either returns the explicit
// name the caller supplied, the canonical name from schools.yaml, or
// throws UnknownSchoolError with a suggestion. Never silently stuffs the
// slug into the display column.
export async function resolveSchoolName(
  schoolId: string,
  explicitName: string | null | undefined,
): Promise<string> {
  const trimmed = typeof explicitName === "string" ? explicitName.trim() : "";
  if (trimmed) return trimmed;

  let result: FetchSchoolsYamlResult;
  try {
    result = await fetchSchoolsYaml();
  } catch (e) {
    throw new UnknownSchoolError(
      `cannot resolve school_name for '${schoolId}': schools.yaml unreachable (${(e as Error).message}) and no explicit school_name supplied. Pass school_name in the request body to bypass the lookup.`,
    );
  }

  const entry = result.entries.find((e) => e.id === schoolId);
  if (entry) return entry.name;

  const suggestion = suggestCanonicalSchool(schoolId, result.entries);
  const hint = suggestion
    ? ` Did you mean school_id='${suggestion.id}' (${suggestion.name})?`
    : "";
  throw new UnknownSchoolError(
    `school_id '${schoolId}' is not in schools.yaml and no explicit school_name was supplied.${hint} Either pass school_name in the request body, or use the canonical school_id.`,
    suggestion?.id,
  );
}

// Resolve the IPEDS Unit ID for a school_id from schools.yaml, or null
// if the school isn't listed or carries no UNITID. Used by the archive
// path so newly inserted cds_documents rows carry ipeds_id automatically
// and the cds_scorecard join works without a separate backfill.
// Errors fetching schools.yaml are swallowed to null — the archive must
// succeed even if the crosswalk is temporarily unavailable.
//
// The resolution is memoized within a single edge-function invocation
// (module-scope cache). archive-process calls this alongside the related
// resolveSchoolName, which ALSO calls fetchSchoolsYaml, so without a
// cache every archive makes two identical GitHub raw fetches. At scale,
// the queue-claim loop multiplies that by N schools per batch. Cache
// lifetime is the isolate lifetime, which matches Supabase's per-request
// isolation guarantees.
let _schoolsYamlCache: Promise<FetchSchoolsYamlResult> | null = null;

export async function resolveSchoolIpedsId(
  schoolId: string,
): Promise<string | null> {
  try {
    if (_schoolsYamlCache === null) {
      _schoolsYamlCache = fetchSchoolsYaml();
    }
    const result = await _schoolsYamlCache;
    const entry = result.entries.find((e) => e.id === schoolId);
    return entry?.ipeds_id ?? null;
  } catch {
    // Reset cache on error so a transient failure doesn't poison the
    // whole isolate's future resolutions.
    _schoolsYamlCache = null;
    return null;
  }
}

// V1 filter: every school that can actually be archived by the current
// pipeline. Sub-institution schools (Columbia et al.) are deferred to a
// follow-up per the approved plan. discovery_seed_url is trimmed before
// the emptiness check to reject whitespace-only values that would
// otherwise pass a truthiness test and waste retry budget at download
// time. The legacy cds_url_hint field is honored as a fallback so the
// PR 5 YAML rename can land before the runtime is recut.
export function filterArchivable(schools: SchoolEntry[]): ArchivableSchool[] {
  const out: ArchivableSchool[] = [];
  for (const s of schools) {
    if (s.scrape_policy !== "active") continue;
    const seed = (s.discovery_seed_url ?? s.cds_url_hint)?.trim();
    if (!seed) continue;
    if (s.sub_institutions && s.sub_institutions.length > 0) continue;
    const browse = s.browse_url?.trim();
    out.push({
      id: s.id,
      name: s.name,
      ...(s.ipeds_id ? { ipeds_id: s.ipeds_id } : {}),
      discovery_seed_url: seed,
      ...(browse ? { browse_url: browse } : {}),
    });
  }
  return out;
}
