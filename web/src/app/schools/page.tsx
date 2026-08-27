import type { Metadata } from "next";
import Link from "next/link";
import { fetchManifest, aggregateSchools, fetchBrandColorIndex } from "@/lib/queries";
import { SchoolTable } from "@/components/SchoolTable";

export const metadata: Metadata = {
  title: "Schools",
  description:
    "Every college with a Common Data Set on file. Open the reports each school published.",
  alternates: { canonical: "/schools" },
  openGraph: { url: "/schools" },
};

export const revalidate = 3600;

export default async function SchoolsPage() {
  const [manifest, brandIndex] = await Promise.all([
    fetchManifest(),
    fetchBrandColorIndex(),
  ]);
  const schools = aggregateSchools(manifest).map((school) => ({
    ...school,
    brand_colors: brandIndex[school.school_id] ?? null,
  }));

  return (
    <div className="mx-auto max-w-5xl" style={{ padding: "52px 24px 72px" }}>
      <header style={{ marginBottom: 28 }}>
        <h1
          className="serif"
          style={{
            fontWeight: 400,
            fontSize: "clamp(42px, 6vw, 68px)",
            lineHeight: 1,
            margin: 0,
            letterSpacing: "-0.02em",
          }}
        >
          Schools
        </h1>
        <p
          className="serif"
          style={{
            margin: "18px 0 0",
            maxWidth: 640,
            fontStyle: "italic",
            fontSize: 18,
            lineHeight: 1.55,
            color: "var(--ink-2)",
          }}
        >
          Every school we have a report from. Don&apos;t see yours? Check{" "}
          <Link href="/coverage">Coverage</Link> — schools without a report still
          get a page with the federal numbers.
        </p>
        <p className="meta" style={{ marginTop: 16 }}>
          {schools.length} schools
        </p>
      </header>
      <SchoolTable schools={schools} />
    </div>
  );
}
