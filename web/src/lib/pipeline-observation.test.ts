import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";
import { LAMP_HEX } from "./pipeline-lamps";
import { PIPELINE_OBSERVATION_REDIRECTS } from "./pipeline-redirect";
import {
  activityFromRows,
  seedPipelineSnapshot,
  snapshotFromFacts,
  snapshotFromRpc,
  toPublicJson,
  type ExtractionActivityRow,
  type PipelineFactRow,
  type PipelineRpcClient,
} from "./pipeline-observation";

const NOW = new Date("2026-08-21T20:00:00.000Z");

const ALLOWED_HEX = new Set(
  [
    LAMP_HEX.capped,
    LAMP_HEX.cappedInk,
    LAMP_HEX.down,
    LAMP_HEX.late,
    LAMP_HEX.ok,
    LAMP_HEX.lock,
    LAMP_HEX.sso,
    LAMP_HEX.waf,
    LAMP_HEX.slate,
    LAMP_HEX.lateInk,
    "#fff",
    "#ffffff",
  ].map((hex) => hex.toLowerCase()),
);

function fact(partial: Partial<PipelineFactRow> & Pick<PipelineFactRow, "station_id" | "class" | "display_name">): PipelineFactRow {
  return {
    cadence_label: "test",
    on_board: true,
    sort_order: 0,
    last_started_at: null,
    last_finished_at: null,
    last_status: "never",
    last_trigger: null,
    last_summary: {},
    last_scheduled_finished_at: null,
    last_scheduled_status: "never",
    last_scheduled_summary: {},
    last_scheduled_error_code: "none",
    last_error_code: "none",
    source_url: null,
    queue_unfinished: null,
    extraction_pending: null,
    ...partial,
  };
}

function activity(
  partial: Partial<ExtractionActivityRow> = {},
): ExtractionActivityRow {
  return {
    activity_at: "2026-08-21T19:00:00.000Z",
    school_id: "harvey-mudd-college",
    school_name: "Harvey Mudd College",
    canonical_year: "2025-26",
    source_format: "pdf_flat",
    extraction_tier: "tier4",
    field_count: 210,
    outcome: "extracted",
    trigger: "schedule",
    run_url:
      "https://github.com/bolewood/collegedata-fyi/actions/runs/123",
    ...partial,
  };
}

