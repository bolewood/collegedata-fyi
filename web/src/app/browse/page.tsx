import type { Metadata } from "next";
import { SchoolBrowser } from "@/components/SchoolBrowser";

export const metadata: Metadata = {
  title: "Queryable School Browser",
  description:
    "Filter the 2024-25 Common Data Set browser rows by admissions, enrollment, price, and outcome metrics.",
  alternates: { canonical: "/browse" },
  openGraph: { url: "/browse" },
};

export default function BrowsePage() {
  return (
    <div className="mx-auto max-w-6xl" style={{ padding: "52px 24px 72px" }}>
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
          <div>§ BROWSER</div>
          <div>2024-25+</div>
          <div>PRIMARY ROWS</div>
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
            Queryable school <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>browser.</span>
          </h1>
          <p
            style={{
              margin: "20px 0 0",
              maxWidth: 720,
              color: "var(--ink-2)",
              fontSize: 17,
              lineHeight: 1.6,
            }}
          >
            Filter the curated 2024-25 browser rows without losing the source trail.
            The default view chooses the latest primary row per school that can answer
            the active filters, then reports how many schools were missing values.
          </p>
        </div>
      </section>

      <SchoolBrowser />

      <style>{`
        @media (max-width: 760px) {
          .browser-hero {
            grid-template-columns: 1fr !important;
            gap: 14px !important;
          }
        }
      `}</style>
    </div>
  );
}
