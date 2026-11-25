"use client";

// PRD 036 M3: the /scholarships table. The default view (all rows, sorted by
// school) renders in the server HTML, so it works without JavaScript; the
// filters and sort enhance it once the page is hydrated.

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  COVERAGE_LABEL,
  EMPTY_FILTERS,
  NOT_STATED,
  RESIDENCY_LABEL,
  SELECTION_LABEL,
  SEPARATE_APP_LABEL,
  closedLabel,
  deadlineCell,
  filterRows,
  freshnessShort,
  selectionCell,
  sortRows,
  sourceLabel,
  type IndexRow,
  type ScholarshipFilters,
  type ScholarshipSort,
} from "@/lib/scholarships";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function Select({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <label className="sch-filter" htmlFor={id}>
      <span className="meta">{label}</span>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Any</option>
        {options.map(([v, text]) => (
          <option key={v} value={v}>{text}</option>
        ))}
      </select>
    </label>
  );
}

const notStated = (entries: [string, string][]): [string, string][] => [...entries, [NOT_STATED, "Not stated"]];

export function ScholarshipIndex({ rows, today }: { rows: IndexRow[]; today: string }) {
  const [filters, setFilters] = useState<ScholarshipFilters>(EMPTY_FILTERS);
  const [sort, setSort] = useState<ScholarshipSort>("school");
  const set = (key: keyof ScholarshipFilters) => (v: string) => setFilters((f) => ({ ...f, [key]: v }));
  const shown = useMemo(() => sortRows(filterRows(rows, filters), sort, today), [rows, filters, sort, today]);
  const active = Object.values(filters).some(Boolean);

  if (rows.length === 0) {
    return (
      <p className="sch-empty">
        No programs are documented yet. The list is partial and is being added to.
      </p>
    );
  }

  return (
    <div>
      <form className="sch-filters" onSubmit={(e) => e.preventDefault()} aria-label="Filters and sort">
        <Select id="f-coverage" label="Coverage" value={filters.coverage} onChange={set("coverage")} options={notStated(Object.entries(COVERAGE_LABEL))} />
        <Select id="f-selection" label="How recipients are chosen" value={filters.selection} onChange={set("selection")} options={notStated(Object.entries(SELECTION_LABEL))} />
        <Select id="f-nm" label="National Merit" value={filters.nationalMerit} onChange={set("nationalMerit")} options={[["semifinalist", "Semifinalist"], ["finalist", "Finalist"]]} />
        <Select id="f-app" label="Separate application" value={filters.separateApplication} onChange={set("separateApplication")} options={notStated(Object.entries(SEPARATE_APP_LABEL))} />
        <Select id="f-month" label="Deadline month" value={filters.deadlineMonth} onChange={set("deadlineMonth")} options={notStated(MONTHS.map((m, i): [string, string] => [String(i + 1), m]))} />
        <Select id="f-res" label="Residency" value={filters.residency} onChange={set("residency")} options={notStated(Object.entries(RESIDENCY_LABEL))} />
        <label className="sch-filter" htmlFor="f-school">
          <span className="meta">School</span>
          <input id="f-school" type="search" placeholder="School name" value={filters.school} onChange={(e) => set("school")(e.target.value)} />
        </label>
        <label className="sch-filter" htmlFor="f-sort">
          <span className="meta">Sort by</span>
          <select id="f-sort" value={sort} onChange={(e) => setSort(e.target.value as ScholarshipSort)}>
            <option value="school">School name</option>
            <option value="deadline">Deadline (soonest first)</option>
            <option value="coverage">Coverage (grouped)</option>
          </select>
        </label>
        {active ? (
          <button type="button" className="cd-btn cd-btn--ghost sch-clear" onClick={() => setFilters(EMPTY_FILTERS)}>
            Clear filters
          </button>
        ) : null}
      </form>

      <p className="sch-count mono" aria-live="polite">
        Showing {shown.length} of {rows.length} listings. A program shared by two schools is listed once for each.
      </p>

      {shown.length === 0 ? (
        <p className="sch-empty">No programs match these filters. The list is partial, so try fewer filters.</p>
      ) : (
        <div className="sch-table-wrap">
          <table className="sch-table" role="table">
            <thead role="rowgroup">
              <tr role="row">
                <th role="columnheader">School</th>
                <th role="columnheader">Program</th>
                <th role="columnheader">What it covers</th>
                <th role="columnheader">Chosen how</th>
                <th role="columnheader">Deadline</th>
                <th role="columnheader">Terms as of</th>
              </tr>
            </thead>
            <tbody role="rowgroup">
              {shown.map((row) => {
                const fresh = freshnessShort(row);
                const closed = closedLabel(row);
                const deadline = deadlineCell(row, today);
                return (
                  <tr key={`${row.program_id}-${row.school_id}`} role="row">
                    <td role="cell" data-label="School">
                      <Link href={`/schools/${row.school_id}#scholarships`}>{row.school_name}</Link>
                    </td>
                    <td role="cell" data-label="Program">
                      {row.official_name}
                      {closed ? <span className="cd-chip sch-chip sch-chip--status">{closed}</span> : null}
                      <div className="sch-sources mono">
                        {row.sources.map((src) => (
                          <a
                            key={src.source_id}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`${row.official_name}: ${sourceLabel(src.authority).replace(" ↗", "")} (opens in a new tab)`}
                          >
                            {sourceLabel(src.authority)}
                          </a>
                        ))}
                      </div>
                    </td>
                    <td role="cell" data-label="What it covers">
                      {row.coverages.length === 0 ? (
                        <span className="sch-muted">Not stated</span>
                      ) : (
                        row.coverages.map((c) =>
                          c === "other" ? (
                            <Link key={c} href={`/schools/${row.school_id}#scholarship-${row.program_id}`} className="cd-chip sch-chip">
                              See details
                            </Link>
                          ) : (
                            <span key={c} className="cd-chip sch-chip">{COVERAGE_LABEL[c] ?? c}</span>
                          ),
                        )
                      )}
                    </td>
                    <td role="cell" data-label="Chosen how">{selectionCell(row.selection_modes)}</td>
                    <td role="cell" data-label="Deadline" className={deadline.past ? "nums sch-amber" : "nums"}>
                      {deadline.text}
                    </td>
                    <td role="cell" data-label="Terms as of" className={fresh.tone === "amber" ? "sch-amber" : undefined}>
                      {fresh.text}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="sch-fine">
        Dates are the schools’ own and may have passed. Confirm on the official page. Not a ranking: rows are
        sorted by the field you choose, never by how generous a program is.
      </p>
    </div>
  );
}
