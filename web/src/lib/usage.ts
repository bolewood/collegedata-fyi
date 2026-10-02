// PRD 033: model for /usage and /usage.json. Pure functions over the rows in
// usage_public_daily and usage_public_school_months; the privacy rules are
// applied when those rows are published, not here.

export const USAGE_LAUNCH_DATE = "2026-11-01";

/** Site requests are tagged from the hour after this deploy; earlier hours are inferred. */
export const SITE_TAGGING_T0 = "2026-10-01T19:16:00Z";

export const METHOD_CHANGELOG: { version: number; from: string; change: string }[] = [
  {
    version: 1,
    from: "2026-07-06",
    change:
      "First version. One download per visitor, file, and day. Browser-like visitors that open more than 30 files in a day count as machine.",
  },
];

export const HEAVY_CLIENT_FILES_PER_DAY = 30;
export const SCHOOL_FLOOR = 10;

export function isUsageLaunched(now: Date = new Date()): boolean {
  return now.getTime() >= Date.parse(`${USAGE_LAUNCH_DATE}T00:00:00Z`);
}

export type UsageMetric =
  | "unique_downloads"
  | "site_downloads"
  | "api_requests"
  | "friendly_api_requests"
  | "serving_requests";

export type UsageDailyRow = {
  day: string;
  metric: UsageMetric;
  access_method: string;
  client_kind: string;
  value: number;
  method_version: number;
};

export type UsageSchoolMonthRow = {
  month: string;
  school_id: string;
  school_name: string;
  unique_downloads: number | null;
  method_version: number;
};

export type DayPoint = { day: string; browser: number; machine: number; bots: number };
export type KindRow = { key: string; label: string; detail: string; value: number };
export type Spike = { day: string; machine: number };
export type WeekRow = { start: string; days: number; browser: number; machine: number; bots: number };
export type Bucket = { label: string; schools: number };
export type SchoolLookupRow = {
  school_id: string;
  school_name: string;
  month: number | null;
  total: number | null;
};

export type UsageModel = {
  firstDay: string;
  lastDay: string;
  dayCount: number;
  period: { start: string; end: string; label: string; complete: boolean };
  daily: DayPoint[];
  averages: DayPoint[];
  headline: {
    browser: number;
    machine: number;
    bots: number;
    browserSinceStart: number;
    machineSinceStart: number;
    siteShare: number | null;
  };
  kinds: { counted: KindRow[]; bots: KindRow[] };
  api: {
    total: number;
    postgrest: number;
    simple: number;
    botsExcluded: number;
    topThreeShare: number | null;
    daily: { day: string; value: number }[];
  };
  serving: number;
  spikes: Spike[];
  weeks: WeekRow[];
  spread: {
    schools: number;
    median: number | null;
    atLeast10: number;
    atLeast100: number;
    buckets: Bucket[];
  } | null;
  schools: SchoolLookupRow[];
  methodVersion: number;
};

const BOT_KINDS = new Set(["declared_bot", "ai_crawler"]);

export function addDays(day: string, n: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + n);
  return date.toISOString().slice(0, 10);
}

function monthEnd(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10);
}

export function formatDay(day: string, opts: { year?: boolean } = {}): string {
  return new Date(`${day}T00:00:00Z`).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    ...(opts.year ? { year: "numeric" } : {}),
    timeZone: "UTC",
  });
}

