import type { FieldValue } from "@/lib/types";

export type C1HeadlineTotals = {
  applied: number | null;
  admitted: number | null;
  enrolled: number | null;
};

type HeadlineSpec = {
  total: string;
  gender: string[];
  residency?: {
    inState: string;
    outOfState: string;
    nonresidents: string;
    unknown: string;
  };
};

function headlineSpecs(schemaVersion?: string | null): {
  applied: HeadlineSpec;
  admitted: HeadlineSpec;
  enrolled: HeadlineSpec;
} {
  if (schemaVersion === "2024-25") {
    return {
      applied: {
        total: "C.117",
        gender: ["C.101", "C.102", "C.103", "C.104"],
      },
      admitted: {
        total: "C.118",
        gender: ["C.105", "C.106", "C.107", "C.108"],
      },
      enrolled: {
        total: "C.119",
        gender: ["C.109", "C.110", "C.111", "C.112", "C.113", "C.114", "C.115", "C.116"],
      },
    };
  }

  // The 2023-24 template uses the 2024-25 numbering without the
  // unknown-gender rows (C.104, C.108, C.115, C.116).
  if (schemaVersion === "2023-24") {
    return {
      applied: { total: "C.117", gender: ["C.101", "C.102", "C.103"] },
      admitted: { total: "C.118", gender: ["C.105", "C.106", "C.107"] },
      enrolled: {
        total: "C.119",
        gender: ["C.109", "C.110", "C.111", "C.112", "C.113", "C.114"],
      },
    };
  }

  if (schemaVersion === "2025-26") {
    return {
      applied: {
        total: "C.116",
        gender: ["C.101", "C.102", "C.103"],
        residency: {
          inState: "C.119",
          outOfState: "C.122",
          nonresidents: "C.125",
          unknown: "C.128",
        },
      },
      admitted: {
        total: "C.117",
        gender: ["C.104", "C.105", "C.106"],
        residency: {
          inState: "C.120",
          outOfState: "C.123",
          nonresidents: "C.126",
          unknown: "C.129",
        },
      },
      enrolled: {
        total: "C.118",
        gender: ["C.107", "C.108", "C.109"],
        residency: {
          inState: "C.121",
          outOfState: "C.124",
          nonresidents: "C.127",
          unknown: "C.130",
        },
      },
    };
  }

  return {
    applied: { total: "C.101", gender: ["C.101", "C.102", "C.103"] },
    admitted: { total: "C.104", gender: ["C.104", "C.105", "C.106"] },
    enrolled: { total: "C.107", gender: ["C.107", "C.108", "C.109"] },
  };
}

export function fieldNumber(
  values: Record<string, FieldValue>,
  id: string,
): number | null {
  const field = values[id];
  if (!field) return null;
  const raw = field.value_decoded ?? field.value;
  if (raw == null || raw === "") return null;
  const n = parseFloat(String(raw).replace(/,/g, ""));
  return Number.isNaN(n) ? null : n;
}

function sumPresent(
  values: Record<string, FieldValue>,
  ids: string[],
): { sum: number; max: number; count: number } | null {
  let sum = 0;
  let max = -Infinity;
  let count = 0;
  for (const id of ids) {
    const n = fieldNumber(values, id);
    if (n == null) continue;
    sum += n;
    if (n > max) max = n;
    count += 1;
  }
  if (count === 0) return null;
  return { sum, max, count };
}

function preferCoherentTotal(
  values: Record<string, FieldValue>,
  spec: HeadlineSpec,
): number | null {
  const gender = sumPresent(values, spec.gender);
  const total = fieldNumber(values, spec.total);

  if (total != null && total === 0 && gender && gender.sum > 0) {
    return gender.sum;
  }

  if (gender && total != null && total < gender.max) {
    return gender.sum;
  }

  const residency = spec.residency;
  if (residency && gender) {
    const inState = fieldNumber(values, residency.inState);
    const outOfState = fieldNumber(values, residency.outOfState);
    const nonresidents = fieldNumber(values, residency.nonresidents);
    const unknown = fieldNumber(values, residency.unknown);
    if (
      total != null &&
      inState != null &&
      outOfState != null &&
      nonresidents != null &&
      Math.abs(total + inState + outOfState - nonresidents) <= 1 &&
      Math.abs(nonresidents - gender.sum) <= 1 &&
      Math.abs(total - nonresidents) > 1
    ) {
      return gender.sum;
    }
    if (
      unknown != null &&
      Math.abs(unknown - gender.sum) <= 1 &&
      total != null &&
      total < unknown
    ) {
      return gender.sum;
    }
    // Older layouts with no C1 total row: the residency table's in-state
    // "Total first-time, first-year" row lands on the total id.
    if (total != null && inState != null && total === inState && gender.sum > total + 1) {
      return gender.sum;
    }
  }

  if (total != null && total > 0) return total;
  if (gender) return gender.sum;
  return total;
}

