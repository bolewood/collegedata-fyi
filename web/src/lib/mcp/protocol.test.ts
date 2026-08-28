import { describe, expect, it } from "vitest";
import { handleMcpMessage } from "./protocol";
import { MCP_TOOL_NAMES } from "./tools";
import { clientIp, rateLimitToolCall, resetRateLimitForTests } from "./rate-limit";

describe("hosted MCP protocol", () => {
  it("handshakes and lists the five tools without hitting the data API", async () => {
    const init = await handleMcpMessage({
      jsonrpc: "2.0",
      id: 0,
      method: "initialize",
      params: { protocolVersion: "2025-03-26" },
    });
    expect(init.kind).toBe("response");
    if (init.kind !== "response") return;
    expect(init.body.result).toMatchObject({
      protocolVersion: "2025-03-26",
      serverInfo: { name: "collegedata-fyi" },
    });

    const listed = await handleMcpMessage({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list",
    });
    expect(listed.kind).toBe("response");
    if (listed.kind !== "response") return;
    const names = (listed.body.result as { tools: Array<{ name: string }> }).tools.map(
      (tool) => tool.name,
    );
    expect(names).toEqual([...MCP_TOOL_NAMES]);
  });

  it("acks initialized with no JSON-RPC body", async () => {
    const ack = await handleMcpMessage({
      jsonrpc: "2.0",
      method: "notifications/initialized",
    });
    expect(ack).toEqual({ kind: "empty" });
  });

  it("returns isError on unknown tools instead of a JSON-RPC fault", async () => {
    const call = await handleMcpMessage({
      jsonrpc: "2.0",
      id: 9,
      method: "tools/call",
      params: { name: "drop_tables", arguments: {} },
    });
    expect(call.kind).toBe("response");
    if (call.kind !== "response") return;
    expect(call.body.result).toMatchObject({ isError: true });
    expect(JSON.stringify(call.body.result)).toContain("Unknown tool");
  });

  it("rate-limits repeated tool calls from one IP", () => {
    resetRateLimitForTests();
    const ip = "203.0.113.9";
    for (let i = 0; i < 60; i += 1) {
      expect(rateLimitToolCall(ip).ok).toBe(true);
    }
    const blocked = rateLimitToolCall(ip);
    expect(blocked.ok).toBe(false);
    if (blocked.ok) return;
    expect(blocked.retryAfterSec).toBeGreaterThan(0);
    expect(clientIp(new Headers({ "x-forwarded-for": "203.0.113.9, 10.0.0.1" }))).toBe(
      "203.0.113.9",
    );
  });
});
