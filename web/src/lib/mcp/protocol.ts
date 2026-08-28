import {
  MCP_INSTRUCTIONS,
  MCP_SERVER_NAME,
  MCP_SERVER_VERSION,
  MCP_TOOL_NAMES,
  MCP_TOOLS,
  negotiateProtocolVersion,
} from "./tools";

export type JsonRpcId = string | number | null;

export type JsonRpcMessage = {
  jsonrpc?: string;
  id?: JsonRpcId;
  method?: string;
  params?: Record<string, unknown>;
};

export type JsonRpcResponse = {
  jsonrpc: "2.0";
  id: JsonRpcId;
  result?: unknown;
  error?: { code: number; message: string };
};

export type McpHandleResult =
  | { kind: "empty" }
  | { kind: "response"; status: number; body: JsonRpcResponse };

function serverInfo() {
  return { name: MCP_SERVER_NAME, version: MCP_SERVER_VERSION };
}

function capabilities() {
  return { tools: {} };
}

function result(id: JsonRpcId, value: unknown): McpHandleResult {
  return {
    kind: "response",
    status: 200,
    body: { jsonrpc: "2.0", id, result: value },
  };
}

function error(id: JsonRpcId, message: string, code = -32000, status = 200): McpHandleResult {
  return {
    kind: "response",
    status,
    body: { jsonrpc: "2.0", id, error: { code, message } },
  };
}

export async function handleMcpMessage(message: JsonRpcMessage): Promise<McpHandleResult> {
  const id = message.id ?? null;
  const method = message.method;
  const params = message.params ?? {};

  if (method === "notifications/initialized" || method === "notifications/cancelled") {
    return { kind: "empty" };
  }

  if (id == null) {
    return { kind: "empty" };
  }

  if (method === "initialize" || method === "server/discover") {
    return result(id, {
      protocolVersion: negotiateProtocolVersion(params.protocolVersion),
      capabilities: capabilities(),
      serverInfo: serverInfo(),
      instructions: MCP_INSTRUCTIONS,
    });
  }

  if (method === "ping") {
    return result(id, {});
  }

  if (method === "tools/list") {
    return result(id, { tools: MCP_TOOLS });
  }

  if (method === "resources/list") {
    return result(id, { resources: [] });
  }

  if (method === "prompts/list") {
    return result(id, { prompts: [] });
  }

  if (method === "tools/call") {
    const name = typeof params.name === "string" ? params.name : "";
    if (!(MCP_TOOL_NAMES as readonly string[]).includes(name)) {
      return result(id, {
        content: [{ type: "text", text: `Unknown tool: ${name}` }],
        isError: true,
      });
    }
    try {
      const { callMcpTool } = await import("./call-tool");
      const payload = await callMcpTool(name, params.arguments ?? {});
      return result(id, {
        content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
      });
    } catch (caught) {
      const messageText = caught instanceof Error ? caught.message : String(caught);
      return result(id, {
        content: [{ type: "text", text: messageText }],
        isError: true,
      });
    }
  }

  return error(id, `Method not found: ${method ?? "unknown"}`, -32601);
}

export function isNotification(message: JsonRpcMessage): boolean {
  return message.id == null && typeof message.method === "string";
}
