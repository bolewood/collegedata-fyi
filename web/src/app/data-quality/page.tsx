import type { Metadata } from "next";
import { Suspense } from "react";
import "./data-quality.css";
import { ArchiveStatusHeader } from "@/components/ArchiveStatusHeader";
import { DataQualityView } from "@/components/DataQualityView";
import { yearsNewestFirst, formatSnapshotDate, formatSnapshotTime, isDataQualityLaunched, qualityLede, snapshotDay, type QualitySnapshot } from "@/lib/data-quality";
import { pendingYearScript } from "@/lib/data-quality-pending";
import { buildTrend } from "@/lib/data-quality-trend";
import { loadAllSnapshots, loadReportsFor } from "@/lib/data-quality-snapshots";

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
  // The loader throws when no snapshot is committed, so there is always one here.
  const snapshots = loadAllSnapshots();
  const snapshot: QualitySnapshot = snapshots[snapshots.length - 1];
  const trend = buildTrend(snapshots);
  const lede = qualityLede(snapshot);
  // The reports behind each count (written with the snapshot). Loaded here so the build checks them against the snapshot
  // even before launch; the page only links to them once launched, and the client fetches the file on the first click.
  const reports = loadReportsFor(snapshot);
  const reportsUrl = reports && isDataQualityLaunched() ? `/data-quality/reports/${snapshotDay(snapshot)}` : null;

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
        <p id="dq-source" style={{ marginTop: 12, fontSize: 13, lineHeight: 1.5, color: "var(--ink-3)", maxWidth: 720 }}>
          Numbers from the archive’s scoreboard run of {formatSnapshotDate(snapshot.snapshot_of)}, {formatSnapshotTime(snapshot.snapshot_of)} (file{" "}
          {snapshot.scoreboard_run}).
        </p>
      </header>

      {/* A direct ?year= link shows the default year until the browser hydrates (the HTML is static). Say so: an inline
          script, which runs before hydration, sets an attribute; CSS then dims the body and shows the matching "Loading"
          line below, and YearStatus clears the attribute once hydrated. */}
      <style>
        {yearsNewestFirst(snapshot)
          .slice(1)
          .map((y) => `html[data-dq-pending="${y.cds_year}"] .dq-pending[data-year="${y.cds_year}"]{display:block}`)
          .join("")}
      </style>
      {yearsNewestFirst(snapshot).slice(1).map((y) => (
        <p key={y.cds_year} role="status" className="dq-pending" data-year={y.cds_year}>
          Loading {y.cds_year}…
        </p>
      ))}
      <div id="dq-body">
        {/* useSearchParams (the year picker) needs a Suspense boundary to keep the page static. */}
        <Suspense fallback={<div className="mono" style={{ padding: "32px 0", color: "var(--ink-3)" }}>LOADING…</div>}>
          <DataQualityView snapshot={snapshot} reportsUrl={reportsUrl} trend={trend} />
        </Suspense>
      </div>
      <script dangerouslySetInnerHTML={{ __html: pendingYearScript(yearsNewestFirst(snapshot).slice(1).map((y) => y.cds_year)) }} />
    </div>
  );
}
