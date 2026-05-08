import { formatFieldValue } from "./format";
import type { FieldValue } from "./types";

export type ReconstructedCell = {
  fieldId: string | null;
  label: string;
  display: string;
  missing: boolean;
};

export type ReconstructedRow = {
  key: string;
  label: string;
  cells: ReconstructedCell[];
};

export type ReconstructedTable = {
  key: string;
  title: string;
  caption: string;
  columns: string[];
  rows: ReconstructedRow[];
  usedFieldIds: string[];
};

export function buildReconstructedTables(
  values: Record<string, FieldValue>,
): ReconstructedTable[] {
  return [
    ...buildB1Tables(values),
    ...buildB2Tables(values),
    ...buildB3Tables(values),
    ...buildB4B5Tables(values),
    ...buildB22Tables(values),
    ...buildC1Tables(values),
    ...buildC7Tables(values),
    ...buildC9Tables(values),
    ...buildD2Tables(values),
    ...buildG1Tables(values),
    ...buildG5Tables(values),
    ...buildH2Tables(values),
    ...buildH2ATables(values),
    ...buildH5Tables(values),
    ...buildI1Tables(values),
    ...buildI3Tables(values),
    ...buildJTables(values),
  ].filter((table) => hasReportedCell(table));
}

function buildB1Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^B\.1\d{2}$/.test(id))) {
    return [];
  }

  return isB12024Layout(values) ? b1Tables2024(values) : b1Tables2025(values);
}

function isB12024Layout(values: Record<string, FieldValue>): boolean {
  const b103 = values["B.103"]?.question?.toLowerCase() ?? "";
  return (
    b103.includes("another gender") ||
    ["B.189", "B.190", "B.191", "B.192", "B.193", "B.194", "B.195"].some(
      (id) => id in values,
    )
  );
}

function b1Tables2025(values: Record<string, FieldValue>): ReconstructedTable[] {
  return [
    makeTable({
      key: "b1-undergraduate",
      title: "B1 undergraduate enrollment",
      caption:
        "Full-time, part-time, and total undergraduate enrollment by reported sex or status.",
      columns: ["Males", "Females", "Unknown", "Total"],
      rows: [
        row2025("ug-ft-first-year", "Full-time first-time first-year degree-seeking", 101),
        row2025("ug-ft-other-first-year", "Full-time other first-year degree-seeking", 102),
        row2025("ug-ft-other-degree", "Full-time all other degree-seeking", 103),
        row2025("ug-ft-total-degree", "Full-time total degree-seeking", 104),
        row2025("ug-ft-other-credit", "Full-time other credit-course undergraduates", 105),
        row2025("ug-ft-total", "Full-time total undergraduates", 106),
        row2025("ug-pt-first-year", "Part-time first-time first-year degree-seeking", 107),
        row2025("ug-pt-other-first-year", "Part-time other first-year degree-seeking", 108),
        row2025("ug-pt-other-degree", "Part-time all other degree-seeking", 109),
        row2025("ug-pt-total-degree", "Part-time total degree-seeking", 110),
        row2025("ug-pt-other-credit", "Part-time other credit-course undergraduates", 111),
        row2025("ug-pt-total", "Part-time total undergraduates", 112),
        row2025("ug-total", "Total undergraduates", 113, "B.176"),
      ],
      values,
    }),
    makeTable({
      key: "b1-graduate",
      title: "B1 graduate enrollment",
      caption:
        "Full-time, part-time, and total graduate enrollment by reported sex or status.",
      columns: ["Males", "Females", "Unknown", "Total"],
      rows: [
        row2025("grad-ft-first-time", "Full-time first-time degree-seeking", 114),
        row2025("grad-ft-other-degree", "Full-time all other degree-seeking", 115),
        row2025("grad-ft-other-credit", "Full-time other credit-course graduates", 116),
        row2025("grad-ft-total", "Full-time total graduates", 117),
        row2025("grad-pt-first-time", "Part-time first-time degree-seeking", 118),
        row2025("grad-pt-other-degree", "Part-time all other degree-seeking", 119),
        row2025("grad-pt-other-credit", "Part-time other credit-course graduates", 120),
        row2025("grad-pt-total", "Part-time total graduates", 121),
        row2025("grad-total", "Total graduate students", 122, "B.177"),
      ],
      values,
    }),
    makeTable({
      key: "b1-overall",
      title: "B1 overall enrollment",
      caption:
        "Institution-wide full-time, part-time, and total enrollment by reported sex or status.",
      columns: ["Males", "Females", "Unknown", "Total"],
      rows: [
        row2025("all-ft", "Total full-time students", 123),
        row2025("all-pt", "Total part-time students", 124),
        row2025("all-total", "Grand total all students", 125, "B.178"),
      ],
      values,
    }),
  ];
}

