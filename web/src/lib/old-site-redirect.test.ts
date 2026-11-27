import { describe, expect, it } from "vitest";
import { matchHas, prepareDestination } from "next/dist/shared/lib/router/utils/prepare-destination";
import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match";
import retiredSchoolAliases from "../data/school-redirects.json";
import { nextConfig } from "../../next.config";
import { OLD_SITE_HOST_PATTERN } from "./old-site-redirect";
import { SITE_HOST, SITE_ORIGIN } from "./site";

type Rule = {
  source: string;
  destination: string;
  has?: { type: string; value?: string }[];
  missing?: { type: string; value?: string }[];
  statusCode?: number;
  permanent?: boolean;
};

const rules = async () => (await nextConfig.redirects!()) as unknown as Rule[];
const isOldSiteRule = (r: Rule) => !!r.has?.some((h) => h.type === "host" && h.value === OLD_SITE_HOST_PATTERN);

/**
 * First redirect that applies, evaluated with Next's own helpers the way its
 * router does: getPathMatch for the source, matchHas for `has`/`missing`,
 * prepareDestination for the destination (params and query).
 */
function firstRedirect(all: Rule[], host: string, pathname: string, search: string) {
  const req = { headers: { host } } as never;
  const query = Object.fromEntries(new URLSearchParams(search));
  for (const rule of all) {
    const match = getPathMatch(rule.source, { strict: true, removeUnnamedParams: true, sensitive: false });
    const params = match(pathname);
    if (!params) continue;
    if (rule.has || rule.missing) {
      const hasParams = matchHas(req, query, rule.has as never, rule.missing as never);
      if (!hasParams) continue;
      Object.assign(params, hasParams);
    }
    const { parsedDestination } = prepareDestination({
      appendParamsToQuery: false,
      destination: rule.destination,
      params,
      query,
    });
    const qs = new URLSearchParams(parsedDestination.query as Record<string, string>).toString();
    const to = `${parsedDestination.protocol ?? "https:"}//${parsedDestination.hostname ?? host}${parsedDestination.pathname}${qs ? `?${qs}` : ""}`;
    return { to, status: rule.statusCode ?? (rule.permanent ? 308 : 307) };
  }
  return null;
}

/** Follows redirects across hosts; throws if the chain does not end. */
function walk(all: Rule[], url: string) {
  const hops: { status: number; to: string }[] = [];
  let current = new URL(url);
  for (let i = 0; i < 10; i++) {
    const hit = firstRedirect(all, current.host, current.pathname, current.search);
    if (!hit) return { hops, final: current };
    const next = new URL(hit.to, current);
    hops.push({ status: hit.status, to: next.toString() });
    current = next;
  }
  throw new Error(`redirect loop for ${url}: ${JSON.stringify(hops)}`);
}

const OLD_HOSTS = ["www.collegedata.fyi", "collegedata.fyi"];

describe("old site host redirects", () => {
  it("puts the old-host rules first, and there are some", async () => {
    const all = await rules();
    const oldIdx = all.map((r, i) => (isOldSiteRule(r) ? i : -1)).filter((i) => i >= 0);
    expect(oldIdx.length).toBeGreaterThanOrEqual(3);
    expect(oldIdx).toEqual(oldIdx.map((_, i) => i));
  });

  it("sends /api/* on both old hosts to the new host with a 308, query kept", async () => {
    const all = await rules();
    for (const host of OLD_HOSTS) {
      expect(walk(all, `https://${host}/api/schools/yale/facts`).hops).toEqual([
        { status: 308, to: `${SITE_ORIGIN}/api/schools/yale/facts` },
      ]);
      expect(walk(all, `https://${host}/api/schools/yale/facts?year=2024-25`).hops).toEqual([
        { status: 308, to: `${SITE_ORIGIN}/api/schools/yale/facts?year=2024-25` },
      ]);
      expect(walk(all, `https://${host}/api`).hops).toEqual([{ status: 308, to: `${SITE_ORIGIN}/api` }]);
    }
  });

  it("sends every other path on both old hosts to the new host with a 301, as the only hop", async () => {
    const all = await rules();
    for (const host of OLD_HOSTS) {
      for (const path of ["/", "/schools/yale", "/schools/yale/2024-25", "/coverage", "/apix/x"]) {
        expect(walk(all, `https://${host}${path}`).hops, `${host}${path}`).toEqual([
          { status: 301, to: `${SITE_ORIGIN}${path}` },
        ]);
      }
      expect(walk(all, `https://${host}/coverage?state=CA`).hops).toEqual([
        { status: 301, to: `${SITE_ORIGIN}/coverage?state=CA` },
      ]);
    }
  });

  it("matches the host case-insensitively and ignores the port", async () => {
    const all = await rules();
    expect(firstRedirect(all, "WWW.COLLEGEDATA.FYI:443", "/schools/yale", "")).toEqual({
      to: `${SITE_ORIGIN}/schools/yale`,
      status: 301,
    });
    expect(firstRedirect(all, "COLLEGEDATA.fyi:443", "/api/x", "")?.status).toBe(308);
  });

  it("does not touch the new host or the old API host", async () => {
    const all = await rules();
    expect(firstRedirect(all, SITE_HOST, "/api/schools", "")).toBeNull();
    expect(firstRedirect(all, "api.collegedata.fyi", "/rest/v1/schools", "")).toBeNull();
    expect(firstRedirect(all, "api.collegedata.fyi", "/api/x", "")).toBeNull();
    expect(firstRedirect(all, "notcollegedata.fyi", "/schools/yale", "")).toBeNull();
  });

  it("reaches the final school page in at most 2 hops for every retired alias on an old host", async () => {
    const all = await rules();
    expect(retiredSchoolAliases.length).toBeGreaterThan(0);
    for (const { alias, school_id } of retiredSchoolAliases) {
      for (const host of OLD_HOSTS) {
        for (const suffix of ["", "/2024-25"]) {
          const { hops, final } = walk(all, `https://${host}/schools/${alias}${suffix}`);
          expect(hops.length, `${host} ${alias}${suffix}`).toBeLessThanOrEqual(2);
          expect(final.toString()).toBe(`${SITE_ORIGIN}/schools/${school_id}${suffix}`);
        }
      }
    }
  });

  it("the walker throws on a loop", () => {
    const loop: Rule[] = [{ source: "/:path*", destination: "https://loop.example/:path*", statusCode: 301 }];
    expect(() => walk(loop, "https://loop.example/x")).toThrow(/loop/);
  });
});
