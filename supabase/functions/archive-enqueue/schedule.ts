import {
  DEFAULT_COOLDOWN_DAYS,
  ProbeOutcome,
} from "../_shared/probe_outcome.ts";

const UNCHANGED_COOLDOWN_DAYS = 7;

export function archiveEnqueueRunKey(now: Date): string {
  const yyyy = now.getUTCFullYear().toString().padStart(4, "0");
  const mm = (now.getUTCMonth() + 1).toString().padStart(2, "0");
  const dd = now.getUTCDate().toString().padStart(2, "0");
  return `archive-enqueue:${yyyy}-${mm}-${dd}`;
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
  _now: Date,
): number {
  if (outcome === "unchanged_verified") {
    return UNCHANGED_COOLDOWN_DAYS;
  }
  return DEFAULT_COOLDOWN_DAYS[outcome] ?? 0;
}
