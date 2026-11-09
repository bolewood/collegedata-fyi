import { NextResponse } from "next/server";
import { fetchCanonicalSchoolId } from "@/lib/queries";
import {
  applyRevalidation,
  isAuthorized,
  parseRevalidateBody,
} from "@/lib/revalidate-schools";

// Never cached: this is a write-style endpoint.
export const dynamic = "force-dynamic";

const NO_STORE = { "Cache-Control": "no-store" };

/**
 * POST /api/revalidate — expire cached school pages after data changes.
 *
 *   Authorization: Bearer $REVALIDATE_SECRET
 *   {"school_ids": ["yale", "mit"]}   or   {"all": true}
 *
 * 503 when REVALIDATE_SECRET is unset, 401 on a bad/missing bearer token.
 */
export async function POST(request: Request) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return NextResponse.json(
      { error: "revalidation_disabled" },
      { status: 503, headers: NO_STORE },
    );
  }
  if (!isAuthorized(request.headers.get("authorization"), secret)) {
    return NextResponse.json(
      { error: "unauthorized" },
      { status: 401, headers: NO_STORE },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_json" },
      { status: 400, headers: NO_STORE },
    );
  }

  const parsed = parseRevalidateBody(body);
  if (!parsed.ok) {
    return NextResponse.json(
      { error: "invalid_request", message: parsed.error },
      { status: 400, headers: NO_STORE },
    );
  }

  const counts = await applyRevalidation(parsed.request, fetchCanonicalSchoolId);
  return NextResponse.json(
    {
      revalidated: true,
      ...counts,
      rejected: parsed.request.kind === "schools" ? parsed.request.rejected : [],
    },
    { headers: NO_STORE },
  );
}
