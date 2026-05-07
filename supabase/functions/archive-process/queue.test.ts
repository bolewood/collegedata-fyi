import {
  buildAttemptBudgetExhaustedUpdate,
  hasExceededAttemptBudget,
  isEmptyClaimResult,
  MAX_ATTEMPTS,
} from "./queue.ts";

Deno.test("isEmptyClaimResult treats null-like composite rows as queue drained", () => {
  if (!isEmptyClaimResult(null)) {
    throw new Error("null should be empty");
  }
  if (!isEmptyClaimResult({ id: null, school_id: null, claimed_at: null })) {
    throw new Error("all-null composite should be empty");
  }
  if (!isEmptyClaimResult([{ id: null, school_id: null, claimed_at: null }])) {
    throw new Error("all-null composite array should be empty");
  }
});

Deno.test("isEmptyClaimResult keeps real claimed rows", () => {
  if (isEmptyClaimResult({
    id: "row-1",
    school_id: "example-school",
    claimed_at: "2026-05-07T00:00:00Z",
  })) {
    throw new Error("real row should not be empty");
  }
});

Deno.test("hasExceededAttemptBudget only short-circuits rows past the retry budget", () => {
  if (hasExceededAttemptBudget({ attempts: MAX_ATTEMPTS })) {
    throw new Error("final allowed attempt should still run");
  }
  if (!hasExceededAttemptBudget({ attempts: MAX_ATTEMPTS + 1 })) {
    throw new Error("attempts past budget should short-circuit");
  }
});

Deno.test("buildAttemptBudgetExhaustedUpdate marks poison rows terminal", () => {
  const update = buildAttemptBudgetExhaustedUpdate(
    { attempts: 2701 },
    "2026-05-07T18:00:00Z",
  );

  if (update.status !== "failed_permanent") {
    throw new Error(`unexpected status ${update.status}`);
  }
  if (update.last_outcome !== "transient") {
    throw new Error(`unexpected last_outcome ${update.last_outcome}`);
  }
  if (update.processed_at !== "2026-05-07T18:00:00Z") {
    throw new Error(`unexpected processed_at ${update.processed_at}`);
  }
  if (!String(update.last_error).includes("reclaimed 2701 times")) {
    throw new Error(`unexpected last_error ${update.last_error}`);
  }
});
