import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import {
  fetchDocumentsBySchoolAndYear,
  fetchAdmissionStrategyByDocumentId,
  fetchExtract,
  fetchScorecardByIpedsId,
  fetchCanonicalSchoolId,
} from "@/lib/queries";
import type { FieldValue, ArtifactNotes } from "@/lib/types";
import { storageUrl, formatBadgeLabel, sourceDownloadLabel } from "@/lib/format";
import { Badge } from "@/components/Badge";
import { KeyStats } from "@/components/KeyStats";
import { FieldsView } from "@/components/FieldsView";
import { MarkdownView } from "@/components/MarkdownView";
import { OutcomesBand } from "@/components/OutcomesBand";
import { ScorecardVintageNote } from "@/components/ScorecardVintageNote";
import { AdmissionStrategyCard } from "@/components/AdmissionStrategyCard";
import { SpreadsheetDownloadLinks } from "@/components/SpreadsheetDownloadLinks";
import { ArchiveLead } from "@/components/ArchiveLead";
import { yearArchiveLead } from "@/lib/archive-lead";

export const revalidate = 3600;

type Params = { school_id: string; year: string };

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { school_id, year } = await params;
  const resolvedSchoolId = (await fetchCanonicalSchoolId(school_id)) ?? school_id;
  const docs = await fetchDocumentsBySchoolAndYear(resolvedSchoolId, year);

  if (docs.length === 0) return { title: "Document Not Found" };

  const doc = docs[0];
  const path = `/schools/${resolvedSchoolId}/${year}`;
  const title = `${doc.school_name} Common Data Set ${year}`;
  const description =
    `View ${doc.school_name} Common Data Set ${year}: official source download plus extracted admissions, enrollment, SAT/ACT, financial aid, and field-level CDS data.`;

  return {
    title,
    description,
    alternates: {
      canonical: path,
      types: {
        "application/rss+xml": `/schools/${resolvedSchoolId}/feed.xml`,
      },
    },
    openGraph: { url: path, title, description },
  };
}

export default async function SchoolYearPage({ params }: {
  params: Promise<Params>;
}) {
  const { school_id, year } = await params;
  const canonicalSchoolId = await fetchCanonicalSchoolId(school_id);
  if (canonicalSchoolId && canonicalSchoolId !== school_id) {
    permanentRedirect(`/schools/${canonicalSchoolId}/${year}`);
  }
  const docs = await fetchDocumentsBySchoolAndYear(school_id, year);

  if (docs.length === 0) {
    notFound();
  }

  // Scorecard is per-school, not per-year — pull once at the page level
  // and render under KeyStats in each document variant.
  const ipedsId = docs.find((d) => d.ipeds_id)?.ipeds_id ?? null;
  const scorecard = await fetchScorecardByIpedsId(ipedsId);

  const schoolName = docs[0].school_name ?? "Unknown school";
  const yearLead = yearArchiveLead({
    schoolId: school_id,
    schoolName,
    year,
    ipedsId,
    hasExtract: docs.some((doc) => doc.extraction_status === "extracted"),
    sourceDownloadHref: storageUrl(docs[0]?.source_storage_path ?? null),
    source_modification_date: docs[0]?.source_modification_date,
    source_creation_date: docs[0]?.source_creation_date,
    source_http_last_modified: docs[0]?.source_http_last_modified,
    discovered_at: docs[0]?.discovered_at,
  });

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
      {/* Breadcrumb + year identity share the school plates with the overview. */}
      <header className="cd-school-header">
        <div>
          <nav className="mono" style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>
            <Link href="/schools">Schools</Link>
            {" / "}
            <Link href={`/schools/${school_id}`}>{schoolName}</Link>
            {" / "}
            <span>{year}</span>
          </nav>
          <h1
            className="serif"
            style={{
              fontWeight: 400,
              fontSize: "clamp(36px, 5vw, 52px)",
              margin: 0,
              letterSpacing: "-0.02em",
              lineHeight: 1,
            }}
          >
            {schoolName}
          </h1>
          <h2 className="serif" style={{ fontSize: 22, fontWeight: 400, margin: "10px 0 0" }}>
            {yearLead.heading}
          </h2>
        </div>
      </header>
      <ArchiveLead lead={yearLead} showHeading={false} />

      {/* Render each document variant. The spreadsheet download covers all
          variants in one workbook, so only the first variant shows links. */}
      {docs.map((doc, i) => (
        <DocumentVariant
          key={doc.document_id}
          doc={doc}
          scorecard={scorecard}
          showSpreadsheetLinks={i === 0}
        />
      ))}
    </div>
  );
}

