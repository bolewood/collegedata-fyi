import { describe, expect, it } from "vitest";
import {
  CAMPUS_FILINGS,
  campusFiling,
  combinedFilingNote,
  notIncludedLead,
} from "./campus-filings";

const text = (parts: { text: string }[] | null) => (parts ?? []).map((p) => p.text).join("");

describe("campus filings", () => {
  it("tells a branch reader the main campus's report does not include them, and links to it", () => {
    const parts = notIncludedLead("miami-university-hamilton", true);
    expect(text(parts)).toBe(
      "We haven’t found a Common Data Set for this campus. Miami University-Oxford publishes one, " +
        "and it does not include this campus. See Miami University-Oxford. " +
        "The federal numbers for this campus are below.",
    );
    expect(parts?.find((p) => p.type === "link")).toEqual({
      type: "link",
      href: "/schools/miami-university-oxford",
      text: "See Miami University-Oxford",
    });
  });

  it("does not promise federal numbers that are not there", () => {
    expect(text(notIncludedLead("miami-university-hamilton", false))).not.toContain("federal");
  });

  it("labels a combined filing on every campus it covers", () => {
    for (const id of [
      "fairleigh-dickinson-university-florham-campus",
      "fairleigh-dickinson-university-metropolitan-campus",
    ]) {
      expect(combinedFilingNote(id)).toBe(
        "Fairleigh Dickinson University publishes one Common Data Set for its Florham and " +
          "Metropolitan campuses together. The numbers from the school’s report on this page " +
          "cover both; the federal numbers are for this campus alone.",
      );
      expect(notIncludedLead(id, true)).toBeNull();
    }
  });

  it("returns nothing for a school with its own filing, including prototype keys", () => {
    for (const id of ["mit", "miami-university-oxford", "constructor", "toString"]) {
      expect(campusFiling(id)).toBeNull();
      expect(notIncludedLead(id, true)).toBeNull();
      expect(combinedFilingNote(id)).toBeNull();
    }
  });

  it("never points a campus at itself or at another entry that has no file", () => {
    for (const [id, filing] of Object.entries(CAMPUS_FILINGS)) {
      if (filing.kind !== "not_included") continue;
      expect(filing.parentId).not.toBe(id);
      expect(CAMPUS_FILINGS[filing.parentId]?.kind).not.toBe("not_included");
    }
  });
});