function b1Tables2024(values: Record<string, FieldValue>): ReconstructedTable[] {
  return [
    makeTable({
      key: "b1-undergraduate",
      title: "B1 undergraduate enrollment",
      caption:
        "Full-time, part-time, and total undergraduate enrollment by reported gender or status.",
      columns: ["Men", "Women", "Another gender", "Unknown", "Total"],
      rows: [
        row2024("ug-ft-first-year", "Full-time first-time first-year degree-seeking", 101),
        row2024("ug-ft-other-first-year", "Full-time other first-year degree-seeking", 105),
        row2024("ug-ft-other-degree", "Full-time all other degree-seeking", 109),
        row2024("ug-ft-total-degree", "Full-time total degree-seeking", 113),
        row2024("ug-ft-other-credit", "Full-time other credit-course undergraduates", 117),
        row2024("ug-ft-total", "Full-time total undergraduates", 121),
        row2024("ug-pt-first-year", "Part-time first-time first-year degree-seeking", 125),
        row2024("ug-pt-other-first-year", "Part-time other first-year degree-seeking", 129),
        row2024("ug-pt-other-degree", "Part-time all other degree-seeking", 133),
        row2024("ug-pt-total-degree", "Part-time total degree-seeking", 137),
        row2024("ug-pt-other-credit", "Part-time other credit-course undergraduates", 141),
        row2024("ug-pt-total", "Part-time total undergraduates", 145),
        row2024("ug-total", "Total undergraduates", 149, "B.193"),
      ],
      values,
    }),
    makeTable({
      key: "b1-graduate",
      title: "B1 graduate enrollment",
      caption:
        "Full-time, part-time, and total graduate enrollment by reported gender or status.",
      columns: ["Men", "Women", "Another gender", "Unknown", "Total"],
      rows: [
        row2024("grad-ft-first-time", "Full-time first-time degree-seeking", 153),
        row2024("grad-ft-other-degree", "Full-time all other degree-seeking", 157),
        row2024("grad-ft-other-credit", "Full-time other credit-course graduates", 161),
        row2024("grad-ft-total", "Full-time total graduates", 165),
        row2024("grad-pt-first-time", "Part-time first-time degree-seeking", 169),
        row2024("grad-pt-other-degree", "Part-time all other degree-seeking", 173),
        row2024("grad-pt-other-credit", "Part-time other credit-course graduates", 177),
        row2024("grad-pt-total", "Part-time total graduates", 181),
        row2024("grad-total", "Total graduate students", 185, "B.194"),
      ],
      values,
    }),
    makeTable({
      key: "b1-overall",
      title: "B1 overall enrollment",
      caption:
        "Institution-wide total enrollment by reported gender or status.",
      columns: ["Men", "Women", "Another gender", "Unknown", "Total"],
      rows: [
        row2024("all-total", "Grand total all students", 189, "B.195"),
      ],
      values,
    }),
  ];
}

function row2025(
  key: string,
  label: string,
  maleIdNumber: number,
  totalId: string | null = null,
): [string, string, (string | null)[]] {
  return [
    key,
    label,
    [
      b1Id(maleIdNumber),
      b1Id(maleIdNumber + 25),
      b1Id(maleIdNumber + 50),
      totalId,
    ],
  ];
}

function row2024(
  key: string,
  label: string,
  firstIdNumber: number,
  totalId: string | null = null,
): [string, string, (string | null)[]] {
  return [
    key,
    label,
    [
      b1Id(firstIdNumber),
      b1Id(firstIdNumber + 1),
      b1Id(firstIdNumber + 2),
      b1Id(firstIdNumber + 3),
      totalId,
    ],
  ];
}

function b1Id(n: number): string {
  return `B.${n}`;
}

