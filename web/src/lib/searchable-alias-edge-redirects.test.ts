import { describe, expect, it } from "vitest";
import { nextConfig } from "../../next.config";
import redirectManifest from "../data/school-redirects.json";
import searchableSlugAliases from "../data/searchable-slug-aliases.json";

// Issue #518: a legal-name alias must 308 before routing and ISR, not from
// inside a cached page. These tests read next.config's real redirect list.
const AMBIGUOUS_ALIASES = ["bethel-university", "union-college", "columbia-college"];

async function configRedirects() {
  return (await nextConfig.redirects?.()) ?? [];
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
      // One entry covers /:year, /gpa, /feed.xml, /:year/cds.csv, /:year/cds.xlsx
      // and /:year/opengraph-image.
      expect(redirects).toContainEqual({
        source: `/schools/${alias}/:path*`,
        destination: `/schools/${school_id}/:path*`,
        permanent: true,
      });
    },
  );

  it.each(AMBIGUOUS_ALIASES)("%s is not redirected", async (alias) => {
    expect(redirectManifest.map((entry) => entry.alias)).not.toContain(alias);
    const sources = (await configRedirects()).map((r) => r.source);
    expect(sources.filter((s) => s.startsWith(`/schools/${alias}`))).toEqual([]);
  });
});
