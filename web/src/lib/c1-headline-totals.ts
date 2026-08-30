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
  }

  if (total != null && total > 0) return total;
  if (gender) return gender.sum;
  return total;
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
