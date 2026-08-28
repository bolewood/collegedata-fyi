import { NextResponse } from "next/server";
import { recordApiUsageEvent } from "@/lib/api-usage";
import { handleMcpMessage, isNotification, type JsonRpcMessage } from "@/lib/mcp/protocol";
import { clientIp, rateLimitToolCall } from "@/lib/mcp/rate-limit";
import {
  MCP_SERVER_NAME,
  MCP_SERVER_VERSION,
  MCP_TOOL_NAMES,
} from "@/lib/mcp/tools";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Accept, MCP-Protocol-Version, Mcp-Protocol-Version, Mcp-Session-Id, Mcp-Method, Mcp-Name, Last-Event-ID, Authorization",
  "Access-Control-Expose-Headers": "MCP-Protocol-Version",
  "Access-Control-Max-Age": "86400",
};

function withCors(response: Response): Response {
  const headers = new Headers(response.headers);
  for (const [key, value] of Object.entries(CORS_HEADERS)) {
    headers.set(key, value);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function json(body: unknown, init?: ResponseInit): Response {
  return withCors(NextResponse.json(body, init));
}

export async function OPTIONS() {
  return withCors(
    new Response(null, {
      status: 204,
      headers: { Allow: "GET, POST, OPTIONS" },
    }),
  );
}

export async function GET(request: Request) {
  const accept = request.headers.get("accept") ?? "";
  if (accept.includes("text/event-stream") && !accept.includes("application/json")) {
    return withCors(
      new Response(JSON.stringify({ error: "sse_not_supported", message: "POST JSON-RPC to this URL." }), {
        status: 405,
        headers: {
          Allow: "GET, POST, OPTIONS",
          "Content-Type": "application/json",
        },
      }),
    );
  }
  return json({
    name: MCP_SERVER_NAME,
    version: MCP_SERVER_VERSION,
    transport: "streamable-http",
    auth: "none",
    endpoint: "https://www.collegedata.fyi/api/mcp",
    tools: MCP_TOOL_NAMES,
    docs: "https://www.collegedata.fyi/api",
  });
}

export async function DELETE() {
  return withCors(
    new Response(null, {
      status: 405,
      headers: { Allow: "GET, POST, OPTIONS" },
    }),
  );
}

async function recordMcpUsage(request: Request, method: string, toolName: string | null) {
  const country = request.headers.get("x-vercel-ip-country");
  await recordApiUsageEvent({
    request_source: "friendly_api",
    route_path: "/api/mcp",
    route_kind: "mcp",
    http_method: "POST",
    client_family: "mcp",
    client_name: "mcp-http",
    client_version: MCP_SERVER_VERSION,
    client_tool: toolName ?? method,
    user_agent_family: "ai_agent",
    referer_host: null,
    country: country && country.trim() ? country.trim().slice(0, 8) : null,
    school_id: null,
    school_count: null,
  });
}

export async function POST(request: Request) {
  let message: JsonRpcMessage;
  try {
    message = (await request.json()) as JsonRpcMessage;
  } catch {
    return json(
      { jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } },
      { status: 400 },
    );
  }

  if (!message || typeof message !== "object" || Array.isArray(message)) {
    return json(
      { jsonrpc: "2.0", id: null, error: { code: -32600, message: "Invalid Request" } },
      { status: 400 },
    );
  }

  if (isNotification(message)) {
    return withCors(new Response(null, { status: 202 }));
  }

  if (message.method === "tools/call") {
    const limited = rateLimitToolCall(clientIp(request.headers));
    if (!limited.ok) {
      return json(
        {
          jsonrpc: "2.0",
          id: message.id ?? null,
          error: {
            code: -32000,
            message: `Rate limit exceeded. Retry after ${limited.retryAfterSec} seconds.`,
          },
        },
        {
          status: 429,
          headers: { "Retry-After": String(limited.retryAfterSec) },
        },
      );
    }
  }

  const toolName =
    message.method === "tools/call" && typeof message.params?.name === "string"
      ? message.params.name
      : null;
  if (typeof message.method === "string") {
    void recordMcpUsage(request, message.method, toolName);
  }

  const handled = await handleMcpMessage(message);
  if (handled.kind === "empty") {
    return withCors(new Response(null, { status: 202 }));
  }
  return json(handled.body, { status: handled.status });
}
