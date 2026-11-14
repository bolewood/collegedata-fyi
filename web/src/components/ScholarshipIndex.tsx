"use client";

// PRD 036 M3: the /scholarships table. The default view (all rows, sorted by
// school) renders in the server HTML, so it works without JavaScript; the
// filters and sort enhance it once the page is hydrated.

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  COVERAGE_LABEL,
  EMPTY_FILTERS,
  RESIDENCY_LABEL,
  SELECTION_LABEL,
  SEPARATE_APP_LABEL,
  deadlineCell,
  filterRows,
  freshnessShort,
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

export function ScholarshipIndex({ rows }: { rows: IndexRow[] }) {
  const [filters, setFilters] = useState<ScholarshipFilters>(EMPTY_FILTERS);
  const [sort, setSort] = useState<ScholarshipSort>("school");
  const set = (key: keyof ScholarshipFilters) => (v: string) => setFilters((f) => ({ ...f, [key]: v }));
  const shown = useMemo(() => sortRows(filterRows(rows, filters), sort), [rows, filters, sort]);
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
        <Select id="f-coverage" label="Coverage" value={filters.coverage} onChange={set("coverage")} options={Object.entries(COVERAGE_LABEL)} />
        <Select id="f-selection" label="How recipients are chosen" value={filters.selection} onChange={set("selection")} options={Object.entries(SELECTION_LABEL)} />
        <Select id="f-nm" label="National Merit" value={filters.nationalMerit} onChange={set("nationalMerit")} options={[["semifinalist", "Semifinalist"], ["finalist", "Finalist"]]} />
        <Select id="f-app" label="Separate application" value={filters.separateApplication} onChange={set("separateApplication")} options={Object.entries(SEPARATE_APP_LABEL)} />
        <Select id="f-month" label="Deadline month" value={filters.deadlineMonth} onChange={set("deadlineMonth")} options={MONTHS.map((m, i) => [String(i + 1), m])} />
        <Select id="f-res" label="Residency" value={filters.residency} onChange={set("residency")} options={Object.entries(RESIDENCY_LABEL)} />
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
          <table className="sch-table">
            <thead>
              <tr>
                <th>School</th>
                <th>Program</th>
                <th>What it covers</th>
                <th>Chosen how</th>
                <th>Deadline</th>
                <th>Terms as of</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => {
                const fresh = freshnessShort(row);
                return (
                  <tr key={`${row.program_id}-${row.school_id}`}>
                    <td data-label="School">
                      <Link href={`/schools/${row.school_id}#scholarships`}>{row.school_name}</Link>
                    </td>
                    <td data-label="Program">
                      {row.official_name}
                      <div className="sch-sources mono">
                        {row.sources.slice(0, 2).map((s) => (
                          <a key={s.source_id} href={s.url} target="_blank" rel="noopener noreferrer">
                            {sourceLabel(s.authority)}
                          </a>
                        ))}
                      </div>
                    </td>
                    <td data-label="What it covers">
                      {row.coverages.length === 0 ? (
                        <span className="sch-muted">Not stated</span>
                      ) : (
                        row.coverages.map((c) => (
                          <span key={c} className="cd-chip sch-chip">{COVERAGE_LABEL[c] ?? c}</span>
                        ))
                      )}
                    </td>
                    <td data-label="Chosen how">
                      {(() => {
                        const known = row.selection_modes.filter((m) => SELECTION_LABEL[m]);
                        return known.length === 0
                          ? <span className="sch-muted">Not stated</span>
                          : known.map((m) => SELECTION_LABEL[m]).join(", ");
                      })()}
                    </td>
                    <td data-label="Deadline" className="nums">{deadlineCell(row)}</td>
                    <td data-label="Terms as of" className={fresh.tone === "amber" ? "sch-amber" : undefined}>
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
        Dates are the schools&rsquo; own and may have passed. Confirm on the official page. Not a ranking: rows are
        sorted by the field you choose, never by how generous a program is.
      </p>
    </div>
  );
}
