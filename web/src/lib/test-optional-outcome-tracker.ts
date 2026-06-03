import { cache } from "react";
import { supabase } from "./supabase";

type UntypedSupabase = {
  from: (table: string) => any;
};

type Panel = "uc" | "comparison";
type OutcomeFieldKey =
  | "retention_rate_full_time"
  | "bachelor_6yr_grad_rate"
  | "transfer_out_rate_total";

type PanelSchool = {
  panel: Panel;
  schoolId: string;
  schoolName: string;
  ipedsId: string;
};

type DirectoryRow = {
  school_id: string | null;
  school_name: string | null;
  ipeds_id: string | null;
};

type BrowserRow = {
  school_id: string | null;
  school_name: string | null;
  canonical_year: string | null;
  year_start: number | null;
  sat_submit_rate: unknown;
  act_submit_rate: unknown;
  sat_composite_p25: unknown;
  sat_composite_p50: unknown;
  sat_composite_p75: unknown;
  act_composite_p25: unknown;
  act_composite_p50: unknown;
  act_composite_p75: unknown;
  archive_url: string | null;
  data_quality_flag: string | null;
};

type IpedsFactRow = {
  ipeds_id: string | null;
  data_year: number | null;
  field_key: string | null;
  value_numeric: unknown;
  source_table: string | null;
  source_variable: string | null;
  release_type: string | null;
};

type ScorecardRow = {
  ipeds_id: string | null;
  scorecard_data_year: string | null;
  retention_rate_ft: unknown;
  graduation_rate_6yr: unknown;
  transfer_out_rate: unknown;
};

type IpedsReleaseRow = {
  data_year: number | null;
  collection_year: string | null;
  release_type: string | null;
  release_date: string | null;
};

export type TestingObservabilityRow = {
  panel: Panel;
  schoolId: string;
  schoolName: string;
  ipedsId: string;
  latestCdsYear: string | null;
  archiveUrl: string | null;
  satSubmitRate: number | null;
  actSubmitRate: number | null;
  satCompositeP25: number | null;
  satCompositeP50: number | null;
  satCompositeP75: number | null;
  actCompositeP25: number | null;
  actCompositeP50: number | null;
  actCompositeP75: number | null;
  scoreBandStatus: "reported" | "submit-rates-only" | "not-reported" | "no-cds-row";
  note: string;
  dataQualityFlag: string | null;
};

export type OutcomeValue = {
  value: number | null;
  sourceTable: string | null;
  sourceVariable: string | null;
  releaseType: string | null;
};

export type UcOutcomeRow = {
  schoolId: string;
  schoolName: string;
  ipedsId: string;
  retentionByYear: Record<number, OutcomeValue>;
  graduationByYear: Record<number, OutcomeValue>;
  transferOutByYear: Record<number, OutcomeValue>;
  retentionDelta: number | null;
  latestRetention: number | null;
  latestGraduation: number | null;
  latestTransferOut: number | null;
  latestDataYear: number | null;
  scorecard: {
    dataYear: string | null;
    retentionRateFt: number | null;
    graduationRate6yr: number | null;
    transferOutRate: number | null;
  } | null;
};

export type TestOptionalOutcomeTrackerData = {
  generatedAt: string;
  methodology: {
    baselineDataYear: number;
    latestIpedsDataYear: number | null;
    latestIpedsRelease: IpedsReleaseRow | null;
    ucPanelSize: number;
    comparisonPanelSize: number;
    notes: string[];
  };
  years: number[];
  testing: TestingObservabilityRow[];
  outcomes: UcOutcomeRow[];
  summary: {
    ucCampusesWithRetentionBaseline: number;
    ucCampusesWithLatestRetention: number;
    latestRetentionMedian: number | null;
    retentionDeltaMedian: number | null;
    ucTestingRowsWithoutScoreBands: number;
  };
};

const BASELINE_DATA_YEAR = 2019;

