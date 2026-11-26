#!/usr/bin/env node

import { mkdir, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const API_BASE = (process.env.QUADFILE_API_BASE || process.env.COLLEGEDATA_API_BASE || "https://www.quadfile.org").replace(/\/$/, "");
const SNAPSHOT_DATE = process.env.QUADFILE_SNAPSHOT_DATE || process.env.COLLEGEDATA_SNAPSHOT_DATE || new Date().toISOString().slice(0, 10);
const OUT_DIR = join(ROOT, "web", "public", "snapshots", "v1", SNAPSHOT_DATE);
// Keep in step with dataLicenseFields() in web/src/lib/data-license.ts (a web test pins it).
// The license lives in the manifest only; never prepend non-record lines to JSONL.
const DATA_LICENSE_FIELDS = {
  data_license: {
    applies_to: "cds_extracts",
    license: "CC-BY-4.0",
    license_url: "https://creativecommons.org/licenses/by/4.0/",
    scope:
      "Covers the structured Common Data Set extracts, field documentation and derived-metric definitions authored by Quadfile. Does not cover the schools' Common Data Set documents, CDS Initiative template text, or federal IPEDS, College Scorecard and FSA facts. Say so if you changed the data.",
    attribution:
      "Common Data Set extracts from Quadfile (https://www.quadfile.org), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Figures as published in each school's Common Data Set.",
  },
};

async function fetchText(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} failed: HTTP ${res.status}`);
  return res.text();
}

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

async function writeSnapshot(name, body) {
  const path = join(OUT_DIR, name);
  await writeFile(path, body);
  return {
    name,
    bytes: Buffer.byteLength(body),
    sha256: sha256(body),
  };
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const files = [];
  files.push(await writeSnapshot("schools.jsonl", await fetchText("/snapshots/latest/schools.jsonl")));
  files.push(await writeSnapshot("school_facts.jsonl", await fetchText("/snapshots/latest/school_facts.jsonl")));
  files.push(await writeSnapshot("sources.jsonl", await fetchText("/snapshots/latest/sources.jsonl")));
  files.push(await writeSnapshot("field_dictionary.json", await fetchText("/snapshots/latest/field_dictionary.json")));

  const duckdb = spawnSync("duckdb", ["--version"], { encoding: "utf8" });
  if (duckdb.status === 0) {
    const dbPath = join(OUT_DIR, "collegedata.duckdb");
    const sql = `
      create table schools as select * from read_json_auto('${join(OUT_DIR, "schools.jsonl")}');
      create table school_facts as select * from read_json_auto('${join(OUT_DIR, "school_facts.jsonl")}');
      create table sources as select * from read_json_auto('${join(OUT_DIR, "sources.jsonl")}');
    `;
    const build = spawnSync("duckdb", [dbPath, sql], { encoding: "utf8" });
    if (build.status !== 0) throw new Error(build.stderr || "duckdb build failed");
    files.push({ name: "collegedata.duckdb", status: "generated" });
  } else {
    files.push({ name: "collegedata.duckdb", status: "skipped_duckdb_cli_not_installed" });
  }

  const manifest = {
    schema_version: "v1",
    generated_at: new Date().toISOString(),
    snapshot_date: SNAPSHOT_DATE,
    api_base: API_BASE,
    ...DATA_LICENSE_FIELDS,
    files,
  };
  await writeFile(join(OUT_DIR, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Wrote ${OUT_DIR}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

