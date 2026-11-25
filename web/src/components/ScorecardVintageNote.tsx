import type { ScorecardSummary } from "@/lib/types";

export function ScorecardVintageNote({
  scorecard,
}: {
  scorecard: ScorecardSummary;
}) {
  return (
    <p
      className="serif"
      style={{
        fontStyle: "italic",
        fontSize: 13,
        color: "var(--ink-3)",
        margin: 0,
        lineHeight: 1.5,
      }}
    >
      Federal data from the U.S. Department of Education&apos;s{" "}
      <a
        href="https://collegescorecard.ed.gov/"
        target="_blank"
        rel="noopener noreferrer"
      >
        College Scorecard
      </a>
      , vintage {scorecard.scorecard_data_year}. Outcomes reflect earlier
      cohorts than the CDS year shown elsewhere on this page.
    </p>
  );
}