function buildB2Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^B\.2(0[1-9]|[12][0-9]|30)$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "b2-race-ethnicity",
      title: "B2 enrollment by race and ethnicity",
      caption:
        "Undergraduate enrollment by race or ethnicity for first-time first-year, degree-seeking, and total undergraduate cohorts.",
      columns: [
        "First-time first-year",
        "Degree-seeking undergraduates",
        "Total undergraduates",
      ],
      rows: [
        b2Row("nonresidents", "Nonresidents", 201),
        b2Row("hispanic-latino", "Hispanic/Latino", 202),
        b2Row("black", "Black or African American, non-Hispanic", 203),
        b2Row("white", "White, non-Hispanic", 204),
        b2Row("american-indian", "American Indian or Alaska Native, non-Hispanic", 205),
        b2Row("asian", "Asian, non-Hispanic", 206),
        b2Row("pacific-islander", "Native Hawaiian or other Pacific Islander, non-Hispanic", 207),
        b2Row("two-or-more", "Two or more races, non-Hispanic", 208),
        b2Row("unknown", "Race and/or ethnicity unknown", 209),
        b2Row("total", "Total", 210),
      ],
      values,
    }),
  ];
}

function b2Row(
  key: string,
  label: string,
  firstYearIdNumber: number,
): [string, string, (string | null)[]] {
  return [
    key,
    label,
    [
      bId(firstYearIdNumber),
      bId(firstYearIdNumber + 10),
      bId(firstYearIdNumber + 20),
    ],
  ];
}

function bId(n: number): string {
  return `B.${n}`;
}

function buildB3Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^B\.30[1-9]$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "b3-degrees-awarded",
      title: "B3 degrees awarded",
      caption: "Degrees awarded by credential level in the reporting year.",
      columns: ["Number awarded"],
      rows: [
        ["certificate", "Certificate/diploma", ["B.301"]],
        ["associate", "Associate degrees", ["B.302"]],
        ["bachelor", "Bachelor's degrees", ["B.303"]],
        ["postbachelor", "Postbachelor's certificates", ["B.304"]],
        ["master", "Master's degrees", ["B.305"]],
        ["post-master", "Post-master's certificates", ["B.306"]],
        ["doctoral-research", "Doctoral degrees, research/scholarship", ["B.307"]],
        ["doctoral-practice", "Doctoral degrees, professional practice", ["B.308"]],
        ["doctoral-other", "Doctoral degrees, other", ["B.309"]],
      ],
      values,
    }),
  ];
}

function buildB4B5Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^B\.[45](0[1-9]|[12][0-9]|3[0-2])$/.test(id))) {
    return [];
  }

  return [
    graduationRateTable(values, "b4-current-graduation-rates", "B4 current graduation-rate cohort", 401),
    graduationRateTable(values, "b5-previous-graduation-rates", "B5 previous graduation-rate cohort", 501),
  ];
}

function graduationRateTable(
  values: Record<string, FieldValue>,
  key: string,
  title: string,
  firstIdNumber: number,
): ReconstructedTable {
  return withPercentRows(makeTable({
    key,
    title,
    caption:
      "Four-year institution graduation-rate cohort counts and six-year graduation rates by aid-recipient category.",
    columns: [
      "Pell Grant",
      "Subsidized Stafford, no Pell",
      "Neither Pell nor subsidized Stafford",
      "Total",
    ],
    rows: [
      graduationRateRow("initial-cohort", "Initial cohort", firstIdNumber),
      graduationRateRow("did-not-persist", "Did not persist", firstIdNumber + 4),
      graduationRateRow("final-cohort", "Final cohort", firstIdNumber + 8),
      graduationRateRow("completed-four", "Completed in less than four years", firstIdNumber + 12),
      graduationRateRow("completed-five", "Completed in less than five years", firstIdNumber + 16),
      graduationRateRow("completed-six", "Completed in less than six years", firstIdNumber + 20),
      graduationRateRow("completed-total", "Total completers", firstIdNumber + 24),
      graduationRateRow("six-year-rate", "Six-year graduation rate", firstIdNumber + 28),
    ],
    values,
  }), ["six-year-rate"]);
}

function graduationRateRow(
  key: string,
  label: string,
  firstIdNumber: number,
): [string, string, (string | null)[]] {
  return [
    key,
    label,
    [bId(firstIdNumber), bId(firstIdNumber + 1), bId(firstIdNumber + 2), bId(firstIdNumber + 3)],
  ];
}

