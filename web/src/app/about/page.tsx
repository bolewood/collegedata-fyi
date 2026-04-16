import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About",
  description:
    "The story behind collegedata.fyi, an open-source archive of U.S. college Common Data Set documents.",
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-bold text-gray-900">
        The Uncommon Data Set
      </h1>

      <div className="mt-8 prose prose-gray max-w-none">
        <p>
          The Common Data Set is a beautiful idea. Twenty-seven years ago, three
          college-guide publishers, the College Board, Peterson&apos;s, and U.S.
          News, sat down with a bunch of college institutional research offices
          and agreed on a single template for reporting the numbers that matter
          about a school. Enrollment. Admissions. Retention. Tuition. Financial
          aid. Faculty.
        </p>

        <p>
          The CDS Initiative still publishes that template today. It is a 47-page
          XLSX with 1,105 fields. It has a beautifully structured Answer Sheet
          tab. It is, genuinely, one of the cleanest open data standards in
          American higher education.
        </p>

        <p>The name is &ldquo;Common Data Set.&rdquo;</p>

        <p>The reality is extremely uncommon.</p>

        <h2>What we found</h2>

        <p>
          Schools publish their CDS in every format imaginable: fillable PDFs
          where every answer lives in a named form field (14% of the corpus),
          flattened PDFs where the form structure has been destroyed (84%),
          scanned images, XLSX files, DOCX files, HTML pages behind JavaScript
          frameworks, Box embeds, SharePoint pages, and Google Drive shares.
        </p>

        <p>
          One school hosts their CDS on a Bepress Digital Commons page that
          intercepts scrapers with a 202 Accepted response and an empty body.
          Another has a &ldquo;test draft&rdquo; at a URL that is actually the
          real production file. Two different schools shared the same physical
          file via a common Google Drive link.
        </p>

        <p>
          None of this is malicious. It&apos;s what happens when you release a
          beautiful canonical template into a distributed system of 800+
          institutional research offices, each with their own webmaster, CMS,
          and IT policies. Over twenty years, the drift is cumulative.
        </p>

        <h2>What we built</h2>

        <p>
          <strong>collegedata.fyi</strong> is the index. We discover each
          school&apos;s CDS document, archive the source file immediately
          (SHA-addressed, preserved forever), extract the numbers into the CDS
          Initiative&apos;s own canonical 1,105-field schema, and expose the
          result as a queryable API.
        </p>

        <p>The pipeline has five stages:</p>

        <ol>
          <li>
            <strong>Schema pipeline</strong> extracts the canonical field
            definitions from the official XLSX template
          </li>
          <li>
            <strong>Corpus pipeline</strong> builds the school list from IPEDS
            data and probes for CDS landing pages
          </li>
          <li>
            <strong>Discovery pipeline</strong> crawls IR pages, archives source
            files to storage
          </li>
          <li>
            <strong>Extraction pipeline</strong> routes each document to a
            format-specific extractor (fillable PDFs via AcroForm, flat PDFs via
            Docling)
          </li>
          <li>
            <strong>Consumer pipeline</strong> exposes everything through a
            public REST API
          </li>
        </ol>

        <h2>Open source</h2>

        <p>
          The entire project is open source under the MIT license. The code,
          the schema, the extraction pipeline, and the archived documents are
          all public.
        </p>

        <ul>
          <li>
            <a
              href="https://github.com/bolewood/collegedata-fyi"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub repository
            </a>
          </li>
          <li>
            <a
              href="https://api.collegedata.fyi/rest/v1/"
              target="_blank"
              rel="noopener noreferrer"
            >
              Public API
            </a>
          </li>
          <li>
            <a
              href="https://commondataset.org/"
              target="_blank"
              rel="noopener noreferrer"
            >
              CDS Initiative
            </a>{" "}
            (the original template publisher)
          </li>
        </ul>

        <h2>Credits</h2>

        <p>
          Built on{" "}
          <a
            href="https://supabase.com"
            target="_blank"
            rel="noopener noreferrer"
          >
            Supabase
          </a>{" "}
          (Postgres, Edge Functions, Storage). Extraction powered by{" "}
          <a
            href="https://github.com/DS4SD/docling"
            target="_blank"
            rel="noopener noreferrer"
          >
            Docling
          </a>{" "}
          for flattened PDFs.{" "}
          <a
            href="https://reducto.ai"
            target="_blank"
            rel="noopener noreferrer"
          >
            Reducto
          </a>{" "}
          reference extracts used as a quality benchmark.
        </p>

        <div className="mt-8 pt-8 border-t border-gray-200">
          <p className="text-sm text-gray-500">
            The &ldquo;Common&rdquo; in Common Data Set is doing a lot of work.
            We&apos;re doing the rest.
          </p>
        </div>
      </div>
    </div>
  );
}
