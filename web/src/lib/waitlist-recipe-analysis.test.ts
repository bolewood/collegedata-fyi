import { describe, expect, it } from "vitest";
import { WAITLIST_ROWS } from "./waitlist-recipe-data";

describe("waitlist recipe identity", () => {
  it("keeps Tufts CDS values attached to the Tufts federal identity", () => {
    const tufts = WAITLIST_ROWS.find(
      (row) => row.documentId === "7a5bb196-7973-4f7f-87c1-adc699248073",
    );

    expect(tufts).toMatchObject({
      ipedsId: "168148",
      schoolId: "tufts",
      schoolName: "Tufts University",
      state: "MA",
      control: "Private nonprofit",
      carnegie: "Doctoral universities",
      undergradEnrollment: 7061,
      schoolUrl: "/schools/tufts/2024-25",
    });
  });
});
