import { assertEquals, assertNotEquals } from "jsr:@std/assert";

import {
  archiveCooldownDaysForOutcome,
  archiveEnqueueRunId,
  archiveEnqueueRunKey,
} from "./schedule.ts";

Deno.test("archiveEnqueueRunKey uses daily attempt buckets year-round", () => {
  assertEquals(
    archiveEnqueueRunKey(new Date("2026-05-08T02:00:00Z")),
    "archive-enqueue:2026-05-08",
  );
  assertEquals(
    archiveEnqueueRunKey(new Date("2026-05-08T23:59:59Z")),
    "archive-enqueue:2026-05-08",
  );
  assertEquals(
    archiveEnqueueRunKey(new Date("2026-05-09T00:00:00Z")),
    "archive-enqueue:2026-05-09",
  );
});

Deno.test("archiveCooldownDaysForOutcome checks unchanged schools weekly year-round", () => {
  assertEquals(
    archiveCooldownDaysForOutcome(
      "unchanged_verified",
      new Date("2026-01-08T02:00:00Z"),
    ),
    7,
  );
  assertEquals(
    archiveCooldownDaysForOutcome(
      "unchanged_verified",
      new Date("2026-10-08T02:00:00Z"),
    ),
    7,
  );
});

Deno.test("archiveCooldownDaysForOutcome preserves outcome-specific backoff", () => {
  assertEquals(
    archiveCooldownDaysForOutcome(
      "auth_walled_microsoft",
      new Date("2026-05-08T02:00:00Z"),
    ),
    90,
  );
  assertEquals(
    archiveCooldownDaysForOutcome(
      "transient",
      new Date("2026-05-08T02:00:00Z"),
    ),
    0,
  );
});

Deno.test("archiveEnqueueRunId remains deterministic and changes across daily attempt buckets", async () => {
  const first = await archiveEnqueueRunId(new Date("2026-05-08T02:00:00Z"));
  const repeat = await archiveEnqueueRunId(new Date("2026-05-08T23:59:59Z"));
  const nextDay = await archiveEnqueueRunId(new Date("2026-05-09T02:00:00Z"));

  assertEquals(first, repeat);
  assertNotEquals(first, nextDay);
});
