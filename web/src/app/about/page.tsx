import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About",
  description:
    "The most comprehensive free college data we know of. School Common Data Set reports, IPEDS, and College Scorecard, in one public place. No account.",
  alternates: { canonical: "/about" },
  openGraph: { url: "/about" },
};

const linkStyle = {
  textDecorationColor: "var(--rule-strong)",
  textUnderlineOffset: 3,
} as const;

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12" style={{ color: "var(--ink-2)" }}>
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
        The <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>Uncommon</span> Data Set
      </h1>

      <div className="mt-8 space-y-5 text-base leading-relaxed">
        <p>
          Choosing a college should not mean a dozen tabs, a paid search
          product, and a PDF you can&apos;t compare. This is the most
          comprehensive free college data we know of: each school&apos;s{" "}
          <Link href="/about/common-data-set" style={linkStyle}>
            Common Data Set
          </Link>
          , plus{" "}
          <Link href="/about/ipeds" style={linkStyle}>
            IPEDS
          </Link>{" "}
          and{" "}
          <Link href="/about/college-scorecard" style={linkStyle}>
            College Scorecard
          </Link>
          , in one public place.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          What you can do
        </h2>

        <ul className="ml-6 list-disc space-y-2 marker:text-gray-400">
          <li>Search a school and open the latest report it published.</li>
          <li>
            If a school hasn&apos;t published its own report, you still get the
            federal numbers.
          </li>
          <li>Download the original file the school posted.</li>
          <li>
            Compare admissions, enrollment, test scores, cost, and aid across
            schools.
          </li>
          <li>
            Build a match list on your device. We don&apos;t store a student
            profile.
          </li>
          <li>
            If you&apos;re in IR or research: use the same data through a{" "}
            <Link href="/api" style={linkStyle}>
              public API
            </Link>
            .
          </li>
        </ul>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          How this is different
        </h2>

        <p>
          Commercial college-search tools can be useful. They often want an
          account, hide where a number came from, or build a student profile
          along the way. We don&apos;t. The school&apos;s own report sits next
          to the federal numbers, the original file is one click away, and you
          don&apos;t have to pay or log in.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          The reports, in one line each
        </h2>

        <ul className="ml-6 list-disc space-y-2 marker:text-gray-400">
          <li>
            <Link href="/about/common-data-set" style={linkStyle}>
              Common Data Set
            </Link>{" "}
            — the yearly report the college writes.
          </li>
          <li>
            <Link href="/about/college-scorecard" style={linkStyle}>
              College Scorecard
            </Link>{" "}
            — federal outcomes and net price.
          </li>
          <li>
            <Link href="/about/ipeds" style={linkStyle}>
              IPEDS
            </Link>{" "}
            — the federal statistical baseline.
          </li>
        </ul>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          Open source
        </h2>

        <p>
          Code, schema, pipeline, and archived files are public (MIT).{" "}
          <a
            href="https://github.com/bolewood/collegedata-fyi"
            target="_blank"
            rel="noopener noreferrer"
            style={linkStyle}
          >
            GitHub
          </a>
          .{" "}
          <Link href="/api" style={linkStyle}>
            API
          </Link>
          . Developers who want extractors and known issues start there, not
          on this page.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>Credits</h2>

        <p>
          Built on{" "}
          <a
            href="https://supabase.com"
            target="_blank"
            rel="noopener noreferrer"
            style={linkStyle}
          >
            Supabase
          </a>
          . Federal baseline facts come from official{" "}
          <a
            href="https://nces.ed.gov/ipeds/"
            target="_blank"
            rel="noopener noreferrer"
            style={linkStyle}
          >
            NCES/IPEDS
          </a>{" "}
          releases.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          Project Sponsors
        </h2>

        <p>collegedata.fyi is supported by:</p>

        <ul className="ml-6 list-disc space-y-2 marker:text-gray-400">
          <li>
            <a
              href="https://bolewood.com"
              target="_blank"
              rel="noopener noreferrer"
              style={linkStyle}
            >
              Bolewood Group
            </a>
          </li>
        </ul>

        <div style={{ marginTop: 40, borderTop: "1px solid var(--rule)", paddingTop: 24, fontSize: 13, fontStyle: "italic", fontFamily: "var(--serif)", color: "var(--ink-3)" }}>
          Better college decisions start with better access to the facts.
        </div>
      </div>
    </div>
  );
}
