import { NextResponse } from "next/server";
import { publicFieldDefinitions } from "@/lib/public-data";

export const revalidate = 3600;

export async function GET() {
  const factKeys = publicFieldDefinitions().map((field) => field.key);
  return NextResponse.json(
    {
      openapi: "3.1.0",
      info: {
        title: "CollegeData.FYI friendly API",
        version: "0.1.0",
        description:
          "Task-oriented, no-auth JSON endpoints for source-linked college facts, school search, comparisons, sources, and field definitions.",
      },
      servers: [{ url: "https://www.collegedata.fyi" }],
      paths: {
        "/api/schools/search": {
          get: {
            summary: "Search schools",
            parameters: [
              { name: "q", in: "query", required: true, schema: { type: "string" } },
              { name: "limit", in: "query", required: false, schema: { type: "integer", minimum: 1, maximum: 25 } },
            ],
            responses: { "200": { description: "School search results" } },
          },
        },
        "/api/schools/{school_id}/facts": {
          get: {
            summary: "Get source-labeled school facts",
            parameters: [
              { name: "school_id", in: "path", required: true, schema: { type: "string" } },
              { name: "categories", in: "query", required: false, schema: { type: "string" } },
              {
                name: "fields",
                in: "query",
                required: false,
                schema: { type: "string", description: `Comma-separated field keys. V1 keys include: ${factKeys.join(", ")}` },
              },
            ],
            responses: { "200": { description: "Facts with provenance" }, "404": { description: "Unknown school" } },
          },
        },
        "/api/schools/{school_id}/sources": {
          get: {
            summary: "Get source ledger for a school",
            parameters: [{ name: "school_id", in: "path", required: true, schema: { type: "string" } }],
            responses: { "200": { description: "Source ledger" }, "404": { description: "Unknown school" } },
          },
        },
        "/api/compare": {
          get: {
            summary: "Compare schools across friendly fact fields",
            parameters: [
              { name: "schools", in: "query", required: true, schema: { type: "string" } },
              { name: "categories", in: "query", required: false, schema: { type: "string" } },
              { name: "fields", in: "query", required: false, schema: { type: "string" } },
            ],
            responses: { "200": { description: "Sparse comparison matrix" } },
          },
        },
        "/api/fields": {
          get: {
            summary: "List V1 friendly field definitions",
            parameters: [{ name: "category", in: "query", required: false, schema: { type: "string" } }],
            responses: { "200": { description: "Field dictionary" } },
          },
        },
        "/api/snapshots": {
          get: {
            summary: "List public snapshot files",
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

