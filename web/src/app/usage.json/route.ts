import { NextResponse } from "next/server";
import { fetchUsageRows } from "@/lib/usage-data";
import { isUsageLaunched, toUsageJson } from "@/lib/usage";

export const revalidate = 3600;

export async function GET() {
  const rows = await fetchUsageRows();
  return NextResponse.json(toUsageJson(rows.daily, rows.schoolMonths, rows.months), {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      ...(isUsageLaunched() ? {} : { "X-Robots-Tag": "noindex" }),
    },
  });
}
