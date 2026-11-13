import { NextResponse } from "next/server";
import { normalizeIpedsId } from "@/lib/ipeds-id";
import { findSchoolsByIpedsId, searchSchools } from "@/lib/public-data";

export const revalidate = 300;

const CACHE_HEADERS = {
  "Cache-Control": "public, s-maxage=300, stale-while-revalidate=3600",
};

export async function GET(request: Request) {
  const url = new URL(request.url);
  const q = url.searchParams.get("q") ?? "";
  const rawIpedsId = url.searchParams.get("ipeds_id");
  const limit = Number(url.searchParams.get("limit") ?? "10");

  // Exact lookup by federal IPEDS unit id, for callers who already hold one.
  if (rawIpedsId != null) {
    const ipedsId = normalizeIpedsId(rawIpedsId);
    if (!ipedsId) {
      return NextResponse.json(
        { error: "invalid_ipeds_id", message: "ipeds_id must be a six-digit IPEDS unit id." },
        { status: 400 },
      );
    }
    return NextResponse.json(await findSchoolsByIpedsId(ipedsId), { headers: CACHE_HEADERS });
  }

  if (!q.trim()) {
    return NextResponse.json(
      {
        error: "missing_query",
        message: "Pass a search string with ?q=, or a six-digit IPEDS unit id with ?ipeds_id=.",
      },
      { status: 400 },
    );
  }

  const payload = await searchSchools(q, Number.isFinite(limit) ? limit : 10);
  return NextResponse.json(payload, { headers: CACHE_HEADERS });
}
