import type { Metadata } from "next";
import Link from "next/link";
import {
  SOURCE_STORY_REVIEWED,
  SourceStoryLayout,
  StoryFigure,
  StoryTable,
} from "@/components/about/SourceStoryLayout";

const CANONICAL = "/about/common-data-set";
const TITLE = "What is the Common Data Set";
const DESCRIPTION =
  "The Common Data Set is a voluntary 47-page school-authored form, not a database. How the template works, why publishing is a mess, and what collegedata.fyi extracts.";

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
    name: "Common Data Set Initiative",
    url: "https://commondataset.org/",
  },
  mainEntityOfPage: `https://www.collegedata.fyi${CANONICAL}`,
};

export default function CommonDataSetPage() {
  return (
    <SourceStoryLayout
      kicker="Common Data Set"
      title={
        <>
          What is the Common Data Set
        </>
      }
      lede="A 47-page PDF on a random institutional-research URL is not a data system. It is a print form that three guidebook publishers asked schools to fill in once."
      jsonLd={jsonLd}
    >
      <h2>The CDS Initiative</h2>
      <p>
        In the late 1990s the College Board, Peterson&apos;s, and U.S. News sat
        down with college institutional-research offices and agreed on one
        template. The point was to stop asking every school for the same
        enrollment, admissions, and aid numbers in fifteen slightly different
        shapes. The{" "}
        <a href="https://commondataset.org/" target="_blank" rel="noopener noreferrer">
          Common Data Set Initiative
        </a>{" "}
        still publishes that template. It is currently a 47-page workbook with
        1,105 fields and an Answer Sheet tab.
      </p>
      <p>
        Participation is voluntary. There is no federal mandate, no central
        filing cabinet, and no API. Each school posts a file on its own
        website, or does not.
      </p>

      <h2>Sections A–J, in English</h2>
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

      <h2>A fillable PDF is the easy case</h2>
      <p>
        Harvey Mudd College still publishes the{" "}
        <Link href="/schools/harvey-mudd/2025-26">
          2025-26 Common Data Set
        </Link>{" "}
        as an unflattened fillable PDF. Named AcroForm fields carry the
        canonical tags from the template. <code>AP_RECD_1ST_MEN_N</code> is
        3,452. That is a 200-millisecond <code>pypdf.get_fields()</code>{" "}
        extract, not a model guess. See{" "}
        <Link href="/schools/harvey-mudd">the Harvey Mudd archive</Link>.
      </p>
      <StoryFigure
        src="/about/harvey-mudd-2025-26-c1-fillable.svg"
        alt="Harvey Mudd College Common Data Set 2025-26 section C1, showing named AcroForm tags such as AP_RECD_1ST_MEN_N with value 3,452 from the fillable PDF."
        caption="Harvey Mudd College, Common Data Set 2025-26, archived fillable PDF CDS-HMC-2025.2026_shared.pdf, section C1. Values are AcroForm field contents."
        href="/schools/harvey-mudd/2025-26"
        hrefLabel="Open the 2025-26 year page"
      />

      <h2>Point the wrong extractor at that file and C1 shifts</h2>
      <p>
        The same kind of table, after a layout parser has flattened it, is why
        this archive exists as software and not as a folder of PDFs. Docling
        on the Harvey Mudd fillable file collapsed C1 so men-applied became
        “3452 1761” and women-applied became “4”. Kerned year numerals read
        as “202 5 -202 6”. The running header printed “Common Data Set
        2025-2026” as a heading five times. That is documented in
        <code> docs/known-issues/harvey-mudd-2025-26.md</code>. The live
        extract is the AcroForm path. The Docling notes are what happens if
        you pick the wrong tool.
      </p>
      <StoryFigure
        src="/about/harvey-mudd-2025-26-c1-docling-shift.svg"
        alt="Docling misread of Harvey Mudd 2025-26 C1, with applicant counts shifted into the wrong rows, shown as a warning rather than the live extract."
        caption="Harvey Mudd College, Common Data Set 2025-26, same archived PDF. This figure is the historical Docling misread of C1, not the live extract."
        href="/schools/harvey-mudd/2025-26"
        hrefLabel="Open the year page whose live extract is correct"
      />
      <StoryFigure
        src="/about/harvey-mudd-2025-26-page-header.svg"
        alt="The phrase Common Data Set 2025-2026 repeated five times as a running page header from the Harvey Mudd fillable PDF."
        caption="Harvey Mudd College, Common Data Set 2025-26, archived fillable PDF. The repeating header is print chrome. The document is a form, not a database."
        href="/schools/harvey-mudd/2025-26"
      />

      <h2>Virginia Tech publishes XLSX and hides the index</h2>
      <p>
        Virginia Tech&apos;s{" "}
        <Link href="/schools/virginia-tech/2025-26">
          2025-26 Common Data Set
        </Link>{" "}
        is an Excel workbook — the theoretically ideal format. The school&apos;s
        own page at{" "}
        <a
          href="https://aie.vt.edu/analytics-and-ai/common-data-set.html"
          target="_blank"
          rel="noopener noreferrer"
        >
          aie.vt.edu
        </a>{" "}
        explains what a CDS is, then says files are available via request to
        aiesupport@vt.edu. The PDFs and workbooks exist on a DAM path. The
        landing page is a dead end.{" "}
        <Link href="/schools/virginia-tech">The Virginia Tech archive</Link>{" "}
        is the public HTML that actually hands over the extract.
      </p>
      <StoryFigure
        src="/about/virginia-tech-2025-26-xlsx-and-email-gate.svg"
        alt="Virginia Tech 2025-26 Common Data Set Excel answer sheet beside the official IR page text that asks the public to email aiesupport@vt.edu for the file."
        caption="Virginia Tech, Common Data Set 2025-26, archived XLSX, next to the school’s own CDS page (email request). Applied total in the 2025-26 extract: 57,755."
        href="/schools/virginia-tech/2025-26"
        hrefLabel="Open the Virginia Tech 2025-26 year page"
      />

      <h2>The publishing mess</h2>
      <p>
        Schools do not publish one way. In this archive we already have, as
        real files:
      </p>
      <ul>
        <li>Unflattened fillable PDFs (Harvey Mudd 2025-26).</li>
        <li>Flattened PDFs where the form structure is gone.</li>
        <li>Image-only scans with almost no extractable text.</li>
        <li>XLSX workbooks (Virginia Tech 2025-26).</li>
        <li>DOCX uploads of the Word template.</li>
        <li>HTML pages, some of them JS-only.</li>
        <li>Box, SharePoint, Google Drive, and Digital Commons item pages.</li>
        <li>
          URLs whose path year is a CMS upload month, not the academic year.
        </li>
        <li>Section-only files, blank templates, and “test” uploads that are the real file.</li>
      </ul>
      <p>
        None of that is a data system. It is a distributed print workflow
        that happens to use a shared template. Stanford&apos;s{" "}
        <Link href="/schools/stanford/2017-18">2017-18 year page</Link> is
        already a used URL: historical files convert when the school no
        longer lists them.
      </p>

      <h2>What “extracted” means here</h2>
      <p>
        Extracted means: canonical field IDs such as C.101 and H.2A, values
        with provenance back to the archived bytes, and a spreadsheet
        download of those fields. It does not mean we are the publisher. The
        numbers are the school&apos;s. The year page links the archived original
        and, when we have a usable HTML URL, the school&apos;s own CDS page.
      </p>
      <p>
        For a counselor: send the year page, not a 47-page PDF, and keep the
        official link in the same paragraph so you are not vouching for a
        scrape.
      </p>

      <h2>What we are not</h2>
      <p>
        Not the publisher. Not{" "}
        <Link href="/about/ipeds">IPEDS</Link>. Not{" "}
        <Link href="/about/college-scorecard">College Scorecard</Link>. Those
        are different systems with different mandates, lags, and field
        definitions. This page is the school-authored form, archived and
        extracted.
      </p>
    </SourceStoryLayout>
  );
}
