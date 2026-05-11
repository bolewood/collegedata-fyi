export type AdmissionStrategyQuality =
  | "ok"
  | "ed_math_inconsistent"
  | "wait_list_math_inconsistent"
  | "insufficient_data";

export type AdmissionFactorImportance =
  | "Very Important"
  | "Important"
  | "Considered"
  | "Not Considered"
  | string;

export type AdmissionStrategySchool = {
  schoolId: string;
  schoolName: string;
  cdsYear: string;
  archiveUrl: string | null;
  dataQualityFlag: string | null;
  applied: number | null;
  admitted: number | null;
  enrolledFirstYear: number | null;
  acceptanceRate: number | null;
  yieldRate: number | null;
  edOffered: boolean | null;
  edApplicants: number | null;
  edAdmitted: number | null;
  edHasSecondDeadline: boolean | null;
  eaOffered: boolean | null;
  eaRestrictive: boolean | null;
  waitListPolicy: boolean | null;
  waitListOffered: number | null;
  waitListAccepted: number | null;
  waitListAdmitted: number | null;
  firstGenFactor: AdmissionFactorImportance | null;
  legacyFactor: AdmissionFactorImportance | null;
  geographyFactor: AdmissionFactorImportance | null;
  stateResidencyFactor: AdmissionFactorImportance | null;
  demonstratedInterestFactor: AdmissionFactorImportance | null;
  appFeeAmount: number | null;
  appFeeWaiverOffered: boolean | null;
  quality: AdmissionStrategyQuality | null;
};

export type AdmissionStrategyDerived = {
  hasEdFlow: boolean;
  hasSingleApplicantFlow: boolean;
  edAdmitRate: number | null;
  nonEarlyResidualAdmitRate: number | null;
  edShareOfAdmitted: number | null;
  edShareOfClass: number | null;
  edAdmitRateMultiple: number | null;
  estimatedEdEnrolled: number | null;
  estimatedNonEarlyEnrolled: number | null;
  nonEarlyApplicants: number | null;
  nonEarlyAdmitted: number | null;
  nonEarlyYield: number | null;
  waitListOfferRate: number | null;
  waitListOptInRate: number | null;
  waitListConditionalAdmitRate: number | null;
  waitListHasCounts: boolean;
  waitListHasAnyCount: boolean;
  waitListCountsAnomalous: boolean;
  waitListCountsMissing: boolean;
  hasHighEdShare: boolean;
  hasRenderableContent: boolean;
};

const HIDDEN_DOCUMENT_FLAGS = new Set(["wrong_file", "blank_template", "low_coverage"]);
// Phase 0 corpus p75 of ED admit share for 2024-25+ rows.
export const HIGH_ED_SHARE_THRESHOLD = 0.1951;

function safeRate(numerator: number | null, denominator: number | null): number | null {
  if (numerator == null || denominator == null || denominator <= 0) return null;
  if (numerator < 0) return null;
  return numerator / denominator;
}

function safeNonNegative(value: number | null): number | null {
  return value == null || value < 0 ? null : value;
}

function important(value: string | null): boolean {
  return value === "Important" || value === "Very Important";
}

export function interestIsRelevant(value: string | null): boolean {
  return value === "Considered" || important(value);
}

