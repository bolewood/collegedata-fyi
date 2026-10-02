import { describe, expect, it } from "vitest";
import {
  addDays,
  buildUsageModel,
  findSpikes,
  isUsageLaunched,
  pickPeriod,
  schoolCountLabel,
  toUsageJson,
  type UsageDailyRow,
  type UsageSchoolMonthRow,
} from "./usage";

function range(start: string, end: string): string[] {
  const out: string[] = [];
  for (let d = start; d <= end; d = addDays(d, 1)) out.push(d);
  return out;
}

function row(day: string, metric: UsageDailyRow["metric"], access_method: string, client_kind: string, value: number): UsageDailyRow {
  return { day, metric, access_method, client_kind, value, method_version: 1 };
}

// Synthetic: Jul 6 to Sep 2, so July (from Jul 6) and August are complete.
const DAYS = range("2026-07-06", "2026-09-02");

function dailyRows(): UsageDailyRow[] {
  const rows: UsageDailyRow[] = [];
  for (const day of DAYS) {
    rows.push(row(day, "unique_downloads", "browser", "browser", 100));
    rows.push(row(day, "unique_downloads", "machine", "integration", 40));
    rows.push(row(day, "unique_downloads", "machine", "script", 20));
    rows.push(row(day, "unique_downloads", "machine", "unknown", 5));
    rows.push(row(day, "unique_downloads", "machine", "heavy_browser", 10));
    rows.push(row(day, "unique_downloads", "machine", "ai_user", 3));
    rows.push(row(day, "unique_downloads", "bots_crawlers", "declared_bot", 200));
    rows.push(row(day, "unique_downloads", "bots_crawlers", "ai_crawler", 50));
    rows.push(row(day, "site_downloads", "browser", "browser", 10));
    rows.push(row(day, "api_requests", "", "script", 300));
    rows.push(row(day, "api_requests", "", "declared_bot", 77));
    rows.push(row(day, "friendly_api_requests", "", "integration", 30));
    rows.push(row(day, "friendly_api_requests", "", "ai_crawler", 1));
    rows.push(row(day, "serving_requests", "", "", 5000));
  }
  return rows;
}

const SCHOOLS: UsageSchoolMonthRow[] = [
  { month: "2026-07-01", school_id: "alpha", school_name: "Alpha College", unique_downloads: 25, method_version: 1 },
  { month: "2026-08-01", school_id: "alpha", school_name: "Alpha College", unique_downloads: 144, method_version: 1 },
  { month: "2026-08-01", school_id: "beta", school_name: "Beta University", unique_downloads: null, method_version: 1 },
  { month: "2026-08-01", school_id: "gamma", school_name: "Gamma Institute", unique_downloads: 12, method_version: 1 },
  { month: "2026-07-01", school_id: "delta", school_name: "Delta State", unique_downloads: null, method_version: 1 },
  { month: "2026-08-01", school_id: "epsilon", school_name: "Epsilon College", unique_downloads: 310, method_version: 1 },
];

