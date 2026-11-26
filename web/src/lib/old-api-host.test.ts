import { describe, expect, it, vi } from "vitest";
import type { NextFetchEvent } from "next/server";
import { NextRequest } from "next/server";
import { matchHas } from "next/dist/shared/lib/router/utils/prepare-destination";
import { getMiddlewareRouteMatcher } from "next/dist/shared/lib/router/utils/middleware-route-matcher";
// @ts-expect-error Next ships its compiled path-to-regexp without types.
import { pathToRegexp } from "next/dist/compiled/path-to-regexp";

const { recordApiUsageEvent } = vi.hoisted(() => ({ recordApiUsageEvent: vi.fn(async () => undefined) }));
vi.mock("@/lib/api-usage", () => ({
  buildApiUsageEvent: vi.fn(() => ({})),
  recordApiUsageEvent,
}));

import { oldApiHostAction, OLD_API_HOSTS, SUPABASE_ORIGIN } from "./old-api-host";
import { config, proxy } from "../proxy";
import { nextConfig } from "../../next.config";

// Next's matchers only read headers.host; the full request type is not needed.
const fakeReq = (host: string) => ({ headers: { host } }) as never;
const ORIGIN = SUPABASE_ORIGIN;
const STORAGE = "/storage/v1/object/public/sources/yale/2024-25.pdf";

describe("oldApiHostAction", () => {
  it("redirects GET and HEAD of public storage objects, query kept, with CORS and a short cache", () => {
    for (const method of ["GET", "HEAD", "get"]) {
      expect(oldApiHostAction("api.collegedata.fyi", method, STORAGE, "?download=1")).toEqual({
        kind: "redirect",
        location: `https://api.quadfile.org${STORAGE}?download=1`,
        headers: { "Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=3600" },
      });
    }
  });

  it("sends the test host's storage redirect to the Supabase origin", () => {
    expect(oldApiHostAction("api-test.quadfile.org", "GET", STORAGE, "")).toMatchObject({
      kind: "redirect",
      location: `${ORIGIN}${STORAGE}`,
    });
  });

  it("compares the host case-insensitively and ignores the port", () => {
    expect(oldApiHostAction("API.CollegeData.FYI:443", "GET", STORAGE, "")).toMatchObject({ kind: "redirect" });
    expect(oldApiHostAction("Api-Test.Quadfile.org:3000", "GET", "/rest/v1/schools", "")).toMatchObject({ kind: "proxy" });
  });

  it("proxies everything else to Supabase with path and query intact", () => {
    expect(oldApiHostAction("api.collegedata.fyi", "GET", "/rest/v1/schools", "?select=*&limit=1")).toEqual({
      kind: "proxy",
      url: `${ORIGIN}/rest/v1/schools?select=*&limit=1`,
    });
    for (const [method, path] of [
      ["OPTIONS", "/rest/v1/schools"],
      ["OPTIONS", STORAGE],
      ["POST", STORAGE],
      ["POST", "/storage/v1/object/list/sources"],
      ["GET", "/storage/v1/object/sign/sources/a.pdf"],
      ["GET", "/storage/v1/object/public"],
      ["GET", "/storage/v1/object/authenticated/sources/a.pdf"],
      ["POST", "/functions/v1/browser-search"],
      ["GET", "/auth/v1/health"],
      ["GET", "/nothing-here"],
      ["GET", "/"],
    ]) {
      expect(oldApiHostAction("api.collegedata.fyi", method, path, ""), `${method} ${path}`).toEqual({
        kind: "proxy",
        url: `${ORIGIN}${path}`,
      });
    }
  });

  it("returns null for every other host", () => {
    for (const host of ["www.collegedata.fyi", "collegedata.fyi", "localhost:3000", "x.vercel.app", "api.quadfile.org", "evil-api.collegedata.fyi", "", null, undefined]) {
      expect(oldApiHostAction(host, "GET", STORAGE, ""), String(host)).toBeNull();
    }
  });
});

const event = { waitUntil: vi.fn() } as unknown as NextFetchEvent;
const run = (url: string, init?: ConstructorParameters<typeof NextRequest>[1]) => proxy(new NextRequest(url, init), event);

