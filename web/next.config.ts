import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
};

export default nextConfig;
