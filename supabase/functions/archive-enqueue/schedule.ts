import {
  DEFAULT_COOLDOWN_DAYS,
  ProbeOutcome,
} from "../_shared/probe_outcome.ts";

const FRESHNESS_SEASON_START_MONTH = 3;
const FRESHNESS_SEASON_END_MONTH = 6;
const FRESHNESS_SEASON_UNCHANGED_COOLDOWN_DAYS = 7;

export function isFreshnessSeason(now: Date): boolean {
  const month = now.getUTCMonth() + 1;
  return month >= FRESHNESS_SEASON_START_MONTH &&
    month <= FRESHNESS_SEASON_END_MONTH;
}

export function archiveEnqueueRunKey(now: Date): string {
  if (isFreshnessSeason(now)) {
    const { year, week } = isoWeek(now);
    return `archive-enqueue:${year}-W${week.toString().padStart(2, "0")}`;
  }

  const yyyy = now.getUTCFullYear().toString().padStart(4, "0");
  const mm = (now.getUTCMonth() + 1).toString().padStart(2, "0");
  return `archive-enqueue:${yyyy}-${mm}`;
}

export async function archiveEnqueueRunId(now: Date): Promise<string> {
  const data = new TextEncoder().encode(archiveEnqueueRunKey(now));
  const hashBuf = await crypto.subtle.digest("SHA-256", data);
  const hex = Array.from(new Uint8Array(hashBuf).slice(0, 16))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return (
    hex.slice(0, 8) + "-" +
    hex.slice(8, 12) + "-" +
    hex.slice(12, 16) + "-" +
    hex.slice(16, 20) + "-" +
    hex.slice(20, 32)
  );
}

export function archiveCooldownDaysForOutcome(
  outcome: ProbeOutcome,
  now: Date,
): number {
  if (outcome === "unchanged_verified" && isFreshnessSeason(now)) {
    return FRESHNESS_SEASON_UNCHANGED_COOLDOWN_DAYS;
  }
  return DEFAULT_COOLDOWN_DAYS[outcome] ?? 0;
}

function isoWeek(now: Date): { year: number; week: number } {
  const date = new Date(Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate(),
  ));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const year = date.getUTCFullYear();
  const yearStart = new Date(Date.UTC(year, 0, 1));
  const week = Math.ceil(
    (((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7,
  );
  return { year, week };
}
