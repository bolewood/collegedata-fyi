import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

export const onRequestError: typeof Sentry.captureRequestError = (...args) => {
  let path: string;
  try {
    path = decodeURIComponent(args[1].path);
  } catch {
    return;
  }
  if (/^\/(?:api\/)?feedback(?:[/?#]|$)/.test(path)) return;
  return Sentry.captureRequestError(...args);
};
