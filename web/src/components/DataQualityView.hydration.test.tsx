import { renderToStaticMarkup, renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

let currentParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/data-quality",
}));

import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { buildTrend } from "@/lib/data-quality-trend";
import { DataQualityView } from "./DataQualityView";

const view = () => <DataQualityView snapshot={FIXTURE_SNAPSHOT} trend={buildTrend([FIXTURE_SNAPSHOT])} reportsUrl="/x" />;

// A static page has no query string at build time, so its HTML is the default year. The browser's first render (the one
// React compares with that HTML) must match it whatever ?year= says; the real hook gives the server's answer to both.
describe("hydration: the first render ignores ?year= (React error #418)", () => {
  it("renders the same markup for every year in the query string as for none", () => {
    currentParams = new URLSearchParams();
    const built = renderToString(view());
    for (const y of FIXTURE_SNAPSHOT.years.map((x) => x.cds_year)) {
      currentParams = new URLSearchParams(`year=${y}`);
      expect(renderToString(view()), y).toBe(built);
    }
    currentParams = new URLSearchParams("year=not-a-year");
    expect(renderToStaticMarkup(view())).toBe(renderToStaticMarkup((currentParams = new URLSearchParams(), view())));
  });
});
