import "server-only";
import type { Database } from "./database.types";
import { createClient } from "@supabase/supabase-js";
import { handleFeedback, type Admission } from "./community-feedback-handler";
export function feedbackWritesEnabled() {
  return (
    process.env.COMMUNITY_FEEDBACK_ENABLED === "true" &&
    (process.env.VERCEL_ENV === "production" ||
      (process.env.NODE_ENV !== "production" &&
        process.env.COMMUNITY_ALLOW_LOCAL_WRITES === "true"))
  );
}
export async function submitFeedback(request: Request) {
  return handleFeedback(request, {
    enabled: feedbackWritesEnabled(),
    origins: (process.env.COMMUNITY_FEEDBACK_ORIGINS ?? "")
      .split(",")
      .filter(Boolean),
    secret: process.env.COMMUNITY_RATE_LIMIT_SECRET,
    clientIp: (req) =>
      process.env.VERCEL === "1"
        ? req.headers.get("x-vercel-forwarded-for")
        : process.env.NODE_ENV !== "production" &&
            process.env.COMMUNITY_ALLOW_LOCAL_WRITES === "true"
          ? "127.0.0.1"
          : null,
    save: async (args) => {
      const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
      if (!url || !key) throw new Error("unavailable");
      const client = createClient<Database>(url, key, {
        auth: { persistSession: false, autoRefreshToken: false },
      });
      const { data, error } = await client
        .rpc("community_submit", {
          p_request_id: args.requestId,
          p_digest: args.digest,
          p_payload: args.payload,
          p_bucket: args.bucket,
          p_previous_bucket: args.previousBucket,
        })
        .abortSignal(AbortSignal.timeout(8000));
      if (error || !data) throw new Error("unavailable");
      return data as unknown as Admission;
    },
  });
}