function buildB22Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  const hasB22 = ids.some((id) => /^B\.220[1-3]$/.test(id));
  const hasTwoYear = ids.some((id) => /^B\.(1[2-9]|20|21)0[1-2]$/.test(id));
  if (!hasB22 && !hasTwoYear) {
    return [];
  }

  return [
    withPercentRows(makeTable({
      key: "b22-first-year-retention",
      title: "B22 first-year retention",
      caption: "First-time full-time bachelor's cohort retention count and rate.",
      columns: ["Value"],
      rows: [
        ["entering-cohort", "Entering cohort", ["B.2201"]],
        ["still-enrolled", "Still enrolled next fall", ["B.2202"]],
        ["retention-rate", "Retention rate", ["B.2203"]],
      ],
      values,
    }), ["retention-rate"]),
    makeTable({
      key: "b12-b21-two-year-graduation-rates",
      title: "B12-B21 two-year graduation rates",
      caption:
        "Two-year institution graduation-rate cohort outcomes for the current and previous cohorts.",
      columns: ["Current cohort", "Previous cohort"],
      rows: [
        twoYearGradRow("initial-cohort", "Initial cohort", 12),
        twoYearGradRow("did-not-persist", "Did not persist", 13),
        twoYearGradRow("final-cohort", "Final cohort", 14),
        twoYearGradRow("completed-two-total", "Completed program in less than two years", 15),
        twoYearGradRow("completed-two-150", "Completed program in less than two years at 150% time", 16),
        twoYearGradRow("completed-four-total", "Completed program in less than four years", 17),
        twoYearGradRow("completed-four-150", "Completed program in less than four years at 150% time", 18),
        twoYearGradRow("transfers-out", "Transfers out", 19),
        twoYearGradRow("transfers-two-year", "Transfers to two-year institutions", 20),
        twoYearGradRow("transfers-four-year", "Transfers to four-year institutions", 21),
      ],
      values,
    }),
  ];
}

function twoYearGradRow(
  key: string,
  label: string,
  sectionNumber: number,
): [string, string, (string | null)[]] {
  return [key, label, [bId(sectionNumber * 100 + 1), bId(sectionNumber * 100 + 2)]];
}

function buildC1Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^C\.1(0[1-9]|1[0-9]|2[0-9]|30)$/.test(id))) {
    return [];
  }

  return [isC12024Layout(values) ? c1Table2024(values) : c1Table2025(values)];
}

function isC12024Layout(values: Record<string, FieldValue>): boolean {
  const c103 = values["C.103"]?.question?.toLowerCase() ?? "";
  const c104 = values["C.104"]?.question?.toLowerCase() ?? "";
  const c117 = values["C.117"]?.question?.toLowerCase() ?? "";
  return (
    c103.includes("another gender") ||
    c104.includes("unknown gender who applied") ||
    c117.includes("students who applied")
  );
}

function c1Table2025(values: Record<string, FieldValue>): ReconstructedTable {
  return makeTable({
    key: "c1-admissions",
    title: "C1 first-year admissions",
    caption:
      "First-time, first-year applicants, admits, and enrolled students by sex or status.",
    columns: ["Males", "Females", "Unknown sex", "Total"],
    rows: [
      ["applied", "Applied", ["C.101", "C.102", "C.103", "C.116"]],
      ["admitted", "Admitted", ["C.104", "C.105", "C.106", "C.117"]],
      ["enrolled", "Enrolled", ["C.107", "C.108", "C.109", "C.118"]],
      ["enrolled-ft", "Enrolled full-time", ["C.110", "C.112", "C.114", null]],
      ["enrolled-pt", "Enrolled part-time", ["C.111", "C.113", "C.115", null]],
    ],
    values,
  });
}

function c1Table2024(values: Record<string, FieldValue>): ReconstructedTable {
  return makeTable({
    key: "c1-admissions",
    title: "C1 first-year admissions",
    caption:
      "First-time, first-year applicants, admits, and enrolled students by gender or status.",
    columns: ["Men", "Women", "Another gender", "Unknown gender", "Total"],
    rows: [
      ["applied", "Applied", ["C.101", "C.102", "C.103", "C.104", "C.117"]],
      ["admitted", "Admitted", ["C.105", "C.106", "C.107", "C.108", "C.118"]],
      ["enrolled-ft", "Enrolled full-time", ["C.109", "C.111", "C.113", "C.115", null]],
      ["enrolled-pt", "Enrolled part-time", ["C.110", "C.112", "C.114", "C.116", null]],
      ["enrolled-total", "Enrolled total", [null, null, null, null, "C.119"]],
    ],
    values,
  });
}

