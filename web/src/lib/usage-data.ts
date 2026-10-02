import { cache } from "react";
import { supabase } from "./supabase";
import type { UsageDailyRow, UsageMonthRow, UsageSchoolMonthRow } from "./usage";

type UntypedSupabase = {
  // Generated DB types lag the PRD 033 migration; rows are typed at the return.
  from: (table: string) => any;
};

const PAGE = 1000;
const HARD_CAP = 200_000;

function isStaticBuild(): boolean {
  return (
    process.env.NEXT_PHASE === "phase-production-build" ||
    process.env.npm_lifecycle_event === "build"
  );
}

async function fetchAll<T>(table: string, select: string, order: string[]): Promise<T[]> {
  const raw = supabase as unknown as UntypedSupabase;
  const out: T[] = [];
  // Page until an empty page, so a lower server max_rows can't truncate silently.
  for (let start = 0; start < HARD_CAP; ) {
    let query = raw.from(table).select(select);
    for (const column of order) query = query.order(column);
    const { data, error } = await query.range(start, start + PAGE - 1);
    if (error) throw new Error(`Failed to fetch ${table}: ${error.message}`);
    const page = (data as T[]) ?? [];
    if (!page.length) return out;
    out.push(...page);
    start += page.length;
  }
  throw new Error(`${table} exceeded ${HARD_CAP} rows`);
}

export type UsageRows = {
  daily: UsageDailyRow[];
  schoolMonths: UsageSchoolMonthRow[];
  months: UsageMonthRow[];
};

/**
 * All published usage rows. At runtime a failed read throws, so ISR keeps
 * serving the last good page; during a build it renders the empty state.
 */
export const fetchUsageRows = cache(async function fetchUsageRows(): Promise<UsageRows> {
  try {
    const [daily, schoolMonths, months] = await Promise.all([
      fetchAll<UsageDailyRow>(
        "usage_public_daily",
        "day,metric,access_method,client_kind,value,method_version",
        ["day", "metric", "access_method", "client_kind"],
      ),
      fetchAll<UsageSchoolMonthRow>(
        "usage_public_school_months",
        "month,school_id,school_name,unique_downloads,method_version",
        ["month", "school_id"],
      ),
      fetchAll<UsageMonthRow>(
        "usage_public_months",
        "month,schools_with_downloads,schools_under_floor,method_version",
        ["month"],
      ),
    ]);
    return {
      daily: daily.map((r) => ({ ...r, value: Number(r.value) })),
      schoolMonths: schoolMonths.map((r) => ({ ...r, unique_downloads: Number(r.unique_downloads) })),
      months,
    };
  } catch (error) {
    if (isStaticBuild()) {
      console.warn(`usage: ${error instanceof Error ? error.message : String(error)}`);
      return { daily: [], schoolMonths: [], months: [] };
    }
    throw error;
  }
});
