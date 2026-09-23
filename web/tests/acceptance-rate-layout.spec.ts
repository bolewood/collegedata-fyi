import { expect, test } from "@playwright/test";
import { ACCEPTANCE_PILOT_SCHOOLS, acceptanceRatePath } from "../src/lib/acceptance-pilot";

// PRD 031: no allowlisted acceptance-rate table may be wider than its
// container on desktop, and no row (gap labels included) may push past it.
test.describe("acceptance-rate table fits its column", () => {
  test.skip(({ isMobile }) => isMobile, "desktop widths only");

  for (const width of [1440, 1024]) {
    for (const schoolId of ACCEPTANCE_PILOT_SCHOOLS) {
      test(`${schoolId} at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        const response = await page.goto(acceptanceRatePath(schoolId));
        expect(response?.status()).toBe(200);
        const sizes = await page.evaluate(() => {
          const scroll = document.querySelector(".acc-table-scroll") as HTMLElement | null;
          const table = document.querySelector(".acc-table") as HTMLElement | null;
          const cells = Array.from(document.querySelectorAll(".acc-table th, .acc-table td"));
          const right = scroll ? scroll.getBoundingClientRect().right : 0;
          return {
            container: scroll?.clientWidth ?? 0,
            table: table?.scrollWidth ?? Infinity,
            scrollOverflow: scroll ? scroll.scrollWidth - scroll.clientWidth : Infinity,
            pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            cellsPastEdge: cells.filter((cell) => cell.getBoundingClientRect().right > right + 0.5).length,
            // Text wider than its fixed-width cell (the round-3 gap-label bug).
            cellsSpilling: cells
              .filter((cell) => cell.scrollWidth > cell.clientWidth + 1)
              .map((cell) => cell.textContent?.trim()),
          };
        });
        expect(sizes.container).toBeGreaterThan(0);
        expect(sizes.table).toBeLessThanOrEqual(sizes.container);
        expect(sizes.scrollOverflow).toBeLessThanOrEqual(0);
        expect(sizes.pageOverflow).toBeLessThanOrEqual(0);
        expect(sizes.cellsPastEdge).toBe(0);
        expect(sizes.cellsSpilling).toEqual([]);
      });
    }
  }
});
