import type { ScorecardSummary } from "@/lib/types";
import type { FsaNonpaymentCurrent } from "@/lib/types";
import { formatCurrency, formatPercent } from "@/lib/format";

function Kpi({
  label,
  value,
  hint,
  sourceTag,
}: {
  label: string;
  value: string;
  hint?: string;
  sourceTag: string;
}) {
  return (
    <div className="cd-outcomes-band__cell">
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 8,
          marginBottom: 6,
        }}
      >
        <div className="meta">{label}</div>
        <span
          className="mono"
          style={{
            fontSize: 10,
            color: "var(--ink-3)",
            letterSpacing: "0.06em",
          }}
        >
          {sourceTag}
        </span>
      </div>
      <div
        className="serif stat-num nums"
        style={{ fontSize: 30, lineHeight: 1.05, letterSpacing: "-0.02em" }}
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
  return `as-of ${asOf} · not the official cohort default rate`;
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
  const cards: { label: string; value: string; hint?: string; sourceTag: string }[] = [];

  if (scorecard?.earnings_10yr_median != null) {
    cards.push({
      label: "Median earnings",
      value: formatCurrency(scorecard.earnings_10yr_median),
      hint: "10 yrs after enrollment",
      sourceTag: "SCORECARD",
    });
  }
  if (scorecard?.graduation_rate_6yr != null) {
    cards.push({
      label: "Graduation rate",
      value: formatPercent(scorecard.graduation_rate_6yr, 0),
      hint: "6-year completion",
      sourceTag: "SCORECARD",
    });
  }
  if (scorecard?.avg_net_price != null) {
    cards.push({
      label: "Average net price",
      value: formatCurrency(scorecard.avg_net_price),
      hint: "sticker minus grants",
      sourceTag: "SCORECARD",
    });
  }
  if (scorecard?.median_debt_completers != null) {
    cards.push({
      label: "Median debt at grad.",
      value: formatCurrency(scorecard.median_debt_completers),
      hint: "federal loans only",
      sourceTag: "SCORECARD",
    });
  }
  if (nonpayment?.nonpayment_rate != null) {
    cards.push({
      label: "Nonpayment",
      value: formatPercent(nonpayment.nonpayment_rate, 0),
      hint: nonpaymentHint(nonpayment),
      sourceTag: "FSA",
    });
  }

  if (cards.length === 0) return null;

  return (
    <div
      className="rule-2 outcomes-band"
      style={{
        marginTop: 16,
        paddingTop: 18,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(156px, 1fr))",
        gap: "18px 24px",
      }}
    >
      {cards.map((c) => (
        <Kpi key={c.label} {...c} />
      ))}
    </div>
  );
}
