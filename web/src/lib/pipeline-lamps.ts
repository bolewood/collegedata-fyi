export type StationClass =
  | "monthly_sla"
  | "daily_sla"
  | "hourly_sla"
  | "continuous_sla"
  | "yearly"
  | "adhoc";

export type HeartbeatStatus = "never" | "running" | "ok" | "error";

export type Lamp = "down" | "late" | "ok" | "run" | "slate";

export type StripLamp = "down" | "late" | "ok";

export const LAMP_HEX = {
  down: "#d7263d",
  late: "#e0a106",
  ok: "#1f7a4d",
  lock: "#6b3fa0",
  sso: "#7a2f6a",
  waf: "#c45c14",
  slate: "#5c5a54",
  lateInk: "#1c1400",
} as const;

export const BOARD_STATION_IDS = [
  "finder_brave",
  "finder_stuck_pdf",
  "finder_landing_hints",
  "archive_enqueue",
  "archive_process",
  "headless_archive",
  "extraction_worker",
  "coverage_refresh",
  "serving_cache_refresh",
  "ipeds_release_probe",
  "schema_build",
  "scorecard_load",
] as const;

export const MANUAL_STATION_IDS = ["directory_enqueue", "mirror_ingest"] as const;

export const RUN_STATION_IDS = new Set<string>([
  "finder_brave",
  "finder_stuck_pdf",
  "finder_landing_hints",
  "headless_archive",
  "extraction_worker",
]);

const EIGHT_HOURS_MS = 8 * 60 * 60 * 1000;
const FIFTEEN_MINUTES_MS = 15 * 60 * 1000;
const TWO_HOURS_MS = 2 * 60 * 60 * 1000;
const THIRTY_SIX_HOURS_MS = 36 * 60 * 60 * 1000;
const THREE_HOURS_MS = 3 * 60 * 60 * 1000;
const FORTY_DAYS_MS = 40 * 24 * 60 * 60 * 1000;
const EIGHTEEN_MONTHS_MS = 18 * 30 * 24 * 60 * 60 * 1000;

export type StationLampInput = {
  stationId: string;
  class: StationClass;
  lastStatus: HeartbeatStatus | null;
  lastStartedAt: string | null;
  lastFinishedAt: string | null;
  lastScheduledStatus: HeartbeatStatus | null;
  lastScheduledFinishedAt: string | null;
  lastScheduledSummary?: Record<string, unknown> | null;
  queueUnfinished?: number | null;
  extractionPending?: number | null;
  now: Date;
};

function ageMs(iso: string | null | undefined, now: Date): number | null {
  if (!iso) return null;
  const ms = now.getTime() - new Date(iso).getTime();
  return Number.isFinite(ms) ? ms : null;
}

function scheduledOkWithin(input: StationLampInput, windowMs: number): boolean {
  if (input.lastScheduledStatus !== "ok") return false;
  const age = ageMs(input.lastScheduledFinishedAt, input.now);
  return age !== null && age <= windowMs;
}

function runningState(input: StationLampInput): "fresh" | "stale" | null {
  if (input.lastStatus !== "running") return null;
  const age = ageMs(input.lastStartedAt, input.now);
  if (age === null || age > EIGHT_HOURS_MS) return "stale";
  return "fresh";
}

function yearlyLamp(input: StationLampInput): Lamp {
  const finishedAge = ageMs(input.lastFinishedAt, input.now);
  if (input.lastFinishedAt && finishedAge !== null && finishedAge > EIGHTEEN_MONTHS_MS) {
    return "down";
  }
  return "slate";
}

function extractionLamp(input: StationLampInput): Lamp {
  if (!scheduledOkWithin(input, THIRTY_SIX_HOURS_MS)) return "down";
  const summary = input.lastScheduledSummary ?? {};
  const pending = Number(input.extractionPending ?? 0);
  const extracted = Number(summary.extracted ?? 0);
  const stoppedReason = String(summary.stopped_reason ?? "");
  if (
    pending > 0 &&
    (stoppedReason === "cap" || stoppedReason === "deadline" || extracted === 0)
  ) {
    return "late";
  }
  return "ok";
}

function archiveProcessLamp(input: StationLampInput): Lamp {
  const unfinished = Number(input.queueUnfinished ?? 0);
  const scheduledAge = ageMs(input.lastScheduledFinishedAt, input.now);
  if (unfinished > 0) {
    if (input.lastScheduledStatus !== "ok") return "down";
    if (scheduledAge === null || scheduledAge > FIFTEEN_MINUTES_MS) return "down";
    return "ok";
  }
  if (scheduledAge === null || scheduledAge > TWO_HOURS_MS) return "down";
  if (input.lastScheduledStatus === "error") return "down";
  if (input.lastScheduledStatus === "ok") return "ok";
  return "down";
}

function slaLamp(input: StationLampInput, windowMs: number): Lamp {
  if (input.lastScheduledStatus === "error") return "down";
  if (scheduledOkWithin(input, windowMs)) return "ok";
  return "down";
}

export function stationLamp(input: StationLampInput): Lamp {
  const running = runningState(input);
  if (running === "stale") return "down";
  if (running === "fresh" && RUN_STATION_IDS.has(input.stationId)) return "run";

  switch (input.class) {
    case "yearly":
      return yearlyLamp(input);
    case "adhoc":
      return "slate";
    case "continuous_sla":
      return archiveProcessLamp(input);
    case "monthly_sla":
      return slaLamp(input, FORTY_DAYS_MS);
    case "hourly_sla":
      return slaLamp(input, THREE_HOURS_MS);
    case "daily_sla":
      if (input.stationId === "extraction_worker") return extractionLamp(input);
      return slaLamp(input, THIRTY_SIX_HOURS_MS);
    default:
      return "down";
  }
}

export function stripLamp(boardLamps: Lamp[]): StripLamp {
  if (boardLamps.some((lamp) => lamp === "down")) return "down";
  if (boardLamps.some((lamp) => lamp === "late")) return "late";
  return "ok";
}
