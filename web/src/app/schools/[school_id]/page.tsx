import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  fetchSchoolDocuments,
  fetchScorecardByIpedsId,
} from "@/lib/queries";
import { DocumentCard } from "@/components/DocumentCard";
import { OutcomesSection } from "@/components/OutcomesSection";
import { yearRange } from "@/lib/format";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ school_id: string }>;
}): Promise<Metadata> {
  const { school_id } = await params;
  const docs = await fetchSchoolDocuments(school_id);
  if (docs.length === 0) return { title: "School Not Found" };

  const name = docs[0].school_name;
  const years = docs
    .map((d) => d.canonical_year)
    .filter((y): y is string => y != null)
    .sort();
  const path = `/schools/${school_id}`;
  const description = `${docs.length} archived Common Data Set document${docs.length !== 1 ? "s" : ""} for ${name}, ${yearRange(years[0], years[years.length - 1])}.`;

  return {
    title: `${name} - Common Data Set Archive`,
    description,
    alternates: { canonical: path },
    openGraph: { url: path, title: `${name} - Common Data Set Archive`, description },
  };
}

export default async function SchoolDetailPage({
  params,
}: {
  params: Promise<{ school_id: string }>;
}) {
  const { school_id } = await params;
  const docs = await fetchSchoolDocuments(school_id);

  if (docs.length === 0) {
    notFound();
  }

  // Every cds_documents row for a school carries the same ipeds_id, so we
  // only need the first one. Scorecard data is per-school-per-vintage, not
  // per-document, so one query returns everything.
  const ipedsId = docs.find((d) => d.ipeds_id)?.ipeds_id ?? null;
  const scorecard = await fetchScorecardByIpedsId(ipedsId);

  const name = docs[0].school_name;
  const years = docs
    .map((d) => d.canonical_year)
    .filter((y): y is string => y != null)
    .sort();

  // Check if this school has sub-institutional variants
  const hasSubs = docs.some((d) => d.sub_institutional != null);

  // Group by sub_institutional if applicable
  const groups: { label: string | null; docs: typeof docs }[] = [];
  if (hasSubs) {
    const subMap = new Map<string | null, typeof docs>();
    for (const doc of docs) {
      const key = doc.sub_institutional;
      const group = subMap.get(key) ?? [];
      group.push(doc);
      subMap.set(key, group);
    }
    for (const [label, groupDocs] of subMap) {
      groups.push({ label, docs: groupDocs });
    }
  } else {
    groups.push({ label: null, docs });
  }

  const schoolUrl = `https://www.collegedata.fyi/schools/${school_id}`;
  const uniqueYears = Array.from(new Set(years));

  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "CollegeOrUniversity",
      name,
      url: schoolUrl,
      description: `Common Data Set archive for ${name}. ${docs.length} document${docs.length !== 1 ? "s" : ""} archived${years.length > 0 ? `, ${yearRange(years[0], years[years.length - 1])}` : ""}.`,
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Schools", item: "https://www.collegedata.fyi/schools" },
        { "@type": "ListItem", position: 2, name, item: schoolUrl },
      ],
    },
    // DataCatalog enumerates every archived year as a Dataset reference.
    // Gives LLMs and search engines a one-stop index of what's in the archive
    // for this school.
    {
      "@context": "https://schema.org",
      "@type": "DataCatalog",
      name: `${name} Common Data Set archive`,
      url: schoolUrl,
      description: `Every archived Common Data Set year for ${name}, keyed to the canonical 1,105-field schema published by the Common Data Set Initiative.`,
      creator: { "@type": "Organization", name, url: schoolUrl },
      provider: { "@type": "Organization", name: "collegedata.fyi", url: "https://www.collegedata.fyi" },
      isAccessibleForFree: true,
      license: "https://opensource.org/licenses/MIT",
      dataset: uniqueYears.map((year) => ({
        "@type": "Dataset",
        name: `${name} Common Data Set ${year}`,
        url: `https://www.collegedata.fyi/schools/${school_id}/${year}`,
        temporalCoverage: year,
      })),
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
      <h1 className="text-2xl font-bold text-gray-900">{name}</h1>
      <p className="text-gray-600 mt-1">
        {docs.length} document{docs.length !== 1 ? "s" : ""} archived
        {years.length > 0 && `, ${yearRange(years[0], years[years.length - 1])}`}
      </p>

      {groups.map((group) => (
        <div key={group.label ?? "main"} className="mt-6">
          {group.label && (
            <h2 className="text-lg font-semibold text-gray-800 mb-3">
              {group.label}
            </h2>
          )}
          <div className="space-y-2">
            {group.docs.map((doc) => (
              <DocumentCard key={doc.document_id} doc={doc} />
            ))}
          </div>
        </div>
      ))}

      {scorecard ? (
        <OutcomesSection scorecard={scorecard} />
      ) : ipedsId ? (
        <p className="mt-10 text-sm text-gray-500">
          Federal outcomes data is not available for this institution.
        </p>
      ) : null}
    </div>
  );
}
