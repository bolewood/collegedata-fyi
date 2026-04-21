import type { ScorecardSummary } from "@/lib/types";

export function ScorecardVintageNote({
  scorecard,
  className = "",
}: {
  scorecard: ScorecardSummary;
  className?: string;
}) {
  return (
    <p className={`text-xs italic text-gray-500 ${className}`}>
      Federal data from the U.S. Department of Education&apos;s{" "}
      <a
        href="https://collegescorecard.ed.gov/"
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-gray-700"
      >
        College Scorecard
      </a>
      , vintage {scorecard.scorecard_data_year}. Outcomes reflect earlier
      cohorts than the CDS year shown elsewhere on this page.
    </p>
  );
}
