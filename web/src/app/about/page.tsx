import { REPO_URL } from "@/lib/repo";
import type { Metadata } from "next";
import Link from "next/link";
import { SOURCE_OWNERSHIP_SENTENCE } from "@/lib/data-license";
import { isUsageLaunched } from "@/lib/usage";

export const metadata: Metadata = {
  title: "About",
  description:
    "We collect colleges’ annual Common Data Set reports alongside federal IPEDS and College Scorecard data, linked to the original files and free with no account.",
  alternates: { canonical: "/about" },
  openGraph: { url: "/about" },
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12" style={{ color: "var(--ink-2)" }}>
      <h1
        className="serif"
        style={{
          fontWeight: 400,
          fontSize: "clamp(40px, 6vw, 56px)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
          margin: 0,
        }}
      >
        The <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>Uncommon</span> Data Set
      </h1>

      <p
        className="serif"
        style={{
          fontStyle: "italic",
          fontSize: 18,
          lineHeight: 1.55,
          color: "var(--ink-2)",
          margin: "20px 0 0",
          maxWidth: "40rem",
        }}
      >
        Most U.S. colleges publish a detailed annual report called the Common
        Data Set, then tuck it away as a PDF somewhere on their website. We
        collect those reports alongside federal IPEDS and College Scorecard data
        so families, counselors, and researchers can look up real numbers in one
        free, public place.
      </p>

      <div className="cd-source-story">
        <h2>What you can do</h2>
        <ul>
          <li>
            Look up any college and read its latest published report, or its
            federal data when the school hasn't published a Common Data
            Set.
          </li>
          <li>Download the original PDF or spreadsheet the college posted.</li>
          <li>
            Compare admissions, test scores, tuition, and financial aid across
            schools.
          </li>
          <li>
            Build a college match list in your browser without creating an
            account or saving a student profile on our servers.
          </li>
          <li>
            Pull the same underlying dataset for research, journalism, or LLM
            tools through the <Link href="/api">public API</Link>.
          </li>
        </ul>

        <h2>How this is different</h2>
        <p>
          Commercial college-search sites can be helpful, though many require an
          account, hide where a figure came from, or build a student profile
          along the way. Here, each school's own report sits next to
          federal data, every figure links back to its source, and nothing sits
          behind a login or paywall.
        </p>

        <h2>The three data sources</h2>
        <ul>
          <li>
            <Link href="/about/common-data-set">Common Data Set</Link>: the
            annual report colleges publish on admissions, enrollment, cost, and
            financial aid.
          </li>
          <li>
            <Link href="/about/college-scorecard">College Scorecard</Link>:
            federal figures on net price, student debt, and post-college
            earnings.
          </li>
          <li>
            <Link href="/about/ipeds">IPEDS</Link>: the federal statistical
            baseline filed each year by U.S. colleges that receive federal
            student aid.
          </li>
        </ul>

        <h2>Open source</h2>
        <p>
          Our code is open source under the MIT license on{" "}
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
          , and the full dataset is available through the{" "}
          <Link href="/api">public API</Link>. The structured extracts we
          derive are licensed CC BY 4.0, so you can reuse them with{" "}
          <Link href="/api#credit">credit</Link>. {SOURCE_OWNERSHIP_SENTENCE} If
          you're curious how files
          are parsed or want to check known data quirks, GitHub is the best
          place to look.{" "}
          {isUsageLaunched() ? (
            <>
              {" "}
              You can also see how the archive is used on the{" "}
              <Link href="/usage">usage page</Link>.
            </>
          ) : null}
        </p>

        <h2>Credits</h2>
        <p>
          Built on{" "}
          <a href="https://supabase.com" target="_blank" rel="noopener noreferrer">
            Supabase
          </a>
          . Federal baseline facts come from official{" "}
          <a
            href="https://nces.ed.gov/ipeds/"
            target="_blank"
            rel="noopener noreferrer"
          >
            NCES/IPEDS
          </a>{" "}
          releases.
        </p>

        <h2>Project Sponsors</h2>
        <p>Quadfile is supported by:</p>
        <ul>
          <li>
            <a href="https://bolewood.com" target="_blank" rel="noopener noreferrer">
              Bolewood Group
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
}
