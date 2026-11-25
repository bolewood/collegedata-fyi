export type StationClass =
  | "monthly_sla"
  | "daily_sla"
  | "hourly_sla"
  | "continuous_sla"
  | "yearly"
  | "adhoc";

export type HeartbeatStatus = "never" | "running" | "ok" | "error";

export type Lamp = "capped" | "down" | "late" | "ok" | "run" | "slate";

export type StripLamp = "down" | "late" | "ok";

export const LAMP_HEX = {
  capped: "#d5e3cf",
  cappedInk: "#27321f",
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
  "discovery_renewal",
  "finder_brave",
  "finder_stuck_pdf",
  "finder_landing_hints",
  "archive_enqueue",
  "archive_process",
  "headless_archive",
  "extraction_worker",
  "coverage_refresh",
  "serving_cache_refresh",
  "corpus_audit",
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
  lastSummary?: Record<string, unknown> | null;
  /** False when the station is absent from the facts RPC although facts loaded. */
  registered?: boolean;
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
    (stoppedReason === "cap" || stoppedReason === "deadline")
  ) {
    return "capped";
  }
  if (pending > 0 && extracted === 0) return "late";
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

const STUCK_MIN_SAMPLE = 10;
const STUCK_DOWN_SHARE = 0.9;
const STUCK_LATE_SHARE = 0.5;

function strictCount(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

/**
 * Share of stuck PDFs the sweep failed to move. "malformed" when either count
 * is missing, null, non-numeric or negative; null when the sample is under the floor.
 */
export function stuckShare(
  summary: Record<string, unknown> | null | undefined,
): number | null | "malformed" {
  const stuck = strictCount(summary?.stuck);
  const still = strictCount(summary?.still_stuck);
  if (stuck === null || still === null) return "malformed";
  if (stuck < STUCK_MIN_SAMPLE) return null;
  return still / stuck;
}

function stuckPdfLamp(input: StationLampInput): Lamp {
  const base = slaLamp(input, FORTY_DAYS_MS);
  if (base !== "ok") return base;
  const share = stuckShare(input.lastScheduledSummary);
  if (share === "malformed") return "down";
  if (share === null) return "ok";
  if (share >= STUCK_DOWN_SHARE) return "down";
  if (share > STUCK_LATE_SHARE) return "late";
  return "ok";
}

/**
 * Summary of the most recent finish. A dispatched run wins only when it
 * finished ok and is newer than the last scheduled finish; a running or failed
 * dispatch (whose summary is empty) never replaces a scheduled result.
 */
export function renewalOutcomeSummary(
  input: Pick<
    StationLampInput,
    "lastStatus" | "lastFinishedAt" | "lastScheduledFinishedAt" | "lastSummary" | "lastScheduledSummary"
  >,
): Record<string, unknown> {
  const any = input.lastFinishedAt ? new Date(input.lastFinishedAt).getTime() : NaN;
  const sched = input.lastScheduledFinishedAt
    ? new Date(input.lastScheduledFinishedAt).getTime()
    : NaN;
  const dispatchWins =
    input.lastStatus === "ok" &&
    Number.isFinite(any) &&
    (!Number.isFinite(sched) || any > sched);
  if (dispatchWins) {
    const dispatch = input.lastSummary ?? {};
    // A floor override may turn the lamp red but never green.
    if (
      dispatch.floor_overridden !== true ||
      dispatch.below_floor === true ||
      dispatch.next_below_floor === true ||
      dispatch.two_year_below_floor === true ||
      dispatch.outstanding_below_floor === true ||
      dispatch.arrivals_below_floor === true
    ) {
      return dispatch;
    }
  }
  return input.lastScheduledSummary ?? {};
}

/** True when the renewal outcome proves the share is at or above the floor. */
export function renewalOutcomeHealthy(outcome: Record<string, unknown>): boolean {
  return (
    outcome.below_floor === false &&
    strictCount(outcome.renewed) !== null &&
    (strictCount(outcome.prev_schools) ?? 0) > 0 &&
    outcome.next_below_floor !== true &&
    outcome.two_year_below_floor !== true &&
    outcome.outstanding_below_floor !== true &&
    outcome.arrivals_below_floor !== true
  );
}

function renewalLamp(input: StationLampInput): Lamp {
  if (input.registered === false) return "slate";
  if (slaLamp(input, THIRTY_SIX_HOURS_MS) !== "ok") return "down";
  return renewalOutcomeHealthy(renewalOutcomeSummary(input)) ? "ok" : "down";
}

/** Down for a failed result while the clock is fresh (not an overdue clock). */
export function isResultFailure(input: StationLampInput, lamp: Lamp): boolean {
  if (lamp !== "down" && lamp !== "late") return false;
  if (runningState(input) === "stale") return false;
  if (input.stationId === "discovery_renewal") {
    return input.registered !== false && scheduledOkWithin(input, THIRTY_SIX_HOURS_MS);
  }
  if (input.stationId === "finder_stuck_pdf") {
    return scheduledOkWithin(input, FORTY_DAYS_MS);
  }
  return false;
}

export function stationLamp(input: StationLampInput): Lamp {
  if (input.stationId === "discovery_renewal" && input.registered === false) return "slate";
  const running = runningState(input);
  if (running === "stale") return "down";
  if (running === "fresh" && RUN_STATION_IDS.has(input.stationId)) return "run";
  if (input.stationId === "discovery_renewal") return renewalLamp(input);
  if (input.stationId === "finder_stuck_pdf") return stuckPdfLamp(input);

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
