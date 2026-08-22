// Shared heartbeat writer for edge functions. Catch, log, never throw.
// A missing RPC (local/fresh DB before the migration) must not fail archive.

export type HeartbeatStatus = "running" | "ok" | "error";
export type HeartbeatTrigger = "schedule" | "dispatch" | "operator" | "cron";

export async function recordPipelineHeartbeat(
  // deno-lint-ignore no-explicit-any
  supabase: { rpc: (fn: string, args: Record<string, unknown>) => Promise<{ error: { message: string } | null }> | any },
  args: {
    stationId: string;
    status: HeartbeatStatus;
    trigger: HeartbeatTrigger;
    summary?: Record<string, unknown>;
    errorCode?: string;
  },
): Promise<void> {
  try {
    const { error } = await supabase.rpc("record_pipeline_heartbeat", {
      p_station_id: args.stationId,
      p_status: args.status,
      p_trigger: args.trigger,
      p_summary: args.summary ?? {},
      p_error_code: args.errorCode ?? "none",
    });
    if (error) {
      console.warn(
        `::warning::pipeline heartbeat failed for ${args.stationId}: ${error.message}`,
      );
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(
      `::warning::pipeline heartbeat failed for ${args.stationId}: ${message}`,
    );
  }
}

export async function countArchiveUnfinished(
  // deno-lint-ignore no-explicit-any
  supabase: any,
): Promise<number> {
  try {
    const { count, error } = await supabase
      .from("archive_queue")
      .select("id", { count: "exact", head: true })
      .in("status", ["ready", "processing"]);
    if (error) return 0;
    return count ?? 0;
  } catch {
    return 0;
  }
}

const WALLED = new Set([
  "auth_walled_microsoft",
  "auth_walled_okta",
  "auth_walled_google",
  "bot_challenge",
]);

export function isWalledOutcome(outcome: string | null | undefined): boolean {
  return Boolean(outcome && WALLED.has(outcome));
}
