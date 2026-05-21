"use client";

import { useState } from "react";
import { type AnalyticsProperties, trackEvent } from "@/lib/analytics";

export function CopyButton({
  text,
  label = "Copy",
  analyticsEvent = "copy_clicked",
  analyticsProperties,
}: {
  text: string;
  label?: string;
  analyticsEvent?: string;
  analyticsProperties?: AnalyticsProperties;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      trackEvent(analyticsEvent, analyticsProperties);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="rounded border border-gray-300 bg-white px-2 py-1 text-[11px] font-medium text-gray-700 hover:bg-gray-100"
    >
      {copied ? "Copied" : label}
    </button>
  );
}
