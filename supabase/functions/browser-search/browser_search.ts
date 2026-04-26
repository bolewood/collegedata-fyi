export type BrowserMode = "latest_per_school" | "all_school_years";
export type VariantScope = "primary_only" | "include_variants";
export type FilterOperator =
  | "="
  | "!="
  | ">"
  | ">="
  | "<"
  | "<="
  | "is blank"
  | "is not blank";

export type BrowserRow = {
  document_id: string;
  school_id: string;
  school_name: string;
  sub_institutional: string | null;
  ipeds_id: string | null;
  canonical_year: string;
  year_start: number;
  schema_version: string;
  source_format: string | null;
  producer: string;
  producer_version: string | null;
  data_quality_flag: string | null;
  archive_url: string;
  applied: number | null;
  admitted: number | null;
  enrolled_first_year: number | null;
  acceptance_rate: number | string | null;
  yield_rate: number | string | null;
  undergrad_enrollment_scorecard: number | null;
  scorecard_data_year: string | null;
  retention_rate: number | string | null;
  avg_net_price: number | null;
  pell_rate: number | string | null;
};

export type BrowserFilter = {
  field: string;
  op: FilterOperator;
  value?: unknown;
};

export type BrowserSearchRequest = {
  mode?: BrowserMode;
  variant_scope?: VariantScope;
  min_year_start?: number;
  filters?: BrowserFilter[];
  columns?: string[];
  sort?: { field: string; direction?: "asc" | "desc" };
  page?: number;
  page_size?: number;
};

export type BrowserSearchResponse = {
  metadata: {
    mode: BrowserMode;
    variant_scope: VariantScope;
    min_year_start: number;
    required_fields: string[];
    schools_in_scope: number;
    schools_with_required_fields: number;
    schools_missing_required_fields: number;
    schools_failing_filters: number;
    total_rows: number;
    rows_returned: number;
    page: number;
    page_size: number;
  };
  rows: Record<string, unknown>[];
};

const OPERATORS = new Set<FilterOperator>([
  "=",
  "!=",
  ">",
  ">=",
  "<",
  "<=",
  "is blank",
  "is not blank",
]);

export const ALLOWED_FIELDS = new Set([
  "document_id",
  "school_id",
  "school_name",
  "sub_institutional",
  "ipeds_id",
  "canonical_year",
  "year_start",
  "schema_version",
  "source_format",
  "producer",
  "producer_version",
  "data_quality_flag",
  "archive_url",
  "applied",
  "admitted",
  "enrolled_first_year",
  "acceptance_rate",
  "yield_rate",
  "undergrad_enrollment_scorecard",
  "scorecard_data_year",
  "retention_rate",
  "avg_net_price",
  "pell_rate",
]);

const NUMERIC_FIELDS = new Set([
  "year_start",
  "applied",
  "admitted",
  "enrolled_first_year",
  "acceptance_rate",
  "yield_rate",
  "undergrad_enrollment_scorecard",
  "retention_rate",
  "avg_net_price",
  "pell_rate",
]);

export function isRequiredOperator(op: FilterOperator): boolean {
  return op !== "is blank";
}

export function requiredFields(filters: BrowserFilter[]): string[] {
  return Array.from(
    new Set(filters.filter((filter) => isRequiredOperator(filter.op)).map((filter) => filter.field)),
  );
}

export function isPopulated(row: BrowserRow, field: string): boolean {
  const value = row[field as keyof BrowserRow];
  return value !== null && value !== undefined && value !== "";
}

export function filterMatches(row: BrowserRow, filter: BrowserFilter): boolean {
  const { field, op } = filter;
  const populated = isPopulated(row, field);
  const current = row[field as keyof BrowserRow] as unknown;

  if (op === "is blank") return !populated;
  if (op === "is not blank") return populated;
  if (!populated) return false;

  // SQL-style three-valued logic for MVP browser filters: `field != NULL`
  // does not satisfy the predicate. Users who want blankness must use
  // `is blank` / `is not blank`.
  if (filter.value === null || filter.value === undefined) return false;

  if (NUMERIC_FIELDS.has(field)) {
    const left = Number(current);
    const right = Number(filter.value);
    if (!Number.isFinite(left) || !Number.isFinite(right)) return false;
    switch (op) {
      case "=":
        return left === right;
      case "!=":
        return left !== right;
      case ">":
        return left > right;
      case ">=":
        return left >= right;
      case "<":
        return left < right;
      case "<=":
        return left <= right;
    }
  }

  const left = String(current);
  const right = String(filter.value);
  switch (op) {
    case "=":
      return left === right;
    case "!=":
      return left !== right;
    case ">":
      return left > right;
    case ">=":
      return left >= right;
    case "<":
      return left < right;
    case "<=":
      return left <= right;
  }
}

export function searchBrowserRows(rows: BrowserRow[], input: BrowserSearchRequest): BrowserSearchResponse {
  const request = normalizeRequest(input);
  const filters = request.filters ?? [];
  const required = requiredFields(filters);
  const candidates = rows.filter((row) => {
    if (row.year_start < request.min_year_start!) return false;
    if (request.variant_scope === "primary_only" && row.sub_institutional !== null) return false;
    return true;
  });

  const evaluated = request.mode === "latest_per_school"
    ? pickLatestRows(candidates, required, request.variant_scope!)
    : candidates.map((row) => ({ row, hasRequired: hasAllRequired(row, required) }));

  const withRequired = evaluated.filter((item) => item.hasRequired);
  const passing = evaluated.filter((item) => {
    if (!item.hasRequired) return false;
    return filters.every((filter) => filterMatches(item.row, filter));
  });

  const sorted = sortRows(passing.map((item) => item.row), request.sort?.field, request.sort?.direction);
  const page = request.page!;
  const pageSize = request.page_size!;
  const start = (page - 1) * pageSize;
  const pageRows = sorted.slice(start, start + pageSize);
  const projectedRows = pageRows.map((row) => projectColumns(row, request.columns));

  return {
    metadata: {
      mode: request.mode!,
      variant_scope: request.variant_scope!,
      min_year_start: request.min_year_start!,
      required_fields: required,
      schools_in_scope: evaluated.length,
      schools_with_required_fields: withRequired.length,
      schools_missing_required_fields: evaluated.length - withRequired.length,
      schools_failing_filters: withRequired.length - passing.length,
      total_rows: passing.length,
      rows_returned: projectedRows.length,
      page,
      page_size: pageSize,
    },
    rows: projectedRows,
  };
}

