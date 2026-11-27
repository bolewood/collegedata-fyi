import { execFile } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:http";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const script = join(dirname(fileURLToPath(import.meta.url)), "bin", "collegedata.js");

// Runs `search mit` against a local server and returns what the server saw.
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
  const base = { ...process.env };
  delete base.QUADFILE_API_BASE;
  delete base.COLLEGEDATA_API_BASE;
  try {
    await run("node", [script, "search", "mit", "--format", "json"], { env: { ...base, ...env(origin) } });
  } finally {
    http.close();
  }
  return seen;
}

describe("collegedata CLI identity", () => {
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
    assert.equal(headers["x-quadfile-client"], "cli");
    assert.equal(headers["x-collegedata-client"], "cli");
    assert.equal(headers["x-quadfile-client-version"], "0.1.0");
    assert.equal(headers["x-collegedata-client-version"], "0.1.0");
    assert.equal(headers["x-quadfile-cli-command"], "search");
    assert.equal(headers["x-collegedata-cli-command"], "search");
  });
});

// With no env set, the default origin is the new site. The preload replaces
// fetch, prints the first URL and exits (no spaces: NODE_OPTIONS splits on them), so nothing reaches the network.
const FIRST_FETCH_PRELOAD =
  "--import=data:text/javascript,globalThis.fetch=async(u)=>{console.error('FETCH:'+u);process.exit(0)}";

describe("collegedata CLI default origin", () => {
  it("fetches from https://www.quadfile.org when no API base is set", async () => {
    const base = { ...process.env, NODE_OPTIONS: FIRST_FETCH_PRELOAD };
    delete base.QUADFILE_API_BASE;
    delete base.COLLEGEDATA_API_BASE;
    const { stderr } = await run("node", [script, "search", "mit", "--format", "json"], { env: base });
    assert.match(stderr, /^FETCH:https:\/\/www\.quadfile\.org\/api\//m);
  });
});
