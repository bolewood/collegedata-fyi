import { CHART_MIN_YEARS } from "./AcceptanceRateChart";
import type { GpaTableRow } from "./GpaTable";
import { bandShare, gpa, gpaChartCaption, gpaChartKind } from "@/lib/gpa-copy";
import { shortFall } from "@/lib/acceptance-rate-copy";
import type { GpaHistory } from "@/lib/c11-gpa";

const BAR_MAX_PX = 136;

export function GpaChart({
  schoolName,
  history,
  rows,
}: {
  schoolName: string;
  history: GpaHistory;
  rows: GpaTableRow[];
}) {
  const kind = gpaChartKind(history);
  const slots = [...rows].reverse();
  const values = slots.flatMap((slot) => {
    if (slot.kind !== "year") return [];
    if (kind === "average") return slot.row.average != null ? [slot.row.average] : [];
    return [slot.row.bands.percents.gpa4];
  });
  if (values.length < CHART_MIN_YEARS) return null;
  const ceiling = kind === "average" ? Math.max(4, ...values) : Math.max(...values);
  const label = `${schoolName} enrolled first-year GPA by entering class, oldest first: ${slots
    .map((slot) => {
      if (slot.kind !== "year") return `fall ${slot.yearStart}, not available`;
      if (kind === "average") {
        return slot.row.average != null
          ? `fall ${slot.row.yearStart}, ${gpa(slot.row.average)}`
          : `fall ${slot.row.yearStart}, not printed`;
      }
      return `fall ${slot.row.yearStart}, ${bandShare(slot.row.bands.percents.gpa4)} at 4.0`;
    })
    .join("; ")}.`;

  return (
    <figure className="acc-chart">
      <div className="acc-chart__plot" role="img" aria-label={label}>
        {slots.map((slot) => {
          const yearStart = slot.kind === "year" ? slot.row.yearStart : slot.yearStart;
          const gap = slot.kind === "gap";
          const value =
            slot.kind === "year"
              ? kind === "average"
                ? slot.row.average
                : slot.row.bands.percents.gpa4
              : null;
          const height = value != null ? Math.max(2, Math.round((value / ceiling) * BAR_MAX_PX)) : 0;
          const shown =
            slot.kind !== "year"
              ? "—"
              : kind === "average"
                ? slot.row.average != null
                  ? gpa(slot.row.average)
                  : "—"
                : bandShare(slot.row.bands.percents.gpa4);
          return (
            <div
              key={yearStart}
              className={gap ? "acc-chart__col acc-chart__col--gap" : "acc-chart__col"}
              aria-hidden="true"
            >
              <div className="acc-chart__track">
                <div className="acc-chart__series">
                  <span className="acc-chart__value">{shown}</span>
                  <span
                    className={value != null ? "acc-chart__bar" : "acc-chart__bar acc-chart__bar--empty"}
                    style={{ height }}
                  />
                </div>
              </div>
              <span className="acc-chart__year">{shortFall(yearStart)}</span>
            </div>
          );
        })}
      </div>
      <figcaption className="acc-chart__caption">{gpaChartCaption(history)}</figcaption>
    </figure>
  );
}