export type C1Template = "2023-24" | "2024-25" | "2025-26";

export type C1TemplateResolution =
  | { template: C1Template; reason?: undefined }
  | { template: null; reason: string };

/**
 * Which C1 numbering an extract's values use. Artifacts without a
 * schema_version come from the Tier 4 / HTML cleaners, whose label map
 * writes 2025-26 ids on every template. Older XLSX files were read with the
 * 2025-26 cell map, which does not fit pre-2024 layouts, so their C1 cells
 * are not trusted.
 */
export function c1TemplateForArtifact({
  schemaVersion,
  producer,
  yearStart,
}: {
  schemaVersion: string | null | undefined;
  producer: string | null | undefined;
  yearStart: number | null | undefined;
}): C1TemplateResolution {
  if (schemaVersion === "2023-24" || schemaVersion === "2024-25") {
    return { template: schemaVersion };
  }
  if (schemaVersion === "2025-26") {
    if (producer === "tier1_xlsx" && yearStart != null && yearStart < 2024) {
      return { template: null, reason: "older XLSX layout read with the 2025-26 cell map" };
    }
    return { template: "2025-26" };
  }
  if (schemaVersion == null && (producer === "tier4_docling" || producer === "tier6_html")) {
    return { template: "2025-26" };
  }
  return {
    template: null,
    reason: `no C1 mapping for schema ${schemaVersion ?? "none"} from ${producer ?? "unknown producer"}`,
  };
}

export function c1HeadlineTotals(
  values: Record<string, FieldValue>,
  schemaVersion?: string | null,
): C1HeadlineTotals {
  const specs = headlineSpecs(schemaVersion);
  return {
    applied: preferCoherentTotal(values, specs.applied),
    admitted: preferCoherentTotal(values, specs.admitted),
    enrolled: preferCoherentTotal(values, specs.enrolled),
  };
}

const THIRD_CATEGORY = /another gender|other\s*\/\s*unknown|unknown gender|unknown sex|gender unknown/i;

export type C1MarkdownRows = {
  /** Third sex/gender category (another gender, other/unknown, unknown sex). */
  third: C1HeadlineTotals;
  partTimeMen: number | null;
  partTimeWomen: number | null;
  /** Part-time enrolled rows present in the table, with or without a value. */
  partTimeRows: { men: boolean; women: boolean };
  /** "first-year men/women who enrolled" rows without a full-/part-time qualifier. */
  hasDirectSexEnrolled: boolean;
};

/**
 * First-year C1 rows read from the extract's markdown table, e.g.
 * "| Total first-time, first-year of another gender who applied | 5582 |".
 * The Tier 4 label map misses the "of another gender" and "other/unknown"
 * wordings and some part-time rows, so older extracts drop them and
 * men + women sums undercount. First occurrence of each row wins.
 */
