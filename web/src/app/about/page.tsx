import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description:
    "The story behind collegedata.fyi, an open-source archive of U.S. college Common Data Set documents.",
  alternates: { canonical: "/about" },
  openGraph: { url: "/about" },
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12" style={{ color: "var(--ink-2)" }}>
      <h1
        style={{
          fontFamily: "var(--serif)",
          fontWeight: 400,
          fontSize: 48,
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
          margin: 0,
        }}
      >
        The <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>Uncommon</span> Data Set
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

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
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

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
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

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          What we built
        </h2>

        <p>
          <strong style={{ fontWeight: 600, color: "var(--ink)" }}>collegedata.fyi</strong>{" "}
          is the index. We discover each school&apos;s CDS document, archive the
          source file, map what we can into the CDS Initiative&apos;s own
          canonical 1,105-field schema, and expose the result as a queryable
          API.
        </p>

        <p>The pipeline has five stages:</p>

        <ol className="ml-6 list-decimal space-y-2 marker:text-gray-400">
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Schema pipeline</strong>{" "}
            extracts the canonical field definitions from the official XLSX
            template.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Corpus pipeline</strong>{" "}
            builds the school list from IPEDS data and probes for CDS landing
            pages.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Discovery pipeline</strong>{" "}
            crawls IR pages and archives source files to storage.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Extraction pipeline</strong>{" "}
            routes each document to a format-specific extractor: filled XLSX
            workbooks via the CDS template&apos;s own cell map, fillable PDFs
            via AcroForm, flattened PDFs via Docling with a schema-targeting
            cleaner, and scanned image PDFs via OCR.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Consumer pipeline</strong>{" "}
            exposes everything through a public REST API.
          </li>
        </ol>

        <p>
          The important caveat is that these formats do not all extract with
          the same reliability. Filled XLSX files and true fillable PDFs are
          comparatively structured, so they map cleanly. Flattened PDFs are
          much harder: once the form fields are gone, we have to reconstruct
          the template from layout and text alone.
        </p>

        <p>
          In practice that means year-specific cleaners. We build parsers for
          the recurring table shapes and labels used by each CDS template
          vintage, then keep refining them as we audit more schools. The
          output is useful today, but it is not perfect, especially on
          flattened PDFs, and some fields will improve as the cleaners get
          better.
        </p>

        <p>
          That&apos;s also why every school-year page links back to the original
          source document. The structured extract is there to make the corpus
          searchable and comparable; the PDF remains the ground truth.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
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
              style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
              href="https://github.com/bolewood/collegedata-fyi"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub repository
            </a>
          </li>
          <li>
            <a
              style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
              href="/api"
            >
              Public API
            </a>
          </li>
          <li>
            <a
              style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
              href="https://commondataset.org/"
              target="_blank"
              rel="noopener noreferrer"
            >
              CDS Initiative
            </a>{" "}
            (the original template publisher)
          </li>
        </ul>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>Credits</h2>

        <p>
          Built on{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://supabase.com"
            target="_blank"
            rel="noopener noreferrer"
          >
            Supabase
          </a>{" "}
          (Postgres, Edge Functions, Storage). Extraction powered by{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://github.com/DS4SD/docling"
            target="_blank"
            rel="noopener noreferrer"
          >
            Docling
          </a>{" "}
          for flattened PDFs.{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://reducto.ai"
            target="_blank"
            rel="noopener noreferrer"
          >
            Reducto
          </a>{" "}
          reference extracts used as a quality benchmark.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          Project Sponsors
        </h2>

        <p>collegedata.fyi is supported by:</p>

        <ul className="ml-6 list-disc space-y-2 marker:text-gray-400">
          <li>
            <a
              style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
              href="https://bolewood.com"
              target="_blank"
              rel="noopener noreferrer"
            >
              Bolewood Group
            </a>
          </li>
        </ul>

        <div style={{ marginTop: 40, borderTop: "1px solid var(--rule)", paddingTop: 24, fontSize: 13, fontStyle: "italic", fontFamily: "var(--serif)", color: "var(--ink-3)" }}>
          The &ldquo;Common&rdquo; in Common Data Set is doing a lot of work.
          We&apos;re doing the rest.
        </div>
      </div>
    </div>
  );
}
