import Link from "next/link";
import { tierLabel, type Caveat } from "@/lib/positioning";
import type { RankedMatchSchool } from "@/lib/list-builder";

function formatPercent(value: number | null): string {
  if (value == null) return "n/a";
  return `${Math.round(value * 100)}%`;
}

function formatPercentile(value: number | null): string {
  if (value == null) return "n/a";
  return `${value}th`;
}

function caveatLabel(caveat: Caveat): string {
  switch (caveat) {
    case "low_sat_submit_rate":
      return "low SAT submit rate";
    case "student_not_submitting":
      return "no score entered";
    case "stale_cds":
      return "stale CDS";
    case "sub_15_admit_rate_suppression":
      return "tier suppressed";
    case "no_sat_data":
      return "no SAT";
    case "no_act_data":
      return "no ACT";
    case "no_test_data":
      return "no test data";
    case "data_incomplete":
      return "incomplete data";
  }
}

export function SchoolListItem({ school }: { school: RankedMatchSchool }) {
  const caveats = school.result.caveats
    .filter((caveat) =>
      ["low_sat_submit_rate", "stale_cds", "sub_15_admit_rate_suppression", "data_incomplete"].includes(caveat),
    )
    .slice(0, 2);

  return (
    <article className="match-school-row rule">
      <div className="match-school-row__identity">
        <div className="match-school-row__name">
          <Link href={school.schoolUrl}>{school.schoolName}</Link>
        </div>
        <div className="match-school-row__meta mono">
          {school.state ?? "state n/a"} · {school.cdsYear} CDS · admit {formatPercent(school.acceptanceRate)}
        </div>
      </div>

      <div className="match-school-row__metrics">
        <div>
          <span className="mono">Tier</span>
          <strong>{tierLabel(school.result.tier)}</strong>
        </div>
        <div>
          <span className="mono">Best pct</span>
          <strong>{formatPercentile(school.bestPercentile)}</strong>
        </div>
        <div>
          <span className="mono">SAT mid</span>
          <strong>{school.satCompositeP50 ?? "n/a"}</strong>
        </div>
        <div>
          <span className="mono">ACT mid</span>
          <strong>{school.actCompositeP50 ?? "n/a"}</strong>
        </div>
      </div>

      <div className="match-school-row__actions">
        <span className="cd-chip">{school.control.replace(/_/g, " ")}</span>
        {caveats.map((caveat) => (
          <span key={caveat} className="cd-chip cd-chip--ochre">
            {caveatLabel(caveat)}
          </span>
        ))}
        {school.archiveUrl ? (
          <a href={school.archiveUrl} target="_blank" rel="noopener noreferrer" className="match-source-link mono">
            source
          </a>
        ) : null}
      </div>
    </article>
  );
}
