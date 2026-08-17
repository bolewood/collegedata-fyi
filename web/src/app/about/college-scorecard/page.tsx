import type { Metadata } from "next";
import Link from "next/link";
import {
  SOURCE_STORY_REVIEWED,
  SourceStoryLayout,
  StoryFigure,
  StoryTable,
} from "@/components/about/SourceStoryLayout";

const CANONICAL = "/about/college-scorecard";
const TITLE = "College Scorecard, and why it is not a CDS";
const DESCRIPTION =
  "College Scorecard is a federal consumer tool joined from IPEDS, NSLDS, Treasury, and FSA. It is not a Common Data Set, and its vintage lags the school-authored CDS year.";

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
  dateModified: SOURCE_STORY_REVIEWED,
  author: { "@type": "Organization", name: "Bolewood Group", url: "https://bolewood.com" },
  publisher: { "@type": "Organization", name: "collegedata.fyi", url: "https://www.collegedata.fyi" },
  about: {
    "@type": "Organization",
    name: "U.S. Department of Education College Scorecard",
    url: "https://collegescorecard.ed.gov/",
  },
  mainEntityOfPage: `https://www.collegedata.fyi${CANONICAL}`,
};

export default function CollegeScorecardPage() {
  return (
    <SourceStoryLayout
      kicker="College Scorecard"
      title={
        <>
          College Scorecard, and why it is not a CDS
        </>
      }
      lede="The federal consumer tool answers cost, debt, and earnings questions the Common Data Set never did. It is not this year’s admit table, and we do not blend the two into one unlabeled number."
      jsonLd={jsonLd}
    >
      <h2>Origin</h2>
      <p>
        The Obama-era{" "}
        <a
          href="https://collegescorecard.ed.gov/"
          target="_blank"
          rel="noopener noreferrer"
        >
          College Scorecard
        </a>{" "}
        is a Department of Education consumer-information product. It was not
        designed as a guidebook survey. Schools do not fill it in the way they
        fill a Common Data Set. Administrative systems already hold the
        records; Scorecard publishes a join of those records for prospective
        students.
      </p>
      <p>
        The official site at collegescorecard.ed.gov is the navigational
        result for “college scorecard.” This page is not trying to replace
        that. It exists so a reader of a school page here can see why a
        Scorecard earnings figure sits next to a CDS admit rate without
        becoming the same number.
      </p>

      <h2>What it actually is now</h2>
      <p>
        Current Scorecard institution files are a join of IPEDS, NSLDS
        (federal student aid), Treasury/IRS earnings, Federal Student Aid
        operating flags, and a handful of OPE and ACS fields. That mapping is
        in{" "}
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
        caption="College Scorecard source systems. Not a screenshot of ed.gov; a map of the join this site actually cites on school pages."
        href="/schools/harvey-mudd"
        hrefLabel="See the pairing on Harvey Mudd"
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
            "A single “latest” number that mixes vintages",
          ],
          [
            "Program-level CIP earnings on the .gov tool",
            "School-authored PDF/XLSX you can archive and cite",
            "Predicting admission for one applicant",
          ],
        ]}
      />

      <h2>Coverage vs the Common Data Set</h2>
      <p>
        IPEDS reporting is mandatory for Title IV schools. The Common Data
        Set is voluntary. That is why a school with no public CDS still has a
        Scorecard row, and why this site’s directory stub can show federal
        facts without pretending a CDS exists. Harvey Mudd and Virginia Tech
        both publish a CDS; they are the worked examples because a reader can
        cross{" "}
        <Link href="/about/common-data-set">the CDS story</Link> and{" "}
        <Link href="/about/ipeds">the IPEDS story</Link> on the same two
        institutions.
      </p>
      <StoryFigure
        src="/about/scorecard-title-iv-vs-cds-coverage.svg"
        alt="Coverage contrast: Title IV mandate gives every participating school a Scorecard row, while Common Data Set publication remains voluntary."
        caption="Coverage rule, not a school-year extract. Directory-only pages on this site exist because of this gap."
        href="/schools"
        hrefLabel="Browse schools"
      />

      <h2>Lag, on a live school page</h2>
      <p>
        On{" "}
        <Link href="/schools/harvey-mudd">Harvey Mudd</Link> and{" "}
        <Link href="/schools/virginia-tech">Virginia Tech</Link>, the
        admissions card is the archived CDS year. Directly under the federal
        outcomes band, the page already prints a vintage note: Scorecard
        outcomes reflect earlier cohorts than the CDS year shown elsewhere on
        the page. That pairing is the product. Scorecard is not “the latest
        CDS.”
      </p>
      <StoryFigure
        src="/about/harvey-mudd-scorecard-vintage-lag.svg"
        alt="Harvey Mudd school page pairing: archived Common Data Set year 2025-26 beside College Scorecard federal vintage note that outcomes lag the CDS year."
        caption="Harvey Mudd College school page. CDS year 2025-26 on the admissions side; College Scorecard vintage note on the federal outcomes side. Same pairing exists on Virginia Tech."
        href="/schools/harvey-mudd"
        hrefLabel="Open the Harvey Mudd hub"
      />

      <h2>Why it belongs next to a CDS here</h2>
      <p>
        Families ask for net price, debt, and earnings. Those questions are
        Scorecard’s job. We show them on the school page, labeled as federal,
        and we do not fold them into §C or §H. Virginia Tech’s{" "}
        <Link href="/schools/virginia-tech/2025-26">2025-26 year page</Link>{" "}
        is still the place for wait-list and testing extracts from the school
        file.
      </p>

      <h2>What the official site does better</h2>
      <p>
        Program-level CIP earnings, the comparison tool, and the full
        dictionary live on{" "}
        <a
          href="https://collegescorecard.ed.gov/"
          target="_blank"
          rel="noopener noreferrer"
        >
          collegescorecard.ed.gov
        </a>
        . We do not impersonate that site. What we do instead is keep
        Scorecard on the same source-linked school page as the archived CDS
        and the{" "}
        <Link href="/about/ipeds">IPEDS baseline</Link>, with the vintage
        mismatch visible.
      </p>
    </SourceStoryLayout>
  );
}