describe("proxy on the old API hosts", () => {
  it("answers a storage GET with a 308 and CORS, before usage recording", () => {
    recordApiUsageEvent.mockClear();
    const res = run(`https://api-test.quadfile.org${STORAGE}?x=1`, { headers: { host: "api-test.quadfile.org" } });
    expect(res.status).toBe(308);
    expect(res.headers.get("location")).toBe(`${ORIGIN}${STORAGE}?x=1`);
    expect(res.headers.get("access-control-allow-origin")).toBe("*");
    expect(res.headers.get("cache-control")).toBe("public, max-age=3600");
    expect(recordApiUsageEvent).not.toHaveBeenCalled();
  });

  it("rewrites other requests to Supabase, adds x-quadfile-proxied, keeps the caller's headers, and does not record usage", () => {
    recordApiUsageEvent.mockClear();
    const res = run("https://api.collegedata.fyi/rest/v1/schools?limit=1", {
      method: "POST",
      headers: { host: "api.collegedata.fyi", apikey: "k", prefer: "count=exact" },
      body: "{}",
    });
    expect(res.headers.get("x-middleware-rewrite")).toBe(`${ORIGIN}/rest/v1/schools?limit=1`);
    expect(res.headers.get("x-middleware-override-headers")).toContain("x-quadfile-proxied");
    expect(res.headers.get("x-middleware-request-x-quadfile-proxied")).toBe("1");
    expect(res.headers.get("x-middleware-request-apikey")).toBe("k");
    expect(res.headers.get("x-middleware-request-prefer")).toBe("count=exact");
    expect(recordApiUsageEvent).not.toHaveBeenCalled();
  });

  it("does not run the school-page logic for these hosts", () => {
    const res = run("https://api.collegedata.fyi/schools/yal%D0%B5", { headers: { host: "api.collegedata.fyi" } });
    expect(res.status).toBe(200);
    expect(res.headers.get("x-middleware-rewrite")).toBe(`${ORIGIN}/schools/yal%D0%B5`);
  });

  it("leaves www.collegedata.fyi exactly as it was: /rest/v1/x is not handled by the proxy", () => {
    recordApiUsageEvent.mockClear();
    const res = run("https://www.collegedata.fyi/rest/v1/x", { headers: { host: "www.collegedata.fyi" } });
    // Today this path is not in the matcher, so the proxy never runs for it
    // (the app answers its own 404). If it did run, it would only fall
    // through to the usage recorder, never rewrite or redirect.
    expect(res.headers.get("x-middleware-rewrite")).toBeNull();
    expect(res.headers.get("location")).toBeNull();
    const www = getMiddlewareRouteMatcher(matchersFor(config.matcher));
    const req = fakeReq("www.collegedata.fyi");
    for (const path of ["/rest/v1/x", "/functions/v1/x", "/storage/v1/object/public/a", "/auth/v1/x"]) {
      expect(www(path, req, {}), path).toBe(false);
    }
  });

  it("keeps the existing matched paths on the site hosts", () => {
    const www = getMiddlewareRouteMatcher(matchersFor(config.matcher));
    const req = fakeReq("www.collegedata.fyi");
    for (const path of ["/api/compare", "/api/schools/yale/facts", "/schools/yale", "/schools"]) {
      expect(www(path, req, {}), path).toBe(true);
    }
  });

  it("matches every path on the old hosts and nothing extra on look-alike hosts", () => {
    const match = getMiddlewareRouteMatcher(matchersFor(config.matcher));
    for (const host of [...OLD_API_HOSTS, "API.collegedata.fyi:443"]) {
      for (const path of ["/rest/v1/schools", "/storage/v1/object/public/a.pdf", "/functions/v1/browser-search", "/auth/v1/x", "/", "/anything"]) {
        expect(match(path, fakeReq(host), {}), `${host}${path}`).toBe(true);
      }
    }
    // An unparenthesised alternation would be anchored as ^a|b$ and match these.
    for (const host of ["api.collegedata.fyi.evil.com", "xapi-test.quadfile.org", "evilapi.collegedata.fyi", "api.collegedata.fyi.attacker.org"]) {
      expect(match("/rest/v1/schools", fakeReq(host), {}), host).toBe(false);
    }
  });
});

type Matcher = string | { source: string; has?: unknown[]; missing?: unknown[] };

/** The compiled form Next hands to getMiddlewareRouteMatcher: a regexp per source. */
function matchersFor(matcher: Matcher[]) {
  return matcher.map((m) => {
    const entry = typeof m === "string" ? { source: m } : m;
    const re = pathToRegexp(entry.source) as unknown as RegExp | { regexp: RegExp };
    return { regexp: (re instanceof RegExp ? re : re.regexp).source, has: entry.has, missing: entry.missing } as never;
  });
}

describe("next.config redirects never match the old API hosts", () => {
  // The current rules plus the planned rename rule, written exactly as planned.
  const FUTURE_HOST_RULE = { type: "host", value: "(www\\.)?collegedata\\.fyi" } as const;

  it("matchHas anchors host values (^...$), lower-cases and strips the port", () => {
    const req = fakeReq;
    expect(matchHas(req("api.collegedata.fyi"), {}, [FUTURE_HOST_RULE] as never)).toBe(false);
    expect(matchHas(req("www.collegedata.fyi"), {}, [FUTURE_HOST_RULE] as never)).not.toBe(false);
    expect(matchHas(req("COLLEGEDATA.fyi:443"), {}, [FUTURE_HOST_RULE] as never)).not.toBe(false);
    // Substring would match; an anchored regex does not.
    expect(matchHas(req("notcollegedata.fyi"), {}, [FUTURE_HOST_RULE] as never)).toBe(false);
  });

  it("no redirect in next.config.ts, today's or the planned host rule, applies to api.collegedata.fyi or api-test.quadfile.org", async () => {
    const redirects = await nextConfig.redirects!();
    expect(redirects.length).toBeGreaterThan(0);
    const paths = ["/", "/rest/v1/schools", "/functions/v1/browser-search", "/auth/v1/token", STORAGE];
    const planned = [{ source: "/:path*", has: [FUTURE_HOST_RULE] }, { source: "/", has: [FUTURE_HOST_RULE] }];
    for (const host of OLD_API_HOSTS) {
      const req = fakeReq(host);
      for (const rule of [...(redirects as Redirect[]), ...planned] as Redirect[]) {
        if (rule.has && matchHas(req, {}, rule.has as never) === false) continue;
        const re = pathToRegexp(rule.source) as unknown as RegExp | { regexp: RegExp };
        const regexp = re instanceof RegExp ? re : re.regexp;
        for (const path of paths) {
          expect(regexp.test(path), `${host} ${path} vs ${rule.source}`).toBe(false);
        }
      }
    }
  });
});

type Redirect = { source: string; has?: unknown[] };
