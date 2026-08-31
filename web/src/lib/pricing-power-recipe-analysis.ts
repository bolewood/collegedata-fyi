export type PricingPowerCdsFields = {
  cdsAcceptanceRate: number;
  cdsYieldRate: number;
  cdsYear: string;
};

export type PricingPowerPanelBFields = {
  burden: number;
  medianDebt: number;
  monthlyPayment: number;
  earnings10yr: number;
  avgNetPrice: number;
  instructionFte: number;
  instructionNetPriceRatio: number;
};

export type PricingPowerSchool = {
  schoolId: string;
  name: string;
  ipedsId: string;
  applied: number;
  admitted: number;
  enrolled: number;
  acceptanceRate: number;
  yieldRate: number;
} & Partial<PricingPowerCdsFields> &
  Partial<PricingPowerPanelBFields>;

export type PricingPowerPanelBSchool = PricingPowerSchool & PricingPowerPanelBFields;

export type PanelAQuadrant =
  | "lowerAcceptanceHigherYield"
  | "higherAcceptanceHigherYield"
  | "lowerAcceptanceLowerYield"
  | "higherAcceptanceLowerYield";

export type PanelBQuadrant =
  | "higherYieldHigherBurden"
  | "lowerYieldHigherBurden"
  | "higherYieldLowerBurden"
  | "lowerYieldLowerBurden";

export type PricingPowerExclusions = {
  missingZeroCounts: number;
  admittedGtApplied: number;
  enrolledGtAdmitted: number;
  outOfScope: number;
  missingNonpositiveScorecard: number;
};

export type PricingPowerJoinMisses = {
  directory: number;
  scorecard: number;
};

export type PricingPowerMeta = {
  generatedAt: string;
  sourceApiUrl: string;
  ipedsCycle: string;
  scorecardYears: readonly string[];
  panelACount: number;
  panelBCount: number;
  medianAcceptance: number;
  medianYield: number;
  medianYieldB: number;
  medianBurden: number;
  quadrantsA: Record<PanelAQuadrant, number>;
  quadrantsB: Record<PanelBQuadrant, number>;
  cdsCrosscheckCount: number;
  cdsAttachedCount: number;
  annotationSchoolId: string;
  annotationIpedsId: string;
  exclusions: PricingPowerExclusions;
  joinMisses: PricingPowerJoinMisses;
};

export const PRICING_POWER_ANNOTATION_SCHOOL_ID = "syracuse-university" as const;
export const PRICING_POWER_ANNOTATION_IPEDS_ID = "196413" as const;

export function computeAcceptanceRate(admitted: number, applied: number): number {
  if (applied <= 0) {
    throw new Error("acceptance rate requires a positive applicant count");
  }
  return admitted / applied;
}

export function computeYieldRate(enrolled: number, admitted: number): number {
  if (admitted <= 0) {
    throw new Error("yield rate requires a positive admitted count");
  }
  return enrolled / admitted;
}

export function computeBurden(monthlyPayment: number, earnings10yr: number): number {
  if (monthlyPayment <= 0 || earnings10yr <= 0) {
    throw new Error("burden requires positive monthly payment and earnings");
  }
  return (monthlyPayment * 12) / earnings10yr;
}

export function computeInstructionNetPriceRatio(
  instructionFte: number,
  avgNetPrice: number,
): number {
  if (instructionFte <= 0 || avgNetPrice <= 0) {
    throw new Error("instruction/net-price ratio requires positive inputs");
  }
  return instructionFte / avgNetPrice;
}

export function isPanelBSchool(row: PricingPowerSchool): row is PricingPowerPanelBSchool {
  return (
    row.burden != null &&
    row.medianDebt != null &&
    row.monthlyPayment != null &&
    row.earnings10yr != null &&
    row.avgNetPrice != null &&
    row.instructionFte != null &&
    row.instructionNetPriceRatio != null
  );
}

export function panelBSchools(
  schools: readonly PricingPowerSchool[],
): PricingPowerPanelBSchool[] {
  return schools.filter(isPanelBSchool);
}

export function panelAQuadrant(
  acceptanceRate: number,
  yieldRate: number,
  medianAcceptance: number,
  medianYield: number,
): PanelAQuadrant {
  const lowerAcceptance = acceptanceRate < medianAcceptance;
  const higherYield = yieldRate >= medianYield;
  if (lowerAcceptance && higherYield) return "lowerAcceptanceHigherYield";
  if (!lowerAcceptance && higherYield) return "higherAcceptanceHigherYield";
  if (lowerAcceptance && !higherYield) return "lowerAcceptanceLowerYield";
  return "higherAcceptanceLowerYield";
}

export function panelBQuadrant(
  yieldRate: number,
  burden: number,
  medianYieldB: number,
  medianBurden: number,
): PanelBQuadrant {
  const higherYield = yieldRate >= medianYieldB;
  const higherBurden = burden >= medianBurden;
  if (higherYield && higherBurden) return "higherYieldHigherBurden";
  if (!higherYield && higherBurden) return "lowerYieldHigherBurden";
  if (higherYield && !higherBurden) return "higherYieldLowerBurden";
  return "lowerYieldLowerBurden";
}

export function median(values: readonly number[]): number {
  if (values.length === 0) throw new Error("median of empty list");
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

export function formatRatePercent(rate: number, digits = 1): string {
  return `${(rate * 100).toFixed(digits)}%`;
}

export function formatBurdenPercent(burden: number, digits = 2): string {
  return `${(burden * 100).toFixed(digits)}%`;
}

export function formatUsd(value: number): string {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

export function formatUsdCents(value: number): string {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatInstructionRatio(ratio: number): string {
  if (ratio >= 2) return `${ratio.toFixed(1)}× net price`;
  return `${Math.round(ratio * 100)}% of net price`;
}