async function DocumentVariant({
  doc,
  scorecard,
  showSpreadsheetLinks,
}: {
  doc: Awaited<ReturnType<typeof fetchDocumentsBySchoolAndYear>>[number];
  scorecard: Awaited<ReturnType<typeof fetchScorecardByIpedsId>>;
  showSpreadsheetLinks: boolean;
}) {
  const sourceDownloadUrl = storageUrl(doc.source_storage_path);
  const isExtracted = doc.extraction_status === "extracted";

  let values: Record<string, FieldValue> = {};
  let totalFields: number | undefined;
  let markdown: string | undefined;
  let schemaVersion: string | undefined;

  if (isExtracted && doc.document_id) {
    const { canonical, mergedValues } = await fetchExtract(doc.document_id);
    const notes = canonical?.notes as ArtifactNotes | null;
    values = mergedValues;
    totalFields = notes?.stats?.total_fields;
    markdown = notes?.markdown ?? undefined;
    schemaVersion = notes?.schema_version ?? doc.cds_year ?? undefined;
  }

  const hasValues = Object.keys(values).length > 0;
  const admissionStrategy = doc.document_id
    ? await fetchAdmissionStrategyByDocumentId(doc.document_id)
    : null;

  return (
    <div style={{ marginTop: 32 }}>
      {doc.sub_institutional && (
        <h2 className="serif" style={{ fontSize: 22, fontWeight: 400, margin: "0 0 8px" }}>
          {doc.sub_institutional}
        </h2>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        {doc.source_format && (
          <Badge
            label={formatBadgeLabel(doc.source_format)}
            className="bg-gray-100 text-gray-700"
          />
        )}
        {sourceDownloadUrl && (
          <a
            href={sourceDownloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mono"
            style={{ fontSize: 13 }}
          >
            {sourceDownloadLabel(doc.source_format, doc.source_storage_path)}
          </a>
        )}
        {showSpreadsheetLinks && hasValues && doc.school_id && doc.canonical_year && (
          <SpreadsheetDownloadLinks
            schoolId={doc.school_id}
            year={doc.canonical_year}
          />
        )}
      </div>

      {hasValues && (
        <div style={{ marginTop: 16 }}>
          <KeyStats schemaVersion={schemaVersion ?? doc.cds_year ?? undefined} values={values} />
        </div>
      )}

      {admissionStrategy && (
        <AdmissionStrategyCard
          school={admissionStrategy}
          sourceHref={sourceDownloadUrl ?? admissionStrategy.archiveUrl}
        />
      )}

      {/* Federal outcomes — Scorecard data. Only render under the first
          document variant; for schools with sub-institutional variants, the
          Scorecard data is IPEDS-level and identical across them. */}
      {scorecard && !doc.sub_institutional && (
        <div style={{ marginTop: 24 }}>
          <div className="meta">§ Federal outcomes</div>
          <h2 className="serif" style={{ fontSize: 22, fontWeight: 400, margin: "6px 0 0" }}>
            Federal outcomes
          </h2>
          <div style={{ marginTop: 4 }}><ScorecardVintageNote scorecard={scorecard} /></div>
          <div style={{ marginTop: 12 }}>
            <OutcomesBand scorecard={scorecard} />
          </div>
        </div>
      )}

      {hasValues ? (
        <div style={{ marginTop: 24 }}>
          <h3 className="serif" style={{ fontSize: 22, fontWeight: 400, margin: "0 0 16px" }}>
            All extracted fields
          </h3>
          <FieldsView
            schemaVersion={schemaVersion ?? doc.cds_year}
            values={values}
            totalFields={totalFields}
          />
        </div>
      ) : isExtracted ? (
        <div className="cd-card" style={{ marginTop: 16, padding: "24px 28px" }}>
          <p>No structured field values available for this document yet.</p>
        </div>
      ) : (
        <div className="cd-card" style={{ marginTop: 16, padding: "24px 28px" }}>
          <p>
            Structured data coming soon. The source document is available for
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
