import { assertEquals } from "jsr:@std/assert";
import {
  isWalledOutcome,
  recordPipelineHeartbeat,
} from "./pipeline_heartbeat.ts";

Deno.test("isWalledOutcome allowlists SSO and bot challenge only", () => {
  assertEquals(isWalledOutcome("auth_walled_microsoft"), true);
  assertEquals(isWalledOutcome("bot_challenge"), true);
  assertEquals(isWalledOutcome("wrong_content_type"), false);
  assertEquals(isWalledOutcome("marked_removed"), false);
  assertEquals(isWalledOutcome(null), false);
});

Deno.test("recordPipelineHeartbeat swallows RPC errors", async () => {
  const warnings: string[] = [];
  const originalWarn = console.warn;
  console.warn = (...args: unknown[]) => {
    warnings.push(String(args[0] ?? ""));
  };
  try {
    await recordPipelineHeartbeat(
      {
        rpc: async () => ({ error: { message: "boom" } }),
      },
      {
        stationId: "archive_process",
        status: "ok",
        trigger: "cron",
        summary: { dequeued: 0 },
      },
    );
  } finally {
    console.warn = originalWarn;
  }
  assertEquals(warnings.length, 1);
  assertEquals(
    warnings[0].startsWith("::warning::pipeline heartbeat failed for archive_process"),
    true,
  );
});