const UC_PANEL: PanelSchool[] = [
  {
    panel: "uc",
    schoolId: "uc-berkeley",
    schoolName: "University of California-Berkeley",
    ipedsId: "110635",
  },
  {
    panel: "uc",
    schoolId: "uc-davis",
    schoolName: "University of California-Davis",
    ipedsId: "110644",
  },
  {
    panel: "uc",
    schoolId: "uc-irvine",
    schoolName: "University of California-Irvine",
    ipedsId: "110653",
  },
  {
    panel: "uc",
    schoolId: "ucla",
    schoolName: "University of California-Los Angeles",
    ipedsId: "110662",
  },
  {
    panel: "uc",
    schoolId: "university-of-california-merced",
    schoolName: "University of California-Merced",
    ipedsId: "445188",
  },
  {
    panel: "uc",
    schoolId: "university-of-california-riverside",
    schoolName: "University of California-Riverside",
    ipedsId: "110671",
  },
  {
    panel: "uc",
    schoolId: "uc-san-diego",
    schoolName: "University of California-San Diego",
    ipedsId: "110680",
  },
  {
    panel: "uc",
    schoolId: "uc-santa-barbara",
    schoolName: "University of California-Santa Barbara",
    ipedsId: "110705",
  },
  {
    panel: "uc",
    schoolId: "university-of-california-santa-cruz",
    schoolName: "University of California-Santa Cruz",
    ipedsId: "110714",
  },
];

const COMPARISON_PANEL: PanelSchool[] = [
  {
    panel: "comparison",
    schoolId: "mit",
    schoolName: "Massachusetts Institute of Technology",
    ipedsId: "166683",
  },
  {
    panel: "comparison",
    schoolId: "dartmouth",
    schoolName: "Dartmouth College",
    ipedsId: "182670",
  },
  {
    panel: "comparison",
    schoolId: "yale",
    schoolName: "Yale University",
    ipedsId: "130794",
  },
];

const ALL_PANEL_SCHOOLS = [...UC_PANEL, ...COMPARISON_PANEL];
const OUTCOME_FIELD_KEYS: OutcomeFieldKey[] = [
  "retention_rate_full_time",
  "bachelor_6yr_grad_rate",
  "transfer_out_rate_total",
];

