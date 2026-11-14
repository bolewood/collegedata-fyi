/**
 * PRD 036 M3: cached reads of the `scholarship_directory` view.
 *
 * The view may not exist yet, or may be empty, when this deploys. Every public
 * function here returns an empty result on a missing relation, a PostgREST
 * error, or a thrown fetch error, so pages render and the build does not fail.
 *
 * Caching: the loader throws on error and the empty fallback is applied
 * OUTSIDE unstable_cache, so a failed read is never cached for a day. Nothing
 * revalidates after `load.py --apply`, so new rows appear when the daily
 * window expires or when /api/revalidate expires the school's tag.
 */
import { unstable_cache } from "next/cache";
import { supabase } from "./supabase";
import {
  SCHOLARSHIP_INDEX_TAG,
  SCHOOL_DATA_REVALIDATE_SECONDS,
  SCHOOL_DATA_TAG,
  schoolCacheTag,
} from "./school-cache-tags";
import {
  SCHOLARSHIP_SELECT,
  humanizeId,
  normalizeScholarshipRow,
  toIndexRow,
  type IndexRow,
  type ScholarshipDirectoryRow,
  type SchoolControl,
} from "./scholarships";

export { SCHOLARSHIP_INDEX_TAG };

type UntypedSupabase = { from: (table: string) => any };

/** Development only: serve the checked-in fixture instead of the view. */
function fixtureEnabled(): boolean {
  return process.env.NODE_ENV === "development" && Boolean(process.env.SCHOLARSHIP_FIXTURE);
}

async function readFixture(): Promise<ScholarshipDirectoryRow[]> {
  // fs, not import: the 170 KB fixture must never reach a production bundle.
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  const file = path.join(process.cwd(), "src/lib/__fixtures__/scholarship-directory.json");
  const raw = JSON.parse(await fs.readFile(file, "utf8")) as unknown[];
  return raw.map(normalizeScholarshipRow).filter((r): r is ScholarshipDirectoryRow => r !== null);
}

type Query = { eq?: [string, string] };

/** Throws on any error (missing relation included). Callers apply the empty fallback. */
export async function loadScholarshipRows(query: Query = {}): Promise<ScholarshipDirectoryRow[]> {
  if (fixtureEnabled()) {
    const rows = await readFixture();
    return query.eq ? rows.filter((r) => (r as unknown as Record<string, unknown>)[query.eq![0]] === query.eq![1]) : rows;
  }
  const client = supabase as unknown as UntypedSupabase;
  const out: ScholarshipDirectoryRow[] = [];
  const PAGE = 1000;
  for (let start = 0; start < 10_000; start += PAGE) {
    let q = client
      .from("scholarship_directory")
      .select(SCHOLARSHIP_SELECT)
      .order("school_id", { ascending: true })
      .order("program_id", { ascending: true })
      .range(start, start + PAGE - 1);
    if (query.eq) q = q.eq(query.eq[0], query.eq[1]);
    const { data, error } = await q;
    if (error) throw new Error(`scholarship_directory: ${error.message}`);
    const page = Array.isArray(data) ? data : [];
    for (const raw of page) {
      const row = normalizeScholarshipRow(raw);
      if (row) out.push(row);
    }
    if (page.length < PAGE) break;
  }
  return out;
}

/** Name, state and control for the schools that appear in the directory. Throws on error. */
export type SchoolInfo = { name: string; control: SchoolControl };

function controlFromNumber(v: unknown): SchoolControl {
  if (v === 1) return "public";
  if (v === 2) return "private_nonprofit";
  if (v === 3) return "private_for_profit";
  return "unknown";
}

export async function loadSchoolInfo(ids: string[]): Promise<Record<string, SchoolInfo>> {
  const out: Record<string, SchoolInfo> = {};
  const unique = Array.from(new Set(ids));
  for (const id of unique) out[id] = { name: humanizeId(id), control: "unknown" };
  if (unique.length === 0) return out;
  const client = supabase as unknown as UntypedSupabase;
  const { data, error } = await client
    .from("institution_directory")
    .select("school_id, school_name, control")
    .in("school_id", unique);
  if (error) throw new Error(`institution_directory: ${error.message}`);
  for (const row of (Array.isArray(data) ? data : []) as Array<{ school_id: string; school_name: string | null; control: unknown }>) {
    out[row.school_id] = {
      name: row.school_name || out[row.school_id]?.name || humanizeId(row.school_id),
      control: controlFromNumber(row.control),
    };
  }
  return out;
}

