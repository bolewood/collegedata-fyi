const WINDOW_MS = 60_000;
const MAX_TOOL_CALLS = 60;

type Bucket = { resetAt: number; count: number };

const buckets = new Map<string, Bucket>();

export function clientIp(headers: Headers): string {
  const forwarded = headers.get("x-forwarded-for") ?? headers.get("x-vercel-forwarded-for");
  if (forwarded) {
    const first = forwarded.split(",")[0]?.trim();
    if (first) return first;
  }
  return headers.get("x-real-ip")?.trim() || "unknown";
}

export function rateLimitToolCall(ip: string): { ok: true } | { ok: false; retryAfterSec: number } {
  const now = Date.now();
  let bucket = buckets.get(ip);
  if (!bucket || now >= bucket.resetAt) {
    bucket = { resetAt: now + WINDOW_MS, count: 0 };
    buckets.set(ip, bucket);
  }
  bucket.count += 1;
  if (bucket.count > MAX_TOOL_CALLS) {
    return {
      ok: false,
      retryAfterSec: Math.max(1, Math.ceil((bucket.resetAt - now) / 1000)),
    };
  }
  return { ok: true };
}

export function resetRateLimitForTests(): void {
  buckets.clear();
}
