import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs/config";
import retiredSchoolAliases from "./src/data/school-redirects.json";
import { APEX_TO_WWW_REDIRECTS } from "./src/lib/apex-redirect";
import { PIPELINE_OBSERVATION_REDIRECTS } from "./src/lib/pipeline-redirect";
import { buildRetiredSchoolRedirects } from "./src/lib/school-alias";
import {
  SENTRY_ORG,
  SENTRY_PROJECT,
  sentryRelease,
  sentrySourceMapsEnabled,
} from "./src/lib/sentry";

export const nextConfig: NextConfig = {
  trailingSlash: false,
  // PRD 040: the Data quality snapshots are read with node:fs at build and on
  // the coverage page's ISR re-render, so make sure the files ship with them.
  // The snapshots are the top-level files; the reports file (reports/<date>.json,
  // about 320 KB) is read only by the Data quality page and its reports route, so
  // /coverage does not carry it (see the excludes below).
  outputFileTracingIncludes: {
    "/coverage": ["./src/data/data-quality/*.json"],
    "/data-quality": ["./src/data/data-quality/**/*.json"],
    "/data-quality/reports/[date]": ["./src/data/data-quality/**/*.json"],
  },
  // Next traces the whole data-quality directory for any route that reads it, so /coverage would still carry the reports
  // file; leave it out there (the include above is not enough on its own, measured with `npm run build`).
  outputFileTracingExcludes: {
    "/coverage": ["./src/data/data-quality/reports/**"],
  },
  async redirects() {
    return [
      ...APEX_TO_WWW_REDIRECTS,
      ...PIPELINE_OBSERVATION_REDIRECTS,
      ...buildRetiredSchoolRedirects(retiredSchoolAliases),
    ];
  },
  // Rewrite the pretty URL `/design-system` and `/design-system/` to the
  // static file under `public/design-system/index.html`. Next's default
  // static handler only serves the full path; rewrites give us the
  // conventional directory URL without adding a React route.
  async rewrites() {
    return [
      { source: "/design-system", destination: "/design-system/index.html" },
      { source: "/design-system/", destination: "/design-system/index.html" },
    ];
  },
  async headers() {
    return [
      {
        // Versioned discovery artifacts (evidence-v1.json, …): the filename
        // IS the version, so the content behind a given path never changes —
        // cache immutably instead of revalidating a ~460KB payload per visit.
        source: "/discovery/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        // Operator clocks. ISR + SWR served the build-time seed as STALE.
        source: "/pipeline-observation",
        headers: [
          {
            key: "Cache-Control",
            value: "private, no-store, no-cache, max-age=0, must-revalidate",
          },
        ],
      },
      {
        source: "/pipeline-observation.json",
        headers: [
          {
            key: "Cache-Control",
            value: "private, no-store, no-cache, max-age=0, must-revalidate",
          },
        ],
      },
    ];
  },
};

const sentryAuthToken = process.env.SENTRY_AUTH_TOKEN;
const uploadSourceMaps = sentrySourceMapsEnabled(sentryAuthToken);

export default withSentryConfig(nextConfig, {
  org: SENTRY_ORG,
  project: SENTRY_PROJECT,
  authToken: sentryAuthToken,
  silent: !process.env.CI,
  widenClientFileUpload: uploadSourceMaps,
  sourcemaps: {
    disable: !uploadSourceMaps,
  },
  release: {
    name: sentryRelease(),
    create: uploadSourceMaps,
    finalize: uploadSourceMaps,
  },
  tunnelRoute: "/sentry-tunnel",
  errorHandler(error) {
    console.warn("[sentry] build step skipped:", error.message);
  },
});