export function computeAdmissionStrategy(
  school: AdmissionStrategySchool,
): AdmissionStrategyDerived {
  const edCountsValid =
    school.quality !== "ed_math_inconsistent" &&
    (school.edOffered === true ||
      (school.edApplicants != null &&
        school.edApplicants > 0 &&
        school.edAdmitted != null &&
        school.edAdmitted <= school.edApplicants)) &&
    school.edApplicants != null &&
    school.edApplicants > 0 &&
    school.edAdmitted != null &&
    school.edAdmitted <= school.edApplicants;

  const edAdmitRate = edCountsValid
    ? safeRate(school.edAdmitted, school.edApplicants)
    : null;

  const nonEarlyResidualAdmitRate =
    edCountsValid &&
    school.applied != null &&
    school.admitted != null &&
    school.applied > school.edApplicants!
      ? safeRate(
          school.admitted - school.edAdmitted!,
          school.applied - school.edApplicants!,
        )
      : null;

  const edShareOfAdmitted =
    edCountsValid && school.admitted != null
      ? safeRate(school.edAdmitted, school.admitted)
      : null;
  const nonEarlyApplicants =
    edCountsValid && school.applied != null
      ? safeNonNegative(school.applied - school.edApplicants!)
      : null;
  const nonEarlyAdmitted =
    edCountsValid && school.admitted != null
      ? safeNonNegative(school.admitted - school.edAdmitted!)
      : null;
  const estimatedEdEnrolled =
    edCountsValid && school.enrolledFirstYear != null
      ? Math.min(school.edAdmitted!, school.enrolledFirstYear)
      : null;
  const estimatedNonEarlyEnrolled =
    estimatedEdEnrolled != null && school.enrolledFirstYear != null
      ? Math.max(school.enrolledFirstYear - estimatedEdEnrolled, 0)
      : null;
  const edShareOfClass =
    estimatedEdEnrolled != null && school.enrolledFirstYear != null
      ? safeRate(estimatedEdEnrolled, school.enrolledFirstYear)
      : null;
  const nonEarlyYield =
    estimatedNonEarlyEnrolled != null && nonEarlyAdmitted != null
      ? safeRate(estimatedNonEarlyEnrolled, nonEarlyAdmitted)
      : null;
  const edAdmitRateMultiple =
    edAdmitRate != null &&
    nonEarlyResidualAdmitRate != null &&
    nonEarlyResidualAdmitRate > 0
      ? edAdmitRate / nonEarlyResidualAdmitRate
      : null;

  const waitListHasAnyCount =
    school.waitListOffered != null ||
    school.waitListAccepted != null ||
    school.waitListAdmitted != null;
  const waitListHasCounts =
    school.waitListOffered != null &&
    school.waitListAccepted != null &&
    school.waitListAdmitted != null;
  const waitListCountsAnomalous =
    school.quality === "wait_list_math_inconsistent" ||
    (school.waitListOffered != null &&
      school.waitListAccepted != null &&
      school.waitListAccepted > school.waitListOffered) ||
    (school.waitListAccepted != null &&
      school.waitListAdmitted != null &&
      school.waitListAdmitted > school.waitListAccepted);
  const waitListCountsMissing =
    school.waitListPolicy === true && !waitListHasCounts;
  const waitListCanCompute =
    (school.waitListPolicy === true || waitListHasCounts) &&
    !waitListCountsAnomalous;
  const waitListOfferRate = waitListCanCompute
    ? safeRate(school.waitListOffered, school.applied)
    : null;
  const waitListOptInRate = waitListCanCompute
    ? safeRate(school.waitListAccepted, school.waitListOffered)
    : null;
  const waitListConditionalAdmitRate = waitListCanCompute
    ? safeRate(school.waitListAdmitted, school.waitListAccepted)
    : null;

  const hasFactorSignal = [
    school.firstGenFactor,
    school.legacyFactor,
    school.geographyFactor,
    school.stateResidencyFactor,
    school.demonstratedInterestFactor,
  ].some(important);

  const hasRenderableContent =
    !HIDDEN_DOCUMENT_FLAGS.has(school.dataQualityFlag ?? "") &&
      school.quality !== "insufficient_data" &&
    (edAdmitRate != null ||
      school.yieldRate != null ||
      waitListOfferRate != null ||
      waitListConditionalAdmitRate != null ||
      waitListHasAnyCount ||
      waitListCountsMissing ||
      hasFactorSignal ||
      school.eaOffered === true);

  return {
    hasEdFlow:
      edCountsValid &&
      school.applied != null &&
      school.admitted != null &&
      school.enrolledFirstYear != null &&
      nonEarlyApplicants != null &&
      nonEarlyAdmitted != null,
    hasSingleApplicantFlow:
      !edCountsValid &&
      school.applied != null &&
      school.admitted != null &&
      school.enrolledFirstYear != null,
    edAdmitRate,
    nonEarlyResidualAdmitRate,
    edShareOfAdmitted,
    edShareOfClass,
    edAdmitRateMultiple,
    estimatedEdEnrolled,
    estimatedNonEarlyEnrolled,
    nonEarlyApplicants,
    nonEarlyAdmitted,
    nonEarlyYield,
    waitListOfferRate,
    waitListOptInRate,
    waitListConditionalAdmitRate,
    waitListHasCounts,
    waitListHasAnyCount,
    waitListCountsAnomalous,
    waitListCountsMissing,
    hasHighEdShare:
      edShareOfAdmitted != null && edShareOfAdmitted >= HIGH_ED_SHARE_THRESHOLD,
    hasRenderableContent,
  };
}

export function formatRate(value: number | null, digits = 0): string {
  if (value == null || !Number.isFinite(value)) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}
