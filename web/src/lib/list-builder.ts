import {
  scorePosition,
  type PositionResult,
  type SchoolAcademicProfile,
  type StudentProfile,
  type Tier,
} from "./positioning";

export type SchoolControl = "public" | "private_nonprofit" | "private_for_profit" | "unknown";
export type Region = "northeast" | "midwest" | "south" | "west" | "territory" | "unknown";
export type TestPolicySignal = "high_submit" | "effective_optional" | "mostly_non_submitters" | "unknown";
export type CarnegieBucket =
  | "doctoral"
  | "masters"
  | "baccalaureate"
  | "associates"
  | "special_focus"
  | "tribal"
  | "unknown";

export type MatchBuilderSchool = SchoolAcademicProfile & {
  documentId: string;
  archiveUrl: string | null;
  yearStart: number | null;
  schoolUrl: string;
  state: string | null;
  control: SchoolControl;
  region: Region;
  carnegieBasic: number | null;
  carnegieBucket: CarnegieBucket;
  testPolicySignal: TestPolicySignal;
};

export type MatchFilters = {
  control: "all" | SchoolControl;
  region: "all" | Region;
  admitRate: "all" | "under_25" | "25_50" | "50_plus";
  testPolicy: "all" | TestPolicySignal;
  currentOnly: boolean;
  carnegie: "all" | CarnegieBucket;
  sort: "fit" | "admit_rate" | "name";
};

export type RankedMatchSchool = MatchBuilderSchool & {
  result: PositionResult;
  bestPercentile: number | null;
  rankScore: number;
};

export const DEFAULT_MATCH_FILTERS: MatchFilters = {
  control: "all",
  region: "all",
  admitRate: "all",
  testPolicy: "all",
  currentOnly: false,
  carnegie: "all",
  sort: "fit",
};

const TIER_ORDER: Record<Tier, number> = {
  strong_fit: 0,
  likely: 1,
  possible: 2,
  unlikely: 3,
  long_shot: 4,
  unknown: 5,
};

const REGION_BY_STATE: Record<string, Region> = {
  CT: "northeast",
  ME: "northeast",
  MA: "northeast",
  NH: "northeast",
  RI: "northeast",
  VT: "northeast",
  NJ: "northeast",
  NY: "northeast",
  PA: "northeast",
  IL: "midwest",
  IN: "midwest",
  MI: "midwest",
  OH: "midwest",
  WI: "midwest",
  IA: "midwest",
  KS: "midwest",
  MN: "midwest",
  MO: "midwest",
  NE: "midwest",
  ND: "midwest",
  SD: "midwest",
  DE: "south",
  DC: "south",
  FL: "south",
  GA: "south",
  MD: "south",
  NC: "south",
  SC: "south",
  VA: "south",
  WV: "south",
  AL: "south",
  KY: "south",
  MS: "south",
  TN: "south",
  AR: "south",
  LA: "south",
  OK: "south",
  TX: "south",
  AZ: "west",
  CO: "west",
  ID: "west",
  MT: "west",
  NV: "west",
  NM: "west",
  UT: "west",
  WY: "west",
  AK: "west",
  CA: "west",
  HI: "west",
  OR: "west",
  WA: "west",
  AS: "territory",
  GU: "territory",
  MP: "territory",
  PR: "territory",
  VI: "territory",
};

export function controlFromScorecard(value: number | null | undefined): SchoolControl {
  if (value === 1) return "public";
  if (value === 2) return "private_nonprofit";
  if (value === 3) return "private_for_profit";
  return "unknown";
}

export function regionFromState(state: string | null | undefined): Region {
  if (!state) return "unknown";
  return REGION_BY_STATE[state.toUpperCase()] ?? "unknown";
}

export function carnegieBucket(code: number | null | undefined): CarnegieBucket {
  if (code == null) return "unknown";
  if (code >= 15 && code <= 17) return "doctoral";
  if (code >= 18 && code <= 20) return "masters";
  if (code >= 21 && code <= 23) return "baccalaureate";
  if (code >= 1 && code <= 14) return "associates";
  if (code >= 24 && code <= 32) return "special_focus";
  if (code === 33) return "tribal";
  return "unknown";
}

export function testPolicySignal(
  satSubmitRate: number | null,
  actSubmitRate: number | null,
): TestPolicySignal {
  const rates = [satSubmitRate, actSubmitRate].filter(
    (rate): rate is number => rate != null && Number.isFinite(rate),
  );
  if (rates.length === 0) return "unknown";
  const highest = Math.max(...rates);
  if (highest >= 0.85) return "high_submit";
  if (highest <= 0.1) return "mostly_non_submitters";
  return "effective_optional";
}

