import { NextResponse } from "next/server";
import { isSentryVerifyAllowed } from "@/lib/sentry";

export const dynamic = "force-dynamic";

/**
 * Gated Sentry wiring check. Returns 404 in Vercel production so it cannot
 * be used to generate noise on the live site. Local and preview still throw
 * a distinctive error through the real server SDK init path.
 */
export async function GET() {
  if (!isSentryVerifyAllowed()) {
    return new NextResponse(null, { status: 404 });
  }

  throw new Error(
    `collegedata-sentry-verify: intentional server error at ${new Date().toISOString()}`,
  );
}
