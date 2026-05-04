import type { Metadata } from "next";
import { MatchListBuilder } from "@/components/MatchListBuilder";
import { fetchMatchBuilderSchools } from "@/lib/queries";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Match List Builder",
  description:
    "Build a college match list from Common Data Set score bands, academic fit, admit rates, and archived source documents.",
  alternates: { canonical: "/match" },
};

export default async function MatchPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const [{ code }, schools] = await Promise.all([searchParams, fetchMatchBuilderSchools()]);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 match-page">
      <header className="match-hero">
        <div className="meta">Match list builder</div>
        <h1 className="serif">Build a school list from source-backed admissions data.</h1>
        <p>
          Enter one profile, filter the corpus, and export a counselor-friendly list with academic
          fit, admissions outlook, percentile, admit rate, CDS year, and source PDF.
        </p>
      </header>

      <MatchListBuilder schools={schools} initialCode={code} />
    </div>
  );
}