export function isRankableSchool(school: MatchBuilderSchool): boolean {
  const hasTestData = school.satCompositeP50 != null || school.actCompositeP50 != null;
  return hasTestData;
}

export function applyMatchFilters(
  schools: MatchBuilderSchool[],
  filters: MatchFilters,
): MatchBuilderSchool[] {
  const latestYear = Math.max(
    ...schools
      .map((school) => school.yearStart)
      .filter((year): year is number => year != null),
  );

  return schools.filter((school) => {
    if (!isRankableSchool(school)) return false;
    if (filters.control !== "all" && school.control !== filters.control) return false;
    if (filters.region !== "all" && school.region !== filters.region) return false;
    if (filters.testPolicy !== "all" && school.testPolicySignal !== filters.testPolicy) return false;
    if (filters.currentOnly && school.yearStart !== latestYear) return false;
    if (filters.carnegie !== "all" && school.carnegieBucket !== filters.carnegie) return false;
    if (filters.admitRate === "under_25" && !((school.acceptanceRate ?? 1) < 0.25)) return false;
    if (
      filters.admitRate === "25_50" &&
      !((school.acceptanceRate ?? 0) >= 0.25 && (school.acceptanceRate ?? 1) < 0.5)
    ) {
      return false;
    }
    if (filters.admitRate === "50_plus" && !((school.acceptanceRate ?? 0) >= 0.5)) return false;
    return true;
  });
}

export function rankMatchSchools(
  profile: StudentProfile,
  schools: MatchBuilderSchool[],
  filters: MatchFilters = DEFAULT_MATCH_FILTERS,
): RankedMatchSchool[] {
  return applyMatchFilters(schools, filters)
    .map((school) => {
      const result = scorePosition(profile, school);
      const bestPercentile = Math.max(result.satPercentile ?? -1, result.actPercentile ?? -1);
      const normalizedBestPercentile = bestPercentile < 0 ? null : bestPercentile;
      const admitBonus = (school.acceptanceRate ?? 0) * 25;
      const gpaTiebreaker =
        profile.gpa != null && school.avgHsGpa != null
          ? Math.max(-2, Math.min(2, (profile.gpa - school.avgHsGpa) * 2))
          : 0;
      return {
        ...school,
        result,
        bestPercentile: normalizedBestPercentile,
        rankScore: (normalizedBestPercentile ?? 0) + admitBonus + gpaTiebreaker,
      };
    })
    .sort((a, b) => {
      const tierDelta = TIER_ORDER[a.result.tier] - TIER_ORDER[b.result.tier];
      if (tierDelta !== 0) return tierDelta;
      if (filters.sort === "admit_rate") {
        const admitDelta = (b.acceptanceRate ?? -1) - (a.acceptanceRate ?? -1);
        if (admitDelta !== 0) return admitDelta;
      }
      if (filters.sort === "name") {
        return a.schoolName.localeCompare(b.schoolName);
      }
      const scoreDelta = b.rankScore - a.rankScore;
      if (scoreDelta !== 0) return scoreDelta;
      return a.schoolName.localeCompare(b.schoolName);
    });
}

export function groupRankedSchools(rows: RankedMatchSchool[]): Record<Tier, RankedMatchSchool[]> {
  return rows.reduce(
    (groups, row) => {
      groups[row.result.tier].push(row);
      return groups;
    },
    {
      likely: [],
      strong_fit: [],
      possible: [],
      unlikely: [],
      long_shot: [],
      unknown: [],
    } as Record<Tier, RankedMatchSchool[]>,
  );
}

function csvValue(value: string | number | null | undefined): string {
  if (value == null) return "";
  const text = String(value);
  if (!/[",\n]/.test(text)) return text;
  return `"${text.replace(/"/g, '""')}"`;
}

export function rankedSchoolsCsv(rows: RankedMatchSchool[]): string {
  const header = [
    "school_name",
    "school_url",
    "tier",
    "best_percentile",
    "admit_rate",
    "cds_year",
    "source_pdf_url",
  ];
  const body = rows.map((row) => [
    row.schoolName,
    row.schoolUrl,
    row.result.tier,
    row.bestPercentile,
    row.acceptanceRate == null ? null : Number((row.acceptanceRate * 100).toFixed(1)),
    row.cdsYear,
    row.archiveUrl,
  ]);

  return [header, ...body].map((line) => line.map(csvValue).join(",")).join("\n");
}
