import type {
  EndowmentDrawRatePoint,
  EndowmentDrawRateSchool,
} from "./endowment-draw-rate-recipe-data";
import { ENDOWMENT_DRAW_RATE_SCHOOLS } from "./endowment-draw-rate-recipe-data";

export type EndowmentDrawRatePointView = {
  year: number;
  beginningValue: number | null;
  endingValue: number | null;
  spendingDistribution: number | null;
  drawRate: number | null;
  exclusionReason: string | null;
  releaseType: string;
  sourceTable: string;
};

export const ENDOWMENT_DRAW_RATE_BUCKET_THRESHOLDS = [0.05, 0.07, 0.15] as const;

export type EndowmentDrawRateBucketThreshold =
  (typeof ENDOWMENT_DRAW_RATE_BUCKET_THRESHOLDS)[number];

export type EndowmentDrawRateBucketMember = Omit<
  EndowmentDrawRatePointView,
  "drawRate" | "exclusionReason"
> & {
  drawRate: number;
  exclusionReason: null;
  ipedsId: string;
  schoolId: string | null;
  hasCurrentSchoolPage: boolean;
  schoolName: string;
  state: string | null;
};

export const DEFAULT_ENDOWMENT_RECIPE_SCHOOL_ID: string | null = null;

export function unpackEndowmentDrawRatePoint(
  point: EndowmentDrawRatePoint,
): EndowmentDrawRatePointView {
  return {
    year: point[0],
    beginningValue: point[1],
    endingValue: point[2],
    spendingDistribution: point[3],
    drawRate: point[4],
    exclusionReason: point[5],
    releaseType: point[6],
    sourceTable: point[7],
  };
}

export function endowmentSchoolLabel(school: EndowmentDrawRateSchool): string {
  const location = school.state ? ` · ${school.state}` : "";
  return `${school.schoolName}${location} · ${school.ipedsId}`;
}

export function endowmentSchoolHistory(
  school: EndowmentDrawRateSchool,
): EndowmentDrawRatePointView[] {
  return school.history.map(unpackEndowmentDrawRatePoint).sort((a, b) => a.year - b.year);
}

export function bucketMembers(
  year: number,
  threshold: EndowmentDrawRateBucketThreshold,
): EndowmentDrawRateBucketMember[] {
  return ENDOWMENT_DRAW_RATE_SCHOOLS.flatMap((school) => {
    const sourcePoint = school.history.find((point) => point[0] === year);
    if (!sourcePoint) return [];

    const point = unpackEndowmentDrawRatePoint(sourcePoint);
    if (
      point.drawRate === null ||
      point.exclusionReason !== null ||
      point.drawRate <= threshold
    ) {
      return [];
    }

    return [{
      ...point,
      drawRate: point.drawRate,
      exclusionReason: point.exclusionReason,
      ipedsId: school.ipedsId,
      schoolId: school.schoolId,
      hasCurrentSchoolPage: school.hasCurrentSchoolPage,
      schoolName: school.schoolName,
      state: school.state,
    }];
  }).sort(
    (a, b) =>
      b.drawRate - a.drawRate ||
      a.schoolName.localeCompare(b.schoolName) ||
      a.ipedsId.localeCompare(b.ipedsId),
  );
}