function buildC7Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^C\.7(0[1-9]|1[0-9])$/.test(id))) {
    return [];
  }

  return [c7Table(values)];
}

const C7_COLUMNS = ["Very important", "Important", "Considered", "Not considered"];

function c7Table(values: Record<string, FieldValue>): ReconstructedTable {
  const factors: [string, string][] = [
    ["C.701", "Rigor of secondary school record"],
    ["C.702", "Class rank"],
    ["C.703", "Academic GPA"],
    ["C.704", "Standardized test scores"],
    ["C.705", "Application essay"],
    ["C.706", "Recommendations"],
    ["C.707", "Interview"],
    ["C.708", "Extracurricular activities"],
    ["C.709", "Talent or ability"],
    ["C.710", "Character and personal qualities"],
    ["C.711", "First generation"],
    ["C.712", "Alumni relation"],
    ["C.713", "Geographical residence"],
    ["C.714", "State residency"],
    ["C.715", "Religious affiliation or commitment"],
    ["C.716", "Volunteer work"],
    ["C.717", "Work experience"],
    ["C.718", "Level of applicant interest"],
  ];

  const usedFieldIds: string[] = [];
  const rows = factors.map(([fieldId, label]) => {
    const field = values[fieldId];
    if (field) usedFieldIds.push(fieldId);
    const selected = normalizeChoice(field ? displayField(field) : "");
    return {
      key: fieldId.toLowerCase().replace(".", "-"),
      label,
      cells: C7_COLUMNS.map((column) => {
        const isSelected = selected === normalizeChoice(column);
        return {
          fieldId: isSelected ? fieldId : null,
          label: column,
          display: field ? (isSelected ? "Yes" : "—") : "Not reported",
          missing: !field || !isSelected,
        };
      }),
    };
  });

  return {
    key: "c7-factors",
    title: "C7 basis for selection",
    caption:
      "Relative importance of academic and nonacademic factors in first-year admissions decisions.",
    columns: C7_COLUMNS,
    rows,
    usedFieldIds,
  };
}

function buildC9Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^C\.9(0[1-9]|[1-5][0-9])$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "c9-submission",
      title: "C9 test-score submission",
      caption: "Share and count of enrolled first-year students who submitted SAT or ACT scores.",
      columns: ["Percent", "Number"],
      rows: [
        ["sat", "SAT", ["C.901", "C.903"]],
        ["act", "ACT", ["C.902", "C.904"]],
      ],
      values,
    }),
    makeTable({
      key: "c9-percentiles",
      title: "C9 test-score percentiles",
      caption: "Reported 25th, 50th, and 75th percentile scores for enrolled first-year students.",
      columns: ["25th percentile", "50th percentile", "75th percentile"],
      rows: [
        ["sat-composite", "SAT composite", ["C.905", "C.906", "C.907"]],
        ["sat-ebrw", "SAT evidence-based reading and writing", ["C.908", "C.909", "C.910"]],
        ["sat-math", "SAT math", ["C.911", "C.912", "C.913"]],
        ["act-composite", "ACT composite", ["C.914", "C.915", "C.916"]],
        ["act-math", "ACT math", ["C.917", "C.918", "C.919"]],
        ["act-english", "ACT English", ["C.920", "C.921", "C.922"]],
        ["act-writing", "ACT Writing", ["C.923", "C.924", "C.925"]],
        ["act-science", "ACT Science", ["C.926", "C.927", "C.928"]],
        ["act-reading", "ACT Reading", ["C.929", "C.930", "C.931"]],
      ],
      values,
    }),
  ];
}

