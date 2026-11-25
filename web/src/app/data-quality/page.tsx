import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { ArchiveStatusHeader } from "@/components/ArchiveStatusHeader";
import { DataQualityView } from "@/components/DataQualityView";
import { isDataQualityLaunched, qualityLede, type QualitySnapshot } from "@/lib/data-quality";
import { loadLatestSnapshot } from "@/lib/data-quality-snapshots";

// The snapshot is committed to the repo and read at build, so the page is
// static. A new snapshot reaches the site with the next deploy.
export const dynamic = "force-static";

export function generateMetadata(): Metadata {
  return {
    title: "Data quality",
    description:
      "How well this archive reads the Common Data Set reports it publishes: how they compare with federal figures, and whether their printed totals add up.",
    alternates: { canonical: "/data-quality" },
    robots: isDataQualityLaunched() ? undefined : { index: false, follow: false },
  };
}

export default function DataQualityPage() {
  const snapshot: QualitySnapshot | null = loadLatestSnapshot();
  // No snapshot before launch means nothing to show. After launch the loader throws instead.
  if (!snapshot) notFound();
  const lede = qualityLede(snapshot);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <ArchiveStatusHeader active="quality" />
      <header style={{ paddingTop: 28, paddingBottom: 8 }}>
        <h1
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 400,
            fontSize: "clamp(36px, 5vw, 56px)",
            lineHeight: 1.05,
            margin: 0,
            letterSpacing: "-0.02em",
          }}
        >
          Data quality
        </h1>
        <p
          className="serif"
          style={{
            marginTop: 18,
            fontSize: 18,
            fontStyle: "italic",
            lineHeight: 1.55,
            color: "var(--ink-2)",
            maxWidth: 720,
          }}
        >
          {lede.populations} {lede.meaning}
        </p>
        <p className="meta" style={{ marginTop: 12 }}>
          Scoreboard run {snapshot.scoreboard_run}
        </p>
      </header>

      {/* useSearchParams (the year picker) needs a Suspense boundary to keep the page static. */}
      <Suspense fallback={<div className="mono" style={{ padding: "32px 0", color: "var(--ink-3)" }}>LOADING…</div>}>
        <DataQualityView snapshot={snapshot} />
      </Suspense>
    </div>
  );
}
