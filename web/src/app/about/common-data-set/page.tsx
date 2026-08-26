import type { Metadata } from "next";
import Link from "next/link";
import {
  SourceStoryLayout,
  StoryTable,
} from "@/components/about/SourceStoryLayout";

const CANONICAL = "/about/common-data-set";
const TITLE = "What is the Common Data Set";
const DESCRIPTION =
  "The Common Data Set is the yearly report a college publishes on admissions, enrollment, cost, and aid. We archive those reports and make the numbers easy to use.";
const REVIEWED = "2026-08-26";

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
  datePublished: REVIEWED,
  dateModified: REVIEWED,
  author: { "@type": "Organization", name: "Bolewood Group", url: "https://bolewood.com" },
  publisher: { "@type": "Organization", name: "collegedata.fyi", url: "https://www.collegedata.fyi" },
  about: {
    "@type": "Organization",
    name: "Common Data Set Initiative",
    url: "https://commondataset.org/",
  },
  mainEntityOfPage: `https://www.collegedata.fyi${CANONICAL}`,
};

export default function CommonDataSetPage() {
  return (
    <SourceStoryLayout
      kicker="Common Data Set"
      title={<>What is the Common Data Set</>}
      lede="Colleges publish a yearly report of admissions, cost, and financial aid. It's called the Common Data Set. We keep those reports public and turn them into pages you can search, compare, and share."
      lastReviewed={REVIEWED}
      jsonLd={jsonLd}
    >
      <h2>What it is</h2>
      <p>
        In the late 1990s, schools and guidebook publishers agreed on one form
        so every college wasn&apos;t answering the same questions fifteen ways.
        The{" "}
        <a href="https://commondataset.org/" target="_blank" rel="noopener noreferrer">
          Common Data Set Initiative
        </a>{" "}
        still publishes that template. Filling it out is voluntary. There is no
        central filing cabinet. Each school posts a file, or doesn&apos;t.
      </p>

      <h2>What&apos;s in it</h2>
      <p>
        About a thousand comparable facts, in sections A through J.
      </p>
      <StoryTable
        caption="Common Data Set sections A through J"
        headers={["Section", "What it covers"]}
        rows={[
          ["A · General Information", "Name, calendar, degrees, respondent contact."],
          ["B · Enrollment and Persistence", "Headcount, race/ethnicity, retention, graduation rates."],
          ["C · First-time, first-year admission", "Applicants, admits, enrolled, tests, wait list, ED/EA."],
          ["D · Transfer admission", "Transfer funnel and requirements."],
          ["E · Academic offerings", "Special programs and policies."],
          ["F · Student life", "Housing, activities, percent in-state."],
          ["G · Annual expenses", "Tuition, fees, food and housing."],
          ["H · Financial aid", "Need and non-need packages, H2A merit counts."],
          ["I · Faculty and class size", "Student-faculty ratio, class-size bands."],
          ["J · Degrees conferred", "Disciplinary areas of degrees awarded."],
        ]}
      />

      <h2>How to use it here</h2>
      <ul>
        <li>
          Search a school, open a year, read the facts, download the original
          file.
        </li>
        <li>
          Counselors: send the year page, not a 47-page PDF. The official file
          is on the same page, so you aren&apos;t asking a family to trust a
          scrape.
        </li>
        <li>
          IR / researchers: the extract uses the template&apos;s field IDs; the{" "}
          <Link href="/api">API</Link> and{" "}
          <a
            href="https://github.com/bolewood/collegedata-fyi"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub repo
          </a>{" "}
          are the portable copy. Contribute a missing year from the school page.
        </li>
      </ul>

      <p>
        Harvey Mudd publishes a fillable 2025–26 file —{" "}
        <Link href="/schools/harvey-mudd/2025-26">open the year page</Link>.
        Virginia Tech&apos;s landing page asks you to email;{" "}
        <Link href="/schools/virginia-tech/2025-26">the file is public here</Link>.
      </p>

      <h2>We don&apos;t replace the school, or the feds</h2>
      <p>
        The numbers are the college&apos;s, as the school published them. We
        aren&apos;t{" "}
        <Link href="/about/ipeds">IPEDS</Link> and we aren&apos;t{" "}
        <Link href="/about/college-scorecard">College Scorecard</Link>. Those
        are different systems with different calendars. On this site they stay
        labeled.
      </p>
    </SourceStoryLayout>
  );
}
