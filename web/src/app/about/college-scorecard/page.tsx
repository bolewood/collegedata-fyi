import type { Metadata } from "next";
import Link from "next/link";
import {
  SOURCE_STORY_REVIEWED,
  SourceStoryLayout,
  StoryFigure,
  StoryTable,
} from "@/components/about/SourceStoryLayout";
import { SITE_NAME, SITE_ORIGIN } from "@/lib/site";

const CANONICAL = "/about/college-scorecard";
const TITLE = "College Scorecard, and how it differs from the Common Data Set";
const DESCRIPTION =
  "College Scorecard reports federal net price, student debt, and post-college earnings across roughly 6,000 schools. Here is what it covers and why its dates lag a college’s Common Data Set.";
const REVIEWED = "2026-11-19";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: CANONICAL },
  openGraph: { url: CANONICAL, title: TITLE, description: DESCRIPTION },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: TITLE,
  description: DESCRIPTION,
  datePublished: SOURCE_STORY_REVIEWED,
  dateModified: REVIEWED,
  author: { "@type": "Organization", name: "Bolewood Group", url: "https://bolewood.com" },
  publisher: { "@type": "Organization", name: SITE_NAME, url: SITE_ORIGIN },
  about: {
    "@type": "Organization",
    name: "U.S. Department of Education College Scorecard",
    url: "https://collegescorecard.ed.gov/",
  },
  mainEntityOfPage: `${SITE_ORIGIN}${CANONICAL}`,
};

export default function CollegeScorecardPage() {
  return (
    <SourceStoryLayout
      kicker="College Scorecard"
      title={<>{TITLE}</>}
      lede="College Scorecard answers questions the Common Data Set never asks, such as what graduates actually borrow and earn years later. Because it draws from federal records rather than this year’s admissions office, we show it next to a school’s report instead of blending the two together."
      lastReviewed={REVIEWED}
      jsonLd={jsonLd}
    >
      <h2>Where it comes from</h2>
      <p>
        Launched by the U.S. Department of Education,{" "}
        <a
          href="https://collegescorecard.ed.gov/"
          target="_blank"
          rel="noopener noreferrer"
        >
          College Scorecard
        </a>{" "}
        is a public consumer database built from existing federal records rather
        than a survey colleges fill out each fall. Because the government
        compiles it from administrative data, it covers nearly every U.S.
        college that participates in federal financial aid, including thousands
        of schools that never publish a Common Data Set.
      </p>

      <h2>What goes into it</h2>
      <p>
        Each institution's Scorecard record combines several federal
        systems: IPEDS institutional surveys, federal student-aid records
        (NSLDS), Treasury/IRS earnings data, Federal Student Aid operating
        flags, and Census/OPE reference fields. We document the field-level
        comparison in{" "}
        <a
          href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/research/cds-vs-college-scorecard.md"
          target="_blank"
          rel="noopener noreferrer"
        >
          CDS vs College Scorecard
        </a>
        .
      </p>
      <StoryFigure
        src="/about/college-scorecard-source-join.svg"
        alt="Diagram of College Scorecard as a join of IPEDS, NSLDS, Treasury/IRS earnings, FSA, and OPE/ACS, not a school-authored Common Data Set."
        caption="How College Scorecard combines five federal data sources into one institutional record."
        href="/schools/harvey-mudd"
        hrefLabel="See how it appears on Harvey Mudd"
      />

      <StoryTable
        caption="What Scorecard is good at, what CDS is good at, and what neither covers"
        headers={["Scorecard is good at", "CDS is good at", "Neither"]}
        rows={[
          [
            "Net price, debt, repayment, earnings by cohort",
            "Current-year applicants / admits / enrolled (C1)",
            "Student-level records",
          ],
          [
            "Title IV universe (~6,000 institutions)",
            "Wait list, ED/EA, C7 factor matrix, H2A merit",
            "A single blended number that hides which year it came from",
          ],
          [
            "Program-level CIP earnings on the .gov tool",
            "Original school-published PDF or spreadsheet you can download and cite",
            "Predicting admission for one applicant",
          ],
        ]}
      />

      <h2>Why Scorecard covers more schools than the Common Data Set</h2>
      <p>
        Federal reporting through IPEDS is mandatory for colleges that accept
        federal student aid, while publishing a Common Data Set is voluntary.
        That is why a college with no public Common Data Set still has a page
        here with federal cost and outcome figures rather than a dead end. Both{" "}
        <Link href="/schools/harvey-mudd">Harvey Mudd</Link> and{" "}
        <Link href="/schools/virginia-tech">Virginia Tech</Link> publish Common
        Data Sets, so they serve as useful side-by-side examples across our{" "}
        <Link href="/about/common-data-set">Common Data Set</Link> and{" "}
        <Link href="/about/ipeds">IPEDS</Link> guides.
      </p>
      <StoryFigure
        src="/about/scorecard-title-iv-vs-cds-coverage.svg"
        alt="Coverage contrast: Title IV mandate gives every participating school a Scorecard row, while Common Data Set publication remains voluntary."
        caption="Mandatory federal reporting covers roughly 6,000 colleges, while voluntary Common Data Set publishing covers only a subset."
        href="/schools"
        hrefLabel="Browse schools"
      />

      <h2>Why Scorecard dates lag a school's own report</h2>
      <p>
        On pages like <Link href="/schools/harvey-mudd">Harvey Mudd</Link> and{" "}
        <Link href="/schools/virginia-tech">Virginia Tech</Link>, admissions and
        test-score cards come from the college's latest archived Common
        Data Set, while federal outcomes sit in their own section with a vintage
        note. Earnings and repayment figures naturally reflect earlier cohorts
        (often students who enrolled a decade earlier), so they will never match
        the current admissions cycle year for year.
      </p>
      <StoryFigure
        src="/about/harvey-mudd-scorecard-vintage-lag.svg"
        alt="Harvey Mudd school page pairing: archived Common Data Set year 2025-26 beside College Scorecard federal vintage note that outcomes lag the CDS year."
        caption="On Harvey Mudd’s school page, the 2025–26 Common Data Set sits alongside federal Scorecard outcomes with their cohort dates clearly noted."
        href="/schools/harvey-mudd"
        hrefLabel="Open the Harvey Mudd page"
      />

      <h2>How we use it alongside the Common Data Set</h2>
      <p>
        Families need both kinds of information: this year's admissions and
        merit-aid picture from the college, and long-term net price, debt, and
        earnings from federal records. Showing both on one page, with each
        section labeled by source and year, lets you read them together without
        mistaking one for the other. For school-specific details like waitlists
        or test policies, open a year page such as{" "}
        <Link href="/schools/virginia-tech/2025-26">Virginia Tech 2025–26</Link>
        .
      </p>

      <h2>When to use the official Scorecard site</h2>
      <p>
        If you want earnings broken down by individual major (CIP code), the
        federal comparison tool, or the full data dictionary, go straight to{" "}
        <a
          href="https://collegescorecard.ed.gov/"
          target="_blank"
          rel="noopener noreferrer"
        >
          collegescorecard.ed.gov
        </a>
        . We bring Scorecard's institutional metrics onto each school page
        so you can read them alongside a college's Common Data Set and{" "}
        <Link href="/about/ipeds">IPEDS baseline</Link> without juggling three
        different sites.
      </p>
    </SourceStoryLayout>
  );
}
