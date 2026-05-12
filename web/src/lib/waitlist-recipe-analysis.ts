import {
  WAITLIST_BUCKETS,
  WAITLIST_RECIPE_SUMMARY,
  WAITLIST_ROWS,
  type WaitlistBucketSummary,
  type WaitlistRecipeRow,
} from "@/lib/waitlist-recipe-data";

export type WaitlistBucketKey = "selectivity" | "control" | "size" | "carnegie";

export type BerkeleyWaitlistHistoryRow = {
  year: string;
  yearStart: number;
  waitListOffered: number;
  waitListAccepted: number;
  waitListAdmitted: number;
  waitListSuccessRate: number;
  sourceKind: "pdf" | "xlsx";
  archiveUrl: string;
};

export type WaitlistAnalysisSummary = {
  allVisibleRows: number;
  completeRows: number;
  analysisRows: number;
  analysisSchools: number;
  latestCompleteSchools: number;
  partialRows: number;
  reportedAnomalyRows: number;
  medianSuccessRate: number | null;
  weightedSuccessRate: number | null;
  medianOfferSuccessRate: number | null;
  zeroishRows: number;
  zeroishShare: number;
};

const WAITLIST_REPORTED_ANOMALY_RATE = 0.95;
const WAITLIST_REPORTED_ANOMALY_ACCEPTED = 100;

export const BERKELEY_WAITLIST_HISTORY: readonly BerkeleyWaitlistHistoryRow[] = [
  {
    year: "2015-16",
    yearStart: 2015,
    waitListOffered: 3760,
    waitListAccepted: 2445,
    waitListAdmitted: 1340,
    waitListSuccessRate: 1340 / 2445,
    sourceKind: "pdf",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2015-16",
  },
  {
    year: "2018-19",
    yearStart: 2018,
    waitListOffered: 7824,
    waitListAccepted: 4127,
    waitListAdmitted: 1536,
    waitListSuccessRate: 1536 / 4127,
    sourceKind: "xlsx",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2018-19",
  },
  {
    year: "2019-20",
    yearStart: 2019,
    waitListOffered: 7531,
    waitListAccepted: 3975,
    waitListAdmitted: 1098,
    waitListSuccessRate: 1098 / 3975,
    sourceKind: "pdf",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2019-20",
  },
  {
    year: "2020-21",
    yearStart: 2020,
    waitListOffered: 8753,
    waitListAccepted: 5043,
    waitListAdmitted: 1651,
    waitListSuccessRate: 1651 / 5043,
    sourceKind: "xlsx",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2020-21",
  },
  {
    year: "2021-22",
    yearStart: 2021,
    waitListOffered: 11725,
    waitListAccepted: 6871,
    waitListAdmitted: 359,
    waitListSuccessRate: 359 / 6871,
    sourceKind: "xlsx",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2021-22",
  },
  {
    year: "2022-23",
    yearStart: 2022,
    waitListOffered: 8456,
    waitListAccepted: 4655,
    waitListAdmitted: 44,
    waitListSuccessRate: 44 / 4655,
    sourceKind: "xlsx",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2022-23",
  },
  {
    year: "2023-24",
    yearStart: 2023,
    waitListOffered: 7001,
    waitListAccepted: 4820,
    waitListAdmitted: 1191,
    waitListSuccessRate: 1191 / 4820,
    sourceKind: "pdf",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2023-24",
  },
  {
    year: "2024-25",
    yearStart: 2024,
    waitListOffered: 10894,
    waitListAccepted: 7853,
    waitListAdmitted: 26,
    waitListSuccessRate: 26 / 7853,
    sourceKind: "xlsx",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2024-25",
  },
  {
    year: "2025-26",
    yearStart: 2025,
    waitListOffered: 9102,
    waitListAccepted: 6479,
    waitListAdmitted: 1,
    waitListSuccessRate: 1 / 6479,
    sourceKind: "xlsx",
    archiveUrl: "https://www.collegedata.fyi/schools/uc-berkeley/2025-26",
  },
];

function median(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function round4(value: number | null): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  return Math.round(value * 10000) / 10000;
}

export function isLikelyWaitlistReportingAnomaly(row: WaitlistRecipeRow): boolean {
  return Boolean(
    row.complete &&
      row.waitListAccepted != null &&
      row.waitListAccepted >= WAITLIST_REPORTED_ANOMALY_ACCEPTED &&
      row.waitListSuccessRate != null &&
      row.waitListSuccessRate >= WAITLIST_REPORTED_ANOMALY_RATE,
  );
}

