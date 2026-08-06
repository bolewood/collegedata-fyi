#!/usr/bin/env -S deno run --allow-net --allow-read=.env
/** Reprobe a deterministic 20-school no_pdfs_found cohort with the real resolver.
 *
 * Read-only: this script performs GET requests to PostgREST and public school
 * sites. It never imports archive writers or calls a database RPC. For failed
 * homepage hints it also evaluates the existing well-known landing paths,
 * which production currently applies only to direct-document hints.
 *
 * Usage:
 *   deno run --allow-net --allow-read=.env --allow-write=scratch/data-integrity-audit \
 *     tools/data_quality/reprobe_resolver_cohort.ts \
 *     --output scratch/data-integrity-audit/n-reprobe.json
 */

import {
  resolveCdsForSchool,
  type ResolveResult,
  wellKnownPathUrls,
} from "../../supabase/functions/_shared/resolve.ts";

const COHORT_SIZE = 20;
const SAMPLE_SALT = "audit-2026-08-06-n1";
const PAGE_SIZE = 1000;
const DOCUMENT_EXT_RE = /\.(pdf|xlsx|docx)(\?|#|$)/i;

interface QueueRow {
  id: string;
  school_id: string;
  school_name: string;
  cds_url_hint: string;
  status: string;
  last_outcome: string | null;
  processed_at: string | null;
  enqueued_at: string;
}

function utcNow(): string {
  return new Date().toISOString();
}

function loadEnv(path: string): Record<string, string> {
  const values: Record<string, string> = {};
  const text = Deno.readTextFileSync(path);
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const splitAt = line.indexOf("=");
    const key = line.slice(0, splitAt).trim();
    let value = line.slice(splitAt + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function parseArgs(args: string[]): { env: string; output: string } {
  let env = ".env";
  let output = "";
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--env") env = args[++i] ?? "";
    else if (args[i] === "--output") output = args[++i] ?? "";
    else throw new Error(`unknown argument: ${args[i]}`);
  }
  if (!env || !output) throw new Error("--output is required");
  return { env, output };
}

export function parseContentRange(value: string | null): {
  start: number | null;
  end: number | null;
  total: number | null;
} {
  if (!value) throw new Error("PostgREST response omitted Content-Range");
  const match = value.match(/^(?:(\d+)-(\d+)|\*)\/(\d+|\*)$/);
  if (!match) throw new Error(`invalid Content-Range: ${value}`);
  return {
    start: match[1] === undefined ? null : Number(match[1]),
    end: match[2] === undefined ? null : Number(match[2]),
    total: match[3] === "*" ? null : Number(match[3]),
  };
}

async function sha256Text(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function fetchQueue(
  baseUrl: string,
  apiKey: string,
): Promise<{ rows: QueueRow[]; pagination: Record<string, unknown> }> {
  const rows: QueueRow[] = [];
  const ranges: string[] = [];
  const seen = new Set<string>();
  let expected: number | null = null;
  let offset = 0;
  while (expected === null || offset < expected) {
    const query = new URLSearchParams({
      select:
        "id,school_id,school_name,cds_url_hint,status,last_outcome,processed_at,enqueued_at",
      order: "id.asc",
    });
    const response = await fetch(
      `${baseUrl.replace(/\/$/, "")}/rest/v1/archive_queue?${query}`,
      {
        method: "GET",
        headers: {
          apikey: apiKey,
          Authorization: `Bearer ${apiKey}`,
          "Range-Unit": "items",
          Range: `${offset}-${offset + PAGE_SIZE - 1}`,
          ...(offset === 0 ? { Prefer: "count=exact" } : {}),
        },
      },
    );
    if (!response.ok) {
      throw new Error(`archive_queue: PostgREST HTTP ${response.status}`);
    }
    const rawRange = response.headers.get("Content-Range");
    const range = parseContentRange(rawRange);
    if (offset === 0) {
      if (range.total === null) {
        throw new Error("first page lacked an exact total");
      }
      expected = range.total;
    }
    const batch = await response.json() as QueueRow[];
    if (expected === 0 && batch.length === 0) {
      ranges.push(rawRange!);
      break;
    }
    if (
      batch.length === 0 || range.start !== offset ||
      range.end !== offset + batch.length - 1
    ) {
      throw new Error(`archive_queue pagination gap at ${offset}: ${rawRange}`);
    }
    if (batch.length < PAGE_SIZE && offset + batch.length !== expected) {
      throw new Error(
        `archive_queue short page before ${expected}: ${rawRange}`,
      );
    }
    for (const row of batch) {
      if (seen.has(row.id)) {
        throw new Error(`duplicate archive_queue id: ${row.id}`);
      }
      seen.add(row.id);
    }
    rows.push(...batch);
    ranges.push(rawRange!);
    offset += batch.length;
  }
  if (rows.length !== expected) {
    throw new Error(
      `fetched ${rows.length} archive rows, expected ${expected}`,
    );
  }
  return {
    rows,
    pagination: {
      expected_rows: expected,
      fetched_rows: rows.length,
      page_size: PAGE_SIZE,
      page_count: ranges.length,
      content_ranges: ranges,
      result_sha256: await sha256Text(
        rows.map((row) => JSON.stringify(row)).join("\n") + "\n",
      ),
      assertions: {
        stable_order_declared: true,
        no_gaps_or_caps: true,
        unique_ids: true,
        fetched_equals_expected: true,
      },
    },
  };
}

async function selectCohort(rows: QueueRow[]): Promise<{
  eligibleCount: number;
  schools: Array<QueueRow & { sample_hash: string }>;
}> {
  const latest = new Map<string, QueueRow>();
  for (const row of rows) {
    const existing = latest.get(row.school_id);
    const rowKey = `${row.processed_at ?? row.enqueued_at}\0${row.id}`;
    const existingKey = existing
      ? `${existing.processed_at ?? existing.enqueued_at}\0${existing.id}`
      : "";
    if (!existing || rowKey > existingKey) latest.set(row.school_id, row);
  }
  const eligible = Array.from(latest.values()).filter((row) =>
    row.status === "failed_permanent" && row.last_outcome === "no_pdfs_found"
  );
  const hashed = await Promise.all(
    eligible.map(async (row) => ({
      ...row,
      sample_hash: await sha256Text(`${SAMPLE_SALT}\0${row.school_id}`),
    })),
  );
  hashed.sort((a, b) =>
    a.sample_hash.localeCompare(b.sample_hash) ||
    a.school_id.localeCompare(b.school_id)
  );
  return {
    eligibleCount: eligible.length,
    schools: hashed.slice(0, COHORT_SIZE),
  };
}

function conciseResult(result: ResolveResult): Record<string, unknown> {
  if (result.kind === "resolved") {
    return {
      kind: result.kind,
      document_count: result.docs.length,
      documents: result.docs.map((doc) => ({
        candidate_kind: doc.candidate_kind,
        url: doc.url,
        cds_year: doc.cds_year,
        filename: doc.filename,
        discovered_via: doc.discovered_via,
        ...(doc.candidate_kind === "section_package"
          ? { sections: doc.parts.map((part) => part.section) }
          : {}),
      })),
    };
  }
  return { kind: result.kind, reason: result.reason };
}

async function probeSchool(row: QueueRow & { sample_hash: string }) {
  const startedAt = utcNow();
  const base = await resolveCdsForSchool(row.cds_url_hint);
  let fallback: Record<string, unknown> | null = null;
  let verdict = base.kind === "resolved"
    ? "resolved_by_current_resolver"
    : "not_found_from_supplied_hint";

  if (base.kind !== "resolved" && !DOCUMENT_EXT_RE.test(row.cds_url_hint)) {
    const attempts: Array<Record<string, unknown>> = [];
    for (const url of wellKnownPathUrls(row.cds_url_hint)) {
      const result = await resolveCdsForSchool(url);
      attempts.push({ url, ...conciseResult(result) });
      if (result.kind === "resolved") {
        verdict = "resolved_by_homepage_well_known_extension";
        break;
      }
    }
    fallback = {
      method:
        "Call the real resolver on each existing wellKnownPathUrls() candidate; stop on first resolution.",
      attempts,
    };
  }
  return {
    school_id: row.school_id,
    school_name: row.school_name,
    supplied_hint: row.cds_url_hint,
    sample_hash: row.sample_hash,
    started_at: startedAt,
    finished_at: utcNow(),
    base_resolver: conciseResult(base),
    homepage_well_known_extension: fallback,
    verdict,
  };
}

async function main(): Promise<void> {
  const args = parseArgs(Deno.args);
  const env = loadEnv(args.env);
  const baseUrl = env.SUPABASE_URL;
  const apiKey = env.SUPABASE_SERVICE_ROLE_KEY;
  if (!baseUrl || !apiKey) {
    throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required");
  }

  const runStartedAt = utcNow();
  const queue = await fetchQueue(baseUrl, apiKey);
  const cohort = await selectCohort(queue.rows);
  if (cohort.schools.length !== COHORT_SIZE) {
    throw new Error(
      `eligible cohort has only ${cohort.schools.length} schools`,
    );
  }

  const results = [];
  for (const school of cohort.schools) {
    console.error(
      `reprobe ${results.length + 1}/${COHORT_SIZE}: ${school.school_id}`,
    );
    try {
      results.push(await probeSchool(school));
    } catch (error) {
      results.push({
        school_id: school.school_id,
        school_name: school.school_name,
        supplied_hint: school.cds_url_hint,
        sample_hash: school.sample_hash,
        verdict: "probe_error",
        error_type: error instanceof Error ? error.name : "unknown",
      });
    }
  }

  const verdicts: Record<string, number> = {};
  for (const result of results) {
    verdicts[result.verdict] = (verdicts[result.verdict] ?? 0) + 1;
  }
  const report = {
    label: "Deterministic 20-school N reprobe",
    run_started_at: runStartedAt,
    run_finished_at: utcNow(),
    method: {
      population:
        "Schools whose latest archive_queue row is failed_permanent/no_pdfs_found",
      sampling:
        `Take the 20 lexicographically smallest SHA-256(${SAMPLE_SALT}\\0school_id) values`,
      sample_salt: SAMPLE_SALT,
      eligible_schools: cohort.eligibleCount,
      cohort_size: COHORT_SIZE,
      resolver:
        "supabase/functions/_shared/resolve.ts resolveCdsForSchool: redirects, direct documents, two-hop discovery, and production candidate selection",
      extension_evaluated:
        "For unsuccessful non-document hints, call the same resolver on the existing well-known paths. Production does not currently do this for homepage hints.",
    },
    archive_queue_pagination: queue.pagination,
    verdicts,
    results,
    interpretation:
      "No unresolved school is called truly absent. The strongest supported label is not_found_from_supplied_hint.",
  };
  const outputUrl = new URL(args.output, `file://${Deno.cwd()}/`);
  await Deno.mkdir(new URL(".", outputUrl), { recursive: true });
  await Deno.writeTextFile(outputUrl, JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify({ output: args.output, verdicts }, null, 2));
}

if (import.meta.main) await main();
