export const MAX_ATTEMPTS = 3;

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
