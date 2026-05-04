export type StudentProfile = {
  sat?: number;
  act?: number;
  gpa?: number;
  gpaScale?: "unweighted_4" | "weighted" | "unknown";
};

export type SchoolAcademicProfile = {
  schoolId: string;
  schoolName: string;
  cdsYear: string;
  acceptanceRate: number | null;
  satSubmitRate: number | null;
  actSubmitRate: number | null;
  satCompositeP25: number | null;
  satCompositeP50: number | null;
  satCompositeP75: number | null;
  actCompositeP25: number | null;
  actCompositeP50: number | null;
  actCompositeP75: number | null;
  avgHsGpa: number | null;
  hsGpaSubmitRate: number | null;
  dataQualityFlag: string | null;
};

export type Tier =
  | "likely"
  | "strong_fit"
  | "possible"
  | "unlikely"
  | "long_shot"
  | "unknown";

export type AcademicFit =
  | "strong_academic_fit"
  | "above_range"
  | "in_range"
  | "below_range"
  | "unknown";

export type AdmissionsOutlook =
  | "likely"
  | "possible"
  | "reach"
  | "high_reach"
  | "unknown";

export type Caveat =
  | "no_sat_data"
  | "no_act_data"
  | "low_sat_submit_rate"
  | "no_test_data"
  | "stale_cds"
  | "student_not_submitting"
  | "data_incomplete"
  | "no_admit_rate"
  | "sub_15_admit_rate_suppression";

export type PositionResult = {
  satPercentile: number | null;
  actPercentile: number | null;
  tier: Tier;
  academicFit: AcademicFit;
  admissionsOutlook: AdmissionsOutlook;
  caveats: Caveat[];
  cdsYear: string;
  positionalSentence: string;
};