function normalizeRequest(input: BrowserSearchRequest): Required<BrowserSearchRequest> {
  const mode = input.mode ?? "latest_per_school";
  if (mode !== "latest_per_school" && mode !== "all_school_years") {
    throw new Error("mode must be latest_per_school or all_school_years");
  }
  const variantScope = input.variant_scope ?? "primary_only";
  if (variantScope !== "primary_only" && variantScope !== "include_variants") {
    throw new Error("variant_scope must be primary_only or include_variants");
  }
  const minYear = input.min_year_start ?? 2024;
  if (!Number.isInteger(minYear) || minYear < 2024) {
    throw new Error("min_year_start must be an integer >= 2024");
  }
  const filters = input.filters ?? [];
  for (const filter of filters) {
    if (!ALLOWED_FIELDS.has(filter.field)) {
      throw new Error(`unsupported filter field: ${filter.field}`);
    }
    if (!OPERATORS.has(filter.op)) {
      throw new Error(`unsupported filter operator: ${filter.op}`);
    }
  }
  const columns = input.columns && input.columns.length > 0
    ? input.columns
    : [
      "document_id",
      "school_id",
      "school_name",
      "sub_institutional",
      "canonical_year",
      "applied",
      "admitted",
      "enrolled_first_year",
      "acceptance_rate",
      "yield_rate",
      "undergrad_enrollment_scorecard",
      "avg_net_price",
      "source_format",
      "data_quality_flag",
      "archive_url",
    ];
  for (const column of columns) {
    if (!ALLOWED_FIELDS.has(column)) {
      throw new Error(`unsupported column: ${column}`);
    }
  }
  const sort = input.sort ?? { field: "school_name", direction: "asc" as const };
  if (!ALLOWED_FIELDS.has(sort.field)) {
    throw new Error(`unsupported sort field: ${sort.field}`);
  }
  if (sort.direction && sort.direction !== "asc" && sort.direction !== "desc") {
    throw new Error("sort.direction must be asc or desc");
  }
  const page = input.page ?? 1;
  const pageSize = input.page_size ?? 50;
  if (!Number.isInteger(page) || page < 1) throw new Error("page must be >= 1");
  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 500) {
    throw new Error("page_size must be between 1 and 500");
  }

  return {
    mode,
    variant_scope: variantScope,
    min_year_start: minYear,
    filters,
    columns,
    sort: { field: sort.field, direction: sort.direction ?? "asc" },
    page,
    page_size: pageSize,
  };
}

function pickLatestRows(
  candidates: BrowserRow[],
  required: string[],
  variantScope: VariantScope,
): { row: BrowserRow; hasRequired: boolean }[] {
  const groups = new Map<string, BrowserRow[]>();
  for (const row of candidates) {
    const key = variantScope === "primary_only"
      ? row.school_id
      : `${row.school_id}\u0000${row.sub_institutional ?? ""}`;
    const group = groups.get(key) ?? [];
    group.push(row);
    groups.set(key, group);
  }

  const winners: { row: BrowserRow; hasRequired: boolean }[] = [];
  for (const group of groups.values()) {
    const ranked = [...group].sort((a, b) => {
      const aRequired = hasAllRequired(a, required);
      const bRequired = hasAllRequired(b, required);
      if (aRequired !== bRequired) return aRequired ? -1 : 1;
      if (a.year_start !== b.year_start) return b.year_start - a.year_start;
      const yearCmp = b.canonical_year.localeCompare(a.canonical_year);
      if (yearCmp !== 0) return yearCmp;
      return a.document_id.localeCompare(b.document_id);
    });
    const row = ranked[0];
    winners.push({ row, hasRequired: hasAllRequired(row, required) });
  }
  return winners;
}

function hasAllRequired(row: BrowserRow, required: string[]): boolean {
  return required.every((field) => isPopulated(row, field));
}

function sortRows(rows: BrowserRow[], field = "school_name", direction: "asc" | "desc" = "asc"): BrowserRow[] {
  const multiplier = direction === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const left = a[field as keyof BrowserRow] as unknown;
    const right = b[field as keyof BrowserRow] as unknown;
    const leftBlank = left === null || left === undefined || left === "";
    const rightBlank = right === null || right === undefined || right === "";
    if (leftBlank && rightBlank) return a.school_name.localeCompare(b.school_name);
    if (leftBlank) return 1;
    if (rightBlank) return -1;
    if (NUMERIC_FIELDS.has(field)) {
      const diff = Number(left) - Number(right);
      if (diff !== 0) return diff * multiplier;
    } else {
      const diff = String(left).localeCompare(String(right));
      if (diff !== 0) return diff * multiplier;
    }
    return a.school_name.localeCompare(b.school_name);
  });
}

function projectColumns(row: BrowserRow, columns: string[]): Record<string, unknown> {
  const projected: Record<string, unknown> = {};
  for (const column of columns) {
    projected[column] = row[column as keyof BrowserRow];
  }
  return projected;
}
