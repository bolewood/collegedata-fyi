export type BrowserMode = "latest_per_school" | "all_school_years";
export type VariantScope = "primary_only" | "include_variants";
export type BrowserOperator =
  | "="
  | "!="
  | ">"
  | ">="
  | "<"
  | "<="
  | "is blank"
  | "is not blank";

export type BrowserFilter = {
  field: BrowserField;
  op: BrowserOperator;
  value?: string | number | null;
};

export type BrowserField =
  | "document_id"
  | "school_id"
  | "school_name"
  | "sub_institutional"
  | "ipeds_id"
  | "canonical_year"
  | "year_start"
  | "schema_version"
  | "source_format"
  | "producer"
  | "producer_version"
  | "data_quality_flag"
  | "archive_url"
  | "applied"
  | "admitted"
  | "enrolled_first_year"
  | "acceptance_rate"
  | "yield_rate"
  | "undergrad_enrollment_scorecard"
  | "scorecard_data_year"
  | "retention_rate"
  | "avg_net_price"
  | "pell_rate"
  | "sat_submit_rate"
  | "act_submit_rate"
  | "sat_composite_p25"
  | "sat_composite_p50"
  | "sat_composite_p75"
  | "sat_ebrw_p25"
  | "sat_ebrw_p50"
  | "sat_ebrw_p75"
  | "sat_math_p25"
  | "sat_math_p50"
  | "sat_math_p75"
  | "act_composite_p25"
  | "act_composite_p50"
  | "act_composite_p75";

export type BrowserSort = {
  field: BrowserField;
  direction?: "asc" | "desc";
};

export type BrowserSearchRequest = {
  mode?: BrowserMode;
  variant_scope?: VariantScope;
  min_year_start?: number;
  filters?: BrowserFilter[];
  columns?: BrowserField[];
  sort?: BrowserSort;
  page?: number;
  page_size?: number;
};

export type BrowserSearchMetadata = {
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
  academic_profile_filters: {
    field: string;
    companion_submit_rate_field: string | null;
    companion_required_for_comparison: boolean;
    rows_with_value: number;
    rows_with_companion_submit_rate: number | null;
    rows_with_value_missing_companion_submit_rate: number | null;
  }[];
};

export type BrowserRow = {
  document_id: string;
  school_id: string;
  school_name: string;
  sub_institutional: string | null;
  canonical_year: string;
  applied: number | null;
  admitted: number | null;
  enrolled_first_year: number | null;
  acceptance_rate: number | null;
  yield_rate: number | null;
  undergrad_enrollment_scorecard: number | null;
  retention_rate: number | null;
  avg_net_price: number | null;
  pell_rate: number | null;
  sat_submit_rate: number | null;
  act_submit_rate: number | null;
  sat_composite_p25: number | null;
  sat_composite_p50: number | null;
  sat_composite_p75: number | null;
  sat_ebrw_p25: number | null;
  sat_ebrw_p50: number | null;
  sat_ebrw_p75: number | null;
  sat_math_p25: number | null;
  sat_math_p50: number | null;
  sat_math_p75: number | null;
  act_composite_p25: number | null;
  act_composite_p50: number | null;
  act_composite_p75: number | null;
  source_format: string | null;
  data_quality_flag: string | null;
  archive_url: string;
};

export type BrowserSearchResponse = {
  metadata: BrowserSearchMetadata;
  rows: BrowserRow[];
};

export const BROWSER_COLUMNS: BrowserField[] = [
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
  "retention_rate",
  "avg_net_price",
  "pell_rate",
  "sat_submit_rate",
  "act_submit_rate",
  "sat_composite_p25",
  "sat_composite_p50",
  "sat_composite_p75",
  "sat_ebrw_p25",
  "sat_ebrw_p50",
  "sat_ebrw_p75",
  "sat_math_p25",
  "sat_math_p50",
  "sat_math_p75",
  "act_composite_p25",
  "act_composite_p50",
  "act_composite_p75",
  "source_format",
  "data_quality_flag",
  "archive_url",
];

export async function searchBrowserRows(
  request: BrowserSearchRequest,
): Promise<BrowserSearchResponse> {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !anonKey) {
    throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY");
  }

  const response = await fetch(`${supabaseUrl}/functions/v1/browser-search`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      apikey: anonKey,
      authorization: `Bearer ${anonKey}`,
    },
    body: JSON.stringify({
      columns: BROWSER_COLUMNS,
      ...request,
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error ?? "Browser search failed");
  }

  return payload as BrowserSearchResponse;
}