const LOW_SUBMIT_RATE = 0.5;
const STALE_CDS_YEAR_AGE = 3;

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function hasMonotonicAnchors(
  p25: number | null,
  p50: number | null,
  p75: number | null,
): p25 is number {
  return (
    isFiniteNumber(p25) &&
    isFiniteNumber(p50) &&
    isFiniteNumber(p75) &&
    p25 <= p50 &&
    p50 <= p75 &&
    p25 < p75
  );
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function cleanScore(value: number | undefined, min: number, max: number): number | null {
  if (!isFiniteNumber(value)) return null;
  if (value < min || value > max) return null;
  return value;
}

export function interpolatePercentile(
  score: number,
  p25: number,
  p50: number,
  p75: number,
): number {
  if (!isFiniteNumber(score) || p25 > p50 || p50 > p75 || p25 === p75) {
    return Number.NaN;
  }

  if (score <= p25) {
    const span = Math.max(1, p50 - p25);
    return clamp(25 - ((p25 - score) / span) * 25, 5, 25);
  }
  if (score <= p50) {
    const span = Math.max(1, p50 - p25);
    return clamp(25 + ((score - p25) / span) * 25, 25, 50);
  }
  if (score <= p75) {
    const span = Math.max(1, p75 - p50);
    return clamp(50 + ((score - p50) / span) * 25, 50, 75);
  }

  const span = Math.max(1, p75 - p50);
  return clamp(75 + ((score - p75) / span) * 25, 75, 95);
}

export function classifyTier(
  satPct: number | null,
  actPct: number | null,
  acceptanceRate: number | null,
): Tier {
  const bestPct = Math.max(satPct ?? -1, actPct ?? -1);
  if (bestPct < 0 || acceptanceRate == null) return "unknown";

  if (acceptanceRate < 0.1) return "long_shot";
  if (bestPct < 25 && acceptanceRate < 0.25) return "long_shot";
  if (bestPct < 25) return "unlikely";
  if (acceptanceRate >= 0.5) return "likely";
  if (acceptanceRate >= 0.25) return "strong_fit";
  if (acceptanceRate >= 0.1) return "possible";
  return "unknown";
}

export function tierLabel(tier: Tier): string {
  switch (tier) {
    case "likely":
      return "Likely";
    case "strong_fit":
      return "Strong fit";
    case "possible":
      return "Possible";
    case "unlikely":
      return "Unlikely";
    case "long_shot":
      return "Long shot";
    case "unknown":
      return "Unknown";
  }
}

export function academicFitLabel(fit: AcademicFit): string {
  switch (fit) {
    case "strong_academic_fit":
      return "Strong academic fit";
    case "above_range":
      return "Above typical range";
    case "in_range":
      return "In range";
    case "below_range":
      return "Below range";
    case "unknown":
      return "Unknown";
  }
}

export function admissionsOutlookLabel(outlook: AdmissionsOutlook): string {
  switch (outlook) {
    case "likely":
      return "Likely";
    case "possible":
      return "Possible";
    case "reach":
      return "Reach";
    case "high_reach":
      return "High reach";
    case "unknown":
      return "Unknown";
  }
}

export function percentileBand(percentile: number | null): string {
  if (percentile == null) return "not computable";
  if (percentile < 25) return "below the 25th percentile";
  if (percentile <= 75) return "within the middle 50%";
  return "above the 75th percentile";
}

function classifyAcademicFitForScore(
  score: number | null,
  p25: number | null,
  p75: number | null,
  aboveDelta: number,
): AcademicFit | null {
  if (score == null || !isFiniteNumber(p25) || !isFiniteNumber(p75) || p25 >= p75) {
    return null;
  }
  if (score >= p75 + aboveDelta) return "above_range";
  if (score >= p75) return "strong_academic_fit";
  if (score >= p25) return "in_range";
  return "below_range";
}

export function classifyAcademicFit(
  sat: number | null,
  act: number | null,
  school: SchoolAcademicProfile,
): AcademicFit {
  const order: Record<AcademicFit, number> = {
    strong_academic_fit: 0,
    above_range: 1,
    in_range: 2,
    below_range: 3,
    unknown: 4,
  };
  const fits = [
    hasMonotonicAnchors(school.satCompositeP25, school.satCompositeP50, school.satCompositeP75)
      ? classifyAcademicFitForScore(sat, school.satCompositeP25, school.satCompositeP75, 100)
      : null,
    hasMonotonicAnchors(school.actCompositeP25, school.actCompositeP50, school.actCompositeP75)
      ? classifyAcademicFitForScore(act, school.actCompositeP25, school.actCompositeP75, 2)
      : null,
  ].filter((fit): fit is AcademicFit => fit != null);

  if (fits.length === 0) return "unknown";
  return fits.sort((a, b) => order[a] - order[b])[0];
}

export function classifyAdmissionsOutlook(acceptanceRate: number | null): AdmissionsOutlook {
  if (acceptanceRate == null) return "unknown";
  if (acceptanceRate < 0.1) return "high_reach";
  if (acceptanceRate < 0.25) return "reach";
  if (acceptanceRate < 0.5) return "possible";
  return "likely";
}

export function scorePosition(
  profile: StudentProfile,
  school: SchoolAcademicProfile,
): PositionResult {
  const caveats = new Set<Caveat>();
  const cdsStartYear = Number.parseInt(school.cdsYear.split("-")[0] ?? "", 10);
  if (
    Number.isFinite(cdsStartYear) &&
    new Date().getFullYear() - cdsStartYear > STALE_CDS_YEAR_AGE
  ) {
    caveats.add("stale_cds");
  }

  const sat = cleanScore(profile.sat, 400, 1600);
  const act = cleanScore(profile.act, 1, 36);
  const hasSatAnchors = hasMonotonicAnchors(
    school.satCompositeP25,
    school.satCompositeP50,
    school.satCompositeP75,
  );
  const hasActAnchors = hasMonotonicAnchors(
    school.actCompositeP25,
    school.actCompositeP50,
    school.actCompositeP75,
  );

  if (!hasSatAnchors) caveats.add(school.satCompositeP50 == null ? "no_sat_data" : "data_incomplete");
  if (!hasActAnchors) caveats.add(school.actCompositeP50 == null ? "no_act_data" : "data_incomplete");
  if (!hasSatAnchors && !hasActAnchors) caveats.add("no_test_data");
  if ((school.satSubmitRate ?? 1) < LOW_SUBMIT_RATE) caveats.add("low_sat_submit_rate");
  if (!sat && !act) caveats.add("student_not_submitting");
  if (school.acceptanceRate == null) caveats.add("no_admit_rate");

  const satPercentile =
    sat != null && hasSatAnchors
      ? Math.round(
          interpolatePercentile(
            sat,
            school.satCompositeP25!,
            school.satCompositeP50!,
            school.satCompositeP75!,
          ),
        )
      : null;
  const actPercentile =
    act != null && hasActAnchors
      ? Math.round(
          interpolatePercentile(
            act,
            school.actCompositeP25!,
            school.actCompositeP50!,
            school.actCompositeP75!,
          ),
        )
      : null;

  const academicFit = classifyAcademicFit(sat, act, school);
  const admissionsOutlook = classifyAdmissionsOutlook(school.acceptanceRate);
  let tier = classifyTier(satPercentile, actPercentile, school.acceptanceRate);
  const bestPct = Math.max(satPercentile ?? -1, actPercentile ?? -1);
  if (
    school.acceptanceRate != null &&
    school.acceptanceRate < 0.15 &&
    bestPct >= 25 &&
    bestPct <= 75
  ) {
    tier = "unknown";
    caveats.add("sub_15_admit_rate_suppression");
  }

  const testClauses: string[] = [];
  if (sat != null) {
    testClauses.push(`Your SAT is ${percentileBand(satPercentile)} of admitted students who submitted scores`);
  }
  if (act != null) {
    testClauses.push(`Your ACT is ${percentileBand(actPercentile)} of admitted students who submitted scores`);
  }

  const gpaClause =
    profile.gpa != null && school.avgHsGpa != null
      ? `Your GPA is shown beside the school's reported average, not scored as a percentile`
      : null;
  const admitClause =
    school.acceptanceRate != null
      ? `This school admits ${Math.round(school.acceptanceRate * 100)}% of applicants`
      : "The CDS-derived admit rate is not available";

  const positionalSentence =
    [...testClauses, gpaClause, admitClause]
      .filter((clause): clause is string => Boolean(clause))
      .join(". ") + ".";

  return {
    satPercentile,
    actPercentile,
    tier,
    academicFit,
    admissionsOutlook,
    caveats: Array.from(caveats),
    cdsYear: school.cdsYear,
    positionalSentence,
  };
}
