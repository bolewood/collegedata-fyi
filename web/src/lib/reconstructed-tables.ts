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
    ...buildC1Tables(values),
    ...buildC9Tables(values),
  ].filter((table) => hasReportedCell(table));
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
