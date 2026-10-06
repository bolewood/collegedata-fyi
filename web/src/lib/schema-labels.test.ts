import { describe, expect, it } from "vitest";
import {
  getFieldDisplayLabel,
  getFieldSubsectionName,
  getFieldValueType,
} from "./schema-labels";

describe("schema-aware field labels", () => {
  it("uses 2024-25 C21 labels for early decision counts", () => {
    const field = { value: "6013" };

    expect(getFieldDisplayLabel("C.2106", field, "2024-25")).toBe(
      "Number of early decision applications received by your institution",
    );
    expect(getFieldValueType("C.2106", field, "2024-25")).toBe("Number");
  });

  it("keeps 2025-26 C21 labels as the default", () => {
    const field = { value: "11" };

    expect(getFieldDisplayLabel("C.2106", field, "2025-26")).toBe(
      "Other early decision plan closing date: Month",
    );
    expect(getFieldValueType("C.2106", field, "2025-26")).toBe("MM");
  });

  it("uses canonical schema labels before stale embedded question text", () => {
    const field = {
      value: "1042",
      question: "Other early decision plan closing date: Day",
      value_type: "DD",
    };

    expect(getFieldDisplayLabel("C.2107", field, "2024-25")).toBe(
      "Number of applicants admitted under early decision plan",
    );
    expect(getFieldValueType("C.2107", field, "2024-25")).toBe("Number");
  });

  it("distinguishes C1 residency rows from the C1 totals", () => {
    const field = { value: "911" };

    expect(getFieldDisplayLabel("C.116", field, "2025-26")).toBe(
      "Total first-time, first-year students who applied",
    );
    expect(getFieldDisplayLabel("C.119", field, "2025-26")).toBe(
      "In-state first-time, first-year who applied",
    );
    expect(getFieldDisplayLabel("C.127", field, "2025-26")).toBe(
      "Nonresident first-time, first-year who enrolled",
    );
    expect(getFieldDisplayLabel("C.120", field, "2024-25")).toBe(
      "In-state first-time, first-year who applied",
    );
    expect(getFieldDisplayLabel("C.131", field, "2024-25")).toBe(
      "Unknown-residency first-time, first-year who enrolled",
    );
  });

  it("resolves 2024-25 subsections from the 2024-25 schema map", () => {
    expect(getFieldSubsectionName("A.008", { value: "Durham" }, "2024-25")).toBe(
      "Respondent Information",
    );
  });
});