describe("pipeline observation JSON", () => {
  it("snapshot has as_of, precomputed lamps, empty locked_doors, no secret-shaped strings", () => {
    const snapshot = snapshotFromFacts(
      [
        fact({
          station_id: "finder_brave",
          display_name: "Finder",
          class: "monthly_sla",
          last_scheduled_status: "error",
          last_scheduled_finished_at: "2026-08-20T20:00:00.000Z",
          last_scheduled_summary: { probed: 12, found: 1, replaced: 0, budget_remaining: 1700 },
          last_scheduled_error_code: "search_provider_rejected",
        }),
        fact({
          station_id: "archive_enqueue",
          display_name: "Enqueue",
          class: "daily_sla",
          last_scheduled_status: "ok",
          last_scheduled_finished_at: "2026-08-21T09:00:00.000Z",
          last_scheduled_summary: { queued: 412, skipped: 1988, errors: 0 },
        }),
      ],
      NOW,
    );
    const json = toPublicJson(snapshot);
    expect(json.as_of).toBe(NOW.toISOString());
    expect(json.locked_doors).toEqual([]);
    expect(json.methodology_url).toContain("#methodology");
    expect(json.stations.some((station) => station.lamp === "down")).toBe(true);
    const blob = JSON.stringify(json);
    expect(blob).not.toMatch(/service_role|sb_secret_|BRAVE_API_KEY|eyJhbGciOi/);
    expect(blob).not.toMatch(/sharepoint\.com\/:x:|force_urls|H1 review/);
    expect(json.strip.lamp).toBe("down");
  });

  it("facts fetch failure keeps seed lamps and a load-error strip", () => {
    const seed = seedPipelineSnapshot(NOW, true);
    expect(seed.load_error).toBe(true);
    expect(seed.strip.text).toBe("Could not load station clocks.");
    expect(seed.strip.lamp).toBe("down");
  });

  it("every board station has plain-English help copy", () => {
    const seed = seedPipelineSnapshot(NOW, false);
    expect(seed.stations.length).toBeGreaterThan(0);
    for (const station of seed.stations) {
      expect(station.help.trim().length).toBeGreaterThan(40);
      expect(station.help).not.toMatch(/\b(SLA|cron|GHA|RPC|service_role)\b/i);
    }
    const json = toPublicJson(seed);
    expect(json.stations[0]).not.toHaveProperty("help");
  });

  it("publishes only normalized recent extraction activity", () => {
    const rows = Array.from({ length: 55 }, (_, index) =>
      activity({
        activity_at: new Date(NOW.getTime() - index * 60_000).toISOString(),
        school_id: `school-${index}`,
        school_name: `School ${index}`,
        trigger: index === 0 ? "dispatch" : "schedule",
        outcome: index === 0 ? "re_extracted" : "extracted",
        run_url:
          index === 1
            ? "https://evil.example/run?token=secret"
            : activity().run_url,
      }),
    );
    rows.push(
      activity({
        activity_at: "2026-07-01T00:00:00.000Z",
        school_id: "too-old",
      }),
    );
    rows.push(activity({ school_id: "../unsafe" }));

    const normalized = activityFromRows(rows, NOW);
    expect(normalized).toHaveLength(50);
    expect(normalized[0]).toMatchObject({
      school_id: "school-0",
      outcome: "re_extracted",
      trigger_label: "Manual run",
      ago_label: "0 sec",
    });
    expect(normalized[1]?.run_url).toBeNull();
    expect(normalized.some((row) => row.school_id === "too-old")).toBe(false);
    expect(normalized.some((row) => row.school_id === "../unsafe")).toBe(false);

    const snapshot = snapshotFromFacts([], NOW, { activityRows: rows });
    const json = toPublicJson(snapshot);
    expect(json.extraction_activity).toHaveLength(50);
    expect(json.extraction_activity[0]).not.toHaveProperty("ago_label");
    const blob = JSON.stringify(json.extraction_activity);
    expect(blob).not.toMatch(/evil\.example|token=|document_id|failure_code/);
  });

  it("drops malformed vocabularies and bounds field counts", () => {
    const rows = [
      activity({ school_id: "bad-format", source_format: "exe" }),
      activity({ school_id: "bad-tier", extraction_tier: "tier99" }),
      activity({ school_id: "bad-outcome", outcome: "stack trace" }),
      activity({ school_id: "bad-trigger", trigger: "pull_request" }),
      activity({
        school_id: "future-row",
        activity_at: "2026-08-22T20:00:00.000Z",
      }),
      activity({ school_id: "valid-row", field_count: -4 }),
    ];
    const normalized = activityFromRows(rows, NOW);
    expect(normalized).toHaveLength(1);
    expect(normalized[0]?.school_id).toBe("valid-row");
    expect(normalized[0]?.field_count).toBeNull();
  });

  it("drops a null school name without turning station clocks red", () => {
    const rows = [
      activity({ school_id: "null-name", school_name: null as unknown as string }),
      activity({ school_id: "valid-name", school_name: "Harvey Mudd" }),
    ];
    expect(activityFromRows(rows, NOW).map((row) => row.school_id)).toEqual([
      "valid-name",
    ]);
    const snapshot = snapshotFromFacts(
      [
        fact({
          station_id: "archive_enqueue",
          display_name: "Enqueue",
          class: "daily_sla",
          last_scheduled_status: "ok",
          last_scheduled_finished_at: "2026-08-21T09:00:00.000Z",
        }),
      ],
      NOW,
      { activityRows: rows },
    );
    expect(snapshot.load_error).toBe(false);
    expect(snapshot.activity_load_error).toBe(false);
    expect(snapshot.extraction_activity).toHaveLength(1);
  });

  it("activity failure does not mark healthy station clocks as load errors", () => {
    const snapshot = snapshotFromFacts(
      [
        fact({
          station_id: "archive_enqueue",
          display_name: "Enqueue",
          class: "daily_sla",
          last_scheduled_status: "ok",
          last_scheduled_finished_at: "2026-08-21T09:00:00.000Z",
        }),
      ],
      NOW,
      { activityLoadError: true },
    );
    expect(snapshot.load_error).toBe(false);
    expect(snapshot.activity_load_error).toBe(true);
    expect(snapshot.extraction_activity).toEqual([]);
  });

  it("RPC activity failure stays independent from station facts", async () => {
    const healthyFact = fact({
      station_id: "archive_enqueue",
      display_name: "Enqueue",
      class: "daily_sla",
      last_scheduled_status: "ok",
      last_scheduled_finished_at: "2026-08-21T19:30:00.000Z",
    });
    const rpc: PipelineRpcClient = {
      rpc: async (name) =>
        name === "pipeline_station_facts"
          ? { data: [healthyFact], error: null }
          : { data: null, error: { message: "activity unavailable" } },
    };
    const snapshot = await snapshotFromRpc(rpc, NOW);
    expect(snapshot.load_error).toBe(false);
    expect(snapshot.activity_load_error).toBe(true);
    expect(snapshot.extraction_activity).toEqual([]);
  });

  it("activity timeout does not hold the dispatch board open", async () => {
    const rpc: PipelineRpcClient = {
      rpc: async (name) => {
        if (name === "pipeline_station_facts") {
          return {
            data: [
              fact({
                station_id: "archive_enqueue",
                display_name: "Enqueue",
                class: "daily_sla",
              }),
            ],
            error: null,
          };
        }
        return new Promise(() => undefined);
      },
    };
    const snapshot = await snapshotFromRpc(rpc, NOW, 1);
    expect(snapshot.load_error).toBe(false);
    expect(snapshot.activity_load_error).toBe(true);
  });

  it("facts timeout still returns independently loaded activity", async () => {
    let factsAborted = false;
    const never = Object.assign(
      new Promise<{ data: unknown[] | null; error: { message: string } | null }>(
        () => undefined,
      ),
      {
        abortSignal: (signal: AbortSignal) => {
          signal.addEventListener("abort", () => {
            factsAborted = true;
          });
          return never;
        },
      },
    );
    const rpc: PipelineRpcClient = {
      rpc: (name) => {
        if (name === "pipeline_recent_extraction_activity") {
          return Promise.resolve({ data: [activity()], error: null });
        }
        return never;
      },
    };
    const snapshot = await snapshotFromRpc(rpc, NOW, 5, 1);
    expect(snapshot.load_error).toBe(true);
    expect(snapshot.activity_load_error).toBe(false);
    expect(snapshot.extraction_activity).toHaveLength(1);
    expect(factsAborted).toBe(true);
  });

  it("isStaticBuild seed paints SLA down and yearly slate", () => {
    const seed = seedPipelineSnapshot(NOW, false);
    expect(seed.load_error).toBe(false);
    expect(seed.strip.lamp).toBe("down");
    expect(seed.strip.text).not.toBe("Could not load station clocks.");
    const yearly = seed.stations.filter((station) => station.station_id === "schema_build" || station.station_id === "scorecard_load");
    expect(yearly.every((station) => station.lamp === "slate")).toBe(true);
    const sla = seed.stations.filter((station) => station.station_id === "finder_brave");
    expect(sla[0]?.lamp).toBe("down");
    expect(seed.manual_sources.map((row) => row.station_id)).toEqual([
      "directory_enqueue",
      "mirror_ingest",
    ]);
    expect(seed.stations.some((station) => station.station_id === "headless_archive")).toBe(true);
  });

  it("paints a daily extract cap as capped with files still waiting", () => {
    const snapshot = snapshotFromFacts(
      [
        fact({
          station_id: "extraction_worker",
          display_name: "Extract",
          class: "daily_sla",
          last_scheduled_status: "ok",
          last_scheduled_finished_at: "2026-08-21T16:23:00.000Z",
          last_scheduled_summary: {
            extracted: 4,
            failed: 0,
            pending_remaining: 3,
            stopped_reason: "deadline",
          },
          extraction_pending: 3,
        }),
      ],
      NOW,
    );
    const extract = snapshot.stations.find(
      (station) => station.station_id === "extraction_worker",
    );
    expect(extract?.lamp).toBe("capped");
    expect(extract?.result_line).toBe("3 still waiting");
  });
});