function buildD2Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^D\.2(0[1-9]|1[0-2])$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "d2-transfer-admissions",
      title: "D2 transfer admissions",
      caption:
        "Transfer applicants, admits, and enrolled students by reported sex or status.",
      columns: ["Males", "Females", "Unknown", "Total"],
      rows: [
        ["applied", "Applied", ["D.201", "D.202", "D.203", "D.204"]],
        ["admitted", "Admitted", ["D.205", "D.206", "D.207", "D.208"]],
        ["enrolled", "Enrolled", ["D.209", "D.210", "D.211", "D.212"]],
      ],
      values,
    }),
  ];
}

function buildG1Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^G\.1(0[1-9]|1[0-9]|20)$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "g1-undergraduate-costs",
      title: "G1 undergraduate costs",
      caption:
        "Published undergraduate tuition, required fees, and on-campus food and housing charges.",
      columns: ["First-year", "All undergraduates"],
      rows: [
        ["tuition", "Tuition", ["G.101", "G.102"]],
        ["tuition-in-district", "Tuition: in-district", ["G.103", "G.107"]],
        ["tuition-in-state", "Tuition: in-state", ["G.104", "G.108"]],
        ["tuition-out-of-state", "Tuition: out-of-state", ["G.105", "G.109"]],
        ["tuition-nonresident", "Tuition: nonresident", ["G.106", "G.110"]],
        ["required-fees", "Required fees", ["G.111", "G.115"]],
        ["food-housing", "Food and housing, on-campus", ["G.112", "G.116"]],
        ["housing-only", "Housing only, on-campus", ["G.113", "G.117"]],
        ["food-only", "Food only, on-campus meal plan", ["G.114", "G.118"]],
        ["comprehensive", "Comprehensive tuition, food, and housing", ["G.119", null]],
        ["other", "Other", ["G.120", null]],
      ],
      values,
    }),
  ];
}

function buildG5Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^G\.5(0[1-9]|1[0-3])$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "g5-estimated-expenses",
      title: "G5 estimated expenses",
      caption:
        "Estimated books, supplies, transportation, food, housing, and personal expenses by living arrangement.",
      columns: [
        "Residents",
        "Commuters living at home",
        "Commuters not living at home",
      ],
      rows: [
        ["books-supplies", "Books and supplies", ["G.501", "G.504", "G.508"]],
        ["food-only", "Food only", [null, "G.505", "G.510"]],
        ["housing-only", "Housing only", [null, null, "G.509"]],
        ["food-housing", "Food and housing total", [null, null, "G.511"]],
        ["transportation", "Transportation", ["G.502", "G.506", "G.512"]],
        ["other", "Other expenses", ["G.503", "G.507", "G.513"]],
      ],
      values,
    }),
  ];
}

function buildH2ATables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^H\.2A(0[1-9]|1[0-2])$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "h2a-non-need-aid",
      title: "H2A non-need-based aid",
      caption:
        "Non-need-based scholarship and grant aid recipients and average awards by undergraduate cohort.",
      columns: [
        "First-year full-time",
        "All undergraduates full-time",
        "All undergraduates less-than-full-time",
      ],
      rows: [
        ["institutional-grant-count", "Institutional non-need grant recipients", ["H.2A01", "H.2A05", "H.2A09"]],
        ["institutional-grant-average", "Average institutional non-need grant", ["H.2A02", "H.2A06", "H.2A10"]],
        ["athletic-grant-count", "Athletic grant recipients", ["H.2A03", "H.2A07", "H.2A11"]],
        ["athletic-grant-average", "Average athletic grant", ["H.2A04", "H.2A08", "H.2A12"]],
      ],
      values,
    }),
  ];
}

function buildH2Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^H\.2(0[1-9]|[1-3][0-9])$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "h2-aid-awarded",
      title: "H2 students awarded aid",
      caption:
        "Need-based aid counts, need met, and average awards by undergraduate cohort.",
      columns: [
        "First-year full-time",
        "All undergraduates full-time",
        "All undergraduates less-than-full-time",
      ],
      rows: [
        h2Row("degree-seeking", "Degree-seeking undergraduates", 201),
        h2Row("applied-need", "Applied for need-based aid", 202),
        h2Row("need-determined", "Determined to have financial need", 203),
        h2Row("any-aid", "Awarded any aid", 204),
        h2Row("need-grant", "Awarded need-based scholarship or grant aid", 205),
        h2Row("need-self-help", "Awarded need-based self-help aid", 206),
        h2Row("non-need-grant", "Awarded non-need-based scholarship or grant aid", 207),
        h2Row("need-fully-met", "Need fully met", 208),
        h2Row("average-need-met", "Average percentage of need met", 209),
        h2Row("average-aid-package", "Average financial aid package", 210),
        h2Row("average-need-grant", "Average need-based scholarship or grant", 211),
        h2Row("average-need-self-help", "Average need-based self-help award", 212),
        h2Row("average-need-loan", "Average need-based loan", 213),
      ],
      values,
    }),
  ];
}

