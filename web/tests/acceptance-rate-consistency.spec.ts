import { expect, test, type Page } from "@playwright/test";
import { ACCEPTANCE_PILOT_SCHOOLS, acceptanceRatePath } from "../src/lib/acceptance-pilot";

// One fact, one number: the latest year's applicants, admits, and rate
// agree across the acceptance-rate page, the school hub's headline ribbon,
// and the year page's key stats, lead, and meta description (#518 moved
// latest-year prose and metaFactFragment off the hub to avoid SERP
// duplication, while keeping the hub ribbon on the same gated figures).
const num = (text: string) => Number(text.replace(/,/g, ""));

type HubAcceptance = {
  year: string;
  rate: string;
  admitted: string;
  applied: string;
};

async function hubAcceptanceStat(page: Page): Promise<HubAcceptance | null> {
  return page.evaluate(() => {
    const cell = document.querySelector('[data-testid="ribbon-cell-hub-acceptance"]');
    if (!cell) return null;
    const value = cell.querySelector(".cd-ribbon__value")?.textContent?.trim() ?? "";
    const sub = cell.querySelector(".cd-ribbon__sub-text")?.textContent?.trim() ?? "";
    const href = cell.querySelector("a.cd-ribbon__source")?.getAttribute("href") ?? "";
    const yearMatch = /\/schools\/[^/]+\/(\d{4}-\d{2})/.exec(href);
    const countsMatch = /^([\d,]+) of ([\d,]+)$/.exec(sub);
    if (!yearMatch || !countsMatch || !value) return null;
    return {
      year: yearMatch[1],
      rate: value.replace("%", ""),
      admitted: countsMatch[1],
      applied: countsMatch[2],
    };
  });
}

// PR 035 (SchoolFactRibbon) moved year-page C1 stats out of `<p>` labels
// into `data-testid="ribbon-cell-*"` cells. The numeric contract is unchanged.
async function yearPageAdmissionsStats(page: Page): Promise<Record<string, string>> {
  return page.evaluate(() => {
    const valueOf = (testId: string) => {
      const text = document
        .querySelector(`[data-testid="${testId}"] .cd-ribbon__value`)
        ?.textContent?.trim();
      return text || undefined;
    };
    const out: Record<string, string> = {};
    const applications = valueOf("ribbon-cell-applications");
    const admitted = valueOf("ribbon-cell-admitted");
    const rate = valueOf("ribbon-cell-acceptance-rate");
    if (applications) out.Applications = applications;
    if (admitted) out.Admitted = admitted;
    if (rate) out["Acceptance Rate"] = rate;
    return out;
  });
}

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
  // IPEDS open admission. The 2024-25 PDF reports 2,106 applied and 2,106
  // admitted; it was suppressed only while an old extraction misread the
  // "another gender" applicants as 41 (2,146 applied).
  ["lake-superior-state-university", null],
  ["university-of-houston", null], // repaired
  // The administrative-unit outcome had one live example, the University of
  // Houston System office, which carried the main campus's file. That copy was
  // hidden on 2026-11-14, so the office has no hub or year page to compare.
  ["cornell", null], // unchanged
];

test.describe("non-pilot hubs and year pages agree", () => {
  test.skip(({ isMobile }) => isMobile, "desktop only");

  for (const [schoolId, suppressedYear] of GATED_SAMPLE) {
    test(schoolId, async ({ page }) => {
      await page.goto(`/schools/${schoolId}`);
      const hub = await hubAcceptanceStat(page);
      if (suppressedYear) expect(hub).toBeNull();
      else expect(hub).not.toBeNull();
      const year = hub?.year ?? suppressedYear!;

      await page.goto(`/schools/${schoolId}/${year}`);
      const stats = await yearPageAdmissionsStats(page);
      const yearText = await page.locator(".cd-archive-lead").first().innerText();
      if (hub) {
        expect(num(stats.Applications ?? "")).toBe(num(hub.applied));
        expect(num(stats.Admitted ?? "")).toBe(num(hub.admitted));
        expect(rateMatches(hub.rate, num(hub.applied), num(hub.admitted))).toBe(true);
        expect(yearText).toContain(`says ${hub.applied} first-year students applied and ${hub.admitted} were admitted`);
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
      const hub = await hubAcceptanceStat(page);
      const hubMeta = (await page.locator('meta[name="description"]').getAttribute("content")) ?? "";
      // Hub stays archive-level so it does not duplicate the latest year's snippet (#518).
      expect(hubMeta).not.toMatch(/acceptance rate/);
      if (hub) {
        expect(hub.year).toBe(year);
        expect(num(hub.applied)).toBe(applied);
        expect(num(hub.admitted)).toBe(admitted);
        expect(rateMatches(hub.rate, applied, admitted)).toBe(true);
      }

      await page.goto(`/schools/${schoolId}/${year}`);
      const stats = await yearPageAdmissionsStats(page);
      expect(num(stats.Applications ?? "")).toBe(applied);
      expect(num(stats.Admitted ?? "")).toBe(admitted);
      expect(rateMatches((stats["Acceptance Rate"] ?? "").replace("%", ""), applied, admitted)).toBe(true);
    });
  }
});
