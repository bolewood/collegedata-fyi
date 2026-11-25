import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { fetchCoverageRows, fetchBrandColorIndex } from "@/lib/queries";
import { ShareButton } from "@/components/ShareButton";
import { CoverageDashboard } from "@/components/CoverageDashboard";
import { ArchiveStatusHeader } from "@/components/ArchiveStatusHeader";
import { loadLatestSnapshot } from "@/lib/data-quality-snapshots";

// ISR: the page re-reads every 15 minutes, but the coverage table itself is
// rebuilt hourly (refresh-coverage cron at minute 17). The copy below says hourly.
export const revalidate = 900;

export const metadata: Metadata = {
  title: "Coverage",
  description:
    "See which U.S. colleges have a current Common Data Set on file, which have older years, and which have federal data only. Filter by state and size.",
  alternates: { canonical: "/coverage" },
};

export default async function CoveragePage() {
  const [rows, brandIndex] = await Promise.all([
    fetchCoverageRows(),
    fetchBrandColorIndex(),
  ]);
  // PRD 040 amendment: current-year renewal comes from the committed Data
  // quality snapshot, not the live rows (they carry only the latest year with
  // numbers). Null before the first snapshot is committed; throws once the
  // Data quality gate is open and no snapshot exists.
  const snapshot = loadLatestSnapshot();
  const renewal = snapshot ? { renewal: snapshot.renewal, snapshotOf: snapshot.snapshot_of } : null;
  const coloredRows = rows.map((row) => ({
    ...row,
    brand_colors: brandIndex[row.school_id] ?? null,
  }));

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <ArchiveStatusHeader active="coverage" />
      <header style={{ paddingTop: 32, paddingBottom: 24 }}>
        <div className="meta" style={{ marginBottom: 12 }}>
          § Coverage
        </div>
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
          Archive coverage
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
          Every U.S. college that participates in federal student aid, and
          whether we have a public Common Data Set on file. Publishing is
          voluntary: some schools post their report openly, some tuck it away,
          and many never publish one at all.
        </p>
        <div style={{ marginTop: 18 }}>
          {/* No path: shares the address bar as it is, filter params included. */}
          <ShareButton surface="coverage" align="start" title="CollegeData.fyi CDS coverage view" />
        </div>
      </header>

      {/* Suspense boundary required because CoverageDashboard reads
          search params via useSearchParams; without it, Next.js bails
          out of static generation for /coverage. */}
      <Suspense fallback={<div className="mono" style={{ padding: "32px 0", color: "var(--ink-3)" }}>LOADING COVERAGE DATA…</div>}>
        <CoverageDashboard rows={coloredRows} renewal={renewal} />
      </Suspense>

      <section style={{ marginTop: 64, maxWidth: 760 }}>
        <h2
          className="serif"
          style={{ fontSize: 22, lineHeight: 1.2, margin: "0 0 16px" }}
        >
          Methodology
        </h2>
        <div
          style={{
            fontSize: 14,
            lineHeight: 1.65,
            color: "var(--ink-2)",
            display: "grid",
            gap: 14,
          }}
        >
          <p style={{ margin: 0 }}>
            We start with active U.S. colleges that serve undergraduates and
            accept federal student aid, then look for public Common Data Set
            files on school-controlled sites and known public archives. The
            table shows our current best status for each school, plus the last
            time we checked.
          </p>
          <p style={{ margin: 0 }}>
            A school marked <em>No public CDS found</em> was checked without a
            usable public source turning up. That is different from saying the
            school never publishes one: CDS files are voluntary, and some are
            posted in places automated discovery cannot reliably reach.{" "}
            <em>Not checked yet</em> means we haven’t checked this
            school yet.
          </p>
          <p style={{ margin: 0 }}>
            Coverage refreshes hourly from{" "}
            <a href="https://collegescorecard.ed.gov/" target="_blank" rel="noopener noreferrer">
              College Scorecard
            </a>. CDS files are often newer than federal outcome datasets.
            Federal numbers stay labeled as federal.
          </p>
          <p style={{ margin: 0 }}>
            Know where a missing report is posted? Open the school’s page
            and <Link href="/feedback">send us the link</Link> so we can archive
            it and update this table.
          </p>
        </div>
      </section>
    </div>
  );
}
