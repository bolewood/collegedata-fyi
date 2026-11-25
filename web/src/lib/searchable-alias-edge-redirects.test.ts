import { describe, expect, it } from "vitest";
import nextConfigExport from "../../next.config";
import redirectManifest from "../data/school-redirects.json";
import searchableSlugAliases from "../data/searchable-slug-aliases.json";

// Issue #518: a legal-name alias must 308 before routing and ISR, not from
// inside a cached page. These tests read the redirect list of the config
// Next actually loads: the default export, wrapped by withSentryConfig.
const AMBIGUOUS_ALIASES = ["bethel-university", "union-college", "columbia-college"];

async function configRedirects() {
  const config =
    typeof nextConfigExport === "function"
      ? await nextConfigExport("phase-production-build", { defaultConfig: {} })
      : nextConfigExport;
  return (await config.redirects?.()) ?? [];
}

describe("searchable legal-name aliases redirect at the edge", () => {
  it("lists the nine aliases this test guards", () => {
    expect(searchableSlugAliases).toHaveLength(9);
  });

  it.each(searchableSlugAliases)(
    "$alias is in the manifest and 308s every child route to $school_id",
    async ({ alias, school_id }) => {
      expect(redirectManifest).toContainEqual({ alias, school_id });
      const redirects = await configRedirects();
      expect(redirects).toContainEqual({
        source: `/schools/${alias}`,
        destination: `/schools/${school_id}`,
        permanent: true,
      });
      expect(redirects).toContainEqual({
        source: `/schools/${alias}/:path+`,
        destination: `/schools/${school_id}/:path+`,
        permanent: true,
      });
    },
  );

  it.each(AMBIGUOUS_ALIASES)("%s is not redirected", async (alias) => {
    expect(redirectManifest.map((entry) => entry.alias)).not.toContain(alias);
    const sources = (await configRedirects()).map((r) => r.source);
    const own = (s: string) =>
      s === `/schools/${alias}` || s.startsWith(`/schools/${alias}/`);
    expect(sources.filter(own)).toEqual([]);
  });

  it("matches only whole slugs: a longer slug sharing the prefix is not mistaken for the alias", () => {
    const own = (s: string, alias: string) =>
      s === `/schools/${alias}` || s.startsWith(`/schools/${alias}/`);
    expect(own("/schools/columbia-college-chicago", "columbia-college")).toBe(false);
    expect(own("/schools/columbia-college/:path+", "columbia-college")).toBe(true);
  });
});
