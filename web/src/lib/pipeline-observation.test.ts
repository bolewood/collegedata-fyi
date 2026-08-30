import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";
import { LAMP_HEX } from "./pipeline-lamps";
import { PIPELINE_OBSERVATION_REDIRECTS } from "./pipeline-redirect";
import {
  seedPipelineSnapshot,
  snapshotFromFacts,
  toPublicJson,
  type PipelineFactRow,
} from "./pipeline-observation";

const NOW = new Date("2026-08-21T20:00:00.000Z");

const ALLOWED_HEX = new Set(
  [
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
