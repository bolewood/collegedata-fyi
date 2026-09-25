import type { NextFetchEvent, NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { buildApiUsageEvent, recordApiUsageEvent } from "@/lib/api-usage";
import { isAcceptanceRateGone } from "@/lib/acceptance-pilot";
import { isEarlyDecisionGone } from "@/lib/early-decision-pilot";

export function proxy(request: NextRequest, event: NextFetchEvent) {
  const { pathname } = request.nextUrl;
  if (pathname.endsWith("/acceptance-rate")) {
    // PRD 031: a submitted stat URL retired after a human decision answers
    // 410, never a silent 404. Everything else renders normally.
    return isAcceptanceRateGone(pathname)
      ? new NextResponse(null, { status: 410 })
      : NextResponse.next();
  }
  if (pathname.endsWith("/early-decision")) {
    return isEarlyDecisionGone(pathname)
      ? new NextResponse(null, { status: 410 })
      : NextResponse.next();
  }
  event.waitUntil(recordApiUsageEvent(buildApiUsageEvent(request)));
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/api/compare",
    "/api/fields",
    "/api/facts/:path*",
    "/api/schools/:path*",
    "/api/snapshots",
    "/schools/:school_id/acceptance-rate",
    "/schools/:school_id/early-decision",
  ],
};
