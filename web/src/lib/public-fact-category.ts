import type { SchoolFactUnifiedRow } from "./types";

export type PublicFactCategory =
  | "identity"
  | "admissions"
  | "enrollment"
  | "cost"
  | "aid"
  | "finance"
  | "outcomes"
  | "sources";

const PUBLIC_FACT_CATEGORIES = new Set<PublicFactCategory>([
  "identity",
  "admissions",
  "enrollment",
  "cost",
  "aid",
  "finance",
  "outcomes",
  "sources",
]);

const COMPARE_FACT_CATEGORIES = new Set<PublicFactCategory>([
  "identity",
  "admissions",
  "enrollment",
  "cost",
  "aid",
  "outcomes",
  "sources",
]);

export function parsePublicFactCategories(
  value: string | null,
): PublicFactCategory[] | undefined {
  if (value === null) return undefined;
  return value
    .split(",")
    .map((part) => part.trim())
    .filter((part): part is PublicFactCategory =>
      PUBLIC_FACT_CATEGORIES.has(part as PublicFactCategory),
    );
}

export function parseCompareFactCategories(value: string | null): {
  categories: PublicFactCategory[] | undefined;
  unsupported: PublicFactCategory[];
} {
  const categories = parsePublicFactCategories(value);
  return {
    categories,
    unsupported: categories?.filter((category) => !COMPARE_FACT_CATEGORIES.has(category)) ?? [],
  };
}

export function federalCategory(
  row: Pick<SchoolFactUnifiedRow, "display_group" | "field_key" | "field_label">,
): PublicFactCategory {
  const group = `${row.display_group} ${row.field_key} ${row.field_label}`.toLowerCase();
  if (group.includes("endowment") || group.includes("finance")) return "finance";
  if (group.includes("admission")) return "admissions";
  if (group.includes("cost") || group.includes("price") || group.includes("tuition")) return "cost";
  if (group.includes("aid") || group.includes("loan") || group.includes("pell")) return "aid";
  if (group.includes("completion") || group.includes("graduation") || group.includes("outcome")) return "outcomes";
  if (group.includes("enrollment")) return "enrollment";
  return "identity";
}