describe("usage model", () => {
  it("returns null with nothing published", () => {
    expect(buildUsageModel([], [])).toBeNull();
  });

  it("picks the latest complete month, starting from the first day", () => {
    expect(pickPeriod(DAYS)).toMatchObject({ start: "2026-08-01", end: "2026-08-31", label: "August", complete: true });
    const july = pickPeriod(range("2026-07-06", "2026-08-10"));
    expect(july).toMatchObject({ start: "2026-07-06", end: "2026-07-31", complete: true });
    expect(july.label).toBe("Jul 6–Jul 31");
    const gap = range("2026-07-06", "2026-08-31").filter((d) => d !== "2026-08-15");
    expect(pickPeriod(gap).start).toBe("2026-07-06");
    expect(pickPeriod(range("2026-07-06", "2026-07-20"))).toMatchObject({ complete: false, end: "2026-07-20" });
  });

  it("totals the headline for the period and since the start", () => {
    const model = buildUsageModel(dailyRows(), SCHOOLS)!;
    expect(model.period.label).toBe("August");
    expect(model.headline.browser).toBe(3100);
    expect(model.headline.machine).toBe(78 * 31);
    expect(model.headline.bots).toBe(250 * 31);
    expect(model.headline.browserSinceStart).toBe(100 * DAYS.length);
    expect(model.headline.siteShare).toBeCloseTo(0.1);
    expect(model.firstDay).toBe("2026-07-06");
    expect(model.lastDay).toBe("2026-09-02");
  });

  it("groups kinds without double counting", () => {
    const model = buildUsageModel(dailyRows(), SCHOOLS)!;
    const counted = Object.fromEntries(model.kinds.counted.map((k) => [k.key, k.value]));
    expect(counted).toEqual({ browser: 3100, integration: 1240, script: 775, heavy_browser: 310, ai_user: 93 });
    const total = model.kinds.counted.reduce((a, k) => a + k.value, 0);
    expect(total).toBe(model.headline.browser + model.headline.machine);
    expect(model.kinds.bots.map((k) => k.value)).toEqual([6200, 1550]);
  });

  it("leaves bots out of API use and keeps serving load separate", () => {
    const model = buildUsageModel(dailyRows(), SCHOOLS)!;
    expect(model.api.postgrest).toBe(300 * 31);
    expect(model.api.simple).toBe(30 * 31);
    expect(model.api.total).toBe(330 * 31);
    expect(model.api.botsExcluded).toBe(78 * 31);
    expect(model.api.daily[0]).toEqual({ day: "2026-07-06", value: 330 });
    expect(model.serving).toBe(5000 * 31);
  });

  it("summarizes the spread across schools for the period month only", () => {
    const model = buildUsageModel(dailyRows(), SCHOOLS)!;
    expect(model.spread).toEqual({
      schools: 4,
      median: 12,
      atLeast10: 3,
      atLeast100: 2,
      buckets: [
        { label: "1–9", schools: 1 },
        { label: "10–29", schools: 1 },
        { label: "30–99", schools: 0 },
        { label: "100–299", schools: 1 },
        { label: "300+", schools: 1 },
      ],
    });
  });

  it("reports a hidden median when most schools are under the floor", () => {
    const rows: UsageSchoolMonthRow[] = ["a", "b", "c"].map((id, i) => ({
      month: "2026-08-01",
      school_id: id,
      school_name: id,
      unique_downloads: i === 2 ? 50 : null,
      method_version: 1,
    }));
    expect(buildUsageModel(dailyRows(), rows)!.spread!.median).toBeNull();
  });

  it("builds the school lookup from published months only", () => {
    const model = buildUsageModel(dailyRows(), SCHOOLS)!;
    const alpha = model.schools.find((s) => s.school_id === "alpha")!;
    expect(alpha).toMatchObject({ month: 144, total: 169 });
    const delta = model.schools.find((s) => s.school_id === "delta")!;
    expect(delta).toMatchObject({ month: null, total: null });
    expect(model.schools.map((s) => s.school_name)).toEqual([
      "Alpha College",
      "Beta University",
      "Delta State",
      "Epsilon College",
      "Gamma Institute",
    ]);
  });

  it("rounds school counts and hides the floor", () => {
    expect(schoolCountLabel(null)).toBe("fewer than 10");
    expect(schoolCountLabel(9)).toBe("fewer than 10");
    expect(schoolCountLabel(14)).toBe("about 10");
    expect(schoolCountLabel(15)).toBe("about 20");
    expect(schoolCountLabel(1234)).toBe("about 1,230");
  });

  it("flags machine spikes against the median day", () => {
    const points = range("2026-08-01", "2026-08-10").map((day, i) => ({
      day,
      browser: 100,
      machine: i === 4 ? 5000 : i === 6 ? 900 : 300,
      bots: 0,
    }));
    expect(findSpikes(points)).toEqual([{ day: "2026-08-05", machine: 5000 }]);
  });

  it("splits weeks from the first day and marks partial weeks", () => {
    const model = buildUsageModel(dailyRows(), SCHOOLS)!;
    expect(model.weeks[0]).toMatchObject({ start: "2026-07-06", days: 7, browser: 700 });
    expect(model.weeks.at(-1)!.days).toBe(DAYS.length % 7 || 7);
  });

  it("gates launch on Nov 1, 2026 UTC", () => {
    expect(isUsageLaunched(new Date("2026-10-31T23:59:59Z"))).toBe(false);
    expect(isUsageLaunched(new Date("2026-11-01T00:00:00Z"))).toBe(true);
  });

  it("writes only published columns to usage.json", () => {
    const extra = { ...dailyRows()[0], published_at: "x" } as UsageDailyRow;
    const json = toUsageJson([extra], SCHOOLS.slice(0, 1), new Date("2026-10-02T00:00:00Z"));
    expect(json.license).toBe("CC0-1.0");
    expect(Object.keys(json.daily[0]).sort()).toEqual(
      ["access_method", "client_kind", "day", "method_version", "metric", "value"],
    );
    expect(Object.keys(json.school_months[0]).sort()).toEqual(
      ["method_version", "month", "school_id", "school_name", "unique_downloads"],
    );
    expect(json.method_changelog[0].version).toBe(1);
  });
});
