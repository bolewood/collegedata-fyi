import { NextResponse } from "next/server";
import { selectableFactKeys } from "@/lib/public-data";

export const revalidate = 3600;

const FACT_CATEGORIES = "identity, admissions, enrollment, cost, aid, finance, outcomes, sources";
const CLIENT_HEADER = {
  name: "X-CollegeData-Client",
  in: "header",
  required: false,
  schema: { type: "string" },
  description: "Short app name (for example my-app-name). Optional. Helps us count API usage by client; no API key is required.",
};

const ERROR_RESPONSE = {
  content: {
    "application/json": {
      schema: {
        type: "object",
        required: ["error"],
        properties: { error: { type: "string" }, message: { type: "string" } },
      },
    },
  },
};

const REDIRECT_RESPONSE = {
  description:
    "308 redirect to the same endpoint under the canonical school_id, when the requested slug is an alias. Follow redirects.",
  headers: { Location: { schema: { type: "string" } } },
};

const COMPARE_CATEGORIES = "identity, admissions, enrollment, cost, aid, outcomes, sources";

export async function GET() {
  const factKeys = selectableFactKeys();
  return NextResponse.json(
    {
      openapi: "3.1.0",
      info: {
        title: "CollegeData.FYI friendly API",
        version: "0.2.0",
        description:
          "Task-oriented, no-auth JSON endpoints for source-linked college facts, school search, comparisons, sources, and field definitions.",
      },
      servers: [{ url: "https://www.collegedata.fyi" }],
      paths: {
        "/api/schools/search": {
          get: {
            summary: "Search schools",
            parameters: [
              CLIENT_HEADER,
              { name: "q", in: "query", required: false, schema: { type: "string" }, description: "Name or alias. Required unless ipeds_id is given." },
              { name: "ipeds_id", in: "query", required: false, schema: { type: "string", pattern: "^\\d{6}$" }, description: "Exact lookup by six-digit IPEDS unit id. Takes precedence over q." },
              { name: "limit", in: "query", required: false, schema: { type: "integer", minimum: 1, maximum: 25, default: 10 } },
            ],
            responses: {
              "200": { description: "School search results" },
              "400": { description: "Missing q (error: missing_query) or malformed ipeds_id (error: invalid_ipeds_id)", ...ERROR_RESPONSE },
            },
          },
        },
        "/api/schools/{school_id}/facts": {
          get: {
            summary: "Get source-labeled school facts",
            parameters: [
              CLIENT_HEADER,
              { name: "school_id", in: "path", required: true, schema: { type: "string" } },
              {
                name: "categories",
                in: "query",
                required: false,
                schema: {
                  type: "string",
                  description: `Comma-separated categories. Valid: ${FACT_CATEGORIES}. Use finance for endowment values and spending (IPEDS Part H, fiscal years 2020+); unknown categories are ignored.`,
                },
              },
              {
                name: "fields",
                in: "query",
                required: false,
                schema: { type: "string", description: `Comma-separated field keys. V1 keys include: ${factKeys.join(", ")}` },
              },
            ],
            responses: {
              "200": {
                description: "Facts with provenance",
                content: {
                  "application/json": {
                    schema: {
                      type: "object",
                      additionalProperties: true,
                      properties: {
                        school_id: { type: "string" },
                        facts: { type: "array", items: { $ref: "#/components/schemas/PublicFact" } },
                      },
                    },
                  },
                },
              },
              "308": REDIRECT_RESPONSE,
              "400": { description: "No recognized categories (error: invalid_categories)", ...ERROR_RESPONSE },
              "404": { description: "Unknown school (error: school_not_found)", ...ERROR_RESPONSE },
            },
          },
        },
        "/api/schools/{school_id}/sources": {
          get: {
            summary: "Get source ledger for a school",
            parameters: [CLIENT_HEADER, { name: "school_id", in: "path", required: true, schema: { type: "string" } }],
            responses: {
              "200": { description: "Source ledger" },
              "308": REDIRECT_RESPONSE,
              "404": { description: "Unknown school", ...ERROR_RESPONSE },
            },
          },
        },
        "/api/compare": {
          get: {
            summary: "Compare schools across friendly fact fields",
            parameters: [
              CLIENT_HEADER,
              {
                name: "schools",
                in: "query",
                required: true,
                schema: { type: "string", description: "Comma-separated canonical school IDs. At most 25 are read; extras are ignored." },
              },
              {
                name: "categories",
                in: "query",
                required: false,
                schema: {
                  type: "string",
                  description: `Comma-separated categories. Valid for compare: ${COMPARE_CATEGORIES}. The finance category is facts-only (per-school endpoint), not comparable.`,
                },
              },
              { name: "fields", in: "query", required: false, schema: { type: "string" } },
            ],
            responses: {
              "200": { description: "Sparse comparison matrix" },
              "400": {
                description: "missing_schools, invalid_categories, or unsupported_categories (finance is not comparable)",
                ...ERROR_RESPONSE,
              },
            },
          },
        },
        "/api/facts/{school_id}": {
          get: {
            summary: "Flat quick-citation facts for one school (deprecated)",
            deprecated: true,
            description:
              "Deprecated: use /api/schools/{school_id}/facts. Flat summary of the most recent extracted Common Data Set filing (applied, admitted, acceptance rate, source URLs). Some fields are read from fixed question numbers and can be null or wrong for some schools and years.",
            parameters: [CLIENT_HEADER, { name: "school_id", in: "path", required: true, schema: { type: "string" } }],
            responses: {
              "200": {
                description: "Flat fact object",
                content: {
                  "application/json": {
                    schema: {
                      type: "object",
                      additionalProperties: true,
                      properties: {
                        school_id: { type: "string" },
                        school_name: { type: "string" },
                        cds_year: { oneOf: [{ type: "string" }, { type: "null" }] },
                        applied: { oneOf: [{ type: "integer" }, { type: "null" }] },
                        admitted: { oneOf: [{ type: "integer" }, { type: "null" }] },
                        acceptance_rate_pct: { oneOf: [{ type: "number" }, { type: "null" }] },
                        source_url: { oneOf: [{ type: "string" }, { type: "null" }] },
                        archive_url: { type: "string" },
                        raw: { type: "object", additionalProperties: true },
                      },
                    },
                  },
                },
              },
              "308": REDIRECT_RESPONSE,
              "404": { description: "No extracted filing (error: school_not_found_or_not_extracted)", ...ERROR_RESPONSE },
            },
          },
        },
        "/api/mcp": {
          post: {
            summary: "MCP Streamable HTTP endpoint",
            description:
              "JSON-RPC MCP server. Paste https://www.collegedata.fyi/api/mcp as a Claude custom connector. No API key.",
            requestBody: {
              required: true,
              content: {
                "application/json": {
                  schema: { type: "object", additionalProperties: true },
                },
              },
            },
            responses: { "200": { description: "JSON-RPC result" } },
          },
        },
        "/api/fields": {
          get: {
            summary: "List V1 friendly field definitions",
            parameters: [
              {
                name: "category",
                in: "query",
                required: false,
                schema: { type: "string", description: `Single category filter. Valid: ${FACT_CATEGORIES}.` },
              },
            ],
            responses: { "200": { description: "Field dictionary" } },
          },
        },
        "/api/snapshots": {
          get: {
            summary: "List public snapshot files",
            description:
              "Links to schools.jsonl, school_facts.jsonl, sources.jsonl, and field_dictionary.json. Files are usually regenerated from live data within the hour (check generated_at); the dated path is an alias, not a frozen copy.",
            responses: { "200": { description: "Snapshot manifest links" } },
          },
        },
      },
      components: {
        schemas: {
          PublicFact: {
            type: "object",
            additionalProperties: true,
            required: ["key", "label", "value", "display_value", "unit", "category", "source", "quality"],
            properties: {
              key: { type: "string" },
              label: { type: "string" },
              value: { oneOf: [{ type: "string" }, { type: "number" }, { type: "boolean" }, { type: "null" }] },
              display_value: { type: "string" },
              unit: { oneOf: [{ type: "string" }, { type: "null" }] },
              category: { type: "string" },
              source: { oneOf: [{ type: "object", additionalProperties: true }, { type: "null" }] },
              quality: {
                type: "object",
                properties: {
                  flag: { type: "string" },
                  note: { oneOf: [{ type: "string" }, { type: "null" }] },
                },
              },
            },
          },
        },
      },
    },
    {
      headers: {
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    },
  );
}
