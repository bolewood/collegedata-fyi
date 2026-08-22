import { describe, expect, it } from "vitest";
import {
  BOARD_STATION_IDS,
  stationLamp,
  stripLamp,
  type HeartbeatStatus,
  type StationClass,
  type StationLampInput,
} from "./pipeline-lamps";

const NOW = new Date("2026-08-21T20:00:00.000Z");

function hoursAgo(hours: number): string {
  return new Date(NOW.getTime() - hours * 60 * 60 * 1000).toISOString();
}

function daysAgo(days: number): string {
  return hoursAgo(days * 24);
}

function base(overrides: Partial<StationLampInput> = {}): StationLampInput {
  return {
    stationId: "archive_enqueue",
    class: "daily_sla",
    lastStatus: "ok",
    lastStartedAt: hoursAgo(11),
    lastFinishedAt: hoursAgo(11),
    lastScheduledStatus: "ok",
    lastScheduledFinishedAt: hoursAgo(11),
    lastScheduledSummary: {},
    queueUnfinished: 0,
    extractionPending: 0,
    now: NOW,
    ...overrides,
  };
}

const CLASSES: StationClass[] = [
  "monthly_sla",
  "daily_sla",
  "hourly_sla",
  "continuous_sla",
  "yearly",
  "adhoc",
];
const STATUSES: HeartbeatStatus[] = ["never", "running", "ok", "error"];

describe("stationLamp", () => {
  it("scheduled error yesterday + dispatch ok today is still down", () => {
    expect(
      stationLamp(
        base({
          stationId: "finder_brave",
          class: "monthly_sla",
          lastStatus: "ok",
          lastFinishedAt: hoursAgo(2),
          lastScheduledStatus: "error",
          lastScheduledFinishedAt: hoursAgo(20),
        }),
      ),
    ).toBe("down");
  });

  it("seed never is down for SLA stations and slate for yearly", () => {
    expect(
      stationLamp(
        base({
          stationId: "finder_brave",
          class: "monthly_sla",
          lastStatus: "never",
          lastScheduledStatus: "never",
          lastScheduledFinishedAt: null,
          lastFinishedAt: null,
        }),
      ),
    ).toBe("down");
    expect(
      stationLamp(
        base({
          stationId: "schema_build",
          class: "yearly",
          lastStatus: "never",
          lastScheduledStatus: "never",
          lastFinishedAt: null,
        }),
      ),
    ).toBe("slate");
  });

  it("archive_process unfinished=0 cron 30s ago is ok; 3h ago is down; unfinished>0 20min is down", () => {
    expect(
      stationLamp(
        base({
          stationId: "archive_process",
          class: "continuous_sla",
          lastScheduledStatus: "ok",
          lastScheduledFinishedAt: new Date(NOW.getTime() - 30_000).toISOString(),
          queueUnfinished: 0,
        }),
      ),
    ).toBe("ok");
    expect(
      stationLamp(
        base({
          stationId: "archive_process",
          class: "continuous_sla",
          lastScheduledStatus: "ok",
          lastScheduledFinishedAt: hoursAgo(3),
          queueUnfinished: 0,
        }),
      ),
    ).toBe("down");
    expect(
      stationLamp(
        base({
          stationId: "archive_process",
          class: "continuous_sla",
          lastScheduledStatus: "ok",
          lastScheduledFinishedAt: hoursAgo(20 / 60),
          queueUnfinished: 4,
        }),
      ),
    ).toBe("down");
  });

  it("running longer than 8 hours is down", () => {
    expect(
      stationLamp(
        base({
          stationId: "extraction_worker",
          class: "daily_sla",
          lastStatus: "running",
          lastStartedAt: hoursAgo(9),
          lastScheduledStatus: "ok",
          lastScheduledFinishedAt: hoursAgo(10),
        }),
      ),
    ).toBe("down");
  });

  it("finder/extraction running within 8 hours is run", () => {
    expect(
      stationLamp(
        base({
          stationId: "finder_brave",
          class: "monthly_sla",
          lastStatus: "running",
          lastStartedAt: hoursAgo(1),
          lastScheduledStatus: "ok",
          lastScheduledFinishedAt: daysAgo(12),
        }),
      ),
    ).toBe("run");
  });

  it("extraction cap with pending remaining is late, not down", () => {
    expect(
      stationLamp(
        base({
          stationId: "extraction_worker",
          class: "daily_sla",
          lastScheduledStatus: "ok",
          lastScheduledFinishedAt: hoursAgo(20),
          extractionPending: 84,
          lastScheduledSummary: {
            extracted: 5,
            failed: 0,
            pending_remaining: 84,
            stopped_reason: "cap",
          },
        }),
      ),
    ).toBe("late");
  });

  it("extraction extracted=0 with pending is late", () => {
    expect(
      stationLamp(
        base({
          stationId: "extraction_worker",
          class: "daily_sla",
          lastScheduledStatus: "ok",
          lastScheduledFinishedAt: hoursAgo(4),
          extractionPending: 12,
          lastScheduledSummary: {
            extracted: 0,
            failed: 0,
            pending_remaining: 12,
            stopped_reason: "complete",
          },
        }),
      ),
    ).toBe("late");
  });

  it("yearly finish older than 18 months is down; recent finish stays slate", () => {
    expect(
      stationLamp(
        base({
          stationId: "scorecard_load",
          class: "yearly",
          lastFinishedAt: daysAgo(19 * 30),
          lastStatus: "ok",
        }),
      ),
    ).toBe("down");
    expect(
      stationLamp(
        base({
          stationId: "scorecard_load",
          class: "yearly",
          lastFinishedAt: daysAgo(40),
          lastStatus: "ok",
        }),
      ),
    ).toBe("slate");
  });

  it("covers the (class, status, age) matrix without throwing", () => {
    const ages = [null, hoursAgo(0.1), hoursAgo(4), hoursAgo(40), daysAgo(50), daysAgo(600)];
    const lamps = new Set<string>();
    for (const stationClass of CLASSES) {
      for (const status of STATUSES) {
        for (const age of ages) {
          lamps.add(
            stationLamp(
              base({
                stationId:
                  stationClass === "continuous_sla"
                    ? "archive_process"
                    : stationClass === "yearly"
                      ? "schema_build"
                      : stationClass === "adhoc"
                        ? "directory_enqueue"
                        : "finder_brave",
                class: stationClass,
                lastStatus: status,
                lastStartedAt: age,
                lastFinishedAt: age,
                lastScheduledStatus: status,
                lastScheduledFinishedAt: age,
                queueUnfinished: stationClass === "continuous_sla" ? 1 : 0,
                extractionPending: 0,
              }),
            ),
          );
        }
      }
    }
    expect(lamps.has("down")).toBe(true);
    expect(lamps.has("slate")).toBe(true);
    expect(lamps.has("ok") || lamps.has("run") || lamps.has("late")).toBe(true);
  });
});

describe("stripLamp", () => {
  it("omits yearly slate and manual stations from the brick", () => {
    expect(stripLamp(["ok", "ok", "slate", "run"])).toBe("ok");
    expect(stripLamp(["ok", "late", "slate"])).toBe("late");
    expect(stripLamp(["ok", "down", "late"])).toBe("down");
  });

  it("board has eleven stations", () => {
    expect(BOARD_STATION_IDS).toHaveLength(11);
    expect(BOARD_STATION_IDS).not.toContain("directory_enqueue");
  });
});
