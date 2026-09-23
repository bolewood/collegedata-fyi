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

// Non-pilot hubs go through the IPEDS gate (c1-hub-gate). Whatever the hub
// shows — a corrected value, the old value, or nothing — its year page
// shows the same. Sample covers each gate outcome.
// [school, the year the hub's latest projected row covers when the hub
// states no figure (suppressed); otherwise read from the hub sentence].
const GATED_SAMPLE: [string, string | null][] = [
  ["washington-university-in-st-louis", null], // repaired, corroborated by IPEDS
  ["fitchburg-state-university", null], // keeps the projection (matches IPEDS)
  ["university-of-arkansas", null], // keeps the projection (closer to IPEDS)
  ["lake-superior-state-university", "2024-25"], // suppressed
  ["university-of-houston", null], // repaired
  ["university-of-houston-system-administration", "2025-26"], // administrative unit: no figures
  ["cornell", null], // unchanged
];

test.describe("non-pilot hubs and year pages agree", () => {
  test.skip(({ isMobile }) => isMobile, "desktop only");

  for (const [schoolId, suppressedYear] of GATED_SAMPLE) {
    test(schoolId, async ({ page }) => {
      await page.goto(`/schools/${schoolId}`);
      const hubText = await page.locator(".cd-archive-lead").first().innerText();
      const hub = /In its (\d{4}-\d{2}) report, .*? says ([\d,]+) first-year students applied and ([\d,]+) were admitted/.exec(hubText);
      if (suppressedYear) expect(hub, hubText).toBeNull();
      else expect(hub, hubText).not.toBeNull();
      const year = hub?.[1] ?? suppressedYear!;

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
      const yearText = await page.locator(".cd-archive-lead").first().innerText();
      if (hub) {
        expect(num(stats.Applications ?? "")).toBe(num(hub[2]));
        expect(num(stats.Admitted ?? "")).toBe(num(hub[3]));
        expect(yearText).toContain(`says ${hub[2]} first-year students applied and ${hub[3]} were admitted`);
      } else {
        expect(stats.Applications, `${schoolId} year page shows applications the hub withheld`).toBeUndefined();
        expect(stats["Acceptance Rate"]).toBeUndefined();
        expect(yearText).not.toMatch(/acceptance rate of/);
      }
    });
  }
});

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
