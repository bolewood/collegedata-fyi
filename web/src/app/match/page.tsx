import type { Metadata } from "next";
import { MatchListBuilder } from "@/components/MatchListBuilder";
import { fetchMatchBuilderSchools, fetchBrandColorIndex } from "@/lib/queries";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Match",
  description:
    "Build a college list from the numbers schools publish. On this device. No account. No student profile stored.",
  alternates: { canonical: "/match" },
};

export default async function MatchPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const [{ code }, schools, brandColors] = await Promise.all([
    searchParams,
    fetchMatchBuilderSchools(),
    fetchBrandColorIndex(),
  ]);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 match-page">
      <header className="match-hero">
        <div className="meta">Match</div>
        <h1 className="serif">
          Build a list from the{" "}
          <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>
            school&apos;s own numbers.
          </span>
        </h1>
        <p className="serif" style={{ fontStyle: "italic", fontSize: 18, lineHeight: 1.55 }}>
          Enter scores and GPA — they stay on this device. Filter by fit and
          admit rate. Export a list with the year and the original file. We
          don&apos;t store a student profile.
        </p>
      </header>

      <MatchListBuilder schools={schools} initialCode={code} brandColors={brandColors} />
    </div>
  );
}
