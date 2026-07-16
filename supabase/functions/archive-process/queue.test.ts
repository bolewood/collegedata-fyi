import {
  attemptCompletionFailure,
  buildAttemptCompletionParams,
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

Deno.test("buildAttemptCompletionParams records the exact claim lease", () => {
  const params = buildAttemptCompletionParams(
    {
      id: "queue-row-1",
      attempts: 3,
      claimed_at: "2026-07-15T02:00:00Z",
    },
    "failed_permanent",
    "transient",
    "upstream timed out",
    "2026-07-15T02:06:40Z",
  );

  if (params.p_queue_id !== "queue-row-1") {
    throw new Error(`unexpected queue id ${params.p_queue_id}`);
  }
  if (params.p_attempt_number !== 3) {
    throw new Error(`unexpected attempt ${params.p_attempt_number}`);
  }
  if (params.p_claimed_at !== "2026-07-15T02:00:00Z") {
    throw new Error(`unexpected lease ${params.p_claimed_at}`);
  }
  if (params.p_status !== "failed_permanent") {
    throw new Error(`unexpected status ${params.p_status}`);
  }
  if (params.p_last_outcome !== "transient") {
    throw new Error(`unexpected outcome ${params.p_last_outcome}`);
  }
  if (params.p_last_error !== "upstream timed out") {
    throw new Error(`unexpected error ${params.p_last_error}`);
  }
  if (params.p_finished_at !== "2026-07-15T02:06:40Z") {
    throw new Error(`unexpected finish ${params.p_finished_at}`);
  }
});

Deno.test("buildAttemptCompletionParams rejects a missing claim lease", () => {
  let threw = false;
  try {
    buildAttemptCompletionParams(
      { id: "queue-row-1", attempts: 1, claimed_at: null },
      "done",
      "unchanged_verified",
      null,
      "2026-07-15T02:06:40Z",
    );
  } catch (error) {
    threw = error instanceof Error &&
      error.message === "cannot complete archive attempt without a claim lease";
  }
  if (!threw) throw new Error("expected a missing claim lease to be rejected");
});

Deno.test("attemptCompletionFailure exposes RPC errors", () => {
  const failure = attemptCompletionFailure({
    completed: false,
    error: "database unavailable",
  });
  if (failure?.status !== 500) {
    throw new Error(`unexpected status ${failure?.status}`);
  }
  if (failure.error !== "terminal update failed: database unavailable") {
    throw new Error(`unexpected error ${failure.error}`);
  }
});

Deno.test("attemptCompletionFailure exposes stale leases", () => {
  const failure = attemptCompletionFailure({ completed: false, error: null });
  if (failure?.status !== 409) {
    throw new Error(`unexpected status ${failure?.status}`);
  }
  if (failure.error !== "claim lease is no longer current") {
    throw new Error(`unexpected error ${failure.error}`);
  }
});

Deno.test("attemptCompletionFailure accepts an atomic completion", () => {
  const failure = attemptCompletionFailure({ completed: true, error: null });
  if (failure !== null) throw new Error("successful completion was rejected");
});
