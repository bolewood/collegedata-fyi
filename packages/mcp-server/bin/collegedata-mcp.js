#!/usr/bin/env node

const API_BASE = (process.env.COLLEGEDATA_API_BASE ?? "https://www.collegedata.fyi").replace(/\/$/, "");
const CLIENT_NAME = "mcp";
const CLIENT_VERSION = "0.2.0";

const FACT_CATEGORIES = "identity, admissions, enrollment, cost, aid, finance, outcomes, sources";
const COMPARE_CATEGORIES = "identity, admissions, enrollment, cost, aid, outcomes, sources";

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
    description: "Get source documents, archive URLs, federal release metadata, and coverage status for one school.",
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

function writeMessage(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function sendResult(id, result) {
  writeMessage({ jsonrpc: "2.0", id, result });
}

function sendError(id, error, code = -32000) {
  writeMessage({
    jsonrpc: "2.0",
    id: id ?? null,
    error: { code, message: error.message ?? String(error) },
  });
}

async function handleMessage(message) {
  if (message.method === "initialize") {
    const requested = message.params?.protocolVersion;
    sendResult(message.id, {
      protocolVersion: requested || "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "collegedata-fyi", version: CLIENT_VERSION },
    });
    return;
  }
  if (message.method === "notifications/initialized" || message.method === "notifications/cancelled") {
    return;
  }
  if (message.method === "ping") {
    sendResult(message.id, {});
    return;
  }
  if (message.method === "tools/list") {
    sendResult(message.id, { tools });
    return;
  }
  if (message.method === "tools/call") {
    try {
      const payload = await callTool(message.params?.name, message.params?.arguments ?? {});
      sendResult(message.id, {
        content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
      });
    } catch (error) {
      sendResult(message.id, {
        content: [{ type: "text", text: error.message ?? String(error) }],
        isError: true,
      });
    }
    return;
  }
  if (message.id != null) {
    sendError(message.id, new Error(`Method not found: ${message.method}`), -32601);
  }
}

let buffer = "";
let queue = Promise.resolve();

function drain() {
  while (true) {
    const newline = buffer.indexOf("\n");
    if (newline === -1) return;
    const line = buffer.slice(0, newline).replace(/\r$/, "");
    buffer = buffer.slice(newline + 1);
    if (!line.trim()) continue;
    let message;
    try {
      message = JSON.parse(line);
    } catch (error) {
      sendError(null, error, -32700);
      continue;
    }
    queue = queue.then(() => handleMessage(message)).catch((error) => {
      sendError(message?.id ?? null, error);
    });
  }
}

process.stderr.write(`collegedata-mcp ${CLIENT_VERSION} ${API_BASE}\n`);
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  buffer += chunk;
  drain();
});
process.stdin.on("end", drain);
