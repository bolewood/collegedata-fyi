import type { Metadata } from "next";
import Link from "next/link";
import {
  SOURCE_STORY_REVIEWED,
  SourceStoryLayout,
  StoryFigure,
  StoryTable,
} from "@/components/about/SourceStoryLayout";

const CANONICAL = "/about/ipeds";
const TITLE = "What IPEDS is, and what it cannot replace";
const DESCRIPTION =
  "IPEDS is the federal statistical database filed each year by roughly 6,400 U.S. colleges. Here is what it covers, how we use it on school pages, and why it cannot replace a Common Data Set.";
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
  publisher: { "@type": "Organization", name: "collegedata.fyi", url: "https://www.collegedata.fyi" },
  about: {
    "@type": "Organization",
    name: "National Center for Education Statistics IPEDS",
    url: "https://nces.ed.gov/ipeds",
  },
  mainEntityOfPage: `https://www.collegedata.fyi${CANONICAL}`,
};

export default function IpedsPage() {
  return (
    <SourceStoryLayout
      kicker="IPEDS"
      title={<>{TITLE}</>}
      lede="The federal government already maintains a comprehensive statistical record of U.S. colleges through IPEDS. It is essential for long-term trends, institutional finances, and broad coverage, but it moves on a slower federal schedule and leaves out key admissions details colleges publish in their Common Data Sets."
      lastReviewed={REVIEWED}
      jsonLd={jsonLd}
    >
      <h2>The federal baseline (and UNITID)</h2>
      <p>
        Run by the{" "}
        <a href="https://nces.ed.gov/" target="_blank" rel="noopener noreferrer">
          National Center for Education Statistics
        </a>
        ,{" "}
        <a
          href="https://nces.ed.gov/ipeds"
          target="_blank"
          rel="noopener noreferrer"
        >
          IPEDS
        </a>{" "}
        (the Integrated Postsecondary Education Data System) collects annual
        survey data from roughly 6,400 U.S. institutions that participate in
        federal financial aid. Every institution has a permanent numeric
        identifier called a <code>UNITID</code> (for example,{" "}
        <code>115409</code> for Harvey Mudd and <code>233921</code> for Virginia
        Tech), which is how we reliably match federal records to each
        school's published reports.
      </p>
      <p>
        For official definitions and raw downloads, go to{" "}
        <a
          href="https://nces.ed.gov/ipeds"
          target="_blank"
          rel="noopener noreferrer"
        >
          nces.ed.gov/ipeds
        </a>
        . This guide explains how those federal tables appear on collegedata.fyi
        and where they differ from a college's Common Data Set.
      </p>

      <h2>How IPEDS data is structured</h2>
      <p>
        Instead of one annual document, IPEDS is organized into separate survey
        components: directory information (<code>HD</code>), institutional
        characteristics (<code>IC</code>), admissions (<code>ADM</code>), fall
        enrollment (<code>EF</code>), graduation rates (<code>GR</code>),
        student financial aid (<code>SFA</code>), and finance (<code>F</code>).
        NCES publishes provisional files first (after quality checks and
        imputations for missing responses), followed later by revised final
        files distributed as Microsoft Access databases and codebooks.
      </p>
      <StoryFigure
        src="/about/ipeds-survey-components.svg"
        alt="IPEDS described as survey components HD, IC, ADM, EF, GR, SFA, and F, released first as provisional then final Access databases."
        caption="IPEDS survey components are released first as provisional files and later as final datasets, keyed by each school’s UNITID."
        href="/schools/virginia-tech"
        hrefLabel="See Virginia Tech’s federal baseline table"
      />

      <h2>How IPEDS appears on a school page</h2>
      <p>
        On every school page, the federal baseline table lists the exact IPEDS
        table, variable name, release status (<code>provisional</code> or{" "}
        <code>final</code>), and how closely the federal definition aligns with
        the Common Data Set:
      </p>
      <StoryTable
        caption="Example IPEDS facts and how they align to CDS"
        headers={["Fact", "Alignment", "Why it matters"]}
        rows={[
          [
            "Admission rate",
            "Near CDS",
            "ADM totals track C1 closely, though definitions of student population, gender reporting, and release timing can differ.",
          ],
          [
            "Endowment",
            "Not CDS-equivalent",
            "Finance (F) is additive context. CDS never had a standard endowment table.",
          ],
          [
            "Locale",
            "Direct",
            "HD locale is a federal geographic classification rather than a Common Data Set field.",
          ],
        ]}
      />
      <StoryFigure
        src="/about/virginia-tech-ipeds-baseline-source-column.svg"
        alt="Federal baseline table with source column showing ADM admission rate as near CDS, finance endowment as not CDS-equivalent, and HD locale as direct, with source_table.source_variable labels."
        caption="Virginia Tech’s federal baseline table, showing the IPEDS table, variable name, and release status for each figure."
        href="/schools/virginia-tech"
        hrefLabel="Open Virginia Tech"
      />

      <h2>What IPEDS cannot replace</h2>
      <p>
        IPEDS is not a substitute for a college's Common Data Set. It does
        not report current-year waitlist numbers, Early Decision vs. Regular
        Decision outcomes, non-need merit aid counts (Section H2A), or the
        school's own published PDF. Common Data Sets also tend to appear
        months before the corresponding IPEDS release. For those school-reported
        details, open a year page such as{" "}
        <Link href="/schools/virginia-tech/2025-26">
          Virginia Tech 2025–26
        </Link>{" "}
        or{" "}
        <Link href="/schools/harvey-mudd/2025-26">
          Harvey Mudd 2025–26
        </Link>
        .
      </p>

      <h2>Why we include it anyway</h2>
      <ul>
        <li>
          <strong>Broader coverage:</strong> When a college doesn't publish
          a Common Data Set, IPEDS still gives you reliable enrollment, cost,
          and admissions context.
        </li>
        <li>
          <strong>Longer history:</strong> Federal series remain consistent over
          time even when a college reorganizes its website or removes older
          PDFs.
        </li>
        <li>
          <strong>Institutional finance:</strong> IPEDS Finance filings include
          endowment and spending figures that the Common Data Set doesn't
          cover (see our{" "}
          <Link href="/recipes/endowment-draw-rate">
            endowment draw-rate analysis
          </Link>
          ).
        </li>
      </ul>

      <h2>Telling the three sources apart on a school page</h2>
      <p>
        Each school page keeps its sources visually separate. Common Data Set
        figures live in the main school-year view alongside the downloadable
        original file. IPEDS figures appear in the federal baseline table with
        their <code>UNITID</code>, table, and variable names. College Scorecard
        outcomes sit in their own section with cohort vintage notes.
      </p>
      <StoryFigure
        src="/about/virginia-tech-cds-and-ipeds-source-labels.svg"
        alt="Annotated split of a school page: Common Data Set extract with field IDs on one side, IPEDS source_table.source_variable on the other, both circled as separate source layers."
        caption="Virginia Tech’s school page, keeping school-published Common Data Set figures separate from the federal IPEDS baseline."
        href="/schools/virginia-tech"
        hrefLabel="Open Virginia Tech"
      />
      <p>
        Related:{" "}
        <Link href="/about/common-data-set">What is the Common Data Set</Link>
        {" · "}
        <Link href="/about/college-scorecard">
          College Scorecard, and how it differs from the Common Data Set
        </Link>
        .
      </p>
    </SourceStoryLayout>
  );
}
