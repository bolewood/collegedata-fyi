export const MCP_SERVER_NAME = "collegedata-fyi";
export const MCP_SERVER_VERSION = "0.2.0";
export const MCP_INSTRUCTIONS =
  "Read-only CollegeData.FYI tools. Preserve source metadata when citing values. Do not blend CDS, IPEDS, and Scorecard numbers without naming the source layer.";

export const FACT_CATEGORIES =
  "identity, admissions, enrollment, cost, aid, finance, outcomes, sources";
export const COMPARE_CATEGORIES =
  "identity, admissions, enrollment, cost, aid, outcomes, sources";

export const MCP_TOOL_NAMES = [
  "search_schools",
  "get_school_facts",
  "compare_schools",
  "get_source_documents",
  "get_field_dictionary",
] as const;

export type McpToolName = (typeof MCP_TOOL_NAMES)[number];

export const MCP_TOOLS = [
  {
    name: "search_schools",
    description: "Find canonical CollegeData.FYI school IDs by name, alias, city, or state.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string" },
        limit: { type: "number" },
      },
      required: ["query"],
    },
  },
  {
    name: "get_school_facts",
    description:
      "Get source-labeled CollegeData.FYI facts for one school. Preserve source metadata when citing values.",
    inputSchema: {
      type: "object",
      properties: {
        school_id: { type: "string" },
        categories: {
          type: "string",
          description: `Optional comma-separated categories. Valid: ${FACT_CATEGORIES}. Use "finance" for endowment values and spending (IPEDS Part H, fiscal years 2020+). Unknown categories are silently ignored.`,
        },
      },
      required: ["school_id"],
    },
  },
  {
    name: "compare_schools",
    description: "Compare schools across source-labeled fact categories. Missing values are explicit nulls.",
    inputSchema: {
      type: "object",
      properties: {
        school_ids: { type: "array", items: { type: "string" } },
        categories: {
          type: "string",
          description: `Optional comma-separated categories. Valid for compare: ${COMPARE_CATEGORIES}. The finance category is facts-only; use get_school_facts for endowment data.`,
        },
        fields: { type: "string" },
      },
      required: ["school_ids"],
    },
  },
  {
    name: "get_source_documents",
    description:
      "Get source documents, archive URLs, federal release metadata, and coverage status for one school.",
    inputSchema: {
      type: "object",
      properties: { school_id: { type: "string" } },
      required: ["school_id"],
    },
  },
  {
    name: "get_field_dictionary",
    description:
      "List friendly fact field definitions, including federal endowment fields (category: finance).",
    inputSchema: {
      type: "object",
      properties: {
        category: {
          type: "string",
          description: `Optional single-category filter. Valid: ${FACT_CATEGORIES}.`,
        },
      },
    },
  },
] as const;

export const SUPPORTED_PROTOCOL_VERSIONS = [
  "2024-11-05",
  "2025-03-26",
  "2025-06-18",
  "2025-11-25",
  "2026-07-28",
] as const;

export const DEFAULT_PROTOCOL_VERSION = "2025-03-26";

export function negotiateProtocolVersion(requested: unknown): string {
  if (typeof requested === "string" && (SUPPORTED_PROTOCOL_VERSIONS as readonly string[]).includes(requested)) {
    return requested;
  }
  return DEFAULT_PROTOCOL_VERSION;
}
