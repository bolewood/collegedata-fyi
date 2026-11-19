import type { Metadata } from "next";
import { SchoolBrowser } from "@/components/SchoolBrowser";
import { fetchSiteStats, fetchBrandColorIndex } from "@/lib/queries";
import { formatCount, formatShortDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "Compare schools",
  description:
    "Compare admissions, test scores, cost, and financial aid across U.S. colleges using each school’s latest published report, with the original file one click away.",
  alternates: { canonical: "/browse" },
  openGraph: { url: "/browse" },
};

export const revalidate = 3600;

export default async function BrowsePage() {
  const [stats, brandColors] = await Promise.all([
    fetchSiteStats(),
    fetchBrandColorIndex(),
  ]);

  return (
    <div className="mx-auto max-w-7xl" style={{ padding: "52px 24px 72px" }}>
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "160px 1fr",
          gap: 34,
          alignItems: "start",
          marginBottom: 34,
        }}
        className="browser-hero"
      >
        <div className="meta" style={{ paddingTop: 10, lineHeight: 1.8 }}>
          <div>§ Compare</div>
          <div>2024–25+</div>
        </div>
        <div>
          <h1
            style={{
              margin: 0,
              fontFamily: "var(--serif)",
              fontWeight: 400,
              fontSize: "clamp(42px, 6vw, 68px)",
              lineHeight: 1,
              letterSpacing: "-0.02em",
            }}
          >
            Compare schools side by side
          </h1>
          <p
            className="serif"
            style={{
              margin: "20px 0 0",
              maxWidth: 720,
              color: "var(--ink-2)",
              fontSize: 18,
              fontStyle: "italic",
              lineHeight: 1.55,
            }}
          >
            Filter and sort admissions, test scores, cost, and financial aid
            across colleges. Each row reflects the latest comparable report as
            the school published it, with the original file linked right
            alongside the numbers.
          </p>
          <div
            className="browser-hero-stats rule-2"
            style={{
              marginTop: 24,
              paddingTop: 16,
              display: "grid",
              gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
              gap: 18,
            }}
          >
            <BrowserHeroStat
              label="Schools"
              value={formatCount(stats.browser_school_count)}
              note="In this table"
            />
            <BrowserHeroStat
              label="Reports"
              value={formatCount(stats.browser_primary_row_count)}
              note="2024–25 and newer"
            />
            <BrowserHeroStat
              label="Data points"
              value={formatCount(stats.queryable_field_count)}
              note="Reported values across 2024–25+ reports"
            />
            <BrowserHeroStat
              label="Updated"
              value={formatShortDate(stats.browser_updated_at)}
            />
          </div>
        </div>
      </section>

      <SchoolBrowser brandColors={brandColors} />

      <style>{`
        @media (max-width: 760px) {
          .browser-hero {
            grid-template-columns: 1fr !important;
            gap: 14px !important;
          }
          .browser-hero-stats {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
          }
        }
        @media (max-width: 520px) {
          .browser-hero-stats {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}

function BrowserHeroStat({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div>
      <div className="meta" style={{ marginBottom: 4 }}>{label}</div>
      <div className="nums" style={{ fontSize: 22, color: "var(--ink)" }}>{value}</div>
      {note ? (
        <div style={{ marginTop: 6, fontSize: 13, color: "var(--ink-3)", lineHeight: 1.4 }}>
          {note}
        </div>
      ) : null}
    </div>
  );
}
