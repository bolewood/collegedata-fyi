import { NextResponse } from "next/server";
import { getSchoolSources } from "@/lib/public-data";

export const revalidate = 3600;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ school_id: string }> },
) {
  const { school_id } = await params;
  const payload = await getSchoolSources(school_id);
  if (!payload) {
    return NextResponse.json(
      {
        error: "school_not_found",
        school_id,
        message: "No public source ledger is available for this school_id.",
      },
      { status: 404 },
    );
  }

  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}

