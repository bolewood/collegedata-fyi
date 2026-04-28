import type { ScorecardSummary } from "@/lib/types";
import { formatCurrency } from "@/lib/format";

type Bracket = {
  label: string;
  field: keyof ScorecardSummary;
  low: number;
  high: number;
};

const BRACKETS: Bracket[] = [
  { label: "$0 – $30,000", field: "net_price_0_30k", low: 0, high: 30000 },
  { label: "$30,001 – $48,000", field: "net_price_30k_48k", low: 30001, high: 48000 },
  { label: "$48,001 – $75,000", field: "net_price_48k_75k", low: 48001, high: 75000 },
  { label: "$75,001 – $110,000", field: "net_price_75k_110k", low: 75001, high: 110000 },
  { label: "$110,001 and up", field: "net_price_110k_plus", low: 110001, high: Infinity },
];

// Horizontal bars of average net price (sticker minus grants) per income
// bracket. Bars are ink; the bracket containing the school's median family
// income is highlighted in forest as the modal bracket. Bar widths are scaled
// to the row max so spread reads cleanly for both progressive and flat
// pricing.
export function NetPriceByIncome({
  scorecard,
}: {
  scorecard: ScorecardSummary;
}) {
  const mfi = scorecard.median_family_income;
  const rows = BRACKETS.map((b) => ({
    label: b.label,
    value: scorecard[b.field] as number | null,
    isModal: mfi != null && mfi >= b.low && mfi <= b.high,
  })).filter((r) => r.value != null);

  if (rows.length === 0) return null;

  const max = Math.max(...rows.map((r) => r.value as number));

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
        }}
      >
        <div>
          <div className="meta" style={{ marginBottom: 6 }}>
            §H · Net price by family income
          </div>
          <h3
            className="serif"
            style={{ fontSize: 22, margin: 0, letterSpacing: "-0.01em" }}
          >
            Average cost after grants
          </h3>
        </div>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          CDS H2A · {scorecard.scorecard_data_year}
        </div>
      </div>

      <div className="rule-2" style={{ marginTop: 20, paddingTop: 14 }}>
        {rows.map((r, i) => {
          const widthPct = max > 0 ? Math.max(4, ((r.value as number) / max) * 100) : 0;
          return (
            <div
              key={r.label}
              className="cd-price-row"
              style={{
                alignItems: "center",
                padding: "14px 0",
                borderBottom:
                  i === rows.length - 1
                    ? "none"
                    : "1px dashed var(--rule)",
              }}
            >
              <span
                className="cd-price-band"
                style={{ fontSize: 14, color: "var(--ink-2)" }}
              >
                {r.label}
              </span>
              <div
                className="cd-price-bar"
                style={{
                  height: 18,
                  background: "var(--paper-2)",
                  position: "relative",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    right: "auto",
                    width: `${widthPct}%`,
                    background: r.isModal ? "var(--forest)" : "var(--ink)",
                  }}
                />
              </div>
              <span
                className="mono cd-price-marker"
                aria-hidden={!r.isModal}
                style={{
                  fontSize: 10.5,
                  color: "var(--forest)",
                  letterSpacing: "0.05em",
                  whiteSpace: "nowrap",
                  visibility: r.isModal ? "visible" : "hidden",
                }}
              >
                ← MODAL BRACKET
              </span>
              <span
                className="mono nums cd-price-value"
                style={{ fontSize: 14, textAlign: "right" }}
              >
                {formatCurrency(r.value)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
