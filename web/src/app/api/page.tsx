import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "API",
  description:
    "Public REST API for the collegedata.fyi Common Data Set archive. PostgREST endpoints, anon key, and example queries.",
  alternates: { canonical: "/api" },
  openGraph: { url: "/api" },
};

const ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlzZHV3bXlndm1kb3pocHZ6YWl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDk3NTksImV4cCI6MjA5MTY4NTc1OX0.fYZOIHyrOWzidgc-CVxWCY5Fe9pQk12-6YjDIS6y9qs";

const BASE = "https://api.collegedata.fyi";

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="mt-2 overflow-x-auto rounded border border-gray-200 bg-gray-50 px-4 py-3 text-xs leading-relaxed text-gray-800">
      <code>{children}</code>
    </pre>
  );
}

export default function ApiDocsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12 text-gray-800">
      <h1 className="text-3xl font-bold text-gray-900">API</h1>
      <p className="mt-3 text-base leading-relaxed text-gray-600">
        The full collegedata.fyi corpus is exposed as a public, read-only{" "}
        <a
          className="text-blue-700 underline hover:text-blue-900"
          href="https://postgrest.org/"
          target="_blank"
          rel="noopener noreferrer"
        >
          PostgREST
        </a>{" "}
        API at{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-sm">{BASE}</code>
        . Every page on this site is built from the same endpoints documented
        below.
      </p>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        Authentication
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        All requests require a Supabase{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">anon</code>{" "}
        key passed as both an{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">apikey</code>{" "}
        query parameter and an{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
          Authorization
        </code>{" "}
        bearer header. The anon key is public and grants read-only access to
        the published views below.
      </p>
      <CodeBlock>{ANON_KEY}</CodeBlock>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        Resources
      </h2>

      <div className="mt-4 space-y-6">
        <Resource
          name="cds_manifest"
          description="One row per archived CDS document. Joins schools, source URLs, format detection, and extraction status. Carries ipeds_id so federal-data joins are one query away."
          fields={[
            "school_id",
            "school_name",
            "ipeds_id",
            "canonical_year",
            "source_format",
            "source_url",
            "storage_path",
            "extraction_status",
            "data_quality_flag",
          ]}
        />
        <Resource
          name="cds_artifacts"
          description="Extracted field values keyed by canonical CDS question number (e.g. B.101). The notes JSON column holds { values: { 'B.101': { value, value_decoded, question, section, ... } } }."
          fields={[
            "document_id",
            "kind",
            "producer",
            "notes",
            "created_at",
          ]}
        />
        <Resource
          name="cds_documents"
          description="Raw archive table — one row per (school, sub-institution, year). Most consumers should prefer cds_manifest."
          fields={[
            "id",
            "school_id",
            "cds_year",
            "detected_year",
            "participation_status",
            "source_sha256",
          ]}
        />
        <Resource
          name="cds_scorecard"
          description="CDS manifest left-joined with the federal College Scorecard. One row per archived CDS document with post-graduation earnings, debt, net price by income bracket, completion rate, and retention attached. Answers 'should I apply here, and what happens if I do?' in a single GET. Currently joined to Scorecard 2022-23."
          fields={[
            "school_name",
            "ipeds_id",
            "cds_year",
            "earnings_10yr_median",
            "median_debt_completers",
            "avg_net_price",
            "net_price_0_30k",
            "graduation_rate_6yr",
            "pell_grant_rate",
          ]}
        />
        <Resource
          name="scorecard_summary"
          description="Curated 41-column subset of the federal College Scorecard, one row per IPEDS UNITID (6,322 institutions — not just CDS-archived ones). Refreshed annually after each Scorecard release. For per-program earnings, race-stratified completion, or other Scorecard fields beyond the curated subset, query Scorecard directly."
          fields={[
            "ipeds_id",
            "school_name",
            "scorecard_data_year",
            "earnings_10yr_median",
            "median_debt_completers",
            "avg_net_price",
            "graduation_rate_6yr",
            "endowment_end",
          ]}
        />
      </div>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">Examples</h2>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        List the most recent year for every school
      </h3>
      <CodeBlock>{`curl '${BASE}/rest/v1/cds_manifest?select=school_id,school_name,canonical_year&order=canonical_year.desc&limit=10' \\
  -H 'apikey: ${ANON_KEY.slice(0, 24)}…' \\
  -H 'Authorization: Bearer ${ANON_KEY.slice(0, 24)}…'`}</CodeBlock>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        Fetch all archived years for one school
      </h3>
      <CodeBlock>{`curl '${BASE}/rest/v1/cds_manifest?school_id=eq.harvard-university&select=canonical_year,source_format,extraction_status' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}</CodeBlock>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        Fetch extracted field values for a document
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        The <code>kind=eq.canonical</code> filter selects the deterministic
        extractor output. To merge in the LLM fallback gap-fill, also fetch
        rows with{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
          producer=eq.tier4_llm_fallback
        </code>{" "}
        and overlay the canonical values on top.
      </p>
      <CodeBlock>{`curl '${BASE}/rest/v1/cds_artifacts?document_id=eq.<uuid>&kind=eq.canonical&select=notes' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}</CodeBlock>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        JavaScript client
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        The same{" "}
        <a
          className="text-blue-700 underline hover:text-blue-900"
          href="https://github.com/supabase/supabase-js"
          target="_blank"
          rel="noopener noreferrer"
        >
          @supabase/supabase-js
        </a>{" "}
        client this site uses works against the public API:
      </p>
      <CodeBlock>{`import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  "${BASE}",
  "<anon key>"
);

const { data } = await supabase
  .from("cds_manifest")
  .select("school_name, canonical_year")
  .eq("extraction_status", "extracted")
  .limit(20);`}</CodeBlock>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        Source documents
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        Original CDS files are hosted on Supabase Storage. Once you have a
        manifest row, build the public URL as{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
          {BASE}/storage/v1/object/public/&lt;storage_path&gt;
        </code>
        . Every file is content-addressed by SHA-256.
      </p>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        Schema and licensing
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        Field IDs follow the canonical 1,105-field schema derived from the CDS
        Initiative&apos;s 2025-26 XLSX template. The full schema is checked
        into the repo at{" "}
        <a
          className="text-blue-700 underline hover:text-blue-900"
          href="https://github.com/bolewood/collegedata-fyi/blob/main/schemas"
          target="_blank"
          rel="noopener noreferrer"
        >
          schemas/
        </a>
        . The dataset is MIT-licensed; the underlying CDS documents are owned
        by their respective institutions and reproduced here under their
        public-document status.
      </p>

      <div className="mt-10 border-t border-gray-200 pt-6 text-sm text-gray-500">
        Found something missing or wrong? Open an issue on{" "}
        <a
          className="text-blue-700 underline hover:text-blue-900"
          href="https://github.com/bolewood/collegedata-fyi/issues"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
        , or browse the <Link href="/schools" className="text-blue-700 underline hover:text-blue-900">school directory</Link>.
      </div>
    </div>
  );
}

function Resource({
  name,
  description,
  fields,
}: {
  name: string;
  description: string;
  fields: string[];
}) {
  return (
    <div className="rounded border border-gray-200 p-4">
      <div className="flex items-baseline justify-between gap-3">
        <code className="text-sm font-semibold text-gray-900">
          GET /rest/v1/{name}
        </code>
        <a
          href={`${BASE}/rest/v1/${name}?limit=1&apikey=${ANON_KEY}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-700 underline hover:text-blue-900"
        >
          try it →
        </a>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        {description}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {fields.map((f) => (
          <code
            key={f}
            className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700"
          >
            {f}
          </code>
        ))}
      </div>
    </div>
  );
}
