import {
  compareSchools,
  getSchoolFacts,
  getSchoolSources,
  publicFieldDefinitions,
  searchSchools,
  type PublicFactCategory,
} from "@/lib/public-data";
import {
  parseCompareFactCategories,
  parsePublicFactCategories,
} from "@/lib/public-fact-category";
import { MCP_TOOL_NAMES, type McpToolName } from "./tools";

export class McpToolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "McpToolError";
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new McpToolError(`${label} is required.`);
  }
  return value.trim();
}

function schoolIds(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

export async function callMcpTool(name: string, rawArgs: unknown): Promise<unknown> {
  if (!(MCP_TOOL_NAMES as readonly string[]).includes(name)) {
    throw new McpToolError(`Unknown tool: ${name}`);
  }
  const args = asRecord(rawArgs);
  const tool = name as McpToolName;

  if (tool === "search_schools") {
    const query = requiredString(args.query, "query");
    const limit = typeof args.limit === "number" ? args.limit : Number(args.limit ?? 10);
    return searchSchools(query, Number.isFinite(limit) ? limit : 10);
  }

  if (tool === "get_school_facts") {
    const schoolId = requiredString(args.school_id, "school_id");
    const rawCategories = typeof args.categories === "string" ? args.categories : null;
    const categories = parsePublicFactCategories(rawCategories);
    if (rawCategories !== null && categories?.length === 0) {
      throw new McpToolError("Pass at least one recognized public fact category.");
    }
    const payload = await getSchoolFacts(schoolId, { categories });
    if (!payload) {
      throw new McpToolError(
        "No public CollegeData.FYI school, CDS, or federal baseline row was found for this school_id.",
      );
    }
    return payload;
  }

  if (tool === "compare_schools") {
    const ids = schoolIds(args.school_ids);
    if (ids.length === 0) {
      throw new McpToolError("Pass one or more canonical school IDs.");
    }
    const rawCategories = typeof args.categories === "string" ? args.categories : null;
    const { categories, unsupported } = parseCompareFactCategories(rawCategories);
    if (rawCategories !== null && categories?.length === 0) {
      throw new McpToolError("Pass at least one recognized public fact category.");
    }
    if (unsupported.length > 0) {
      throw new McpToolError(
        "Finance facts are available from get_school_facts, not compare_schools.",
      );
    }
    const fields =
      typeof args.fields === "string"
        ? args.fields.split(",").map((field) => field.trim()).filter(Boolean)
        : undefined;
    return compareSchools(ids, { categories, fields });
  }

  if (tool === "get_source_documents") {
    const schoolId = requiredString(args.school_id, "school_id");
    const payload = await getSchoolSources(schoolId);
    if (!payload) {
      throw new McpToolError("No public source ledger is available for this school_id.");
    }
    return payload;
  }

  const category =
    typeof args.category === "string" ? (args.category as PublicFactCategory) : null;
  const fields = publicFieldDefinitions().filter((field) =>
    category ? field.category === category : true,
  );
  return {
    generated_at: new Date().toISOString(),
    fields,
  };
}
