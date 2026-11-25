import { describe, expect, it } from "vitest";
import {
  BOARD_STATION_IDS,
  isResultFailure,
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

  it("extraction cap or deadline with pending remaining is capped, not late", () => {
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
    ).toBe("capped");
    expect(
      stationLamp(
        base({
          stationId: "extraction_worker",
          class: "daily_sla",
          lastScheduledStatus: "ok",
          lastScheduledFinishedAt: hoursAgo(1),
          extractionPending: 3,
          lastScheduledSummary: {
            extracted: 4,
            failed: 0,
            pending_remaining: 3,
            stopped_reason: "deadline",
          },
        }),
      ),
    ).toBe("capped");
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
    expect(stripLamp(["ok", "capped", "slate"])).toBe("ok");
    expect(stripLamp(["ok", "late", "slate"])).toBe("late");
    expect(stripLamp(["ok", "down", "late"])).toBe("down");
  });

  it("board has twelve stations", () => {
    expect(BOARD_STATION_IDS).toHaveLength(14);
    expect(BOARD_STATION_IDS).toContain("corpus_audit");
    expect(BOARD_STATION_IDS).toContain("headless_archive");
    expect(BOARD_STATION_IDS).not.toContain("directory_enqueue");
  });

  describe("discovery_renewal", () => {
    const GOOD = { below_floor: false, renewed: 400, prev_schools: 479, floor_pct: 82 };
    const BAD = { below_floor: true, renewed: 364, prev_schools: 479, floor_pct: 82 };
    const renewal = (o: Partial<StationLampInput> = {}) =>
      base({
        stationId: "discovery_renewal",
        class: "daily_sla",
        lastStatus: "ok",
        lastFinishedAt: hoursAgo(5),
        lastScheduledFinishedAt: hoursAgo(5),
        lastSummary: GOOD,
        lastScheduledSummary: GOOD,
        registered: true,
        ...o,
      });

    it("absent from facts is slate, never down", () => {
      expect(
        stationLamp(
          renewal({
            registered: false,
            lastStatus: "never",
            lastScheduledStatus: "never",
            lastFinishedAt: null,
            lastScheduledFinishedAt: null,
          }),
        ),
      ).toBe("slate");
    });

    it("registered but never run is down", () => {
      expect(
        stationLamp(
          renewal({
            lastStatus: "never",
            lastScheduledStatus: "never",
            lastFinishedAt: null,
            lastScheduledFinishedAt: null,
          }),
        ),
      ).toBe("down");
    });

    it("other stations absent from facts keep their old behaviour (down)", () => {
      expect(
        stationLamp(
          base({
            stationId: "archive_enqueue",
            registered: false,
            lastStatus: "never",
            lastScheduledStatus: "never",
            lastScheduledFinishedAt: null,
          }),
        ),
      ).toBe("down");
    });

    it("fresh ok scheduled run above the floor is ok", () => {
      expect(stationLamp(renewal())).toBe("ok");
    });

    it("is routed by station id even if the class changes", () => {
      expect(
        stationLamp(renewal({ class: "monthly_sla", lastSummary: BAD, lastScheduledSummary: BAD })),
      ).toBe("down");
    });

    it("prev_schools of 0 is down", () => {
      const z = { below_floor: false, renewed: 0, prev_schools: 0 };
      expect(stationLamp(renewal({ lastSummary: z, lastScheduledSummary: z }))).toBe("down");
    });

    it("a hung run is a clock failure, not a result failure", () => {
      const hung = renewal({ lastStatus: "running", lastStartedAt: hoursAgo(9) });
      expect(stationLamp(hung)).toBe("down");
      expect(isResultFailure(hung, "down")).toBe(false);
      expect(isResultFailure(renewal({ lastSummary: BAD, lastScheduledSummary: BAD }), "down")).toBe(true);
    });

    it("scheduled heartbeat older than 36h is down", () => {
      expect(
        stationLamp(renewal({ lastFinishedAt: hoursAgo(37), lastScheduledFinishedAt: hoursAgo(37) })),
      ).toBe("down");
    });

    it("last scheduled error is down; stale running is down", () => {
      expect(stationLamp(renewal({ lastScheduledStatus: "error" }))).toBe("down");
      expect(
        stationLamp(renewal({ lastStatus: "running", lastStartedAt: hoursAgo(9) })),
      ).toBe("down");
    });

    it("below_floor or next_below_floor is down", () => {
      expect(stationLamp(renewal({ lastSummary: BAD, lastScheduledSummary: BAD }))).toBe("down");
      const n = { ...GOOD, next_below_floor: true };
      expect(stationLamp(renewal({ lastSummary: n, lastScheduledSummary: n }))).toBe("down");
    });

    it("fails closed on missing, null, string or numeric flags and counts", () => {
      const cases: Array<Record<string, unknown>> = [
        {},
        { renewed: 400, prev_schools: 479 },
        { ...GOOD, below_floor: null },
        { ...GOOD, below_floor: "false" },
        { ...GOOD, below_floor: 0 },
        { ...GOOD, renewed: null },
        { ...GOOD, prev_schools: "479" },
      ];
      for (const summary of cases) {
        expect(
          stationLamp(renewal({ lastSummary: summary, lastScheduledSummary: summary })),
        ).toBe("down");
      }
    });

    it("a newer ok dispatch below floor turns it down; a newer ok dispatch above floor restores it", () => {
      const down = stationLamp(
        renewal({
          lastScheduledSummary: GOOD,
          lastScheduledFinishedAt: hoursAgo(10),
          lastSummary: BAD,
          lastFinishedAt: hoursAgo(2),
        }),
      );
      expect(down).toBe("down");
      const restored = stationLamp(
        renewal({
          lastScheduledSummary: BAD,
          lastScheduledFinishedAt: hoursAgo(10),
          lastSummary: GOOD,
          lastFinishedAt: hoursAgo(1),
        }),
      );
      expect(restored).toBe("ok");
    });

    it("two_year_below_floor is down; absent is ignored", () => {
      const t = { ...GOOD, two_year_below_floor: true };
      expect(stationLamp(renewal({ lastSummary: t, lastScheduledSummary: t }))).toBe("down");
      expect(stationLamp(renewal())).toBe("ok");
    });

    it("an overridden dispatch below the two-year floor turns red, never green", () => {
      const t = { ...GOOD, floor_overridden: true, two_year_below_floor: true };
      expect(
        stationLamp(
          renewal({
            lastScheduledSummary: GOOD,
            lastScheduledFinishedAt: hoursAgo(10),
            lastSummary: t,
            lastFinishedAt: hoursAgo(2),
          }),
        ),
      ).toBe("down");
      const sched = { ...GOOD, two_year_below_floor: true };
      expect(
        stationLamp(
          renewal({
            lastScheduledSummary: sched,
            lastScheduledFinishedAt: hoursAgo(10),
            lastSummary: { ...GOOD, floor_overridden: true },
            lastFinishedAt: hoursAgo(2),
          }),
        ),
      ).toBe("down");
    });

    it("an overridden dispatch can turn the lamp red but never green", () => {
      const overridden = { ...GOOD, floor_overridden: true };
      // scheduled below floor + newer overridden dispatch not below floor: still down
      expect(
        stationLamp(
          renewal({
            lastScheduledSummary: BAD,
            lastScheduledFinishedAt: hoursAgo(10),
            lastSummary: overridden,
            lastFinishedAt: hoursAgo(2),
          }),
        ),
      ).toBe("down");
      // scheduled ok + newer overridden dispatch below floor: down
      expect(
        stationLamp(
          renewal({
            lastScheduledSummary: GOOD,
            lastScheduledFinishedAt: hoursAgo(10),
            lastSummary: { ...BAD, floor_overridden: true },
            lastFinishedAt: hoursAgo(2),
          }),
        ),
      ).toBe("down");
      // a newer non-overridden ok dispatch above floor restores it
      expect(
        stationLamp(
          renewal({
            lastScheduledSummary: BAD,
            lastScheduledFinishedAt: hoursAgo(10),
            lastSummary: GOOD,
            lastFinishedAt: hoursAgo(1),
          }),
        ),
      ).toBe("ok");
    });

    it("an older dispatch finish does not override the newer scheduled summary", () => {
      expect(
        stationLamp(
          renewal({
            lastScheduledSummary: GOOD,
            lastScheduledFinishedAt: hoursAgo(2),
            lastSummary: BAD,
            lastFinishedAt: hoursAgo(6),
          }),
        ),
      ).toBe("ok");
    });

    it("a running heartbeat with an empty summary does not hide a below-floor scheduled result", () => {
      expect(
        stationLamp(
          renewal({
            lastStatus: "running",
            lastStartedAt: hoursAgo(0.1),
            lastFinishedAt: hoursAgo(1),
            lastSummary: GOOD,
            lastScheduledSummary: BAD,
            lastScheduledFinishedAt: hoursAgo(10),
          }),
        ),
      ).toBe("down");
    });

    it("a failed dispatch with an empty summary does not hide a below-floor scheduled result", () => {
      expect(
        stationLamp(
          renewal({
            lastStatus: "error",
            lastFinishedAt: hoursAgo(1),
            lastSummary: GOOD,
            lastScheduledSummary: BAD,
            lastScheduledFinishedAt: hoursAgo(10),
          }),
        ),
      ).toBe("down");
    });
  });

  describe("finder_stuck_pdf result lamp", () => {
    const stuck = (summary: Record<string, unknown>, o: Partial<StationLampInput> = {}) =>
      base({
        stationId: "finder_stuck_pdf",
        class: "monthly_sla",
        lastScheduledFinishedAt: daysAgo(3),
        lastScheduledSummary: summary,
        ...o,
      });

    it("71 of 78 still stuck is down", () => {
      expect(stationLamp(stuck({ stuck: 78, reprobed: 78, still_stuck: 71 }))).toBe("down");
    });
    it("40 of 78 still stuck is late; 39 of 78 (exactly half) is ok", () => {
      expect(stationLamp(stuck({ stuck: 78, still_stuck: 40 }))).toBe("late");
      expect(stationLamp(stuck({ stuck: 78, still_stuck: 39 }))).toBe("ok");
    });
    it("exactly 90% is down; exactly 50% is ok", () => {
      expect(stationLamp(stuck({ stuck: 10, still_stuck: 9 }))).toBe("down");
      expect(stationLamp(stuck({ stuck: 10, still_stuck: 5 }))).toBe("ok");
    });
    it("fewer than 10 stuck is ok even when all are still stuck", () => {
      expect(stationLamp(stuck({ stuck: 9, still_stuck: 9 }))).toBe("ok");
    });
    it("missing or malformed counts on a scheduled ok summary fail closed", () => {
      const bad: Array<Record<string, unknown>> = [
        {},
        { stuck: 78, still_stuck: null },
        { stuck: 78, still_stuck: "" },
        { stuck: 78, still_stuck: true },
        { stuck: 78, still_stuck: -1 },
        { stuck: null, still_stuck: 71 },
        { still_stuck: 71 },
      ];
      for (const summary of bad) expect(stationLamp(stuck(summary))).toBe("down");
    });
    it("is routed by station id even if the class changes", () => {
      expect(
        stationLamp(stuck({ stuck: 78, still_stuck: 71 }, { class: "daily_sla" })),
      ).toBe("down");
    });
    it("an overdue heartbeat is down regardless of the result", () => {
      expect(
        stationLamp(stuck({ stuck: 78, still_stuck: 1 }, { lastScheduledFinishedAt: daysAgo(41) })),
      ).toBe("down");
    });
  });
});
