import type {
  EndowmentDrawRatePoint,
  EndowmentDrawRateSchool,
} from "./endowment-draw-rate-recipe-data";

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
