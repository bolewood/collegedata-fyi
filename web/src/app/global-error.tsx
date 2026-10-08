"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";
import "./globals.css";

export default function GlobalError({
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
    <html lang="en">
      <body className="cd-theme min-h-full">
        <div className="mx-auto max-w-5xl px-4 py-24 text-center">
          <h1 className="text-2xl font-bold">Something went wrong</h1>
          <p className="mt-4">
            Unable to load the page. This is usually temporary.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-8 rounded-lg bg-[var(--forest)] px-5 py-2.5 text-sm font-medium text-[var(--paper)]"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
