import type { ScorecardSummary } from "@/lib/types";
import type { FsaNonpaymentCurrent } from "@/lib/types";
import { formatCurrency, formatPercent } from "@/lib/format";

function Kpi({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div>
      <div className="meta" style={{ marginBottom: 8 }}>
        {label}
      </div>
      <div
        className="serif stat-num"
        style={{ fontSize: 34, lineHeight: 1, letterSpacing: "-0.02em" }}
      >
        {value}
      </div>
      {hint && (
        <div
          className="mono"
          style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 6 }}
        >
          {hint}
        </div>
      )}
    </div>
  );
}

function nonpaymentHint(row: FsaNonpaymentCurrent): string {
  const asOf = row.as_of_label || row.as_of_date;
  return `FSA · as-of ${asOf} · not the official cohort default rate`;
}

// Compact headline for federal outcomes. Null fields drop out. Render when
// Scorecard or a current FSA nonpayment row exists.
export function OutcomesBand({
  scorecard,
  nonpayment,
}: {
  scorecard?: ScorecardSummary | null;
  nonpayment?: FsaNonpaymentCurrent | null;
}) {
  const cards: { label: string; value: string; hint?: string }[] = [];

  if (scorecard?.earnings_10yr_median != null) {
    cards.push({
      label: "Median earnings",
      value: formatCurrency(scorecard.earnings_10yr_median),
      hint: "10 yrs after enrollment",
    });
  }
  if (scorecard?.graduation_rate_6yr != null) {
    cards.push({
      label: "Graduation rate",
      value: formatPercent(scorecard.graduation_rate_6yr, 0),
      hint: "6-year completion",
    });
  }
  if (scorecard?.avg_net_price != null) {
    cards.push({
      label: "Average net price",
      value: formatCurrency(scorecard.avg_net_price),
      hint: "sticker minus grants",
    });
  }
  if (scorecard?.median_debt_completers != null) {
    cards.push({
      label: "Median debt at grad.",
      value: formatCurrency(scorecard.median_debt_completers),
      hint: "federal loans only",
    });
  }
  if (nonpayment?.nonpayment_rate != null) {
    cards.push({
      label: "Nonpayment",
      value: formatPercent(nonpayment.nonpayment_rate, 0),
      hint: nonpaymentHint(nonpayment),
    });
  }

  if (cards.length === 0) return null;

  return (
    <div
      className="rule-2 outcomes-band"
      style={{
        marginTop: 20,
        paddingTop: 24,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
        gap: 32,
      }}
    >
      {cards.map((c) => (
        <Kpi key={c.label} {...c} />
      ))}
    </div>
  );
}
