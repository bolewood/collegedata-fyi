import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description:
    "The story behind collegedata.fyi, an open-source archive of U.S. college Common Data Set documents with source-labeled federal baseline facts.",
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
          Choosing a college should not require stitching together a dozen
          tabs, a spreadsheet, a federal database, and a commercial search
          product just to answer basic questions.
        </p>

        <p>
          The good news is that a lot of the data already exists. Colleges
          publish{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://commondataset.org/"
            target="_blank"
            rel="noopener noreferrer"
          >
            Common Data Set
          </a>{" "}
          files. The Department of Education publishes{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://collegescorecard.ed.gov/"
            target="_blank"
            rel="noopener noreferrer"
          >
            College Scorecard
          </a>{" "}
          and{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://nces.ed.gov/ipeds/"
            target="_blank"
            rel="noopener noreferrer"
          >
            IPEDS
          </a>{" "}
          data. The hard part is that none of those sources, by itself, gives
          families a simple, current, trustworthy way to browse the college
          landscape.
        </p>

        <p>
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://nces.ed.gov/"
            target="_blank"
            rel="noopener noreferrer"
          >
            NCES
          </a>{" "}
          is the Department of Education&apos;s statistical center, and IPEDS is
          its core postsecondary data system for institution-reported federal
          data.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          The problem
        </h2>

        <p>
          Common Data Set files are excellent, but scattered. They show up on
          school websites in many formats, on different timetables, under
          different URLs, and only a minority of the 3,000+ in-scope
          undergraduate institutions publish a current public CDS that is easy
          to find.
        </p>

        <p>
          College Scorecard is useful, especially for outcomes like net price,
          debt, completion, and earnings, but it is not a substitute for the
          richer admissions and aid details schools publish in the CDS.
        </p>

        <p>
          IPEDS is powerful and broad, but federal releases lag the freshest
          school-published files, and the official tools can be hard to navigate
          unless you already know the survey components, table names, and Access
          database workflow.
        </p>

        <p>
          And if you want enriched data, the default option has often been a
          proprietary vendor platform. Those tools can be useful, but they may
          require accounts, hide their source lineage, limit API access, or
          create another student-data profile along the way.
        </p>

        <p>
          So the gap was not &ldquo;does college data exist?&rdquo; The gap was:
          where can a student, parent, counselor, journalist, or builder browse
          the freshest school-published facts, federal baseline data, source
          links, and an open API in one place?
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          What you can do now
        </h2>

        <p>
          <strong style={{ fontWeight: 600, color: "var(--ink)" }}>collegedata.fyi</strong>{" "}
          is a public college-data browser built around source transparency.
          Search for a school, see whether we found a public CDS, inspect the
          original source file, read extracted fields, and compare key facts
          across schools without creating an account.
        </p>

        <ul className="ml-6 list-disc space-y-2 marker:text-gray-400">
          <li>
            Find a school&apos;s latest archived Common Data Set and download the
            original PDF, XLSX, DOCX, or HTML source.
          </li>
          <li>
            Browse extracted admissions, enrollment, test-score, aid, and
            academic fields across schools.
          </li>
          <li>
            See source-labeled federal baseline facts for schools where no
            public CDS is archived.
          </li>
          <li>
            Use academic positioning, admission strategy, merit-aid, and match
            list tools without sending student profile data to a server.
          </li>
          <li>
            Query the same data through a public REST API for spreadsheets,
            research, dashboards, or your own tools.
          </li>
        </ul>

        <p>
          If you want starter ideas, the{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="/recipes"
          >
            Recipes
          </a>{" "}
          page has worked examples you can adapt.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          What makes it different
        </h2>

        <ol className="ml-6 list-decimal space-y-2 marker:text-gray-400">
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Fresh school-authored data first.</strong>{" "}
            When a current CDS exists, we treat it as the primary source for
            CDS-native fields.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Federal coverage where CDS is missing.</strong>{" "}
            NCES/IPEDS fills in source-labeled baseline facts for institutions
            that do not publish a public CDS.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Clear provenance.</strong>{" "}
            Values keep their source attached: CDS, IPEDS provisional/final, or
            Scorecard context. We do not blend them into one unlabeled number.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Accessible tables and durable links.</strong>{" "}
            Public pages prioritize readable, keyboard-friendly tables and link
            back to the original source documents.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Open API.</strong>{" "}
            The API is the same data surface the website uses, so researchers
            and builders do not have to scrape the site.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Privacy by default.</strong>{" "}
            The core site works without accounts. Student profile tools are
            local-first unless a future feature explicitly says otherwise.
          </li>
          <li>
            <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Built for everyday use.</strong>{" "}
            Pages are designed to be fast, readable, accessible, and stable
            enough for families, counselors, and builders to rely on.
          </li>
        </ol>

        <p>
          Structured extracts are useful, but source documents still matter.
          Every school-year page links back to the original file, and federal
          baseline rows keep enough source context to understand where a number
          came from and how it should be read.
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
          reference extracts used as a quality benchmark. Federal baseline
          facts come from official{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://nces.ed.gov/ipeds/"
            target="_blank"
            rel="noopener noreferrer"
          >
            NCES/IPEDS
          </a>{" "}
          releases.
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
          Better college decisions start with better access to the facts.
        </div>
      </div>
    </div>
  );
}
