import type { Metadata } from "next";
import { DiscoverFlow } from "@/components/discover/DiscoverFlow";

export const metadata: Metadata = {
  title: "Discover Schools",
  description:
    "Learn what you value before you search: sort real campus experiences, set your own boundaries, and build a preference profile grounded in source-backed data.",
  alternates: { canonical: "/discover" },
  // Soft launch: the discovery rounds engine ships in a later slice, so the
  // funnel is intentionally unindexed until the experience is complete.
  robots: { index: false, follow: false },
};

export default function DiscoverPage() {
  return (
    <div id="discover-flow" className="mx-auto max-w-3xl px-4 sm:px-6 py-8">
      <DiscoverFlow />
    </div>
  );
}
