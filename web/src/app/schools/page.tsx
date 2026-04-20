import type { Metadata } from "next";
import { fetchManifest, aggregateSchools } from "@/lib/queries";
import { SchoolTable } from "@/components/SchoolTable";

export const metadata: Metadata = {
  title: "Schools",
  description:
    "Browse U.S. colleges with archived Common Data Set documents. Search by name, sort by year or document count.",
  alternates: { canonical: "/schools" },
  openGraph: { url: "/schools" },
};

export const revalidate = 3600;

export default async function SchoolsPage() {
  const manifest = await fetchManifest();
  const schools = aggregateSchools(manifest);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">School Directory</h1>
      <p className="text-gray-600 mb-6">
        {schools.length} schools with archived Common Data Set documents.
      </p>
      <SchoolTable schools={schools} />
    </div>
  );
}
