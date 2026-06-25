#!/usr/bin/env node

const API_BASE = (process.env.COLLEGEDATA_API_BASE ?? "https://www.collegedata.fyi").replace(/\/$/, "");
const CLIENT_NAME = "mcp";
const CLIENT_VERSION = "0.1.0";

const tools = [
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
    description: "Get source-labeled CollegeData.FYI facts for one school. Preserve source metadata when citing values.",
    inputSchema: {
      type: "object",
      properties: {
        school_id: { type: "string" },
        categories: { type: "string", description: "Optional comma-separated categories." },
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
        categories: { type: "string" },
        fields: { type: "string" },
      },
      required: ["school_ids"],
    },
  },
  {
    name: "get_source_documents",
    description: "Get source documents, archive URLs, federal release metadata, and coverage status for one school.",
    inputSchema: {
      type: "object",
      properties: { school_id: { type: "string" } },
      required: ["school_id"],
    },
  },
  {
    name: "get_field_dictionary",
    description: "List V1 friendly fact field definitions.",
    inputSchema: {
      type: "object",
      properties: { category: { type: "string" } },
    },
  },
];

function withClientParams(path, toolName) {
  const url = new URL(path, "https://collegedata.fyi");
  url.searchParams.set("cd_client", CLIENT_NAME);
  url.searchParams.set("cd_client_version", CLIENT_VERSION);
  if (toolName) url.searchParams.set("cd_tool", toolName);
  return `${url.pathname}?${url.searchParams.toString()}`;
}

async function getJson(path, toolName) {
  const res = await fetch(`${API_BASE}${withClientParams(path, toolName)}`, {
    headers: {
      "X-CollegeData-Client": CLIENT_NAME,
      "X-CollegeData-Client-Version": CLIENT_VERSION,
      ...(toolName ? { "X-CollegeData-MCP-Tool": toolName } : {}),
    },
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload?.message ?? payload?.error ?? `HTTP ${res.status}`);
  return payload;
}

async function callTool(name, args) {
  if (name === "search_schools") {
    const params = new URLSearchParams({ q: args.query });
    if (args.limit) params.set("limit", String(args.limit));
    return getJson(`/api/schools/search?${params}`, name);
  }
  if (name === "get_school_facts") {
    const params = new URLSearchParams();
    if (args.categories) params.set("categories", args.categories);
    return getJson(`/api/schools/${encodeURIComponent(args.school_id)}/facts${params.size ? `?${params}` : ""}`, name);
  }
  if (name === "compare_schools") {
    const params = new URLSearchParams({ schools: args.school_ids.join(",") });
    if (args.categories) params.set("categories", args.categories);
    if (args.fields) params.set("fields", args.fields);
    return getJson(`/api/compare?${params}`, name);
  }
  if (name === "get_source_documents") {
    return getJson(`/api/schools/${encodeURIComponent(args.school_id)}/sources`, name);
  }
  if (name === "get_field_dictionary") {
    const params = new URLSearchParams();
    if (args.category) params.set("category", args.category);
    return getJson(`/api/fields${params.size ? `?${params}` : ""}`, name);
  }
  throw new Error(`Unknown tool: ${name}`);
}

function send(id, result) {
  const body = JSON.stringify({ jsonrpc: "2.0", id, result });
  process.stdout.write(`Content-Length: ${Buffer.byteLength(body, "utf8")}\r\n\r\n${body}`);
}

function sendError(id, error) {
  const body = JSON.stringify({
    jsonrpc: "2.0",
    id,
    error: { code: -32000, message: error.message },
  });
  process.stdout.write(`Content-Length: ${Buffer.byteLength(body, "utf8")}\r\n\r\n${body}`);
}

let buffer = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", async (chunk) => {
  buffer += chunk;
  while (true) {
    const headerEnd = buffer.indexOf("\r\n\r\n");
    if (headerEnd === -1) return;
    const header = buffer.slice(0, headerEnd);
    const match = header.match(/Content-Length:\s*(\d+)/i);
    if (!match) {
      buffer = "";
      return;
    }
    const length = Number(match[1]);
    const bodyStart = headerEnd + 4;
    if (buffer.length < bodyStart + length) return;
    const body = buffer.slice(bodyStart, bodyStart + length);
    buffer = buffer.slice(bodyStart + length);
    let message;
    try {
      message = JSON.parse(body);
      if (message.method === "initialize") {
        send(message.id, {
          protocolVersion: "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: "collegedata-fyi", version: "0.1.0" },
        });
      } else if (message.method === "tools/list") {
        send(message.id, { tools });
      } else if (message.method === "tools/call") {
        const payload = await callTool(message.params.name, message.params.arguments ?? {});
        send(message.id, {
          content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
        });
      } else if (message.id != null) {
        send(message.id, {});
      }
    } catch (error) {
      sendError(message?.id ?? null, error);
    }
  }
});
