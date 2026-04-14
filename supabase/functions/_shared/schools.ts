// schools.yaml loader for edge functions. Fetches the committed file from
// GitHub raw at runtime so new schools land without a function redeploy.
// See the plan for rejected alternatives (embed-at-deploy, push-to-storage-
// on-commit).

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
export interface SchoolEntry {
  id: string;
  name: string;
  domain?: string;
  ipeds_id?: string;
  scrape_policy: "active" | "unknown" | "verified_absent";
  cds_url_hint?: string | null;
  sub_institutions?: SubInstitution[];
  notes?: string;
}

export interface ArchivableSchool {
  id: string;
  name: string;
  cds_url_hint: string;
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
  if (
    e.cds_url_hint !== undefined &&
    e.cds_url_hint !== null &&
    typeof e.cds_url_hint !== "string"
  ) return false;
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
// follow-up per the approved plan. cds_url_hint is trimmed before the
// emptiness check to reject whitespace-only values that would otherwise
// pass a truthiness test and waste retry budget at download time.
export function filterArchivable(schools: SchoolEntry[]): ArchivableSchool[] {
  const out: ArchivableSchool[] = [];
  for (const s of schools) {
    if (s.scrape_policy !== "active") continue;
    const hint = s.cds_url_hint?.trim();
    if (!hint) continue;
    if (s.sub_institutions && s.sub_institutions.length > 0) continue;
    out.push({
      id: s.id,
      name: s.name,
      cds_url_hint: hint,
    });
  }
  return out;
}
