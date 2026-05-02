import { describe, expect, it } from "vitest";
import {
  computeAdmissionStrategy,
  type AdmissionStrategySchool,
} from "./admission-strategy";

const base: AdmissionStrategySchool = {
  schoolId: "example",
  schoolName: "Example College",
  cdsYear: "2025-26",
  archiveUrl: null,
  dataQualityFlag: null,
  applied: 1000,
  admitted: 100,
  acceptanceRate: 0.1,
  yieldRate: 0.5,
  edOffered: true,
  edApplicants: 200,
  edAdmitted: 40,
  edHasSecondDeadline: false,
  eaOffered: null,
  eaRestrictive: null,
  waitListPolicy: true,
  waitListOffered: 300,
  waitListAccepted: 150,
  waitListAdmitted: 30,
  firstGenFactor: "Important",
  legacyFactor: "Considered",
  geographyFactor: "Not Considered",
  stateResidencyFactor: "Not Considered",
  demonstratedInterestFactor: "Very Important",
  appFeeAmount: 85,
  appFeeWaiverOffered: true,
  quality: "ok",
};

describe("computeAdmissionStrategy", () => {
  it("computes ED, residual, class-share, and wait-list rates", () => {
    const result = computeAdmissionStrategy(base);

    expect(result.edAdmitRate).toBe(0.2);
    expect(result.nonEarlyResidualAdmitRate).toBe(0.075);
    expect(result.edShareOfAdmitted).toBe(0.4);
    expect(result.hasHighEdShare).toBe(true);
    expect(result.waitListOfferRate).toBe(0.3);
    expect(result.waitListConditionalAdmitRate).toBe(0.2);
    expect(result.hasRenderableContent).toBe(true);
  });

  it("suppresses ED math when quality rejects the ED counts", () => {
    const result = computeAdmissionStrategy({
      ...base,
      quality: "ed_math_inconsistent",
      edApplicants: 40,
      edAdmitted: 41,
    });

    expect(result.edAdmitRate).toBeNull();
    expect(result.nonEarlyResidualAdmitRate).toBeNull();
    expect(result.edShareOfAdmitted).toBeNull();
    expect(result.hasRenderableContent).toBe(true);
  });

  it("renders EA-only schools without inventing an EA admit rate", () => {
    const result = computeAdmissionStrategy({
      ...base,
      edOffered: false,
      edApplicants: null,
      edAdmitted: null,
      eaOffered: true,
      eaRestrictive: true,
      yieldRate: null,
      waitListPolicy: false,
      firstGenFactor: null,
      demonstratedInterestFactor: null,
      appFeeAmount: null,
      appFeeWaiverOffered: null,
    });

    expect(result.edAdmitRate).toBeNull();
    expect(result.nonEarlyResidualAdmitRate).toBeNull();
    expect(result.hasRenderableContent).toBe(true);
  });

  it("hides insufficient cards", () => {
    const result = computeAdmissionStrategy({
      ...base,
      edOffered: null,
      edApplicants: null,
      edAdmitted: null,
      eaOffered: null,
      eaRestrictive: null,
      yieldRate: null,
      waitListPolicy: null,
      waitListOffered: null,
      waitListAccepted: null,
      waitListAdmitted: null,
      firstGenFactor: null,
      legacyFactor: null,
      geographyFactor: null,
      stateResidencyFactor: null,
      demonstratedInterestFactor: null,
      appFeeAmount: null,
      appFeeWaiverOffered: null,
      quality: "insufficient_data",
    });

    expect(result.hasRenderableContent).toBe(false);
  });
});
