"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-24 text-center">
      <h1 className="text-3xl">Something went wrong</h1>
      <p className="mt-4 text-[var(--ink-2)]">
        Unable to load data. This is usually temporary.
      </p>
      <button type="button" onClick={reset} className="cd-btn mt-8">
        Try again
      </button>
    </div>
  );
}
