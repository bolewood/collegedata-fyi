import type { ScorecardSummary } from "@/lib/types";
import { formatCurrency } from "@/lib/format";

type Bracket = {
  label: string;
  field: keyof ScorecardSummary;
};

const BRACKETS: Bracket[] = [
  { label: "$0 – $30,000", field: "net_price_0_30k" },
  { label: "$30,001 – $48,000", field: "net_price_30k_48k" },
  { label: "$48,001 – $75,000", field: "net_price_48k_75k" },
  { label: "$75,001 – $110,000", field: "net_price_75k_110k" },
  { label: "$110,001 and up", field: "net_price_110k_plus" },
];

// Horizontal bars of the average net price (sticker minus grants) paid by
// enrolled students at each family-income bracket. Bar width is relative to
// the school's own max bracket so the spread is legible both for schools
// with progressive pricing (Harvard: $2K → $53K) and flat pricing (most
// state universities). Hides entirely if no brackets have data.
export function NetPriceByIncome({
  scorecard,
}: {
  scorecard: ScorecardSummary;
}) {
  const rows = BRACKETS.map((b) => ({
    label: b.label,
    value: scorecard[b.field] as number | null,
  })).filter((r) => r.value != null);

  if (rows.length === 0) return null;

  const max = Math.max(...rows.map((r) => r.value as number));

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-gray-900">
          Net price by family income
        </h3>
        <p className="text-xs text-gray-500">Average cost after grants</p>
      </div>
      <dl className="mt-4 space-y-2.5">
        {rows.map((r) => {
          const widthPct =
            max > 0 ? Math.max(4, ((r.value as number) / max) * 100) : 0;
          return (
            <div key={r.label} className="flex items-center gap-3 text-sm">
              <dt className="w-40 shrink-0 text-gray-600">{r.label}</dt>
              <div className="relative h-5 flex-1 overflow-hidden rounded bg-gray-100">
                <div
                  className="h-full rounded bg-blue-500"
                  style={{ width: `${widthPct}%` }}
                />
              </div>
              <dd className="w-20 shrink-0 text-right font-medium text-gray-900">
                {formatCurrency(r.value)}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
