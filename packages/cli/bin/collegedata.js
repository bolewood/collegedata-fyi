#!/usr/bin/env node

const API_BASE = (process.env.COLLEGEDATA_API_BASE ?? "https://www.collegedata.fyi").replace(/\/$/, "");

function usage() {
  console.error(`Usage:
  collegedata search <query> [--format json]
  collegedata facts <school_id> [--categories admissions,cost,outcomes] [--format json|table]
  collegedata compare <school_id...> [--categories admissions,cost,outcomes] [--fields applied,admitted] [--format json|csv|table]
  collegedata sources <school_id> [--format json]
  collegedata fields [--category admissions] [--format json|table]
  collegedata export <snapshot> [--format jsonl|json|duckdb]`);
}

function parseOptions(args) {
  const out = { _: [] };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith("--")) {
        out[key] = next;
        i += 1;
      } else {
        out[key] = true;
      }
    } else {
      out._.push(arg);
    }
  }
  return out;
}

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  const text = await res.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  if (!res.ok) {
    const message = payload?.message ?? payload?.error ?? `HTTP ${res.status}`;
    throw new Error(message);
  }
  return payload;
}

function printJson(payload) {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}

function printTable(rows, columns) {
  if (rows.length === 0) return;
  const widths = columns.map((column) =>
    Math.min(
      42,
      Math.max(
        column.length,
        ...rows.map((row) => String(row[column] ?? "").length),
      ),
    ),
  );
  process.stdout.write(`${columns.map((column, i) => column.padEnd(widths[i])).join("  ")}\n`);
  process.stdout.write(`${widths.map((width) => "-".repeat(width)).join("  ")}\n`);
  for (const row of rows) {
    process.stdout.write(
      `${columns
        .map((column, i) => String(row[column] ?? "").slice(0, widths[i]).padEnd(widths[i]))
        .join("  ")}\n`,
    );
  }
}

function printCsv(rows, columns) {
  const esc = (value) => {
    const s = String(value ?? "");
    return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  process.stdout.write(`${columns.map(esc).join(",")}\n`);
  for (const row of rows) {
    process.stdout.write(`${columns.map((column) => esc(row[column])).join(",")}\n`);
  }
}

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  const opts = parseOptions(rest);
  const format = opts.format ?? (process.stdout.isTTY ? "table" : "json");

  if (!command || command === "help" || command === "--help") {
    usage();
    return;
  }

  if (command === "search") {
    const q = opts._.join(" ");
    if (!q) throw new Error("search requires a query");
    const payload = await getJson(`/api/schools/search?q=${encodeURIComponent(q)}`);
    if (format === "json") return printJson(payload);
    return printTable(payload.results, ["school_id", "school_name", "city", "state", "coverage_status"]);
  }

  if (command === "facts") {
    const school = opts._[0];
    if (!school) throw new Error("facts requires a school_id");
    const params = new URLSearchParams();
    if (opts.categories) params.set("categories", opts.categories);
    const payload = await getJson(`/api/schools/${encodeURIComponent(school)}/facts${params.size ? `?${params}` : ""}`);
    if (format === "json") return printJson(payload);
    return printTable(
      payload.facts.map((fact) => ({
        key: fact.key,
        value: fact.display_value,
        source: fact.source?.layer ?? "",
        quality: fact.quality?.flag ?? "",
      })),
      ["key", "value", "source", "quality"],
    );
  }

  if (command === "compare") {
    const schools = opts._;
    if (schools.length === 0) throw new Error("compare requires one or more school_id values");
    const params = new URLSearchParams({ schools: schools.join(",") });
    if (opts.categories) params.set("categories", opts.categories);
    if (opts.fields) params.set("fields", opts.fields);
    const payload = await getJson(`/api/compare?${params}`);
    if (format === "json") return printJson(payload);
    const columns = ["school", ...payload.columns.map((column) => column.key)];
    const rows = payload.rows.map((row) => ({
      school: row.school_name,
      ...Object.fromEntries(
        payload.columns.map((column) => [column.key, row.values[column.key]?.display_value ?? ""]),
      ),
    }));
    if (format === "csv") return printCsv(rows, columns);
    return printTable(rows, columns);
  }

  if (command === "sources") {
    const school = opts._[0];
    if (!school) throw new Error("sources requires a school_id");
    const payload = await getJson(`/api/schools/${encodeURIComponent(school)}/sources`);
    return printJson(payload);
  }

  if (command === "fields") {
    const params = new URLSearchParams();
    if (opts.category) params.set("category", opts.category);
    const payload = await getJson(`/api/fields${params.size ? `?${params}` : ""}`);
    if (format === "json") return printJson(payload);
    return printTable(payload.fields, ["key", "label", "category", "source_layer"]);
  }

  if (command === "export") {
    const snapshot = opts._[0];
    if (!snapshot) throw new Error("export requires a snapshot name");
    const extension = opts.format ?? "jsonl";
    const res = await fetch(`${API_BASE}/snapshots/latest/${snapshot}.${extension}`);
    if (!res.ok) throw new Error(`snapshot download failed: HTTP ${res.status}`);
    process.stdout.write(await res.text());
    return;
  }

  usage();
  process.exitCode = 2;
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});