export function formatMonth(month: string): string {
  return new Date(`${month.slice(0, 7)}-01T00:00:00Z`).toLocaleString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function formatCount(n: number): string {
  return n.toLocaleString("en-US");
}

/** School counts on the page: rounded to 10, and "fewer than 10" below the floor. */
export function schoolCountLabel(n: number | null): string {
  if (n === null || n < SCHOOL_FLOOR) return "fewer than 10";
  return `about ${formatCount(Math.round(n / 10) * 10)}`;
}

function sum(values: number[]): number {
  return values.reduce((a, b) => a + b, 0);
}

/**
 * Latest calendar month whose every day, from the first published day on, is
 * published. Falls back to everything published when no month is complete.
 */
export function pickPeriod(days: string[]): UsageModel["period"] {
  const have = new Set(days);
  const first = days[0];
  const last = days[days.length - 1];
  for (let month = last.slice(0, 7); month >= first.slice(0, 7); ) {
    const start = `${month}-01` < first ? first : `${month}-01`;
    const end = monthEnd(month);
    let complete = end <= last;
    for (let d = start; complete && d <= end; d = addDays(d, 1)) complete = have.has(d);
    if (complete) {
      const label = start === `${month}-01` ? formatMonth(month).split(" ")[0] : `${formatDay(start)}–${formatDay(end)}`;
      return { start, end, label, complete: true };
    }
    const [y, m] = month.split("-").map(Number);
    month = m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
  }
  return { start: first, end: last, label: `${formatDay(first)}–${formatDay(last)}`, complete: false };
}

function trailingAverage(points: DayPoint[], window = 7): DayPoint[] {
  return points.map((point, i) => {
    const slice = points.slice(Math.max(0, i - window + 1), i + 1);
    return {
      day: point.day,
      browser: sum(slice.map((p) => p.browser)) / slice.length,
      machine: sum(slice.map((p) => p.machine)) / slice.length,
      bots: sum(slice.map((p) => p.bots)) / slice.length,
    };
  });
}

export const SPIKE_FLOOR = 2000;

/** Days where machine downloads jump: at least SPIKE_FLOOR and 4x the median machine day. */
export function findSpikes(points: DayPoint[]): Spike[] {
  if (!points.length) return [];
  const sorted = points.map((p) => p.machine).sort((a, b) => a - b);
  const median = sorted[Math.floor((sorted.length - 1) / 2)];
  const threshold = Math.max(SPIKE_FLOOR, 4 * median);
  return points.filter((p) => p.machine >= threshold).map((p) => ({ day: p.day, machine: p.machine }));
}

const SPREAD_BUCKETS: { label: string; min: number; max: number }[] = [
  { label: "10–29", min: 10, max: 29 },
  { label: "30–99", min: 30, max: 99 },
  { label: "100–299", min: 100, max: 299 },
  { label: "300+", min: 300, max: Number.POSITIVE_INFINITY },
];

function spreadFor(rows: UsageSchoolMonthRow[]): UsageModel["spread"] {
  if (!rows.length) return null;
  const values = rows.map((r) => r.unique_downloads);
  // Hidden cells are 1 to 9, so they sort below every published value.
  const ordered = values.map((v) => v ?? 0).sort((a, b) => a - b);
  const mid = ordered[Math.floor((ordered.length - 1) / 2)];
  const hidden = values.filter((v) => v === null).length;
  return {
    schools: rows.length,
    median: mid >= SCHOOL_FLOOR ? mid : null,
    atLeast10: rows.length - hidden,
    atLeast100: values.filter((v) => v !== null && v >= 100).length,
    buckets: [
      { label: "1–9", schools: hidden },
      ...SPREAD_BUCKETS.map((b) => ({
        label: b.label,
        schools: values.filter((v) => v !== null && v >= b.min && v <= b.max).length,
      })),
    ],
  };
}

function kindsFor(rows: UsageDailyRow[]): UsageModel["kinds"] {
  const byKey = new Map<string, number>();
  const add = (key: string, value: number) => byKey.set(key, (byKey.get(key) ?? 0) + value);
  for (const row of rows) {
    if (row.access_method === "browser") add("browser", row.value);
    else if (row.access_method === "machine") {
      if (row.client_kind === "integration") add("integration", row.value);
      else if (row.client_kind === "heavy_browser") add("heavy_browser", row.value);
      else if (row.client_kind === "ai_user" || row.client_kind === "ai_agent") add("ai_user", row.value);
      else add("script", row.value);
    } else if (row.access_method === "bots_crawlers") {
      add(row.client_kind === "ai_crawler" ? "ai_crawler" : "declared_bot", row.value);
    }
  }
  const get = (key: string) => byKey.get(key) ?? 0;
  return {
    counted: [
      { key: "browser", label: "Browser", detail: "People in a web browser", value: get("browser") },
      { key: "integration", label: "Integrations", detail: "Apps and services built on the archive", value: get("integration") },
      { key: "script", label: "Scripts", detail: "Code that fetches files directly", value: get("script") },
      {
        key: "heavy_browser",
        label: "Busy browsers",
        detail: `Browser-like, more than ${HEAVY_CLIENT_FILES_PER_DAY} files a day`,
        value: get("heavy_browser"),
      },
      { key: "ai_user", label: "AI assistants", detail: "Fetching for a person who asked", value: get("ai_user") },
    ],
    bots: [
      { key: "declared_bot", label: "Search and other bots", detail: "Programs that name themselves as bots", value: get("declared_bot") },
      { key: "ai_crawler", label: "AI crawlers", detail: "Collecting pages for model training", value: get("ai_crawler") },
    ],
  };
}

function weeksFor(points: DayPoint[]): WeekRow[] {
  const weeks: WeekRow[] = [];
  for (let i = 0; i < points.length; i += 7) {
    const slice = points.slice(i, i + 7);
    weeks.push({
      start: slice[0].day,
      days: slice.length,
      browser: sum(slice.map((p) => p.browser)),
      machine: sum(slice.map((p) => p.machine)),
      bots: sum(slice.map((p) => p.bots)),
    });
  }
  return weeks;
}

function schoolsFor(rows: UsageSchoolMonthRow[], periodMonth: string | null): SchoolLookupRow[] {
  const bySchool = new Map<string, SchoolLookupRow>();
  for (const row of rows) {
    const current = bySchool.get(row.school_id) ?? {
      school_id: row.school_id,
      school_name: row.school_name,
      month: null,
      total: null,
    };
    if (row.unique_downloads !== null) current.total = (current.total ?? 0) + row.unique_downloads;
    if (periodMonth && row.month.slice(0, 7) === periodMonth) {
      current.month = row.unique_downloads;
      current.school_name = row.school_name;
    }
    bySchool.set(row.school_id, current);
  }
  return [...bySchool.values()].sort((a, b) => a.school_name.localeCompare(b.school_name));
}

export function buildUsageModel(
  dailyRows: UsageDailyRow[],
  schoolRows: UsageSchoolMonthRow[],
): UsageModel | null {
  const downloadRows = dailyRows.filter((r) => r.metric === "unique_downloads");
  const days = [...new Set(downloadRows.map((r) => r.day))].sort();
  if (!days.length) return null;

  const pointByDay = new Map<string, DayPoint>(days.map((day) => [day, { day, browser: 0, machine: 0, bots: 0 }]));
  for (const row of downloadRows) {
    const point = pointByDay.get(row.day)!;
    if (row.access_method === "browser") point.browser += row.value;
    else if (row.access_method === "machine") point.machine += row.value;
    else if (row.access_method === "bots_crawlers") point.bots += row.value;
  }
  const daily = days.map((day) => pointByDay.get(day)!);

  const period = pickPeriod(days);
  const inPeriod = (day: string) => day >= period.start && day <= period.end;
  const periodPoints = daily.filter((p) => inPeriod(p.day));
  const periodRows = dailyRows.filter((r) => inPeriod(r.day));
  const browser = sum(periodPoints.map((p) => p.browser));
  const siteDownloads = sum(periodRows.filter((r) => r.metric === "site_downloads").map((r) => r.value));

  const apiByDay = new Map<string, number>(days.map((day) => [day, 0]));
  let postgrest = 0;
  let simple = 0;
  let botsExcluded = 0;
  for (const row of dailyRows) {
    if (row.metric !== "api_requests" && row.metric !== "friendly_api_requests") continue;
    if (BOT_KINDS.has(row.client_kind)) {
      if (inPeriod(row.day)) botsExcluded += row.value;
      continue;
    }
    if (apiByDay.has(row.day)) apiByDay.set(row.day, apiByDay.get(row.day)! + row.value);
    if (!inPeriod(row.day)) continue;
    if (row.metric === "api_requests") postgrest += row.value;
    else simple += row.value;
  }
  const apiDaily = days.map((day) => ({ day, value: apiByDay.get(day)! }));
  const apiPeriod = apiDaily.filter((d) => inPeriod(d.day)).map((d) => d.value);
  const apiTotal = postgrest + simple;
  const topThree = [...apiPeriod].sort((a, b) => b - a).slice(0, 3);

  const periodMonth = period.complete ? period.start.slice(0, 7) : null;
  const monthRows = periodMonth ? schoolRows.filter((r) => r.month.slice(0, 7) === periodMonth) : [];

  return {
    firstDay: days[0],
    lastDay: days[days.length - 1],
    dayCount: days.length,
    period,
    daily,
    averages: trailingAverage(daily),
    headline: {
      browser,
      machine: sum(periodPoints.map((p) => p.machine)),
      bots: sum(periodPoints.map((p) => p.bots)),
      browserSinceStart: sum(daily.map((p) => p.browser)),
      machineSinceStart: sum(daily.map((p) => p.machine)),
      siteShare: browser > 0 ? siteDownloads / browser : null,
    },
    kinds: kindsFor(periodRows.filter((r) => r.metric === "unique_downloads")),
    api: {
      total: apiTotal,
      postgrest,
      simple,
      botsExcluded,
      topThreeShare: apiTotal > 0 ? sum(topThree) / apiTotal : null,
      daily: apiDaily,
    },
    serving: sum(periodRows.filter((r) => r.metric === "serving_requests").map((r) => r.value)),
    spikes: findSpikes(daily),
    weeks: weeksFor(daily),
    spread: spreadFor(monthRows),
    schools: schoolsFor(schoolRows, periodMonth),
    methodVersion: Math.max(...downloadRows.map((r) => r.method_version)),
  };
}

export type UsageJson = {
  license: "CC0-1.0";
  generated_at: string;
  method_url: string;
  site_tagging_t0: string;
  heavy_client_files_per_day: number;
  school_floor: number;
  method_changelog: typeof METHOD_CHANGELOG;
  daily: UsageDailyRow[];
  school_months: UsageSchoolMonthRow[];
};

export function toUsageJson(
  dailyRows: UsageDailyRow[],
  schoolRows: UsageSchoolMonthRow[],
  now: Date = new Date(),
): UsageJson {
  return {
    license: "CC0-1.0",
    generated_at: now.toISOString(),
    method_url: "https://www.collegedata.fyi/usage#how-we-count",
    site_tagging_t0: SITE_TAGGING_T0,
    heavy_client_files_per_day: HEAVY_CLIENT_FILES_PER_DAY,
    school_floor: SCHOOL_FLOOR,
    method_changelog: METHOD_CHANGELOG,
    daily: dailyRows.map(({ day, metric, access_method, client_kind, value, method_version }) => ({
      day,
      metric,
      access_method,
      client_kind,
      value,
      method_version,
    })),
    school_months: schoolRows.map(({ month, school_id, school_name, unique_downloads, method_version }) => ({
      month,
      school_id,
      school_name,
      unique_downloads,
      method_version,
    })),
  };
}
