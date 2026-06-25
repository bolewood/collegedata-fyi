import type { NextFetchEvent, NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { buildApiUsageEvent, recordApiUsageEvent } from "@/lib/api-usage";

export function proxy(request: NextRequest, event: NextFetchEvent) {
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
  ],
};
