import { expect, test } from "@playwright/test";
import { GPA_SCHOOLS, gpaPath } from "../src/lib/gpa-pilot";

test.describe("gpa table fits its column", () => {
  test.skip(({ isMobile }) => isMobile, "desktop widths only");

  for (const width of [1440, 1024]) {
    for (const schoolId of GPA_SCHOOLS) {
      test(`${schoolId} at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        const response = await page.goto(gpaPath(schoolId));
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
