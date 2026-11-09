"use client";
import { Analytics } from "@vercel/analytics/next";
import { communityAnalyticsUrl } from "@/lib/community-privacy";
export function PrivateAnalytics() {
  return (
    <Analytics
      beforeSend={(event) => ({
        ...event,
        url: communityAnalyticsUrl(event.url),
      })}
    />
  );
}
