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
  "IPEDS is the NCES statistical system of record for U.S. colleges, keyed by UNITID. It cannot replace current-year Common Data Set wait-list, ED/EA, or H2A merit counts.";

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
    name: "National Center for Education Statistics IPEDS",
    url: "https://nces.ed.gov/ipeds",
  },
  mainEntityOfPage: `https://www.collegedata.fyi${CANONICAL}`,
};

export default function IpedsPage() {
  return (
    <SourceStoryLayout
      kicker="IPEDS"
      title={
        <>
          What IPEDS is, and what it cannot replace
        </>
      }
      lede="NCES already has a statistical system of record. It is a stack of survey tables with dictionaries, not a PDF, and it is not this year’s school-authored Common Data Set."
      jsonLd={jsonLd}
    >
      <h2>NCES and UNITID</h2>
      <p>
        The{" "}
        <a href="https://nces.ed.gov/" target="_blank" rel="noopener noreferrer">
          National Center for Education Statistics
        </a>{" "}
        runs{" "}
        <a
          href="https://nces.ed.gov/ipeds"
          target="_blank"
          rel="noopener noreferrer"
        >
          IPEDS
        </a>
        , the Integrated Postsecondary Education Data System. About 6,400
        Title IV institutions file interrelated annual surveys. The join key
        this site actually uses is UNITID — Harvey Mudd is 115409, Virginia
        Tech is 233921.
      </p>
      <p>
        The navigational query “IPEDS” belongs to nces.ed.gov/ipeds. This
        page is the counselor-facing explanation of what those tables are,
        how they show up on a school page here, and what they cannot stand in
        for.
      </p>

      <h2>How data gets in</h2>
      <p>
        Components include HD (directory), IC (characteristics), ADM
        (admissions), EF (fall enrollment), GR (graduation rates), SFA
        (student financial aid), and F (finance), among others. NCES releases
        provisional files after quality control, including imputations for
        nonrespondents, then final files with institutional revisions.
        Recent years still arrive as Microsoft Access databases plus
        dictionaries. That is the silo on the federal side: not a 47-page
        PDF, a stack of tables.
      </p>
      <StoryFigure
        src="/about/ipeds-survey-components.svg"
        alt="IPEDS described as survey components HD, IC, ADM, EF, GR, SFA, and F, released first as provisional then final Access databases."
        caption="IPEDS survey-component stack. Official documentation: nces.ed.gov/ipeds. UNITID is the join key on this site."
        href="/schools/virginia-tech"
        hrefLabel="See Virginia Tech’s federal baseline table"
      />

      <h2>Worked examples on a live school page</h2>
      <p>
        The school-page federal baseline table (the IPEDS coverage layer)
        keeps source_table, source_variable, release type, and
        definition-alignment visible. Typical alignments:
      </p>
      <StoryTable
        caption="Example IPEDS facts and how they align to CDS"
        headers={["Fact", "Alignment", "Why it matters"]}
        rows={[
          [
            "Admission rate",
            "Near CDS",
            "ADM totals can match C1 in spirit and still differ in population, gender treatment, and vintage.",
          ],
          [
            "Endowment",
            "Not CDS-equivalent",
            "Finance (F) is additive context. CDS never had a standard endowment table.",
          ],
          [
            "Locale",
            "Direct",
            "HD locale is a federal classification, not a school-authored CDS cell.",
          ],
        ]}
      />
      <StoryFigure
        src="/about/virginia-tech-ipeds-baseline-source-column.svg"
        alt="Federal baseline table with source column showing ADM admission rate as near CDS, finance endowment as not CDS-equivalent, and HD locale as direct, with source_table.source_variable labels."
        caption="Virginia Tech school page, NCES/IPEDS baseline table. Source column is source_table.source_variable plus release status. Not a substitute for the 2025-26 CDS extract."
        href="/schools/virginia-tech"
        hrefLabel="Open the Virginia Tech hub"
      />

      <h2>What IPEDS cannot replace</h2>
      <p>
        In public language, the coverage layer’s non-goals are: IPEDS is not
        a drop-in Common Data Set. It does not give you current-year wait-list
        behavior, Early Decision versus other rounds, H2A merit counts, or
        the school-authored PDF as accountability. CDS files often publish
        months before the matching IPEDS release. We do not silently blend
        CDS and IPEDS into one unlabeled number.
      </p>
      <p>
        For those CDS-native slices, use the year page:{" "}
        <Link href="/schools/virginia-tech/2025-26">
          Virginia Tech 2025-26
        </Link>{" "}
        and{" "}
        <Link href="/schools/harvey-mudd/2025-26">
          Harvey Mudd 2025-26
        </Link>
        .
      </p>

      <h2>Why we load it</h2>
      <ul>
        <li>
          Directory-scale coverage when no public CDS exists — the search
          result is still a school page, not a dead end.
        </li>
        <li>Historical series that outlast a school’s current IR listing.</li>
        <li>
          Finance (endowment draw, Part H) that the CDS template never had.
          See the{" "}
          <Link href="/recipes/endowment-draw-rate">
            endowment draw-rate recipe
          </Link>
          .
        </li>
      </ul>

      <h2>How to tell CDS from IPEDS on a school page</h2>
      <p>
        CDS lives on the year page and in the document ledger: a downloadable
        file, field IDs, an academic year in the URL. IPEDS lives in the
        “source-labeled federal facts” table: UNITID, source_table,
        source_variable, provisional or final. Scorecard is a third layer,
        with its own vintage note. If a row does not name its source, do not
        cite it.
      </p>
      <StoryFigure
        src="/about/virginia-tech-cds-and-ipeds-source-labels.svg"
        alt="Annotated split of a school page: Common Data Set extract with field IDs on one side, IPEDS source_table.source_variable on the other, both circled as separate source layers."
        caption="Virginia Tech school page, CDS extract versus IPEDS baseline. Source labels are the product. Harvey Mudd uses the same two-layer layout."
        href="/schools/virginia-tech"
        hrefLabel="Open Virginia Tech"
      />
      <p>
        Related:{" "}
        <Link href="/about/common-data-set">What is the Common Data Set</Link>
        {" · "}
        <Link href="/about/college-scorecard">
          College Scorecard, and why it is not a CDS
        </Link>
        .
      </p>
    </SourceStoryLayout>
  );
}
