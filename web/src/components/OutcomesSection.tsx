import type { ScorecardSummary } from "@/lib/types";
import { formatCurrency, formatPercent } from "@/lib/format";
import { OutcomesBand } from "./OutcomesBand";
import { NetPriceByIncome } from "./NetPriceByIncome";
import { ScorecardVintageNote } from "./ScorecardVintageNote";

function MiniCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-gray-200 bg-white px-3 py-2">
      <p className="text-[11px] text-gray-500 uppercase tracking-wide">
        {label}
      </p>
      <p className="mt-0.5 text-base font-semibold text-gray-900">{value}</p>
    </div>
  );
}

type Stat = { label: string; value: string };

// Full federal-outcomes section for the school landing page. Composes the
// compact 4-card band, the net-price-by-income widget, and two secondary
// stat grids (completion / retention, and student profile). Every grid
// filters out null fields so the section shrinks gracefully for schools
// with partial data.
export function OutcomesSection({
  scorecard,
}: {
  scorecard: ScorecardSummary;
}) {
  const completion: Stat[] = [];
  if (scorecard.graduation_rate_4yr != null)
    completion.push({
      label: "4-year grad",
      value: formatPercent(scorecard.graduation_rate_4yr, 0),
    });
  if (scorecard.graduation_rate_6yr != null)
    completion.push({
      label: "6-year grad",
      value: formatPercent(scorecard.graduation_rate_6yr, 0),
    });
  if (scorecard.graduation_rate_8yr != null)
    completion.push({
      label: "8-year grad",
      value: formatPercent(scorecard.graduation_rate_8yr, 0),
    });
  if (scorecard.retention_rate_ft != null)
    completion.push({
      label: "Retention (FT)",
      value: formatPercent(scorecard.retention_rate_ft, 0),
    });
  if (scorecard.grad_rate_pell != null)
    completion.push({
      label: "Pell grad rate",
      value: formatPercent(scorecard.grad_rate_pell, 0),
    });
  if (scorecard.transfer_out_rate != null)
    completion.push({
      label: "Transfer out",
      value: formatPercent(scorecard.transfer_out_rate, 0),
    });

  const profile: Stat[] = [];
  if (scorecard.pell_grant_rate != null)
    profile.push({
      label: "Pell recipients",
      value: formatPercent(scorecard.pell_grant_rate, 0),
    });
  if (scorecard.federal_loan_rate != null)
    profile.push({
      label: "With federal loans",
      value: formatPercent(scorecard.federal_loan_rate, 0),
    });
  if (scorecard.first_generation_share != null)
    profile.push({
      label: "First-generation",
      value: formatPercent(scorecard.first_generation_share, 0),
    });
  if (scorecard.median_family_income != null)
    profile.push({
      label: "Median family income",
      value: formatCurrency(scorecard.median_family_income),
    });
  if (scorecard.enrollment != null)
    profile.push({
      label: "Undergraduate enrollment",
      value: scorecard.enrollment.toLocaleString("en-US"),
    });

  const earningsRange: Stat[] = [];
  if (scorecard.earnings_10yr_p25 != null)
    earningsRange.push({
      label: "25th percentile",
      value: formatCurrency(scorecard.earnings_10yr_p25),
    });
  if (scorecard.earnings_10yr_median != null)
    earningsRange.push({
      label: "Median",
      value: formatCurrency(scorecard.earnings_10yr_median),
    });
  if (scorecard.earnings_10yr_p75 != null)
    earningsRange.push({
      label: "75th percentile",
      value: formatCurrency(scorecard.earnings_10yr_p75),
    });

  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold text-gray-900">Federal outcomes</h2>
      <ScorecardVintageNote scorecard={scorecard} className="mt-1" />

      <div className="mt-5">
        <OutcomesBand scorecard={scorecard} />
      </div>

      {earningsRange.length >= 2 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-gray-900">
            Earnings distribution, 10 years after enrollment
          </h3>
          <p className="mt-1 text-xs text-gray-500">
            Federal-worker-and-not-enrolled cohort, reported in{" "}
            {scorecard.scorecard_data_year} dollars.
          </p>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {earningsRange.map((s) => (
              <MiniCard key={s.label} {...s} />
            ))}
          </div>
        </div>
      )}

      <div className="mt-6">
        <NetPriceByIncome scorecard={scorecard} />
      </div>

      {completion.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-gray-900">
            Completion and retention
          </h3>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {completion.map((s) => (
              <MiniCard key={s.label} {...s} />
            ))}
          </div>
        </div>
      )}

      {profile.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-gray-900">
            Student profile
          </h3>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {profile.map((s) => (
              <MiniCard key={s.label} {...s} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
