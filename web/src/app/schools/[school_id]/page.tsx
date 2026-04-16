import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchSchoolDocuments } from "@/lib/queries";
import { DocumentCard } from "@/components/DocumentCard";
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

  return {
    title: `${name} - Common Data Set Archive`,
    description: `${docs.length} archived Common Data Set document${docs.length !== 1 ? "s" : ""} for ${name}, ${yearRange(years[0], years[years.length - 1])}.`,
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

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
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
    </div>
  );
}
