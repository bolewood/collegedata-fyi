import { describe, expect, it } from "vitest";
import { isOwnEdNote, readC21Note } from "./c21-ed-note";
import type { FieldValue } from "./types";

function vals(entries: Record<string, string>): Record<string, FieldValue> {
  return Object.fromEntries(Object.entries(entries).map(([id, value]) => [id, { value }]));
}

describe("isOwnEdNote", () => {
  it("accepts a school-written plan note", () => {
    expect(
      isOwnEdNote(
        "Students admitted under Early Decision I or II are required to withdraw all other applications.",
      ),
    ).toBe(true);
  });

  it("rejects empty, short, stock, URL-only, and form-chrome disclaimers", () => {
    expect(isOwnEdNote(null)).toBe(false);
    expect(isOwnEdNote("N/A")).toBe(false);
    expect(isOwnEdNote("See website.")).toBe(false);
    expect(isOwnEdNote("Please provide significant details about your early decision plan:")).toBe(
      false,
    );
    expect(isOwnEdNote("Binding.")).toBe(false);
    expect(
      isOwnEdNote("For more information, visit www.bowdoin.edu/admissions/apply/early-decision/"),
    ).toBe(false);
    expect(
      isOwnEdNote(
        "Does your institution offer an early decision plan (an admission plan that permits students to apply and be notified of an admission decision well in advance of the regular notification date)",
      ),
    ).toBe(false);
    expect(isOwnEdNote("Number of early decision applications received by your institution")).toBe(
      false,
    );
    expect(isOwnEdNote("Click or tap here to enter text.")).toBe(false);
    expect(
      isOwnEdNote("https://admissions.northwestern.edu/apply/application-options.html#early-decision"),
    ).toBe(false);
    expect(isOwnEdNote("## For the Fall 2020 entering class:")).toBe(false);
    expect(isOwnEdNote("C22 Early action C22 Yes C22")).toBe(false);
  });
});

describe("readC21Note", () => {
  it("reads 2023-24 / 2024-25 notes at C.2108", () => {
    expect(
      readC21Note({
        values: vals({
          "C.2108": "Early Decision is binding; admitted students must enroll.",
        }),
        schemaVersion: "2024-25",
        producer: "tier4_docling",
        yearStart: 2024,
      }),
    ).toBe("Early Decision is binding; admitted students must enroll.");
  });

  it("reads 2025-26 notes at C.2112, not the date parts that took 2108", () => {
    expect(
      readC21Note({
        values: vals({
          "C.2108": "11",
          "C.2112": "Two rounds: ED I in November and ED II in January.",
        }),
        schemaVersion: "2025-26",
        producer: "tier4_docling",
        yearStart: 2025,
      }),
    ).toBe("Two rounds: ED I in November and ED II in January.");
  });

  it("recovers a note from markdown when the field is empty", () => {
    expect(
      readC21Note({
        values: {},
        schemaVersion: null,
        producer: "tier4_docling",
        yearStart: 2023,
        markdown: `Please provide significant details about your early decision plan:
Applicants must state in writing that they wish to be considered for Early Decision and that they will enroll if admitted.

## C22. Early action
No
`,
      }),
    ).toMatch(/^Applicants must state in writing/);
  });

  it("stops the markdown note before C22 and form labels", () => {
    expect(
      readC21Note({
        values: {},
        schemaVersion: null,
        producer: "tier4_docling",
        yearStart: 2023,
        markdown: `Please provide significant details about your early decision plan:
Early Decision applicants must meet the 1/15 application deadline, even if converting to Early Decision between 1/15 and 2/1.
If 'yes,' please complete the following:
First or only early decision plan closing date
## C22. Early action
No
`,
      }),
    ).toBe(
      "Early Decision applicants must meet the 1/15 application deadline, even if converting to Early Decision between 1/15 and 2/1.",
    );
  });
});
