import { execFile } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:http";
import { readFile, rm } from "node:fs/promises";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const here = dirname(fileURLToPath(import.meta.url));
const script = join(here, "build_public_snapshots.mjs");
const snapshots = join(here, "..", "..", "web", "public", "snapshots", "v1");

// Runs the script against a local server and returns its manifest.
async function manifestFor(env, date) {
  const http = createServer((req, res) => {
    res.end(req.url.endsWith(".json") ? "{}" : '{"a":1}\n');
  });
  http.listen(0, "127.0.0.1");
  await once(http, "listening");
  const origin = `http://127.0.0.1:${http.address().port}`;
  const base = { ...process.env, PATH: dirname(process.execPath) }; // no duckdb on PATH
  delete base.QUADFILE_API_BASE;
  delete base.COLLEGEDATA_API_BASE;
  delete base.QUADFILE_SNAPSHOT_DATE;
  delete base.COLLEGEDATA_SNAPSHOT_DATE;
  const outDir = join(snapshots, date);
  try {
    await run(process.execPath, [script], { env: { ...base, ...env(origin) } });
    return { manifest: JSON.parse(await readFile(join(outDir, "manifest.json"), "utf8")), origin };
  } finally {
    http.close();
    await rm(outDir, { recursive: true, force: true });
  }
}

describe("public snapshot builder env names", () => {
  it("QUADFILE_* wins over COLLEGEDATA_*", async () => {
    const { manifest, origin } = await manifestFor(
      (o) => ({
        QUADFILE_API_BASE: o,
        COLLEGEDATA_API_BASE: "http://127.0.0.1:1",
        QUADFILE_SNAPSHOT_DATE: "1999-01-02",
        COLLEGEDATA_SNAPSHOT_DATE: "1999-01-03",
      }),
      "1999-01-02",
    );
    assert.equal(manifest.snapshot_date, "1999-01-02");
    assert.equal(manifest.api_base, origin);
  });

  it("COLLEGEDATA_* still works alone", async () => {
    const { manifest, origin } = await manifestFor(
      (o) => ({ COLLEGEDATA_API_BASE: o, COLLEGEDATA_SNAPSHOT_DATE: "1999-01-03" }),
      "1999-01-03",
    );
    assert.equal(manifest.snapshot_date, "1999-01-03");
    assert.equal(manifest.api_base, origin);
  });
});
