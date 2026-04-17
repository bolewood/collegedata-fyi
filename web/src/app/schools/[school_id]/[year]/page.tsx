import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  fetchDocumentBySchoolAndYear,
  fetchCanonicalArtifact,
} from "@/lib/queries";
import type { FieldValue } from "@/lib/types";
import { storageUrl, formatBadgeLabel } from "@/lib/format";
import { Badge } from "@/components/Badge";
import { KeyStats } from "@/components/KeyStats";
import { FieldsView } from "@/components/FieldsView";

export const revalidate = 3600;

type Params = { school_id: string; year: string };

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { school_id, year } = await params;
  const doc = await fetchDocumentBySchoolAndYear(school_id, year);

  if (!doc) return { title: "Document Not Found" };

  return {
    title: `${doc.school_name} Common Data Set ${year}`,
    description: `Common Data Set ${year} for ${doc.school_name}. Admissions, enrollment, financial aid, and more, extracted from the official CDS document.`,
  };
}

export default async function SchoolYearPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { school_id, year } = await params;
  const doc = await fetchDocumentBySchoolAndYear(school_id, year);

  if (!doc) {
    notFound();
  }

  const pdfUrl = storageUrl(doc.source_storage_path);
  const isExtracted = doc.extraction_status === "extracted";

  let artifact = null;
  let values: Record<string, FieldValue> = {};
  let totalFields: number | undefined;

  if (isExtracted && doc.latest_canonical_artifact_id) {
    artifact = await fetchCanonicalArtifact(doc.document_id);
    if (artifact?.notes?.values) {
      values = artifact.notes.values;
    }
    totalFields = artifact?.notes?.stats?.total_fields;
  }

  const hasValues = Object.keys(values).length > 0;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: `${doc.school_name} Common Data Set ${year}`,
    description: `Common Data Set ${year} for ${doc.school_name}, containing admissions, enrollment, financial aid, and other institutional data.`,
    url: `https://collegedata.fyi/schools/${school_id}/${year}`,
    creator: { "@type": "Organization", name: doc.school_name },
    temporalCoverage: year,
    license: "https://opensource.org/licenses/MIT",
    isAccessibleForFree: true,
    provider: {
      "@type": "Organization",
      name: "collegedata.fyi",
      url: "https://collegedata.fyi",
    },
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
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
          {doc.school_name}
        </Link>
        {" / "}
        <span className="text-gray-900">{year}</span>
      </nav>

      {/* Header */}
      <h1 className="text-3xl font-bold text-gray-900">
        {doc.school_name}
      </h1>
      <p className="text-xl text-gray-600 mt-1">
        Common Data Set {year}
      </p>

      {/* Meta */}
      <div className="flex items-center gap-3 mt-3 flex-wrap">
        {doc.source_format && (
          <Badge
            label={formatBadgeLabel(doc.source_format)}
            className="bg-gray-100 text-gray-700"
          />
        )}
        {doc.sub_institutional && (
          <span className="text-sm text-gray-500">
            {doc.sub_institutional}
          </span>
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
        <div className="mt-8">
          <KeyStats values={values} />
        </div>
      )}

      {/* Full fields */}
      {hasValues ? (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            All Extracted Fields
          </h2>
          <FieldsView values={values} totalFields={totalFields} />
        </div>
      ) : isExtracted ? (
        <div className="mt-8 rounded-lg border border-gray-200 p-6 text-center text-gray-500">
          <p>No structured field values available for this document yet.</p>
        </div>
      ) : (
        <div className="mt-8 rounded-lg border border-yellow-200 bg-yellow-50 p-6 text-center text-yellow-800">
          <p>Structured data coming soon. The source PDF is available for download above.</p>
        </div>
      )}
    </div>
  );
}
