import { describe, expect, it } from "vitest";
import {
  AID_CANT_CHECK_SAMPLE,
  formatSnapshotTime,
  FEDERAL_DIFFERS_SAMPLE,
  HAND_CHECK_DATE,
  HAND_CHECK_ISO,
  aidCantCheckNote,
  federalDiffersNote,
} from "./data-quality";
import { FIXTURE_SNAPSHOT } from "./__fixtures__/data-quality-snapshot";

// The facts behind the two hand-check notes, written out as literals so they can't drift together with the
// constants that generate the notes. Source: PRD 040 "M0 samples (2026-11-25)", samples 1 and 2.

describe("hand-check facts (independent of the constants)", () => {
  it("financial aid sample: 20 of the 217 can't-check reports in 2023-24, 19 filled in and not stored in full", () => {
    expect({ ...AID_CANT_CHECK_SAMPLE, years: [...AID_CANT_CHECK_SAMPLE.years] }).toEqual({
      years: ["2023-24"],
      checked: 20,
      ours: 19,
      population: 217,
      keepRange: [0.9, 1.1],
    });
  });

  it("admissions 'differs' sample: 10 reports from 2023-24 and 2024-25; 8 had our number in the file, 2 were on our side", () => {
    expect({ ...FEDERAL_DIFFERS_SAMPLE, years: [...FEDERAL_DIFFERS_SAMPLE.years] }).toEqual({
      years: ["2023-24", "2024-25"],
      checked: 10,
      sameInFile: 8,
      ours: 2,
      populationReports: 140,
      populationValues: 219,
      keepRange: [0.9, 1.1],
    });
  });

  it("both samples were taken on 2026-11-25", () => {
    expect(HAND_CHECK_ISO).toBe("2026-11-25");
    expect(HAND_CHECK_DATE).toBe("November 25, 2026");
  });

  it("the notes print those facts", () => {
    const aid = aidCantCheckNote(FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2023-24")!)!;
    expect(aid).toContain("20 of the reports we couldn’t check");
    expect(aid).toContain("November 25, 2026");
    expect(aid).toContain("19 had the financial aid table filled in");
    expect(aid).not.toMatch(/\b217\b/);
    expect(aid).not.toMatch(/most of/i);
    const fed = federalDiffersNote(FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2024-25")!, FIXTURE_SNAPSHOT)!;
    expect(fed).toContain("10 differing reports (2023-24 and 2024-25, sampled on November 25, 2026)");
    expect(fed).toContain("8 had the number we compared in the school’s file");
    expect(fed).toContain("which can include our matching");
    expect(fed).toContain("2 were on our side");
    expect(fed).not.toContain("The other 2 were ours");
  });
});

describe("formatSnapshotTime", () => {
  it("prints UTC hours and minutes on a 24-hour clock, never 24:xx", () => {
    expect(formatSnapshotTime("2026-11-24T00:05:00Z")).toBe("00:05 UTC");
    expect(formatSnapshotTime("2026-11-24T12:25:03Z")).toBe("12:25 UTC");
    expect(formatSnapshotTime("2026-11-24T23:59:59Z")).toBe("23:59 UTC");
    expect(formatSnapshotTime("2026-11-24T09:07:00+02:00")).toBe("07:07 UTC");
  });
});
