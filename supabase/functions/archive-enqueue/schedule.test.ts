import { assertEquals, assertNotEquals } from "jsr:@std/assert";

import {
  archiveCooldownDaysForOutcome,
  archiveEnqueueRunId,
  archiveEnqueueRunKey,
  parseCooldownDaysOverride,
  parseSchoolIdsOverride,
  restrictSchoolsToIds,
  schoolIdsFilterMeta,
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

Deno.test("archiveCooldownDaysForOutcome checks every successful outcome weekly", () => {
  for (
    const outcome of [
      "inserted",
      "refreshed",
      "unchanged_verified",
      "unchanged_repaired",
    ] as const
  ) {
    assertEquals(
      archiveCooldownDaysForOutcome(
        outcome,
        new Date("2026-01-08T02:00:00Z"),
      ),
      7,
    );
    assertEquals(
      archiveCooldownDaysForOutcome(
        outcome,
        new Date("2026-10-08T02:00:00Z"),
      ),
      7,
    );
  }
});

Deno.test("archiveCooldownDaysForOutcome daily-escalates only demand-tier success past 9 months", () => {
  const now = new Date("2026-08-18T12:00:00Z");
  const tenMonthsAgo = new Date("2025-10-18T12:00:00Z");
  const eightMonthsAgo = new Date("2025-12-18T12:00:00Z");
  assertEquals(
    archiveCooldownDaysForOutcome("unchanged_verified", now, {
      isDemandTier: true,
      freshnessAt: tenMonthsAgo,
    }),
    1,
  );
  assertEquals(
    archiveCooldownDaysForOutcome("unchanged_verified", now, {
      isDemandTier: true,
      freshnessAt: eightMonthsAgo,
    }),
    7,
  );
  assertEquals(
    archiveCooldownDaysForOutcome("unchanged_verified", now, {
      isDemandTier: false,
      freshnessAt: tenMonthsAgo,
    }),
    7,
  );
  assertEquals(
    archiveCooldownDaysForOutcome("auth_walled_microsoft", now, {
      isDemandTier: true,
      freshnessAt: tenMonthsAgo,
    }),
    90,
  );
  assertEquals(
    archiveCooldownDaysForOutcome("dead_url", now, {
      isDemandTier: true,
      freshnessAt: tenMonthsAgo,
    }),
    14,
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

Deno.test("parseCooldownDaysOverride validates and bounds operator input", () => {
  assertEquals(parseCooldownDaysOverride(null), null);
  assertEquals(parseCooldownDaysOverride("0"), 0);
  assertEquals(parseCooldownDaysOverride("180"), 180);
  assertEquals(parseCooldownDaysOverride("3650"), 3650);

  for (const invalid of ["", "abc", "-1", "1.5", "3651"]) {
    let threw = false;
    try {
      parseCooldownDaysOverride(invalid);
    } catch {
      threw = true;
    }
    assertEquals(threw, true, `expected '${invalid}' to be rejected`);
  }
});

Deno.test("parseSchoolIdsOverride splits and rejects empty lists", () => {
  assertEquals(parseSchoolIdsOverride(null), null);
  assertEquals(parseSchoolIdsOverride("ou, uf"), ["ou", "uf"]);
  let threw = false;
  try {
    parseSchoolIdsOverride("  ,  ");
  } catch {
    threw = true;
  }
  assertEquals(threw, true);
});

Deno.test("restrictSchoolsToIds keeps only requested ids", () => {
  const rows = [{ id: "a" }, { id: "b" }, { id: "c" }];
  assertEquals(restrictSchoolsToIds(rows, null), rows);
  assertEquals(restrictSchoolsToIds(rows, ["c", "a"]), [{ id: "a" }, { id: "c" }]);
});

Deno.test("schoolIdsFilterMeta is a positive assertion that the filter ran", () => {
  assertEquals(schoolIdsFilterMeta(null, 2000), {
    school_ids_requested: null,
    school_ids_matched: null,
  });
  assertEquals(schoolIdsFilterMeta(["__canary__"], 0), {
    school_ids_requested: 1,
    school_ids_matched: 0,
  });
  assertEquals(schoolIdsFilterMeta(["a", "b"], 2), {
    school_ids_requested: 2,
    school_ids_matched: 2,
  });
});
