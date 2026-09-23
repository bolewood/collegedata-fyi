import { expect, test } from "@playwright/test";
import { ACCEPTANCE_PILOT_SCHOOLS, acceptanceRatePath } from "../src/lib/acceptance-pilot";

// One fact, one number: the latest year's applicants, admits, and rate
// agree on the acceptance-rate page, the school hub (summary and meta
// description), and the year page's key stats. Rates are compared against
// admitted ÷ applied at each surface's own display precision.
const num = (text: string) => Number(text.replace(/,/g, ""));

function rateMatches(printed: string, applied: number, admitted: number): boolean {
  const decimals = printed.includes(".") ? printed.split(".")[1].length : 0;
  return ((admitted / applied) * 100).toFixed(decimals) === printed;
}

test.describe("acceptance counts agree across pages", () => {
  test.skip(({ isMobile }) => isMobile, "desktop only");

  for (const schoolId of ACCEPTANCE_PILOT_SCHOOLS) {
    test(schoolId, async ({ page }) => {
      await page.goto(acceptanceRatePath(schoolId));
      const lead = await page.locator(".acc-lead p").first().innerText();
      const stat = /admitted (\d+\.\d)% of first-year applicants for fall (\d{4}) \(([\d,]+) of ([\d,]+)\)/.exec(lead);
      expect(stat, lead).not.toBeNull();
      const [, statRate, fall, admittedText, appliedText] = stat!;
      const applied = num(appliedText);
      const admitted = num(admittedText);
      expect(rateMatches(statRate, applied, admitted)).toBe(true);
      const year = `${fall}-${String((Number(fall) + 1) % 100).padStart(2, "0")}`;

      await page.goto(`/schools/${schoolId}`);
      const hubText = await page.locator(".cd-archive-lead").first().innerText();
      const hub = /In its (\d{4}-\d{2}) report, .*? says ([\d,]+) first-year students applied and ([\d,]+) were admitted, an acceptance rate of ([\d.]+)%/.exec(hubText);
      const meta = (await page.locator('meta[name="description"]').getAttribute("content")) ?? "";
      const hubMeta = /(\d{4}-\d{2}) report: ([\d.]+)% acceptance rate, ([\d,]+) applicants/.exec(meta);
      if (hub) {
        expect(hub[1]).toBe(year);
        expect(num(hub[2])).toBe(applied);
        expect(num(hub[3])).toBe(admitted);
        expect(rateMatches(hub[4], applied, admitted)).toBe(true);
      } else {
        // The hub's latest report has no usable counts (Rice 2025-26): it
        // states no acceptance figure, so there is nothing to disagree with.
        expect(hubText).not.toMatch(/acceptance rate of/);
      }
      if (hubMeta) {
        expect(hubMeta[1]).toBe(year);
        expect(num(hubMeta[3])).toBe(applied);
        expect(rateMatches(hubMeta[2], applied, admitted)).toBe(true);
      } else {
        expect(meta).not.toMatch(/acceptance rate/);
      }

      await page.goto(`/schools/${schoolId}/${year}`);
      const stats = await page.evaluate(() => {
        const out: Record<string, string> = {};
        for (const label of Array.from(document.querySelectorAll("p"))) {
          const value = label.nextElementSibling;
          if (value && ["Acceptance Rate", "Applications", "Admitted"].includes(label.textContent ?? "")) {
            out[label.textContent!] = value.textContent ?? "";
          }
        }
        return out;
      });
      expect(num(stats.Applications ?? "")).toBe(applied);
      expect(num(stats.Admitted ?? "")).toBe(admitted);
      expect(rateMatches((stats["Acceptance Rate"] ?? "").replace("%", ""), applied, admitted)).toBe(true);
    });
  }
});
