import { describe, expect, it } from "vitest";
import { c1HeadlineTotals } from "./c1-headline-totals";
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
});
