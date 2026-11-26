import { spawn } from "node:child_process";
import { once } from "node:events";
import { dirname, join } from "node:path";
import { createServer } from "node:http";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const script = join(root, "bin", "collegedata-mcp.js");

function startServer(env = { COLLEGEDATA_API_BASE: "https://www.collegedata.fyi" }) {
  const base = { ...process.env };
  delete base.QUADFILE_API_BASE;
  delete base.COLLEGEDATA_API_BASE;
  const proc = spawn("node", [script], {
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...base, ...env },
  });
  proc.stdout.setEncoding("utf8");
  proc.stderr.setEncoding("utf8");
  let stdout = "";
  proc.stdout.on("data", (chunk) => {
    stdout += chunk;
  });
  let stderr = "";
  proc.stderr.on("data", (chunk) => {
    stderr += chunk;
  });

  async function readJson(timeoutMs = 2000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const nl = stdout.indexOf("\n");
      if (nl !== -1) {
        const line = stdout.slice(0, nl);
        stdout = stdout.slice(nl + 1);
        if (!line.trim()) continue;
        assert.doesNotMatch(line, /^Content-Length:/i);
        return JSON.parse(line);
      }
      await new Promise((resolve) => setTimeout(resolve, 25));
    }
    throw new Error(`No MCP JSON line within ${timeoutMs}ms. stderr=${stderr}`);
  }

  function send(message) {
    proc.stdin.write(`${JSON.stringify(message)}\n`);
  }

  async function close() {
    proc.kill("SIGTERM");
    await Promise.race([once(proc, "exit"), new Promise((resolve) => setTimeout(resolve, 500))]);
  }

  return { proc, send, readJson, close, getStderr: () => stderr };
}

describe("collegedata MCP stdio", () => {
  it("handshakes over newline-delimited JSON, not Content-Length", async () => {
    const server = startServer();
    try {
      server.send({
        jsonrpc: "2.0",
        id: 0,
        method: "initialize",
        params: {
          protocolVersion: "2025-03-26",
          capabilities: {},
          clientInfo: { name: "claude-desktop", version: "test" },
        },
      });
      const init = await server.readJson();
      assert.equal(init.id, 0);
      assert.equal(init.result.protocolVersion, "2025-03-26");
      assert.equal(init.result.serverInfo.name, "collegedata-fyi");
      assert.ok(init.result.capabilities.tools);

      server.send({ jsonrpc: "2.0", method: "notifications/initialized" });
      server.send({ jsonrpc: "2.0", id: 1, method: "ping" });
      const ping = await server.readJson();
      assert.equal(ping.id, 1);
      assert.deepEqual(ping.result, {});

      server.send({ jsonrpc: "2.0", id: 2, method: "tools/list" });
      const listed = await server.readJson();
      assert.equal(listed.id, 2);
      const names = listed.result.tools.map((tool) => tool.name);
      assert.deepEqual(names, [
        "search_schools",
        "get_school_facts",
        "compare_schools",
        "get_source_documents",
        "get_field_dictionary",
      ]);
    } finally {
      await server.close();
    }
  });
});

// Rename prep: QUADFILE_API_BASE wins, COLLEGEDATA_API_BASE still works, and
// every request carries both the new and the old client headers.
async function requestsSeen(env) {
  const seen = [];
  const http = createServer((req, res) => {
    seen.push({ url: req.url, headers: req.headers });
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ results: [] }));
  });
  http.listen(0, "127.0.0.1");
  await once(http, "listening");
  const origin = `http://127.0.0.1:${http.address().port}`;
  const server = startServer(env(origin));
  try {
    server.send({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: "search_schools", arguments: { query: "mit" } },
    });
    await server.readJson(5000);
  } finally {
    await server.close();
    http.close();
  }
  return seen;
}

describe("collegedata MCP identity", () => {
  it("QUADFILE_API_BASE wins over COLLEGEDATA_API_BASE", async () => {
    const seen = await requestsSeen((origin) => ({
      QUADFILE_API_BASE: origin,
      COLLEGEDATA_API_BASE: "http://127.0.0.1:1",
    }));
    assert.equal(seen.length, 1);
  });

  it("COLLEGEDATA_API_BASE still works alone", async () => {
    const seen = await requestsSeen((origin) => ({ COLLEGEDATA_API_BASE: origin }));
    assert.equal(seen.length, 1);
  });

  it("sends the new and the old client headers with the same values", async () => {
    const [{ headers }] = await requestsSeen((origin) => ({ QUADFILE_API_BASE: origin }));
    assert.equal(headers["x-quadfile-client"], "mcp");
    assert.equal(headers["x-collegedata-client"], "mcp");
    assert.equal(headers["x-quadfile-client-version"], headers["x-collegedata-client-version"]);
    assert.equal(headers["x-quadfile-mcp-tool"], "search_schools");
    assert.equal(headers["x-collegedata-mcp-tool"], "search_schools");
  });
});
