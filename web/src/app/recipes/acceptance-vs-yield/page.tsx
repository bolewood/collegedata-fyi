import type { Metadata } from "next";
import Link from "next/link";
import { AcceptanceYieldChart } from "@/components/AcceptanceYieldChart";

export const metadata: Metadata = {
  title: "Acceptance rate vs. yield",
  description:
    "Two numbers, eighteen schools worth of context: how selective a school looks on paper (acceptance rate) against how selective it actually is (yield).",
  alternates: { canonical: "/recipes/acceptance-vs-yield" },
  openGraph: { url: "/recipes/acceptance-vs-yield" },
};

const QUADRANTS = [
  {
    num: "I",
    head: "Selective and desired",
    body: "Low acceptance, high yield. Both hard to get into and hard to turn down.",
  },
  {
    num: "II",
    head: "Loved despite openness",
    body: "Higher acceptance but strong yield. Often regional flagships or niche-fit schools.",
  },
  {
    num: "III",
    head: "Selective but second-choice",
    body: "Hard to get into, but most admits choose somewhere else. Cross-admit peers of top-left.",
  },
  {
    num: "IV",
    head: "Accessible and optional",
    body: "Admits freely, captures a smaller share. Common among safety-school territory.",
  },
];

export default function AcceptanceVsYieldPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
      {/* Header */}
      <header
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto",
          alignItems: "end",
          gap: 24,
          paddingTop: 16,
          paddingBottom: 8,
        }}
      >
        <div>
          <div
            className="mono"
            style={{
              fontSize: 11,
              color: "var(--ink-3)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            <Link
              href="/recipes"
              style={{ color: "var(--ink-3)", textDecoration: "none" }}
            >
              RECIPES
            </Link>{" "}
            / <span style={{ color: "var(--ink)" }}>ACCEPTANCE × YIELD</span>
          </div>
          <h1
            className="serif"
            style={{
              fontWeight: 400,
              fontSize: "clamp(36px, 5.5vw, 52px)",
              margin: "12px 0 0",
              letterSpacing: "-0.02em",
              lineHeight: 1,
            }}
          >
            Acceptance rate{" "}
            <span style={{ fontStyle: "italic" }}>vs.</span> yield
          </h1>
          <p
            style={{
              maxWidth: 640,
              marginTop: 12,
              color: "var(--ink-2)",
              fontSize: 16,
              lineHeight: 1.55,
            }}
          >
            Two numbers, eighteen schools worth of context. A{" "}
            <span
              className="serif"
              style={{ fontStyle: "italic" }}
            >
              collegedata.fyi
            </span>{" "}
            recipe.
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
          <span className="cd-chip">CDS C1</span>
          <span className="cd-chip">B1</span>
          <span className="cd-chip">B22</span>
        </div>
      </header>

      {/* Chart */}
      <section style={{ marginTop: 28 }}>
        <AcceptanceYieldChart />
      </section>

      {/* Reader's guide */}
      <section
        style={{
          marginTop: 48,
          display: "grid",
          gridTemplateColumns: "200px 1fr",
          gap: 40,
        }}
        className="cd-recipe-guide"
      >
        <div>
          <div className="meta" style={{ marginBottom: 6 }}>
            § How to read
          </div>
          <div
            className="serif"
            style={{
              fontSize: 20,
              fontStyle: "italic",
              color: "var(--ink-2)",
              lineHeight: 1.3,
            }}
          >
            &ldquo;Four quadrants, each
            <br />
            with teeth.&rdquo;
          </div>
        </div>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.65,
            color: "var(--ink-2)",
            maxWidth: 720,
            margin: 0,
          }}
        >
          The x-axis is how selective a school{" "}
          <span className="serif" style={{ fontStyle: "italic" }}>
            looks
          </span>{" "}
          on paper — its acceptance rate. The y-axis is how selective it
          actually{" "}
          <span className="serif" style={{ fontStyle: "italic" }}>
            is
          </span>{" "}
          in practice — its yield, the share of admitted students who
          actually enroll. Low acceptance + high yield is the top-left
          quadrant: schools that turn most applicants away and still capture
          most of the students they admit. Low acceptance + low yield is the
          bottom-left: schools that look selective but lose most of their
          admits to competitors.
        </p>
      </section>

      {/* Quadrant cards */}
      <section
        style={{
          marginTop: 48,
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 24,
        }}
        className="cd-recipe-quadrants"
      >
        {QUADRANTS.map((q) => (
          <div
            key={q.num}
            className="cd-card"
            style={{ padding: 20, display: "flex", gap: 16 }}
          >
            <div
              className="serif"
              style={{
                fontSize: 38,
                lineHeight: 0.9,
                color: "var(--forest)",
                fontStyle: "italic",
              }}
            >
              {q.num}.
            </div>
            <div>
              <div
                className="meta"
                style={{ marginBottom: 4, color: "var(--ink-3)" }}
              >
                QUADRANT {q.num}
              </div>
              <div
                className="serif"
                style={{ fontSize: 20, letterSpacing: "-0.005em" }}
              >
                {q.head}
              </div>
              <div
                style={{
                  fontSize: 14,
                  color: "var(--ink-2)",
                  lineHeight: 1.55,
                  marginTop: 6,
                }}
              >
                {q.body}
              </div>
            </div>
          </div>
        ))}
      </section>

      {/* Query block */}
      <section style={{ marginTop: 48 }}>
        <div className="meta" style={{ marginBottom: 10 }}>
          § Scale to all 697 schools
        </div>
        <pre
          style={{
            background: "var(--ink)",
            color: "var(--paper)",
            padding: "20px 24px",
            fontFamily: "var(--mono)",
            fontSize: 13,
            lineHeight: 1.55,
            margin: 0,
            borderRadius: 2,
            overflowX: "auto",
          }}
        >
{`curl https://collegedata.fyi/api/facts \\
  ?fields=C.116,C.117,C.118        `}
          <span style={{ color: "#c9c2ae" }}>{`# accept · admit · enroll`}</span>
{`
  &year=latest                     `}
          <span style={{ color: "#c9c2ae" }}>{`# most-recent CDS per school`}</span>
{`
  &verified=true                   `}
          <span style={{ color: "#c9c2ae" }}>{`# skip PDFs awaiting review`}</span>
        </pre>
        <div
          style={{
            marginTop: 14,
            display: "flex",
            gap: 16,
            flexWrap: "wrap",
            fontSize: 13,
          }}
        >
          <a
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/acceptance-vs-yield.md"
            target="_blank"
            rel="noopener noreferrer"
          >
            Read the full write-up →
          </a>
          <a href="/recipes/acceptance-vs-yield-starter.xlsx">
            Download XLSX starter
          </a>
        </div>
      </section>
    </div>
  );
}