describe("pipeline observation CSS hex allowlist", () => {
  it("uses only the PRD lamp hexes plus white; no teal, no blue", () => {
    const cssPath = join(
      dirname(fileURLToPath(import.meta.url)),
      "../app/pipeline-observation/pipeline-observation.css",
    );
    const css = readFileSync(cssPath, "utf8");
    expect(css.toLowerCase()).not.toContain("#2a9d8f");
    expect(css.toLowerCase()).not.toMatch(/#[0-9a-f]{6}.*(blue|teal)/i);
    const hexes = css.match(/#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/g) ?? [];
    for (const hex of hexes) {
      const normalized = hex.length === 4
        ? `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`.toLowerCase()
        : hex.toLowerCase();
      expect(ALLOWED_HEX.has(normalized)).toBe(true);
    }
  });
});

describe("pipeline redirects", () => {
  it("308s /pipeline to /pipeline-observation", async () => {
    expect(PIPELINE_OBSERVATION_REDIRECTS).toEqual([
      {
        source: "/pipeline",
        destination: "/pipeline-observation",
        statusCode: 308,
      },
    ]);
    const redirects = await nextConfig.redirects?.();
    expect(redirects).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: "/pipeline",
          destination: "/pipeline-observation",
          statusCode: 308,
        }),
      ]),
    );
  });

  it("leaves trailingSlash unset/false so /pipeline-observation/ 308s to the canonical path", () => {
    expect(nextConfig.trailingSlash).not.toBe(true);
  });
});
