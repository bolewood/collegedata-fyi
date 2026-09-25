import type { AcceptanceTableRow } from "./AcceptanceRateTable";
import { pct, shortFall } from "@/lib/acceptance-rate-copy";

const BAR_MAX_PX = 136;
/** Below this many usable years the table says everything; no chart. */
export const CHART_MIN_YEARS = 4;

/**
 * Column chart of acceptance rate by entering class, oldest on the left.
 * One ink colour by default. When a school reports C21 early-decision
 * counts, a forest bar sits beside each year's overall rate. Bars start at
 * zero, scaled to the highest rate shown (overall or ED). Missing years
 * keep their slot. The table below carries the same numbers.
 */
export function AcceptanceRateChart({
  schoolName,
  rows,
  series = "acceptance",
}: {
  schoolName: string;
  rows: AcceptanceTableRow[];
  series?: "acceptance" | "early-decision";
}) {
  const slots = [...rows].reverse();
  const overall = slots.flatMap((slot) => (slot.kind === "year" ? [slot.row.rate] : []));
  if (overall.length < CHART_MIN_YEARS) return null;
  const showEd = series === "acceptance" && slots.some((slot) => slot.kind === "year" && slot.row.ed != null);
  const edRates = slots.flatMap((slot) => (slot.kind === "year" && slot.row.ed ? [slot.row.ed.rate] : []));
  const max = Math.max(...overall, ...edRates);
  const hasGap = slots.some((slot) => slot.kind === "gap");
  const rateNoun = series === "early-decision" ? "early decision" : "acceptance rate";
  const label = `${schoolName} ${rateNoun} by entering class, oldest first: ${slots
    .map((slot) => {
      if (slot.kind !== "year") return `fall ${slot.yearStart}, not available`;
      const ed = slot.row.ed ? `, early decision ${pct(slot.row.ed.rate)}` : "";
      return `fall ${slot.row.yearStart}, ${pct(slot.row.rate)}${showEd ? ed : ""}`;
    })
    .join("; ")}.`;

  return (
    <figure className="acc-chart">
      <div className="acc-chart__plot" role="img" aria-label={label}>
        {slots.map((slot) => {
          const yearStart = slot.kind === "year" ? slot.row.yearStart : slot.yearStart;
          const gap = slot.kind === "gap";
          const overallHeight =
            slot.kind === "year" ? Math.max(2, Math.round((slot.row.rate / max) * BAR_MAX_PX)) : 0;
          const ed = slot.kind === "year" ? slot.row.ed : null;
          const edHeight = ed ? Math.max(2, Math.round((ed.rate / max) * BAR_MAX_PX)) : 0;
          return (
            <div
              key={yearStart}
              className={gap ? "acc-chart__col acc-chart__col--gap" : "acc-chart__col"}
              aria-hidden="true"
            >
              <div className={showEd ? "acc-chart__track acc-chart__track--pair" : "acc-chart__track"}>
                <div className="acc-chart__series">
                  <span className="acc-chart__value">{slot.kind === "year" ? pct(slot.row.rate) : "—"}</span>
                  <span className="acc-chart__bar" style={{ height: overallHeight }} />
                </div>
                {showEd ? (
                  <div className="acc-chart__series">
                    <span className="acc-chart__value acc-chart__value--ed">
                      {gap || !ed ? "—" : pct(ed.rate)}
                    </span>
                    <span
                      className={ed ? "acc-chart__bar acc-chart__bar--ed" : "acc-chart__bar acc-chart__bar--empty"}
                      style={{ height: edHeight }}
                    />
                  </div>
                ) : null}
              </div>
              <span className="acc-chart__year">{shortFall(yearStart)}</span>
            </div>
          );
        })}
      </div>
      <figcaption className="acc-chart__caption">
        {series === "early-decision"
          ? "Share of early-decision applicants admitted, by fall entering class."
          : showEd
            ? "Dark bars show first-year admission. Olive bars show early decision."
            : "Share of first-year applicants admitted, by fall entering class."}
        {hasGap ? " — = not reported or not usable." : ""}
      </figcaption>
    </figure>
  );
}
