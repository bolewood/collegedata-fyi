import type { ScorecardSummary } from "@/lib/types";
import { formatCurrency, formatPercent } from "@/lib/format";

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-xl font-semibold text-gray-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

// Compact 4-card headline for federal Scorecard outcomes. Null fields drop
// out, so a small school that doesn't report to Scorecard renders fewer
// cards instead of a row of dashes.
export function OutcomesBand({ scorecard }: { scorecard: ScorecardSummary }) {
  const cards: { label: string; value: string; hint?: string }[] = [];

  if (scorecard.earnings_10yr_median != null) {
    cards.push({
      label: "Median earnings",
      value: formatCurrency(scorecard.earnings_10yr_median),
      hint: "10 years after enrollment",
    });
  }
  if (scorecard.graduation_rate_6yr != null) {
    cards.push({
      label: "Graduation rate",
      value: formatPercent(scorecard.graduation_rate_6yr, 0),
      hint: "6-year completion",
    });
  }
  if (scorecard.avg_net_price != null) {
    cards.push({
      label: "Average net price",
      value: formatCurrency(scorecard.avg_net_price),
      hint: "Sticker minus grants",
    });
  }
  if (scorecard.median_debt_completers != null) {
    cards.push({
      label: "Median debt at graduation",
      value: formatCurrency(scorecard.median_debt_completers),
      hint: "Federal loans only",
    });
  }

  if (cards.length === 0) return null;

  // Tailwind JIT requires literal class names — can't interpolate grid cols.
  // Pick the right class based on card count; 4 is the cap.
  const colClass =
    cards.length >= 4
      ? "sm:grid-cols-4"
      : cards.length === 3
        ? "sm:grid-cols-3"
        : cards.length === 2
          ? "sm:grid-cols-2"
          : "sm:grid-cols-1";

  return (
    <div className={`grid grid-cols-2 gap-3 ${colClass}`}>
      {cards.map((c) => (
        <StatCard key={c.label} {...c} />
      ))}
    </div>
  );
}
