export const SUPABASE_QUERY_TIMEOUT_MS = 4_000;

export function createTimedFetch(timeoutMs: number) {
  return function timedFetch(
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> {
    const timeoutSignal = AbortSignal.timeout(timeoutMs);
    const signal = init?.signal
      ? AbortSignal.any([init.signal, timeoutSignal])
      : timeoutSignal;
    return fetch(input, { ...init, signal });
  };
}

export const timedFetch = createTimedFetch(SUPABASE_QUERY_TIMEOUT_MS);
