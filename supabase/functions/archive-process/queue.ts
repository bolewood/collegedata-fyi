export const MAX_ATTEMPTS = 3;

export type ArchiveQueueTerminalStatus = "ready" | "done" | "failed_permanent";

export interface ArchiveAttemptCompletionResult {
  completed: boolean;
  error: string | null;
}

export interface ArchiveQueueRow {
  id: string;
  enqueued_run_id: string;
  school_id: string;
  school_name: string;
  cds_url_hint: string;
  status: string;
  attempts: number;
  last_error: string | null;
  enqueued_at: string;
  claimed_at: string | null;
  processed_at: string | null;
}

export function isEmptyClaimResult(claimed: unknown): boolean {
  if (claimed == null) return true;

  if (Array.isArray(claimed)) {
    return claimed.length === 0 || isEmptyClaimResult(claimed[0]);
  }

  if (typeof claimed !== "object") return false;

  const row = claimed as Partial<ArchiveQueueRow>;
  return row.id == null && row.school_id == null && row.claimed_at == null;
}

export function hasExceededAttemptBudget(
  row: Pick<ArchiveQueueRow, "attempts">,
  maxAttempts = MAX_ATTEMPTS,
): boolean {
  return (row.attempts ?? 0) > maxAttempts;
}

export function buildAttemptBudgetExhaustedUpdate(
  row: Pick<ArchiveQueueRow, "attempts">,
  processedAt: string,
  maxAttempts = MAX_ATTEMPTS,
): Record<string, unknown> {
  const attempts = row.attempts ?? 0;
  return {
    status: "failed_permanent",
    processed_at: processedAt,
    last_outcome: "transient",
    last_error:
      `exhausted ${maxAttempts} attempts before processing ` +
      `(row was reclaimed ${attempts} times without a terminal update, likely prior edge-function timeout)`,
  };
}

export function buildAttemptCompletionParams(
  row: Pick<ArchiveQueueRow, "id" | "attempts" | "claimed_at">,
  status: ArchiveQueueTerminalStatus,
  lastOutcome: string | null,
  lastError: string | null,
  finishedAt: string,
): Record<string, string | number | null> {
  if (!row.claimed_at) {
    throw new Error("cannot complete archive attempt without a claim lease");
  }
  return {
    p_queue_id: row.id,
    p_attempt_number: row.attempts,
    p_claimed_at: row.claimed_at,
    p_status: status,
    p_last_outcome: lastOutcome,
    p_last_error: lastError,
    p_finished_at: finishedAt,
  };
}

export function attemptCompletionFailure(
  result: ArchiveAttemptCompletionResult,
): { status: 500 | 409; error: string } | null {
  if (result.error) {
    return { status: 500, error: `terminal update failed: ${result.error}` };
  }
  if (!result.completed) {
    return { status: 409, error: "claim lease is no longer current" };
  }
  return null;
}