function uniqueBy<T>(items: readonly T[], keyFor: (item: T) => string): T[] {
  const seen = new Set<string>();
  const unique: T[] = [];
  for (const item of items) {
    const key = keyFor(item);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
  }
  return unique;
}

const COMPLETE_SCHOOL_YEAR_ROWS = uniqueBy(
  WAITLIST_ROWS.filter(
    (row) => row.complete && row.waitListAccepted != null && row.waitListAccepted > 0,
  ),
  (row) => `${row.schoolId}:${row.year}`,
);

export const WAITLIST_REPORTED_ANOMALY_ROWS = COMPLETE_SCHOOL_YEAR_ROWS.filter(
  isLikelyWaitlistReportingAnomaly,
);

export const WAITLIST_ANALYSIS_ROWS = COMPLETE_SCHOOL_YEAR_ROWS.filter(
  (row) => !isLikelyWaitlistReportingAnomaly(row),
);

function summarizeRows(rows: readonly WaitlistRecipeRow[]): Omit<
  WaitlistAnalysisSummary,
  "allVisibleRows" | "completeRows" | "analysisRows" | "analysisSchools" | "latestCompleteSchools" | "partialRows" | "reportedAnomalyRows"
> {
  const successRates = rows
    .map((row) => row.waitListSuccessRate)
    .filter((value): value is number => value != null && Number.isFinite(value));
  const offerSuccessRates = rows
    .map((row) => row.waitListOfferSuccessRate)
    .filter((value): value is number => value != null && Number.isFinite(value));
  const accepted = rows.reduce((sum, row) => sum + (row.waitListAccepted ?? 0), 0);
  const admitted = rows.reduce((sum, row) => sum + (row.waitListAdmitted ?? 0), 0);
  const zeroishRows = rows.filter(
    (row) => row.waitListSuccessRate != null && row.waitListSuccessRate < 0.02,
  ).length;

  return {
    medianSuccessRate: round4(median(successRates)),
    weightedSuccessRate: accepted > 0 ? round4(admitted / accepted) : null,
    medianOfferSuccessRate: round4(median(offerSuccessRates)),
    zeroishRows,
    zeroishShare: rows.length > 0 ? round4(zeroishRows / rows.length) ?? 0 : 0,
  };
}

export const WAITLIST_ANALYSIS_SUMMARY: WaitlistAnalysisSummary = {
  allVisibleRows: WAITLIST_RECIPE_SUMMARY.allVisibleRows,
  completeRows: WAITLIST_RECIPE_SUMMARY.completeRows,
  analysisRows: WAITLIST_ANALYSIS_ROWS.length,
  analysisSchools: new Set(WAITLIST_ANALYSIS_ROWS.map((row) => row.schoolId)).size,
  latestCompleteSchools: new Set(WAITLIST_ANALYSIS_ROWS.map((row) => row.schoolId)).size,
  partialRows: WAITLIST_RECIPE_SUMMARY.partialRows,
  reportedAnomalyRows: WAITLIST_REPORTED_ANOMALY_ROWS.length,
  ...summarizeRows(WAITLIST_ANALYSIS_ROWS),
};

export function summarizeWaitlistBuckets(
  rows: readonly WaitlistRecipeRow[],
  bucketKey: WaitlistBucketKey,
): WaitlistBucketSummary[] {
  const labels = WAITLIST_BUCKETS[bucketKey].map((bucket) => bucket.label);

  return labels.map((label) => {
    const bucketRows = rows.filter((row) => row[bucketKey] === label);
    const accepted = bucketRows.reduce((sum, row) => sum + (row.waitListAccepted ?? 0), 0);
    const admitted = bucketRows.reduce((sum, row) => sum + (row.waitListAdmitted ?? 0), 0);
    const bucketSummary = summarizeRows(bucketRows);

    return {
      label,
      rows: bucketRows.length,
      schools: new Set(bucketRows.map((row) => row.schoolId)).size,
      medianSuccessRate: bucketSummary.medianSuccessRate,
      weightedSuccessRate: accepted > 0 ? round4(admitted / accepted) : null,
      medianOfferSuccessRate: bucketSummary.medianOfferSuccessRate,
      zeroishShare: bucketSummary.zeroishShare,
      medianAccepted:
        median(
          bucketRows
            .map((row) => row.waitListAccepted)
            .filter((value): value is number => value != null && Number.isFinite(value)),
        ) ?? 0,
    };
  });
}
