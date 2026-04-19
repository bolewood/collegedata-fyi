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
  discovery_seed_url: string;
  browse_url?: string;
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
  return true;
}

export interface FetchSchoolsYamlResult {
  entries: SchoolEntry[];
  skipped_invalid: number;
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
  return { entries, skipped_invalid };
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
      discovery_seed_url: seed,
      ...(browse ? { browse_url: browse } : {}),
    });
  }
  return out;
}
