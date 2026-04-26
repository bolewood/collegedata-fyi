import { assertEquals, assertThrows } from "jsr:@std/assert";

import {
  filterMatches,
  isRequiredOperator,
  searchBrowserRows,
  type BrowserRow,
} from "./browser_search.ts";

function row(overrides: Partial<BrowserRow>): BrowserRow {
  return {
    document_id: "00000000-0000-0000-0000-000000000001",
    school_id: "example",
    school_name: "Example College",
    sub_institutional: null,
    ipeds_id: "123456",
    canonical_year: "2024-25",
    year_start: 2024,
    schema_version: "2025-26",
    source_format: "pdf_fillable",
    producer: "tier2_acroform",
    producer_version: "0.1.0",
    data_quality_flag: null,
    archive_url: "https://www.collegedata.fyi/schools/example/2024-25",
    applied: null,
    admitted: null,
    enrolled_first_year: null,
    acceptance_rate: null,
    yield_rate: null,
    undergrad_enrollment_scorecard: null,
    scorecard_data_year: null,
    retention_rate: null,
    avg_net_price: null,
    pell_rate: null,
    ...overrides,
  };
}

Deno.test("required fields derive from operators", () => {
  assertEquals(isRequiredOperator("="), true);
  assertEquals(isRequiredOperator("!="), true);
  assertEquals(isRequiredOperator(">"), true);
  assertEquals(isRequiredOperator(">="), true);
  assertEquals(isRequiredOperator("<"), true);
  assertEquals(isRequiredOperator("<="), true);
  assertEquals(isRequiredOperator("is not blank"), true);
  assertEquals(isRequiredOperator("is blank"), false);
});

Deno.test("latest-per-school chooses newest row with required fields populated", () => {
  const result = searchBrowserRows(
    [
      row({
        document_id: "00000000-0000-0000-0000-000000000025",
        canonical_year: "2025-26",
        year_start: 2025,
        applied: 100,
        admitted: 20,
        enrolled_first_year: null,
      }),
      row({
        document_id: "00000000-0000-0000-0000-000000000024",
        canonical_year: "2024-25",
        year_start: 2024,
        applied: 90,
        admitted: 18,
        enrolled_first_year: 9,
      }),
    ],
    {
      filters: [{ field: "enrolled_first_year", op: ">=", value: 1 }],
      columns: ["document_id", "canonical_year", "enrolled_first_year"],
    },
  );

  assertEquals(result.metadata.schools_in_scope, 1);
  assertEquals(result.metadata.schools_with_required_fields, 1);
  assertEquals(result.rows, [
    {
      document_id: "00000000-0000-0000-0000-000000000024",
      canonical_year: "2024-25",
      enrolled_first_year: 9,
    },
  ]);
});

Deno.test("primary_only excludes sub-institutional variants by default", () => {
  const result = searchBrowserRows(
    [
      row({ school_id: "columbia", school_name: "Columbia", sub_institutional: null, applied: 100 }),
      row({
        document_id: "00000000-0000-0000-0000-000000000002",
        school_id: "columbia",
        school_name: "Columbia GS",
        sub_institutional: "general-studies",
        applied: 200,
      }),
    ],
    {
      filters: [{ field: "applied", op: ">=", value: 1 }],
      columns: ["school_id", "sub_institutional", "applied"],
    },
  );

  assertEquals(result.metadata.schools_in_scope, 1);
  assertEquals(result.rows, [{ school_id: "columbia", sub_institutional: null, applied: 100 }]);
});

Deno.test("include_variants ranks per school and sub-institutional identity", () => {
  const result = searchBrowserRows(
    [
      row({ school_id: "columbia", school_name: "Columbia", sub_institutional: null, applied: 100 }),
      row({
        document_id: "00000000-0000-0000-0000-000000000002",
        school_id: "columbia",
        school_name: "Columbia GS",
        sub_institutional: "general-studies",
        applied: 200,
      }),
    ],
    {
      variant_scope: "include_variants",
      filters: [{ field: "applied", op: ">=", value: 1 }],
      columns: ["school_id", "sub_institutional", "applied"],
      sort: { field: "applied", direction: "asc" },
    },
  );

  assertEquals(result.metadata.schools_in_scope, 2);
  assertEquals(result.rows, [
    { school_id: "columbia", sub_institutional: null, applied: 100 },
    { school_id: "columbia", sub_institutional: "general-studies", applied: 200 },
  ]);
});

Deno.test("is blank does not count as required for answerability", () => {
  const result = searchBrowserRows(
    [
      row({
        document_id: "00000000-0000-0000-0000-000000000025",
        canonical_year: "2025-26",
        year_start: 2025,
        avg_net_price: null,
      }),
    ],
    {
      filters: [{ field: "avg_net_price", op: "is blank" }],
      columns: ["avg_net_price"],
    },
  );

  assertEquals(result.metadata.required_fields, []);
  assertEquals(result.metadata.schools_missing_required_fields, 0);
  assertEquals(result.rows, [{ avg_net_price: null }]);
});

Deno.test("not-equals does not match null", () => {
  const blank = row({ avg_net_price: null });
  assertEquals(filterMatches(blank, { field: "avg_net_price", op: "!=", value: 30000 }), false);
  assertEquals(filterMatches(blank, { field: "avg_net_price", op: "!=", value: null }), false);
});

Deno.test("unsupported fields are rejected", () => {
  assertThrows(
    () => searchBrowserRows([row({})], { filters: [{ field: "made_up", op: "=", value: 1 }] }),
    Error,
    "unsupported filter field",
  );
});
