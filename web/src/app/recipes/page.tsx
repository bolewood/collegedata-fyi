import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Recipes",
  description:
    "Worked examples of what you can do with the collegedata.fyi Common Data Set archive: interactive charts seeded with hand-verified data, extendable to the full corpus via the public API.",
  alternates: { canonical: "/recipes" },
  openGraph: { url: "/recipes" },
};

type Recipe = {
  slug: string;
  title: string;
  tagline: string;
  audience: string;
  demoPath: string;
  writeupUrl: string;
  sections: string;
  extras?: { label: string; path: string }[];
};

const RECIPES: Recipe[] = [
  {
    slug: "acceptance-vs-yield",
    title: "Acceptance rate vs. yield",
    tagline:
      "Scatter plot of how selective a school looks on paper (acceptance rate) against how selective it actually is in practice (yield). Four quadrants with teeth: selective-and-desired, loved-despite-openness, selective-but-second-choice, accessible-and-optional.",
    audience:
      "Students and parents building a target list; counselors calibrating reach/match/safety.",
    demoPath: "/recipes/acceptance-vs-yield-demo.html",
    writeupUrl:
      "https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/acceptance-vs-yield.md",
    sections: "C1, B1, B22",
    extras: [
      {
        label: "XLSX starter",
        path: "/recipes/acceptance-vs-yield-starter.xlsx",
      },
    ],
  },
  {
    slug: "test-optional-tracker",
    title: "Test-optional tracker",
    tagline:
      "Line chart of SAT submission percentage over time for seven well-documented schools (Yale 2009\u20132024, Caltech 2002\u20132020, MIT, Princeton, Stanford, Harvard, Wake Forest). Uses the submission rate as an honest proxy for effective test-optional policy \u2014 written disclosures lie, enrollment numbers don't.",
    audience:
      "Students deciding whether a school's \u201ctest-optional\u201d is real; reporters tracking the post-COVID reversion.",
    demoPath: "/recipes/test-optional-tracker-demo.html",
    writeupUrl:
      "https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/test-optional-tracker.md",
    sections: "C8, C9",
  },
];

export default function RecipesPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <div className="meta" style={{ marginBottom: 16 }}>§ Recipes</div>
      <h1
        style={{
          fontFamily: "var(--serif)",
          fontWeight: 400,
          fontSize: 48,
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
          margin: 0,
        }}
      >
        Worked <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>examples</span>.
      </h1>
      <p style={{ marginTop: 20, fontSize: 16, lineHeight: 1.6, color: "var(--ink-2)" }}>
        What you can do with the archive. Each recipe pairs a short write-up with an interactive
        artifact seeded from hand-verified data, plus a copy-pasteable API query you can use to
        scale it to the full corpus. If you want to contribute one,{" "}
        <a
          href="https://github.com/bolewood/collegedata-fyi/blob/main/CONTRIBUTING.md"
          target="_blank"
          rel="noopener noreferrer"
        >
          PRs welcome
        </a>
        .
      </p>

      <div className="mt-8 space-y-5">
        {RECIPES.map((r) => (
          <article
            key={r.slug}
            className="cd-card cd-card--cut"
            style={{ padding: 20 }}
          >
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
              <h2
                style={{
                  fontFamily: "var(--serif)",
                  fontWeight: 500,
                  fontSize: 22,
                  letterSpacing: "-0.01em",
                  color: "var(--ink)",
                  margin: 0,
                }}
              >
                <a href={r.demoPath} style={{ textDecoration: "none", color: "inherit" }}>
                  {r.title}
                </a>
              </h2>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>
                CDS {r.sections}
              </span>
            </div>
            <p style={{ marginTop: 10, fontSize: 14, lineHeight: 1.55, color: "var(--ink-2)" }}>
              {r.tagline}
            </p>
            <p style={{ marginTop: 8, fontSize: 12, color: "var(--ink-3)" }}>
              <span className="meta" style={{ marginRight: 6 }}>For</span>
              {r.audience}
            </p>
            <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
              <a href={r.demoPath} className="cd-btn" style={{ padding: "8px 14px", fontSize: 13 }}>
                Open demo →
              </a>
              <a
                href={r.writeupUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 12 }}
              >
                Read write-up
              </a>
              {r.extras?.map((x) => (
                <a key={x.path} href={x.path} style={{ fontSize: 12 }}>
                  {x.label}
                </a>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div
        style={{
          marginTop: 40,
          border: "1px dashed var(--rule-strong)",
          background: "var(--paper-2)",
          padding: 20,
          borderRadius: 2,
        }}
      >
        <div className="meta" style={{ marginBottom: 10 }}>§ Not yet built</div>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, color: "var(--ink-2)", lineHeight: 1.6 }}>
          <li>
            Net-price-by-income-bracket (H2A, H4) — the single most-asked
            question in college search.
          </li>
          <li>
            Realistic/reach/safety calibration from the published C9/C11
            distributions.
          </li>
          <li>
            Recruited athlete × program strength (Section F × Section J).
          </li>
          <li>
            &ldquo;Has this school changed?&rdquo; — longitudinal view of
            one school&apos;s selectivity, yield, and aid generosity over 5+
            years.
          </li>
        </ul>
        <p style={{ marginTop: 14, fontSize: 12, color: "var(--ink-3)" }}>
          Want to build one of these?{" "}
          <a
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/README.md"
            target="_blank"
            rel="noopener noreferrer"
          >
            See the recipes guide
          </a>
          .
        </p>
      </div>

      <div style={{ marginTop: 40, borderTop: "1px solid var(--rule)", paddingTop: 24, fontSize: 14, color: "var(--ink-3)" }}>
        Looking for the data directly? Head to the{" "}
        <Link href="/api">public API</Link> or browse every school in the{" "}
        <Link href="/schools">directory</Link>.
      </div>
    </div>
  );
}
