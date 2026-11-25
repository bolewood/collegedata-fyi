import type { Metadata } from "next";
import { MatchListBuilder } from "@/components/MatchListBuilder";
import { fetchMatchBuilderSchools, fetchBrandColorIndex } from "@/lib/queries";

// Hourly ISR. Do not read searchParams here — that opts /match out of
// static generation and re-runs the school query on every share-link hit.
export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Match",
  description:
    "Build a college list from each school’s published admissions and test-score data. Runs locally in your browser with no account and no stored student profile.",
  alternates: { canonical: "/match" },
  // Generic on purpose (PRD 024 M1): never put a Match code or any profile
  // value in preview metadata.
  openGraph: {
    title: "CollegeData.fyi Match List Builder",
    description: "Build a college match list from the numbers schools publish.",
    url: "/match",
    siteName: "collegedata.fyi",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "CollegeData.fyi Match List Builder",
    description: "Build a college match list from the numbers schools publish.",
  },
};

export default async function MatchPage() {
  const [schools, brandColors] = await Promise.all([
    fetchMatchBuilderSchools(),
    fetchBrandColorIndex(),
  ]);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 match-page">
      <header className="match-hero">
        <div className="meta">Match</div>
        <h1 className="serif">
          Build your college list from published numbers
        </h1>
        <p className="serif" style={{ fontStyle: "italic", fontSize: 18, lineHeight: 1.55 }}>
          Enter your test scores and GPA to see schools grouped by academic fit,
          narrow the list by region, school type, admit rate, or test policy,
          and export your results with links to each school's original
          report. Everything stays in your browser; we never save a student
          profile.
        </p>
      </header>

      <MatchListBuilder schools={schools} brandColors={brandColors} />
    </div>
  );
}
