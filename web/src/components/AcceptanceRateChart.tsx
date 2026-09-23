import type { AcceptanceTableRow } from "./AcceptanceRateTable";
import { share } from "@/lib/school-summary";

const BAR_MAX_PX = 96;

/**
 * Column chart of acceptance rate by report year, oldest on the left.
 * Bars start at zero and are scaled to the highest rate shown. Missing
 * years keep their slot so gaps stay visible. The table below carries the
 * same numbers; the chart's accessible name lists them.
 */
export function AcceptanceRateChart({
  schoolName,
  rows,
}: {
  schoolName: string;
  rows: AcceptanceTableRow[];
}) {
  const slots = [...rows].reverse();
  const rates = slots.flatMap((slot) => (slot.kind === "year" ? [slot.row.rate] : []));
  if (rates.length < 2) return null;
  const max = Math.max(...rates);
  const latest = rows.find((slot) => slot.kind === "year");
  const latestYear = latest?.kind === "year" ? latest.row.year : null;
  const label = `${schoolName} acceptance rate by report year, oldest first: ${slots
    .map((slot) =>
      slot.kind === "year" ? `${slot.row.year}, ${share(slot.row.rate)}` : `${slot.year}, no data`,
    )
    .join("; ")}.`;

  return (
    <figure className="acc-chart" style={{ maxWidth: `min(42rem, ${slots.length * 76}px)` }}>
      <div className="acc-chart__plot" role="img" aria-label={label}>
        {slots.map((slot) => {
          const year = slot.kind === "year" ? slot.row.year : slot.year;
          const gap = slot.kind === "gap";
          const height = gap ? 0 : Math.max(2, Math.round((slot.row.rate / max) * BAR_MAX_PX));
          const classes = [
            "acc-chart__col",
            gap ? "acc-chart__col--gap" : "",
            year === latestYear ? "acc-chart__col--latest" : "",
          ].filter(Boolean).join(" ");
          return (
            <div key={year} className={classes} aria-hidden="true">
              <div className="acc-chart__track">
                <span className="acc-chart__value">{gap ? "—" : share(slot.row.rate)}</span>
                <span className="acc-chart__bar" style={{ height }} />
              </div>
              <span className="acc-chart__year">{year.slice(2)}</span>
            </div>
          );
        })}
      </div>
      <figcaption className="acc-chart__caption">
        Acceptance rate by report year. Bars start at zero.
        {slots.some((slot) => slot.kind === "gap") ? " A dash marks a year with no usable report." : ""}
      </figcaption>
    </figure>
  );
}
