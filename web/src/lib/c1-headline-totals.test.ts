import { describe, expect, it } from "vitest";
import { c1HeadlineTotals, c1TemplateForArtifact, readC1Totals } from "./c1-headline-totals";
import type { FieldValue } from "./types";

function field(value: string): FieldValue {
  return { value, value_type: "Number" };
}

describe("c1HeadlineTotals", () => {
  it("keeps a coherent 2025-26 total", () => {
    const totals = c1HeadlineTotals(
      {
        "C.101": field("1200"),
        "C.102": field("1300"),
        "C.116": field("2500"),
        "C.104": field("100"),
        "C.105": field("200"),
        "C.117": field("300"),
      },
      "2025-26",
    );
    expect(totals.applied).toBe(2500);
    expect(totals.admitted).toBe(300);
  });

  it("does not treat in-state as the college total when it is smaller than males", () => {
    const totals = c1HeadlineTotals(
      {
        "C.101": field("2496"),
        "C.104": field("1424"),
        "C.107": field("264"),
        "C.116": field("911"),
        "C.117": field("657"),
        "C.118": field("185"),
        "C.119": field("741"),
        "C.120": field("519"),
        "C.121": field("56"),
        "C.122": field("844"),
        "C.123": field("248"),
        "C.124": field("23"),
        "C.125": field("2496"),
        "C.126": field("1424"),
        "C.127": field("264"),
      },
      "2025-26",
    );
    expect(totals.applied).toBe(2496);
    expect(totals.admitted).toBe(1424);
    expect(totals.enrolled).toBe(264);
  });

  it("detects a Total-last zip when the published total is still larger than each gender", () => {
    const totals = c1HeadlineTotals(
      {
        "C.101": field("5000"),
        "C.102": field("4958"),
        "C.116": field("8120"),
        "C.119": field("1688"),
        "C.122": field("150"),
        "C.125": field("9958"),
      },
      "2025-26",
    );
    expect(totals.applied).toBe(9958);
  });

  it("does not replace a women's-college total that matches each gender column", () => {
    const totals = c1HeadlineTotals(
      {
        "C.101": field("2070"),
        "C.102": field("2070"),
        "C.116": field("2070"),
      },
      "2025-26",
    );
    expect(totals.applied).toBe(2070);
  });

  it("uses gender components when the published total is zero", () => {
    const totals = c1HeadlineTotals(
      {
        "C.101": field("100"),
        "C.102": field("120"),
        "C.116": field("0"),
      },
      "2025-26",
    );
    expect(totals.applied).toBe(220);
  });

  it("reads 2026-27 with the 2025-26 numbering", () => {
    const values = {
      "C.101": field("1200"),
      "C.102": field("1300"),
      "C.116": field("2500"),
      "C.104": field("100"),
      "C.105": field("200"),
      "C.117": field("300"),
      "C.107": field("40"),
      "C.108": field("60"),
      "C.118": field("100"),
    };
    expect(c1HeadlineTotals(values, "2026-27")).toEqual(c1HeadlineTotals(values, "2025-26"));
    expect(c1HeadlineTotals(values, "2026-27")).toEqual({ applied: 2500, admitted: 300, enrolled: 100 });
  });
});

describe("the 2026-27 Total row by sex", () => {
  it("is used before a sum of the rows by sex when the residency total is blank", () => {
    // Only the men rows were read: their sum is not a total, the printed row is.
    const values = {
      "C.101": field("22819"),
      "C.104": field("1189"),
      "C.107": field("799"),
      "C.1T01": field("50264"),
      "C.1T02": field("2387"),
      "C.1T03": field("1633"),
    };
    expect(c1HeadlineTotals(values, "2026-27")).toEqual({ applied: 50264, admitted: 2387, enrolled: 1633 });
  });

  it("is used when the residency total is 0", () => {
    const values = {
      "C.116": field("0"),
      "C.101": field("100"),
      "C.102": field("120"),
      "C.1T01": field("225"),
    };
    expect(c1HeadlineTotals(values, "2026-27").applied).toBe(225);
  });

  it("is ignored when it is 0 or smaller than a row it totals", () => {
    expect(
      c1HeadlineTotals({ "C.101": field("100"), "C.102": field("120"), "C.1T01": field("0") }, "2026-27").applied,
    ).toBe(220);
    expect(
      c1HeadlineTotals({ "C.101": field("100"), "C.102": field("120"), "C.1T01": field("90") }, "2026-27").applied,
    ).toBe(220);
    expect(c1HeadlineTotals({ "C.1T01": field("0") }, "2026-27").applied).toBeNull();
  });

  it("does not replace a residency total that is present", () => {
    const values = { "C.116": field("2500"), "C.101": field("1200"), "C.102": field("1300"), "C.1T01": field("2400") };
    expect(c1HeadlineTotals(values, "2026-27").applied).toBe(2500);
  });

  it("counts as the school's own total, so the headline is shown without the third-category check", () => {
    // A fillable PDF on the 2025-26 form filed for 2026-27: no markdown, no unknown-sex row,
    // and the totals sit on the by-sex ids.
    const reading = readC1Totals({
      values: {
        "C.101": field("1200"),
        "C.102": field("1300"),
        "C.1T01": field("2500"),
        "C.104": field("100"),
        "C.105": field("200"),
        "C.1T02": field("300"),
        "C.107": field("40"),
        "C.108": field("60"),
        "C.1T03": field("100"),
      },
      schemaVersion: "2026-27",
      producer: "tier2_acroform",
      yearStart: 2026,
    });
    expect(reading.totals).toEqual({ applied: 2500, admitted: 300, enrolled: 100 });
  });

  it("without it, an unconfirmed men + women sum is still withheld", () => {
    const reading = readC1Totals({
      values: { "C.101": field("1200"), "C.102": field("1300") },
      schemaVersion: "2026-27",
      producer: "tier2_acroform",
      yearStart: 2026,
    });
    expect(reading.totals?.applied).toBeNull();
  });
});

describe("c1TemplateForArtifact", () => {
  it("maps a 2026-27 extract to the 2025-26 numbering", () => {
    for (const producer of ["tier4_docling", "tier2_acroform", "tier1_xlsx", "tier2_template_overlay"]) {
      expect(c1TemplateForArtifact({ schemaVersion: "2026-27", producer, yearStart: 2026 })).toEqual({
        template: "2025-26",
      });
    }
  });

  it("still has no mapping for a template year it does not know", () => {
    const unknown = c1TemplateForArtifact({ schemaVersion: "2027-28", producer: "tier2_acroform", yearStart: 2027 });
    expect(unknown.template).toBeNull();
  });
});

describe("readC1Totals", () => {
  it("returns headline totals for a 2026-27 extract", () => {
    const reading = readC1Totals({
      values: { "C.116": field("2500"), "C.117": field("300"), "C.118": field("100") },
      schemaVersion: "2026-27",
      producer: "tier2_acroform",
      yearStart: 2026,
    });
    expect(reading.template).toBe("2025-26");
    expect(reading.totals).toEqual({ applied: 2500, admitted: 300, enrolled: 100 });
  });
});
