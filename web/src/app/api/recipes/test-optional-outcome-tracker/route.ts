import { NextResponse } from "next/server";
import {
  fetchTestOptionalOutcomeTracker,
  testOptionalOutcomeTrackerCsv,
} from "@/lib/test-optional-outcome-tracker";

export const revalidate = 3600;

export async function GET(request: Request) {
  const url = new URL(request.url);
  const data = await fetchTestOptionalOutcomeTracker();

  if (url.searchParams.get("format") === "csv") {
    return new Response(testOptionalOutcomeTrackerCsv(data), {
      headers: {
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="test-optional-outcome-tracker.csv"',
      },
    });
  }

  return NextResponse.json(data, {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
