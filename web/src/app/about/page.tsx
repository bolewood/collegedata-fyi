import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description:
    "The story behind collegedata.fyi, an open-source archive of U.S. college Common Data Set documents.",
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12 text-gray-800">
      <h1 className="text-3xl font-bold text-gray-900">
        The Uncommon Data Set
      </h1>

      <div className="mt-8 space-y-5 text-base leading-relaxed">
        <p>
          The Common Data Set is a beautiful idea. Almost thirty years ago,
          three college-guide publishers — the College Board, Peterson&apos;s,
          and U.S. News — sat down with a bunch of college institutional
          research offices and agreed on a single template for reporting the
          numbers that matter about a school: enrollment, admissions,
          retention, tuition, financial aid, faculty.
        </p>

        <p>
          The CDS Initiative still publishes that template today. It is a 47-page
          XLSX with 1,105 fields. It has a beautifully structured Answer Sheet
          tab. It is, genuinely, one of the cleanest open data standards in
          American higher education.
        </p>

        <p>The name is &ldquo;Common Data Set.&rdquo;</p>

        <p>The reality is extremely uncommon.</p>

        <h2 className="mt-10 text-xl font-semibold text-gray-900">
          What we found
        </h2>

        <p>
          Schools publish their CDS in every format imaginable: fillable PDFs
          where every answer lives in a named form field, flattened PDFs where
          the form structure has been destroyed, scanned images, filled XLSX
          workbooks, DOCX files, HTML pages behind JavaScript frameworks, Box
          embeds, SharePoint pages, and Google Drive shares.
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

        <h2 className="mt-10 text-xl font-semibold text-gray-900">
          Why we did this anyway
        </h2>

        <p>
          It started as a side project. I was building a college spreadsheet
          for my son and got tired of typing numbers from PDFs. The more I
          looked at the existing options, the more obvious it was that nobody
          had built the index this data deserves.
        </p>

        <p>
          We kept building because we think it&apos;s a public good. Students,
          parents, and counselors navigating college selection deserve direct,
          free access to the data colleges already publish about themselves,
          in a form that&apos;s actually queryable. For the past two decades
          that access has been mediated by commercial aggregators who package
          the same numbers and sell them back, sometimes for hundreds of
          dollars per seat.
        </p>

        <p>
          We also think colleges will appreciate having the infrastructure
          they didn&apos;t have to build themselves. The institutional research
          staff who painstakingly produce the CDS each year do so in PDF
          format, on their own websites, where the work is effectively
          invisible to anyone outside the institution until an aggregator
          picks it up. We give that work direct attribution and a much larger
          audience.
        </p>

        <p>
          The open-access version of this data will probably annoy the
          incumbent aggregators. We&apos;re fine with that.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-gray-900">
          What we built
        </h2>

        <p>
          <strong className="font-semibold text-gray-900">collegedata.fyi</strong>{" "}
          is the index. We discover each school&apos;s CDS document, archive the
          source file immediately (SHA-addressed, preserved forever), extract
          the numbers into the CDS Initiative&apos;s own canonical 1,105-field
          schema, and expose the result as a queryable API.
        </p>

        <p>The pipeline has five stages:</p>

        <ol className="ml-6 list-decimal space-y-2 marker:text-gray-400">
          <li>
            <strong className="font-semibold text-gray-900">Schema pipeline</strong>{" "}
            extracts the canonical field definitions from the official XLSX
            template.
          </li>
          <li>
            <strong className="font-semibold text-gray-900">Corpus pipeline</strong>{" "}
            builds the school list from IPEDS data and probes for CDS landing
            pages.
          </li>
          <li>
            <strong className="font-semibold text-gray-900">Discovery pipeline</strong>{" "}
            crawls IR pages and archives source files to storage.
          </li>
          <li>
            <strong className="font-semibold text-gray-900">Extraction pipeline</strong>{" "}
            routes each document to a format-specific extractor: filled XLSX
            workbooks via the CDS template&apos;s own cell map, fillable PDFs
            via AcroForm, flattened PDFs via Docling with a schema-targeting
            cleaner, and scanned image PDFs via OCR.
          </li>
          <li>
            <strong className="font-semibold text-gray-900">Consumer pipeline</strong>{" "}
            exposes everything through a public REST API.
          </li>
        </ol>

        <h2 className="mt-10 text-xl font-semibold text-gray-900">
          Open source
        </h2>

        <p>
          The entire project is open source under the MIT license. The code,
          the schema, the extraction pipeline, and the archived documents are
          all public.
        </p>

        <ul className="ml-6 list-disc space-y-2 marker:text-gray-400">
          <li>
            <a
              className="text-blue-700 underline hover:text-blue-900"
              href="https://github.com/bolewood/collegedata-fyi"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub repository
            </a>
          </li>
          <li>
            <a
              className="text-blue-700 underline hover:text-blue-900"
              href="/api"
            >
              Public API
            </a>
          </li>
          <li>
            <a
              className="text-blue-700 underline hover:text-blue-900"
              href="https://commondataset.org/"
              target="_blank"
              rel="noopener noreferrer"
            >
              CDS Initiative
            </a>{" "}
            (the original template publisher)
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-gray-900">Credits</h2>

        <p>
          Built on{" "}
          <a
            className="text-blue-700 underline hover:text-blue-900"
            href="https://supabase.com"
            target="_blank"
            rel="noopener noreferrer"
          >
            Supabase
          </a>{" "}
          (Postgres, Edge Functions, Storage). Extraction powered by{" "}
          <a
            className="text-blue-700 underline hover:text-blue-900"
            href="https://github.com/DS4SD/docling"
            target="_blank"
            rel="noopener noreferrer"
          >
            Docling
          </a>{" "}
          for flattened PDFs.{" "}
          <a
            className="text-blue-700 underline hover:text-blue-900"
            href="https://reducto.ai"
            target="_blank"
            rel="noopener noreferrer"
          >
            Reducto
          </a>{" "}
          reference extracts used as a quality benchmark.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-gray-900">
          Project Sponsors
        </h2>

        <p>collegedata.fyi is supported by:</p>

        <ul className="ml-6 list-disc space-y-2 marker:text-gray-400">
          <li>
            <a
              className="text-blue-700 underline hover:text-blue-900"
              href="https://bolewood.com"
              target="_blank"
              rel="noopener noreferrer"
            >
              Bolewood Group
            </a>
          </li>
        </ul>

        <div className="mt-10 border-t border-gray-200 pt-6 text-sm text-gray-500">
          The &ldquo;Common&rdquo; in Common Data Set is doing a lot of work.
          We&apos;re doing the rest.
        </div>
      </div>
    </div>
  );
}