export function c1MarkdownRows(markdown: string | null | undefined): C1MarkdownRows {
  const rows: C1MarkdownRows = {
    third: { applied: null, admitted: null, enrolled: null },
    partTimeMen: null,
    partTimeWomen: null,
    partTimeRows: { men: false, women: false },
    hasDirectSexEnrolled: false,
  };
  if (!markdown) return rows;
  let thirdEnrolledDirect: number | null = null;
  let thirdEnrolledParts: number | null = null;
  const seen = new Set<string>();
  for (const line of markdown.split("\n")) {
    const cells = line.split("|").map((cell) => cell.trim());
    if (cells.length < 3) continue;
    const label = cells[1];
    if (!/first-year/i.test(label) || /transfer/i.test(label)) continue;
    const stage = /who applied/i.test(label)
      ? "applied"
      : /who were admitted/i.test(label)
        ? "admitted"
        : /who enrolled/i.test(label)
          ? "enrolled"
          : null;
    if (!stage) continue;
    const sex = THIRD_CATEGORY.test(label)
      ? "third"
      : /\bwomen\b|\bfemales?\b/i.test(label)
        ? "women"
        : /\bmen\b|\bmales?\b/i.test(label)
          ? "men"
          : null;
    if (!sex) continue;
    const load = /full-time/i.test(label) ? "ft" : /part-time/i.test(label) ? "pt" : "direct";
    if (stage === "enrolled" && sex !== "third" && load === "direct") rows.hasDirectSexEnrolled = true;
    if (stage === "enrolled" && sex !== "third" && load === "pt") rows.partTimeRows[sex] = true;

    // The value is the first non-empty cell; later cells can be subtotals.
    const valueCell = cells.slice(2).find((cell) => cell !== "");
    if (valueCell === undefined || !/^\d[\d,]*(\.0+)?$/.test(valueCell)) continue;
    const key = `${stage}|${sex}|${load}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const value = Number(valueCell.replace(/,/g, "").replace(/\.0+$/, ""));

    if (sex === "third") {
      if (stage !== "enrolled") rows.third[stage] = value;
      else if (load === "direct") thirdEnrolledDirect = value;
      else thirdEnrolledParts = (thirdEnrolledParts ?? 0) + value;
    } else if (stage === "enrolled" && load === "pt") {
      if (sex === "men") rows.partTimeMen = value;
      else rows.partTimeWomen = value;
    }
  }
  rows.third.enrolled = thirdEnrolledDirect ?? thirdEnrolledParts;
  return rows;
}

function addTo(
  values: Record<string, FieldValue>,
  id: string,
  extra: number,
): FieldValue {
  return { value: String((fieldNumber(values, id) ?? 0) + extra), source: "markdown_c1_row" };
}

/**
 * 2025-26 numbering, as the Tier 4 cleaner writes it for every template:
 * - fill C.103 / C.106 / C.109 (third category) from the markdown when empty;
 * - on templates with only full-time / part-time enrolled rows, C.107 / C.108
 *   hold the full-time count and C.111 / C.113 the part-time count, so add
 *   part-time in.
 */
function withMarkdownC1Rows(
  values: Record<string, FieldValue>,
  markdown: string | null | undefined,
): Record<string, FieldValue> {
  if (!markdown) return values;
  const rows = c1MarkdownRows(markdown);
  const filled = { ...values };
  const slots: [keyof C1HeadlineTotals, string][] = [
    ["applied", "C.103"],
    ["admitted", "C.106"],
    ["enrolled", "C.109"],
  ];
  for (const [stage, id] of slots) {
    const value = rows.third[stage];
    if (value != null && value > 0 && fieldNumber(values, id) == null) {
      filled[id] = { value: String(value), source: "markdown_c1_row" };
    }
  }
  if (!rows.hasDirectSexEnrolled) {
    const parts: [string, string, number | null][] = [
      ["C.107", "C.111", rows.partTimeMen],
      ["C.108", "C.113", rows.partTimeWomen],
    ];
    for (const [total, partTimeId, partTimeRow] of parts) {
      const pt = fieldNumber(values, partTimeId) ?? partTimeRow;
      if (pt != null && pt > 0 && fieldNumber(values, total) != null) {
        filled[total] = addTo(values, total, pt);
      }
    }
  }
  return filled;
}

export type C1Reading =
  | { template: C1Template; totals: C1HeadlineTotals; reason?: undefined }
  | { template: null; totals: null; reason: string };

/**
 * Headline C1 counts for display: picks the numbering the artifact uses,
 * recovers third-category rows from the markdown, and drops any stage whose
 * men + women sum is incomplete. Year pages and the acceptance history both
 * read through here so the two never disagree.
 */
export function readC1Totals({
  values,
  schemaVersion,
  producer,
  yearStart,
  markdown,
}: {
  values: Record<string, FieldValue>;
  schemaVersion: string | null | undefined;
  producer: string | null | undefined;
  yearStart: number | null | undefined;
  markdown?: string | null;
}): C1Reading {
  const mapping = c1TemplateForArtifact({ schemaVersion, producer, yearStart });
  if (!mapping.template) return { template: null, totals: null, reason: mapping.reason };
  const read = mapping.template === "2025-26" ? withMarkdownC1Rows(values, markdown) : values;
  const totals = c1HeadlineTotals(read, mapping.template);
  const unreliable = c1UnreliableSums(read, mapping.template);
  const unconfirmed = unconfirmedSums(read, mapping.template, Boolean(markdown));
  if (mapping.template === "2025-26" && markdown && !usesPublishedTotal(read, headlineSpecs("2025-26").enrolled)) {
    // Full-/part-time-only layouts sometimes lose the table's last row: one
    // part-time row read, the other missing entirely. (When both are
    // missing the rows were blank or zero in the files checked.)
    const rows = c1MarkdownRows(markdown);
    if (!rows.hasDirectSexEnrolled) {
      const men = rows.partTimeRows.men || fieldNumber(values, "C.111") != null;
      const women = rows.partTimeRows.women || fieldNumber(values, "C.113") != null;
      if (men !== women) unconfirmed.enrolled = true;
    }
  }
  return {
    template: mapping.template,
    totals: {
      applied: unreliable.applied || unconfirmed.applied ? null : totals.applied,
      admitted: unreliable.admitted || unconfirmed.admitted ? null : totals.admitted,
      enrolled: unreliable.enrolled || unconfirmed.enrolled ? null : totals.enrolled,
    },
  };
}

// Beyond men and women, each group (one category, any of its full-/part-time
// cells) must be present for a sum to count as complete.
const THIRD_CATEGORY_IDS: Record<C1Template, Record<keyof C1HeadlineTotals, string[][]>> = {
  "2023-24": { applied: [["C.103"]], admitted: [["C.107"]], enrolled: [["C.113", "C.114"]] },
  "2024-25": {
    applied: [["C.103"], ["C.104"]],
    admitted: [["C.107"], ["C.108"]],
    enrolled: [["C.113", "C.114"], ["C.115", "C.116"]],
  },
  "2025-26": { applied: [["C.103"]], admitted: [["C.106"]], enrolled: [["C.109"]] },
};

function usesPublishedTotal(values: Record<string, FieldValue>, spec: HeadlineSpec): boolean {
  const published = fieldNumber(values, spec.total);
  return published != null && published > 0 && preferCoherentTotal(values, spec) === published;
}

/**
 * A men + women sum is only complete if the third category was read too.
 * Without the markdown to check, and with no third-category cell present,
 * the sum may silently leave out another-gender or unknown counts (the
 * AcroForm NON_BINARY fields, for one), so it is not shown.
 */
function unconfirmedSums(
  values: Record<string, FieldValue>,
  template: C1Template,
  hasMarkdown: boolean,
): C1UnreliableSums {
  const specs = headlineSpecs(template);
  const check = (stage: keyof C1HeadlineTotals): boolean => {
    if (usesPublishedTotal(values, specs[stage])) return false;
    if (hasMarkdown) return false;
    return !THIRD_CATEGORY_IDS[template][stage].every((group) =>
      group.some((id) => fieldNumber(values, id) != null),
    );
  };
  return { applied: check("applied"), admitted: check("admitted"), enrolled: check("enrolled") };
}

const SPLIT_GAP_MIN = 20;

export type C1UnreliableSums = { applied: boolean; admitted: boolean; enrolled: boolean };

/**
 * Stages whose headline number is a men + women sum that cannot be trusted:
 * - one side is missing or zero while a neighboring stage has at least
 *   SPLIT_GAP_MIN of that sex (400 women admitted, no women applied), or
 * - the men and women cells are identical at this stage and another one,
 *   the signature of one column read twice (seen at women's colleges).
 * Stages that use the school's own published total are never flagged. Only
 * the 2025-26 numbering is checked; the older extracts that rely on sums
 * all use it.
 */
export function c1UnreliableSums(
  values: Record<string, FieldValue>,
  template: C1Template,
): C1UnreliableSums {
  if (template !== "2025-26") return { applied: false, admitted: false, enrolled: false };
  const specs = headlineSpecs(template);
  const stages = [
    { spec: specs.applied, ids: ["C.101", "C.102"] },
    { spec: specs.admitted, ids: ["C.104", "C.105"] },
    { spec: specs.enrolled, ids: ["C.107", "C.108"] },
  ];
  const sides = stages.map(({ ids }) => ids.map((id) => fieldNumber(values, id)));
  const duplicated = sides.map(([men, women]) => men != null && men > 0 && men === women);
  const duplicatedStages = duplicated.filter(Boolean).length;

  const flagged = (stage: number): boolean => {
    if (usesPublishedTotal(values, stages[stage].spec)) return false;
    if (duplicated[stage] && duplicatedStages >= 2) return true;
    return [0, 1].some((side) => {
      const here = sides[stage][side];
      if (here != null && here !== 0) return false;
      return [stage - 1, stage + 1].some((neighbor) => {
        const count = sides[neighbor]?.[side];
        return count != null && count >= SPLIT_GAP_MIN;
      });
    });
  };
  return { applied: flagged(0), admitted: flagged(1), enrolled: flagged(2) };
}
