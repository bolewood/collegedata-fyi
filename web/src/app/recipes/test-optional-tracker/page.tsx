import type { Metadata } from "next";
import Link from "next/link";
import { TestOptionalChart } from "@/components/TestOptionalChart";

export const metadata: Metadata = {
  title: "Test-optional tracker",
  description:
    "What share of enrolled first-years actually submitted SAT scores, year by year. Written disclosures lie; enrollment numbers don't.",
  alternates: { canonical: "/recipes/test-optional-tracker" },
  openGraph: { url: "/recipes/test-optional-tracker" },
};

const BANDS = [
  {
    range: "≥ 85% submission",
    head: "Effectively test-required",
    body: "Almost every admit submits scores; not submitting is a meaningful disadvantage.",
    accent: "var(--brick)",
  },
  {
    range: "10–85% submission",
    head: "Genuinely test-optional",
    body: "A real fraction of admits get in without scores. The middle band is where written and effective policy actually agree.",
    accent: "var(--ochre)",
  },
  {
    range: "< 10% submission",
    head: "Effectively test-blind",
    body: "Written policy is binding regardless of whether a student submits. Score data has no place in the decision.",
    accent: "var(--forest)",
  },
];

export default function TestOptionalTrackerPage() {
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
            /{" "}
            <span style={{ color: "var(--ink)" }}>
              TEST-OPTIONAL TRACKER
            </span>
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
            Test-<span style={{ fontStyle: "italic" }}>optional</span>?
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
            What share of enrolled first-years actually submitted SAT
            scores, year by year. A{" "}
            <span className="serif" style={{ fontStyle: "italic" }}>
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
          <span className="cd-chip">CDS C8</span>
          <span className="cd-chip">C9</span>
        </div>
      </header>

      {/* Chart */}
      <section style={{ marginTop: 28 }}>
        <TestOptionalChart />
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
            &ldquo;Policy claims;
            <br />
            enrollment proves.&rdquo;
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
          The y-axis is the percentage of enrolled first-year students who
          submitted SAT scores. Higher = more students submitted = closer
          to a de-facto{" "}
          <span className="serif" style={{ fontStyle: "italic" }}>
            test-required
          </span>{" "}
          school. The dashed lines mark 85% (above = effectively
          test-required) and 10% (below = effectively test-blind); anything
          between is{" "}
          <span className="serif" style={{ fontStyle: "italic" }}>
            genuinely
          </span>{" "}
          test-optional. Written policy and effective practice do not
          always match — which is the whole point.
        </p>
      </section>

      {/* Band cards */}
      <section
        style={{
          marginTop: 48,
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 24,
        }}
        className="cd-recipe-bands"
      >
        {BANDS.map((b) => (
          <div
            key={b.range}
            className="cd-card"
            style={{
              padding: 20,
              borderLeft: `3px solid ${b.accent}`,
            }}
          >
            <div
              className="meta"
              style={{ marginBottom: 4, color: "var(--ink-3)" }}
            >
              {b.range}
            </div>
            <div
              className="serif"
              style={{ fontSize: 20, letterSpacing: "-0.005em" }}
            >
              {b.head}
            </div>
            <div
              style={{
                fontSize: 14,
                color: "var(--ink-2)",
                lineHeight: 1.55,
                marginTop: 6,
              }}
            >
              {b.body}
            </div>
          </div>
        ))}
      </section>

      {/* Query block */}
      <section style={{ marginTop: 48 }}>
        <div className="meta" style={{ marginBottom: 10 }}>
          § Pull this for any school
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
  ?fields=C.901,C.902              `}
          <span style={{ color: "#c9c2ae" }}>{`# % submitting SAT · ACT`}</span>
{`
  &school=yale-university           `}
          <span style={{ color: "#c9c2ae" }}>{`# any slug from /schools`}</span>
{`
  &year=2009-2024                  `}
          <span style={{ color: "#c9c2ae" }}>{`# every archived year`}</span>
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
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/test-optional-tracker.md"
            target="_blank"
            rel="noopener noreferrer"
          >
            Read the full write-up →
          </a>
        </div>
      </section>
    </div>
  );
}