function h2Row(
  key: string,
  label: string,
  firstYearIdNumber: number,
): [string, string, (string | null)[]] {
  return [
    key,
    label,
    [
      h2Id(firstYearIdNumber),
      h2Id(firstYearIdNumber + 13),
      h2Id(firstYearIdNumber + 26),
    ],
  ];
}

function h2Id(n: number): string {
  return `H.${n}`;
}

function buildH5Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^H\.5(0[1-9]|1[0-5])$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "h5-student-loans",
      title: "H5 student loans",
      caption:
        "Graduating first-time student loan borrowers by loan source, share of class, and average per-borrower debt.",
      columns: ["Number in class", "Percent of class", "Average per borrower"],
      rows: [
        h5Row("any-loan", "Any loan program", 501),
        h5Row("federal-loans", "Federal loan programs", 502),
        h5Row("institutional-loans", "Institutional loan programs", 503),
        h5Row("state-loans", "State loan programs", 504),
        h5Row("private-loans", "Private student loans", 505),
      ],
      values,
    }),
  ];
}

function h5Row(
  key: string,
  label: string,
  countIdNumber: number,
): [string, string, (string | null)[]] {
  return [
    key,
    label,
    [hId(countIdNumber), hId(countIdNumber + 5), hId(countIdNumber + 10)],
  ];
}

function hId(n: number): string {
  return `H.${n}`;
}

function buildI1Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^I\.1(0[1-9]|[12][0-9]|30)$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "i1-instructional-faculty",
      title: "I1 instructional faculty",
      caption:
        "Instructional faculty counts by full-time status and selected demographic or credential category.",
      columns: ["Full-time", "Part-time", "Total"],
      rows: [
        i1Row("total", "Total instructional faculty", 101),
        i1Row("minority", "Members of minority groups", 102),
        i1Row("female", "Females", 103),
        i1Row("male", "Males", 104),
        i1Row("nonresident", "Nonresidents", 105),
        i1Row("terminal-degree", "Doctorate or other terminal degree", 106),
        i1Row("masters", "Master's, but not terminal master's", 107),
        i1Row("bachelors", "Bachelor's degree", 108),
        i1Row("unknown-degree", "Unknown or other highest degree", 109),
        i1Row("graduate-only", "Stand-alone graduate/professional programs", 110),
      ],
      values,
    }),
  ];
}

function i1Row(
  key: string,
  label: string,
  fullTimeIdNumber: number,
): [string, string, (string | null)[]] {
  return [
    key,
    label,
    [iId(fullTimeIdNumber), iId(fullTimeIdNumber + 10), iId(fullTimeIdNumber + 20)],
  ];
}

function buildI3Tables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^I\.3(0[1-9]|1[0-6])$/.test(id))) {
    return [];
  }

  return [
    makeTable({
      key: "i3-undergraduate-class-size",
      title: "I3 undergraduate class size",
      caption:
        "Undergraduate class sections and subsections by enrollment size band.",
      columns: ["Class sections", "Class subsections"],
      rows: [
        i3Row("2-9", "2-9 students", 301),
        i3Row("10-19", "10-19 students", 302),
        i3Row("20-29", "20-29 students", 303),
        i3Row("30-39", "30-39 students", 304),
        i3Row("40-49", "40-49 students", 305),
        i3Row("50-99", "50-99 students", 306),
        i3Row("100-plus", "100+ students", 307),
        i3Row("total", "Total", 308),
      ],
      values,
    }),
  ];
}

function i3Row(
  key: string,
  label: string,
  sectionIdNumber: number,
): [string, string, (string | null)[]] {
  return [key, label, [iId(sectionIdNumber), iId(sectionIdNumber + 8)]];
}

function iId(n: number): string {
  return `I.${n}`;
}

