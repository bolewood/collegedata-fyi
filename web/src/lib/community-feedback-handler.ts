import { createHash, createHmac } from "node:crypto";
import { isIP } from "node:net";
import { validateFeedback, type FeedbackRequest } from "./community-feedback";
export type Admission = {
  status: "created" | "duplicate" | "conflict" | "limited";
  receipt?: string;
  retry_after?: number;
};
export type FeedbackDependencies = {
  enabled: boolean;
  origins: string[];
  secret?: string;
  /** Only Vercel's overwritten x-vercel-forwarded-for in production. */
  clientIp: (request: Request) => string | null;
  save: (args: {
    requestId: string;
    digest: string;
    payload: Omit<FeedbackRequest, "requestId">;
    bucket: string;
    previousBucket: string;
  }) => Promise<Admission>;
  now?: () => Date;
};
function response(
  status: number,
  body: unknown,
  extra: Record<string, string> = {},
) {
  return Response.json(body, {
    status,
    headers: { "Cache-Control": "no-store", ...extra },
  });
}
async function readJson(request: Request) {
  const reader = request.body?.getReader();
  if (!reader) throw new Error("invalid");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 65536) {
        try {
          await reader.cancel();
        } catch {
          /* Size rejection does not depend on stream cleanup. */
        }
        throw new Error("size");
      }
      chunks.push(value);
    }
    const buffer = Buffer.concat(chunks);
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(buffer));
  } finally {
    reader.releaseLock();
  }
}
export async function handleFeedback(
  request: Request,
  deps: FeedbackDependencies,
): Promise<Response> {
  const origin = request.headers.get("Origin");
  if (!origin || !deps.origins.includes(origin))
    return response(403, { error: "origin" });
  if (!deps.enabled || !deps.secret || deps.secret.length < 32)
    return response(503, { error: "unavailable" });
  if (
    request.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase() !==
    "application/json"
  )
    return response(415, { error: "media_type" });
  if (Number(request.headers.get("Content-Length")) > 65536)
    return response(413, { error: "size" });
  let input: unknown;
  try {
    input = await readJson(request);
  } catch (error) {
    return response(
      error instanceof Error && error.message === "size" ? 413 : 400,
      {
        error:
          error instanceof Error && error.message === "size"
            ? "size"
            : "invalid",
      },
    );
  }
  const parsed = validateFeedback(input);
  if (!parsed.value)
    return response(400, { error: "invalid", fields: parsed.errors });
  const ip = deps.clientIp(request);
  if (!ip || !isIP(ip)) return response(503, { error: "unavailable" });
  const now = deps.now?.() ?? new Date();
  const bucketFor = (date: Date) =>
    createHmac("sha256", deps.secret!)
      .update(`${date.toISOString().slice(0, 10)}\n${ip}`)
      .digest("hex");
  const { requestId, ...payload } = parsed.value;
  try {
    const result = await deps.save({
      requestId,
      payload,
      digest: createHash("sha256")
        .update(JSON.stringify(payload))
        .digest("hex"),
      bucket: bucketFor(now),
      previousBucket: bucketFor(new Date(now.getTime() - 86400000)),
    });
    if (result.status === "conflict")
      return response(409, { error: "conflict" });
    if (result.status === "limited")
      return response(
        429,
        { error: "limited", retryAfter: result.retry_after },
        { "Retry-After": String(result.retry_after ?? 600) },
      );
    if (!["created", "duplicate"].includes(result.status) || !result.receipt)
      return response(503, { error: "unavailable" });
    return response(result.status === "created" ? 201 : 200, {
      receipt: result.receipt,
    });
  } catch {
    return response(503, { error: "unavailable" });
  } // Never log provider errors: they may contain submitted values.
}