/** Run a loader; on any error warn once and return the fallback. */
export async function emptyOnError<T>(label: string, fallback: T, fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    console.warn(`${label}: ${error instanceof Error ? error.message : String(error)}`);
    return fallback;
  }
}

function cached<T>(key: string[], tags: string[], fn: () => Promise<T>): Promise<T> {
  if (fixtureEnabled()) return fn(); // never cache the dev fixture
  return unstable_cache(fn, key, {
    revalidate: SCHOOL_DATA_REVALIDATE_SECONDS,
    tags: [SCHOOL_DATA_TAG, ...tags],
  })();
}

type AllScholarships = {
  rows: ScholarshipDirectoryRow[];
  info: Record<string, SchoolInfo>;
};

const NONE: AllScholarships = { rows: [], info: {} };

/**
 * The whole directory in one cached read (the view is small). School pages and
 * the index both derive from it, so a crawler sweep of thousands of school
 * pages costs one query a day, not one per school. Throws on error.
 */
async function fetchAllScholarships(): Promise<AllScholarships> {
  return cached(["fetchAllScholarships"], [SCHOLARSHIP_INDEX_TAG], async () => {
    const rows = await loadScholarshipRows();
    if (rows.length === 0) return NONE;
    let info: Record<string, SchoolInfo> = {};
    try {
      info = await loadSchoolInfo(rows.flatMap((r) => [r.school_id, ...r.participating_school_ids]));
    } catch (error) {
      // Names and types are a nicety; never fail the directory for them.
      console.warn(`scholarship school names: ${error instanceof Error ? error.message : String(error)}`);
    }
    return { rows, info };
  });
}

export type SchoolScholarships = {
  programs: ScholarshipDirectoryRow[];
  /** School id to display name, for joint programs and related lines. */
  names: Record<string, string>;
};

const NO_PROGRAMS: SchoolScholarships = { programs: [], names: {} };

/** Programs for one school page, filtered from the one cached read. Empty on a missing view or any error. */
export async function fetchScholarshipsBySchoolId(schoolId: string): Promise<SchoolScholarships> {
  return emptyOnError("fetchScholarshipsBySchoolId", NO_PROGRAMS, () =>
    // Thin per-school entry so `school:<id>` still expires this school's pages.
    cached(["fetchScholarshipsBySchoolId", schoolId], [schoolCacheTag(schoolId)], async () => {
      const all = await fetchAllScholarships();
      const programs = all.rows.filter((r) => r.school_id === schoolId);
      if (programs.length === 0) return NO_PROGRAMS;
      const names: Record<string, string> = {};
      for (const id of programs.flatMap((p) => p.participating_school_ids)) {
        if (id !== schoolId) names[id] = all.info[id]?.name ?? humanizeId(id);
      }
      return { programs, names };
    }),
  );
}

export type ScholarshipIndex = {
  rows: IndexRow[];
  controls: Record<string, SchoolControl>;
  /** Lead school and program id per program, for counts by school type. */
  programs: { program_id: string; school_id: string; participating_school_ids: string[] }[];
};

const NO_INDEX: ScholarshipIndex = { rows: [], controls: {}, programs: [] };

/** Slim rows for /scholarships: only what the table and its filters read. Empty on a missing view or any error. */
export async function fetchScholarshipIndex(): Promise<ScholarshipIndex> {
  return emptyOnError("fetchScholarshipIndex", NO_INDEX, async () => {
    const all = await fetchAllScholarships();
    if (all.rows.length === 0) return NO_INDEX;
    const nameOf = (id: string) => all.info[id]?.name ?? humanizeId(id);
    const controls: Record<string, SchoolControl> = {};
    for (const [id, v] of Object.entries(all.info)) controls[id] = v.control;
    return {
      rows: all.rows.map((r) => toIndexRow(r, nameOf(r.school_id))),
      controls,
      programs: all.rows.map((r) => ({
        program_id: r.program_id,
        school_id: r.school_id,
        participating_school_ids: r.participating_school_ids,
      })),
    };
  });
}
