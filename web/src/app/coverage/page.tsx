import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { fetchCoverageRows } from "@/lib/queries";
import { CoverageDashboard } from "@/components/CoverageDashboard";

export const revalidate = 900; // ISR: 15 minutes, matches the refresh-coverage cron

export const metadata: Metadata = {
  title: "Coverage — collegedata.fyi",
  description:
    "Per-institution Common Data Set coverage status across every active, undergraduate-serving Title-IV institution. Filter by state, enrollment, and the resolver's last attempt to see which schools we have, which we have an older year for, and which haven't yet published one we could find.",
  alternates: { canonical: "/coverage" },
};

export default async function CoveragePage() {
  const rows = await fetchCoverageRows();

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
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
          What we have, <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>and what we don&rsquo;t.</span>
        </h1>
        <p
          style={{
            marginTop: 18,
            fontSize: 16,
            lineHeight: 1.55,
            color: "var(--ink-2)",
            maxWidth: 720,
          }}
        >
          Every active, undergraduate-serving Title-IV institution in the
          United States, with our latest verdict on whether we have a public
          Common Data Set archived. The Common Data Set is voluntary; some
          schools publish openly, some bury it, and some don&rsquo;t publish
          at all. This page is an honest accounting of which is which.
        </p>
      </header>

      {/* Suspense boundary required because CoverageDashboard reads
          search params via useSearchParams; without it, Next.js bails
          out of static generation for /coverage. */}
      <Suspense fallback={<div className="mono" style={{ padding: "32px 0", color: "var(--ink-3)" }}>LOADING COVERAGE DATA…</div>}>
        <CoverageDashboard rows={rows} />
      </Suspense>

      <section style={{ marginTop: 64 }}>
        <h2
          className="serif"
          style={{ fontSize: 22, lineHeight: 1.2, margin: "0 0 16px" }}
        >
          Methodology
        </h2>
        <ul
          style={{
            margin: 0,
            paddingLeft: 22,
            fontSize: 14,
            lineHeight: 1.7,
            color: "var(--ink-2)",
            maxWidth: 720,
          }}
        >
          <li>
            <strong>The CDS is voluntary.</strong> No school is required to
            publish one, and there&rsquo;s no central registry. We have to
            find each one ourselves.
          </li>
          <li>
            <strong>Our discovery is automated.</strong> A resolver fetches
            each school&rsquo;s website and looks for CDS-shaped links. It
            misses sources buried behind logins, JavaScript-only pages, or
            non-obvious filenames. <em>No public CDS found</em> means the
            resolver tried and didn&rsquo;t see one — not that the school
            doesn&rsquo;t publish one.
          </li>
          <li>
            <strong>Not checked yet</strong> means we know the school exists
            and is in scope, but our resolver hasn&rsquo;t scanned it. Coverage
            refreshes every 15 minutes from{" "}
            <a href="https://collegescorecard.ed.gov/" target="_blank" rel="noopener noreferrer">
              College Scorecard
            </a>
            ; the directory expands faster than discovery does.
          </li>
          <li>
            <strong>Federal data is older than CDS.</strong> Scorecard uses
            two-year-old cohorts; the most recent CDS is the current academic
            year. They answer different questions and shouldn&rsquo;t be
            compared directly.
          </li>
          <li>
            <strong>Know where one of these is published?</strong> Click into
            the school page and{" "}
            <Link href="/about">send us the link</Link>. We&rsquo;ll archive
            it. This page is how we make the gaps visible — not a final word.
          </li>
        </ul>
      </section>
    </div>
  );
}
