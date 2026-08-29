export type AlignmentGapRow = {
  schoolId: string;
  schoolName: string;
  cdsYear: string;
  satCompositeP50: number;
  earnings10yrMedian: number;
  medianDebtCompleters: number;
  medianDebtMonthlyPayment: number;
  avgNetPrice: number;
  endowmentEnd: number;
  instructionalExpenditureFte: number;
  undergraduateEnrollment: number;
  burden: number;
  gap: number;
  endowmentPerStudent: number;
  instructionShare: number;
};

export type AlignmentGapMeritRow = {
  schoolId: string;
  schoolName: string;
  cdsYear: string;
  meritShare: number;
  avgMeritGrant: number;
  meritPerFirstYear: number;
  earnings10yrMedian: number;
  medianDebtCompleters: number;
  medianDebtMonthlyPayment: number;
  avgNetPrice: number;
  endowmentEnd: number;
  undergraduateEnrollment: number;
  burden: number;
  gap: number;
  endowmentPerStudent: number;
};

export type MeritRegion = "covers" | "constrained" | "none";

export const MERIT_SHARE_MIN = 0;
export const MERIT_SHARE_MAX = 1;
export const MERIT_GRANT_MIN = 0;
export const MERIT_GRANT_MAX = 80_000;

export type AlignmentGapQuadrant =
  | "capacity"
  | "constrained"
  | "absorbs"
  | "earnings";

export function computeBurden(
  monthlyPayment: number,
  earnings10yrMedian: number,
): number {
  if (monthlyPayment <= 0 || earnings10yrMedian <= 0) {
    throw new Error("burden requires positive monthly payment and earnings");
  }
  return (monthlyPayment * 12) / earnings10yrMedian;
}

export function computeGap(
  medianDebtCompleters: number,
  burden: number,
  medianBurden: number,
): number {
  if (medianDebtCompleters <= 0 || burden <= 0) {
    throw new Error("gap requires positive completer debt and burden");
  }
  return (medianDebtCompleters * (1 - medianBurden / burden)) / 4;
}

export function computeEndowmentPerStudent(
  endowmentEnd: number,
  undergraduateEnrollment: number,
): number {
  if (endowmentEnd <= 0 || undergraduateEnrollment <= 0) {
    throw new Error("endowment per student requires positive inputs");
  }
  return endowmentEnd / undergraduateEnrollment;
}

export function computeInstructionShare(
  instructionalExpenditureFte: number,
  avgNetPrice: number,
): number {
  if (instructionalExpenditureFte <= 0 || avgNetPrice <= 0) {
    throw new Error("instruction share requires positive inputs");
  }
  return instructionalExpenditureFte / avgNetPrice;
}

export function quadrantFor(
  gap: number,
  endowmentPerStudent: number,
  medianEndowmentPerStudent: number,
): AlignmentGapQuadrant {
  const aboveBurden = gap > 0;
  const aboveEndowment = endowmentPerStudent >= medianEndowmentPerStudent;
  if (aboveBurden && aboveEndowment) return "capacity";
  if (aboveBurden) return "constrained";
  if (aboveEndowment) return "absorbs";
  return "earnings";
}

export function median(values: readonly number[]): number {
  if (values.length === 0) throw new Error("median of empty list");
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

export function formatGapUsd(gap: number): string {
  const abs = Math.abs(Math.round(gap)).toLocaleString("en-US");
  if (gap > 0) return `+$${abs}`;
  if (gap < 0) return `−$${abs}`;
  return "$0";
}

export function formatEndowmentPerStudent(value: number): string {
  if (value >= 1_000_000) {
    const millions = value / 1_000_000;
    return `$${millions >= 10 ? millions.toFixed(1) : millions.toFixed(2)}M`;
  }
  if (value >= 1000) return `$${Math.round(value / 1000).toLocaleString("en-US")}k`;
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

export function formatInstructionShare(share: number): string {
  if (share >= 2) return `${share.toFixed(1)}× net price`;
  return `${Math.round(share * 100)}% of net price`;
}

export function meritShareInRange(share: number): boolean {
  return share >= MERIT_SHARE_MIN && share <= MERIT_SHARE_MAX;
}

export function meritGrantInRange(grant: number): boolean {
  return grant > MERIT_GRANT_MIN && grant <= MERIT_GRANT_MAX;
}

export function computeMeritPerFirstYear(
  meritShare: number,
  avgMeritGrant: number,
): number {
  if (!meritShareInRange(meritShare) || !meritGrantInRange(avgMeritGrant)) {
    throw new Error("merit spend requires a 0–1 share and a grant in (0, 80000]");
  }
  return meritShare * avgMeritGrant;
}

export function coversGap(meritPerFirstYear: number, gap: number): boolean {
  return meritPerFirstYear >= gap;
}

export function meritRegion(
  gap: number,
  meritPerFirstYear: number,
): MeritRegion {
  if (gap <= 0) return "none";
  return coversGap(meritPerFirstYear, gap) ? "covers" : "constrained";
}

export function endowmentTercile(
  endowmentPerStudent: number,
  firstBreak: number,
  secondBreak: number,
): 0 | 1 | 2 {
  if (endowmentPerStudent >= secondBreak) return 2;
  if (endowmentPerStudent >= firstBreak) return 1;
  return 0;
}

export function formatUsd(value: number): string {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}
