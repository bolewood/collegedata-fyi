import type { ScorecardSummary } from "@/lib/types";
import { formatPercent } from "@/lib/format";
import { OutcomesBand } from "./OutcomesBand";
import { NetPriceByIncome } from "./NetPriceByIncome";
import { EarningsDistribution } from "./EarningsDistribution";

function SmallKpi({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="meta" style={{ marginBottom: 4 }}>
        {label}
      </div>
      <div
        className="serif stat-num"
        style={{ fontSize: 26, lineHeight: 1, letterSpacing: "-0.02em" }}
      >
        {value}
      </div>
    </div>
  );
}

type Stat = { label: string; value: string };

// Full federal-outcomes section for the school landing page. Composes the
// 4-cell headline band, earnings spread, net-price-by-income widget, and
// the completion / retention strip. Every grid filters out null fields so
// the section shrinks gracefully for schools with partial Scorecard data.
export function OutcomesSection({
  scorecard,
}: {
  scorecard: ScorecardSummary;
}) {
  const completion: Stat[] = [];
  if (scorecard.graduation_rate_4yr != null)
    completion.push({
      label: "4-yr grad",
      value: formatPercent(scorecard.graduation_rate_4yr, 0),
    });
  if (scorecard.graduation_rate_6yr != null)
    completion.push({
      label: "6-yr grad",
      value: formatPercent(scorecard.graduation_rate_6yr, 0),
    });
  if (scorecard.graduation_rate_8yr != null)
    completion.push({
      label: "8-yr grad",
      value: formatPercent(scorecard.graduation_rate_8yr, 0),
    });
  if (scorecard.retention_rate_ft != null)
    completion.push({
      label: "Retention",
      value: formatPercent(scorecard.retention_rate_ft, 0),
    });
  if (scorecard.grad_rate_pell != null)
    completion.push({
      label: "Pell grad",
      value: formatPercent(scorecard.grad_rate_pell, 0),
    });
  if (scorecard.transfer_out_rate != null)
    completion.push({
      label: "Transfer",
      value: formatPercent(scorecard.transfer_out_rate, 0),
    });

  const hasEarnings =
    scorecard.earnings_10yr_p25 != null &&
    scorecard.earnings_10yr_median != null &&
    scorecard.earnings_10yr_p75 != null;

  return (
    <>
      <section style={{ marginTop: 56 }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: 24,
            flexWrap: "wrap",
          }}
        >
          <div>
            <div className="meta" style={{ marginBottom: 6 }}>
              § Federal outcomes
            </div>
            <h2
              className="serif"
              style={{ fontSize: 32, margin: 0, letterSpacing: "-0.015em" }}
            >
              What federal data says
            </h2>
          </div>
          <div
            className="mono"
            style={{
              fontSize: 11,
              color: "var(--ink-3)",
              letterSpacing: "0.05em",
              textAlign: "right",
              maxWidth: 360,
              lineHeight: 1.5,
            }}
          >
            SRC · U.S. DEPT. OF ED., COLLEGE SCORECARD{" "}
            {scorecard.scorecard_data_year}.<br />
            OUTCOMES LAG THE CDS YEAR SHOWN ABOVE.
          </div>
        </div>

        <OutcomesBand scorecard={scorecard} />
      </section>

      {hasEarnings && (
        <section style={{ marginTop: 48 }}>
          <div className="meta" style={{ marginBottom: 6 }}>
            § Earnings distribution
          </div>
          <h3
            className="serif"
            style={{ fontSize: 22, margin: 0, letterSpacing: "-0.01em" }}
          >
            Ten years after enrollment, in {scorecard.scorecard_data_year}{" "}
            dollars
          </h3>
          <EarningsDistribution scorecard={scorecard} />
        </section>
      )}

      <section style={{ marginTop: 48 }}>
        <NetPriceByIncome scorecard={scorecard} />
      </section>

      {completion.length > 0 && (
        <section style={{ marginTop: 48 }}>
          <div className="meta" style={{ marginBottom: 6 }}>
            §B · Completion and retention
          </div>
          <div
            className="rule-2"
            style={{
              marginTop: 14,
              paddingTop: 20,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              gap: 24,
            }}
          >
            {completion.map((s) => (
              <SmallKpi key={s.label} {...s} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
