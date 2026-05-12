import type { Metadata } from "next";
import Link from "next/link";
import { WaitlistOddsExplorer } from "@/components/WaitlistOddsExplorer";
import { WAITLIST_ANALYSIS_SUMMARY } from "@/lib/waitlist-recipe-analysis";

const WSJ_URL =
  "https://www.wsj.com/us-news/education/college-waitlists-national-decision-day-4cb7b5d8";

export const metadata: Metadata = {
  title: "Wait-list odds",
  description:
    "A CDS-based recipe for measuring college wait-list outcomes by selectivity, control, size, and Carnegie class.",
  alternates: { canonical: "/recipes/waitlist-odds" },
  openGraph: { url: "/recipes/waitlist-odds" },
};

export default function WaitlistOddsPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
      <header
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto",
          alignItems: "end",
          gap: 24,
          paddingTop: 16,
          paddingBottom: 8,
        }}
        className="waitlist-recipe-header"
      >
        <div>
          <div
            className="mono"
            style={{
              color: "var(--ink-3)",
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            <Link href="/recipes" style={{ color: "var(--ink-3)", textDecoration: "none" }}>
              RECIPES
            </Link>{" "}
            / <span style={{ color: "var(--ink)" }}>WAIT-LIST ODDS</span>
          </div>
          <h1
            className="serif"
            style={{
              fontSize: "clamp(36px, 5.5vw, 52px)",
              fontWeight: 400,
              letterSpacing: "-0.02em",
              lineHeight: 1,
              margin: "12px 0 0",
            }}
          >
            Should you get your hopes up about a{" "}
            <span style={{ fontStyle: "italic" }}>wait list</span>?
          </h1>
          <p
            style={{
              color: "var(--ink-2)",
              fontSize: 16,
              lineHeight: 1.55,
              marginTop: 14,
              maxWidth: 720,
            }}
          >
            Inspired by Roshan Fernandez&apos;s{" "}
            <a href={WSJ_URL} target="_blank" rel="noopener noreferrer">
              May 10, 2026 Wall Street Journal story
            </a>{" "}
            on ballooning college wait lists, this recipe ignores anecdotes and
            looks across every complete C2 wait-list row currently visible in
            the collegedata.fyi CDS corpus, with high-volume near-total admit
            rows treated as data-quality caveats.
          </p>
        </div>
        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            justifyContent: "flex-end",
          }}
        >
          <span className="cd-chip">CDS C2</span>
          <span className="cd-chip">C1</span>
          <span className="cd-chip">Scorecard</span>
        </div>
      </header>

      <section
        className="rule-2 waitlist-intro-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "1.15fr 0.85fr",
          gap: 32,
          marginTop: 28,
          paddingTop: 22,
        }}
      >
        <div>
          <div className="meta">§ Reading the odds</div>
          <p style={{ color: "var(--ink-2)", fontSize: 16, lineHeight: 1.65, marginTop: 10 }}>
            The CDS asks schools how many applicants were offered a wait-list
            spot, how many accepted it, and how many were eventually admitted.
            This page uses the success rate that matters to an applicant:{" "}
            <span className="serif" style={{ fontStyle: "italic" }}>
              admitted divided by accepted wait-list spots
            </span>
            . Rows without all three counts are visible as partial data but are
            excluded from rate medians.
          </p>
        </div>
        <div className="cd-card cd-card--cut" style={{ padding: 18 }}>
          <div className="meta">Corpus scope</div>
          <div
            className="serif nums"
            style={{ fontSize: 40, lineHeight: 1, marginTop: 8 }}
          >
            {WAITLIST_ANALYSIS_SUMMARY.latestCompleteSchools}
          </div>
          <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "8px 0 0" }}>
            schools in the rate analysis, across{" "}
            {WAITLIST_ANALYSIS_SUMMARY.analysisRows} school-year rows. Another{" "}
            {WAITLIST_ANALYSIS_SUMMARY.partialRows} rows report only part of C2,
            and {WAITLIST_ANALYSIS_SUMMARY.reportedAnomalyRows} high-volume
            near-total admit rows are shown as caveats.
          </p>
        </div>
      </section>

      <WaitlistOddsExplorer />

      <section style={{ marginTop: 48 }}>
        <div className="meta" style={{ marginBottom: 10 }}>
          § Pull the fields yourself
        </div>
        <pre
          style={{
            background: "var(--ink)",
            borderRadius: 2,
            color: "var(--paper)",
            fontFamily: "var(--mono)",
            fontSize: 13,
            lineHeight: 1.55,
            margin: 0,
            overflowX: "auto",
            padding: "20px 24px",
          }}
        >
{`curl 'https://api.collegedata.fyi/rest/v1/school_browser_rows?select=school_id,school_name,canonical_year,acceptance_rate,wait_list_policy,wait_list_offered,wait_list_accepted,wait_list_admitted&wait_list_offered=not.is.null'`}
        </pre>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13, marginTop: 14 }}>
          <a
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/waitlist-odds.md"
            target="_blank"
            rel="noopener noreferrer"
          >
            Read the methodology →
          </a>
          <a href={WSJ_URL} target="_blank" rel="noopener noreferrer">
            WSJ inspiration →
          </a>
        </div>
      </section>
    </div>
  );
}