function numberOrNull(value: unknown): number | null {
  if (value == null || value === "") return null;
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function median(values: Array<number | null | undefined>): number | null {
  const clean = values
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
    .sort((a, b) => a - b);
  if (clean.length === 0) return null;
  const middle = Math.floor(clean.length / 2);
  if (clean.length % 2) return clean[middle];
  return (clean[middle - 1] + clean[middle]) / 2;
}

function latestBrowserRows(rows: BrowserRow[]): Map<string, BrowserRow> {
  const latest = new Map<string, BrowserRow>();
  for (const row of rows) {
    if (!row.school_id) continue;
    const current = latest.get(row.school_id);
    const rowYear = numberOrNull(row.year_start) ?? 0;
    const currentYear = numberOrNull(current?.year_start) ?? 0;
    if (!current || rowYear > currentYear) latest.set(row.school_id, row);
  }
  return latest;
}

function scoreBandStatus(row: BrowserRow | undefined): TestingObservabilityRow["scoreBandStatus"] {
  if (!row) return "no-cds-row";
  const hasBands =
    numberOrNull(row.sat_composite_p25) != null ||
    numberOrNull(row.sat_composite_p50) != null ||
    numberOrNull(row.sat_composite_p75) != null ||
    numberOrNull(row.act_composite_p25) != null ||
    numberOrNull(row.act_composite_p50) != null ||
    numberOrNull(row.act_composite_p75) != null;
  if (hasBands) return "reported";
  const hasSubmitRates =
    numberOrNull(row.sat_submit_rate) != null || numberOrNull(row.act_submit_rate) != null;
  return hasSubmitRates ? "submit-rates-only" : "not-reported";
}

function observabilityNote(
  panel: Panel,
  status: TestingObservabilityRow["scoreBandStatus"],
): string {
  if (status === "no-cds-row") return "No current primary CDS browser row in the public serving table.";
  if (status === "reported") return "CDS reports score bands in the current serving row.";
  if (status === "submit-rates-only") return "CDS reports submit rates but not score bands in the current serving row.";
  if (panel === "uc") {
    return "CDS row exists, but SAT/ACT submit rates and bands are not reported in the serving row.";
  }
  return "CDS row exists, but SAT/ACT score fields are not reported in the serving row.";
}

function valueForYear(
  facts: IpedsFactRow[],
  ipedsId: string,
  fieldKey: OutcomeFieldKey,
  dataYear: number,
): OutcomeValue {
  const row = facts.find(
    (fact) =>
      fact.ipeds_id === ipedsId &&
      fact.field_key === fieldKey &&
      fact.data_year === dataYear,
  );
  return {
    value: numberOrNull(row?.value_numeric),
    sourceTable: row?.source_table ?? null,
    sourceVariable: row?.source_variable ?? null,
    releaseType: row?.release_type ?? null,
  };
}

function normalizeName(
  school: PanelSchool,
  directory: Map<string, DirectoryRow>,
  browser: BrowserRow | undefined,
): string {
  return browser?.school_name ?? directory.get(school.schoolId)?.school_name ?? school.schoolName;
}

async function fetchTrackerDataUncached(): Promise<TestOptionalOutcomeTrackerData> {
  const client = supabase as unknown as UntypedSupabase;
  const schoolIds = ALL_PANEL_SCHOOLS.map((school) => school.schoolId);
  const ucIpedsIds = UC_PANEL.map((school) => school.ipedsId);

  const [
    directoryResult,
    browserResult,
    factsResult,
    scorecardResult,
    releaseResult,
  ] = await Promise.all([
    client
      .from("institution_directory")
      .select("school_id,school_name,ipeds_id")
      .in("school_id", schoolIds),
    client
      .from("school_browser_rows")
      .select(
        "school_id,school_name,canonical_year,year_start,sat_submit_rate,act_submit_rate,sat_composite_p25,sat_composite_p50,sat_composite_p75,act_composite_p25,act_composite_p50,act_composite_p75,archive_url,data_quality_flag",
      )
      .in("school_id", schoolIds)
      .is("sub_institutional", null)
      .gte("year_start", 2024)
      .order("school_id", { ascending: true })
      .order("year_start", { ascending: false }),
    client
      .from("ipeds_facts")
      .select(
        "ipeds_id,data_year,field_key,value_numeric,source_table,source_variable,release_type",
      )
      .in("ipeds_id", ucIpedsIds)
      .in("field_key", OUTCOME_FIELD_KEYS)
      .gte("data_year", BASELINE_DATA_YEAR)
      .order("ipeds_id", { ascending: true })
      .order("field_key", { ascending: true })
      .order("data_year", { ascending: true }),
    client
      .from("scorecard_summary")
      .select("ipeds_id,scorecard_data_year,retention_rate_ft,graduation_rate_6yr,transfer_out_rate")
      .in("ipeds_id", ucIpedsIds),
    client
      .from("ipeds_releases")
      .select("data_year,collection_year,release_type,release_date")
      .order("data_year", { ascending: false })
      .order("release_date", { ascending: false, nullsFirst: false })
      .limit(1)
      .maybeSingle(),
  ]);

  if (directoryResult.error) {
    throw new Error(`test optional tracker directory query failed: ${directoryResult.error.message}`);
  }
  if (browserResult.error) {
    throw new Error(`test optional tracker browser query failed: ${browserResult.error.message}`);
  }
  if (factsResult.error) {
    throw new Error(`test optional tracker IPEDS query failed: ${factsResult.error.message}`);
  }
  if (scorecardResult.error) {
    throw new Error(`test optional tracker Scorecard query failed: ${scorecardResult.error.message}`);
  }
  if (releaseResult.error) {
    throw new Error(`test optional tracker release query failed: ${releaseResult.error.message}`);
  }

  const directoryBySchool = new Map(
    ((directoryResult.data ?? []) as DirectoryRow[])
      .filter((row): row is DirectoryRow & { school_id: string } => Boolean(row.school_id))
      .map((row) => [row.school_id, row]),
  );
  const latestBrowserBySchool = latestBrowserRows((browserResult.data ?? []) as BrowserRow[]);
  const facts = (factsResult.data ?? []) as IpedsFactRow[];
  const scorecardByIpeds = new Map(
    ((scorecardResult.data ?? []) as ScorecardRow[])
      .filter((row): row is ScorecardRow & { ipeds_id: string } => Boolean(row.ipeds_id))
      .map((row) => [row.ipeds_id, row]),
  );

  const years = Array.from(
    new Set(
      facts
        .map((row) => row.data_year)
        .filter((year): year is number => typeof year === "number" && year >= BASELINE_DATA_YEAR),
    ),
  ).sort((a, b) => a - b);
  const latestIpedsDataYear = years.at(-1) ?? null;

  const testing = ALL_PANEL_SCHOOLS.map((school): TestingObservabilityRow => {
    const browser = latestBrowserBySchool.get(school.schoolId);
    const status = scoreBandStatus(browser);
    return {
      panel: school.panel,
      schoolId: school.schoolId,
      schoolName: normalizeName(school, directoryBySchool, browser),
      ipedsId: directoryBySchool.get(school.schoolId)?.ipeds_id ?? school.ipedsId,
      latestCdsYear: browser?.canonical_year ?? null,
      archiveUrl: browser?.archive_url ?? null,
      satSubmitRate: numberOrNull(browser?.sat_submit_rate),
      actSubmitRate: numberOrNull(browser?.act_submit_rate),
      satCompositeP25: numberOrNull(browser?.sat_composite_p25),
      satCompositeP50: numberOrNull(browser?.sat_composite_p50),
      satCompositeP75: numberOrNull(browser?.sat_composite_p75),
      actCompositeP25: numberOrNull(browser?.act_composite_p25),
      actCompositeP50: numberOrNull(browser?.act_composite_p50),
      actCompositeP75: numberOrNull(browser?.act_composite_p75),
      scoreBandStatus: status,
      note: observabilityNote(school.panel, status),
      dataQualityFlag: browser?.data_quality_flag ?? null,
    };
  });

  const outcomes = UC_PANEL.map((school): UcOutcomeRow => {
    const browser = latestBrowserBySchool.get(school.schoolId);
    const schoolName = normalizeName(school, directoryBySchool, browser);
    const retentionByYear: Record<number, OutcomeValue> = {};
    const graduationByYear: Record<number, OutcomeValue> = {};
    const transferOutByYear: Record<number, OutcomeValue> = {};
    for (const year of years) {
      retentionByYear[year] = valueForYear(facts, school.ipedsId, "retention_rate_full_time", year);
      graduationByYear[year] = valueForYear(facts, school.ipedsId, "bachelor_6yr_grad_rate", year);
      transferOutByYear[year] = valueForYear(facts, school.ipedsId, "transfer_out_rate_total", year);
    }
    const latestRetention =
      latestIpedsDataYear == null ? null : retentionByYear[latestIpedsDataYear]?.value ?? null;
    const baselineRetention = retentionByYear[BASELINE_DATA_YEAR]?.value ?? null;
    const latestGraduation =
      latestIpedsDataYear == null ? null : graduationByYear[latestIpedsDataYear]?.value ?? null;
    const latestTransferOut =
      latestIpedsDataYear == null ? null : transferOutByYear[latestIpedsDataYear]?.value ?? null;
    const scorecard = scorecardByIpeds.get(school.ipedsId);

    return {
      schoolId: school.schoolId,
      schoolName,
      ipedsId: school.ipedsId,
      retentionByYear,
      graduationByYear,
      transferOutByYear,
      retentionDelta:
        latestRetention == null || baselineRetention == null
          ? null
          : latestRetention - baselineRetention,
      latestRetention,
      latestGraduation,
      latestTransferOut,
      latestDataYear: latestIpedsDataYear,
      scorecard: scorecard
        ? {
            dataYear: scorecard.scorecard_data_year,
            retentionRateFt: numberOrNull(scorecard.retention_rate_ft),
            graduationRate6yr: numberOrNull(scorecard.graduation_rate_6yr),
            transferOutRate: numberOrNull(scorecard.transfer_out_rate),
          }
        : null,
    };
  });

  return {
    generatedAt: new Date().toISOString(),
    methodology: {
      baselineDataYear: BASELINE_DATA_YEAR,
      latestIpedsDataYear,
      latestIpedsRelease: (releaseResult.data ?? null) as IpedsReleaseRow | null,
      ucPanelSize: UC_PANEL.length,
      comparisonPanelSize: COMPARISON_PANEL.length,
      notes: [
        "Formal test-policy labels are not inferred from CDS submit rates.",
        "UC outcome rows use undergraduate UC campuses only; UC San Francisco and UC Law SF are excluded from the panel.",
        "IPEDS percentages are institution-level values. They are not course-level or major-level readiness measures.",
        "Completion and transfer-out rates are lagged entering-cohort outcomes.",
      ],
    },
    years,
    testing,
    outcomes,
    summary: {
      ucCampusesWithRetentionBaseline: outcomes.filter(
        (row) => row.retentionByYear[BASELINE_DATA_YEAR]?.value != null,
      ).length,
      ucCampusesWithLatestRetention: outcomes.filter((row) => row.latestRetention != null).length,
      latestRetentionMedian: median(outcomes.map((row) => row.latestRetention)),
      retentionDeltaMedian: median(outcomes.map((row) => row.retentionDelta)),
      ucTestingRowsWithoutScoreBands: testing.filter(
        (row) => row.panel === "uc" && row.scoreBandStatus !== "reported",
      ).length,
    },
  };
}

export const fetchTestOptionalOutcomeTracker = cache(fetchTrackerDataUncached);

function csvEscape(value: string | number | null | undefined): string {
  if (value == null) return "";
  const text = String(value);
  if (!/[",\n\r]/.test(text)) return text;
  return `"${text.replace(/"/g, '""')}"`;
}

export function testOptionalOutcomeTrackerCsv(data: TestOptionalOutcomeTrackerData): string {
  const headers = [
    "panel",
    "school_id",
    "school_name",
    "ipeds_id",
    "latest_cds_year",
    "score_band_status",
    "sat_submit_rate",
    "act_submit_rate",
    "sat_composite_p25",
    "sat_composite_p50",
    "sat_composite_p75",
    "act_composite_p25",
    "act_composite_p50",
    "act_composite_p75",
    "retention_2019",
    `retention_${data.methodology.latestIpedsDataYear ?? "latest"}`,
    "retention_delta_points",
    `bachelor_6yr_grad_rate_${data.methodology.latestIpedsDataYear ?? "latest"}`,
    `transfer_out_rate_total_${data.methodology.latestIpedsDataYear ?? "latest"}`,
    "archive_url",
    "note",
  ];

  const outcomeBySchool = new Map(data.outcomes.map((row) => [row.schoolId, row]));
  const rows = data.testing.map((testing) => {
    const outcome = outcomeBySchool.get(testing.schoolId);
    const latestYear = data.methodology.latestIpedsDataYear;
    return [
      testing.panel,
      testing.schoolId,
      testing.schoolName,
      testing.ipedsId,
      testing.latestCdsYear,
      testing.scoreBandStatus,
      testing.satSubmitRate,
      testing.actSubmitRate,
      testing.satCompositeP25,
      testing.satCompositeP50,
      testing.satCompositeP75,
      testing.actCompositeP25,
      testing.actCompositeP50,
      testing.actCompositeP75,
      outcome?.retentionByYear[BASELINE_DATA_YEAR]?.value,
      latestYear == null ? null : outcome?.retentionByYear[latestYear]?.value,
      outcome?.retentionDelta,
      latestYear == null ? null : outcome?.graduationByYear[latestYear]?.value,
      latestYear == null ? null : outcome?.transferOutByYear[latestYear]?.value,
      testing.archiveUrl,
      testing.note,
    ];
  });

  return [headers, ...rows]
    .map((row) => row.map((value) => csvEscape(value)).join(","))
    .join("\n");
}
