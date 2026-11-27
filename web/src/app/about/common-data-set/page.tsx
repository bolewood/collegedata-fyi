import { REPO_URL } from "@/lib/repo";
import type { Metadata } from "next";
import Link from "next/link";
import {
  SourceStoryLayout,
  StoryTable,
} from "@/components/about/SourceStoryLayout";
import { SITE_NAME, SITE_ORIGIN } from "@/lib/site";

const CANONICAL = "/about/common-data-set";
const TITLE = "What is the Common Data Set";
const DESCRIPTION =
  "The Common Data Set is the annual report U.S. colleges publish on admissions, enrollment, cost, and financial aid. Here is what it covers and how to use it.";
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
  datePublished: "2026-08-26",
  dateModified: REVIEWED,
  author: { "@type": "Organization", name: "Bolewood Group", url: "https://bolewood.com" },
  publisher: { "@type": "Organization", name: SITE_NAME, url: SITE_ORIGIN },
  about: {
    "@type": "Organization",
    name: "Common Data Set Initiative",
    url: "https://commondataset.org/",
  },
  mainEntityOfPage: `${SITE_ORIGIN}${CANONICAL}`,
};

export default function CommonDataSetPage() {
  return (
    <SourceStoryLayout
      kicker="Common Data Set"
      title={<>What is the Common Data Set</>}
      lede="Every year, hundreds of U.S. colleges publish a standardized report covering admissions, enrollment, costs, and financial aid. It's called the Common Data Set. We archive those files and turn them into searchable pages you can compare and share."
      lastReviewed={REVIEWED}
      jsonLd={jsonLd}
    >
      <h2>What it is</h2>
      <p>
        In the late 1990s, schools and guidebook publishers agreed on one form
        so every college wasn't answering the same questions fifteen ways.
        The{" "}
        <a href="https://commondataset.org/" target="_blank" rel="noopener noreferrer">
          Common Data Set Initiative
        </a>{" "}
        still publishes that template. Filling it out is voluntary, and there is
        no central federal repository. Each college decides whether and where to
        post its own file.
      </p>

      <h2>What's in it</h2>
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
          Families and students: search a school to see its latest admissions,
          test-score, and aid numbers, with the college's original file
          linked on the same page.
        </li>
        <li>
          Counselors: send the year page, not a 47-page PDF. The official file
          is on the same page, so you aren't asking a family to trust a
          scrape.
        </li>
        <li>
          IR / researchers: the dataset preserves the template's official
          field IDs; the <Link href="/api">API</Link> and{" "}
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub repo
          </a>{" "}
          are the portable copy. Contribute a missing year from the school page.
        </li>
      </ul>

      <h2>How it relates to federal data</h2>
      <p>
        Every Common Data Set number on this site comes directly from the
        college, as the school published it. We display it alongside federal
        data from <Link href="/about/ipeds">IPEDS</Link> and{" "}
        <Link href="/about/college-scorecard">College Scorecard</Link>, which
        run on different calendars and definitions, and we keep each source
        clearly labeled.
      </p>
    </SourceStoryLayout>
  );
}
