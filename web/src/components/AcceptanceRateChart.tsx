import type { AcceptanceTableRow } from "./AcceptanceRateTable";
import { pct, shortFall } from "@/lib/acceptance-rate-copy";

const BAR_MAX_PX = 136;
/** Below this many usable years the table says everything; no chart. */
export const CHART_MIN_YEARS = 4;

/**
 * Column chart of acceptance rate by entering class, oldest on the left.
 * One ink colour; bars start at zero, scaled to the highest rate shown.
 * Missing years keep their slot so gaps stay visible. The accessible name
 * lists every value; the table below carries the same numbers.
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
  if (rates.length < CHART_MIN_YEARS) return null;
  const max = Math.max(...rates);
  const hasGap = slots.some((slot) => slot.kind === "gap");
  const label = `${schoolName} acceptance rate by entering class, oldest first: ${slots
    .map((slot) =>
      slot.kind === "year"
        ? `fall ${slot.row.yearStart}, ${pct(slot.row.rate)}`
        : `fall ${slot.yearStart}, not available`,
    )
    .join("; ")}.`;

  return (
    <figure className="acc-chart">
      <div className="acc-chart__plot" role="img" aria-label={label}>
        {slots.map((slot) => {
          const yearStart = slot.kind === "year" ? slot.row.yearStart : slot.yearStart;
          const gap = slot.kind === "gap";
          const height = gap ? 0 : Math.max(2, Math.round((slot.row.rate / max) * BAR_MAX_PX));
          return (
            <div
              key={yearStart}
              className={gap ? "acc-chart__col acc-chart__col--gap" : "acc-chart__col"}
              aria-hidden="true"
            >
              <div className="acc-chart__track">
                <span className="acc-chart__value">{gap ? "—" : pct(slot.row.rate)}</span>
                <span className="acc-chart__bar" style={{ height }} />
              </div>
              <span className="acc-chart__year">{shortFall(yearStart)}</span>
            </div>
          );
        })}
      </div>
      <figcaption className="acc-chart__caption">
        Share of first-year applicants admitted, by fall entering class.
        {hasGap ? " — = not available." : ""}
      </figcaption>
    </figure>
  );
}
