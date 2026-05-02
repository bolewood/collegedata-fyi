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
  edAdmitRate: number | null;
  nonEarlyResidualAdmitRate: number | null;
  edShareOfAdmitted: number | null;
  waitListOfferRate: number | null;
  waitListConditionalAdmitRate: number | null;
  hasHighEdShare: boolean;
  hasRenderableContent: boolean;
};

const HIDDEN_DOCUMENT_FLAGS = new Set(["wrong_file", "blank_template", "low_coverage"]);
export const HIGH_ED_SHARE_THRESHOLD = 0.1951;

function safeRate(numerator: number | null, denominator: number | null): number | null {
  if (numerator == null || denominator == null || denominator <= 0) return null;
  if (numerator < 0) return null;
  return numerator / denominator;
}

function important(value: string | null): boolean {
  return value === "Important" || value === "Very Important";
}

export function computeAdmissionStrategy(
  school: AdmissionStrategySchool,
): AdmissionStrategyDerived {
  const edCountsValid =
    school.quality !== "ed_math_inconsistent" &&
    school.edOffered === true &&
    school.edApplicants != null &&
    school.edApplicants > 0 &&
    school.edAdmitted != null;

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

  const waitListValid =
    school.quality !== "wait_list_math_inconsistent" &&
    school.waitListPolicy === true;
  const waitListOfferRate = waitListValid
    ? safeRate(school.waitListOffered, school.applied)
    : null;
  const waitListConditionalAdmitRate = waitListValid
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
      hasFactorSignal ||
      school.eaOffered != null ||
      school.appFeeAmount != null ||
      school.appFeeWaiverOffered != null);

  return {
    edAdmitRate,
    nonEarlyResidualAdmitRate,
    edShareOfAdmitted,
    waitListOfferRate,
    waitListConditionalAdmitRate,
    hasHighEdShare:
      edShareOfAdmitted != null && edShareOfAdmitted >= HIGH_ED_SHARE_THRESHOLD,
    hasRenderableContent,
  };
}

export function formatRate(value: number | null, digits = 0): string {
  if (value == null || !Number.isFinite(value)) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}
