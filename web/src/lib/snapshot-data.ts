import { fetchCoverageRows, fetchManifest } from "./queries";
import { supabase } from "./supabase";
import { FRIENDLY_FACT_FIELDS, publicFieldDefinitions } from "./public-data";

type UntypedSupabase = {
  from: (table: string) => any;
};

const SNAPSHOT_DATE = "2026-05-09";
const SNAPSHOT_BASE = `https://www.collegedata.fyi/snapshots/v1/${SNAPSHOT_DATE}`;

async function fetchPagedRows<T>(
  table: string,
  select: string,
  build?: (query: any) => any,
): Promise<T[]> {
  const PAGE = 1000;
  const HARD_CAP = 100_000;
  const out: T[] = [];
  const raw = supabase as unknown as UntypedSupabase;
  for (let start = 0; start < HARD_CAP; start += PAGE) {
    const base = raw.from(table).select(select).range(start, start + PAGE - 1);
    const query = build ? build(base) : base;
    const { data, error } = await query;
    if (error) throw new Error(`Failed to fetch ${table}: ${error.message}`);
    const rows = (data as T[]) ?? [];
    out.push(...rows);
    if (rows.length < PAGE) break;
  }
  return out;
}

function jsonl(rows: unknown[]): string {
  return `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`;
}

export async function snapshotManifest() {
  return {
    schema_version: "v1",
    generated_at: new Date().toISOString(),
    snapshot_date: SNAPSHOT_DATE,
    files: [
      { name: "schools.jsonl", format: "jsonl", url: `${SNAPSHOT_BASE}/schools.jsonl` },
      { name: "school_facts.jsonl", format: "jsonl", url: `${SNAPSHOT_BASE}/school_facts.jsonl` },
      { name: "sources.jsonl", format: "jsonl", url: `${SNAPSHOT_BASE}/sources.jsonl` },
      { name: "field_dictionary.json", format: "json", url: `${SNAPSHOT_BASE}/field_dictionary.json` },
      {
        name: "collegedata.duckdb",
        format: "duckdb",
        url: `${SNAPSHOT_BASE}/collegedata.duckdb`,
        status: "generator_skips_when_duckdb_cli_is_unavailable",
      },
    ],
    latest_alias: "https://www.collegedata.fyi/snapshots/latest/manifest.json",
  };
}

export async function snapshotFile(file: string): Promise<{ body: string; contentType: string; status?: number }> {
  if (file === "manifest.json") {
    return {
      body: JSON.stringify(await snapshotManifest(), null, 2),
      contentType: "application/json; charset=utf-8",
    };
  }

  if (file === "field_dictionary.json") {
    return {
      body: JSON.stringify({ generated_at: new Date().toISOString(), fields: publicFieldDefinitions() }, null, 2),
      contentType: "application/json; charset=utf-8",
    };
  }

  if (file === "schools.jsonl") {
    const rows = await fetchCoverageRows();
    return { body: jsonl(rows), contentType: "application/x-ndjson; charset=utf-8" };
  }

  if (file === "sources.jsonl") {
    const rows = (await fetchManifest()).map((row) => ({
      document_id: row.document_id,
      school_id: row.school_id,
      school_name: row.school_name,
      ipeds_id: row.ipeds_id,
      canonical_year: row.canonical_year,
      sub_institutional: row.sub_institutional,
      source_url: row.source_url,
      source_storage_path: row.source_storage_path,
      source_format: row.source_format,
      extraction_status: row.extraction_status,
      data_quality_flag: row.data_quality_flag,
      discovered_at: row.discovered_at,
      last_verified_at: row.last_verified_at,
      removed_at: row.removed_at,
    }));
    return { body: jsonl(rows), contentType: "application/x-ndjson; charset=utf-8" };
  }

  if (file === "school_facts.jsonl") {
    const browserRows = await fetchPagedRows<Record<string, unknown>>(
      "school_browser_rows",
      "school_id, school_name, canonical_year, year_start, applied, admitted, enrolled_first_year, acceptance_rate, yield_rate, sat_submit_rate, act_submit_rate, sat_composite_p50, act_composite_p50, ed_offered, ed_applicants, ed_admitted, ea_offered, wait_list_offered",
      (query) => query.gte("year_start", 2024).is("sub_institutional", null).order("school_id", { ascending: true }).order("year_start", { ascending: false }),
    );
    const latest = new Map<string, Record<string, unknown>>();
    for (const row of browserRows) {
      const schoolId = String(row.school_id ?? "");
      if (schoolId && !latest.has(schoolId)) latest.set(schoolId, row);
    }
    const browserFacts = Array.from(latest.values()).flatMap((row) =>
      FRIENDLY_FACT_FIELDS.filter((field) => field.path?.startsWith("browser.")).map((field) => {
        const key = field.path?.split(".")[1] ?? "";
        return {
          school_id: row.school_id,
          school_name: row.school_name,
          key: field.key,
          label: field.label,
          value: row[key],
          category: field.category,
          source_layer: field.source_layer,
          canonical_year: row.canonical_year,
        };
      }),
    );
    return {
      body: jsonl(browserFacts),
      contentType: "application/x-ndjson; charset=utf-8",
    };
  }

  if (file === "collegedata.duckdb") {
    return {
      body: "DuckDB snapshot generation is available through tools/snapshots/build_public_snapshots.mjs when duckdb is installed.\n",
      contentType: "text/plain; charset=utf-8",
      status: 501,
    };
  }

  return { body: "not found\n", contentType: "text/plain; charset=utf-8", status: 404 };
}
