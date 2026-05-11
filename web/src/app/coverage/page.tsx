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
            We start with active Title-IV institutions that serve
            undergraduates, then look for public Common Data Set files on
            school-controlled sites and known public archives. The table shows
            our current best status for each school, plus the last time we
            checked.
          </p>
          <p style={{ margin: 0 }}>
            A school marked <em>No public CDS found</em> was checked without a
            usable public source turning up. That is different from saying the
            school never publishes one: CDS files are voluntary, and some are
            posted in places automated discovery cannot reliably reach.
            <em> Not checked yet</em> means the school is in scope, but the
            resolver has not scanned it.
          </p>
          <p style={{ margin: 0 }}>
            Coverage refreshes every 15 minutes from{" "}
            <a href="https://collegescorecard.ed.gov/" target="_blank" rel="noopener noreferrer">
              College Scorecard
            </a>. CDS files are often newer than federal outcome datasets, while
            NCES/IPEDS and Scorecard provide broader baseline context. We keep
            those sources labeled separately so readers can tell what came from
            a school publication and what came from federal data.
          </p>
          <p style={{ margin: 0 }}>
            Know where one of these is published? Open the school page and{" "}
            <Link href="/about">send us the link</Link>. We&rsquo;ll archive
            the source and update the coverage status.
          </p>
        </div>
      </section>
    </div>
  );
}