function buildJTables(values: Record<string, FieldValue>): ReconstructedTable[] {
  const ids = Object.keys(values);
  if (!ids.some((id) => /^J\.(1\d{2}|2[0-2]\d)$/.test(id))) {
    return [];
  }

  return [
    withPercentCells(makeTable({
      key: "j-degrees-conferred",
      title: "J degrees conferred by discipline",
      caption:
        "Percentage distribution of degrees conferred by discipline and award level.",
      columns: ["Certificate/diploma", "Associate", "Bachelor's"],
      rows: J_DISCIPLINES.map((label, i) => [
        label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
        label,
        [jId(101 + i), jId(141 + i), jId(181 + i)],
      ]),
      values,
    })),
  ];
}

const J_DISCIPLINES = [
  "Agriculture",
  "Natural resources and conservation",
  "Architecture",
  "Area, ethnic, and gender studies",
  "Communication/journalism",
  "Communication technologies",
  "Computer and information sciences",
  "Personal and culinary services",
  "Education",
  "Engineering",
  "Engineering technologies",
  "Foreign languages, literatures, and linguistics",
  "Family and consumer sciences",
  "Law/legal studies",
  "English",
  "Liberal arts/general studies",
  "Library science",
  "Biological/life sciences",
  "Mathematics and statistics",
  "Military science and military technologies",
  "Interdisciplinary studies",
  "Parks and recreation",
  "Philosophy and religious studies",
  "Theology and religious vocations",
  "Physical sciences",
  "Science technologies",
  "Psychology",
  "Homeland Security, law enforcement, firefighting, and protective services",
  "Public administration and social services",
  "Social sciences",
  "Construction trades",
  "Mechanic and repair technologies",
  "Precision production",
  "Transportation and materials moving",
  "Visual and performing arts",
  "Health professions and related programs",
  "Business/marketing",
  "History",
  "Other",
  "Total",
];

function jId(n: number): string {
  return `J.${n}`;
}

function withPercentRows(
  table: ReconstructedTable,
  rowKeys: string[],
): ReconstructedTable {
  const percentRows = new Set(rowKeys);
  return {
    ...table,
    rows: table.rows.map((row) =>
      percentRows.has(row.key)
        ? { ...row, cells: row.cells.map(formatPercentCell) }
        : row,
    ),
  };
}

function withPercentCells(table: ReconstructedTable): ReconstructedTable {
  return {
    ...table,
    rows: table.rows.map((row) => ({
      ...row,
      cells: row.cells.map(formatPercentCell),
    })),
  };
}

function formatPercentCell(cell: ReconstructedCell): ReconstructedCell {
  if (cell.missing || cell.display.endsWith("%")) {
    return cell;
  }
  return { ...cell, display: `${cell.display}%` };
}

function makeTable({
  key,
  title,
  caption,
  columns,
  rows,
  values,
}: {
  key: string;
  title: string;
  caption: string;
  columns: string[];
  rows: [string, string, (string | null)[]][];
  values: Record<string, FieldValue>;
}): ReconstructedTable {
  const usedFieldIds: string[] = [];
  const reconstructedRows = rows.map(([rowKey, rowLabel, fieldIds]) => ({
    key: rowKey,
    label: rowLabel,
    cells: fieldIds.map((fieldId, i) => {
      const field = fieldId ? values[fieldId] : undefined;
      if (fieldId && field) usedFieldIds.push(fieldId);
      const display = field ? displayField(field) : "Not reported";
      return {
        fieldId,
        label: columns[i],
        display,
        missing: !field || isMissingDisplay(display),
      };
    }),
  }));

  return {
    key,
    title,
    caption,
    columns,
    rows: reconstructedRows,
    usedFieldIds,
  };
}

function displayField(field: FieldValue): string {
  const raw = field.value_decoded ?? field.value ?? "";
  const display = formatFieldValue(raw, field.value_type);
  return display || "Not reported";
}

function hasReportedCell(table: ReconstructedTable): boolean {
  return table.rows.some((row) => row.cells.some((cell) => !cell.missing));
}

function isMissingDisplay(display: string): boolean {
  const normalized = display.trim().toLowerCase();
  return (
    normalized === "" ||
    normalized === "—" ||
    normalized === "not reported" ||
    normalized.includes("not provided")
  );
}

function normalizeChoice(value: string): string {
  return value.trim().toLowerCase().replace(/[-\s]+/g, " ");
}
