import { describe, expect, it } from "vitest";
import { matchHas } from "next/dist/shared/lib/router/utils/prepare-destination";
// @ts-expect-error Next ships its compiled path-to-regexp without types.
import { pathToRegexp } from "next/dist/compiled/path-to-regexp";
import retiredSchoolAliases from "../data/school-redirects.json";
import { nextConfig } from "../../next.config";
import { SITE_HOST, SITE_ORIGIN } from "./site";

type Rule = {
  source: string;
  destination: string;
  has?: unknown[];
  statusCode?: number;
  permanent?: boolean;
};

const rules = async () => (await nextConfig.redirects!()) as Rule[];

/** First rule that matches host and path, with its destination filled in, as Next evaluates `redirects()` in order. */
function firstRedirect(all: Rule[], host: string, path: string) {
  const req = { headers: { host } } as never;
  for (const rule of all) {
    if (rule.has && matchHas(req, {}, rule.has as never) === false) continue;
    const keys: { name: string }[] = [];
    const re = pathToRegexp(rule.source, keys) as RegExp;
    const m = re.exec(path);
    if (!m) continue;
    let destination = rule.destination;
    keys.forEach((key, i) => {
      // An empty optional/repeated parameter drops its leading slash, as path-to-regexp's compile does.
      const value = m[i + 1] ?? "";
      destination = destination.replace(new RegExp(`${value ? "" : "/?"}:${key.name}[*+?]?`), value);
    });
    return { destination, status: rule.statusCode ?? (rule.permanent ? 308 : 307) };
  }
  return null;
}

/** Follows redirects across hosts; returns the hops taken and the final URL. */
function walk(all: Rule[], url: string) {
  const hops: { status: number; to: string }[] = [];
  let current = new URL(url);
  for (let i = 0; i < 10; i++) {
    const hit = firstRedirect(all, current.host, current.pathname);
    if (!hit) break;
    const next = new URL(hit.destination, current);
    hops.push({ status: hit.status, to: next.toString() });
    current = next;
  }
  return { hops, final: current };
}

describe("old site host redirects", () => {
  it("sends /api/* on both old hosts to the new host with a 308", async () => {
    const all = await rules();
    for (const host of ["www.collegedata.fyi", "collegedata.fyi"]) {
      expect(walk(all, `https://${host}/api/schools/yale/facts`).hops).toEqual([
        { status: 308, to: `${SITE_ORIGIN}/api/schools/yale/facts` },
      ]);
      expect(walk(all, `https://${host}/api`).hops).toEqual([{ status: 308, to: `${SITE_ORIGIN}/api` }]);
    }
  });

  it("sends every other path on both old hosts to the new host with a 301", async () => {
    const all = await rules();
    for (const host of ["www.collegedata.fyi", "collegedata.fyi"]) {
      for (const path of ["/", "/schools/yale", "/schools/yale/2024-25", "/coverage", "/apix/x"]) {
        const { hops } = walk(all, `https://${host}${path}`);
        expect(hops[0], `${host}${path}`).toEqual({ status: 301, to: `${SITE_ORIGIN}${path}` });
      }
    }
  });

  it("does not touch the new host or the old API host", async () => {
    const all = await rules();
    expect(firstRedirect(all, SITE_HOST, "/api/schools")).toBeNull();
    expect(firstRedirect(all, "api.collegedata.fyi", "/rest/v1/schools")).toBeNull();
    expect(firstRedirect(all, "api.collegedata.fyi", "/api/x")).toBeNull();
  });

  it("puts the old-host rules before every other rule", async () => {
    const all = await rules();
    const firstOther = all.findIndex((r) => !JSON.stringify(r.has ?? []).includes("collegedata"));
    const lastOld = all.map((r) => JSON.stringify(r.has ?? []).includes("collegedata")).lastIndexOf(true);
    expect(lastOld).toBeLessThan(firstOther);
  });

  it("reaches the final school page in at most 2 hops for every retired alias on an old host", async () => {
    const all = await rules();
    expect(retiredSchoolAliases.length).toBeGreaterThan(0);
    for (const { alias, school_id } of retiredSchoolAliases) {
      for (const host of ["www.collegedata.fyi", "collegedata.fyi"]) {
        for (const suffix of ["", "/2024-25"]) {
          const { hops, final } = walk(all, `https://${host}/schools/${alias}${suffix}`);
          expect(hops.length, `${host} ${alias}${suffix}`).toBeLessThanOrEqual(2);
          expect(final.toString()).toBe(`${SITE_ORIGIN}/schools/${school_id}${suffix}`);
        }
      }
    }
  });
});
