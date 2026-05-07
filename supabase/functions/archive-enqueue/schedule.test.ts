import { assertEquals, assertNotEquals } from "jsr:@std/assert";

import {
  archiveCooldownDaysForOutcome,
  archiveEnqueueRunId,
  archiveEnqueueRunKey,
  isFreshnessSeason,
} from "./schedule.ts";

Deno.test("archiveEnqueueRunKey uses weekly buckets during March-June freshness season", () => {
  assertEquals(
    archiveEnqueueRunKey(new Date("2026-05-08T02:00:00Z")),
    "archive-enqueue:2026-W19",
  );
  assertEquals(
    archiveEnqueueRunKey(new Date("2026-05-11T02:00:00Z")),
    "archive-enqueue:2026-W20",
  );
});

Deno.test("archiveEnqueueRunKey keeps monthly buckets outside freshness season", () => {
  assertEquals(
    archiveEnqueueRunKey(new Date("2026-02-28T02:00:00Z")),
    "archive-enqueue:2026-02",
  );
  assertEquals(
    archiveEnqueueRunKey(new Date("2026-07-01T02:00:00Z")),
    "archive-enqueue:2026-07",
  );
});

Deno.test("isFreshnessSeason includes March through June in UTC", () => {
  assertEquals(isFreshnessSeason(new Date("2026-02-28T23:59:59Z")), false);
  assertEquals(isFreshnessSeason(new Date("2026-03-01T00:00:00Z")), true);
  assertEquals(isFreshnessSeason(new Date("2026-06-30T23:59:59Z")), true);
  assertEquals(isFreshnessSeason(new Date("2026-07-01T00:00:00Z")), false);
});

Deno.test("archiveCooldownDaysForOutcome shortens only unchanged_verified during freshness season", () => {
  assertEquals(
    archiveCooldownDaysForOutcome(
      "unchanged_verified",
      new Date("2026-05-08T02:00:00Z"),
    ),
    7,
  );
  assertEquals(
    archiveCooldownDaysForOutcome(
      "unchanged_verified",
      new Date("2026-10-08T02:00:00Z"),
    ),
    30,
  );
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

Deno.test("archiveEnqueueRunId remains deterministic and changes across weekly freshness buckets", async () => {
  const first = await archiveEnqueueRunId(new Date("2026-05-08T02:00:00Z"));
  const repeat = await archiveEnqueueRunId(new Date("2026-05-10T02:00:00Z"));
  const nextWeek = await archiveEnqueueRunId(new Date("2026-05-11T02:00:00Z"));

  assertEquals(first, repeat);
  assertNotEquals(first, nextWeek);
});
