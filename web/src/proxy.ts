import type { NextFetchEvent, NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { buildApiUsageEvent, recordApiUsageEvent } from "@/lib/api-usage";
import { isAcceptanceRateGone } from "@/lib/acceptance-pilot";
import { isEarlyDecisionGone } from "@/lib/early-decision-pilot";
import { isGpaGone } from "@/lib/gpa-pilot";

const NON_PRINTABLE_ASCII = /[^\x21-\x7E]/;

/**
 * True when a /schools path has a character no school slug can have, such as
 * a look-alike Cyrillic letter. Next adds the request path to the
 * `x-next-cache-tags` response header by itself, and a non-ASCII value there
 * fails the whole response with a 500, so these are answered here, before
 * any rendering.
 */
export function isUnroutableSchoolPath(pathname: string): boolean {
  if (NON_PRINTABLE_ASCII.test(pathname)) return true;
  try {
    return NON_PRINTABLE_ASCII.test(decodeURIComponent(pathname));
  } catch {
    return true; // malformed percent-encoding
  }
}

export function proxy(request: NextRequest, event: NextFetchEvent) {
  const { pathname } = request.nextUrl;
  const schoolPage = pathname === "/schools" || pathname.startsWith("/schools/");
  if (schoolPage && isUnroutableSchoolPath(pathname)) {
    return new NextResponse("Not found", { status: 404 });
  }
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
  if (pathname.endsWith("/gpa")) {
    return isGpaGone(pathname)
      ? new NextResponse(null, { status: 410 })
      : NextResponse.next();
  }
  // School pages pass through here only for the checks above; API usage is
  // recorded for the API routes alone.
  if (schoolPage) return NextResponse.next();
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
    "/schools/:path*",
  ],
};
