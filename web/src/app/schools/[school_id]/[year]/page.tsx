import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  fetchDocumentsBySchoolAndYear,
  fetchExtract,
  fetchScorecardByIpedsId,
} from "@/lib/queries";
import type { FieldValue, ArtifactNotes } from "@/lib/types";
import { storageUrl, formatBadgeLabel } from "@/lib/format";
import { Badge } from "@/components/Badge";
import { KeyStats } from "@/components/KeyStats";
import { FieldsView } from "@/components/FieldsView";
import { MarkdownView } from "@/components/MarkdownView";
import { OutcomesBand } from "@/components/OutcomesBand";
import { ScorecardVintageNote } from "@/components/ScorecardVintageNote";

export const revalidate = 3600;

type Params = { school_id: string; year: string };

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { school_id, year } = await params;
  const docs = await fetchDocumentsBySchoolAndYear(school_id, year);

  if (docs.length === 0) return { title: "Document Not Found" };

  const doc = docs[0];
  const path = `/schools/${school_id}/${year}`;
  const title = `${doc.school_name} Common Data Set ${year}`;
  const description = `Common Data Set ${year} for ${doc.school_name}. Admissions, enrollment, financial aid, and more, extracted from the official CDS document.`;

  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: { url: path, title, description },
  };
}

export default async function SchoolYearPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { school_id, year } = await params;
  const docs = await fetchDocumentsBySchoolAndYear(school_id, year);

  if (docs.length === 0) {
    notFound();
  }

  // Scorecard is per-school, not per-year — pull once at the page level
  // and render under KeyStats in each document variant.
  const ipedsId = docs.find((d) => d.ipeds_id)?.ipeds_id ?? null;
  const scorecard = await fetchScorecardByIpedsId(ipedsId);

  const schoolName = docs[0].school_name;

  const canonicalUrl = `https://www.collegedata.fyi/schools/${school_id}/${year}`;
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "Dataset",
      name: `${schoolName} Common Data Set ${year}`,
      description: `Common Data Set ${year} for ${schoolName}, containing admissions, enrollment, financial aid, and other institutional data.`,
      url: canonicalUrl,
      creator: { "@type": "Organization", name: schoolName },
      temporalCoverage: year,
      license: "https://opensource.org/licenses/MIT",
      isAccessibleForFree: true,
      provider: {
        "@type": "Organization",
        name: "collegedata.fyi",
        url: "https://www.collegedata.fyi",
      },
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Schools", item: "https://www.collegedata.fyi/schools" },
        { "@type": "ListItem", position: 2, name: schoolName, item: `https://www.collegedata.fyi/schools/${school_id}` },
        { "@type": "ListItem", position: 3, name: year, item: canonicalUrl },
      ],
    },
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
        }}
      />
      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500 mb-4">
        <Link href="/schools" className="hover:text-gray-700">
          Schools
        </Link>
        {" / "}
        <Link
          href={`/schools/${school_id}`}
          className="hover:text-gray-700"
        >
          {schoolName}
        </Link>
        {" / "}
        <span className="text-gray-900">{year}</span>
      </nav>

      {/* Header */}
      <h1 className="text-3xl font-bold text-gray-900">{schoolName}</h1>
      <p className="text-xl text-gray-600 mt-1">Common Data Set {year}</p>

      {/* Render each document variant */}
      {docs.map((doc) => (
        <DocumentVariant
          key={doc.document_id}
          doc={doc}
          scorecard={scorecard}
        />
      ))}
    </div>
  );
}

async function DocumentVariant({
  doc,
  scorecard,
}: {
  doc: Awaited<ReturnType<typeof fetchDocumentsBySchoolAndYear>>[number];
  scorecard: Awaited<ReturnType<typeof fetchScorecardByIpedsId>>;
}) {
  const pdfUrl = storageUrl(doc.source_storage_path);
  const isExtracted = doc.extraction_status === "extracted";

  let values: Record<string, FieldValue> = {};
  let totalFields: number | undefined;
  let markdown: string | undefined;

  if (isExtracted && doc.document_id) {
    const { canonical, mergedValues } = await fetchExtract(doc.document_id);
    const notes = canonical?.notes as ArtifactNotes | null;
    values = mergedValues;
    totalFields = notes?.stats?.total_fields;
    markdown = notes?.markdown ?? undefined;
  }

  const hasValues = Object.keys(values).length > 0;

  return (
    <div className="mt-8">
      {/* Sub-institutional label */}
      {doc.sub_institutional && (
        <h2 className="text-lg font-semibold text-gray-800 mb-2">
          {doc.sub_institutional}
        </h2>
      )}

      {/* Meta */}
      <div className="flex items-center gap-3 flex-wrap">
        {doc.source_format && (
          <Badge
            label={formatBadgeLabel(doc.source_format)}
            className="bg-gray-100 text-gray-700"
          />
        )}
        {pdfUrl && (
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            Download source PDF
          </a>
        )}
      </div>

      {/* Key stats */}
      {hasValues && (
        <div className="mt-4">
          <KeyStats values={values} />
        </div>
      )}

      {/* Federal outcomes — Scorecard data. Only render under the first
          document variant; for schools with sub-institutional variants, the
          Scorecard data is IPEDS-level and identical across them. */}
      {scorecard && !doc.sub_institutional && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-900">
            Federal outcomes
          </h2>
          <ScorecardVintageNote scorecard={scorecard} className="mt-1" />
          <div className="mt-3">
            <OutcomesBand scorecard={scorecard} />
          </div>
        </div>
      )}

      {/* Full fields */}
      {hasValues ? (
        <div className="mt-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            All Extracted Fields
          </h3>
          <FieldsView values={values} totalFields={totalFields} />
        </div>
      ) : isExtracted ? (
        <div className="mt-4 rounded-lg border border-gray-200 p-6 text-center text-gray-500">
          <p>No structured field values available for this document yet.</p>
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-yellow-200 bg-yellow-50 p-6 text-center text-yellow-800">
          <p>
            Structured data coming soon. The source PDF is available for
            download above.
          </p>
        </div>
      )}

      {/* Docling source markdown */}
      {markdown && (
        <MarkdownView
          markdown={markdown}
          schoolName={doc.school_name ?? "School"}
          year={doc.canonical_year ?? "unknown"}
        />
      )}
    </div>
  );
}
