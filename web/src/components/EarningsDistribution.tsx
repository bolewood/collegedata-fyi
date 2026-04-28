import type { ScorecardSummary } from "@/lib/types";

// Earnings spread as a flat scale: P25 and P75 are ink dots; the median is a
// larger forest dot; a faint forest band fills the interquartile range.
// Renders only when all three percentiles are present (graceful render
// elsewhere strips the section if the data is missing).
export function EarningsDistribution({
  scorecard,
}: {
  scorecard: ScorecardSummary;
}) {
  const p25 = scorecard.earnings_10yr_p25;
  const p50 = scorecard.earnings_10yr_median;
  const p75 = scorecard.earnings_10yr_p75;
  if (p25 == null || p50 == null || p75 == null) return null;

  // Domain wide enough to hold ~99% of US schools; clamped per-school
  // so visually shorter ranges still read as "tight" rather than "small".
  const domainMin = 15000;
  const domainMax = 85000;
  const min = Math.min(domainMin, p25 - 5000);
  const max = Math.max(domainMax, p75 + 5000);
  const pct = (v: number) => ((v - min) / (max - min)) * 100;

  const ticks = [20000, 40000, 60000, 80000].filter(
    (t) => t >= min && t <= max,
  );

  return (
    <div style={{ position: "relative", height: 120, marginTop: 24 }}>
      <div style={{ position: "relative", height: 44 }}>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 22,
            height: 1,
            background: "var(--rule-strong)",
          }}
        />
        {[p25, p75].map((v, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              top: 17,
              left: `${pct(v)}%`,
              transform: "translateX(-50%)",
              width: 10,
              height: 10,
              background: "var(--ink)",
              borderRadius: "50%",
            }}
          />
        ))}
        <div
          style={{
            position: "absolute",
            top: 16,
            left: `${pct(p25)}%`,
            width: `${pct(p75) - pct(p25)}%`,
            height: 12,
            background: "var(--forest)",
            opacity: 0.22,
            borderRadius: 6,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 12,
            left: `${pct(p50)}%`,
            transform: "translateX(-50%)",
            width: 18,
            height: 18,
            background: "var(--forest)",
            borderRadius: "50%",
            boxShadow: "0 0 0 3px var(--paper)",
          }}
        />
        {[
          { v: p25, label: "P25" },
          { v: p50, label: "Median" },
          { v: p75, label: "P75" },
        ].map((t) => (
          <div
            key={t.label}
            className="cd-earnings-tick"
            style={{
              position: "absolute",
              top: 44,
              left: `${pct(t.v)}%`,
              transform: "translateX(-50%)",
              textAlign: "center",
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: "var(--ink-3)",
                letterSpacing: "0.06em",
              }}
            >
              {t.label.toUpperCase()}
            </div>
            <div className="serif nums cd-earnings-tick__value">
              <span className="cd-earnings-tick__full">
                ${t.v.toLocaleString("en-US")}
              </span>
              <span className="cd-earnings-tick__short">
                ${Math.round(t.v / 1000)}k
              </span>
            </div>
          </div>
        ))}
      </div>
      <div style={{ position: "relative", marginTop: 60, height: 16 }}>
        {ticks.map((v) => (
          <div
            key={v}
            className="mono"
            style={{
              position: "absolute",
              left: `${pct(v)}%`,
              transform: "translateX(-50%)",
              fontSize: 10,
              color: "var(--ink-4)",
              letterSpacing: "0.04em",
            }}
          >
            ${v / 1000}k
          </div>
        ))}
      </div>
    </div>
  );
}
