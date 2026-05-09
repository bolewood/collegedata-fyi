import { NextResponse } from "next/server";
import { searchSchools } from "@/lib/public-data";

export const revalidate = 300;

export async function GET(request: Request) {
  const url = new URL(request.url);
  const q = url.searchParams.get("q") ?? "";
  const limit = Number(url.searchParams.get("limit") ?? "10");

  if (!q.trim()) {
    return NextResponse.json(
      { error: "missing_query", message: "Pass a search string with ?q=." },
      { status: 400 },
    );
  }

  const payload = await searchSchools(q, Number.isFinite(limit) ? limit : 10);
  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "public, s-maxage=300, stale-while-revalidate=3600",
    },
  });
}

