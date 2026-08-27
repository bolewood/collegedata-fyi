import type { Metadata } from "next";
import Link from "next/link";
import { WaitlistOddsExplorer } from "@/components/WaitlistOddsExplorer";
import { TrackedLink } from "@/components/TrackedLink";
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
            Offered, accepted,{" "}
            <span style={{ fontStyle: "italic" }}>admitted.</span>
          </h1>
          <p
            className="serif"
            style={{
              color: "var(--ink-2)",
              fontSize: 18,
              fontStyle: "italic",
              lineHeight: 1.55,
              marginTop: 14,
              maxWidth: 720,
            }}
          >
            Offer, accept, and admit counts from CDS C2, across every complete
            row in the corpus, bucketed by C1 selectivity and by federal
            control, size, and Carnegie class. High-volume near-total admit
            rows are flagged as data-quality caveats, not dropped silently.
            Inspired by Roshan Fernandez&apos;s{" "}
            <TrackedLink
              external
              href={WSJ_URL}
              target="_blank"
              rel="noopener noreferrer"
              analyticsEvent="recipe_inspiration_opened"
              analyticsProperties={{
                surface: "recipe_hero",
                recipe: "waitlist-odds",
                source: "wsj",
              }}
            >
              May 2026 WSJ story
            </TrackedLink>; the numbers here are from the filings, not the article.
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
            The rate here is{" "}
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
          <TrackedLink
            external
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/waitlist-odds.md"
            target="_blank"
            rel="noopener noreferrer"
            analyticsEvent="recipe_writeup_opened"
            analyticsProperties={{
              surface: "recipe_detail",
              recipe: "waitlist-odds",
            }}
          >
            Read the methodology →
          </TrackedLink>
          <TrackedLink
            external
            href={WSJ_URL}
            target="_blank"
            rel="noopener noreferrer"
            analyticsEvent="recipe_inspiration_opened"
            analyticsProperties={{
              surface: "recipe_detail",
              recipe: "waitlist-odds",
              source: "wsj",
            }}
          >
            WSJ inspiration →
          </TrackedLink>
        </div>
      </section>
    </div>
  );
}
